#!/usr/bin/env python3
"""
Audio Looper System - SD Card Optimized Version

Minimizes write operations to the SD card for longer storage lifespan.
"""

import logging
import sys
import time
import signal
import threading

from audio_loop.audio.manager import AudioManager
from audio_loop.config import load_config, validate_runtime_requirements
from audio_loop.core.looper_engine import LooperEngine
from audio_loop.web.stats_server import run_stats_server
from audio_loop.stats.collector import StatsCollector
from audio_loop.infra.logging_setup import setup_logging
from audio_loop.infra.watchdog import (
    WATCHDOG_INTERVAL,
    notify_ready,
    send_watchdog,
)


setup_logging()
logger = logging.getLogger(__name__)


class AudioLooper:
    """Top-level application class optimized for SD card longevity.

    Orchestrates all subsystems (audio, buttons, logic, stats) and runs
    the main application loop with periodic health checks and watchdog pings.
    """

    def __init__(self):
        """Initialize the application and all subsystem components."""
        self.config = load_config()
        validate_runtime_requirements(self.config)

        self.audio_manager = None
        self.looper_engine = None
        self.input_handler = None
        self.modbus_bus = None
        self.led_controller = None
        self.stats_server_thread = None
        self.stats_collector = None

        self.running = False

        # Throttle status log entries to reduce SD card writes.
        self.last_status_log = 0
        self.status_log_interval = 600  # Log system status every 10 minutes.

        # Periodic audio stream health check.
        self.last_health_check = 0
        self.health_check_interval = 60  # Check stream every 60 seconds.

        # Systemd watchdog ping tracking.
        self.last_watchdog = 0

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self._initialize_components()

    def _initialize_components(self):
        """Instantiate all subsystem components and wire them together.

        A single ``StatsCollector`` instance is created here and passed
        to both ``LooperEngine`` and ``run_stats_server`` so all parts of
        the system share one in-memory stats store.
        """
        try:
            # Create one shared StatsCollector instance that is injected into
            # all components that need it, avoiding duplicated counters.
            self.stats_collector = StatsCollector()

            self.audio_manager = AudioManager(self.config)

            self.modbus_bus = self._create_modbus_bus()
            self.led_controller = self._create_led_controller(self.modbus_bus)

            self.looper_engine = LooperEngine(
                self.audio_manager,
                self.config,
                self.stats_collector,
                led_controller=self.led_controller
            )

            self.input_handler = self._create_input_handler(self.modbus_bus)

            # Pass the shared stats_collector so the server reads from RAM.
            self.stats_server_thread = threading.Thread(
                target=run_stats_server,
                args=(
                    self.config['stats_server']['host'],
                    self.config['stats_server']['port'],
                    self.stats_collector
                ),
                daemon=True
            )
        except Exception as e:
            logger.error(
                f"Critical component initialization failed: {e}"
            )
            self.shutdown(exit_code=1)

    def _create_modbus_bus(self):
        """Create the shared Modbus bus for DIN inputs and LED outputs."""
        input_config = self.config.get('inputs', {})
        provider = input_config.get('provider', 'modbus_panel')
        output_config = self.config.get('outputs', {})
        output_provider = output_config.get('provider', 'modbus_panel')

        if provider == 'modbus_panel' or output_provider == 'modbus_panel':
            from audio_loop.hardware.modbus_bus import ModbusBus

            return ModbusBus(self.config)

        return None

    def _create_led_controller(self, modbus_bus):
        """Create optional best-effort LED output provider."""
        output_config = self.config.get('outputs', {})
        if not output_config.get('enabled', True):
            return None

        provider = output_config.get('provider', 'modbus_panel')
        if provider == 'modbus_panel':
            from audio_loop.output.led_panel import ModbusLedController

            return ModbusLedController(self.config, bus=modbus_bus)

        raise RuntimeError(f"Unsupported output provider: {provider}")

    def _create_input_handler(self, modbus_bus):
        """Create the configured physical input provider.

        ``modbus_panel`` is the production path and is cross-platform.
        """
        input_config = self.config.get('inputs', {})
        provider = input_config.get('provider')

        if provider is None:
            # The production default is the external Modbus panel.
            provider = 'modbus_panel'

        if provider == 'modbus_panel':
            from audio_loop.input.modbus_panel import ModbusButtonHandler

            return ModbusButtonHandler(
                self.looper_engine.handle_button_press,
                self.config,
                bus=modbus_bus
            )

        raise RuntimeError(f"Unsupported input provider: {provider}")

    def _signal_handler(self, signum, frame):
        """Initiate a graceful shutdown in response to OS signals.

        Args:
            signum: Signal number received (e.g. SIGTERM, SIGINT).
            frame: Current stack frame (unused).
        """
        logger.warning(f"Received signal {signum}, initiating shutdown.")
        self.shutdown()

    def run(self):
        """Start all subsystems and enter the main application loop.

        The loop runs at 1-second intervals and performs:
        - Periodic statistics save (every 5 minutes)
        - Audio stream health check (every 60 seconds)
        - Systemd watchdog ping (every 25 seconds)
        - System status log (every 10 minutes, only when active)
        """
        logger.warning("Starting SD-Optimized Audio Looper System")

        try:
            if hasattr(self.audio_manager, 'get_current_song_info'):
                song_info = self.audio_manager.get_current_song_info()
                logger.warning(f"Initial song: {song_info['name']}")

            self.looper_engine.start()
            if self.led_controller:
                self.led_controller.start()
            self.input_handler.start()
            self.stats_server_thread.start()
            self.running = True

            # Notify systemd that the service is fully initialised.
            notify_ready()

            loop_counter = 0
            while self.running:
                current_time = time.time()
                loop_counter += 1

                # Periodic stats flush: every 300 loop iterations (~5 min).
                if loop_counter % 300 == 0:
                    if hasattr(self.stats_collector, 'periodic_save'):
                        self.stats_collector.periodic_save()

                # Audio stream health check every 60 seconds.
                if (current_time - self.last_health_check
                        > self.health_check_interval):
                    if hasattr(self.audio_manager, 'check_stream_health'):
                        self.audio_manager.check_stream_health()
                    self.last_health_check = current_time

                # Systemd watchdog keep-alive ping.
                if (current_time - self.last_watchdog
                        > WATCHDOG_INTERVAL):
                    send_watchdog()
                    self.last_watchdog = current_time

                # Throttled status log: only when system is active.
                if (current_time - self.last_status_log
                        > self.status_log_interval):
                    if hasattr(self.looper_engine, 'get_system_status'):
                        status = self.looper_engine.get_system_status()
                        if status['system_active']:
                            logger.warning(
                                f"System active - Song: "
                                f"{status['current_song']['name']}, "
                                f"Active instruments: "
                                f"{len(status['active_instruments'])}"
                            )
                    self.last_status_log = current_time

                time.sleep(1)

        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            self.shutdown(exit_code=1)

    def shutdown(self, exit_code: int = 0):
        """Gracefully stop all subsystems and exit the process.

        Saves any pending statistics before stopping components, ensuring
        no usage data is lost on shutdown.

        Args:
            exit_code: Process exit code passed to ``sys.exit()``.
        """
        logger.warning("Shutting down SD-Optimized Audio Looper System...")
        self.running = False

        # Flush pending stats before stopping other components.
        if hasattr(self, 'stats_collector') and self.stats_collector:
            try:
                self.stats_collector.force_save()
            except Exception as e:
                logger.error(f"Failed to save stats on shutdown: {e}")

        if hasattr(self, 'input_handler') and self.input_handler:
            self.input_handler.stop()
        if hasattr(self, 'looper_engine') and self.looper_engine:
            self.looper_engine.shutdown()
        if hasattr(self, 'led_controller') and self.led_controller:
            self.led_controller.stop()
        if hasattr(self, 'modbus_bus') and self.modbus_bus:
            self.modbus_bus.close()
        if hasattr(self, 'audio_manager') and self.audio_manager:
            self.audio_manager.shutdown()

        logger.warning("Shutdown complete.")
        sys.exit(exit_code)


def main():
    """Entry point: construct the application and start the main loop."""
    try:
        app = AudioLooper()
        app.run()
    except FileNotFoundError as e:
        print("\nSETUP ERROR:")
        print(f"{e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

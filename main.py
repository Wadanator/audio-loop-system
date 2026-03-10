#!/usr/bin/env python3
"""
Audio Looper System - SD Card Optimized Version

Minimizes write operations to the SD card for longer storage lifespan.
"""

import sys
import os
import logging
import time
import signal
import json
import threading

from audio_manager import AudioManager
from button_handler import UniversalButtonHandler
from looper_engine import LooperEngine
from stats_server import run_stats_server
from stats_collector import StatsCollector
from logging_setup import setup_logging


setup_logging()
logger = logging.getLogger(__name__)

# Interval in seconds between systemd watchdog keep-alive pings.
_WATCHDOG_INTERVAL = 25


def _send_watchdog():
    """Send a WATCHDOG=1 notification to systemd if sdnotify is available.

    Uses a graceful fallback: if the ``sdnotify`` package is not installed,
    the call is silently skipped so the rest of the system is unaffected.
    The watchdog is only active when the service is running under systemd
    with ``WatchdogSec`` set in the unit file.
    """
    try:
        import sdnotify
        n = sdnotify.SystemdNotifier()
        n.notify("WATCHDOG=1")
    except ImportError:
        pass  # sdnotify not installed; watchdog pings are silently skipped.
    except Exception as e:
        logger.warning(f"Watchdog notify failed: {e}")


class AudioLooper:
    """Top-level application class optimized for SD card longevity.

    Orchestrates all subsystems (audio, buttons, logic, stats) and runs
    the main application loop with periodic health checks and watchdog pings.
    """

    def __init__(self):
        """Initialize the application and all subsystem components."""
        self._check_requirements()
        self.config = self._load_config()

        self.audio_manager = None
        self.looper_engine = None
        self.button_handler = None
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

    def _check_requirements(self):
        """Verify that all required files and directories are present.

        Raises:
            FileNotFoundError: If ``config.json``, ``audio_files/``, or the
                expected WAV file structure is missing.
        """
        if not os.path.exists("config.json"):
            raise FileNotFoundError("config.json required but not found")

        if not os.path.exists("audio_files"):
            raise FileNotFoundError(
                "audio_files/ directory required but not found"
            )

        try:
            with open("config.json", 'r') as f:
                config = json.load(f)
        except Exception as e:
            raise FileNotFoundError(f"Could not read config.json: {e}")

        song_rotation_config = config.get('song_rotation', {})

        if song_rotation_config.get('enable', False):
            self._check_song_folders(config)
        else:
            self._check_direct_wav_files()

    def _check_song_folders(self, config):
        """Verify that at least one configured song subfolder contains WAV files.

        Args:
            config: Parsed configuration dictionary.

        Raises:
            FileNotFoundError: If no valid song folder is found.
        """
        song_config = config.get('song_rotation', {})
        base_dir = song_config.get('base_directory', 'audio_files')
        song_folders = song_config.get('song_folders', ['song1'])

        found_valid_songs = False

        for song_name in song_folders:
            if song_name == 'default':
                song_path = base_dir
            else:
                song_path = os.path.join(base_dir, song_name)

            if os.path.exists(song_path) and os.path.isdir(song_path):
                wav_files = [
                    f for f in os.listdir(song_path) if f.endswith('.wav')
                ]
                if wav_files:
                    found_valid_songs = True

        if not found_valid_songs:
            raise FileNotFoundError("No valid song folders found!")

    def _check_direct_wav_files(self):
        """Verify that at least one WAV file exists in the audio_files directory.

        Raises:
            FileNotFoundError: If the directory contains no WAV files.
        """
        wav_files = [
            f for f in os.listdir("audio_files") if f.endswith('.wav')
        ]
        if not wav_files:
            raise FileNotFoundError(
                "No .wav files found in audio_files/ directory"
            )

    def _load_config(self) -> dict:
        """Read and parse the application configuration file.

        Returns:
            Parsed configuration dictionary.
        """
        with open("config.json", 'r') as f:
            return json.load(f)

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

            self.looper_engine = LooperEngine(
                self.audio_manager, self.config, self.stats_collector
            )

            self.button_handler = UniversalButtonHandler(
                self.looper_engine.handle_button_press,
                self.config
            )

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
            self.button_handler.start()
            self.stats_server_thread.start()
            self.running = True

            # Notify systemd that the service is fully initialised.
            try:
                import sdnotify
                sdnotify.SystemdNotifier().notify("READY=1")
            except ImportError:
                pass

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
                        > _WATCHDOG_INTERVAL):
                    _send_watchdog()
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

        if hasattr(self, 'button_handler') and self.button_handler:
            self.button_handler.stop()
        if hasattr(self, 'looper_engine') and self.looper_engine:
            self.looper_engine.shutdown()
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
        print(f"\n❌ SETUP ERROR:")
        print(f"{e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
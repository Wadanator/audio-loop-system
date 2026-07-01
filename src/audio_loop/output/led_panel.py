"""Best-effort Modbus DO controller for DIN button LEDs."""

import logging
import queue
import threading
import time
from typing import Dict, Iterable, Optional, Tuple

from audio_loop.hardware.modbus_bus import ModbusBus


logger = logging.getLogger(__name__)


class ModbusLedController:
    """Mirror active audio layers to Modbus DO outputs.

    Public methods enqueue work and return quickly so LED communication cannot
    block audio state changes in the looper engine.
    """

    def __init__(self, config: dict, bus: Optional[ModbusBus] = None):
        outputs_config = config.get("outputs", {})
        provider = outputs_config.get("provider", "modbus_panel")
        self.enabled = bool(outputs_config.get("enabled", True))
        self.enabled = self.enabled and provider == "modbus_panel"

        self.bus = bus or ModbusBus(config)
        self.owns_bus = bus is None
        self.instrument_outputs: Dict[int, Tuple[str, int]] = (
            self.bus.get_output_mappings()
        )

        self.commands: "queue.Queue[tuple]" = queue.Queue(maxsize=100)
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False
        self.last_output_state: Dict[int, bool] = {}
        self.last_error: Optional[str] = None
        self.last_error_at: float = 0.0
        self.last_error_log_at: float = 0.0
        self.error_log_interval = float(
            config.get("modbus_panel", {}).get("error_log_interval_seconds", 600)
        )

    def start(self):
        """Start the background LED worker and clear all configured LEDs."""
        if not self.enabled:
            logger.info("Modbus LED controller disabled")
            return
        if self.running:
            return

        self.running = True
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="modbus-led-controller",
            daemon=True,
        )
        self.worker_thread.start()
        self.set_all(False, force=True)
        logger.info(
            "Modbus LED controller started for %s output(s)",
            len(self.instrument_outputs),
        )

    def stop(self):
        """Turn all configured LEDs off and stop the worker."""
        if not self.enabled:
            if self.owns_bus:
                self.bus.close()
            return

        if not self.running:
            try:
                self._apply_all(False, force=True)
            except Exception as exc:
                self._record_error(str(exc))
            if self.owns_bus:
                self.bus.close()
            return

        self.set_all(False, force=True)
        self._enqueue(("stop",))
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        self.running = False

        if self.owns_bus:
            self.bus.close()
        logger.info("Modbus LED controller stopped")

    def set_layer_active(self, instrument: int, active: bool):
        """Set one layer LED to match its active state."""
        if not self.enabled:
            return
        if instrument not in self.instrument_outputs:
            logger.debug("No LED mapping for instrument %s", instrument)
            return
        self._enqueue(("instrument", int(instrument), bool(active), False))

    def set_all(self, active: bool, force: bool = False):
        """Set every configured LED to the same state."""
        if not self.enabled:
            return
        self._enqueue(("all", bool(active), bool(force)))

    def sync_from_active_layers(self, active_layers: Iterable[int]):
        """Sync every configured LED from the complete active layer list."""
        if not self.enabled:
            return
        self._enqueue(("sync", tuple(int(layer) for layer in active_layers)))

    def get_status(self):
        return {
            "enabled": self.enabled,
            "mapped_outputs": self.instrument_outputs.copy(),
            "last_output_state": self.last_output_state.copy(),
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
        }

    def _enqueue(self, command: tuple):
        try:
            self.commands.put_nowait(command)
        except queue.Full:
            self._record_error("LED command queue is full")

    def _worker_loop(self):
        while True:
            command = self.commands.get()
            try:
                kind = command[0]
                if kind == "stop":
                    break
                if kind == "instrument":
                    _, instrument, active, force = command
                    self._apply_instrument_state(instrument, active, force)
                elif kind == "all":
                    _, active, force = command
                    self._apply_all(active, force)
                elif kind == "sync":
                    _, active_layers = command
                    self._apply_sync(active_layers)
            except Exception as exc:
                self._record_error(str(exc))
            finally:
                self.commands.task_done()

        # Last best-effort clear before the worker exits.
        try:
            self._apply_all(False, force=True)
        except Exception as exc:
            self._record_error(str(exc))

    def _apply_all(self, active: bool, force: bool):
        for instrument in sorted(self.instrument_outputs):
            self._apply_instrument_state(instrument, active, force)

    def _apply_sync(self, active_layers: Iterable[int]):
        active_set = set(active_layers)
        for instrument in sorted(self.instrument_outputs):
            self._apply_instrument_state(
                instrument,
                instrument in active_set,
                force=False,
            )

    def _apply_instrument_state(
        self,
        instrument: int,
        active: bool,
        force: bool,
    ):
        if not force and self.last_output_state.get(instrument) == active:
            return

        module_name, channel = self.instrument_outputs[instrument]
        self.bus.write_output(module_name, channel, active)
        self.last_output_state[instrument] = active
        logger.debug(
            "LED state updated: instrument %s -> %s DO%s=%s",
            instrument,
            module_name,
            channel,
            int(active),
        )

    def _record_error(self, message: str):
        previous_error = self.last_error
        self.last_error = message
        now = time.time()
        self.last_error_at = now
        if (
            message != previous_error
            or now - self.last_error_log_at >= self.error_log_interval
        ):
            logger.warning("Modbus LED update failed: %s", message)
            self.last_error_log_at = now

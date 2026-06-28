"""Modbus TCP button handler for Waveshare IO 8CH modules.

Reads DIN button states through the shared ModbusBus and emits one audio button
event on each debounced rising edge. The handler does not own raw pymodbus
clients when the main app injects a bus, so DI polling and DO LED writes stay
synchronized per box.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from modbus_bus import ModbusBus, ModbusBusError


logger = logging.getLogger(__name__)


ChannelKey = Tuple[str, int]


@dataclass
class _ChannelState:
    """Debounce state for one physical DI channel."""

    raw: bool
    stable: bool
    changed_at: float
    last_trigger_at: float = 0.0


class ModbusButtonHandler:
    """Poll external Modbus DI modules and dispatch instrument button events."""

    def __init__(
        self,
        callback: Callable[[int], None],
        config: dict,
        bus: Optional[ModbusBus] = None,
    ):
        if not callable(callback):
            raise TypeError("Provided callback is not callable")

        self.callback = callback
        self.config = config.get("modbus_panel", {})
        if not self.config.get("enabled", False):
            raise RuntimeError("modbus_panel input provider is not enabled")

        self.poll_interval = self.config.get("poll_interval_ms", 75) / 1000.0
        self.debounce_time = self.config.get("debounce_time_ms", 80) / 1000.0
        self.min_press_duration = (
            self.config.get("min_press_duration_ms", 10) / 1000.0
        )
        self.double_press_protection = (
            self.config.get("double_press_protection_ms", 250) / 1000.0
        )

        self.bus = bus or ModbusBus(config)
        self.owns_bus = bus is None
        self.input_mappings = self.bus.get_input_mappings()
        if not self.input_mappings:
            raise RuntimeError("modbus_panel has no input mappings")

        self.channel_states: Dict[ChannelKey, _ChannelState] = {}
        self.running = False
        self.poll_thread: Optional[threading.Thread] = None

    def start(self):
        """Start polling all configured Modbus modules."""
        if self.running:
            logger.warning("Modbus button handler already running")
            return

        self.running = True
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        logger.info(
            "Modbus button handler started for %s module(s)",
            len(self.input_mappings),
        )

    def stop(self):
        """Stop polling and close the bus if this handler created it."""
        if not self.running:
            if self.owns_bus:
                self.bus.close()
            return

        logger.info("Stopping Modbus button handler...")
        self.running = False
        if self.poll_thread and self.poll_thread.is_alive():
            self.poll_thread.join(timeout=2.0)
        if self.owns_bus:
            self.bus.close()
        logger.info("Modbus button handler stopped.")

    def _poll_loop(self):
        while self.running:
            for module_name, channel_map in self.input_mappings.items():
                self._poll_module(module_name, channel_map)
            time.sleep(self.poll_interval)

    def _poll_module(self, module_name: str, channel_map: Dict[int, int]):
        try:
            bits = self.bus.read_inputs(module_name)
        except ModbusBusError as exc:
            logger.debug("Skipping Modbus module %s: %s", module_name, exc)
            return
        except Exception as exc:
            logger.warning("Unexpected Modbus input error on %s: %s", module_name, exc)
            return

        for channel, instrument in channel_map.items():
            self._process_channel(module_name, channel, bits[channel - 1], instrument)

    def _process_channel(
        self,
        module_name: str,
        channel: int,
        current: bool,
        instrument: int,
    ):
        now = time.time()
        key = (module_name, channel)
        state = self.channel_states.get(key)

        if state is None:
            self.channel_states[key] = _ChannelState(
                raw=current,
                stable=current,
                changed_at=now,
            )
            return

        if current != state.raw:
            state.raw = current
            state.changed_at = now
            return

        if state.raw == state.stable:
            return

        stable_for = now - state.changed_at
        if stable_for < max(self.debounce_time, self.min_press_duration):
            return

        previous_stable = state.stable
        state.stable = state.raw

        if state.stable and not previous_stable:
            if now - state.last_trigger_at < self.double_press_protection:
                logger.debug(
                    "Ignoring rapid Modbus press on %s DI%s",
                    module_name,
                    channel,
                )
                return

            state.last_trigger_at = now
            logger.info(
                "Modbus press detected: %s DI%s -> instrument %s",
                module_name,
                channel,
                instrument,
            )
            threading.Thread(
                target=self.callback,
                args=(instrument,),
                daemon=True,
            ).start()

    def get_button_status(self):
        """Return a compact diagnostic snapshot for future web/status use."""
        return {
            "mappings": {
                module_name: channel_map.copy()
                for module_name, channel_map in self.input_mappings.items()
            },
            "bus": self.bus.get_status(),
        }
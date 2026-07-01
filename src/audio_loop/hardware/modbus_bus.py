"""Shared Modbus TCP access for the DIN IO panel.

This module owns the pymodbus clients so input polling and LED writes do not
race each other on the same TCP connection. There is one client and one lock
per configured box/IP address.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from pymodbus.client import ModbusTcpClient
except ImportError as exc:  # pragma: no cover - exercised on missing install.
    ModbusTcpClient = None
    _PYMODBUS_IMPORT_ERROR = exc
else:
    _PYMODBUS_IMPORT_ERROR = None


logger = logging.getLogger(__name__)


class ModbusBusError(RuntimeError):
    """Raised when a Modbus module cannot currently satisfy a read/write."""


@dataclass
class _ModuleRuntime:
    name: str
    host: str
    port: int
    unit_id: int
    input_channel_to_instrument: Dict[int, int]
    output_instrument_to_channel: Dict[int, int]
    client: object
    lock: threading.Lock
    connected: bool = False
    failure_count: int = 0
    next_retry_at: float = 0.0
    last_error_log_at: float = 0.0
    last_success_at: float = 0.0
    last_error: Optional[str] = None


class ModbusBus:
    """Synchronized Modbus TCP bus for all configured DIN boxes."""

    def __init__(self, config: dict):
        if _PYMODBUS_IMPORT_ERROR is not None:
            raise RuntimeError(
                "pymodbus is required for the modbus_panel provider. "
                "Install it with: pip install pymodbus"
            ) from _PYMODBUS_IMPORT_ERROR

        self.config = config.get("modbus_panel", {})
        if not self.config.get("enabled", False):
            raise RuntimeError("modbus_panel is not enabled")

        self.timeout = self.config.get("timeout_seconds", 2)
        self.error_log_interval = float(
            self.config.get(
                "error_log_interval_seconds",
                self.config.get("status_log_interval_seconds", 600),
            )
        )
        self.default_port = int(self.config.get("port", 4196))
        self.modules = self._build_modules()
        if not self.modules:
            raise RuntimeError("modbus_panel.modules must contain at least one module")

    def _build_modules(self) -> Dict[str, _ModuleRuntime]:
        modules = {}
        for index, module_cfg in enumerate(self.config.get("modules", []), start=1):
            name = module_cfg.get("name", f"module_{index}")
            host = module_cfg.get("host")
            if not host:
                raise RuntimeError(f"modbus_panel module {name!r} is missing host")
            if name in modules:
                raise RuntimeError(f"Duplicate modbus_panel module name: {name}")

            input_map = {}
            output_map = {}
            for channel_cfg in module_cfg.get("channels", []):
                channel = int(channel_cfg["channel"])
                instrument = int(channel_cfg["instrument"])
                if not 1 <= channel <= 8:
                    raise RuntimeError(
                        f"Invalid channel {channel} in modbus module {name}"
                    )
                input_map[channel] = instrument
                output_map[instrument] = channel

            port = int(module_cfg.get("port", self.default_port))
            modules[name] = _ModuleRuntime(
                name=name,
                host=host,
                port=port,
                unit_id=int(module_cfg.get("unit_id", 1)),
                input_channel_to_instrument=input_map,
                output_instrument_to_channel=output_map,
                client=ModbusTcpClient(host, port=port, timeout=self.timeout),
                lock=threading.Lock(),
            )
        return modules

    def get_input_mappings(self) -> Dict[str, Dict[int, int]]:
        """Return module -> DI channel -> instrument mappings."""
        return {
            name: module.input_channel_to_instrument.copy()
            for name, module in self.modules.items()
        }

    def get_output_mappings(self) -> Dict[int, Tuple[str, int]]:
        """Return instrument -> (module name, DO channel) mappings."""
        mappings = {}
        for module in self.modules.values():
            for instrument, channel in module.output_instrument_to_channel.items():
                mappings[instrument] = (module.name, channel)
        return mappings

    def read_inputs(self, module_name: str) -> List[bool]:
        """Read all 8 DI channels from one module."""
        module = self._get_module(module_name)
        with module.lock:
            if not self._ensure_connected_locked(module):
                raise ModbusBusError(
                    f"Modbus module {module.name} is not connected"
                )

            try:
                result = self._read_discrete_inputs_locked(module)
                bits = self._validate_bits(result)
            except Exception as exc:
                self._mark_disconnected_locked(module, exc)
                raise ModbusBusError(str(exc)) from exc

            self._mark_success_locked(module)
            return bits

    def write_output(self, module_name: str, channel: int, state: bool):
        """Write one DO coil on one module."""
        if not 1 <= channel <= 8:
            raise ValueError(f"Invalid DO channel: {channel}")

        module = self._get_module(module_name)
        with module.lock:
            if not self._ensure_connected_locked(module):
                raise ModbusBusError(
                    f"Modbus module {module.name} is not connected"
                )

            try:
                result = self._write_coil_locked(module, channel, state)
                is_error = getattr(result, "isError", None)
                if callable(is_error) and is_error():
                    raise RuntimeError(f"Modbus DO write error: {result}")
            except Exception as exc:
                self._mark_disconnected_locked(module, exc)
                raise ModbusBusError(str(exc)) from exc

            self._mark_success_locked(module)

    def set_instrument_output(self, instrument: int, state: bool):
        """Write the configured DO output for one audio instrument."""
        for module in self.modules.values():
            channel = module.output_instrument_to_channel.get(instrument)
            if channel is not None:
                self.write_output(module.name, channel, state)
                return
        raise KeyError(f"No Modbus output mapping for instrument {instrument}")

    def get_status(self):
        """Return a diagnostic snapshot of each module."""
        status = {}
        for name, module in self.modules.items():
            with module.lock:
                status[name] = {
                    "host": module.host,
                    "port": module.port,
                    "unit_id": module.unit_id,
                    "connected": module.connected,
                    "last_success_at": module.last_success_at,
                    "last_error": module.last_error,
                    "next_retry_at": module.next_retry_at,
                    "failure_count": module.failure_count,
                    "input_channels": module.input_channel_to_instrument.copy(),
                    "output_channels": module.output_instrument_to_channel.copy(),
                }
        return status

    def close(self):
        """Close all Modbus TCP clients."""
        for module in self.modules.values():
            with module.lock:
                try:
                    module.client.close()
                except Exception as exc:
                    logger.debug(
                        "Error closing Modbus client %s: %s",
                        module.name,
                        exc,
                    )
                module.connected = False

    def _get_module(self, module_name: str) -> _ModuleRuntime:
        module = self.modules.get(module_name)
        if module is None:
            raise KeyError(f"Unknown Modbus module: {module_name}")
        return module

    def _ensure_connected_locked(self, module: _ModuleRuntime) -> bool:
        if module.connected:
            return True

        now = time.time()
        if now < module.next_retry_at:
            return False

        try:
            module.connected = bool(module.client.connect())
        except Exception as exc:
            self._schedule_retry_locked(module, exc)
            return False

        if module.connected:
            module.failure_count = 0
            module.last_error = None
            logger.info(
                "Connected to Modbus module %s at %s:%s",
                module.name,
                module.host,
                module.port,
            )
            return True

        self._schedule_retry_locked(module, "connect returned False")
        return False

    def _read_discrete_inputs_locked(self, module: _ModuleRuntime):
        try:
            return module.client.read_discrete_inputs(
                address=0,
                count=8,
                device_id=module.unit_id,
            )
        except TypeError:
            return module.client.read_discrete_inputs(
                address=0,
                count=8,
                slave=module.unit_id,
            )

    def _write_coil_locked(
        self,
        module: _ModuleRuntime,
        channel: int,
        state: bool,
    ):
        try:
            return module.client.write_coil(
                address=channel - 1,
                value=state,
                device_id=module.unit_id,
            )
        except TypeError:
            return module.client.write_coil(
                address=channel - 1,
                value=state,
                slave=module.unit_id,
            )

    def _validate_bits(self, result) -> List[bool]:
        if result is None:
            raise RuntimeError("read_discrete_inputs returned None")

        is_error = getattr(result, "isError", None)
        if callable(is_error) and is_error():
            raise RuntimeError(f"Modbus DI read error: {result}")

        bits = getattr(result, "bits", None)
        if bits is None:
            raise RuntimeError("Modbus DI result has no bits")
        if len(bits) < 8:
            raise RuntimeError(f"Modbus DI result too short: {len(bits)} bits")

        return [bool(bit) for bit in bits[:8]]

    def _mark_success_locked(self, module: _ModuleRuntime):
        module.failure_count = 0
        module.last_success_at = time.time()
        module.last_error = None

    def _mark_disconnected_locked(self, module: _ModuleRuntime, error):
        try:
            module.client.close()
        except Exception:
            pass
        module.connected = False
        self._schedule_retry_locked(module, error)

    def _schedule_retry_locked(self, module: _ModuleRuntime, error):
        module.failure_count += 1
        retry_delay = 2 if module.failure_count == 1 else 5
        if module.failure_count > 5:
            retry_delay = 30

        module.next_retry_at = time.time() + retry_delay
        module.last_error = str(error)

        now = time.time()
        if (
            now - module.last_error_log_at >= self.error_log_interval
            or module.failure_count == 1
        ):
            logger.warning(
                "Modbus module %s unavailable (%s). Retrying in %ss.",
                module.name,
                error,
                retry_delay,
            )
            module.last_error_log_at = now

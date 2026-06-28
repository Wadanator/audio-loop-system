"""Compatibility wrapper for the refactored Modbus input module."""

from pathlib import Path
import sys


_SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from audio_loop.input.modbus_panel import ModbusButtonHandler


__all__ = ["ModbusButtonHandler"]

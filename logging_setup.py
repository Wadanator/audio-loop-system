"""Compatibility wrapper for the refactored logging setup module."""

from pathlib import Path
import sys


_SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from audio_loop.infra.logging_setup import setup_logging


__all__ = ["setup_logging"]

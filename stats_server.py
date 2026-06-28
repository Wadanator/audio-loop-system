"""Compatibility wrapper for the refactored stats server module."""

from pathlib import Path
import sys


_SRC_ROOT = Path(__file__).resolve().parent / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from audio_loop.web.stats_server import run_stats_server


__all__ = ["run_stats_server"]

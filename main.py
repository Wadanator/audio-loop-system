#!/usr/bin/env python3
"""Project entry point for the audio_loop package."""

from pathlib import Path
import sys


_PROJECT_ROOT = Path(__file__).resolve().parent
_SRC_ROOT = _PROJECT_ROOT / "src"
for path in (_PROJECT_ROOT, _SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from audio_loop.app import main


if __name__ == "__main__":
    main()
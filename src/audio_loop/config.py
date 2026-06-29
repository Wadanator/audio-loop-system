"""Configuration loading and runtime requirement checks."""

import json
from pathlib import Path
from typing import Optional

from audio_loop.infra.paths import runtime_path


def resolve_runtime_path(path_value: str) -> Path:
    """Resolve a config path relative to the project runtime directory."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return runtime_path(path_value)


def load_config(config_path: Optional[str] = None) -> dict:
    """Load `config.json` using UTF-8 with optional BOM tolerance."""
    path = Path(config_path) if config_path else runtime_path("config.json")
    if not path.exists():
        raise FileNotFoundError("config.json required but not found")

    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except Exception as exc:
        raise FileNotFoundError(f"Could not read config.json: {exc}") from exc


def validate_runtime_requirements(config: dict) -> None:
    """Validate filesystem requirements needed before startup."""
    audio_dir = resolve_runtime_path("audio_files")
    if not audio_dir.exists():
        raise FileNotFoundError("audio_files/ directory required but not found")

    song_rotation_config = config.get("song_rotation", {})
    if song_rotation_config.get("enable", False):
        _check_song_folders(song_rotation_config)
    else:
        _check_direct_wav_files(audio_dir)


def _check_song_folders(song_config: dict) -> None:
    base_dir = resolve_runtime_path(song_config.get("base_directory", "audio_files"))
    song_folders = song_config.get("song_folders", ["song1"])

    found_valid_songs = False
    for song_name in song_folders:
        song_path = base_dir if song_name == "default" else base_dir / song_name
        if song_path.exists() and song_path.is_dir():
            wav_files = [path for path in song_path.iterdir() if path.name.endswith(".wav")]
            if wav_files:
                found_valid_songs = True

    if not found_valid_songs:
        raise FileNotFoundError("No valid song folders found!")


def _check_direct_wav_files(audio_dir: Path) -> None:
    wav_files = [path for path in audio_dir.iterdir() if path.name.endswith(".wav")]
    if not wav_files:
        raise FileNotFoundError("No .wav files found in audio_files/ directory")

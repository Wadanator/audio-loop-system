"""Dashboard log capture and persistence for the audio-loop web UI."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Deque, Dict, Iterable, List, Optional

from audio_loop.infra.paths import runtime_path


LEVEL_NAMES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_AUDIT_LOGGER = "audio_loop.audit"
DEFAULT_IGNORED_LOGGERS = ("werkzeug", "flask")


@dataclass(frozen=True)
class DashboardLogSettings:
    """Runtime settings for dashboard-visible logs."""

    enabled: bool = True
    max_entries: int = 1000
    min_level: int = logging.WARNING
    include_info_loggers: tuple[str, ...] = (DEFAULT_AUDIT_LOGGER,)
    ignored_loggers: tuple[str, ...] = DEFAULT_IGNORED_LOGGERS
    persist_enabled: bool = True
    persist_path: Path = field(
        default_factory=lambda: runtime_path("logs", "dashboard_events.jsonl")
    )
    max_file_bytes: int = 1024 * 1024
    backup_count: int = 5
    load_limit: int = 250

    @classmethod
    def from_config(cls, config: Optional[dict]) -> "DashboardLogSettings":
        config = config or {}
        web_config = config.get("web", {}) or {}
        logs_config = web_config.get("logs", {}) or {}

        return cls(
            enabled=bool(logs_config.get("enabled", True)),
            max_entries=_coerce_int(logs_config.get("max_entries"), 1000, 50, 5000),
            min_level=_coerce_level(logs_config.get("min_level"), logging.WARNING),
            include_info_loggers=_coerce_tuple(
                logs_config.get("include_info_loggers"),
                (DEFAULT_AUDIT_LOGGER,),
            ),
            ignored_loggers=_coerce_tuple(
                logs_config.get("ignored_loggers"),
                DEFAULT_IGNORED_LOGGERS,
            ),
            persist_enabled=bool(logs_config.get("persist_enabled", True)),
            persist_path=runtime_path(
                logs_config.get("persist_path", "logs/dashboard_events.jsonl")
            ),
            max_file_bytes=_coerce_int(
                logs_config.get("max_file_bytes"),
                1024 * 1024,
                64 * 1024,
                16 * 1024 * 1024,
            ),
            backup_count=_coerce_int(logs_config.get("backup_count"), 5, 1, 20),
            load_limit=_coerce_int(logs_config.get("load_limit"), 250, 0, 2000),
        )


def _coerce_level(value: Any, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        level = logging.getLevelName(value.upper())
        if isinstance(level, int):
            return level
    return default


def _coerce_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _coerce_tuple(value: Any, default: Iterable[str]) -> tuple[str, ...]:
    if value is None:
        return tuple(default)
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    return tuple(default)


class DashboardLogStore:
    """Thread-safe in-memory dashboard log buffer with small JSONL persistence."""

    def __init__(self) -> None:
        self.settings = DashboardLogSettings()
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=self.settings.max_entries)
        self._lock = threading.Lock()
        self._loaded_path: Optional[Path] = None

    def configure(self, settings: DashboardLogSettings) -> None:
        with self._lock:
            existing = list(self._entries)[-settings.max_entries:]
            self.settings = settings
            self._entries = deque(existing, maxlen=settings.max_entries)
            should_load = settings.persist_enabled and self._loaded_path != settings.persist_path
            if should_load:
                self._entries.clear()
                self._load_existing_unlocked()
                self._loaded_path = settings.persist_path

    def should_capture(self, record: logging.LogRecord) -> bool:
        settings = self.settings
        if not settings.enabled:
            return False
        if record.name.startswith(settings.ignored_loggers):
            return False
        if record.levelno >= settings.min_level:
            return True
        if record.levelno >= logging.INFO and record.name.startswith(settings.include_info_loggers):
            return True
        return False

    def add_from_record(self, record: logging.LogRecord) -> None:
        if not self.should_capture(record):
            return
        entry = self._entry_from_record(record)
        self.add_entry(entry, persist=True)

    def add_entry(self, entry: Dict[str, Any], *, persist: bool = False) -> None:
        with self._lock:
            self._entries.append(entry)
            if persist and self.settings.persist_enabled:
                self._persist_entry_unlocked(entry)

    def get_history(self, *, level: str = "", limit: Optional[int] = None) -> List[Dict[str, Any]]:
        level = (level or "").upper()
        with self._lock:
            entries = list(self._entries)
        if level in LEVEL_NAMES:
            entries = [entry for entry in entries if entry.get("level") == level]
        if limit is not None and limit >= 0:
            entries = entries[-limit:]
        return entries

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def _entry_from_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        module = record.name.rsplit(".", 1)[-1] if record.name else "root"
        entry = {
            "timestamp": datetime.fromtimestamp(record.created).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )[:-3],
            "level": record.levelname,
            "module": module,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self._format_exception(record)
        return entry

    def _format_exception(self, record: logging.LogRecord) -> List[str]:
        formatter = logging.Formatter("%(message)s")
        formatted = formatter.formatException(record.exc_info)
        return formatted.splitlines()

    def _persist_entry_unlocked(self, entry: Dict[str, Any]) -> None:
        path = self.settings.persist_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed_unlocked(path)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
        except Exception:
            # Logging must never fail the audio runtime.
            return

    def _rotate_if_needed_unlocked(self, path: Path) -> None:
        if not path.exists() or path.stat().st_size < self.settings.max_file_bytes:
            return

        for index in range(self.settings.backup_count - 1, 0, -1):
            source = path.with_suffix(path.suffix + f".{index}")
            target = path.with_suffix(path.suffix + f".{index + 1}")
            if source.exists():
                if target.exists():
                    target.unlink()
                os.replace(source, target)

        first_backup = path.with_suffix(path.suffix + ".1")
        if first_backup.exists():
            first_backup.unlink()
        os.replace(path, first_backup)

    def _load_existing_unlocked(self) -> None:
        if self.settings.load_limit <= 0:
            return

        paths = self._persisted_paths_oldest_first()
        loaded: List[Dict[str, Any]] = []
        for path in paths:
            if not path.exists():
                continue
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(entry, dict):
                            loaded.append(entry)
            except Exception:
                continue

        for entry in loaded[-self.settings.load_limit:]:
            self._entries.append(entry)

    def _persisted_paths_oldest_first(self) -> List[Path]:
        path = self.settings.persist_path
        backups = [
            path.with_suffix(path.suffix + f".{index}")
            for index in range(self.settings.backup_count, 0, -1)
        ]
        return backups + [path]


class DashboardLogHandler(logging.Handler):
    """Logging handler that forwards selected records to the dashboard store."""

    def __init__(self, store: DashboardLogStore) -> None:
        super().__init__(logging.DEBUG)
        self.store = store

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.store.add_from_record(record)
        except Exception:
            self.handleError(record)


_STORE = DashboardLogStore()
_HANDLER: Optional[DashboardLogHandler] = None
_HANDLER_LOCK = threading.Lock()


def configure_dashboard_logging(config: Optional[dict] = None) -> DashboardLogStore:
    """Configure dashboard log capture and ensure the root handler is attached."""
    settings = DashboardLogSettings.from_config(config)
    _STORE.configure(settings)

    global _HANDLER
    with _HANDLER_LOCK:
        if _HANDLER is None:
            _HANDLER = DashboardLogHandler(_STORE)
            logging.getLogger().addHandler(_HANDLER)
    return _STORE


def get_dashboard_log_store() -> DashboardLogStore:
    return _STORE
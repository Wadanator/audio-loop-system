"""systemd watchdog notification helpers."""

import logging


logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL = 25


def notify_ready() -> None:
    """Tell systemd the service is ready when sdnotify is installed."""
    _notify("READY=1")


def send_watchdog() -> None:
    """Send a WATCHDOG=1 keep-alive when sdnotify is installed."""
    _notify("WATCHDOG=1")


def _notify(message: str) -> None:
    try:
        import sdnotify

        sdnotify.SystemdNotifier().notify(message)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("Watchdog notify failed: %s", exc)

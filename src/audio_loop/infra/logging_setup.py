# logging_setup.py
"""Logging configuration optimized for minimal SD card writes."""

import logging
import sys
from logging.handlers import RotatingFileHandler
import os

from audio_loop.infra.paths import runtime_path


def setup_logging():
    """Configure the logging system for SD card longevity.

    Strategy:
    - FILE handler:   ERROR and above only  -> writes to SD card (minimal I/O)
    - STDOUT handler: INFO and above        -> captured by systemd/journald
                                              without any SD card writes

    This allows full runtime visibility via ``journalctl --user -u
    audio_looper.service -f`` without increasing SD card wear for
    routine informational messages.
    """
    log_dir = str(runtime_path('logs'))

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # FILE handler: ERROR and CRITICAL only -- minimal SD card writes.
    log_file = os.path.join(log_dir, 'critical_errors.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=2               # Keep only 2 backup files
    )
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    )

    # STDOUT handler: systemd/journald captures these without writing to SD.
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(
        logging.Formatter('%(levelname)s: %(name)s - %(message)s')
    )

    # Configure the root logger.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove any pre-existing handlers before adding our own.
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stdout_handler)

    # Reduce verbosity for modules that produce high-frequency log entries.
    logging.getLogger('audio_manager').setLevel(logging.WARNING)
    logging.getLogger('audio_loop.audio.manager').setLevel(logging.WARNING)
    logging.getLogger('button_handler').setLevel(logging.WARNING)
    logging.getLogger('looper_engine').setLevel(logging.WARNING)
    logging.getLogger('audio_loop.core.looper_engine').setLevel(logging.WARNING)
    logging.getLogger('stats_collector').setLevel(logging.INFO)
    logging.getLogger('audio_loop.stats.collector').setLevel(logging.INFO)

    logging.info(
        "Logging setup complete - ERROR -> file (SD card), INFO+ -> stdout (journald)"
    )
    logging.info(f"Critical errors logged to: {log_file}")
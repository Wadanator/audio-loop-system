# stats_collector.py
"""SD card-optimized usage statistics collector."""

import json
import os
import logging
import time
from typing import Dict


logger = logging.getLogger(__name__)


class StatsCollector:
    """Collects and persists instrument activation statistics.

    Keeps all counters in RAM and writes to disk only every 5 minutes
    or when explicitly forced, minimizing SD card wear.
    """

    def __init__(self, stats_file: str = "stats.json", max_instruments: int = 16):
        """Initialize the stats collector.

        Args:
            stats_file: Path to the JSON file used for persistent storage.
        """
        self.stats_file = stats_file
        self.max_instruments = max(1, int(max_instruments))
        self.stats: Dict[str, int] = {
            f"instrument_{i}": 0 for i in range(1, self.max_instruments + 1)
        }
        self.stats.update({
            "command_status": 0,
            "command_stop": 0,
            "command_quit": 0
        })

        # SD card optimisation: defer disk writes.
        self.last_save_time = 0
        self.save_interval = 300  # Write to disk at most every 5 minutes.
        self.pending_changes = False

        self._load_stats()

    def _load_stats(self):
        """Load existing statistics from the JSON file into RAM.

        If the file does not exist, the in-memory counters remain at zero.
        """
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    loaded_stats = json.load(f)
                    for key, value in loaded_stats.items():
                        if key in self.stats:
                            self.stats[key] = value
                logger.info(f"Loaded statistics from {self.stats_file}")
            except Exception as e:
                logger.error(
                    f"Failed to load stats from {self.stats_file}: {e}"
                )
        else:
            logger.info(
                "No existing stats file found, starting with empty stats"
            )

    def _should_save(self, force: bool = False) -> bool:
        """Determine whether a disk write should be performed.

        Args:
            force: If True, always return True regardless of elapsed time.

        Returns:
            True if the stats should be written to disk now.
        """
        current_time = time.time()
        time_passed = current_time - self.last_save_time

        return force or (
            self.pending_changes and time_passed >= self.save_interval
        )

    def _save_stats(self, force: bool = False):
        """Write statistics to disk if the save policy permits.

        Uses an atomic write (temp file + replace) to prevent data corruption
        if the process is interrupted mid-write.

        Args:
            force: If True, write to disk regardless of the save interval.
        """
        if not self._should_save(force):
            return

        try:
            # Write to a temp file first, then atomically replace the target to
            # prevent a corrupt stats file if the process is interrupted.
            temp_file = self.stats_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.stats, f, indent=2)

            os.replace(temp_file, self.stats_file)

            self.last_save_time = time.time()
            self.pending_changes = False
            logger.info("Stats saved to disk (SD card write)")

        except Exception as e:
            logger.error(f"Failed to save stats to {self.stats_file}: {e}")

    def record_instrument(self, instrument: int):
        """Increment the activation counter for an instrument (RAM only).

        The change is marked as pending but not written to disk immediately
        to reduce SD card wear.

        Args:
            instrument: Instrument number within the configured range.
        """
        if 1 <= instrument <= self.max_instruments:
            key = f"instrument_{instrument}"
            self.stats[key] = self.stats.get(key, 0) + 1
            self.pending_changes = True
            # Do not write to disk immediately -- only mark as changed.
            logger.info(
                f"Recorded activation for {key}: {self.stats[key]} "
                f"(in memory)"
            )

    def record_command(self, command: str):
        """Increment the counter for a named command (RAM only).

        Args:
            command: One of ``'status'``, ``'stop'``, or ``'quit'``.
        """
        if command in ['status', 'stop', 'quit']:
            key = f"command_{command}"
            self.stats[key] = self.stats.get(key, 0) + 1
            self.pending_changes = True
            logger.info(
                f"Recorded command {key}: {self.stats[key]} (in memory)"
            )

    def get_stats(self) -> Dict[str, int]:
        """Return a shallow copy of the current in-memory statistics.

        Returns:
            Dictionary mapping stat keys to their integer counts.
        """
        return self.stats.copy()

    def force_save(self):
        """Flush any pending in-memory changes to disk immediately."""
        if self.pending_changes:
            self._save_stats(force=True)
            logger.info("Stats force-saved to disk")

    def periodic_save(self):
        """Write stats to disk if the save interval has elapsed.

        Intended to be called from the main application loop.
        """
        self._save_stats(force=False)

    def reset_stats(self):
        """Reset all counters to zero and immediately persist the result."""
        for key in self.stats:
            self.stats[key] = 0
        self.pending_changes = True
        self._save_stats(force=True)
        logger.warning("Statistics reset to zero")
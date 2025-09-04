# stats_collector.py
import json
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class StatsCollector:
    """Collects and stores statistics about instrument and command usage."""
    
    def __init__(self, stats_file: str = "stats.json"):
        """
        Initializes the StatsCollector.

        Args:
            stats_file (str): The path to the JSON file for storing stats.
        """
        self.stats_file = stats_file
        self.stats: Dict[str, int] = {
            f"instrument_{i}": 0 for i in range(1, 19)
        }
        self.stats.update({
            "command_status": 0,
            "command_stop": 0,
            "command_quit": 0
        })
        self._load_stats()
    
    def _load_stats(self):
        """Loads existing statistics from the JSON file."""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    loaded_stats = json.load(f)
                    self.stats.update(loaded_stats)
                logger.info(f"Loaded statistics from {self.stats_file}")
            except Exception as e:
                logger.error(f"Failed to load stats from {self.stats_file}: {e}")
        else:
            logger.info("No existing stats file found, starting with empty stats")
    
    def _save_stats(self):
        """Saves statistics to the JSON file."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=4)
            logger.debug(f"Saved statistics to {self.stats_file}")
        except Exception as e:
            logger.error(f"Failed to save stats to {self.stats_file}: {e}")
    
    def record_instrument(self, instrument: int):
        """
        Records an instrument activation.

        Args:
            instrument (int): The number of the instrument activated.
        """
        if 1 <= instrument <= 18:
            key = f"instrument_{instrument}"
            self.stats[key] = self.stats.get(key, 0) + 1
            logger.debug(f"Recorded activation for {key}: {self.stats[key]}")
            self._save_stats()
    
    def record_command(self, command: str):
        """
        Records a command execution.

        Args:
            command (str): The command that was executed ('status', 'stop', 'quit').
        """
        if command in ['status', 'stop', 'quit']:
            key = f"command_{command}"
            self.stats[key] = self.stats.get(key, 0) + 1
            logger.debug(f"Recorded command {key}: {self.stats[key]}")
            self._save_stats()
    
    def get_stats(self) -> Dict[str, int]:
        """
        Returns the current statistics.

        Returns:
            Dict[str, int]: A dictionary containing the current stats.
        """
        return self.stats.copy()
    
    def reset_stats(self):
        """Resets all statistics to zero and saves the change."""
        for key in self.stats:
            self.stats[key] = 0
        self._save_stats()
        logger.info("Statistics reset to zero")
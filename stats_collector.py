# stats_collector.py - Optimalizovaná verzia pre šetrenie SD karty
import json
import os
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)

class StatsCollector:
    """
    Optimalizovaný zberač štatistík pre šetrenie SD karty.
    - Zapisuje na disk iba každých 5 minút alebo pri shutdown
    - Udržuje dáta v pamäti
    """
    
    def __init__(self, stats_file: str = "stats.json"):
        self.stats_file = stats_file
        self.stats: Dict[str, int] = {
            f"instrument_{i}": 0 for i in range(1, 19)
        }
        self.stats.update({
            "command_status": 0,
            "command_stop": 0,
            "command_quit": 0
        })
        
        # Optimalizácia pre SD kartu
        self.last_save_time = 0
        self.save_interval = 300  # Zapisuj iba každých 5 minút
        self.pending_changes = False
        
        self._load_stats()
    
    def _load_stats(self):
        """Načíta existujúce štatistiky zo súboru."""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    loaded_stats = json.load(f)
                    self.stats.update(loaded_stats)
                logger.warning(f"Loaded statistics from {self.stats_file}")
            except Exception as e:
                logger.error(f"Failed to load stats from {self.stats_file}: {e}")
        else:
            logger.warning("No existing stats file found, starting with empty stats")
    
    def _should_save(self, force: bool = False) -> bool:
        """Rozhodne, či je čas zapísať na disk."""
        current_time = time.time()
        time_passed = current_time - self.last_save_time
        
        return force or (self.pending_changes and time_passed >= self.save_interval)
    
    def _save_stats(self, force: bool = False):
        """Uloží štatistiky - iba ak je to potrebné."""
        if not self._should_save(force):
            return
        
        try:
            # Atomic write - zapíš do temp súboru a potom rename
            temp_file = self.stats_file + ".tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.stats, f, indent=2)  # Zmenšené odsadenie
            
            # Atomic rename
            os.rename(temp_file, self.stats_file)
            
            self.last_save_time = time.time()
            self.pending_changes = False
            logger.error(f"Stats saved to disk (SD card write)")  # ERROR level pre monitoring
            
        except Exception as e:
            logger.error(f"Failed to save stats to {self.stats_file}: {e}")
    
    def record_instrument(self, instrument: int):
        """Zaznamenáva aktiváciu nástroja - iba v pamäti."""
        if 1 <= instrument <= 18:
            key = f"instrument_{instrument}"
            self.stats[key] = self.stats.get(key, 0) + 1
            self.pending_changes = True
            # Nezapisuj na disk hneď - iba označ že sú zmeny
            logger.info(f"Recorded activation for {key}: {self.stats[key]} (in memory)")
    
    def record_command(self, command: str):
        """Zaznamenáva vykonanie príkazu - iba v pamäti."""
        if command in ['status', 'stop', 'quit']:
            key = f"command_{command}"
            self.stats[key] = self.stats.get(key, 0) + 1
            self.pending_changes = True
            logger.info(f"Recorded command {key}: {self.stats[key]} (in memory)")
    
    def get_stats(self) -> Dict[str, int]:
        """Vracia aktuálne štatistiky z pamäte."""
        return self.stats.copy()
    
    def force_save(self):
        """Vynúti okamžité uloženie na disk (napr. pri shutdown)."""
        if self.pending_changes:
            self._save_stats(force=True)
            logger.error("Stats force-saved to disk")
    
    def periodic_save(self):
        """Periodické ukladanie - volať z main loop."""
        self._save_stats(force=False)
    
    def reset_stats(self):
        """Resetuje všetky štatistiky na nulu."""
        for key in self.stats:
            self.stats[key] = 0
        self.pending_changes = True
        self._save_stats(force=True)
        logger.error("Statistics reset to zero")
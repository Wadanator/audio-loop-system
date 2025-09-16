#!/usr/bin/env python3
"""
Audio Looper System - SD Card Optimized Version
Minimalizuje zápisy na SD kartu pre dlhšiu životnosť
"""
import sys
import os
import logging
import time
import signal
import json
import threading

from audio_manager import AudioManager
from button_handler import UniversalButtonHandler
from looper_engine import LooperEngine
from stats_server import run_stats_server
from stats_collector import StatsCollector
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class AudioLooper:
    """Hlavná trieda optimalizovaná pre šetrenie SD karty."""
    
    def __init__(self):
        self._check_requirements()
        self.config = self._load_config()
        
        self.audio_manager = None
        self.looper_engine = None
        self.button_handler = None
        self.stats_server_thread = None
        self.stats_collector = None
        
        self.running = False
        
        # Pre SD optimalizáciu
        self.last_status_log = 0
        self.status_log_interval = 600  # Status iba každých 10 minút
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        self._initialize_components()

    def _check_requirements(self):
        """Kontrola potrebných súborov - minimálne logovania."""
        if not os.path.exists("config.json"):
            raise FileNotFoundError("config.json required but not found")
        
        if not os.path.exists("audio_files"):
            raise FileNotFoundError("audio_files/ directory required but not found")
        
        try:
            with open("config.json", 'r') as f:
                config = json.load(f)
        except Exception as e:
            raise FileNotFoundError(f"Could not read config.json: {e}")
        
        song_rotation_config = config.get('song_rotation', {})
        
        if song_rotation_config.get('enable', False):
            self._check_song_folders(config)
        else:
            self._check_direct_wav_files()

    def _check_song_folders(self, config):
        """Kontrola štruktúry song priečinkov."""
        song_config = config.get('song_rotation', {})
        base_dir = song_config.get('base_directory', 'audio_files')
        song_folders = song_config.get('song_folders', ['song1'])
        
        found_valid_songs = False
        
        for song_name in song_folders:
            if song_name == 'default':
                song_path = base_dir
            else:
                song_path = os.path.join(base_dir, song_name)
            
            if os.path.exists(song_path) and os.path.isdir(song_path):
                wav_files = [f for f in os.listdir(song_path) if f.endswith('.wav')]
                if wav_files:
                    found_valid_songs = True
        
        if not found_valid_songs:
            raise FileNotFoundError(f"No valid song folders found!")

    def _check_direct_wav_files(self):
        """Kontrola priamych .wav súborov."""
        wav_files = [f for f in os.listdir("audio_files") if f.endswith('.wav')]
        if not wav_files:
            raise FileNotFoundError("No .wav files found in audio_files/ directory")

    def _load_config(self) -> dict:
        """Načíta konfiguráciu zo súboru."""
        with open("config.json", 'r') as f:
            return json.load(f)

    def _initialize_components(self):
        """Inicializuje komponenty systému."""
        try:
            song_rotation = self.config.get('song_rotation', {})
            
            self.audio_manager = AudioManager(self.config)
            self.stats_collector = StatsCollector()  # Nová optimalizovaná verzia
            self.looper_engine = LooperEngine(self.audio_manager, self.config)
            self.button_handler = UniversalButtonHandler(
                self.looper_engine.handle_button_press, 
                self.config
            )
            self.stats_server_thread = threading.Thread(
                target=run_stats_server,
                args=(self.config['stats_server']['host'], self.config['stats_server']['port']),
                daemon=True
            )
        except Exception as e:
            logger.error(f"Critical component initialization failed: {e}")
            self.shutdown(exit_code=1)

    def _signal_handler(self, signum, frame):
        """Spracováva signály pre graceful shutdown."""
        logger.error(f"Received signal {signum}, initiating shutdown.")
        self.shutdown()

    def run(self):
        """Spúšťa hlavnú aplikačnú slučku."""
        logger.error("Starting SD-Optimized Audio Looper System")
        
        try:
            if hasattr(self.audio_manager, 'get_current_song_info'):
                song_info = self.audio_manager.get_current_song_info()
                logger.error(f"Initial song: {song_info['name']}")  # ERROR level pre startup log
            
            self.looper_engine.start()
            self.button_handler.start()
            self.stats_server_thread.start()
            self.running = True
            
            # Hlavná slučka s minimálnym logovaním
            loop_counter = 0
            while self.running:
                current_time = time.time()
                loop_counter += 1
                
                # Periodické ukladanie stats (každých 5 minút)
                if loop_counter % 300 == 0:  # Každých 300 sekúnd
                    if hasattr(self.stats_collector, 'periodic_save'):
                        self.stats_collector.periodic_save()
                
                # Status log iba každých 10 minút ak je systém aktívny
                if (current_time - self.last_status_log) > self.status_log_interval:
                    if hasattr(self.looper_engine, 'get_system_status'):
                        status = self.looper_engine.get_system_status()
                        if status['system_active']:
                            logger.error(f"System active - Song: {status['current_song']['name']}, "
                                       f"Active instruments: {len(status['active_instruments'])}")
                    self.last_status_log = current_time
                
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Fatal error in main loop: {e}")
            self.shutdown(exit_code=1)
            
    def shutdown(self, exit_code: int = 0):
        """Bezpečne vypína všetky komponenty systému."""
        logger.error("Shutting down SD-Optimized Audio Looper System...")
        self.running = False
        
        # Dôležité: ulož štatistiky pred vypnutím
        if hasattr(self, 'stats_collector') and self.stats_collector:
            try:
                self.stats_collector.force_save()
            except Exception as e:
                logger.error(f"Failed to save stats on shutdown: {e}")
        
        if hasattr(self, 'button_handler') and self.button_handler:
            self.button_handler.stop()
        if hasattr(self, 'looper_engine') and self.looper_engine:
            self.looper_engine.shutdown()
        if hasattr(self, 'audio_manager') and self.audio_manager:
            self.audio_manager.shutdown()
        
        logger.error("Shutdown complete.")
        sys.exit(exit_code)

def main():
    """Hlavná funkcia na spustenie aplikácie."""
    try:
        app = AudioLooper()
        app.run()
    except FileNotFoundError as e:
        print(f"\n❌ SETUP ERROR:")
        print(f"{e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
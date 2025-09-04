#!/usr/bin/env python3
"""
Audio Looper System - Refactored Version
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
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class AudioLooper:
    """The main application class for the audio looper system."""
    
    def __init__(self):
        """Initializes the main application components."""
        self._check_requirements()
        self.config = self._load_config()
        
        self.audio_manager = None
        self.looper_engine = None
        self.button_handler = None
        self.stats_server_thread = None
        
        self.running = False
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialize components in a separate method to handle setup failures
        self._initialize_components()

    def _check_requirements(self):
        """Checks for required files and directories."""
        if not os.path.exists("config.json"):
            raise FileNotFoundError("config.json required but not found")
        if not os.path.exists("audio_files"):
            raise FileNotFoundError("audio_files/ directory required but not found")
        if not any(f.endswith('.wav') for f in os.listdir("audio_files")):
            raise FileNotFoundError("No .wav files found in audio_files/ directory")

    def _load_config(self) -> dict:
        """Loads the configuration from a JSON file."""
        with open("config.json", 'r') as f:
            return json.load(f)

    def _initialize_components(self):
        """Initializes all system components and handles potential setup errors."""
        try:
            self.audio_manager = AudioManager(self.config)
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
            logger.critical(f"Critical component initialization failed: {e}", exc_info=True)
            self.shutdown(exit_code=1)

    def _signal_handler(self, signum, frame):
        """Handles termination signals for a graceful shutdown."""
        logger.info(f"Received signal {signum}, initiating shutdown.")
        self.shutdown()

    def run(self):
        """Starts the main application loop."""
        logger.info("Starting Audio Looper System")
        try:
            self.looper_engine.start()
            self.button_handler.start()
            self.stats_server_thread.start()
            self.running = True
            
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
            self.shutdown(exit_code=1)
            
    def shutdown(self, exit_code: int = 0):
        """
        Safely shuts down all system components.

        Args:
            exit_code (int): The exit code to use when shutting down.
        """
        logger.info("Shutting down Audio Looper System...")
        self.running = False
        
        if hasattr(self, 'button_handler') and self.button_handler:
            self.button_handler.stop()
        if hasattr(self, 'looper_engine') and self.looper_engine:
            self.looper_engine.shutdown()
        if hasattr(self, 'audio_manager') and self.audio_manager:
            self.audio_manager.shutdown()
        
        logger.info("Shutdown complete.")
        sys.exit(exit_code)

def main():
    """Main function to start the application."""
    app = AudioLooper()
    app.run()

if __name__ == "__main__":
    main()
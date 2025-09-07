#!/usr/bin/env python3
"""
Audio Looper System - Enhanced Version with Song Rotation
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
    """The main application class for the audio looper system with song rotation."""
    
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
        """
        Checks for required files and directories.
        Supports both old format (audio_files/*.wav) and new format (audio_files/song*/*.wav)
        """
        if not os.path.exists("config.json"):
            raise FileNotFoundError("config.json required but not found")
        
        if not os.path.exists("audio_files"):
            raise FileNotFoundError("audio_files/ directory required but not found")
        
        # Load config to check song rotation settings
        try:
            with open("config.json", 'r') as f:
                config = json.load(f)
        except Exception as e:
            raise FileNotFoundError(f"Could not read config.json: {e}")
        
        song_rotation_config = config.get('song_rotation', {})
        
        if song_rotation_config.get('enable', False):
            # NEW FORMAT: Check song folders
            self._check_song_folders(config)
        else:
            # OLD FORMAT: Check direct .wav files
            self._check_direct_wav_files()

    def _check_song_folders(self, config):
        """Checks the new song folder structure."""
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
                    logger.info(f"Found song folder '{song_name}' with {len(wav_files)} .wav files")
        
        if not found_valid_songs:
            raise FileNotFoundError(
                f"No valid song folders found!\n"
                f"Expected structure:\n"
                f"  {base_dir}/\n" + 
                "".join([f"  ├── {song}/\n  │   ├── 1.wav\n  │   ├── 2.wav\n  │   └── ...\n" 
                        for song in song_folders[:2]]) +
                f"For configured songs: {song_folders}"
            )

    def _check_direct_wav_files(self):
        """Checks the old direct .wav files structure."""
        wav_files = [f for f in os.listdir("audio_files") if f.endswith('.wav')]
        if not wav_files:
            raise FileNotFoundError(
                "No .wav files found in audio_files/ directory\n"
                "For song rotation, enable it in config.json and create song folders:\n"
                "  audio_files/song1/1.wav, audio_files/song1/2.wav, etc.\n"
                "For single song mode, place files directly:\n"
                "  audio_files/1.wav, audio_files/2.wav, etc."
            )

    def _load_config(self) -> dict:
        """Loads the configuration from a JSON file."""
        with open("config.json", 'r') as f:
            return json.load(f)

    def _initialize_components(self):
        """Initializes all system components and handles potential setup errors."""
        try:
            # Log configuration info
            song_rotation = self.config.get('song_rotation', {})
            if song_rotation.get('enable', False):
                logger.info(f"Song rotation ENABLED - Songs: {song_rotation.get('song_folders', [])}")
            else:
                logger.info("Song rotation DISABLED - Using direct audio files")
            
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
        logger.info("Starting Enhanced Audio Looper System")
        
        try:
            # Log initial system status
            if hasattr(self.audio_manager, 'get_current_song_info'):
                song_info = self.audio_manager.get_current_song_info()
                logger.info(f"Initial song: {song_info['name']} "
                           f"({len(song_info['available_instruments'])} instruments, "
                           f"{song_info['duration_seconds']:.1f}s duration)")
            
            self.looper_engine.start()
            self.button_handler.start()
            self.stats_server_thread.start()
            self.running = True
            
            # Main loop with periodic status logging
            last_status_log = 0
            while self.running:
                current_time = time.time()
                
                # Log status every 60 seconds if system is active
                if (current_time - last_status_log) > 60:
                    if hasattr(self.looper_engine, 'get_system_status'):
                        status = self.looper_engine.get_system_status()
                        if status['system_active']:
                            logger.info(f"System active - Song: {status['current_song']['name']}, "
                                       f"Session: {status['session_duration']:.0f}s, "
                                       f"Active instruments: {len(status['active_instruments'])}")
                    last_status_log = current_time
                
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
        logger.info("Shutting down Enhanced Audio Looper System...")
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
    try:
        app = AudioLooper()
        app.run()
    except FileNotFoundError as e:
        print(f"\n❌ SETUP ERROR:")
        print(f"{e}")
        print(f"\n🔧 QUICK FIX:")
        print(f"1. Create audio files in the correct structure")
        print(f"2. Or disable song_rotation in config.json")
        print(f"3. Check the logs/ directory for more details")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        print(f"Check the logs/ directory for detailed error information")
        sys.exit(1)

if __name__ == "__main__":
    main()
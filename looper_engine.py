# looper_engine.py
import logging
import time
import threading
from audio_manager import AudioManager
from stats_collector import StatsCollector

logger = logging.getLogger(__name__)

class LooperEngine:
    """
    Enhanced looper engine with song rotation support.
    Automatically switches songs when global timeout expires.
    """
    
    def __init__(self, audio_manager: AudioManager, config: dict):
        """
        Initializes the looper engine with song rotation.

        Args:
            audio_manager (AudioManager): The audio manager instance.
            config (dict): The configuration dictionary.
        """
        self.audio_manager = audio_manager
        self.stats_collector = StatsCollector()
        self.config = config

        # Timeout configuration
        self.global_timeout = self.config['timeouts']['global_timeout']
        self.instrument_timeout = self.config['timeouts']['instrument_timeout']
        self.fade_duration = self.config['timeouts']['fade_duration']
        self.button_cooldown_seconds = self.config.get('raspberry_pi', {}).get('button_cooldown_seconds', 0.8)

        # Song rotation configuration
        self.song_rotation_config = self.config.get('song_rotation', {})
        self.enable_song_rotation = self.song_rotation_config.get('enable', True)
        self.song_switch_on_timeout = self.song_rotation_config.get('switch_on_global_timeout', True)
        
        # System state
        self.system_active = False
        self.running = False
        self.instrument_active = {i: False for i in range(1, 19)}
        
        # Timing state
        self.global_expiry_time = 0
        self.instrument_expiry_times = {i: 0 for i in range(1, 19)}
        self.last_press_times = {i: 0 for i in range(1, 19)}

        # Song rotation tracking
        self.session_start_time = 0
        self.total_sessions = 0
        
        self.logic_thread = threading.Thread(target=self._logic_loop, daemon=True)

    def start(self):
        """Starts the main logic loop."""
        if self.running:
            return
        self.running = True
        self.logic_thread.start()
        logger.info("Enhanced Looper Engine with song rotation started.")

    def shutdown(self):
        """Safely shuts down the engine."""
        logger.info("Shutting down Enhanced Looper Engine.")
        self.running = False
        if self.system_active:
            self._deactivate_system()
        if self.logic_thread.is_alive():
            self.logic_thread.join(timeout=1.0)
        logger.info("Enhanced Looper Engine stopped.")

    def handle_button_press(self, instrument_num: int):
        """
        Processes a button press with song rotation awareness.

        Args:
            instrument_num (int): The number of the instrument button pressed.
        """
        current_time = time.time()
        
        # Button cooldown check
        if (current_time - self.last_press_times.get(instrument_num, 0)) < self.button_cooldown_seconds:
            logger.debug(f"Ignoring rapid press for instrument {instrument_num}. Cooldown active.")
            return

        self.last_press_times[instrument_num] = current_time
        
        if not 1 <= instrument_num <= 18:
            logger.warning(f"Invalid instrument number received: {instrument_num}")
            return
        
        # System activation
        if not self.system_active:
            success = self._activate_system(restart_song=True)
            if not success:
                logger.error("Failed to activate system")
                return

        # Reset global timer
        self.global_expiry_time = time.time() + self.global_timeout
        logger.debug(f"Global timer reset. Expires in {self.global_timeout}s.")

        # Handle instrument toggle
        if self.instrument_active[instrument_num]:
            self._deactivate_instrument(instrument_num)
        else:
            if instrument_num in self.audio_manager.get_available_instruments():
                self._activate_instrument(instrument_num)
                self.stats_collector.record_instrument(instrument_num)
                
                # Log current song info for stats
                song_info = self.audio_manager.get_current_song_info()
                logger.debug(f"Instrument {instrument_num} activated in song '{song_info['name']}'")
            else:
                current_song = self.audio_manager.get_current_song_info()['name']
                logger.warning(f"Instrument {instrument_num} not available in song '{current_song}' (no audio file).")

    def _activate_system(self, restart_song: bool = False) -> bool:
        """
        Activates the entire system with song rotation support.

        Args:
            restart_song (bool): If True, restarts playback from the beginning.

        Returns:
            bool: True if activation was successful, False otherwise.
        """
        current_song = self.audio_manager.get_current_song_info()['name']
        logger.info(f"Activating system with song: {current_song}")
        
        success = False
        if restart_song:
            success = self.audio_manager.restart_from_beginning()
        else:
            success = self.audio_manager.start_master_playback()
        
        if success:
            self.system_active = True
            self.global_expiry_time = time.time() + self.global_timeout
            self.session_start_time = time.time()
            self.total_sessions += 1
            
            song_info = self.audio_manager.get_current_song_info()
            logger.info(f"System activated - Song: {song_info['name']} "
                       f"({song_info['index'] + 1}/{song_info['total_songs']}), "
                       f"Session #{self.total_sessions}")
        else:
            logger.error("Failed to activate audio system")
        
        return success

    def _deactivate_system(self):
        """Deactivates the system and handles song rotation."""
        session_duration = time.time() - self.session_start_time if self.session_start_time > 0 else 0
        current_song_info = self.audio_manager.get_current_song_info()
        
        logger.info(f"Global timeout reached. Session duration: {session_duration:.1f}s, "
                   f"Song was: {current_song_info['name']}")
        
        # Stop current playback
        self.audio_manager.stop_master_playback()
        self.system_active = False
        self.instrument_active = {i: False for i in range(1, 19)}
        self.instrument_expiry_times = {i: 0 for i in range(1, 19)}
        
        # Handle song rotation
        if self.enable_song_rotation and self.song_switch_on_timeout:
            self._handle_song_rotation()

    def _handle_song_rotation(self):
        """Handles automatic song switching after system deactivation."""
        try:
            old_song = self.audio_manager.get_current_song_info()['name']
            new_song = self.audio_manager.switch_to_next_song()
            
            if old_song != new_song:
                logger.info(f"Song rotation: {old_song} → {new_song}")
                
                # Log rotation stats
                song_info = self.audio_manager.get_current_song_info()
                logger.info(f"Next session will use: {song_info['name']} "
                           f"({song_info['index'] + 1}/{song_info['total_songs']} songs)")
            else:
                logger.debug("Song rotation: No change (single song or rotation disabled)")
                
        except Exception as e:
            logger.error(f"Error during song rotation: {e}")
            # Continue with current song if rotation fails

    def _activate_instrument(self, instrument_num: int):
        """
        Activates a single instrument.

        Args:
            instrument_num (int): The instrument number to activate.
        """
        current_song = self.audio_manager.get_current_song_info()['name']
        logger.info(f"Activating instrument {instrument_num} (song: {current_song})")
        
        self.instrument_active[instrument_num] = True
        self.instrument_expiry_times[instrument_num] = time.time() + self.instrument_timeout
        self.audio_manager.fade_in(instrument_num, self.fade_duration)

    def _deactivate_instrument(self, instrument_num: int):
        """
        Deactivates a single instrument.

        Args:
            instrument_num (int): The instrument number to deactivate.
        """
        logger.info(f"Deactivating instrument {instrument_num}")
        self.instrument_active[instrument_num] = False
        self.instrument_expiry_times[instrument_num] = 0
        self.audio_manager.fade_out(instrument_num, self.fade_duration)

    def _logic_loop(self):
        """
        Enhanced logic loop with song rotation monitoring.
        """
        while self.running:
            if not self.system_active:
                time.sleep(0.5)
                continue

            current_time = time.time()

            # Check global timeout
            if current_time >= self.global_expiry_time:
                self._deactivate_system()
                continue

            # Check instrument timeouts
            for i in range(1, 19):
                if self.instrument_active[i] and current_time >= self.instrument_expiry_times[i]:
                    logger.info(f"Instrument {i} timeout - fading out.")
                    self._deactivate_instrument(i)
            
            time.sleep(0.2)

    def force_song_switch(self) -> str:
        """
        Manually forces a song switch (for testing or manual control).
        
        Returns:
            str: Name of the new active song
        """
        logger.info("Manual song switch requested")
        
        # If system is active, deactivate it first
        was_active = self.system_active
        if self.system_active:
            self._deactivate_system()
        
        try:
            new_song = self.audio_manager.switch_to_next_song()
            logger.info(f"Manual song switch completed: {new_song}")
            
            # If system was active, reactivate with new song
            if was_active:
                self._activate_system(restart_song=True)
            
            return new_song
            
        except Exception as e:
            logger.error(f"Manual song switch failed: {e}")
            raise

    def get_system_status(self) -> dict:
        """Returns comprehensive system status including song info."""
        song_info = self.audio_manager.get_current_song_info()
        
        active_instruments = [i for i in range(1, 19) if self.instrument_active[i]]
        session_duration = time.time() - self.session_start_time if self.session_start_time > 0 else 0
        
        return {
            'system_active': self.system_active,
            'current_song': song_info,
            'active_instruments': active_instruments,
            'available_instruments': self.audio_manager.get_available_instruments(),
            'session_duration': session_duration,
            'total_sessions': self.total_sessions,
            'time_until_timeout': max(0, self.global_expiry_time - time.time()) if self.system_active else 0,
            'song_rotation_enabled': self.enable_song_rotation
        }
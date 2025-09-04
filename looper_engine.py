# looper_engine.py
import logging
import time
import threading
from audio_manager import AudioManager
from stats_collector import StatsCollector

logger = logging.getLogger(__name__)

class LooperEngine:
    """
    The main control unit for the audio looper.
    Manages state, timers, and interactions with the AudioManager.
    """
    
    def __init__(self, audio_manager: AudioManager, config: dict):
        """
        Initializes the looper engine.

        Args:
            audio_manager (AudioManager): The audio manager instance.
            config (dict): The configuration dictionary.
        """
        self.audio_manager = audio_manager
        self.stats_collector = StatsCollector()
        self.config = config

        self.global_timeout = self.config['timeouts']['global_timeout']
        self.instrument_timeout = self.config['timeouts']['instrument_timeout']
        self.fade_duration = self.config['timeouts']['fade_duration']
        self.button_cooldown_seconds = self.config.get('raspberry_pi', {}).get('button_cooldown_seconds', 0.8)

        self.system_active = False
        self.running = False
        self.instrument_active = {i: False for i in range(1, 19)}
        
        self.global_expiry_time = 0
        self.instrument_expiry_times = {i: 0 for i in range(1, 19)}
        self.last_press_times = {i: 0 for i in range(1, 19)}

        self.logic_thread = threading.Thread(target=self._logic_loop, daemon=True)

    def start(self):
        """Starts the main logic loop."""
        if self.running:
            return
        self.running = True
        self.logic_thread.start()
        logger.info("Looper Engine started.")

    def shutdown(self):
        """Safely shuts down the engine."""
        logger.info("Shutting down Looper Engine.")
        self.running = False
        if self.system_active:
            self._deactivate_system()
        if self.logic_thread.is_alive():
            self.logic_thread.join(timeout=1.0)
        logger.info("Looper Engine stopped.")

    def handle_button_press(self, instrument_num: int):
        """
        Processes a button press, acting as a callback for ButtonHandler.

        Args:
            instrument_num (int): The number of the instrument button pressed.
        """
        current_time = time.time()
        
        if (current_time - self.last_press_times.get(instrument_num, 0)) < self.button_cooldown_seconds:
            logger.warning(f"Ignoring rapid press for instrument {instrument_num}. Cooldown active.")
            return

        self.last_press_times[instrument_num] = current_time
        
        if not 1 <= instrument_num <= 18:
            logger.warning(f"Invalid instrument number received: {instrument_num}")
            return
        
        if not self.system_active:
            success = self._activate_system(restart_song=True)
            if not success:
                logger.error("Failed to activate system")
                return

        self.global_expiry_time = time.time() + self.global_timeout
        logger.debug(f"Global timer reset. Expires in {self.global_timeout}s.")

        if self.instrument_active[instrument_num]:
            self._deactivate_instrument(instrument_num)
        else:
            if instrument_num in self.audio_manager.get_available_instruments():
                self._activate_instrument(instrument_num)
                self.stats_collector.record_instrument(instrument_num)
            else:
                logger.warning(f"Instrument {instrument_num} not available (no audio file).")

    def _activate_system(self, restart_song: bool = False) -> bool:
        """
        Activates the entire system.

        Args:
            restart_song (bool): If True, restarts playback from the beginning.

        Returns:
            bool: True if activation was successful, False otherwise.
        """
        logger.info("Activating system...")
        
        success = False
        if restart_song:
            success = self.audio_manager.restart_from_beginning()
        else:
            success = self.audio_manager.start_master_playback()
        
        if success:
            self.system_active = True
            self.global_expiry_time = time.time() + self.global_timeout
            logger.info("System activated successfully")
        else:
            logger.error("Failed to activate audio system")
        
        return success

    def _deactivate_system(self):
        """Deactivates the entire system (after global timeout)."""
        logger.info("Global timeout reached. Deactivating system.")
        self.audio_manager.stop_master_playback()
        self.system_active = False
        self.instrument_active = {i: False for i in range(1, 19)}
        self.instrument_expiry_times = {i: 0 for i in range(1, 19)}

    def _activate_instrument(self, instrument_num: int):
        """
        Activates (turns on) a single instrument.

        Args:
            instrument_num (int): The instrument number to activate.
        """
        logger.info(f"Activating instrument {instrument_num}")
        self.instrument_active[instrument_num] = True
        self.instrument_expiry_times[instrument_num] = time.time() + self.instrument_timeout
        self.audio_manager.fade_in(instrument_num, self.fade_duration)

    def _deactivate_instrument(self, instrument_num: int):
        """
        Deactivates (turns off) a single instrument.

        Args:
            instrument_num (int): The instrument number to deactivate.
        """
        logger.info(f"Deactivating instrument {instrument_num}")
        self.instrument_active[instrument_num] = False
        self.instrument_expiry_times[instrument_num] = 0
        self.audio_manager.fade_out(instrument_num, self.fade_duration)

    def _logic_loop(self):
        """
        Main loop for checking timers.
        Runs in a separate thread.
        """
        while self.running:
            if not self.system_active:
                time.sleep(0.5)
                continue

            current_time = time.time()

            if current_time >= self.global_expiry_time:
                self._deactivate_system()
                continue

            for i in range(1, 19):
                if self.instrument_active[i] and current_time >= self.instrument_expiry_times[i]:
                    logger.info(f"Instrument {i} timeout - fading out.")
                    self._deactivate_instrument(i)
            
            time.sleep(0.2)
# looper_engine.py
"""Looper engine: business logic, timeout management, and song rotation."""

import logging
import time
import threading

from audio_manager import AudioManager
from stats_collector import StatsCollector


logger = logging.getLogger(__name__)


class LooperEngine:
    """Controls playback logic, dual-timer timeouts, and song rotation.

    Automatically advances to the next song when the global inactivity
    timeout expires. Runs its own background thread for timer checks.
    """

    def __init__(
        self,
        audio_manager: AudioManager,
        config: dict,
        stats_collector: StatsCollector,
        led_controller=None
    ):
        """Initialize the looper engine.

        Args:
            audio_manager: Shared ``AudioManager`` instance for playback
                control.
            config: Application configuration dictionary.
            stats_collector: Shared ``StatsCollector`` instance. Injected
                from the caller so that a single object is used throughout
                the application (no duplicate counters).
            led_controller: Optional best-effort LED output controller. LED
                errors must not block audio state changes.
        """
        self.audio_manager = audio_manager
        # Receive the shared instance rather than creating a duplicate.
        self.stats_collector = stats_collector
        self.led_controller = led_controller
        self.config = config

        # Timeout values loaded from configuration.
        self.global_timeout = self.config['timeouts']['global_timeout']
        self.instrument_timeout = self.config['timeouts']['instrument_timeout']
        self.fade_duration = self.config['timeouts']['fade_duration']
        self.button_cooldown_seconds = (
            self.config.get('raspberry_pi', {})
            .get('button_cooldown_seconds', 0.8)
        )

        # Song rotation settings.
        self.song_rotation_config = self.config.get('song_rotation', {})
        self.enable_song_rotation = self.song_rotation_config.get(
            'enable', True
        )
        self.song_switch_on_timeout = self.song_rotation_config.get(
            'switch_on_global_timeout', True
        )

        # System-wide playback state.
        self.system_active = False
        self.running = False
        self.instrument_active = {i: False for i in range(1, 19)}

        # Per-instrument and global expiry timestamps.
        self.global_expiry_time = 0
        self.instrument_expiry_times = {i: 0 for i in range(1, 19)}
        self.last_press_times = {i: 0 for i in range(1, 19)}

        # Session statistics.
        self.session_start_time = 0
        self.total_sessions = 0

        # --- FIX P1 + P3 ---
        # Single lock that serialises every state-changing operation:
        # handle_button_press, _activate_system, _deactivate_system.
        #
        # Why one lock instead of two separate ones:
        #   - _activate_system and _deactivate_system both touch
        #     system_active, audio_manager, and instrument_active.
        #   - Using two different locks would risk deadlock or still
        #     allow interleaving between activate and deactivate.
        #   - handle_button_press already holds this lock when it calls
        #     _activate_system, so _logic_loop (which also calls
        #     _deactivate_system) will block until the press is fully
        #     processed before it can deactivate.
        #
        # _logic_loop acquires the lock only for the deactivate call,
        # so the 200 ms sleep between checks is NOT held under the lock
        # and audio playback is never blocked.
        self._state_lock = threading.Lock()

        self.logic_thread = threading.Thread(
            target=self._logic_loop, daemon=True
        )

    def start(self):
        """Start the background logic loop thread."""
        if self.running:
            return
        self.running = True
        self.logic_thread.start()
        logger.info(
            "Enhanced Looper Engine with song rotation started."
        )

    def shutdown(self):
        """Stop the logic loop and deactivate the system if it is running."""
        logger.info("Shutting down Enhanced Looper Engine.")
        self.running = False
        with self._state_lock:
            if self.system_active:
                self._deactivate_system()
        if self.logic_thread.is_alive():
            self.logic_thread.join(timeout=1.0)
        logger.info("Enhanced Looper Engine stopped.")

    def handle_button_press(self, instrument_num: int):
        """Process a single button press event.

        Acquires ``_state_lock`` for the full duration so that two
        simultaneous presses (e.g. two visitors at the same time) cannot
        both see ``system_active == False`` and both try to start
        playback at the same time.

        Args:
            instrument_num: Instrument number corresponding to the pressed
                button (1–18).
        """
        current_time = time.time()

        # Cooldown check BEFORE acquiring the lock so we never block the
        # lock for a press that will be discarded anyway.
        if ((current_time - self.last_press_times.get(instrument_num, 0))
                < self.button_cooldown_seconds):
            logger.debug(
                f"Ignoring rapid press for instrument {instrument_num}. "
                f"Cooldown active."
            )
            return

        if not 1 <= instrument_num <= 18:
            logger.warning(
                f"Invalid instrument number received: {instrument_num}"
            )
            return

        with self._state_lock:
            # Re-read time inside the lock so the cooldown stamp is
            # accurate even if we waited briefly for the lock.
            self.last_press_times[instrument_num] = time.time()

            # Activate the system on the first button press from idle state.
            if not self.system_active:
                success = self._activate_system(restart_song=True)
                if not success:
                    logger.error("Failed to activate system")
                    return

            # Any valid press resets the global inactivity timer.
            self.global_expiry_time = time.time() + self.global_timeout
            logger.debug(
                f"Global timer reset. Expires in {self.global_timeout}s."
            )

            # Toggle the pressed instrument on or off.
            if self.instrument_active[instrument_num]:
                self._deactivate_instrument(instrument_num)
            else:
                if instrument_num in self.audio_manager.get_available_instruments():
                    self._activate_instrument(instrument_num)
                    self.stats_collector.record_instrument(instrument_num)

                    song_info = self.audio_manager.get_current_song_info()
                    logger.debug(
                        f"Instrument {instrument_num} activated in song "
                        f"'{song_info['name']}'"
                    )
                else:
                    current_song = (
                        self.audio_manager.get_current_song_info()['name']
                    )
                    logger.warning(
                        f"Instrument {instrument_num} not available in song "
                        f"'{current_song}' (no audio file)."
                    )

    def _activate_system(self, restart_song: bool = False) -> bool:
        """Start audio playback and initialize session tracking.

        Must be called with ``_state_lock`` held.

        Args:
            restart_song: If True, reset the playback position to the
                beginning before starting.

        Returns:
            True if activation succeeded, False otherwise.
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
            logger.info(
                f"System activated - Song: {song_info['name']} "
                f"({song_info['index'] + 1}/{song_info['total_songs']}), "
                f"Session #{self.total_sessions}"
            )
        else:
            logger.error("Failed to activate audio system")

        return success

    def _deactivate_system(self):
        """Stop playback, reset all instrument states, and trigger rotation.

        Must be called with ``_state_lock`` held.
        """
        session_duration = (
            time.time() - self.session_start_time
            if self.session_start_time > 0 else 0
        )
        current_song_info = self.audio_manager.get_current_song_info()

        logger.info(
            f"Global timeout reached. Session duration: "
            f"{session_duration:.1f}s, Song was: "
            f"{current_song_info['name']}"
        )

        self.audio_manager.stop_master_playback()
        self.system_active = False
        self.instrument_active = {i: False for i in range(1, 19)}
        self.instrument_expiry_times = {i: 0 for i in range(1, 19)}
        self._sync_leds([])

        # Advance to the next song if rotation is enabled.
        if self.enable_song_rotation and self.song_switch_on_timeout:
            self._handle_song_rotation()

    def _handle_song_rotation(self):
        """Advance to the next song after the current session ends.

        Must be called with ``_state_lock`` held.
        """
        try:
            old_song = self.audio_manager.get_current_song_info()['name']
            new_song = self.audio_manager.switch_to_next_song()

            if old_song != new_song:
                logger.info(f"Song rotation: {old_song} -> {new_song}")

                song_info = self.audio_manager.get_current_song_info()
                logger.info(
                    f"Next session will use: {song_info['name']} "
                    f"({song_info['index'] + 1}/"
                    f"{song_info['total_songs']} songs)"
                )
            else:
                logger.debug(
                    "Song rotation: No change (single song or rotation "
                    "disabled)"
                )

        except Exception as e:
            logger.error(f"Error during song rotation: {e}")
            # Continue with the current song if loading the next one fails.

    def _set_led_state(self, instrument_num: int, active: bool):
        """Best-effort LED update for one instrument."""
        if not self.led_controller:
            return
        try:
            self.led_controller.set_layer_active(instrument_num, active)
        except Exception as exc:
            logger.warning(
                "LED update failed for instrument %s: %s",
                instrument_num,
                exc,
            )

    def _sync_leds(self, active_layers):
        """Best-effort LED sync for the complete active layer list."""
        if not self.led_controller:
            return
        try:
            self.led_controller.sync_from_active_layers(active_layers)
        except Exception as exc:
            logger.warning("LED sync failed: %s", exc)

    def _activate_instrument(self, instrument_num: int):
        """Fade in a single instrument and start its individual timer.

        Must be called with ``_state_lock`` held.

        Args:
            instrument_num: Instrument number to activate (1–18).
        """
        current_song = self.audio_manager.get_current_song_info()['name']
        logger.info(
            f"Activating instrument {instrument_num} (song: {current_song})"
        )

        self.instrument_active[instrument_num] = True
        self.instrument_expiry_times[instrument_num] = (
            time.time() + self.instrument_timeout
        )
        self.audio_manager.fade_in(instrument_num, self.fade_duration)
        self._set_led_state(instrument_num, True)

    def _deactivate_instrument(self, instrument_num: int):
        """Fade out a single instrument and clear its timer.

        Must be called with ``_state_lock`` held.

        Args:
            instrument_num: Instrument number to deactivate (1–18).
        """
        logger.info(f"Deactivating instrument {instrument_num}")
        self.instrument_active[instrument_num] = False
        self.instrument_expiry_times[instrument_num] = 0
        self.audio_manager.fade_out(instrument_num, self.fade_duration)
        self._set_led_state(instrument_num, False)

    def _logic_loop(self):
        """Background loop that evaluates global and per-instrument timeouts.

        Sleeps for 0.5 s while the system is idle and for 0.2 s while
        active, keeping CPU usage minimal.

        The lock is acquired only for the actual state-change calls, NOT
        during the sleep, so audio playback is never blocked by this loop.
        """
        while self.running:
            if not self.system_active:
                time.sleep(0.5)
                continue

            current_time = time.time()

            # Check timeouts under the lock to avoid racing with
            # handle_button_press activating the system at the same moment.
            with self._state_lock:
                # Re-check inside the lock: a button press may have already
                # reset the timer or deactivated the system while we waited.
                if not self.system_active:
                    continue

                if current_time >= self.global_expiry_time:
                    self._deactivate_system()
                    continue

                # Fade out any instruments whose individual timers expired.
                for i in range(1, 19):
                    if (self.instrument_active[i]
                            and current_time >= self.instrument_expiry_times[i]):
                        logger.info(f"Instrument {i} timeout - fading out.")
                        self._deactivate_instrument(i)

            time.sleep(0.2)

    def force_song_switch(self) -> str:
        """Force an immediate song switch, regardless of session state.

        If the system is currently active it is deactivated first, then
        reactivated with the new song after the switch.

        Returns:
            Name of the newly active song.

        Raises:
            Exception: Propagates any exception raised by
                ``audio_manager.switch_to_next_song()``.
        """
        logger.info("Manual song switch requested")

        with self._state_lock:
            was_active = self.system_active
            if self.system_active:
                self._deactivate_system()

            try:
                new_song = self.audio_manager.switch_to_next_song()
                logger.info(f"Manual song switch completed: {new_song}")

                if was_active:
                    self._activate_system(restart_song=True)

                return new_song

            except Exception as e:
                logger.error(f"Manual song switch failed: {e}")
                raise

    def get_system_status(self) -> dict:
        """Return a snapshot of the current system state.

        Returns:
            Dictionary containing playback state, active song info,
            per-instrument status, session counters, and timeout values.
        """
        song_info = self.audio_manager.get_current_song_info()

        active_instruments = [
            i for i in range(1, 19) if self.instrument_active[i]
        ]
        session_duration = (
            time.time() - self.session_start_time
            if self.session_start_time > 0 else 0
        )

        return {
            'system_active': self.system_active,
            'current_song': song_info,
            'active_instruments': active_instruments,
            'available_instruments': (
                self.audio_manager.get_available_instruments()
            ),
            'session_duration': session_duration,
            'total_sessions': self.total_sessions,
            'time_until_timeout': (
                max(0, self.global_expiry_time - time.time())
                if self.system_active else 0
            ),
            'song_rotation_enabled': self.enable_song_rotation
        }
"""Looper engine: business logic, timeout management, and song rotation."""

from __future__ import annotations

from enum import Enum
import logging
import time
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audio_loop.audio.manager import AudioManager
    from audio_loop.stats.collector import StatsCollector


logger = logging.getLogger(__name__)


class InstrumentState(Enum):
    """Button-state machine state for one audio layer."""

    OFF_READY = "off_ready"
    ON_LOCKED = "on_locked"
    ON_READY = "on_ready"
    OFF_COOLDOWN = "off_cooldown"


class LooperEngine:
    """Controls playback logic, button state, timeouts, and song rotation."""

    def __init__(
        self,
        audio_manager: AudioManager,
        config: dict,
        stats_collector: StatsCollector,
        led_controller=None,
    ):
        """Initialize the looper engine."""
        self.audio_manager = audio_manager
        self.stats_collector = stats_collector
        self.led_controller = led_controller
        self.config = config

        self.max_instruments = max(
            1,
            int(
                self.config.get("performance", {})
                .get("max_concurrent_sounds", 16)
            ),
        )

        # Timeout values loaded from configuration.
        self.global_timeout = self.config["timeouts"]["global_timeout"]
        self.instrument_timeout = self.config["timeouts"]["instrument_timeout"]
        self.fade_duration = self.config["timeouts"]["fade_duration"]

        input_config = self.config.get("inputs", {})
        self.min_on_seconds = float(input_config.get("min_on_seconds", 1.5))
        self.rearm_seconds = float(input_config.get("rearm_seconds", 0.2))

        # Song rotation settings.
        self.song_rotation_config = self.config.get("song_rotation", {})
        self.enable_song_rotation = self.song_rotation_config.get("enable", True)
        self.song_switch_on_timeout = self.song_rotation_config.get(
            "switch_on_global_timeout", True
        )

        # System-wide playback state.
        self.system_active = False
        self.running = False

        # Per-instrument button/audio state.
        self.instrument_states = self._new_state_map(InstrumentState.OFF_READY)
        self.instrument_expiry_times = self._new_float_map()
        self.instrument_activated_at = self._new_float_map()
        self.instrument_deactivated_at = self._new_float_map()

        # Session statistics.
        self.session_start_time = 0
        self.total_sessions = 0

        # Single lock that serializes every state-changing operation.
        self._state_lock = threading.Lock()

        self.logic_thread = threading.Thread(
            target=self._logic_loop,
            daemon=True,
        )

    def _instrument_numbers(self):
        return range(1, self.max_instruments + 1)

    def _new_state_map(self, state: InstrumentState) -> dict[int, InstrumentState]:
        return {instrument: state for instrument in self._instrument_numbers()}

    def _new_float_map(self) -> dict[int, float]:
        return {instrument: 0.0 for instrument in self._instrument_numbers()}

    @staticmethod
    def _state_is_active(state: InstrumentState) -> bool:
        return state in (InstrumentState.ON_LOCKED, InstrumentState.ON_READY)

    def _active_instruments_unlocked(self) -> list[int]:
        return [
            instrument
            for instrument in self._instrument_numbers()
            if self._state_is_active(self.instrument_states[instrument])
        ]

    def _reset_instrument_states_unlocked(self):
        self.instrument_states = self._new_state_map(InstrumentState.OFF_READY)
        self.instrument_expiry_times = self._new_float_map()
        self.instrument_activated_at = self._new_float_map()
        self.instrument_deactivated_at = self._new_float_map()

    def _reset_global_timer_unlocked(self, now: float | None = None):
        now = time.time() if now is None else now
        self.global_expiry_time = now + self.global_timeout
        logger.debug("Global timer reset. Expires in %ss.", self.global_timeout)

    def start(self):
        """Start the background logic loop thread."""
        if self.running:
            return
        self.running = True
        self.logic_thread.start()
        logger.info("Enhanced Looper Engine with song rotation started.")

    def shutdown(self):
        """Stop the logic loop and deactivate the system if it is running."""
        logger.info("Shutting down Enhanced Looper Engine.")
        self.running = False
        with self._state_lock:
            if self.system_active:
                self._deactivate_system()
            else:
                self._reset_instrument_states_unlocked()
                self._sync_leds([])
        if self.logic_thread.is_alive():
            self.logic_thread.join(timeout=1.0)
        logger.info("Enhanced Looper Engine stopped.")

    def handle_button_press(self, instrument_num: int):
        """Process one physical or remote button press event."""
        if not 1 <= instrument_num <= self.max_instruments:
            logger.warning("Invalid instrument number received: %s", instrument_num)
            return

        with self._state_lock:
            now = time.time()
            self._advance_instrument_states_unlocked(now)
            state = self.instrument_states[instrument_num]

            if state == InstrumentState.OFF_READY:
                if instrument_num not in self.audio_manager.get_available_instruments():
                    current_song = self.audio_manager.get_current_song_info()["name"]
                    logger.warning(
                        "Instrument %s not available in song '%s' (no audio file).",
                        instrument_num,
                        current_song,
                    )
                    return

                if not self.system_active:
                    success = self._activate_system(restart_song=True)
                    if not success:
                        logger.error("Failed to activate system")
                        return
                    now = time.time()

                self._reset_global_timer_unlocked(now)
                self._activate_instrument(instrument_num, now=now)
                self.stats_collector.record_instrument(instrument_num)

                song_info = self.audio_manager.get_current_song_info()
                logger.debug(
                    "Instrument %s activated in song '%s'",
                    instrument_num,
                    song_info["name"],
                )
                return

            if state == InstrumentState.ON_LOCKED:
                logger.debug(
                    "Ignoring press for instrument %s: minimum-on lock active.",
                    instrument_num,
                )
                return

            if state == InstrumentState.ON_READY:
                self._reset_global_timer_unlocked(now)
                self._deactivate_instrument(instrument_num, now=now)
                return

            if state == InstrumentState.OFF_COOLDOWN:
                logger.debug(
                    "Ignoring press for instrument %s: re-arm cooldown active.",
                    instrument_num,
                )
                return

    def _activate_system(self, restart_song: bool = False) -> bool:
        """Start audio playback and initialize session tracking.

        Must be called with ``_state_lock`` held.
        """
        current_song = self.audio_manager.get_current_song_info()["name"]
        logger.info("Activating system with song: %s", current_song)

        if restart_song:
            success = self.audio_manager.restart_from_beginning()
        else:
            success = self.audio_manager.start_master_playback()

        if success:
            self.system_active = True
            self._reset_global_timer_unlocked()
            self.session_start_time = time.time()
            self.total_sessions += 1

            song_info = self.audio_manager.get_current_song_info()
            logger.info(
                "System activated - Song: %s (%s/%s), Session #%s",
                song_info["name"],
                song_info["index"] + 1,
                song_info["total_songs"],
                self.total_sessions,
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
            if self.session_start_time > 0
            else 0
        )
        current_song_info = self.audio_manager.get_current_song_info()

        logger.info(
            "Global timeout reached. Session duration: %.1fs, Song was: %s",
            session_duration,
            current_song_info["name"],
        )

        self.audio_manager.stop_master_playback()
        self.system_active = False
        self._reset_instrument_states_unlocked()
        self._sync_leds([])

        if self.enable_song_rotation and self.song_switch_on_timeout:
            self._handle_song_rotation()

    def _handle_song_rotation(self):
        """Advance to the next song after the current session ends.

        Must be called with ``_state_lock`` held.
        """
        try:
            old_song = self.audio_manager.get_current_song_info()["name"]
            new_song = self.audio_manager.switch_to_next_song()

            if old_song != new_song:
                logger.info("Song rotation: %s -> %s", old_song, new_song)

                song_info = self.audio_manager.get_current_song_info()
                logger.info(
                    "Next session will use: %s (%s/%s songs)",
                    song_info["name"],
                    song_info["index"] + 1,
                    song_info["total_songs"],
                )
            else:
                logger.debug(
                    "Song rotation: No change (single song or rotation disabled)"
                )

        except Exception as exc:
            logger.error("Error during song rotation: %s", exc)

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

    def _activate_instrument(self, instrument_num: int, now: float | None = None):
        """Fade in one instrument and start its individual timer.

        Must be called with ``_state_lock`` held.
        """
        now = time.time() if now is None else now
        current_song = self.audio_manager.get_current_song_info()["name"]
        logger.info(
            "Activating instrument %s (song: %s)",
            instrument_num,
            current_song,
        )

        self.instrument_states[instrument_num] = InstrumentState.ON_LOCKED
        self.instrument_activated_at[instrument_num] = now
        self.instrument_expiry_times[instrument_num] = now + self.instrument_timeout
        self.audio_manager.fade_in(instrument_num, self.fade_duration)
        self._set_led_state(instrument_num, True)

    def _deactivate_instrument(self, instrument_num: int, now: float | None = None):
        """Fade out one instrument and start its re-arm cooldown.

        Must be called with ``_state_lock`` held.
        """
        now = time.time() if now is None else now
        logger.info("Deactivating instrument %s", instrument_num)
        self.instrument_states[instrument_num] = InstrumentState.OFF_COOLDOWN
        self.instrument_deactivated_at[instrument_num] = now
        self.instrument_expiry_times[instrument_num] = 0
        self.audio_manager.fade_out(instrument_num, self.fade_duration)
        self._set_led_state(instrument_num, False)

    def _advance_instrument_states_unlocked(self, now: float):
        """Advance timed button-state transitions.

        Must be called with ``_state_lock`` held.
        """
        for instrument in self._instrument_numbers():
            state = self.instrument_states[instrument]

            if state == InstrumentState.ON_LOCKED:
                if now - self.instrument_activated_at[instrument] >= self.min_on_seconds:
                    self.instrument_states[instrument] = InstrumentState.ON_READY

            elif state == InstrumentState.OFF_COOLDOWN:
                if now - self.instrument_deactivated_at[instrument] >= self.rearm_seconds:
                    self.instrument_states[instrument] = InstrumentState.OFF_READY

    def _logic_loop(self):
        """Background loop that evaluates state transitions and timeouts."""
        while self.running:
            if not self.system_active:
                time.sleep(0.5)
                continue

            current_time = time.time()

            with self._state_lock:
                if not self.system_active:
                    continue

                self._advance_instrument_states_unlocked(current_time)

                if current_time >= self.global_expiry_time:
                    self._deactivate_system()
                    continue

                for instrument in self._instrument_numbers():
                    state = self.instrument_states[instrument]
                    expiry = self.instrument_expiry_times[instrument]
                    if (
                        self._state_is_active(state)
                        and expiry > 0
                        and current_time >= expiry
                    ):
                        logger.info(
                            "Instrument %s timeout - fading out.",
                            instrument,
                        )
                        self._deactivate_instrument(instrument, now=current_time)

            time.sleep(0.2)

    def force_song_switch(self) -> str:
        """Force an immediate song switch, regardless of session state."""
        logger.info("Manual song switch requested")

        with self._state_lock:
            was_active = self.system_active
            if self.system_active:
                self._deactivate_system()

            try:
                new_song = self.audio_manager.switch_to_next_song()
                logger.info("Manual song switch completed: %s", new_song)

                if was_active:
                    self._activate_system(restart_song=True)

                return new_song

            except Exception as exc:
                logger.error("Manual song switch failed: %s", exc)
                raise

    def get_system_status(self) -> dict:
        """Return a snapshot of the current system state."""
        now = time.time()
        with self._state_lock:
            active_instruments = self._active_instruments_unlocked()
            instrument_states = {
                instrument: self.instrument_states[instrument].value
                for instrument in self._instrument_numbers()
                if self.instrument_states[instrument] != InstrumentState.OFF_READY
            }
            session_duration = (
                now - self.session_start_time
                if self.session_start_time > 0
                else 0
            )
            time_until_timeout = (
                max(0, self.global_expiry_time - now)
                if self.system_active
                else 0
            )
            system_active = self.system_active
            total_sessions = self.total_sessions

        song_info = self.audio_manager.get_current_song_info()

        return {
            "system_active": system_active,
            "current_song": song_info,
            "active_instruments": active_instruments,
            "available_instruments": self.audio_manager.get_available_instruments(),
            "instrument_states": instrument_states,
            "session_duration": session_duration,
            "total_sessions": total_sessions,
            "time_until_timeout": time_until_timeout,
            "song_rotation_enabled": self.enable_song_rotation,
            "max_instruments": self.max_instruments,
        }
# audio_manager.py
"""Synchronized multi-track audio player with song rotation support."""

import sounddevice as sd
import numpy as np
import soundfile as sf
import os
import logging
import threading
from typing import Dict, Optional, List


logger = logging.getLogger(__name__)


class AudioManager:
    """Manages synchronized playback of multiple WAV tracks with song rotation.

    Only one song is loaded into RAM at a time. All tracks within a song
    share a single playback position so they remain perfectly in sync.
    """

    def __init__(self, config: dict):
        """Initialize the audio manager and load the first song.

        Args:
            config: Application configuration dictionary. Must contain
                ``'song_rotation'``, ``'jack'``, and ``'audio'`` keys.
        """
        self.config = config

        self.max_instruments = max(
            1,
            int(config.get('performance', {}).get('max_concurrent_sounds', 16)),
        )

        # Song rotation configuration.
        self.song_config = config.get('song_rotation', {})
        self.available_songs = self.song_config.get(
            'song_folders', ['song1']
        )
        self.current_song_index = 0
        self.current_song_name = (
            self.available_songs[0] if self.available_songs else 'song1'
        )

        # Audio device settings.
        self.sample_rate = None  # Determined from the first loaded audio file.
        self.block_size = config['jack'].get('buffer_size', 1024)

        # Single master position shared by all tracks for tight synchronization.
        self.master_position = 0
        self.loop_length_samples = 0
        self.loop_length_seconds = 0.0

        # Audio data for the currently loaded song only.
        self.audio_tracks: Dict[int, np.ndarray] = {}

        # Protects audio_tracks and loop_length_samples from race conditions
        # between the audio callback thread and the song-switch thread.
        self.audio_data_lock = threading.Lock()

        # Per-track volume state for fade-in / fade-out.
        self.master_playing = False
        self.volumes: Dict[int, float] = {i: 0.0 for i in self._instrument_numbers()}
        self.target_volumes: Dict[int, float] = {
            i: 0.0 for i in self._instrument_numbers()
        }
        self.fade_rates: Dict[int, float] = {i: 0.0 for i in self._instrument_numbers()}

        # Guards ``song_switch_pending`` and coordinates switch silence.
        self.song_switch_pending = False
        self.song_switch_lock = threading.Lock()

        self.output_stream: Optional[sd.OutputStream] = None

        self._validate_song_folders()
        self._load_current_song()
        self._setup_audio_device()

    def _instrument_numbers(self):
        return range(1, self.max_instruments + 1)

    def _validate_song_folders(self):
        """Validate configured song folders and update the available list.

        Folders that do not exist or contain no WAV files are removed from
        ``available_songs``. Falls back to the root ``audio_files``
        directory if no valid folders are found.
        """
        audio_base_dir = (
            self.config.get('song_rotation', {})
            .get('base_directory', 'audio_files')
        )

        valid_songs = []
        for song_name in self.available_songs:
            song_path = os.path.join(audio_base_dir, song_name)
            if os.path.exists(song_path) and os.path.isdir(song_path):
                wav_files = [
                    f for f in os.listdir(song_path) if f.endswith('.wav')
                ]
                if wav_files:
                    valid_songs.append(song_name)
                    logger.info(
                        f"Found valid song folder: {song_name} "
                        f"({len(wav_files)} audio files)"
                    )
                else:
                    logger.warning(
                        f"Song folder '{song_name}' exists but contains "
                        f"no .wav files"
                    )
            else:
                logger.warning(
                    f"Song folder '{song_name}' not found at {song_path}"
                )

        if not valid_songs:
            # No valid subfolders found: use the base directory directly.
            logger.warning(
                "No valid song folders found, falling back to default "
                "'audio_files' directory"
            )
            self.available_songs = ['default']
            self.current_song_name = 'default'
        else:
            self.available_songs = valid_songs
            self.current_song_name = valid_songs[0]

        logger.info(f"Available songs: {self.available_songs}")

    def _get_song_directory(self, song_name: str = None) -> str:
        """Return the filesystem path for the given song.

        Args:
            song_name: Song identifier. Defaults to the currently active
                song if not provided.

        Returns:
            Absolute or relative path to the song's directory.
        """
        if song_name is None:
            song_name = self.current_song_name

        audio_base_dir = (
            self.config.get('song_rotation', {})
            .get('base_directory', 'audio_files')
        )

        if song_name == 'default':
            return audio_base_dir
        else:
            return os.path.join(audio_base_dir, song_name)

    def _load_current_song(self):
        """Load all WAV tracks for the active song into RAM.

        Clears the previous song's data first, reads each ``N.wav``
        file within the configured instrument range, normalises all tracks to the same length, and
        atomically replaces the shared audio data under ``audio_data_lock``.

        Raises:
            FileNotFoundError: If the song directory does not exist.
            RuntimeError: If no audio files could be loaded.
            ValueError: If tracks within the song have inconsistent sample
                rates, or if the song's sample rate differs from the already
                running audio stream (which would cause silent pitch/tempo
                distortion).
        """
        song_dir = self._get_song_directory()

        logger.info(
            f"Loading song: {self.current_song_name} from {song_dir}"
        )

        temp_tracks = {}
        sample_rates = []

        if not os.path.exists(song_dir):
            raise FileNotFoundError(
                f"Song directory '{song_dir}' not found."
            )

        # Attempt to load tracks in the configured instrument range.
        for i in self._instrument_numbers():
            filepath = os.path.join(song_dir, f"{i}.wav")
            if os.path.exists(filepath):
                try:
                    data, sr = sf.read(filepath, dtype=np.float32)

                    # Downmix stereo to mono by averaging channels.
                    if len(data.shape) > 1:
                        data = np.mean(data, axis=1)

                    temp_tracks[i] = data
                    sample_rates.append(sr)
                    logger.debug(
                        f"Loaded {self.current_song_name}/{i}.wav: "
                        f"{len(data)} samples at {sr}Hz"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to load {self.current_song_name}/{i}.wav: "
                        f"{e}"
                    )

        if not temp_tracks:
            raise RuntimeError(
                f"No audio files loaded for song '{self.current_song_name}'!"
            )

        # --- FIX P4: Sample rate consistency checks ---

        # 1. All tracks within the same song must share one sample rate.
        unique_rates = set(sample_rates)
        if len(unique_rates) > 1:
            raise ValueError(
                f"Song '{self.current_song_name}' contains tracks with "
                f"mixed sample rates: {unique_rates}. "
                f"All WAV files in a song folder must use the same rate."
            )

        new_sample_rate = int(sample_rates[0])

        # 2. The new song's sample rate must match the already-open stream.
        #    Changing sample rate mid-run would require closing and re-opening
        #    the OutputStream. If it differs, we log a clear error and abort
        #    the switch so the previous song keeps playing rather than
        #    producing silent or pitch-shifted audio with no warning.
        if self.sample_rate is not None and new_sample_rate != self.sample_rate:
            raise ValueError(
                f"Song '{self.current_song_name}' has sample rate "
                f"{new_sample_rate} Hz but the audio stream is running at "
                f"{self.sample_rate} Hz. All songs must use the same sample "
                f"rate, or stop/restart the stream between songs. "
                f"Song switch aborted."
            )

        # Derive loop length from the longest track.
        max_length = max(len(data) for data in temp_tracks.values())
        new_loop_length_samples = max_length
        new_loop_length_seconds = max_length / new_sample_rate

        # Honour the optional maximum loop length cap from configuration.
        max_loop_seconds = self.config.get('audio', {}).get('max_loop_length')
        if max_loop_seconds and new_loop_length_seconds > max_loop_seconds:
            new_loop_length_samples = int(max_loop_seconds * new_sample_rate)
            new_loop_length_seconds = max_loop_seconds

        # Pad shorter tracks with zeros and truncate longer ones so that
        # every track has exactly the same number of samples.
        new_audio_tracks = {}
        for i, data in temp_tracks.items():
            if len(data) > new_loop_length_samples:
                new_audio_tracks[i] = data[:new_loop_length_samples]
            elif len(data) < new_loop_length_samples:
                padding = new_loop_length_samples - len(data)
                new_audio_tracks[i] = np.pad(data, (0, padding), 'constant')
            else:
                new_audio_tracks[i] = data

        # Atomically replace the shared audio data while holding the lock
        # so the audio callback never sees a partially updated state.
        with self.audio_data_lock:
            self.audio_tracks.clear()
            self.audio_tracks.update(new_audio_tracks)
            self.sample_rate = new_sample_rate
            self.loop_length_samples = new_loop_length_samples
            self.loop_length_seconds = new_loop_length_seconds

        logger.info(
            f"Song '{self.current_song_name}' loaded: "
            f"{len(self.audio_tracks)} tracks, "
            f"{self.loop_length_seconds:.2f}s duration, "
            f"{self.sample_rate}Hz"
        )

    def _setup_audio_device(self):
        """Apply audio device settings and verify they are supported.

        Raises:
            Exception: Propagates any exception raised by
                ``sounddevice.check_output_settings()``.
        """
        try:
            sd.default.samplerate = self.sample_rate
            sd.default.blocksize = self.block_size
            sd.default.dtype = np.float32

            output_device = self.config.get('audio', {}).get('output_device')
            if output_device:
                sd.default.device[1] = output_device
                logger.info(
                    f"Using audio output device: {output_device}"
                )

            sd.check_output_settings()
            logger.info("Audio device settings successfully checked.")
        except Exception as e:
            logger.error(f"Audio device setup failed: {e}")
            raise

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time,
        status
    ):
        """Fill the output buffer with the current mix of active tracks.

        Called by the sounddevice audio thread on every buffer period.
        Uses a non-blocking lock acquisition: if ``audio_data_lock`` is
        held by the song-switch thread, silence is returned immediately
        rather than blocking the real-time audio thread.

        Args:
            outdata: Output buffer to fill (shape: [frames, 1]).
            frames: Number of audio frames requested.
            time: sounddevice timing information (unused).
            status: sounddevice status flags.
        """
        if status:
            logger.debug(f"Audio status: {status}")

        outdata.fill(0.0)

        # Output silence while a song switch is in progress.
        with self.song_switch_lock:
            if self.song_switch_pending:
                return

        if not self.master_playing:
            return

        # Non-blocking acquire: return silence if data is being replaced.
        if not self.audio_data_lock.acquire(blocking=False):
            return

        try:
            if not self.audio_tracks:
                return

            pos = self.master_position % self.loop_length_samples
            available_until_loop = self.loop_length_samples - pos

            if frames <= available_until_loop:
                # Simple case: the requested frames do not cross the loop end.
                for track_id, track_data in self.audio_tracks.items():
                    volume = self.volumes[track_id]
                    if volume > 0.001:
                        outdata[:frames, 0] += (
                            track_data[pos:pos + frames] * volume
                        )

                self.master_position += frames
            else:
                # Wrap-around case: split the buffer across the loop boundary.
                first_part = available_until_loop
                second_part = frames - first_part

                for track_id, track_data in self.audio_tracks.items():
                    volume = self.volumes[track_id]
                    if volume > 0.001:
                        if first_part > 0:
                            outdata[:first_part, 0] += (
                                track_data[pos:pos + first_part] * volume
                            )
                        if second_part > 0:
                            outdata[first_part:frames, 0] += (
                                track_data[:second_part] * volume
                            )

                self.master_position = second_part
        finally:
            self.audio_data_lock.release()

        # Apply linear volume fading for each track toward its target level.
        for track_id in self._instrument_numbers():
            current_vol = self.volumes[track_id]
            target_vol = self.target_volumes[track_id]
            fade_rate = self.fade_rates[track_id]

            if abs(current_vol - target_vol) > 0.0001 and fade_rate > 0:
                volume_change = fade_rate * frames
                if current_vol < target_vol:
                    self.volumes[track_id] = min(
                        target_vol, current_vol + volume_change
                    )
                else:
                    self.volumes[track_id] = max(
                        target_vol, current_vol - volume_change
                    )

        # Hard clip to prevent digital clipping on the output.
        np.clip(outdata, -0.95, 0.95, out=outdata)

    def switch_to_next_song(self) -> str:
        """Advance to the next song in the rotation list.

        No-op if only one song is available. Loads the new song and
        resets the playback position before releasing the switch lock.

        If the new song has a different sample rate than the current stream,
        ``_load_current_song`` will raise ``ValueError`` and the switch is
        aborted: the index is rolled back so the next rotation attempt
        tries the same song again (it won't succeed either, but at least
        the system stays consistent and logs a clear error).

        Returns:
            Name of the newly active song.

        Raises:
            Exception: Propagates loading failures after resetting the
                switch-pending flag.
        """
        if len(self.available_songs) <= 1:
            logger.info("Only one song available, no switching needed")
            return self.current_song_name

        with self.song_switch_lock:
            self.song_switch_pending = True

            # Silence all tracks immediately during the switch.
            for i in self._instrument_numbers():
                self.volumes[i] = 0.0
                self.target_volumes[i] = 0.0

            # Advance the index cyclically through the song list.
            previous_index = self.current_song_index
            self.current_song_index = (
                (self.current_song_index + 1) % len(self.available_songs)
            )
            self.current_song_name = (
                self.available_songs[self.current_song_index]
            )

            logger.info(
                f"Switching to song: {self.current_song_name} "
                f"({self.current_song_index + 1}/"
                f"{len(self.available_songs)})"
            )

            try:
                # _load_current_song performs an atomic swap under
                # audio_data_lock. It also validates sample rate consistency
                # and raises ValueError if the new song cannot be used with
                # the current stream.
                self._load_current_song()

                self.master_position = 0

                # _setup_audio_device updates sd.default.* for the NEXT
                # stream open. The currently running stream is unaffected,
                # which is correct because _load_current_song already
                # verified the sample rate matches.
                self._setup_audio_device()

                self.song_switch_pending = False
                logger.info(
                    f"Successfully switched to song: {self.current_song_name}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to switch to song "
                    f"'{self.current_song_name}': {e}"
                )
                # Roll back index so the system stays on the previous song.
                self.current_song_index = previous_index
                self.current_song_name = (
                    self.available_songs[previous_index]
                )
                self.song_switch_pending = False
                raise

        return self.current_song_name

    def get_current_song_info(self) -> dict:
        """Return metadata about the currently loaded song.

        Returns:
            Dictionary with keys: ``'name'``, ``'index'``,
            ``'total_songs'``, ``'available_instruments'``,
            ``'duration_seconds'``, and ``'next_song'``.
        """
        return {
            'name': self.current_song_name,
            'index': self.current_song_index,
            'total_songs': len(self.available_songs),
            'available_instruments': list(self.audio_tracks.keys()),
            'duration_seconds': self.loop_length_seconds,
            'next_song': self.available_songs[
                (self.current_song_index + 1) % len(self.available_songs)
            ]
        }

    def start_master_playback(self) -> bool:
        """Open the audio output stream and begin playback.

        Returns:
            True if the stream started successfully, False on error.
        """
        if self.master_playing:
            logger.debug("Master playback already active")
            return True

        try:
            logger.info(
                f"Starting playback for song: {self.current_song_name}"
            )
            self.master_position = 0

            self.output_stream = sd.OutputStream(
                callback=self._audio_callback,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=1,
                dtype=np.float32,
                latency='low'
            )

            self.output_stream.start()
            self.master_playing = True

            logger.info(
                f"Audio stream started: {self.sample_rate}Hz, "
                f"{self.block_size} samples/block"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            return False

    def stop_master_playback(self):
        """Stop the audio stream and reset all volume levels."""
        if not self.master_playing:
            return

        logger.info("Stopping master playback")
        self.master_playing = False

        if self.output_stream:
            try:
                self.output_stream.stop()
                self.output_stream.close()
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")
            finally:
                self.output_stream = None

        for i in self._instrument_numbers():
            self.volumes[i] = 0.0
            self.target_volumes[i] = 0.0

    def restart_from_beginning(self):
        """Stop playback, reset the position to zero, and restart.

        Returns:
            Return value of ``start_master_playback()``.
        """
        logger.info("Restarting loop from beginning")

        if self.master_playing:
            self.stop_master_playback()

        self.master_position = 0

        return self.start_master_playback()

    def check_stream_health(self) -> bool:
        """Verify the audio output stream is alive and restart it if not.

        Intended to be called periodically from the main application loop
        to recover from hardware events such as a USB DAC being
        disconnected and reconnected.

        Returns:
            True if the stream is healthy or was successfully restarted.
            False if the restart attempt also failed.
        """
        if not self.master_playing:
            return True  # System is idle; no stream is expected.

        if self.output_stream is None:
            logger.error(
                "Stream health check: master_playing=True but "
                "output_stream is None. Restarting..."
            )
            return self.start_master_playback()

        try:
            if not self.output_stream.active:
                logger.error(
                    "Stream health check: audio stream is no longer "
                    "active. Restarting..."
                )
                self.output_stream = None
                self.master_playing = False
                return self.start_master_playback()
        except Exception as e:
            logger.error(f"Stream health check failed: {e}")
            return False

        return True

    def fade_in(self, instrument: int, duration: float):
        """Schedule a linear fade-in for the specified instrument.

        Args:
            instrument: Instrument track number within the configured range.
            duration: Fade duration in seconds.
        """
        if instrument not in self.audio_tracks:
            logger.warning(
                f"Instrument {instrument} not available in song "
                f"'{self.current_song_name}'"
            )
            return

        if not self.master_playing:
            logger.warning("Cannot fade in: playback not active")
            return

        fade_samples = max(1, int(duration * self.sample_rate))
        self.target_volumes[instrument] = 1.0
        self.fade_rates[instrument] = 1.0 / fade_samples

        logger.debug(
            f"Fading in instrument {instrument} "
            f"(song: {self.current_song_name}) over {duration:.2f}s"
        )

    def fade_out(self, instrument: int, duration: float):
        """Schedule a linear fade-out for the specified instrument.

        Args:
            instrument: Instrument track number within the configured range.
            duration: Fade duration in seconds.
        """
        if not 1 <= instrument <= self.max_instruments:
            return

        fade_samples = max(1, int(duration * self.sample_rate))
        self.target_volumes[instrument] = 0.0
        self.fade_rates[instrument] = 1.0 / fade_samples

        logger.debug(
            f"Fading out instrument {instrument} over {duration:.2f}s"
        )

    def get_available_instruments(self) -> list:
        """Return loaded instrument track numbers for the current song.

        Returns:
            List of integer track IDs present in ``audio_tracks``.
        """
        return list(self.audio_tracks.keys())

    def shutdown(self):
        """Stop playback and release all audio resources."""
        logger.info("Shutting down AudioManager")
        self.stop_master_playback()
        with self.audio_data_lock:
            self.audio_tracks.clear()
        logger.info("AudioManager shutdown complete")
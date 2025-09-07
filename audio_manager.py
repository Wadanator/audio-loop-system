# audio_manager.py
import sounddevice as sd
import numpy as np
import soundfile as sf
import os
import logging
import threading
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class AudioManager:
    """
    Enhanced synchronized audio looper with song rotation support.
    Efficiently manages multiple songs by loading only the active song.
    """
    
    def __init__(self, config: dict):
        """
        Initializes the AudioManager with song rotation capabilities.

        Args:
            config (dict): The configuration dictionary for audio settings.
        """
        self.config = config
        
        # Song rotation configuration
        self.song_config = config.get('song_rotation', {})
        self.available_songs = self.song_config.get('song_folders', ['song1'])
        self.current_song_index = 0
        self.current_song_name = self.available_songs[0] if self.available_songs else 'song1'
        
        # Audio configuration - use native file sample rate
        self.sample_rate = None  # Will be set from first audio file
        self.block_size = config['jack'].get('buffer_size', 1024)
        
        # Master synchronization - SINGLE position for ALL tracks
        self.master_position = 0
        self.loop_length_samples = 0
        self.loop_length_seconds = 0.0
        
        # Audio data storage - only current song loaded
        self.audio_tracks: Dict[int, np.ndarray] = {}
        
        # Playback state
        self.master_playing = False
        self.volumes: Dict[int, float] = {i: 0.0 for i in range(1, 19)}
        self.target_volumes: Dict[int, float] = {i: 0.0 for i in range(1, 19)}
        self.fade_rates: Dict[int, float] = {i: 0.0 for i in range(1, 19)}
        
        # Song switching state
        self.song_switch_pending = False
        self.song_switch_lock = threading.Lock()
        
        self.output_stream: Optional[sd.OutputStream] = None
        
        # Initialize with first song
        self._validate_song_folders()
        self._load_current_song()
        self._setup_audio_device()

    def _validate_song_folders(self):
        """Validates that all configured song folders exist."""
        audio_base_dir = self.config.get('song_rotation', {}).get('base_directory', 'audio_files')
        
        valid_songs = []
        for song_name in self.available_songs:
            song_path = os.path.join(audio_base_dir, song_name)
            if os.path.exists(song_path) and os.path.isdir(song_path):
                # Check if folder has at least one .wav file
                wav_files = [f for f in os.listdir(song_path) if f.endswith('.wav')]
                if wav_files:
                    valid_songs.append(song_name)
                    logger.info(f"Found valid song folder: {song_name} ({len(wav_files)} audio files)")
                else:
                    logger.warning(f"Song folder '{song_name}' exists but contains no .wav files")
            else:
                logger.warning(f"Song folder '{song_name}' not found at {song_path}")
        
        if not valid_songs:
            # Fallback to default structure
            logger.warning("No valid song folders found, falling back to default 'audio_files' directory")
            self.available_songs = ['default']
            self.current_song_name = 'default'
        else:
            self.available_songs = valid_songs
            self.current_song_name = valid_songs[0]
        
        logger.info(f"Available songs: {self.available_songs}")

    def _get_song_directory(self, song_name: str = None) -> str:
        """Gets the directory path for a specific song."""
        if song_name is None:
            song_name = self.current_song_name
        
        audio_base_dir = self.config.get('song_rotation', {}).get('base_directory', 'audio_files')
        
        if song_name == 'default':
            return audio_base_dir
        else:
            return os.path.join(audio_base_dir, song_name)

    def _load_current_song(self):
        """Loads the currently active song, unloading the previous one to save memory."""
        song_dir = self._get_song_directory()
        
        # Clear previous song data to free memory
        self.audio_tracks.clear()
        
        logger.info(f"Loading song: {self.current_song_name} from {song_dir}")
        
        temp_tracks = {}
        sample_rates = []
        
        if not os.path.exists(song_dir):
            raise FileNotFoundError(f"Song directory '{song_dir}' not found.")
        
        # Load all available tracks for current song
        for i in range(1, 19):
            filepath = os.path.join(song_dir, f"{i}.wav")
            if os.path.exists(filepath):
                try:
                    data, sr = sf.read(filepath, dtype=np.float32)
                    
                    # Ensure mono
                    if len(data.shape) > 1:
                        data = np.mean(data, axis=1)
                    
                    temp_tracks[i] = data
                    sample_rates.append(sr)
                    logger.debug(f"Loaded {self.current_song_name}/{i}.wav: {len(data)} samples at {sr}Hz")
                    
                except Exception as e:
                    logger.error(f"Failed to load {self.current_song_name}/{i}.wav: {e}")
        
        if not temp_tracks:
            raise RuntimeError(f"No audio files loaded for song '{self.current_song_name}'!")
        
        # Set sample rate from most common rate
        from collections import Counter
        most_common_sr = Counter(sample_rates).most_common(1)[0][0]
        self.sample_rate = int(most_common_sr)
        
        # Normalize track lengths
        max_length = max(len(data) for data in temp_tracks.values())
        self.loop_length_samples = max_length
        self.loop_length_seconds = max_length / self.sample_rate
        
        # Apply max loop length limit if configured
        max_loop_seconds = self.config.get('audio', {}).get('max_loop_length')
        if max_loop_seconds and self.loop_length_seconds > max_loop_seconds:
            self.loop_length_samples = int(max_loop_seconds * self.sample_rate)
            self.loop_length_seconds = max_loop_seconds
        
        # Normalize all tracks to exact same length
        for i, data in temp_tracks.items():
            if len(data) > self.loop_length_samples:
                self.audio_tracks[i] = data[:self.loop_length_samples]
            elif len(data) < self.loop_length_samples:
                padding = self.loop_length_samples - len(data)
                self.audio_tracks[i] = np.pad(data, (0, padding), 'constant')
            else:
                self.audio_tracks[i] = data
        
        logger.info(f"Song '{self.current_song_name}' loaded: {len(self.audio_tracks)} tracks, "
                   f"{self.loop_length_seconds:.2f}s duration")

    def _setup_audio_device(self):
        """Sets up audio device with optimal settings."""
        try:
            sd.default.samplerate = self.sample_rate
            sd.default.blocksize = self.block_size
            sd.default.dtype = np.float32
            
            output_device = self.config.get('audio', {}).get('output_device')
            if output_device:
                sd.default.device[1] = output_device
                logger.info(f"Using audio output device: {output_device}")
            
            sd.check_output_settings()
            logger.info("Audio device settings successfully checked.")
        except Exception as e:
            logger.error(f"Audio device setup failed: {e}")
            raise

    def _audio_callback(self, outdata: np.ndarray, frames: int, time, status):
        """
        Audio callback with song switching support.
        """
        if status:
            logger.debug(f"Audio status: {status}")
        
        outdata.fill(0.0)
        
        # Handle song switching
        with self.song_switch_lock:
            if self.song_switch_pending:
                # During song switch, output silence
                return
        
        if not self.master_playing or not self.audio_tracks:
            return
        
        # Standard audio processing
        pos = self.master_position % self.loop_length_samples
        available_until_loop = self.loop_length_samples - pos
        
        if frames <= available_until_loop:
            for track_id, track_data in self.audio_tracks.items():
                volume = self.volumes[track_id]
                if volume > 0.001:
                    outdata[:frames, 0] += track_data[pos:pos + frames] * volume
            
            self.master_position += frames
        else:
            first_part = available_until_loop
            second_part = frames - first_part
            
            for track_id, track_data in self.audio_tracks.items():
                volume = self.volumes[track_id]
                if volume > 0.001:
                    if first_part > 0:
                        outdata[:first_part, 0] += track_data[pos:pos + first_part] * volume
                    if second_part > 0:
                        outdata[first_part:frames, 0] += track_data[:second_part] * volume
            
            self.master_position = second_part
        
        # Handle volume fading
        for track_id in range(1, 19):
            current_vol = self.volumes[track_id]
            target_vol = self.target_volumes[track_id]
            fade_rate = self.fade_rates[track_id]
            
            if abs(current_vol - target_vol) > 0.0001 and fade_rate > 0:
                volume_change = fade_rate * frames
                if current_vol < target_vol:
                    self.volumes[track_id] = min(target_vol, current_vol + volume_change)
                else:
                    self.volumes[track_id] = max(target_vol, current_vol - volume_change)
        
        np.clip(outdata, -0.95, 0.95, out=outdata)

    def switch_to_next_song(self) -> str:
        """
        Switches to the next song in rotation.
        
        Returns:
            str: Name of the new active song
        """
        if len(self.available_songs) <= 1:
            logger.info("Only one song available, no switching needed")
            return self.current_song_name
        
        with self.song_switch_lock:
            self.song_switch_pending = True
            
            # Stop all current sounds
            for i in range(1, 19):
                self.volumes[i] = 0.0
                self.target_volumes[i] = 0.0
            
            # Move to next song
            self.current_song_index = (self.current_song_index + 1) % len(self.available_songs)
            self.current_song_name = self.available_songs[self.current_song_index]
            
            logger.info(f"Switching to song: {self.current_song_name} ({self.current_song_index + 1}/{len(self.available_songs)})")
            
            try:
                # Load new song
                self._load_current_song()
                
                # Reset playback position
                self.master_position = 0
                
                # Re-setup audio device if sample rate changed
                self._setup_audio_device()
                
                self.song_switch_pending = False
                logger.info(f"Successfully switched to song: {self.current_song_name}")
                
            except Exception as e:
                logger.error(f"Failed to switch to song '{self.current_song_name}': {e}")
                self.song_switch_pending = False
                raise
        
        return self.current_song_name

    def get_current_song_info(self) -> dict:
        """Returns information about the current song."""
        return {
            'name': self.current_song_name,
            'index': self.current_song_index,
            'total_songs': len(self.available_songs),
            'available_instruments': list(self.audio_tracks.keys()),
            'duration_seconds': self.loop_length_seconds,
            'next_song': self.available_songs[(self.current_song_index + 1) % len(self.available_songs)]
        }

    def start_master_playback(self) -> bool:
        """Starts synchronized playback."""
        if self.master_playing:
            logger.debug("Master playback already active")
            return True
        
        try:
            logger.info(f"Starting playback for song: {self.current_song_name}")
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
            
            logger.info(f"Audio stream started: {self.sample_rate}Hz, {self.block_size} samples/block")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            return False

    def stop_master_playback(self):
        """Stops all playback."""
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
        
        for i in range(1, 19):
            self.volumes[i] = 0.0
            self.target_volumes[i] = 0.0

    def restart_from_beginning(self):
        """Restarts the loop from position 0 and starts playback."""
        logger.info("Restarting loop from beginning")
        
        if self.master_playing:
            self.stop_master_playback()
        
        self.master_position = 0
        
        return self.start_master_playback()

    def fade_in(self, instrument: int, duration: float):
        """Fades in an instrument over a specified duration."""
        if instrument not in self.audio_tracks:
            logger.warning(f"Instrument {instrument} not available in song '{self.current_song_name}'")
            return
        
        if not self.master_playing:
            logger.warning("Cannot fade in: playback not active")
            return
        
        fade_samples = max(1, int(duration * self.sample_rate))
        self.target_volumes[instrument] = 1.0
        self.fade_rates[instrument] = 1.0 / fade_samples
        
        logger.debug(f"Fading in instrument {instrument} (song: {self.current_song_name}) over {duration:.2f}s")

    def fade_out(self, instrument: int, duration: float):
        """Fades out an instrument over a specified duration."""
        if instrument not in range(1, 19):
            return
        
        fade_samples = max(1, int(duration * self.sample_rate))
        self.target_volumes[instrument] = 0.0
        self.fade_rates[instrument] = 1.0 / fade_samples
        
        logger.debug(f"Fading out instrument {instrument} over {duration:.2f}s")

    def get_available_instruments(self) -> list:
        """Returns a list of loaded instruments for the current song."""
        return list(self.audio_tracks.keys())

    def shutdown(self):
        """Performs a clean shutdown."""
        logger.info("Shutting down AudioManager")
        self.stop_master_playback()
        self.audio_tracks.clear()
        logger.info("AudioManager shutdown complete")
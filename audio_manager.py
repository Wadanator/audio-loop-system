# audio_manager.py
import sounddevice as sd
import numpy as np
import soundfile as sf
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class AudioManager:
    """
    Synchronized audio looper - all instruments share the exact same playback position.
    Critical: Perfect timing synchronization for musical looping.
    """
    
    def __init__(self, config: dict):
        """
        Initializes the AudioManager.

        Args:
            config (dict): The configuration dictionary for audio settings.
        """
        self.config = config
        
        # Audio configuration - use native file sample rate
        self.sample_rate = None  # Will be set from first audio file
        self.block_size = config['jack'].get('buffer_size', 1024)
        
        # Master synchronization - SINGLE position for ALL tracks
        self.master_position = 0
        self.loop_length_samples = 0
        self.loop_length_seconds = 0.0
        
        # Audio data storage - all tracks MUST be the same length
        self.audio_tracks: Dict[int, np.ndarray] = {}
        
        # Playback state
        self.master_playing = False
        self.volumes: Dict[int, float] = {i: 0.0 for i in range(1, 19)}
        self.target_volumes: Dict[int, float] = {i: 0.0 for i in range(1, 19)}
        self.fade_rates: Dict[int, float] = {i: 0.0 for i in range(1, 19)}
        
        self.output_stream: Optional[sd.OutputStream] = None
        
        self._load_and_prepare_tracks()
        self._setup_audio_device()

    def _load_and_prepare_tracks(self):
        """Loads all tracks and ensures perfect length synchronization."""
        audio_dir = "audio_files"
        temp_tracks = {}
        sample_rates = []
        
        if not os.path.exists(audio_dir):
            raise FileNotFoundError(f"Audio directory '{audio_dir}' not found.")
        
        # First pass: load all files and check sample rates
        for i in range(1, 19):
            filepath = os.path.join(audio_dir, f"{i}.wav")
            if os.path.exists(filepath):
                try:
                    data, sr = sf.read(filepath, dtype=np.float32)
                    
                    # Ensure mono
                    if len(data.shape) > 1:
                        data = np.mean(data, axis=1)
                    
                    temp_tracks[i] = data
                    sample_rates.append(sr)
                    logger.info(f"Loaded {i}.wav: {len(data)} samples at {sr}Hz")
                    
                except Exception as e:
                    logger.error(f"Failed to load {i}.wav: {e}")
        
        if not temp_tracks:
            raise RuntimeError("No audio files loaded!")
        
        from collections import Counter
        most_common_sr = Counter(sample_rates).most_common(1)[0][0]
        self.sample_rate = int(most_common_sr)
        logger.info(f"Using sample rate: {self.sample_rate}Hz")
        
        # Find the maximum length to normalize all tracks
        max_length = max(len(data) for data in temp_tracks.values())
        self.loop_length_samples = max_length
        self.loop_length_seconds = max_length / self.sample_rate
        
        # Apply max loop length limit if configured
        max_loop_seconds = self.config.get('audio', {}).get('max_loop_length')
        if max_loop_seconds and self.loop_length_seconds > max_loop_seconds:
            self.loop_length_samples = int(max_loop_seconds * self.sample_rate)
            self.loop_length_seconds = max_loop_seconds
            logger.info(f"Limited loop length to {max_loop_seconds}s")
        
        # Normalize all tracks to exact same length
        for i, data in temp_tracks.items():
            if len(data) > self.loop_length_samples:
                # Truncate if too long
                self.audio_tracks[i] = data[:self.loop_length_samples]
                logger.info(f"Truncated track {i} to {self.loop_length_seconds:.2f}s")
            elif len(data) < self.loop_length_samples:
                # Pad with zeros if too short
                padding = self.loop_length_samples - len(data)
                self.audio_tracks[i] = np.pad(data, (0, padding), 'constant')
                logger.info(f"Padded track {i} to {self.loop_length_seconds:.2f}s")
            else:
                self.audio_tracks[i] = data
        
        logger.info(f"All {len(self.audio_tracks)} tracks synchronized to {self.loop_length_seconds:.2f}s "
                    f"({self.loop_length_samples} samples)")

    def _setup_audio_device(self):
        """Sets up audio device with optimal settings."""
        try:
            # Configure defaults
            sd.default.samplerate = self.sample_rate
            sd.default.blocksize = self.block_size
            sd.default.dtype = np.float32
            
            # Use specific device if configured
            output_device = self.config.get('audio', {}).get('output_device')
            if output_device:
                sd.default.device[1] = output_device
                logger.info(f"Using audio output device: {output_device}")
            
            # Check if device is available
            sd.check_output_settings()
            logger.info("Audio device settings successfully checked.")
        except Exception as e:
            logger.error(f"Audio device setup failed: {e}")
            raise

    def _audio_callback(self, outdata: np.ndarray, frames: int, time, status):
        """
        Optimized real-time audio callback for low-power devices.
        Uses block processing for better performance.
        """
        if status:
            logger.debug(f"Audio status: {status}")
        
        outdata.fill(0.0)
        
        if not self.master_playing or not self.audio_tracks:
            return
        
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

    def start_master_playback(self) -> bool:
        """Starts synchronized playback."""
        if self.master_playing:
            logger.debug("Master playback already active")
            return True
        
        try:
            logger.info("Starting synchronized master playback")
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
        """
        Fades in an instrument over a specified duration.

        Args:
            instrument (int): The instrument number to fade in.
            duration (float): The duration of the fade in seconds.
        """
        if instrument not in self.audio_tracks:
            logger.warning(f"Instrument {instrument} not available")
            return
        
        if not self.master_playing:
            logger.warning("Cannot fade in: playback not active")
            return
        
        fade_samples = max(1, int(duration * self.sample_rate))
        self.target_volumes[instrument] = 1.0
        self.fade_rates[instrument] = 1.0 / fade_samples
        
        logger.debug(f"Fading in instrument {instrument} over {duration:.2f}s")

    def fade_out(self, instrument: int, duration: float):
        """
        Fades out an instrument over a specified duration.

        Args:
            instrument (int): The instrument number to fade out.
            duration (float): The duration of the fade in seconds.
        """
        if instrument not in range(1, 19):
            return
        
        fade_samples = max(1, int(duration * self.sample_rate))
        self.target_volumes[instrument] = 0.0
        self.fade_rates[instrument] = 1.0 / fade_samples
        
        logger.debug(f"Fading out instrument {instrument} over {duration:.2f}s")

    def get_available_instruments(self) -> list:
        """Returns a list of loaded instruments."""
        return list(self.audio_tracks.keys())

    def shutdown(self):
        """Performs a clean shutdown."""
        logger.info("Shutting down AudioManager")
        self.stop_master_playback()
        self.audio_tracks.clear()
        logger.info("AudioManager shutdown complete")
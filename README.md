# 🎵 Audio Looper System

**A Raspberry Pi-based audio looper system** for synchronized playback of up to **18 audio tracks**, controlled by physical buttons.  
The system plays **WAV files in perfect sync**, allowing users to toggle instrument tracks with smooth **fade-in/out effects**, tracks usage statistics, and provides a **web interface for monitoring**.  
Designed for **efficiency** – it stops playback during idle periods to conserve **CPU/RAM**.

---

## ✨ Features
- **Synchronized playback** of up to **18 WAV files** (`1.wav` to `18.wav`) using `sounddevice` for low-latency audio output.
- **Button-driven control** via Raspberry Pi GPIO pins to toggle instrument tracks.
- **Smooth fade-in/out effects** for seamless track transitions (configurable duration).
- **Dual-timer system**:
  - Per-instrument timeout (**60s** by default).
  - Global timeout (**75s** by default) to stop playback when idle.
- **Web server** for real-time statistics (instrument activations and command usage) via HTML dashboard or JSON API.
- **Efficient idle state**: playback stops after global timeout or when all instruments are inactive.
- **Logging** with file rotation (10MB per file, 5 backups) for debugging and monitoring.
- **Configurable** via `config.json` for GPIO mappings, timeouts, and audio settings.

---

## ⚙️ Requirements
- **Raspberry Pi** with GPIO pins configured for buttons.
- **Python 3** with required libraries: `sounddevice`, `numpy`, `soundfile`, `RPi.GPIO`.
- `audio_files/` directory containing WAV files (`1.wav` to `18.wav`).
- `config.json` for system configuration (button mappings, timeouts, audio settings).
- Internet access for web-based statistics dashboard (optional).

---

## 📂 File Structure
- **`main.py`** → Entry point, initializes the AudioLooper system as a service, handles clean shutdown.
- **`audio_manager.py`** → Manages audio playback, loads WAV files, ensures synchronized playback, and handles fade-in/out.
- **`looper_engine.py`** → Controls system logic, manages dual timers (instrument and global), and coordinates track activation.
- **`button_handler.py`** → Handles GPIO button inputs for up to 18 buttons with polling-based debouncing.
- **`stats_collector.py`** → Tracks usage statistics (instrument activations, commands) and saves to `stats.json`.
- **`stats_server.py`** → Runs an HTTP server for real-time statistics dashboard (HTML) and JSON API.
- **`logging_setup.py`** → Configures logging with file rotation (10MB per file, 5 backups).
- **`config.json`** → Defines GPIO pin mappings, timeouts, audio settings, and stats server configuration.

---

## 🚀 Setup and Installation
1. **Prepare the audio files**:
   - Place WAV files (`1.wav` to `18.wav`) in the `audio_files/` directory.
   - Ensure all files are mono and have the same sample rate for synchronization.

2. **Configure the system**:
   - Edit `config.json` to map GPIO pins to instruments, set timeouts, and configure audio settings (e.g., sample rate, buffer size).
   - Example `config.json`:
     ```json
     {
       "raspberry_pi": {
         "button_pins": {
           "1": 4,
           "2": 17,
           ...
         },
         "pull_up": true,
         "button_cooldown_seconds": 1.5
       },
       "timeouts": {
         "global_timeout": 75,
         "instrument_timeout": 60,
         "fade_duration": 2
       },
       "jack": {
         "sample_rate": 48000,
         "buffer_size": 1024
       },
       "audio": {
         "max_loop_length": 120
       },
       "stats_server": {
         "host": "192.168.0.191",
         "port": 8000
       }
     }
     ```

3. **Install dependencies**:
   ```bash
   pip3 install sounddevice numpy soundfile RPi.GPIO
   ```

4. **Run the system**:
   ```bash
   python3 main.py
   ```

5. **Run as a service** (optional):
   - Configure as a systemd service for automatic startup:
     ```bash
     sudo cp audio-looper.service /etc/systemd/system/
     sudo systemctl enable audio-looper
     sudo systemctl start audio-looper
     ```

---

## 🎮 Usage and Controls
### Button Controls
- **Instrument Toggle (Buttons 1–18)**:
  - Press a button (mapped to GPIO pins in `config.json`) to toggle the corresponding instrument track (1–18).
  - If the track is off, pressing the button activates it with a fade-in effect (default 2s).
  - If the track is on, pressing the button deactivates it with a fade-out effect (default 2s).
  - A cooldown period (default 1.5s) prevents rapid button presses from causing unintended toggles.
- **System Activation**:
  - Pressing any instrument button when the system is idle starts playback from the beginning and activates the selected instrument.
- **Timeouts**:
  - Each active instrument automatically fades out after its timeout (default 60s).
  - The entire system stops playback after the global timeout (default 75s) if no buttons are pressed.

### Monitoring
- **Web Dashboard**:
  - Access the statistics dashboard at `http://<raspberry_pi_ip>:8000` (default: `http://192.168.0.191:8000`).
  - Displays real-time counts of instrument activations and command executions (e.g., stop, status, quit).
  - Refresh the page to update statistics.
- **JSON API**:
  - Access raw statistics at `http://<raspberry_pi_ip>:8000/stats`.
- **Logs**:
  - View application logs at `logs/app.log`:
    ```bash
    tail -f logs/app.log
    ```

### Service Management
- Check service status:
  ```bash
  sudo systemctl status audio-looper
  ```
- View service logs:
  ```bash
  sudo journalctl -u audio-looper -f
  ```
- Restart the service:
  ```bash
  sudo systemctl restart audio-looper
  ```
- Stop the service:
  ```bash
  sudo systemctl stop audio-looper
  ```
- Uninstall the service:
  ```bash
  sudo ./uninstall_service.sh
  ```

---

## 🔧 Troubleshooting
- **No audio output**:
  - Ensure WAV files are in `audio_files/` and are valid mono WAV files.
  - Check the audio output device in `config.json` (`audio.output_device`).
  - Verify the sample rate matches the WAV files.
- **Buttons not responding**:
  - Confirm GPIO pin mappings in `config.json` match your hardware setup.
  - Check for correct pull-up/pull-down resistor settings (`pull_up` in `config.json`).
- **Web dashboard not accessible**:
  - Verify the Raspberry Pi’s IP address and port in `config.json` (`stats_server.host` and `port`).
  - Ensure the Raspberry Pi is on the same network and the port is open.
- **High CPU usage**:
  - Adjust `jack.buffer_size` in `config.json` (e.g., increase to 2048) for better performance on slower hardware.

---

## 📝 Notes
- All tracks are synchronized to the length of the longest WAV file (up to `audio.max_loop_length` seconds).
- The system uses `sounddevice` for low-latency audio playback, replacing `pygame.mixer` for better performance.
- Statistics are persistently stored in `stats.json` and updated with each instrument activation or command.
- The system is optimized for Raspberry Pi, with polling-based button handling to ensure reliable input detection.

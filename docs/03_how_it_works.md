# 03 – How the System Works

This document explains the internal architecture, data flow, and design decisions of the Audio Loop System.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  AudioLooper – orchestrates all components, main loop       │
└──────┬──────────────┬───────────────┬────────────┬──────────┘
       │              │               │            │
       ▼              ▼               ▼            ▼
button_handler   looper_engine   audio_manager  stats_server
  .py              .py             .py            .py
  │                │               │
  │  GPIO events   │  fade_in()    │  sounddevice
  └───────────────►│  fade_out()   │  OutputStream
                   └──────────────►│
                                   │  _audio_callback()
                   stats_collector │  (runs in audio thread)
                       .py         │
                   (shared by      │
                   main + engine)  │
```

---

## Module Descriptions

### `main.py` – Application Entry Point and Orchestrator

The top-level `AudioLooper` class:
1. Checks that required files (`config.json`, `audio_files/`) exist
2. Creates **one shared `StatsCollector` instance**
3. Initializes all other components, passing the shared `StatsCollector`
4. Starts the button handler, looper engine, and stats server threads
5. Runs a **main loop** (1-second tick) that:
   - Triggers `periodic_save()` every 5 minutes
   - Calls `check_stream_health()` every 60 seconds
   - Sends a systemd watchdog ping every 25 seconds
   - Logs system status every 10 minutes
6. Handles `SIGTERM`/`SIGINT` for graceful shutdown

---

### `audio_manager.py` – Low-Level Audio Engine

Manages the actual audio playback using `sounddevice`.

**Initialization:**
- Loads all WAV files for the current song into RAM as NumPy float32 arrays
- Normalizes all tracks to the same length (padding with zeros if needed)
- Opens a `sounddevice.OutputStream` with a callback

**The Audio Callback (`_audio_callback`):**
- Called by the audio driver ~every 10ms (depends on buffer size)
- Runs in a **separate high-priority audio thread**
- For each active instrument, multiplies the audio buffer slice by the instrument's volume and adds it to the output buffer
- Handles loop wrapping (seamless transition from end back to start)
- Applies per-frame volume fading (linear interpolation toward target volume)
- Clips output to ±0.95 to prevent clipping distortion
- Uses `audio_data_lock.acquire(blocking=False)` — if song switch is in progress, returns silence instead of risking a race condition

**Song Switching:**
- Loads new WAV files into temporary arrays
- Atomically swaps them into `self.audio_tracks` under `audio_data_lock`
- Resets `master_position` to 0

**Stream Health Check:**
- `check_stream_health()` verifies `output_stream.active`
- If the stream died (e.g. USB DAC disconnected), calls `start_master_playback()` automatically

---

### `looper_engine.py` – Business Logic Controller

Controls what plays and when, running its own background thread (`_logic_loop`).

**Button Press Handling (`handle_button_press`):**
1. Checks button cooldown (prevents double triggers)
2. If system is idle → activates the system (starts audio)
3. Resets global timer
4. Toggles the instrument: if active → fade out; if inactive → fade in
5. Records the activation in `StatsCollector`

**Logic Loop (`_logic_loop`, runs every 200ms):**
- Checks **global timeout**: if `current_time >= global_expiry_time` → deactivates system
- Checks **per-instrument timeouts**: if any instrument's timer expired → fades it out

**Song Rotation:**
- When the system deactivates (global timeout), calls `audio_manager.switch_to_next_song()`
- Cycles through `available_songs` list in order
- Falls back to same song if only one is available or if loading fails

---

### `button_handler.py` – GPIO Input Handler

Polls all GPIO pins in a tight loop (configurable interval, default 5ms).

**Debouncing State Machine (per pin):**

```
Raw GPIO reading
       │
       ▼
State changed?
   YES → reset debounce timer, return False
   NO  ↓
Time since change < debounce_time (80ms)?
   YES → still bouncing, return False
   NO  ↓
Stable state changed?
   NO → return False
   YES ↓
Is this a new press (LOW transition)?
   YES ↓
press_start_times[pin] == 0?
   YES → record time, return False (wait for next cycle)
   NO  ↓
Elapsed >= min_press_duration?
   NO → return False (glitch filter)
   YES ↓
Double-press protection elapsed?
   NO → return False
   YES → ✅ Valid press → call callback in new thread
```

**Key design decision:** All debouncing is **non-blocking**. No `time.sleep()` calls exist in the polling loop, so all 18 pins are always serviced on every 5ms tick.

---

### `stats_collector.py` – Usage Statistics

Keeps counters in RAM, persists to `stats.json` on disk.

**Write strategy:**
- `record_instrument()` → only updates RAM, sets `pending_changes = True`
- `periodic_save()` → writes to disk **only** if `pending_changes == True` AND 5 minutes have elapsed
- `force_save()` → writes immediately (called on shutdown)
- Atomic write: writes to `stats.json.tmp`, then `os.rename()` → no corrupted files on power loss

---

### `stats_server.py` – HTTP Statistics Server

A minimal HTTP server based on Python's `http.server`.

**Endpoints:**
- `GET /` → HTML dashboard (styled with Tailwind CSS via CDN)
- `GET /stats` → raw JSON

**Data source:** Reads from `StatsCollector.get_stats()` (in-memory) — no disk reads per request.

**Resilience:** If the server fails to bind (e.g. port in use), it retries up to 5 times with a 10-second delay before giving up.

---

### `logging_setup.py` – Logging Configuration

Two handlers:
| Handler | Level | Destination | SD Card impact |
|---------|-------|-------------|----------------|
| `RotatingFileHandler` | ERROR+ | `logs/critical_errors.log` | Minimal writes |
| `StreamHandler(stdout)` | INFO+ | stdout → journald | No SD writes |

The file handler rotates at 5MB, keeping 2 backups. This bounds SD card usage regardless of runtime.

---

## Threading Model

| Thread | Owner | Purpose |
|--------|-------|---------|
| Main thread | `AudioLooper.run()` | Main loop, watchdog, health checks |
| Audio thread | `sounddevice` (internal) | `_audio_callback` – real-time audio output |
| Logic thread | `LooperEngine._logic_loop()` | Timeout checking (daemon) |
| Poll thread | `ButtonHandler._poll_loop()` | GPIO polling (daemon) |
| Stats server thread | `run_stats_server()` | HTTP server (daemon) |
| Per-press thread | `ButtonHandler._poll_loop()` | Spawned per button press (daemon) |

---

## Data Flow – Button Press to Sound

```
GPIO pin goes LOW
       │
       ▼
_poll_loop() detects it (5ms later)
       │
       ▼
_debounce_button() validates (80ms + 10ms min duration)
       │
       ▼
New daemon thread spawned
       │
       ▼
looper_engine.handle_button_press(instrument_num)
       │
       ├─► If idle: audio_manager.restart_from_beginning()
       │                  │
       │                  ▼
       │           sounddevice.OutputStream.start()
       │
       ├─► Reset global_expiry_time (+75s)
       │
       ├─► If instrument OFF: audio_manager.fade_in(instrument, 2.0s)
       │                             │
       │                             ▼
       │                   Sets target_volumes[i] = 1.0
       │                   Sets fade_rates[i] = rate/sample
       │                   (applied per frame in _audio_callback)
       │
       └─► stats_collector.record_instrument(instrument_num)
```

---

## Configuration Reference (`config.json`)

```jsonc
{
  "raspberry_pi": {
    "button_pins": { "1": 4, "2": 17, ... },  // GPIO BCM pin per instrument
    "pull_up": true,                           // true = buttons connect to GND
    "button_cooldown_seconds": 1.5             // min time between same-button presses
  },
  "debouncing": {
    "debounce_time_ms": 80,            // wait for signal to stabilize
    "min_press_duration_ms": 10,       // glitch filter
    "poll_interval_ms": 5,             // how often GPIO is read
    "double_press_protection_ms": 1000 // min time between two valid presses
  },
  "song_rotation": {
    "enable": true,
    "switch_on_global_timeout": true,
    "base_directory": "audio_files",
    "song_folders": ["song1", "song2", "song3"]
  },
  "timeouts": {
    "global_timeout": 75,      // seconds of inactivity before system stops
    "instrument_timeout": 60,  // seconds before individual instrument fades out
    "fade_duration": 2         // fade in/out duration in seconds
  },
  "jack": {
    "buffer_size": 2048        // audio buffer (larger = more stable, more latency)
  },
  "stats_server": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "audio": {
    "output_device": null,     // null = system default, or set device name/index
    "max_loop_length": 180     // maximum loop length in seconds
  }
}
```

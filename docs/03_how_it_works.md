# How the System Works

## High-Level Flow

```text
DIN button press
  -> Modbus TCP read in input/modbus_panel.py
  -> LooperEngine.handle_button_press(instrument)
  -> AudioManager fade in/out
  -> Modbus LED controller writes DO state best-effort
  -> StatsCollector records activation
```

## Main Components

### `main.py`

Small launcher only. It adds `src/` to `sys.path` and calls `audio_loop.app.main()`.

### `src/audio_loop/app.py`

Top-level orchestrator. It loads config, validates runtime paths, creates shared components, starts background threads, and handles shutdown.

### `src/audio_loop/config.py`

Loads `config.json` as UTF-8 with BOM tolerance and validates audio folder requirements before startup.

### `src/audio_loop/hardware/modbus_bus.py`

Owns Modbus TCP clients. Each module/IP has its own client and lock. This keeps reads and writes thread-safe when input polling and LED writes happen at the same time.

### `src/audio_loop/input/modbus_panel.py`

Polls configured DI channels, applies debounce/rising-edge detection, and calls `handle_button_press(instrument)`.

### `src/audio_loop/output/led_panel.py`

Maintains desired LED state and writes DO coils asynchronously. This is best-effort so a LED failure does not block audio.

### `src/audio_loop/core/looper_engine.py`

Owns playback state, layer toggling, global timeout, instrument timeout, song rotation, and LED sync calls.

### `src/audio_loop/audio/manager.py`

Loads WAV files and runs the audio stream. The audio callback is kept separate from web and IO work.

### `src/audio_loop/stats/collector.py`

Keeps activation counters in memory and saves them periodically.

### `src/audio_loop/web/stats_server.py`

Current lightweight stats HTTP server. The future simplified room dashboard is planned as Goal 3.

## Config Shape

```json
{
  "inputs": {
    "provider": "modbus_panel",
    "button_cooldown_seconds": 1.5
  },
  "outputs": {
    "provider": "modbus_panel",
    "enabled": true
  },
  "modbus_panel": {
    "modules": [
      {
        "name": "box_1",
        "host": "192.168.0.200",
        "port": 4196,
        "unit_id": 1,
        "channels": [
          {"channel": 1, "instrument": 1}
        ]
      }
    ]
  }
}
```

## Degraded Modes

- Web down: audio and physical buttons continue.
- LED write fails: audio and input continue.
- One future box offline: the other box should continue after production bus isolation is completed.
- Missing WAV for a pressed instrument: log warning, do not activate that layer.
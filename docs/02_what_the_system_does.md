# What the System Does

Audio Loop System is an interactive museum-room looper. Visitors press physical buttons, and each button toggles one synchronized audio layer. LEDs in the buttons mirror which layers are actively playing.

## Visitor Flow

1. The room is idle and silent.
2. Visitor presses a button.
3. The system starts the current song from the beginning.
4. The selected instrument fades in and its LED turns on.
5. More buttons add or remove more layers.
6. Missing audio files are ignored safely with a warning.
7. Per-instrument timeout fades inactive layers out.
8. Global timeout stops the session and can rotate to the next song.

## Current Hardware Model

- Physical input comes from DIN Modbus TCP modules, not Raspberry Pi GPIO.
- Box 1 is verified: 8 digital inputs and 8 digital outputs.
- Future target: two boxes for 16 inputs and 16 LED outputs.
- One Raspberry Pi will host audio, IO processing, stats, and web UI.

## LED Behavior

- LED ON means the corresponding audio layer is actively playing.
- LED OFF means the layer is inactive, unavailable, timed out, or the whole system is idle.
- LED writes are best-effort. Audio behavior has priority over LED updates.

## Reliability Priorities

1. Audio playback and state must keep working.
2. Physical buttons must keep working.
3. Web UI is optional and must not block audio or buttons.
4. LEDs are useful feedback but must not stop the system if a write fails.
5. Stats are useful but lower priority than runtime behavior.

## Runtime Layout

Runtime code lives in `src/audio_loop/`. Root `main.py` is only a launcher.

```text
src/audio_loop/
  app.py
  audio/manager.py
  core/looper_engine.py
  hardware/modbus_bus.py
  input/modbus_panel.py
  output/led_panel.py
  stats/collector.py
  web/server.py
  infra/
```
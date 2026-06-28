# Goal 2 - Production codebase refactor

## Goal

Make the project more production-ready by replacing the current flat file
layout with focused modules. Behavior should stay stable while moving code.
The refactor should make it easy to maintain audio, input, output, web, stats,
and runtime safety separately.

## Current state

- `[implemented] 2026-06-28 22:34:29 +02:00` - The main runtime modules now
  live under `src/audio_loop/`:
  - `src/audio_loop/app.py`
  - `src/audio_loop/audio/manager.py`
  - `src/audio_loop/core/looper_engine.py`
  - `src/audio_loop/hardware/modbus_bus.py`
  - `src/audio_loop/input/modbus_panel.py`
  - `src/audio_loop/output/led_panel.py`
  - `src/audio_loop/stats/collector.py`
  - `src/audio_loop/web/stats_server.py`
  - `src/audio_loop/infra/logging_setup.py`
  - `src/audio_loop/infra/paths.py`
- Root files such as `main.py`, `audio_manager.py`, `looper_engine.py`,
  `modbus_bus.py`, `stats_server.py`, and `logging_setup.py` are now thin
  compatibility wrappers during the transition.
- `button_handler.py` remains only as historical GPIO reference and is still
  outside the production startup path.
- `config.json` still stays in the project root for this phase.

## Target structure

```text
src/audio_loop/
  __init__.py
  app.py
  config.py

  audio/
    __init__.py
    manager.py

  core/
    __init__.py
    looper_engine.py
    events.py

  input/
    __init__.py
    base.py
    modbus_panel.py

  output/
    __init__.py
    base.py
    led_panel.py

  web/
    __init__.py
    app.py
    routes.py

  stats/
    __init__.py
    collector.py

  infra/
    __init__.py
    logging_setup.py
    paths.py
    watchdog.py

config/
  config.json

scripts/
  run_dev.py
  verify_modbus_panel.py

tests/
```

## Refactor rules

- Do not change playback behavior during the first move.
- Keep `python main.py` working as a compatibility entry point.
- Add minimal smoke tests before moving code.
- Move code, update imports, then run smoke tests after each small move.
- Avoid mixing hardware migration and file movement in one commit if possible.
- Keep audio logic independent from web and hardware implementation details.

## Implementation log

- `[implemented] 2026-06-28 22:34:29 +02:00` - Added
  `tests/smoke_refactor.py`. It imports the app entry without importing
  `button_handler`/`RPi.GPIO`, and verifies `LooperEngine` activation and
  deactivation with fake audio/stats/LED dependencies.
- `[implemented] 2026-06-28 22:34:29 +02:00` - Created the `src/audio_loop/`
  package skeleton and moved app, audio, core, hardware, input, output, stats,
  web, and infra modules into focused subpackages.
- `[implemented] 2026-06-28 22:34:29 +02:00` - Root `main.py` is now a thin
  compatibility launcher that imports `audio_loop.app.main`; old root module
  names remain as wrappers for transitional compatibility.
- `[implemented] 2026-06-28 22:34:29 +02:00` - Added
  `src/audio_loop/infra/paths.py` and fixed `logging_setup.py` so logs still go
  to project-root `logs/`, not inside `src/audio_loop/infra/`.
- `[implemented] 2026-06-28 22:34:29 +02:00` - Updated `LooperEngine` type-only
  dependencies to use `TYPE_CHECKING`, so importing `audio_loop.core` no longer
  requires audio runtime packages like `sounddevice`.
- `[verified] 2026-06-28 22:34:29 +02:00` - `py_compile` passed for root
  wrappers and refactored package modules; `tests/smoke_refactor.py` passed;
  package imports and compatibility imports passed; the user's Python 3.13
  imported root `main.py` and resolved `main.main.__module__ == "audio_loop.app"`.
- `[pending]` - Run the real hardware app once after the refactor to confirm
  Box 1 DI/DO behavior is unchanged.
- `[pending]` - Move config loading/validation into `src/audio_loop/config.py`
  and extract watchdog helper into `src/audio_loop/infra/watchdog.py`.

## Implementation steps

1. Add pre-refactor smoke tests - `[implemented] 2026-06-28 22:34:29 +02:00`
   - Add a test that imports `main.py` or the future app entry without starting
     real hardware.
   - Add a test that imports `LooperEngine` with fake audio/stats objects.
   - Add a test that confirms Windows/dev import does not require `RPi.GPIO`
     once input providers are isolated.
   - These tests are the guardrail before files start moving.

2. Add package skeleton - `[implemented] 2026-06-28 22:34:29 +02:00`
   - Create `src/audio_loop/` and subpackages.
   - Add empty `__init__.py` files.
   - Add `pyproject.toml` or keep simple path setup at first.

3. Move infrastructure first - `[partially implemented] 2026-06-28 22:34:29 +02:00`
   - Move `logging_setup.py` to `src/audio_loop/infra/logging_setup.py`.
   - Add `src/audio_loop/infra/paths.py` for runtime paths.
   - Keep `logs/`, `stats.json`, and dashboard static paths anchored to the
     project/runtime directory or explicit config, not to `src/audio_loop/`.
   - Move systemd watchdog helper from `main.py` into
     `src/audio_loop/infra/watchdog.py`.
   - Update imports.
   - Run a quick import check.

4. Move stats - `[implemented] 2026-06-28 22:34:29 +02:00`
   - Move `stats_collector.py` to `src/audio_loop/stats/collector.py`.
   - Keep current public class name `StatsCollector`.
   - Do not change save behavior in this step.

5. Move audio manager - `[implemented] 2026-06-28 22:34:29 +02:00`
   - Move `audio_manager.py` to `src/audio_loop/audio/manager.py`.
   - Keep class name `AudioManager`.
   - Update all imports.

6. Move core engine - `[implemented] 2026-06-28 22:34:29 +02:00`
   - Move `looper_engine.py` to `src/audio_loop/core/looper_engine.py`.
   - Keep method names stable:
     - `handle_button_press`
     - `force_song_switch`
     - `get_system_status`
   - Add optional dependency slots for future controllers:
     - `led_controller=None`
     - `event_bus=None` or callback list if needed later.

7. Move input code - `[partially implemented] 2026-06-28 22:34:29 +02:00`
   - Move the new Modbus input code into `src/audio_loop/input/modbus_panel.py`.
   - Leave old `button_handler.py` out of the app startup path and delete it in
     a later cleanup once Modbus input is fully proven.
   - Add `src/audio_loop/input/base.py`.
   - Add provider factory:
     - `create_input_handler(config, callback)`.

8. Move web code - `[partially implemented] 2026-06-28 22:34:29 +02:00`
   - Move `stats_server.py` into `src/audio_loop/web/`.
   - Later replace it with the fuller dashboard API from Goal 3.

9. Create new app orchestration - `[implemented] 2026-06-28 22:34:29 +02:00`
   - Move `AudioLooper` class from root `main.py` to `src/audio_loop/app.py`.
   - Root `main.py` becomes a thin wrapper:

```python
from audio_loop.app import main

if __name__ == "__main__":
    main()
```

10. Move config loading - `[pending]`
   - Add `src/audio_loop/config.py`.
   - Centralize:
     - config path
     - validation
     - default values
     - migration warning for old keys
   - Keep `config.json` readable from the current working directory during the
     transition.

11. Update tests and scripts - `[partially implemented] 2026-06-28 22:34:29 +02:00`
    - Update imports in `test/`.
    - Rename `test/` to `tests/` if desired.
    - Add a smoke test that imports the app package without requiring RPi GPIO.

## Acceptance criteria

- `python main.py` still starts the app.
- Importing the package on Windows/dev machine does not require `RPi.GPIO`.
- Existing audio logic has no behavior change from file movement alone.
- The app can select input provider from config.
- Log files are written to the configured runtime `logs/` directory, not inside
  the Python package after moving to `src/`.
- Web code is not imported unless enabled.
- Tests can import `LooperEngine`, `StatsCollector`, and config helpers from
  the new package path.

## Future cleanup after the move

- Replace hard-coded 18 ranges with `max_instruments` from config, while
  keeping default 18.
- Add type hints to public interfaces.
- Split `AudioManager` only if it becomes necessary:
  - audio file loading
  - playback stream
  - song rotation
- Replace ad-hoc dictionaries with small dataclasses only where it helps.
- Simplify installation paths before deployment: prefer `requirements.txt`, one
  install script, and systemd service templates over multiple overlapping
  installer helpers.

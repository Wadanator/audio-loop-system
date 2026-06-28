# Goal 2 - Production codebase refactor

## Goal

Make the project more production-ready by replacing the current flat file
layout with focused modules. Behavior should stay stable while moving code.
The refactor should make it easy to maintain audio, input, output, web, stats,
and runtime safety separately.

## Current state

The root directory currently contains most application files:

- `main.py`
- `audio_manager.py`
- `looper_engine.py`
- `button_handler.py`
- `stats_server.py`
- `stats_collector.py`
- `logging_setup.py`
- `config.json`

This works, but the next features need clearer boundaries.

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
    gpio_legacy.py

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

## Implementation steps

1. Add pre-refactor smoke tests
   - Add a test that imports `main.py` or the future app entry without starting
     real hardware.
   - Add a test that imports `LooperEngine` with fake audio/stats objects.
   - Add a test that confirms Windows/dev import does not require `RPi.GPIO`
     once input providers are isolated.
   - These tests are the guardrail before files start moving.

2. Add package skeleton
   - Create `src/audio_loop/` and subpackages.
   - Add empty `__init__.py` files.
   - Add `pyproject.toml` or keep simple path setup at first.

3. Move infrastructure first
   - Move `logging_setup.py` to `src/audio_loop/infra/logging_setup.py`.
   - Add `src/audio_loop/infra/paths.py` for runtime paths.
   - Keep `logs/`, `stats.json`, and dashboard static paths anchored to the
     project/runtime directory or explicit config, not to `src/audio_loop/`.
   - Move systemd watchdog helper from `main.py` into
     `src/audio_loop/infra/watchdog.py`.
   - Update imports.
   - Run a quick import check.

4. Move stats
   - Move `stats_collector.py` to `src/audio_loop/stats/collector.py`.
   - Keep current public class name `StatsCollector`.
   - Do not change save behavior in this step.

5. Move audio manager
   - Move `audio_manager.py` to `src/audio_loop/audio/manager.py`.
   - Keep class name `AudioManager`.
   - Update all imports.

6. Move core engine
   - Move `looper_engine.py` to `src/audio_loop/core/looper_engine.py`.
   - Keep method names stable:
     - `handle_button_press`
     - `force_song_switch`
     - `get_system_status`
   - Add optional dependency slots for future controllers:
     - `led_controller=None`
     - `event_bus=None` or callback list if needed later.

7. Move input code
   - Move current `button_handler.py` to
     `src/audio_loop/input/gpio_legacy.py`.
   - Rename class later if useful, but keep compatibility during the move.
   - Add `src/audio_loop/input/base.py`.
   - Add provider factory:
     - `create_input_handler(config, callback)`.

8. Move web code
   - Move `stats_server.py` into `src/audio_loop/web/`.
   - Later replace it with the fuller dashboard API from Goal 3.

9. Create new app orchestration
   - Move `AudioLooper` class from root `main.py` to `src/audio_loop/app.py`.
   - Root `main.py` becomes a thin wrapper:

```python
from audio_loop.app import main

if __name__ == "__main__":
    main()
```

10. Move config loading
   - Add `src/audio_loop/config.py`.
   - Centralize:
     - config path
     - validation
     - default values
     - migration warning for old keys
   - Keep `config.json` readable from the current working directory during the
     transition.

11. Update tests and scripts
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

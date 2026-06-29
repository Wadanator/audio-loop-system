# Goal 4 - Runtime safety and fallback behavior

## Goal

Make the system safe to run even when one subsystem is missing or unhealthy.
Everything runs on one Raspberry Pi for the room, but the physical installation
should keep working if the web dashboard fails. Development is still allowed to
be rough, but the runtime boundaries should be production-minded before the
final museum install.

## Safety priorities

1. Audio playback and physical DIN buttons are primary.
2. Web dashboard is secondary.
3. Statistics are useful, but should not block playback.
4. LED feedback should follow active state, but LED errors should not break
   audio.
5. Startup should fail only for truly required pieces.

## Implementation log

- `[implemented] 2026-06-28 22:11:36 +02:00` - LED output is now best-effort.
  `LooperEngine` catches LED update/sync errors, and `modbus_led_controller.py`
  sends output writes on a background worker so audio state changes are not
  blocked by normal LED calls.
- `[implemented] 2026-06-28 22:11:36 +02:00` - `main.py` starts input and LED
  output from one shared `ModbusBus`, then stops input first, deactivates the
  looper, requests LEDs off, closes the Modbus bus, and only then shuts down
  audio.
- `[implemented] 2026-06-28 22:34:29 +02:00` - After the package refactor,
  `src/audio_loop/infra/paths.py` anchors runtime paths to the project root and
  `logging_setup.py` was fixed so `critical_errors.log` still goes to root
  `logs/` instead of inside the package directory.
- `[implemented] 2026-06-29 10:47:35 +02:00` - Config loading and
  startup filesystem checks now live in `src/audio_loop/config.py`; systemd
  READY/WATCHDOG notification code now lives in `src/audio_loop/infra/watchdog.py`.
  This keeps runtime setup and watchdog behavior explicit after the package
  refactor.
- `[pending]` - Hardware fault tests: disconnect Box 1 during playback, confirm
  audio continues, LED errors are logged, and reconnect resumes normal LED
  writes.
## Required degraded modes

| Failure | Expected behavior |
| --- | --- |
| Web server cannot bind port | Log error, app continues with DIN buttons |
| Dashboard frontend missing | API can still run, app continues |
| Stats file cannot save | Log error, app continues |
| LED write fails | Audio state changes, log warning, retry later |
| Modbus input disconnected at startup | App starts in degraded mode only if config allows it |
| Modbus input disconnects while running | Keep retrying, dashboard shows input offline |
| Audio files missing | App fails startup with clear setup error |

## Config additions

```json
{
  "runtime": {
    "require_input_provider": true,
    "require_audio_files": true,
    "start_web_in_degraded_mode": true,
    "led_errors_are_fatal": false,
    "status_log_interval_seconds": 600
  },
  "web": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8000
  },
  "paths": {
    "logs_dir": "logs",
    "stats_file": "stats.json",
    "dashboard_static_dir": "src/audio_loop/web/static"
  },
  "modbus_panel": {
    "connect_retry_seconds": 2,
    "max_startup_failures": 3
  }
}
```

## Implementation steps

1. Make subsystem startup explicit
   - In `AudioLooper._initialize_components`, split setup into:
     - load config
     - setup stats
     - setup audio
     - setup LED output
     - setup core engine
     - setup input
     - setup web
   - Each block logs success/failure with subsystem name.

2. Resolve runtime paths once at startup - `[implemented] 2026-06-29 10:47:35 +02:00`
   - Use explicit `paths` config or project-root defaults.
   - Log files must go to `logs/` under the runtime/project directory, not into
     the installed Python package.
   - Stats and dashboard static paths should be visible in `/api/status` for
     diagnostics.

3. Treat web as optional
   - Start web server in its own thread only if `web.enabled`.
   - Catch web startup exceptions inside the web thread.
   - Do not call `shutdown(exit_code=1)` because web failed.

4. Treat LEDs as best-effort - `[implemented, fault-test pending] 2026-06-28 22:11:36 +02:00`
   - Wrap each LED controller call from `LooperEngine`.
   - Track last LED error for diagnostics.
   - Provide `resync_leds(active_layers)` after Modbus reconnect.

5. Input health
   - Modbus input handler keeps connection state:
     - `connected`
     - `last_success_at`
     - `last_error`
     - `read_failures`
   - If read fails, sleep briefly and retry.
   - Do not spin hot on connection failure.
   - Use explicit reconnect/backoff:
     - first retry after 2 seconds
     - next retries after 5 seconds
     - after 5 consecutive failures, retry every 30 seconds
     - log repeated failures at most once per minute
   - After reconnect, resync LED state from `LooperEngine` active layers.

6. Atomic state snapshots
   - `LooperEngine.get_system_status()` should be safe to call from web.
   - Use existing `_state_lock` when returning mutable state if needed.
   - Return copies/lists, not references to internal dictionaries.

7. Clean shutdown order - `[partially implemented] 2026-06-28 22:11:36 +02:00`
   - Stop input handler first, so no new button events are created.
   - Stop web server or mark it shutting down.
   - Save stats.
   - Turn LEDs off best-effort.
   - Stop looper engine.
   - Stop audio manager.

8. Health endpoints
   - `/health` returns process alive.
   - `/api/status` returns subsystem health:
     - audio ready
     - input provider
     - input connected
     - web enabled
     - stats pending changes
     - last errors

9. Logging
   - Keep current rotating file logs.
   - Avoid per-request web access logs.
   - Add one clear log line for each remote press and physical press.
   - Rate-limit repeated Modbus connection warnings.

## Acceptance criteria

- Killing or disabling the web server does not stop physical button control.
- Disconnecting the DIN box logs input offline and reconnects when restored.
- LED communication errors do not prevent layer activation/deactivation.
- Shutdown attempts to turn all LEDs off.
- `/api/status` clearly reports degraded subsystem state.
- Logs, stats, and dashboard static files resolve to explicit runtime paths.
- systemd watchdog remains compatible with the new app structure.

## Production notes before museum install

- Decide whether input provider is fatal at startup:
  - During development: maybe false, so web-only testing works.
  - Final install: true, so a broken DIN panel is noticed immediately.
- Enable web auth before the system is reachable from any shared network.
- Keep service restart policy, but avoid restart loops for web-only failures.

# Audio Loop System - implementation roadmap

This folder splits the production-ready work into independent implementation
goals. Each file is meant to be usable as a small project ticket: goal, scope,
steps, acceptance criteria, and risks.

Reference inputs:

- Current project: `audio-loop-system`
- Hardware guide: `C:/Users/Wajdy/Desktop/Museum/Miestnosti_Popisy_napady/Second ROOM/navod.md`
  (V11 - DIN box wiring and Python reference implementation)
- UI reference project: `C:/Users/Wajdy/Documents/Kodovanie/museum-system`

## Documentation rule: plan + implementation log

These `.md` files are not only plans. They are also the implementation log for
work done in small phases.

Whenever a phase, step, script, or behavior is implemented, update the relevant
`.md` file in the same change with:

- status marker: `[implemented]`, `[partially implemented]`, `[verified]`, or
  `[pending]`
- timestamp in local time, for example `2026-06-28 21:55:36 +02:00`
- changed files
- what was verified
- what remains pending

Do not leave a completed code change represented only as a future TODO in the
plan. If code exists, the matching plan section must say so explicitly.

## Target outcome

The audio system keeps the current reliable playback core, but replaces direct
Raspberry Pi GPIO buttons with DIN box Modbus buttons and backlight outputs.
One Raspberry Pi hosts everything for the room: audio playback, Modbus panel
polling, LED feedback, statistics, and the web dashboard.

The web UI should use the same design language as `museum-system`, so every
museum room can feel like part of one system. This room's dashboard is much
simpler: it shows active audio layers and allows remote "press button" control.
The web UI is useful, but it must not be required for the physical installation
to work.

## Deployment model

- One Raspberry Pi per room runs the full room stack.
- The Python backend serves the API and the built dashboard from the same host
  and port in production.
- During frontend development, Vite may run on a separate local port, but it
  should proxy `/api` and `/health` to the Python backend instead of requiring
  production CORS.
- Each room can have its own labels, audio files, and config, but the dashboard
  components and visual style should stay shared or copied from the same source.

## Hardware topology (decided, V11)

The button panel for this room is built as three DIN boxes:

- **Box 1** - Waveshare IO 8CH module + its own Ethernet-to-RS485 module, own
  IP (e.g. `192.168.0.200`), Modbus unit `0x01`.
- **Box 2** - Waveshare IO 8CH module + its own Ethernet-to-RS485 module, own
  IP (e.g. `192.168.0.201`), Modbus unit `0x01`.
- **Box 3** - Raspberry Pi.

Box 1 and Box 2 are hardware-identical and fully independent: each has its own
Ethernet module and its own IP address, and there is **no RS485 wiring between
the boxes**. Both Waveshare IO modules stay on their factory Modbus address
(`0x01`) - they are distinguished by IP, not by unit ID. The Raspberry Pi talks
to each box over its own Modbus TCP connection.

This means the software must treat the panel as **two independent Modbus TCP
endpoints**, not as one endpoint addressing two unit IDs on a shared bus.

## Current implementation milestone

One external IO module is already confirmed working via `tests/di_monitor.py`.
The current software milestone is Phase A of `01_DIN_MODBUS_BUTTONS.md`: remove
RPi GPIO from the production startup path and accept external Modbus DI events
from the working 8-channel module. That path must run on Windows as well as on
Raspberry Pi.

Implementation log:

- `[implemented] 2026-06-28 21:55:36 +02:00` - Phase A code path created.
  `main.py` now creates `modbus_panel`, the Modbus input handler was added
  and later moved to `src/audio_loop/input/modbus_panel.py`, `config.json`
  points to `box_1` at `192.168.0.200:4196`, and normal install dependencies
  no longer include `RPi.GPIO`.
- `[verified] 2026-06-28 22:11:36 +02:00` - Full app started on Windows with
  Box 1 connected. Real DI presses were logged through the running app for
  multiple channels (`DI1`, `DI3`, `DI4`, `DI6`, `DI7`, `DI8`) and reached
  `LooperEngine.handle_button_press(...)`. Channels without WAV files correctly
  produced "instrument not available" warnings instead of crashing.
- `[implemented] 2026-06-28 22:11:36 +02:00` - Shared Modbus bus and LED output
  code added. `modbus_bus.py` now owns one client/lock per module, input polling
  uses that shared bus, and `modbus_led_controller.py` mirrors active layers to
  DO outputs best-effort.
- `[implemented] 2026-06-28 22:16:02 +02:00` - Fixed config encoding after the
  `outputs` edit. `config.json` is UTF-8 without BOM again, and `main.py` reads
  config with `utf-8-sig` so a future BOM does not block startup.
- `[verified] 2026-06-28 22:20:24 +02:00` - Box 1 DI1/DO1 end-to-end hardware
  test passed in the running app: DI1 triggered instrument 1 and DO1/LED1
  turned on/off with the layer state.
- `[verified] 2026-06-28 22:23:20 +02:00` - Deliberate full Box 1 DI1-DI8 app
  pass completed. Instruments 1-4 activate and light active LEDs; instruments
  5-8 are unavailable in the current `song1` audio set and correctly log
  warnings without activating or crashing.
- `[implemented] 2026-06-28 22:34:29 +02:00` - Goal 2 refactor first pass
  completed. Runtime modules moved under `src/audio_loop/`, `python main.py`
  imports `audio_loop.app`, and smoke/import checks passed. Real Box 1 hardware
  retest after refactor is still pending.
- `[implemented] 2026-06-29 10:28:27 +02:00` - Clean development policy applied:
  old root compatibility wrappers and the historical GPIO `button_handler.py`
  were removed. Future refactor work should prefer deleting obsolete files over
  preserving unused old entry points.
- `[implemented] 2026-06-29 10:37:00 +02:00` - Test/bench scripts moved
  into `tests/`; the old `test/` directory and GPIO-only button test were
  removed.
- `[implemented] 2026-06-29 10:47:35 +02:00` - Goal 2 config/watchdog
  cleanup completed. Config loading lives in `src/audio_loop/config.py`, systemd
  notifications live in `src/audio_loop/infra/watchdog.py`, and smoke/import
  checks passed.
- `[implemented] 2026-06-29 10:55:23 +02:00` - Clean config/install/docs cleanup completed.
  Runtime config no longer contains a `raspberry_pi` block; button cooldown now
  lives under `inputs.button_cooldown_seconds`. `src/audio_loop/app.py` now uses
  `input_handler` naming, `requirements.txt` no longer includes `pygame`, root
  shell scripts were refreshed, obsolete `install_requirements.py` and
  `docs/TODO_rs485_migration.md` were deleted, active docs were rewritten for
  the current Modbus TCP architecture, and generated `__pycache__` folders were
  removed.
- `[verified] 2026-06-29 10:56:59 +02:00` - Syntax check passed for the launcher, changed package
  modules, and test/bench scripts. `tests/smoke_refactor.py` passed. PowerShell
  JSON check confirmed `inputs.provider = modbus_panel`,
  `inputs.button_cooldown_seconds = 1.5`, and no `raspberry_pi` key in
  `config.json`.
- `[implemented] 2026-06-29 11:22:08 +02:00` - Goal 3 React dashboard foundation added.
  Backend API is in `src/audio_loop/web/server.py`, React/Vite source is in
  `dashboard/`, and `npm run build` outputs production assets to
  `src/audio_loop/web/static/`. Browser and hardware remote-press verification
  remain pending.
- `[implemented] 2026-06-29 11:40:10 +02:00` - Goal 3 operator UI pass applied.
  The React dashboard now has only `Prehlad` and `Zvuky`, Slovak UI copy,
  no operator Diagnostics page, simplified layer cards with count/INPUT/LED,
  and a default 16-sound room target. Changed files are logged in
  `03_WEB_DASHBOARD.md`.
- `[verified] 2026-06-29 15:29:30 +02:00` - Goal 3 operator dashboard build and smoke pass
  completed. `npm run build` refreshed `src/audio_loop/web/static/`, the static
  bundle no longer contains the old operator Diagnostics UI, Python
  `py_compile` passed, and `tests/smoke_refactor.py` passed.
- `[pending]` - Run the real Box 1 app after the refactor/config cleanup to
  confirm DI/DO behavior is unchanged, then continue with Goal 3 dashboard
  verification or the remaining runtime safety improvements.
- `[reviewed] 2026-06-29 15:34:54 +02:00` - Button feel rework plan corrected
  against the real code. `03.1_BUTTON_REWORK_TODO.md` now targets `config.json`,
  16 sounds, a per-instrument engine state machine, removal of redundant timing
  guards, and conservative Modbus timing defaults until two-box measurement.
- `[implemented, verified] 2026-06-29 15:44:29 +02:00` - Button feel rework
  implemented. `LooperEngine` now uses per-instrument states, old cooldown and
  Modbus double-press guards were removed, config now uses `min_on_seconds` and
  `rearm_seconds`, runtime/stats/audio paths use the 16-sound config target,
  and smoke tests cover locked press, rearm cooldown, missing audio, and clean
  config. Real Box 1 bench verification is still pending.
- `[implemented, verified] 2026-06-29 15:54:15 +02:00` - Clean-development pass after button rework: runtime docstrings/plans now reflect the 16-sound room target, and `StatsCollector` ignores unknown historical layer keys such as `instrument_17` when loading an old `stats.json`. `py_compile` and `tests/smoke_refactor.py` passed again.

## Implementation order

0. `00A_MODBUS_BRINGUP.md`
   - Test Modbus TCP, one IO box (its own Ethernet-to-RS485 module plus the
     Waveshare IO module), one button, and one LED before touching the audio
     system.
   - Then test the second IO box independently, on its own IP address.
   - Then run both boxes concurrently from one Python process and confirm
     they do not interfere with each other.

1. `01_DIN_MODBUS_BUTTONS.md`
   - Make the audio system work with the DIN button boxes from the hardware
     guide.
   - Remove direct RPi GPIO buttons from the production path.
   - Drive button LEDs from active audio layer state.

2. `02_CODEBASE_REFACTOR.md`
   - Turn the flat Python files into a cleaner package structure.
   - Keep behavior stable while moving code into focused modules.
   - Prepare clean boundaries for inputs, outputs, web, stats, and playback.

3. `03_WEB_DASHBOARD.md`
   - Bring over the useful dashboard look and small UI building blocks from
     `museum-system`.
   - Build a much smaller dashboard for active layers and remote button press.
   - Keep remote press routed through the same logic as physical buttons.

3.1. `03.1_BUTTON_REWORK_TODO.md`
   - Rework button feel with a per-instrument state machine.
   - Remove redundant old timing guards and keep LED feedback simple.

4. `04_RUNTIME_SAFETY.md`
   - Make sure web failure does not stop physical buttons or audio playback.
   - Add safer startup, degraded modes, health status, and recovery behavior.

5. `05_TESTING_AND_DEPLOYMENT.md`
   - Add the tests and manual verification needed before installing on the
     final Raspberry Pi.
   - Prepare service files, setup checks, and deployment checklist.

## Early risk checkpoints

Handle these before the larger refactor starts:

- **Resolved** - Ethernet-to-RS485 bridge behavior. The panel uses two fully
  independent boxes, each with its own Ethernet-to-RS485 module and its own
  IP address. There is no shared RS485 bus between boxes. Both Waveshare IO
  modules stay on their factory Modbus address (unit `0x01`) and are
  distinguished by IP, not by unit ID. The software needs two independent
  Modbus TCP endpoints (one client per box), not one endpoint addressing two
  unit IDs. See `navod.md` (V11) for the wiring and Python reference this
  decision is based on.
- Put all Modbus reads and writes behind one shared bus layer. `pymodbus`
  clients should not be used concurrently from input and LED threads without
  a lock or command queue. Because there are two independent boxes, the bus
  layer owns one client per box (per IP) and synchronizes access to each
  client separately.
- Add smoke tests before moving files. Refactor should start only after there
  is at least one import/startup test that runs without Raspberry Pi GPIO.
- Start Modbus polling conservatively at 50-100 ms and measure on real
  hardware before lowering it.
- Implement reconnect/backoff early, because hardware/network failure is more
  likely than dashboard logic failure. Each box reconnects independently - one
  box being offline must not block polling or LED writes for the other.
- Define runtime paths explicitly (`logs`, `stats`, dashboard static files) so
  moving code into `src/` does not accidentally write inside the package.
- Keep the production dashboard same-origin. Use a Vite dev proxy for local UI
  development instead of making CORS part of the production design.

## High-level architecture target

```text
src/audio_loop/
  app.py
  config.py
  audio/
    manager.py
  core/
    looper_engine.py
    events.py
  hardware/
    modbus_bus.py
  input/
    base.py
    modbus_panel.py
  output/
    led_panel.py
  web/
    app.py
    routes.py
    static/
  stats/
    collector.py
  infra/
    logging_setup.py
    paths.py
    watchdog.py

config/
  config.json

scripts/
  verify_modbus_panel.py
  run_dev.py

tests/
```

## Non-negotiable behavior

- One Raspberry Pi must be enough to run the complete room system.
- Physical DIN buttons must work without web UI.
- Audio playback must not depend on the dashboard being reachable.
- Web remote press must behave exactly like a physical button press.
- Button LED state must reflect currently active audio layers.
- Startup should be useful in development even before final museum install.
- Refactor should be incremental, but because the system is still in
  development, obsolete compatibility files should be deleted instead of kept
  indefinitely.
- The panel is two independent Modbus TCP endpoints (one per box). One box
  being unreachable must not prevent the other box from working.

## Important design decision

This room is now planned as a maximum 16-sound installation because the DIN
hardware target is 2x Waveshare 8CH modules: 16 DI button inputs and 16 DO LED
outputs.

Implementation rules:

- buttons 1-8: Box 1 by default
- buttons 9-16: Box 2 by default once the second module is added
- dashboard displays at most 16 sounds for this room
- audio/config may stay mapping-driven, but the default room target is 16, not
  the old 18-layer prototype layout
- do not add compatibility-only files for the older GPIO/prototype structure;
  this system is still in development, so obsolete files should be deleted
## Done when

- All implementation files are either completed or converted into issues.
- The old `docs/TODO_rs485_migration.md` was deleted after being superseded by these files.
- The README points to this roadmap after implementation begins.

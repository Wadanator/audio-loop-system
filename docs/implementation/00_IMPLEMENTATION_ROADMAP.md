# Audio Loop System - implementation roadmap

This folder splits the production-ready work into independent implementation
goals. Each file is meant to be usable as a small project ticket: goal, scope,
steps, acceptance criteria, and risks.

Reference inputs:

- Current project: `audio-loop-system`
- Hardware guide: `C:/Users/Wajdy/Desktop/Museum/Miestnosti_Popisy_napady/Second ROOM/navod.md`
  (V11 - DIN box wiring and Python reference implementation)
- UI reference project: `C:/Users/Wajdy/Documents/Kodovanie/museum-system`

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

One external IO module is already confirmed working via `test/di_monitor.py`.
The next software step is not the full dashboard or two-box setup yet. The next
step is to remove RPi GPIO from the production path and make the app accept
external Modbus DI events from the working 8-channel module. That path must run
on Windows as well as on Raspberry Pi.

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
- Refactor should be incremental: move first, change behavior second.
- The panel is two independent Modbus TCP endpoints (one per box). One box
  being unreachable must not prevent the other box from working.

## Important design decision

The current code supports 18 instruments. The documented DIN hardware has
2x Waveshare 8CH modules (one per independent box), so it gives 16 physical
button channels.

Implementation should keep 18 audio layers supported, but make physical mapping
configurable:

- buttons 1-16: DIN panel by default (8 on Box 1, 8 on Box 2)
- buttons 17-18: web-only, future third module, or disabled by config

Do not hard-code the number 16 into the audio engine. Hardware mapping belongs
in input/output config only.

## Done when

- All implementation files are either completed or converted into issues.
- The old `docs/TODO_rs485_migration.md` is superseded by these files.
- The README points to this roadmap after implementation begins.

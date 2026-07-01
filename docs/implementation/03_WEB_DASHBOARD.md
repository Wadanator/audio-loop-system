# Goal 3 - Simple operator dashboard with remote layer control

## Goal

Add a small React dashboard that looks consistent with `museum-system`, but is
focused on room operation only. It should show the current song, short runtime
status, active audio layers, activation counts, and allow
remote "press button" actions. The operator UI intentionally does not show
separate INPUT/LED boxes on each sound card; the active card state and the
physical button LED are the normal feedback.

The dashboard must be optional. If it crashes, fails to bind, or is not built,
the DIN buttons and audio playback must still work.

Production is single-RPi and same-origin: the Python process serves both the API
and the built dashboard. During development, Vite can run separately, but it
should proxy API calls to the Python backend so production does not need CORS.

UI text is Slovak for the operator. Source code, component names, and comments
stay English.

## Exact UI reference

Use this project as the concrete design reference:

`C:/Users/Wajdy/Documents/Kodovanie/museum-system/museum-dashboard`

Copy the visual language and useful primitives from there, but keep this room dashboard much smaller. The app shell should feel like it was assembled from the same component template as museum-system; room-specific differences should be limited to the audio views and audio actions.

## What to copy from museum-system

Use the reference dashboard for look and structure, not for full feature scope.

Useful source files:

- `museum-dashboard/package.json`
- `museum-dashboard/src/styles/theme.css`
- `museum-dashboard/src/styles/base.css`
- `museum-dashboard/src/styles/layout.css`
- `museum-dashboard/src/styles/components.css`
- `museum-dashboard/src/components/Layout/AppLayout.jsx`
- `museum-dashboard/src/components/Layout/Sidebar.jsx`
- `museum-dashboard/src/components/ui/Button.jsx`
- `museum-dashboard/src/components/ui/Card.jsx`
- `museum-dashboard/src/components/ui/StatusBadge.jsx`
- `museum-dashboard/src/services/api.js`

Do not copy heavy features:

- scene editor
- media manager
- React Flow
- Monaco editor
- full MQTT device management
- drag and drop libraries
- technical Diagnostics page for normal operators

## Target UI scope

Views:

1. Overview / Prehľad
   - current song
   - simple system state: ready, playing, or dashboard offline
   - active sound count and a short list of what is running
   - time until global timeout
   - Modbus panel state in short form
   - overview shows a compact warning when one or both configured Modbus boxes are disconnected
   - web/backend connection state

2. Sounds / Zvuky
   - grid of audio sounds 1-16
   - each card shows only operator-relevant data:
     - number/name
     - status: hrá, čaká, or chýba
     - activation count
     - small connection dot: green means the module for this sound communicates and the channel is mapped; red means module offline, not communicating, or mapping missing
     - no tooltip for the connection dot
     - one remote press button
     - green active card when the sound is playing
     - no separate INPUT/LED boxes for normal operators
   - do not show module/channel/IP/register details in this view

No operator Diagnostics page is planned for this room dashboard. Technical
information stays in logs, health/status API responses, and developer tooling.

## Backend API

Replace the old stats-only server with small Flask JSON routes and a static React build server.

Minimum routes:

```text
GET  /api/status
GET  /api/layers
POST /api/layers/<instrument_num>/press
GET  /api/stats
GET  /health
```

`GET /api/status` should return:

```json
{
  "system_active": true,
  "current_song": {"name": "song1", "index": 0, "total_songs": 3},
  "active_instruments": [1, 3, 7],
  "available_instruments": [1, 2, 3, 4],
  "time_until_timeout": 51.2,
  "web_enabled": true,
  "input_provider": "modbus_panel",
  "modbus_connected": true
}
```

`POST /api/layers/<instrument_num>/press` must call:

```python
looper_engine.handle_button_press(instrument_num)
```

That is important. Do not duplicate toggle logic in web routes.

## Remote press behavior

Remote press is not a separate control mode. It is the same event as a physical
button press.

Expected result:

- dashboard user clicks sound 4
- backend calls `handle_button_press(4)`
- audio layer 4 toggles with normal fade behavior
- stats record instrument 4 exactly as a physical press would
- LED 4 updates because `LooperEngine` updates LED state
- `/api/status` and `/api/layers` reflect the new state

## Frontend implementation steps

1. Create `dashboard/` - `[implemented] 2026-06-29 11:20:00 +02:00`
   - Use Vite + React. Current source path: `dashboard/`.
   - Keep dependencies small:
     - `react`
     - `react-dom`
     - `vite`
     - `lucide-react`
   - Avoid React Router until there are multiple real pages. A simple tab state
     is enough.

2. Copy selected CSS/design primitives - `[implemented] 2026-06-29 11:40:10 +02:00`
   - Keep the same general language as `museum-system`: dark sidebar, compact
     top status strip, white hero/status card, status color bands, clear cards,
     and Lucide icons.
   - Keep only the CSS needed for app shell, sidebar, buttons, login, system
     actions, overview status, layer cards, and badges.
   - Remove unused operator diagnostics styling.

3. Create API service - `[implemented, auth-header prepared] 2026-06-29 16:25:42 +02:00`
   - `dashboard/src/services/api.js`
   - In production, call same-origin `/api/...` URLs.
   - In development, configure Vite proxy for `/api` and `/health` to avoid
     browser CORS issues while keeping production simple.
   - API requests include `Authorization` from localStorage `auth_header` when
     present, matching the `museum-system` frontend shape for later backend auth.
   - Methods:
     - `getStatus`
     - `getLayers`
     - `pressLayer`
     - `getStats`

4. Create components - `[implemented, extended] 2026-06-29 16:25:42 +02:00`
   - `dashboard/src/components/Layout/AppLayout.jsx`
   - `dashboard/src/components/Layout/Sidebar.jsx`
   - `dashboard/src/components/Runtime/RuntimeStatusBar.jsx`
   - `dashboard/src/components/Overview/OverviewHero.jsx`
   - `dashboard/src/components/Overview/OverviewView.jsx`
   - `dashboard/src/components/Layers/LayersView.jsx`
   - `dashboard/src/components/Layers/LayerCard.jsx`
   - `dashboard/src/components/Auth/LoginView.jsx`
   - `dashboard/src/components/System/SystemView.jsx`
   - `dashboard/src/components/ui/Button.jsx`
   - `dashboard/src/components/ui/StatusBadge.jsx`

5. Add polling - `[implemented] 2026-06-29 11:20:00 +02:00`
   - Poll `/health`, `/api/status`, `/api/layers`, and `/api/stats` every
     second while dashboard is open.
   - Show stale/offline state if fetch fails.

6. Add lightweight live updates - `[pending]`
   - Prefer Server-Sent Events for status/layer changes once basic polling is
     no longer enough.
   - SSE is enough for dashboard feedback and avoids WebSocket complexity.
   - Keep polling as fallback when the SSE stream disconnects.
   - Socket.IO is not currently part of the dashboard dependency set; add it only if real push updates become worth the extra dependency.

7. Build static assets - `[verified] 2026-06-29 15:29:30 +02:00`
   - Vite build outputs into Python web static directory:
     - `src/audio_loop/web/static/`
   - Python backend serves the built `index.html` for dashboard paths.

## Backend implementation steps

1. Replace inline HTML dashboard - `[implemented] 2026-06-29 11:20:00 +02:00`
   - Keep `/api/stats` compatible with existing stats.
   - Serve built React app for `/` from the same Raspberry Pi backend.
   - Do not require production CORS when frontend and API are same-origin.

2. Inject dependencies into web app - `[implemented] 2026-06-29 11:20:00 +02:00`
   - Web routes need references to:
     - `LooperEngine`
     - `StatsCollector`
     - input/LED status provider if available

3. Add auth only if needed - `[partially implemented in frontend] 2026-06-29 16:25:42 +02:00`
   - Frontend login panel now matches `museum-system` and uses the same default
     credentials: `admin` / `admin12321`.
   - Successful login stores localStorage `auth_header` and API requests send it.
   - Backend auth enforcement is implemented for `/api/` routes when `web.auth_enabled` is true.
   - Remote press and system command routes are protected on the backend before final install.

4. Make web optional - `[implemented] 2026-06-29 11:20:00 +02:00`
   - Config:

```json
{
  "web": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8000,
    "auth_enabled": true,
    "username": "admin",
    "password": "admin12321",
    "system_actions_enabled": true,
    "system_service_name": "audio_looper.service"
  }
}
```

   - If disabled, app starts without web thread.
   - If bind fails, log error and keep app running.

## Implementation log

- `[implemented] 2026-07-01` - Backend auth and system actions wired.
  `/api/` routes now enforce Basic Auth when enabled in `config.json`, frontend
  login validates against the backend, and the System tab calls authenticated
  endpoints for service restart, Raspberry Pi reboot, and Raspberry Pi shutdown.
  The dashboard uses a local confirmation dialog matching the museum-system
  interaction pattern. `install.sh` configures a narrow sudoers rule for only the
  reboot/shutdown commands.
- `[implemented] 2026-06-29 11:20:00 +02:00` - Backend dashboard API started.
  `src/audio_loop/web/server.py` serves `/health`, `/api/status`, `/api/layers`,
  `/api/stats`, and `POST /api/layers/<instrument>/press`. Remote press routes
  call `LooperEngine.handle_button_press(...)` directly.
- `[implemented] 2026-06-29 11:20:00 +02:00` - Modular React/Vite dashboard
  source created under `dashboard/`, following the structure and visual language
  of `C:/Users/Wajdy/Documents/Kodovanie/museum-system/museum-dashboard`.
  The Python backend serves the built files from `src/audio_loop/web/static/`.
- `[verified] 2026-06-29 11:23:57 +02:00` - `npm install` completed for
  `dashboard/` and `npm run build` generated React production assets into
  `src/audio_loop/web/static/`.
- `[verified] 2026-06-29 11:23:57 +02:00` - Python `py_compile` passed for
  `main.py`, `src/audio_loop/app.py`, `src/audio_loop/web/server.py`, and
  dashboard-related tests. `tests/smoke_refactor.py` passed after the web server
  rename.
- `[verified] 2026-06-29 11:25:46 +02:00` - Vite dev server started for the React dashboard and
  returned HTTP 200 at `http://127.0.0.1:5174`. It will show backend-offline
  state until the Python backend is running on port 8000.
- `[implemented] 2026-06-29 11:40:10 +02:00` - Operator UI pass completed in
  source. Removed the Diagnostics view from navigation/rendering, changed the
  UI copy to Slovak, limited the dashboard target to 16 sounds, simplified layer
  cards to status/count/INPUT/LED/remote press, and matched the `museum-system`
  dashboard visual structure more closely.
  Changed files: `dashboard/src/App.jsx`, `dashboard/src/components/Layout/Sidebar.jsx`,
  `dashboard/src/components/Runtime/RuntimeStatusBar.jsx`,
  `dashboard/src/components/Overview/OverviewHero.jsx`,
  `dashboard/src/components/Overview/OverviewView.jsx`,
  `dashboard/src/components/Layers/LayersView.jsx`,
  `dashboard/src/components/Layers/LayerCard.jsx`,
  `dashboard/src/styles/components.css`, `src/audio_loop/web/server.py`,
  `config.json`.
  Verification: source scan found no `Diagnostics` component references in
  `dashboard/src`. Production build verification is recorded separately after
  running `npm run build`.
- `[verified] 2026-06-29 15:29:30 +02:00` - Production React build completed after the
  operator UI redesign. `npm run build` in `dashboard/` generated
  `src/audio_loop/web/static/index.html`, `assets/index-C4OR_I5n.js`, and
  `assets/index-cEPzPVN-.css`. A source/static scan confirmed no operator
  `Diagnostics` page or old English dashboard labels remain in the active
  React source/build. Python `py_compile` passed for `main.py`,
  `src/audio_loop/app.py`, `src/audio_loop/web/server.py`, and dashboard smoke
  tests. `tests/smoke_refactor.py` passed.

- `[implemented, verified] 2026-06-29 16:12:18 +02:00` - Operator cleanup from screenshot review.
  The Overview page now removes duplicate summary cards (`Aktívne zvuky`,
  `Pripravené`) and keeps only the compact status/current song/running layers
  surface. Layer cards no longer show `Zvuk X` twice when the label is the
  default. `/api/layers` now includes `input_state` from the debounced Modbus DI
  state and `led_state` from successful DO writes, and the React INPUT/LED
  indicators use those live states instead of only showing whether a channel is
  mapped. Removed the now-unused `SummaryCard.jsx` component.
  Changed files: `src/audio_loop/input/modbus_panel.py`,
  `src/audio_loop/web/server.py`, `dashboard/src/components/Overview/OverviewView.jsx`,
  `dashboard/src/components/Overview/OverviewHero.jsx`,
  `dashboard/src/components/Layers/LayersView.jsx`,
  `dashboard/src/components/Layers/LayerCard.jsx`,
  `dashboard/src/styles/components.css`, `tests/smoke_refactor.py`, and the built
  files under `src/audio_loop/web/static/`.
  Verification: Python `py_compile` passed, `tests/smoke_refactor.py` passed,
  and `npm run build` regenerated the production dashboard assets.
- `[implemented, verified] 2026-06-29 16:25:42 +02:00` - Museum-style login and system tab pass completed.
  Added the `museum-system`-style login panel with the same default credentials
  (`admin` / `admin12321`), localStorage `auth_header`, and matching API auth
  header shape. Added a `Systém` navigation tab with backend/RPi restart and
  shutdown buttons wired to authenticated backend command endpoints with confirmation dialogs. Removed the separate INPUT/LED boxes from sound
  cards so the operator sees only status, count, and the remote sound button;
  the green active card and real panel LED remain the normal feedback.
  Changed files: `src/audio_loop/stats/collector.py`, `tests/smoke_refactor.py`,
  `dashboard/src/App.jsx`, `dashboard/src/context/AuthContext.jsx`,
  `dashboard/src/services/api.js`, `dashboard/src/components/Auth/LoginView.jsx`,
  `dashboard/src/components/System/SystemView.jsx`,
  `dashboard/src/components/Layout/AppLayout.jsx`,
  `dashboard/src/components/Layout/Sidebar.jsx`,
  `dashboard/src/components/Layers/LayerCard.jsx`, `dashboard/src/components/ui/*`,
  `dashboard/src/styles/theme.css`, `dashboard/src/styles/components.css`, and
  the built files under `src/audio_loop/web/static/`.
  Verification: Python `py_compile` passed, `tests/smoke_refactor.py` passed,
  `npm run build` regenerated `assets/index-D7cLrbf-.js` and
  `assets/index-r7ljb3CZ.css`, and source scan found no old INPUT/LED layer-card
  UI tokens in `dashboard/src`.
- `[implemented, verified] 2026-06-30 16:59:22 +02:00` - Per-sound Modbus connection dot and `Zvuky` header alignment completed.
  `/api/layers` now exposes `input_connected`, which is true only when a
  physical input mapping exists for the sound and the owning Modbus module
  currently reports `connected`. Missing mapping, offline module, or failed
  communication returns false for the dashboard. Layer cards show only a small
  green/red dot next to the status badge, with no visible tooltip, and the
  `Zvuky` page now uses the shared `PageHeader` style like the `System` page.
  Changed files: `src/audio_loop/web/server.py`, `tests/smoke_refactor.py`,
  `dashboard/src/components/Layers/LayersView.jsx`,
  `dashboard/src/components/Layers/LayerCard.jsx`, `dashboard/src/styles/components.css`,
  and the rebuilt files under `src/audio_loop/web/static/`.
  Verification: Python `py_compile` passed for the changed backend/test files,
  `tests/smoke_refactor.py` passed, `npm run build` passed, and a UTF-8 source
  check confirmed the Slovak dashboard copy is not mojibake.

- `[implemented, verified] 2026-06-30 17:12:15 +02:00` - Shared museum-style app shell pass completed.
  The audio dashboard now uses the same `museum-system` sidebar pattern: MUSEUM
  brand block, compact audio-specific navigation, admin footer with avatar,
  `Správca` label, theme toggle icon button, and icon-only logout button. Added
  a small `useTheme` hook with `data-theme`/localStorage support and dark theme
  tokens copied from the reference style approach. The `Systém` view now matches
  the reference card layout more closely: no persistent bottom note, prepared
  actions show a floating toast-style message, and secondary/danger buttons use
  the shared gradient control style.
  Changed files: `dashboard/src/App.jsx`, `dashboard/src/hooks/useTheme.js`,
  `dashboard/src/components/Layout/AppLayout.jsx`,
  `dashboard/src/components/Layout/Sidebar.jsx`,
  `dashboard/src/components/System/SystemView.jsx`, `dashboard/src/styles/theme.css`,
  `dashboard/src/styles/layout.css`, `dashboard/src/styles/components.css`, and
  the rebuilt files under `src/audio_loop/web/static/`.
  Verification: `npm run build` passed and a UTF-8 source check found no
  mojibake in the changed React/CSS files.
- `[implemented, verified] 2026-06-30 17:22:37 +02:00` - Web backend migrated from the built-in `http.server` handler to Flask.
  `src/audio_loop/web/server.py` now exposes `create_dashboard_app(...)`, a
  `DashboardService` payload layer, Flask API routes for `/health`,
  `/api/status`, `/api/layers`, `/api/stats`, and the same remote layer press
  route. The Flask app also serves the React production build and SPA fallbacks
  from `src/audio_loop/web/static/`. `run_dashboard_server(...)` still runs the
  web stack as an optional background server with bind retries, so physical
  Modbus buttons and audio are not dependent on the dashboard.
  Changed files: `src/audio_loop/web/server.py`, `requirements.txt`,
  `tests/smoke_refactor.py`, `tests/test_live_system.py`, `README.md`,
  `docs/03_how_it_works.md`, and the implementation docs.
  Verification: Flask is available in the local Python environment, Python
  `py_compile` passed, `tests/smoke_refactor.py` passed, `npm run build` passed,
  and Flask `test_client` returned HTTP 200 for `/health`, `/api/status`,
  `/api/layers`, `/`, `/system`, and the built JS asset. `/health` reports
  `web_backend: flask`.

- `[implemented, verified] 2026-06-30 17:27:16 +02:00` - Final small branding alignment.
  The Vite HTML title now uses `Museum Control System` instead of `Audio Loop
  Dashboard`, matching the shared museum dashboard brand. `npm run build`
  regenerated the Flask-served static `index.html`, and Flask `test_client`
  route checks still returned HTTP 200.
- `[implemented, verified] 2026-06-30 17:37:20 +02:00` - Overview Modbus degraded warning added.
  `/api/status` now reports `modbus_degraded` and
  `modbus_disconnected_modules`, derived from the shared Modbus bus status.
  The `Prehľad` hero shows a Slovak warning if one configured box is offline
  and a stronger warning if both configured boxes are offline, while remote web
  control and any still-connected module continue to work. Socket.IO was not
  added in this pass because neither `flask_socketio` nor `socket.io-client` is
  installed in this project, and the existing one-second polling remains the
  simpler safe fallback for the current operator dashboard.
  Changed files: `src/audio_loop/web/server.py`,
  `dashboard/src/components/Overview/OverviewHero.jsx`,
  `dashboard/src/styles/components.css`, `tests/smoke_refactor.py`, and the
  rebuilt files under `src/audio_loop/web/static/`.
  Verification: Python `py_compile` passed, `tests/smoke_refactor.py` passed,
  `npm run build` passed, and UTF-8 source checks confirmed the Slovak warning
  copy is not mojibake.

## Acceptance criteria

- Dashboard loads from the Raspberry Pi web server on the same host as the API.
- Vite development can call the backend through a dev proxy without CORS errors.
- It shows active sounds within 1-2 seconds; physical INPUT/LED details stay in backend API/logs and the active card plus real panel LED are enough for operators.
- Clicking sound 1 remote press behaves like physical button 1.
- Physical DIN button press updates dashboard state.
- Web failure does not stop audio or physical controls.
- Overview shows a clear Modbus warning when one or both configured boxes are disconnected, without blocking other working controls.
- The visual style clearly matches `museum-system`, but the feature surface is
  much smaller.
- The operator UI is Slovak and does not expose technical diagnostics as a
  normal navigation item.
- The default dashboard and config target a maximum of 16 sounds for this room.

## Nice-to-have later

- WebSocket only if two-way realtime control becomes necessary. For this
  dashboard, SSE plus normal POST commands should be enough.
- Read-only kiosk mode.
- Layer labels from config, for example instrument names instead of numbers.
- Per-layer last pressed timestamp.

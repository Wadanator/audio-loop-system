# Goal 3 - Simple dashboard with remote layer control

## Goal

Add a simple web dashboard that looks consistent with `museum-system`, but is
much smaller. It should show active audio layers, current song/session state,
button/LED health, and allow remote "press button" actions.

The dashboard must be optional. If it crashes, fails to bind, or is not built,
the DIN buttons and audio playback must still work.

Production is single-RPi and same-origin: the Python process serves both the API
and the built dashboard. During development, Vite can run separately, but it
should proxy API calls to the Python backend so production does not need CORS.

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

## Target UI scope

Views:

1. Overview
   - current song
   - system active / idle
   - active layer count
   - time until global timeout
   - Modbus panel connection state
   - web/backend connection state

2. Layers
   - grid of audio layers 1-18
   - each layer shows:
     - number/name
     - available audio file yes/no
     - active yes/no
     - physical mapping if present
     - LED state if known
   - each layer has a remote press button

3. Diagnostics
   - last physical press
   - last remote press
   - Modbus errors
   - stats counters
   - service uptime

## Backend API

Replace or extend `stats_server.py` with small JSON routes.

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

- dashboard user clicks layer 4
- backend calls `handle_button_press(4)`
- audio layer 4 toggles with normal fade behavior
- stats record instrument 4 exactly as a physical press would
- LED 4 updates because `LooperEngine` updates LED state
- `/api/status` and `/api/layers` reflect the new state

## Frontend implementation steps

1. Create `web-dashboard/` or `dashboard/`
   - Use Vite + React.
   - Keep dependencies small:
     - `react`
     - `react-dom`
     - `vite`
     - `lucide-react`
   - Avoid React Router until there are multiple real pages. A simple tab state
     is enough.

2. Copy selected CSS/design primitives
   - Copy the CSS variables from `theme.css`.
   - Keep a small shared room UI kit so future rooms can reuse the same visual
     language with different room names, labels, and layer counts.
   - Copy only the layout and component CSS needed for:
     - app shell
     - sidebar or compact nav
     - buttons
     - cards
     - badges
   - Rename classes if needed to avoid unused large styling.

3. Create API service
   - `src/services/api.js`
   - In production, call same-origin `/api/...` URLs.
   - In development, configure Vite proxy for `/api` and `/health` to avoid
     browser CORS issues while keeping production simple.
   - Methods:
     - `getStatus`
     - `getLayers`
     - `pressLayer`
     - `getStats`

4. Create components
   - `src/components/AppShell.jsx`
   - `src/components/StatusStrip.jsx`
   - `src/components/LayerGrid.jsx`
   - `src/components/LayerCard.jsx`
   - `src/components/DiagnosticsPanel.jsx`

5. Add polling
   - Poll `/api/status` every 1 second while dashboard is open.
   - Poll `/api/layers` every 1-2 seconds.
   - Show stale/offline state if fetch fails.

6. Add lightweight live updates
   - Prefer Server-Sent Events for status/layer changes once the basic polling
     API works.
   - SSE is enough for dashboard feedback and avoids WebSocket complexity.
   - Keep polling as fallback when the SSE stream disconnects.

7. Build static assets
   - Vite build outputs into Python web static directory:
     - `src/audio_loop/web/static/`
   - Python backend serves the built `index.html` for dashboard paths.

## Backend implementation steps

1. Replace inline HTML dashboard
   - Keep `/api/stats` compatible with existing stats.
   - Serve built React app for `/` from the same Raspberry Pi backend.
   - Do not require production CORS when frontend and API are same-origin.

2. Inject dependencies into web app
   - Web routes need references to:
     - `LooperEngine`
     - `StatsCollector`
     - input/LED status provider if available

3. Add auth only if needed
   - Development can start with LAN-only access.
   - Before museum deployment, add simple Basic Auth or token config.
   - Remote press must be protected before final install.

4. Make web optional
   - Config:

```json
{
  "web": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8000,
    "auth_enabled": false
  }
}
```

   - If disabled, app starts without web thread.
   - If bind fails, log error and keep app running.

## Acceptance criteria

- Dashboard loads from the Raspberry Pi web server on the same host as the API.
- Vite development can call the backend through a dev proxy without CORS errors.
- It shows active layers within 1-2 seconds.
- Clicking layer 1 remote press behaves like physical button 1.
- Physical DIN button press updates dashboard state.
- Web failure does not stop audio or physical controls.
- The visual style clearly matches `museum-system`, but the feature surface is
  much smaller.
- The room name, layer labels, and diagnostics are configurable per room while
  the UI structure stays consistent across rooms.

## Nice-to-have later

- WebSocket only if two-way realtime control becomes necessary. For this
  dashboard, SSE plus normal POST commands should be enough.
- Read-only kiosk mode.
- Layer labels from config, for example instrument names instead of numbers.
- Per-layer last pressed timestamp.

# Audio Loop System

Museum-room audio looper controlled by external Modbus DIN IO modules.
The current production/development input path is Modbus TCP, not Raspberry Pi GPIO.

## Current State

- Audio playback is currently configured for a maximum of 16 room sounds/layers.
- Box 1 is verified with 8 DI inputs and 8 DO/LED outputs.
- DI1-DI8 are read from `192.168.0.200:4196`, Modbus unit `1`.
- DO outputs mirror active audio layers best-effort; LED failures must not stop audio.
- Root `main.py` is only the launcher. Runtime code lives under `src/audio_loop/`.
- Dashboard source is a modular React/Vite app in `dashboard/`; the operator UI is Slovak and intentionally minimal (`Prehlad` + `Zvuky`).

## Structure

```text
main.py
config.json
dashboard/
  src/
    components/
    hooks/
    services/
    styles/
src/audio_loop/
  app.py
  audio/manager.py
  core/looper_engine.py
  hardware/modbus_bus.py
  input/modbus_panel.py
  output/led_panel.py
  stats/collector.py
  web/server.py
  web/static/
  infra/logging_setup.py
  infra/paths.py
  infra/watchdog.py
tests/
  di_monitor.py
  do_chaser.py
  smoke_refactor.py
  test_live_system.py
```

## Run

```powershell
python main.py
```

On this machine the tested command is:

```powershell
C:\Users\Wajdy\AppData\Local\Programs\Python\Python313\python.exe c:/Users/Wajdy/Documents/Kodovanie/audio-loop-system/main.py
```

## Dashboard

Build the React dashboard into the Python static directory:

```powershell
cd dashboard
npm install
npm run build
```

During development, Vite proxies `/api` and `/health` to the Python backend:

```powershell
cd dashboard
npm run dev
```

The backend serves production dashboard files from `src/audio_loop/web/static/`. The UI shows the current song, simple runtime status, active sounds, activation counts, INPUT/LED indicators, and remote press controls for up to 16 sounds.

## Bench Scripts

Watch DI inputs on the current Box 1:

```powershell
python tests/di_monitor.py --ip 192.168.0.200 --port 4196 --slave 1
```

Run the DO output chaser:

```powershell
python tests/do_chaser.py --ip 192.168.0.200 --port 4196 --slave 1 --delay 0.5 --cycles 3
```

Run the refactor/import smoke test:

```powershell
python tests/smoke_refactor.py
```

## Dependencies

Install the Python dependencies from:

```powershell
pip install -r requirements.txt
```

Current hardware/software dependency highlights:

- `pymodbus` for Modbus TCP DI/DO.
- `sounddevice`, `soundfile`, `numpy` for audio playback.
- `react`, `vite`, and `lucide-react` for the dashboard.
- No `RPi.GPIO` dependency in the current codebase.

## Documentation

Implementation plans and logs are in `docs/implementation/`.
Every implemented step should be logged there with status, timestamp,
changed files, verification, and remaining pending work.
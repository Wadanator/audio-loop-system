# Installation Guide

This project is currently a development build for one museum room. The runtime is cross-platform, but the target deployment is one Raspberry Pi that runs audio processing, Modbus IO, and the local web UI.

## Hardware

- Raspberry Pi 4 or newer for deployment.
- DIN Modbus TCP IO modules for physical buttons and LEDs.
- Current verified module: Box 1 at `192.168.0.200:4196`, Modbus unit `1`.
- Box 1 provides DI1-DI8 and DO1-DO8.
- Box 2 is configured at `192.168.0.201:4196`, Modbus unit `1`, for inputs/outputs 9-16; hardware verification is still pending.
- Audio output through USB DAC, HDMI, or the system default audio device.

Direct Raspberry Pi GPIO buttons are not part of the current system. Do not add `RPi.GPIO` back as a runtime dependency.

## Python Setup

```powershell
pip install -r requirements.txt
```

On the current Windows development machine, the tested command is:

```powershell
C:\Users\Wajdy\AppData\Local\Programs\Python\Python313\python.exe main.py
```

On Raspberry Pi, run the same entrypoint from the project root:

```bash
python3 main.py
```

## Configuration

The active input and output providers are configured in `config.json`:

```json
"inputs": {
  "provider": "modbus_panel",
  "min_on_seconds": 1.5,
  "rearm_seconds": 0.2
},
"outputs": {
  "provider": "modbus_panel",
  "enabled": true
}
```

The Modbus module mapping lives under `modbus_panel.modules`. The current config contains Box 1 for instruments 1-8 and Box 2 for instruments 9-16. Keep both IP addresses unique, and run the bench scripts against each box after wiring changes.

## Audio Files

Put WAV files in `audio_files/<song>/` using numbered filenames:

```text
audio_files/
  song1/
    1.wav
    2.wav
    3.wav
    4.wav
```

Only instruments with a matching WAV in the current song can become active. If DI5 is pressed but `5.wav` is missing, the app logs a warning and the LED should not stay active for that missing layer.

## Bench Tests

Before running the full app on hardware, verify Modbus IO directly:

```powershell
python tests/di_monitor.py --ip 192.168.0.200 --port 4196 --slave 1
python tests/do_chaser.py --ip 192.168.0.200 --port 4196 --slave 1 --delay 0.5 --cycles 3
python tests/di_monitor.py --ip 192.168.0.201 --port 4196 --slave 1
python tests/do_chaser.py --ip 192.168.0.201 --port 4196 --slave 1 --delay 0.5 --cycles 3
```

## Run

```powershell
python main.py
```

Expected startup signs:

- logging initializes without config errors
- Modbus bus connects to Box 1
- Modbus input handler starts for one module
- LED controller starts for 8 outputs
- stats server starts on port 8000

## Web

The current stats server is available at:

```text
http://<rpi-ip>:8000
```

The richer room dashboard is planned in `docs/implementation/03_WEB_DASHBOARD.md`.
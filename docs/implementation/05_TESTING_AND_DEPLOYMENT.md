# Goal 5 - Testing, verification, and deployment

## Goal

Prepare the implementation for real Raspberry Pi deployment without waiting
until the museum is live. The system is still in development, so tests should
make iteration faster and safer rather than slow everything down.

## Test layers

1. Pure unit tests
   - No Raspberry Pi.
   - No real audio device.
   - No real Modbus hardware.

2. Integration tests with fakes
   - Fake input provider calls `handle_button_press`.
   - Fake LED controller records LED calls.
   - Fake audio manager records fade/start/stop calls.
   - Fake Modbus bus verifies that input reads and LED writes for each box are
     serialized through one shared layer, and that one box's fake failures do
     not block the other box's calls.

3. Hardware verification scripts
   - Run on bench hardware.
   - Verify Modbus input and output, on each box independently.
   - Do not require full audio install.

4. Raspberry Pi smoke tests
   - Run with real config and real audio files.
   - Confirm service starts, dashboard loads, and buttons work on both boxes.
   - Start with Box 1 offline and confirm the app reports degraded mode while
     Box 2 still works; repeat the same test with Box 2 offline.

## Unit test checklist

- `LooperEngine`
  - first press starts system and activates layer
  - second press toggles same layer off
  - global timeout deactivates system
  - instrument timeout deactivates only that layer
  - instrument timeout does not reset or incorrectly extend global timeout
  - global timeout clears all active instrument states and LED states
  - instrument timeout and global timeout firing close together is deterministic
  - remote press and physical press use same method
  - LED controller receives on/off calls
  - LED controller exception does not break audio state

- Config
  - valid Modbus config loads, including per-module `host`/`unit_id`
  - old GPIO config gives migration warning
  - missing audio directory fails clearly
  - web disabled config starts without web
  - with two modules configured, one offline module can be marked degraded
    without preventing the other module from working

- Web routes
  - `GET /api/status` returns current state
  - `POST /api/layers/1/press` calls `handle_button_press(1)`
  - invalid layer returns 400
  - production API and dashboard are same-origin
  - auth blocks remote press when enabled

## Fake classes to add

Add small test fakes under `tests/fakes.py`:

```python
class FakeAudioManager:
    def __init__(self):
        self.started = False
        self.fade_ins = []
        self.fade_outs = []

class FakeLedController:
    def __init__(self):
        self.calls = []
        self.fail = False
```

Use fakes instead of mocking large modules when possible.

## Hardware verification scripts

Create `scripts/verify_modbus_panel.py`:

- prints configured host/port for each module
- connects independently to each box's Ethernet-to-RS485 module (one TCP
  client per IP)
- reads DI from Box 1 and Box 2 - both respond as unit `0x01`, distinguished
  by IP, not by unit ID
- blinks every configured DO LED one by one, box by box
- prints detected button transitions for 30 seconds across both boxes
- exits non-zero if any configured box cannot be reached

Create `scripts/verify_audio_layers.py`:

- loads configured audio folder
- lists available instruments per song
- starts playback briefly if an output device is present
- can run in dry-run mode on development machine

Create `scripts/verify_dashboard.py`:

- calls `/health`
- calls `/api/status`
- calls `/api/layers`
- verifies the dashboard and API are served by the same Raspberry Pi backend in
  production mode
- optionally sends one remote press to a test layer

## Manual bench checklist

1. Power and wiring
   - 12V bus measured correctly, on each box.
   - DI COM connected to GND bus, on each box.
   - DGND connected to GND bus, on each box.
   - DO COM connected to +12V bus, on each box.
   - RS485 A/B wiring verified between each box's own Ethernet module and its
     own IO module (this wiring never crosses between Box 1 and Box 2).

2. Modbus addressing
   - Box 1 responds as unit `0x01` through its own Ethernet module at its own
     IP (e.g. `.50`).
   - Box 2 responds as unit `0x01` through its own Ethernet module at its own
     IP (e.g. `.51`).
   - Box 1 and Box 2 are independent Modbus TCP endpoints. Confirm there is no
     RS485 cable run between the two boxes.

3. Button input
   - Button 1 maps to instrument 1.
   - Button 8 maps to instrument 8.
   - Button 9 maps to instrument 9.
   - Button 16 maps to instrument 16.

4. LED output
   - Activating layer 1 turns button 1 LED on.
   - Deactivating layer 1 turns button 1 LED off.
   - Global timeout turns all LEDs off, on both boxes.
   - App shutdown turns all LEDs off best-effort, on both boxes.

5. Dashboard
   - Dashboard opens on LAN from the same Raspberry Pi as the backend API.
   - Physical press updates active layer display.
   - Remote press toggles the layer and LED.
   - Stopping the dashboard does not stop physical control.
   - Room title, layer labels, and visual style match the shared museum UI.

## Deployment steps

1. Prepare Raspberry Pi
   - Install Python dependencies from `requirements.txt`.
   - Copy project to target directory.
   - Copy or create production `config/config.json`, with both modules'
     `host` values set to the final IPs assigned to Box 1 and Box 2.
   - Copy audio files into `audio_files/`.
   - Confirm systemd `WorkingDirectory` matches the runtime/project directory
     so relative paths resolve predictably.

2. Build dashboard
   - From dashboard directory, run production build.
   - Copy build output into Python web static directory.
   - Confirm `index.html` is served by the Python app on the same RPi/port as
     the API.

3. Install service
   - Update systemd service to run the new entry point.
   - Keep watchdog support if used.
   - Set restart policy for process-level failure.

4. First boot verification
   - Check service status.
   - Check logs.
   - Run `/health`.
   - Press one physical button on Box 1 and one on Box 2.
   - Trigger one remote press if auth/network is ready.

5. Leave development escape hatches
   - Keep web-only input disabled by default, but available for bench tests.
   - Keep GPIO legacy handler only if needed for local testing.
   - Keep verification scripts in repo.

## Acceptance criteria

- Automated tests cover engine behavior without hardware.
- Modbus verification script confirms both DIN boxes independently, each at
  its own IP.
- One configured box offline at startup is reported as degraded and does not
  block the other configured box from reading inputs or writing LEDs.
- Dashboard verification confirms API is reachable from the same RPi backend.
- Production service starts on Raspberry Pi after reboot.
- Full bench test passes for both boxes before museum installation.

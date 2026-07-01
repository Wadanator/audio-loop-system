# Final programming TODO

This file is the short handoff checklist for a new chat or a later coding pass.
The detailed history stays in the numbered implementation docs, but this page
is the current programming backlog.

## Current known-good state

Status timestamp: `[documented] 2026-06-30 17:37:20 +02:00`

- Box 1 works with the real IO module at `192.168.0.200:4196`.
- Box 2 is configured at `192.168.0.201:4196` for instruments 9-16; hardware bench/full app verification is still pending.
- DI input and DO/LED output are implemented through Modbus, not Raspberry Pi GPIO.
- The app can run on Windows and Raspberry Pi as long as config/audio/device dependencies are available.
- The React dashboard exists, builds into `src/audio_loop/web/static/`, and shows the current room state.
- The web backend now runs on Flask and serves the same-origin API plus the built React app.
- The dashboard has a frontend login using `admin` / `admin12321`.
- The dashboard shell now uses the museum-system-style MUSEUM sidebar, admin footer, icon-only logout, and theme toggle.
- Remote sound press uses the same backend path as a physical button press.
- Each sound card now has a small Modbus connection dot: green means mapped module is communicating; red means module offline/not communicating or mapping missing.
- The Overview page warns when one or both configured Modbus modules are disconnected, but does not block audio, web remote press, or the still-connected module.
- Current practical audio target is max 16 sounds and up to about 3 minutes per song.

## Programming work still worth doing

1. Backend auth enforcement - `[implemented, verify on RPi] 2026-07-01`
   - Backend API routes under `/api/` now enforce Basic Auth when `web.auth_enabled` is true.
   - Frontend login validates credentials against the backend `/api/status` route instead of only checking locally.
   - Remote press routes and system command routes are protected before shared-network deployment.

2. System tab backend commands - `[implemented, verify on RPi] 2026-07-01`
   - The `Systém` tab now calls backend endpoints for:
     - restart backend service via `systemctl --user restart audio_looper.service`
     - reboot Raspberry Pi via `sudo /usr/sbin/reboot` or `/sbin/reboot`
     - shutdown Raspberry Pi via `sudo /usr/sbin/shutdown -h now` or `/sbin/shutdown -h now`
   - The UI uses a museum-system-style confirmation dialog before destructive commands.
   - System actions require both `web.auth_enabled` and `web.system_actions_enabled`.

3. Audio loader RAM optimization - `[pending]`
   - If `audio.max_loop_length` is set, load only the needed duration instead of reading the whole WAV and trimming afterward.
   - This matters for large source songs, even if the final target is around 3 minutes.
   - Keep all tracks in one song normalized to the same length and sample rate.

4. Raspberry Pi deployment files - `[partially implemented] 2026-07-01`
   - Finalize systemd service file for the new `main.py` entry point.
   - Confirm `WorkingDirectory` points to the project directory.
   - Confirm restart policy and logs are appropriate for the museum install.
   - Confirm dashboard static build is refreshed before deployment.
   - Installer now configures Raspberry Pi 3.5mm headphones output best-effort and sets system audio volume to 95% by default.
   - Installer now writes a narrow sudoers rule for dashboard reboot/shutdown commands.

5. Box 2 config support - `[implemented, config verified; hardware verification pending] 2026-06-30 16:37:02 +02:00`
   - `config.json` now contains `box_2` at `192.168.0.201:4196`.
   - Box 2 channels 1-8 are mapped to instruments 9-16.
   - `config.json` parses and `tests/smoke_refactor.py` passed.
   - Still run DI/DO bench tests and full app tests with both boxes.

6. Runtime safety hardening - `[partially implemented] 2026-06-30 17:37:20 +02:00`
   - Overview degraded Modbus warning is implemented for one/both disconnected configured boxes.
   - Repeated Modbus/pymodbus/LED error logging is rate-limited to protect the Raspberry Pi SD card during long outages.
   - Test what happens when the Modbus box disconnects while audio is playing.
   - Ensure web/dashboard failure does not stop physical buttons or audio.
   - Ensure shutdown flushes stats and turns LEDs off best-effort.

7. Documentation cleanup - `[partially updated] 2026-06-30 16:59:22 +02:00`
   - Some older implementation log lines still mention intermediate UI states such as INPUT/LED indicators.
   - Current state is now explicit: sound cards use one connection dot only, not separate INPUT/LED boxes.
   - Keep historical notes if useful, but make the current state obvious.
   - Keep this file updated whenever a final TODO is completed.

## Not urgent right now

- Server-Sent Events, WebSockets, or Socket.IO. One-second polling is acceptable for now and remains the safer fallback without extra dependencies.
- More UI pages for normal operators.
- Major architecture refactors. The code is already modular enough for the current phase.

## Suggested next coding order

1. Build and smoke-test the dashboard/backend package after the auth/system-action wiring.
2. Audio loader RAM optimization.
3. Raspberry Pi service/reboot/shutdown verification on hardware.
4. Runtime fault tests and fixes.
5. Box 2 DI/DO and full app verification on hardware.

## New-chat handoff prompt

Use this if continuing in a new Codex chat:

```text
Open C:/Users/Wajdy/Documents/Kodovanie/audio-loop-system/docs/implementation/06_FINAL_PROGRAMMING_TODO.md and continue from the highest-priority pending item. The current project intentionally has no old GPIO compatibility path. Keep updating the relevant .md file with implemented/verified status and timestamp after each change.
```

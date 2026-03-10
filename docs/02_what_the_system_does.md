# 02 – What the System Does

The **Audio Loop System** is an interactive music installation designed for **24/7 unattended operation** in public spaces such as museums, galleries, or exhibitions.

It lets visitors physically interact with music by pressing buttons, each of which adds or removes an instrument from a synchronized audio playback — creating a layered, evolving soundscape.

---

## Core Concept

The system plays a set of synchronized audio tracks (WAV files), each representing a single instrument (e.g. bass, drums, melody, strings). All tracks loop in perfect sync — they all start at position 0 and run at the same speed.

When a visitor presses a button, the corresponding instrument **fades in** to the mix. Pressing the button again **fades it out**. If no buttons are pressed for a configurable period, the system automatically goes silent and rotates to the next song.

---

## What Visitors Experience

1. The room is **silent** — the system is in idle state
2. A visitor presses a button → music starts from the beginning, the pressed instrument fades in
3. The visitor presses more buttons → more instruments join the mix, layering on top of each other
4. After ~60 seconds of no interaction, each instrument fades out automatically
5. After ~75 seconds of total inactivity, the music stops completely
6. The **next song** is automatically loaded for the next visitor

---

## Key Features

### 🎵 Synchronized Multi-Track Playback
- Plays up to **18 WAV tracks simultaneously**, all locked to the same position in the loop
- All tracks are the same length — the loop wraps seamlessly
- Volume for each track is independently controlled

### 🎛️ Smooth Fade In / Fade Out
- Each instrument fades in and out over a configurable duration (default: 2 seconds)
- Prevents jarring cuts between silence and full volume

### ⏱️ Dual Timeout System
- **Per-instrument timeout (default: 60s)** — each instrument auto-fades if its button isn't pressed again
- **Global timeout (default: 75s)** — if no button is pressed at all, the whole system stops
- Both timers reset on any button press, keeping the system active as long as someone is interacting

### 🔄 Song Rotation
- Multiple songs (in subfolders `song1/`, `song2/`, `song3/`, ...) can be configured
- After each session ends (global timeout), the system automatically advances to the next song
- The next visitor gets a fresh musical experience with a different arrangement

### 🛡️ 24/7 Reliability Features
- Automatic audio stream recovery if the stream drops (e.g. USB DAC reconnect)
- systemd watchdog — the OS automatically restarts the service if it freezes
- Restart limits — prevents infinite crash loops
- Graceful shutdown on SIGTERM/SIGINT — statistics saved before exit

### 📊 Statistics Dashboard
- Built-in web server accessible from any browser on the local network
- Shows how many times each instrument was activated
- Available at `http://<raspberry_pi_ip>:8000`
- JSON API at `http://<raspberry_pi_ip>:8000/stats`

### 💾 SD Card Optimization
- Logs are written to disk only on ERROR — normal INFO messages go to journald (no SD writes)
- Statistics are kept in RAM and written to disk only every 5 minutes
- Atomic file writes (write to `.tmp`, then rename) prevent corrupted stats files
- Log files rotate at 5MB with 2 backups — SD card usage stays bounded

---

## System Boundaries

| Parameter | Default | Configurable |
|-----------|---------|:---:|
| Max instruments | 18 | ❌ (hardware limit) |
| Instrument timeout | 60s | ✅ |
| Global timeout | 75s | ✅ |
| Fade duration | 2s | ✅ |
| Button cooldown | 1.5s | ✅ |
| Songs in rotation | 3 | ✅ |
| Stats save interval | 5 min | ✅ |
| Log file max size | 5 MB × 2 files | ✅ |

---

## Hardware Summary

The system runs on a **Raspberry Pi 4** with:
- Physical push buttons wired to GPIO pins (one per instrument)
- Audio output via 3.5mm jack, USB DAC, or HDMI
- Optional: network connection for the web statistics dashboard

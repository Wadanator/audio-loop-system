# 01 – Installation Guide: Fresh Raspberry Pi 4

This guide walks you through setting up the **Audio Loop System** on a brand-new Raspberry Pi 4 from scratch.

---

## Requirements

| Component | Specification |
|-----------|--------------|
| Hardware | Raspberry Pi 4 (any RAM variant) |
| OS | Raspberry Pi OS Lite (64-bit, Bookworm) |
| Audio output | 3.5mm jack, USB DAC, or HDMI to amplifier |
| Buttons | Up to 18 momentary push buttons wired to GPIO |
| Storage | Minimum 4GB microSD card (Class 10 / A1 recommended) |
| Power | Official RPi 4 USB-C power supply (5V/3A) |

---

## Step 1 – Flash the OS

1. Download **[Raspberry Pi Imager](https://www.raspberrypi.com/software/)** on your PC
2. Insert your microSD card
3. Choose **Raspberry Pi OS Lite (64-bit)** – no desktop needed
4. In **Advanced settings (⚙️)**:
   - Set hostname: `audiolooper`
   - Enable SSH
   - Set username/password (e.g. `pi` / your password)
   - Configure Wi-Fi if needed
5. Flash and insert the card into the Pi

---

## Step 2 – First Boot and SSH

```bash
ssh pi@audiolooper.local
# Or use the IP address if hostname doesn't resolve
```

Update the system:
```bash
sudo apt update && sudo apt upgrade -y
```

---

## Step 3 – Install System Dependencies

```bash
sudo apt install -y python3 python3-pip git python3-numpy python3-rpi.gpio
```

Install audio libraries:
```bash
sudo apt install -y libportaudio2 libsndfile1
```

---

## Step 4 – Clone the Project

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/audio-loop-system.git
cd audio-loop-system
```

> If you don't use Git, copy the project folder to the Pi via SCP:
> ```bash
> scp -r ./audio-loop-system pi@audiolooper.local:~/
> ```

---

## Step 5 – Run the Installer

The installer handles everything: Python packages, GPIO groups, logs directory, and systemd service.

```bash
cd ~/audio-loop-system
chmod +x install.sh
./install.sh
```

The installer will:
1. Install Python packages: `sounddevice`, `soundfile`, `sdnotify`
2. Add your user to `audio` and `gpio` groups
3. Create the `logs/` directory
4. Create and enable a **systemd user service** that starts on boot

---

## Step 6 – Add Your Audio Files

Place your WAV files inside `audio_files/`. The system supports **song rotation** – each song is a subfolder:

```
audio_files/
├── song1/
│   ├── 1.wav     ← instrument 1 (bass)
│   ├── 2.wav     ← instrument 2 (drums)
│   └── ...
├── song2/
│   ├── 1.wav
│   └── ...
└── song3/
    └── ...
```

**WAV file requirements:**
- Format: 16-bit or 32-bit PCM WAV
- Channels: Mono (stereo files are automatically downmixed)
- Sample rate: Any (48000 Hz recommended)
- All tracks in one song should be the **same length** for perfect synchronization

---

## Step 7 – Configure GPIO Pins

Edit `config.json` to match your button wiring:

```json
"raspberry_pi": {
  "button_pins": {
    "1": 4,    ← instrument 1 is wired to GPIO 4
    "2": 17,
    "3": 27,
    ...
  },
  "pull_up": true,
  "button_cooldown_seconds": 1.5
}
```

**Wiring (pull-up configuration):**
- Connect one leg of each button to the GPIO pin
- Connect the other leg to **GND**
- Internal pull-up resistors are used – no external resistors needed

---

## Step 8 – Set Audio Output

Find your audio device name:
```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

Set it in `config.json`:
```json
"audio": {
  "output_device": null
}
```
Leave `null` to use the system default, or set a device name/index from the list above.

For USB DAC or HDMI audio you may need to set the default ALSA device:
```bash
sudo nano /etc/asound.conf
```
```
defaults.pcm.card 1
defaults.ctl.card 1
```

---

## Step 9 – Start and Verify

```bash
# Check service status
systemctl --user status audio_looper.service

# View live logs
journalctl --user -u audio_looper.service -f

# Restart the service
systemctl --user restart audio_looper.service
```

Open the statistics dashboard in a browser:
```
http://audiolooper.local:8000
```

---

## Step 10 – Enable Auto-Start on Boot

The installer already does this, but to verify:
```bash
systemctl --user is-enabled audio_looper.service
# Should output: enabled
```

For the service to run **without a logged-in user**, linger must be enabled:
```bash
loginctl enable-linger pi
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| No audio output | Check `audio.output_device` in `config.json`, verify WAV files are in `audio_files/` |
| Buttons not responding | Check GPIO pin numbers in `config.json`, verify button wiring to GND |
| Service won't start | Run `journalctl --user -u audio_looper.service --no-pager` for error logs |
| Web dashboard not accessible | Verify Pi's IP address, check port 8000 is not blocked by firewall |
| Audio glitches | Increase `jack.buffer_size` in `config.json` (try 2048 or 4096) |
| Permission denied on GPIO | Run `sudo usermod -aG gpio pi` then reboot |

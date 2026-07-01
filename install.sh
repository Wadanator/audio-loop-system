#!/bin/bash
set -euo pipefail

SERVICE_NAME="audio_looper.service"
PROJECT_DIR="$(pwd)"
USER_NAME="$(whoami)"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME"

if [[ ! -f "main.py" || ! -f "config.json" || ! -f "requirements.txt" ]]; then
    echo "ERROR: run install.sh from the audio-loop-system project root."
    exit 1
fi

echo "Audio Loop System installer"
echo "Project: $PROJECT_DIR"
echo "User: $USER_NAME"

if command -v apt >/dev/null 2>&1; then
    sudo apt update
    sudo apt install -y python3 python3-pip python3-numpy libportaudio2 libsndfile1 alsa-utils
fi

if python3 -m pip install --user -r requirements.txt; then
    echo "Python dependencies installed."
else
    echo "Retrying pip install with --break-system-packages..."
    python3 -m pip install --user --break-system-packages -r requirements.txt
fi

sudo usermod -aG audio "$USER_NAME" || true

if [[ -f "scripts/configure_rpi_audio.sh" ]]; then
    AUDIO_LOOP_VOLUME_PERCENT="${AUDIO_LOOP_VOLUME_PERCENT:-95}" \
        bash scripts/configure_rpi_audio.sh --install
fi

mkdir -p logs "$SERVICE_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Audio Loop System
After=sound.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=120
StartLimitBurst=5

[Service]
Type=notify
ExecStartPre=/bin/bash $PROJECT_DIR/scripts/configure_rpi_audio.sh --volume-only
ExecStart=/usr/bin/python3 $PROJECT_DIR/main.py
WorkingDirectory=$PROJECT_DIR
Restart=on-failure
RestartSec=10
KillSignal=SIGTERM
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1
Environment=AUDIO_LOOP_VOLUME_PERCENT=${AUDIO_LOOP_VOLUME_PERCENT:-95}
WatchdogSec=60

[Install]
WantedBy=default.target
EOF

sudo loginctl enable-linger "$USER_NAME"
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

sleep 3
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "Service is running."
    echo "Status: systemctl --user status $SERVICE_NAME"
    echo "Logs: journalctl --user -u $SERVICE_NAME -f"
    echo "Web: http://$(hostname -I | awk '{print $1}'):8000"
else
    echo "ERROR: service failed to start."
    echo "Check: journalctl --user -u $SERVICE_NAME --no-pager -n 80"
    exit 1
fi

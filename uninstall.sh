#!/bin/bash
set -euo pipefail

SERVICE_NAME="audio_looper.service"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME"
USER_NAME="$(whoami)"

if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl --user stop "$SERVICE_NAME"
fi

if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl --user disable "$SERVICE_NAME"
fi

rm -f "$SERVICE_FILE"
systemctl --user daemon-reload
sudo loginctl disable-linger "$USER_NAME" || true

echo "Audio Loop System service removed. Project files and audio files were not deleted."
#!/bin/bash

# ==============================================================
# Audio Looper System - Simple Uninstaller
# ==============================================================

set -e

SERVICE_NAME="audio_looper.service"
USER_NAME="$(whoami)"

echo "🗑️  Audio Looper System - Uninstaller"
echo "===================================="

# Stop service
if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "🛑 Stopping service..."
    systemctl --user stop "$SERVICE_NAME"
fi

# Disable service
if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "❌ Disabling service..."
    systemctl --user disable "$SERVICE_NAME"
fi

# Remove service file
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME"
if [[ -f "$SERVICE_FILE" ]]; then
    echo "🗂️  Removing service file..."
    rm -f "$SERVICE_FILE"
fi

# Reload systemd
systemctl --user daemon-reload

# Disable linger
echo "⚡ Disabling user linger..."
sudo loginctl disable-linger "$USER_NAME"

echo ""
echo "✅ Audio Looper System has been uninstalled"
echo ""
echo "Note: Audio files and project files remain untouched"
echo "Python packages were not removed (they might be used by other projects)"
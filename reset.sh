#!/bin/bash
set -euo pipefail

SERVICE_NAME="audio_looper.service"

echo "Restarting $SERVICE_NAME..."
systemctl --user restart "$SERVICE_NAME"
sleep 2

if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "Service is active."
else
    echo "Service is not active. Recent logs:"
    journalctl --user -u "$SERVICE_NAME" --no-pager --lines=50
    exit 1
fi

journalctl --user -u "$SERVICE_NAME" --no-pager --lines=20
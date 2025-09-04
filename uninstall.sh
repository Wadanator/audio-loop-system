#!/bin/bash

# ==============================================================
# Audio Looper System - Uninstall User Systemd Service
# ==============================================================

set -e

SERVICE_NAME="audio_looper.service"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME"
USER_NAME="admin"

echo "🗑️ Spúšťam odinštaláciu Audio Looper System (user service)."

# -------------------------
# Krok 1: Zastavenie služby
# -------------------------
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo "⏹️ Zastavujem službu $SERVICE_NAME..."
    systemctl --user stop $SERVICE_NAME
fi

# -------------------------
# Krok 2: Zakázanie služby
# -------------------------
if systemctl --user is-enabled --quiet $SERVICE_NAME; then
    echo "🚫 Zakazujem službu $SERVICE_NAME..."
    systemctl --user disable $SERVICE_NAME
fi

# -------------------------
# Krok 3: Odstránenie súboru služby
# -------------------------
if [ -f "$SERVICE_FILE" ]; then
    echo "🗑️ Odstraňujem súbor služby $SERVICE_FILE..."
    rm -f "$SERVICE_FILE"
fi

# -------------------------
# Krok 4: Reload user systemd
# -------------------------
echo "🔄 Načítavam user systemd po zmene..."
systemctl --user daemon-reload

# -------------------------
# Krok 5: Odstránenie linger
# -------------------------
echo "❌ Zakazujem linger pre používateľa $USER_NAME..."
sudo loginctl disable-linger $USER_NAME

echo "✅ Odinštalácia dokončená. Služba Audio Looper System bola odstránená."

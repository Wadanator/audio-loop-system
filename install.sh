#!/bin/bash

# ==============================================================
# Audio Looper System - Robustná Inštalácia User Systemd Service
# ==============================================================

# Zastavenie pri akejkoľvek chybe
set -e

# Globálne premenné
SERVICE_NAME="audio_looper.service"
PROJECT_DIR="/home/admin/Documents/audio_loop_system"
SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME"
PYTHON_EXECUTABLE="/usr/bin/python3"
USER_NAME="admin"

echo "Spúšťam inštaláciu Audio Looper System (user service)."

# -------------------------
# Krok 1: Kontrola súborov a závislostí
# -------------------------
echo "Kontrolujem existenciu súborov..."

if [ ! -f "${PROJECT_DIR}/main.py" ]; then
    echo "CHYBA: Súbor main.py sa nenašiel na ceste ${PROJECT_DIR}/main.py"
    exit 1
fi

if [ ! -f "${PROJECT_DIR}/config.json" ]; then
    echo "CHYBA: Súbor config.json sa nenašiel"
    exit 1
fi

if [ ! -d "${PROJECT_DIR}/audio_files" ]; then
    echo "CHYBA: Adresár audio_files sa nenašiel"
    exit 1
fi

# Kontrola Python závislostí
echo "Kontrolujem Python závislosti..."
$PYTHON_EXECUTABLE -c "import sounddevice, soundfile, numpy, pygame" 2>/dev/null || {
    echo "CHYBA: Chýbajú Python závislosti. Nainštalujte ich príkazom:"
    echo "pip install sounddevice soundfile numpy pygame"
    exit 1
}

# -------------------------
# Krok 2: Overenie audio skupiny a oprávnení
# -------------------------
if ! groups $USER_NAME | grep -qw audio; then
    echo "Pridávam používateľa $USER_NAME do skupiny audio..."
    sudo usermod -aG audio $USER_NAME
    echo "UPOZORNENIE: Po pridaní do skupiny sa odporúča reštart systému."
fi

# Kontrola GPIO skupiny pre Raspberry Pi
if ! groups $USER_NAME | grep -qw gpio; then
    echo "Pridávam používateľa $USER_NAME do skupiny gpio..."
    sudo usermod -aG gpio $USER_NAME
fi

# -------------------------
# Krok 3: Vytvorenie logs adresára
# -------------------------
mkdir -p "${PROJECT_DIR}/logs"
chmod 755 "${PROJECT_DIR}/logs"

# -------------------------
# Krok 4: Vytvorenie robustnej user systemd služby
# -------------------------
echo "Vytváram user systemd službu: $SERVICE_NAME..."
mkdir -p "$(dirname "$SERVICE_FILE")"

tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Audio Looper System
Documentation=file://${PROJECT_DIR}/README.md
After=sound.target
Wants=sound.target

[Service]
Type=simple
ExecStart=${PYTHON_EXECUTABLE} ${PROJECT_DIR}/main.py
WorkingDirectory=${PROJECT_DIR}

# Robustný restart policy
Restart=always
RestartSec=5
StartLimitInterval=300
StartLimitBurst=5

# Process management
KillMode=mixed
KillSignal=SIGTERM
TimeoutStopSec=30

# Environment
Environment=DISPLAY=:0
Environment=PULSE_RUNTIME_PATH=/run/user/%i/pulse
Environment=PYTHONUNBUFFERED=1

# Security (optional - môžete zakomentovať ak spôsobuje problémy)
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=audio_looper

[Install]
WantedBy=default.target
EOF

echo "Súbor služby úspešne vytvorený: $SERVICE_FILE"

# -------------------------
# Krok 5: Povolenie linger pre boot autostart
# -------------------------
echo "Povolenie linger pre $USER_NAME (potrebné pre autostart pri boote)..."
sudo loginctl enable-linger $USER_NAME

# Overenie že linger je aktívny
if ! sudo loginctl show-user $USER_NAME | grep -q "Linger=yes"; then
    echo "UPOZORNENIE: Linger nebol úspešne nastavený. Služba sa nemusí spustiť pri boote."
fi

# -------------------------
# Krok 6: Zastavenie existujúcej služby (ak beží)
# -------------------------
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo "Zastavujem existujúcu službu..."
    systemctl --user stop $SERVICE_NAME
fi

# -------------------------
# Krok 7: Načítanie a povolenie user služby
# -------------------------
echo "Načítavam a povoľujem user službu..."
systemctl --user daemon-reload
systemctl --user enable $SERVICE_NAME

# -------------------------
# Krok 8: Spustenie služby
# -------------------------
echo "Spúšťam službu..."
systemctl --user start $SERVICE_NAME

# Krátka pauza na spustenie
sleep 3

# -------------------------
# Krok 9: Kontrola stavu a diagnostika
# -------------------------
echo "=== STATUS SLUŽBY ==="
if systemctl --user is-active --quiet $SERVICE_NAME; then
    echo "ÚSPECH: Služba je aktívna"
    systemctl --user status $SERVICE_NAME --no-pager --lines=10
else
    echo "CHYBA: Služba nie je aktívna!"
    echo ""
    echo "=== POSLEDNÉ LOGY ==="
    journalctl --user -u $SERVICE_NAME --no-pager --lines=20
    exit 1
fi

# -------------------------
# Krok 10: Užitočné príkazy
# -------------------------
echo ""
echo "=== INŠTALÁCIA DOKONČENÁ ==="
echo ""
echo "Užitočné príkazy na správu služby:"
echo "  Stav služby:        systemctl --user status $SERVICE_NAME"
echo "  Zastavenie služby:  systemctl --user stop $SERVICE_NAME"
echo "  Spustenie služby:   systemctl --user start $SERVICE_NAME"
echo "  Reštart služby:     systemctl --user restart $SERVICE_NAME"
echo "  Zobrazenie logov:   journalctl --user -u $SERVICE_NAME -f"
echo "  Sledovanie logov:   journalctl --user -u $SERVICE_NAME --follow"
echo ""
echo "Služba sa automaticky spustí pri každom boote a reštartuje sa pri crash."
echo "Pre úplné otestovanie autostart funkcionality odporúčame reštart systému."
#!/bin/bash

# ==============================================================
# Audio Looper System - Simple One-Click Installer
# ==============================================================

set -e

echo "🎵 Audio Looper System - Simple Installer"
echo "========================================"

# Detect current directory
CURRENT_DIR="$(pwd)"
PROJECT_NAME="audio-loop-system"
SERVICE_NAME="audio_looper.service"
USER_NAME="$(whoami)"

# Check if we're in the right directory
if [[ ! -f "main.py" ]] || [[ ! -f "config.json" ]]; then
    echo "❌ ERROR: main.py or config.json not found!"
    echo "Please run this script from the project directory containing main.py"
    exit 1
fi

echo "📁 Project directory: $CURRENT_DIR"
echo "👤 User: $USER_NAME"

# Step 1: Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."

# Try system packages first (Debian/Ubuntu way)
echo "Trying system packages first..."
sudo apt update
sudo apt install -y python3-pygame python3-numpy || echo "Some system packages not available, continuing..."

# For packages not available via apt, use pip with --break-system-packages
echo "Installing remaining packages via pip..."
if command -v pip3 &> /dev/null; then
    pip3 install --user --break-system-packages sounddevice soundfile sdnotify pymodbus || {
        echo "Trying alternative installation method..."
        python3 -m pip install --user --break-system-packages sounddevice soundfile sdnotify pymodbus
    }
else
    python3 -m pip install --user --break-system-packages sounddevice soundfile sdnotify pymodbus
fi

echo "✅ Python dependencies installed"

# Step 2: Add user to required groups
echo ""
echo "Adding user to audio group..."
sudo usermod -aG audio "$USER_NAME"

# Step 3: Create logs directory
echo ""
echo "📋 Creating logs directory..."
mkdir -p logs

# Step 4: Verify audio files directory
echo ""
echo "🎧 Checking audio files..."
if [[ ! -d "audio_files" ]]; then
    echo "⚠️  WARNING: audio_files directory not found!"
    echo "Creating empty audio_files directory..."
    mkdir -p audio_files
    echo "Please add your .wav files (1.wav, 2.wav, etc.) to the audio_files/ directory"
else
    WAV_COUNT=$(find audio_files -name "*.wav" | wc -l)
    echo "✅ Found $WAV_COUNT .wav files in audio_files/"
fi

# Step 5: Create systemd service
echo ""
echo "🔧 Creating systemd service..."

# Ensure user systemd directory exists
mkdir -p "$HOME/.config/systemd/user"

SERVICE_FILE="$HOME/.config/systemd/user/$SERVICE_NAME"

# Create service file
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Audio Looper System
# FIX P5: Závislosť aj na sieti (stats server), nielen zvuku
After=sound.target network.target
# FIX P5: Ochrana pred nekonečnou reštart slučkou
# Ak service padne viac ako 5x za 120s, systemd ho zastaví
StartLimitIntervalSec=120
StartLimitBurst=5

[Service]
# FIX P5: Type=notify umožňuje systemd watchdog a READY=1 signalizáciu
Type=notify
ExecStart=/usr/bin/python3 $CURRENT_DIR/main.py
WorkingDirectory=$CURRENT_DIR
Restart=on-failure
# FIX P5: Dlhší restart delay – dáva čas audiohardvéru na inicializáciu
RestartSec=10
KillSignal=SIGTERM
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1
# FIX P5: Watchdog – ak Python kód neodpovie do 60s, service sa reštartuje
# Vyžaduje sdnotify knižnicu (nainštalovanú vyššie) a WATCHDOG=1 ping z main.py
WatchdogSec=60

[Install]
WantedBy=default.target
EOF

echo "✅ Service file created: $SERVICE_FILE"

# Step 6: Enable linger for the user
echo ""
echo "⚡ Enabling user linger..."
sudo loginctl enable-linger "$USER_NAME"

# Step 7: Start and enable the service
echo ""
echo "🚀 Starting the service..."

# Stop service if already running
if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "Stopping existing service..."
    systemctl --user stop "$SERVICE_NAME"
fi

# Reload, enable and start
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user start "$SERVICE_NAME"

# Step 8: Wait and check status
sleep 3

echo ""
echo "📊 Checking service status..."
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "✅ SUCCESS: Audio Looper System is running!"
    echo ""
    echo "📱 Web interface: http://$(hostname -I | awk '{print $1}'):8000"
    echo "📋 Service status: systemctl --user status $SERVICE_NAME"
    echo "📋 View logs: journalctl --user -u $SERVICE_NAME -f"
    echo "🔄 Restart: systemctl --user restart $SERVICE_NAME"
    echo "🛑 Stop: systemctl --user stop $SERVICE_NAME"
else
    echo "❌ ERROR: Service failed to start!"
    echo "Check logs: journalctl --user -u $SERVICE_NAME --no-pager"
    exit 1
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Next steps:"
echo "1. Add your .wav files (1.wav, 2.wav, etc.) to audio_files/ directory"
echo "2. Configure modbus_panel in config.json for the external DIN IO module"
echo "3. Visit the web interface to see statistics"
echo ""
echo "The system will start automatically on boot."
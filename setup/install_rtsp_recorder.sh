#!/usr/bin/env bash
#===============================================================================
# Install RTSP Recorder Service
# This installs the separate recording service that captures the RTSP stream
#===============================================================================

set -e

echo "=== Installing RTSP Recorder Service ==="

# Check if running as root
if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Find rtsp_recorder.sh
if [[ -f "${PROJECT_ROOT}/rtsp_recorder.sh" ]]; then
    RECORDER_SRC="${PROJECT_ROOT}/rtsp_recorder.sh"
elif [[ -f "${SCRIPT_DIR}/rtsp_recorder.sh" ]]; then
    RECORDER_SRC="${SCRIPT_DIR}/rtsp_recorder.sh"
elif [[ -f "./rtsp_recorder.sh" ]]; then
    RECORDER_SRC="./rtsp_recorder.sh"
else
    echo "ERROR: rtsp_recorder.sh not found."
    echo "Searched: ${PROJECT_ROOT}/rtsp_recorder.sh, ${SCRIPT_DIR}/rtsp_recorder.sh, ./rtsp_recorder.sh"
    exit 1
fi

# Install ffmpeg if not present
if ! command -v ffmpeg &>/dev/null; then
    echo "Installing ffmpeg..."
    apt-get update
    apt-get install -y ffmpeg
fi

# Copy script
echo "Installing rtsp_recorder.sh from ${RECORDER_SRC}..."
cp "${RECORDER_SRC}" /usr/local/bin/rtsp_recorder.sh
chmod +x /usr/local/bin/rtsp_recorder.sh

# Remove BOM if present (Windows file)
sed -i '1s/^\xEF\xBB\xBF//' /usr/local/bin/rtsp_recorder.sh

# Convert line endings if needed
sed -i 's/\r$//' /usr/local/bin/rtsp_recorder.sh

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/rtsp-recorder.service << 'EOF'
[Unit]
Description=RTSP Stream Recorder (ffmpeg)
Documentation=https://github.com/yourusername/rtsp-recorder
After=network.target rpi-av-rtsp-recorder.service
Wants=rpi-av-rtsp-recorder.service

[Service]
Type=simple
User=root
EnvironmentFile=-/etc/rpi-cam/config.env
ExecStart=/usr/local/bin/rtsp_recorder.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/var/cache/rpi-cam /var/log/rpi-cam /etc/rpi-cam

[Install]
WantedBy=multi-user.target
EOF

# Ensure directories exist
mkdir -p /var/cache/rpi-cam/recordings
mkdir -p /var/log/rpi-cam
chmod 755 /var/cache/rpi-cam /var/cache/rpi-cam/recordings /var/log/rpi-cam

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable rtsp-recorder.service

echo ""
echo "=== Installation complete ==="
echo ""
echo "The recorder service is now enabled."
echo "It will start automatically after rpi-av-rtsp-recorder."
echo ""
echo "To start manually:"
echo "  sudo systemctl start rtsp-recorder"
echo ""
echo "To check status:"
echo "  sudo systemctl status rtsp-recorder"
echo ""
echo "To view logs:"
echo "  journalctl -u rtsp-recorder -f"
echo "  tail -f /var/log/rpi-cam/rtsp_recorder.log"
echo ""
echo "Configuration is in: /etc/rpi-cam/config.env"
echo "  - RECORD_ENABLE=yes|no"
echo "  - RECORD_DIR=/var/cache/rpi-cam/recordings"
echo "  - SEGMENT_SECONDS=300"
echo "  - MIN_FREE_DISK_MB=1000 (0=disabled)"
echo ""

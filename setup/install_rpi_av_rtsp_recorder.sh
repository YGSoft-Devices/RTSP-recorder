#!/usr/bin/env bash
#===============================================================================
# File: install_rpi_av_rtsp_recorder.sh
# Purpose:
#   - Install the runtime script to /usr/local/bin
#   - Create a systemd service to auto-start on boot
#   - Create config file in /etc/rpi-cam
#   - Setup basic logrotate for the service log
#
# Version: 2.0.1
# Changelog:
#   - 2.0.0: Updated for v2 recorder with better USB camera support
#   - 1.0.0: Initial release
#===============================================================================

set -euo pipefail

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Look for main script in multiple locations
if [[ -f "${PROJECT_ROOT}/rpi_av_rtsp_recorder.sh" ]]; then
  SCRIPT_SRC="${PROJECT_ROOT}/rpi_av_rtsp_recorder.sh"
elif [[ -f "${SCRIPT_DIR}/rpi_av_rtsp_recorder.sh" ]]; then
  SCRIPT_SRC="${SCRIPT_DIR}/rpi_av_rtsp_recorder.sh"
elif [[ -f "./rpi_av_rtsp_recorder.sh" ]]; then
  SCRIPT_SRC="./rpi_av_rtsp_recorder.sh"
else
  SCRIPT_SRC=""
fi

# Locate Python CSI Server script
if [[ -f "${PROJECT_ROOT}/rpi_csi_rtsp_server.py" ]]; then
  PY_SCRIPT_SRC="${PROJECT_ROOT}/rpi_csi_rtsp_server.py"
elif [[ -f "${SCRIPT_DIR}/rpi_csi_rtsp_server.py" ]]; then
  PY_SCRIPT_SRC="${SCRIPT_DIR}/rpi_csi_rtsp_server.py"
elif [[ -f "./rpi_csi_rtsp_server.py" ]]; then
  PY_SCRIPT_SRC="./rpi_csi_rtsp_server.py"
else
  PY_SCRIPT_SRC=""
fi

SCRIPT_DST="/usr/local/bin/rpi_av_rtsp_recorder.sh"
PY_SCRIPT_DST="/usr/local/bin/rpi_csi_rtsp_server.py"
CONFIG_DIR="/etc/rpi-cam"
CONFIG_FILE="${CONFIG_DIR}/recorder.conf"

SERVICE_NAME="rpi-av-rtsp-recorder"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

LOGROTATE_FILE="/etc/logrotate.d/${SERVICE_NAME}"

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run as root: sudo $0"
    exit 1
  fi
}

need_root

if [[ -z "$SCRIPT_SRC" ]] || [[ ! -f "$SCRIPT_SRC" ]]; then
  echo "ERROR: rpi_av_rtsp_recorder.sh not found."
  echo "Searched: ${PROJECT_ROOT}/rpi_av_rtsp_recorder.sh, ${SCRIPT_DIR}/rpi_av_rtsp_recorder.sh, ./rpi_av_rtsp_recorder.sh"
  echo ""
  echo "Make sure the script file is present in the setup directory."
  exit 1
fi

echo "[*] Using source: ${SCRIPT_SRC}"

echo "[*] Installing runtime script to ${SCRIPT_DST}"
install -m 0755 "${SCRIPT_SRC}" "${SCRIPT_DST}"

# Remove BOM if present (Windows file)
sed -i '1s/^\xEF\xBB\xBF//' "${SCRIPT_DST}"
# Convert line endings if needed
sed -i 's/\r$//' "${SCRIPT_DST}"

# ----------------------------------------------------
# Install CSI Native Server (Python)
# ----------------------------------------------------
# Look for rpi_csi_rtsp_server.py
CSI_SRC=""
if [[ -f "${PROJECT_ROOT}/rpi_csi_rtsp_server.py" ]]; then
  CSI_SRC="${PROJECT_ROOT}/rpi_csi_rtsp_server.py"
elif [[ -f "${SCRIPT_DIR}/../rpi_csi_rtsp_server.py" ]]; then
  CSI_SRC="${SCRIPT_DIR}/../rpi_csi_rtsp_server.py"
fi

if [[ -n "$CSI_SRC" && -f "$CSI_SRC" ]]; then
    CSI_DST="/usr/local/bin/rpi_csi_rtsp_server.py"
    echo "[*] Installing CSI Server to ${CSI_DST}"
    install -m 0755 "${CSI_SRC}" "${CSI_DST}"
    sed -i '1s/^\xEF\xBB\xBF//' "${CSI_DST}"
    sed -i 's/\r$//' "${CSI_DST}"
else
    echo "[!] WARNING: rpi_csi_rtsp_server.py not found. CSI Mode will not work."
fi

echo "[*] Creating folders"
mkdir -p /var/cache/rpi-cam/recordings /var/log/rpi-cam "${CONFIG_DIR}"
chmod 755 /var/cache/rpi-cam /var/cache/rpi-cam/recordings /var/log/rpi-cam "${CONFIG_DIR}" || true

# Create default config if it doesn't exist
if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "[*] Creating default config: ${CONFIG_FILE}"
  cat > "${CONFIG_FILE}" <<'EOFCONF'
# Configuration du serveur RTSP
# Modifiez ce fichier pour personnaliser les paramètres

# RTSP Server
RTSP_PORT=8554
RTSP_PATH=stream

# Video settings
# Avec l'encodeur HARDWARE (v4l2h264enc), on peut utiliser une bonne résolution
# Si v4l2h264enc n'est pas disponible, le système utilisera x264enc (logiciel)
# IMPORTANT: Sur Pi 3B+ l'encodeur hardware (v4l2h264enc) peut être cassé
# Dans ce cas, x264enc (software) sera utilisé automatiquement
# Valeurs par défaut SÉCURITAIRES pour x264enc (software):
VIDEO_WIDTH=640
VIDEO_HEIGHT=480
VIDEO_FPS=15
VIDEO_DEVICE=/dev/video0

# Camera mode: auto, yes, no
CSI_ENABLE=auto
USB_ENABLE=auto

# Audio settings
AUDIO_ENABLE=auto
AUDIO_DEVICE=auto
AUDIO_RATE=48000
AUDIO_CHANNELS=1
AUDIO_BITRATE_KBPS=64

# H264 encoding (utilisé seulement si encodeur SOFTWARE - x264enc)
# Ignoré si encodeur HARDWARE (v4l2h264enc) fonctionne
# Bitrate réduit pour Pi 3B+ avec x264enc
H264_BITRATE_KBPS=1200
H264_KEYINT=30

# Recording
RECORD_ENABLE=yes
RECORD_DIR=/var/cache/rpi-cam/recordings
SEGMENT_SECONDS=300
MIN_FREE_DISK_MB=1000

# Debug
GST_DEBUG_LEVEL=2
EOFCONF
  chmod 644 "${CONFIG_FILE}"
else
  echo "[*] Config exists: ${CONFIG_FILE} (keeping current)"
fi

echo "[*] Writing systemd service: ${SERVICE_FILE}"
cat > "${SERVICE_FILE}" <<'EOF'
[Unit]
Description=Raspberry Pi RTSP (GStreamer) + Segmented Recording
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root

# Config is loaded from /etc/rpi-cam/recorder.conf
# Environment variables can override config file settings

# IMPORTANT: Le script teste automatiquement si v4l2h264enc fonctionne
# S'il est cassé, il bascule sur x264enc avec les paramètres optimisés
# Les valeurs par défaut (640x480@15fps) conviennent à x264enc
# Si hardware fonctionne, vous pouvez augmenter: 1280x720@20fps

ExecStart=/usr/local/bin/rpi_av_rtsp_recorder.sh
Restart=always
RestartSec=5
StandardOutput=append:/var/log/rpi-cam/rpi_av_rtsp_recorder.log
StandardError=append:/var/log/rpi-cam/rpi_av_rtsp_recorder.log

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "[*] Writing logrotate config: ${LOGROTATE_FILE}"
cat > "${LOGROTATE_FILE}" <<'EOF'
/var/log/rpi-cam/rpi_av_rtsp_recorder.log {
  daily
  rotate 14
  compress
  delaycompress
  missingok
  notifempty
  copytruncate
}
EOF

echo "[*] Reloading systemd and enabling service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

cat << 'EOF'

================================================================================
 Installation terminée !
================================================================================

Configuration:
  /etc/rpi-cam/recorder.conf   (paramètres RTSP/vidéo/audio)

Commandes utiles:
  # Tester la configuration avant de démarrer
  sudo /usr/local/bin/test_gstreamer_rtsp.sh

  # Démarrer le service
  sudo systemctl start rpi-av-rtsp-recorder

  # Vérifier le status
  sudo systemctl status rpi-av-rtsp-recorder

  # Voir les logs
  tail -f /var/log/rpi-cam/rpi_av_rtsp_recorder.log

  # Arrêter le service
  sudo systemctl stop rpi-av-rtsp-recorder

URL RTSP:
  rtsp://<IP_DU_PI>:8554/stream

Enregistrements:
  ls -lh /var/cache/rpi-cam/recordings/

Notes pour Pi 3B+:
  - Utilisez 640x480@15fps pour l'encodage H264 logiciel
  - Les caméras MJPEG sont recommandées (moins de charge CPU)
  - Éditez /etc/rpi-cam/recorder.conf pour ajuster

================================================================================

EOF

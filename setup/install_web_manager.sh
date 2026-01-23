#!/usr/bin/env bash
#===============================================================================
# File: install_web_manager.sh
# Purpose: Install RTSP Recorder Web Management Interface
# Target: Raspberry Pi OS Trixie (64-bit) - basé sur Debian 13
# Version: 2.4.1
#
# NOTE: Ce script installe UNIQUEMENT l'interface web (Flask/Gunicorn)
#       Les autres composants (RTSP, recorder, watchdog) sont installés
#       par leurs scripts respectifs via install.sh
#===============================================================================

set -uo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Platform info (always Raspberry Pi)
PLATFORM_NAME="Raspberry Pi"
PI_MODEL=""

get_pi_model() {
    if [[ -f /proc/device-tree/model ]]; then
        PI_MODEL="$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo "Raspberry Pi")"
    else
        PI_MODEL="Raspberry Pi"
    fi
}

get_pi_model
log_info "Plateforme: $PI_MODEL"

# Check if running as root
if [[ "${EUID}" -ne 0 ]]; then
    log_error "Ce script doit être exécuté en tant que root"
    echo "Usage: sudo $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="/opt/rpi-cam-webmanager"
SERVICE_NAME="rpi-cam-webmanager"
CONFIG_DIR="/etc/rpi-cam"
LOG_DIR="/var/log/rpi-cam"
RECORD_DIR="/var/cache/rpi-cam/recordings"
WEB_USER="www-data"
WEB_PORT=5000

log_info "======================================"
log_info "Installation de l'interface web RTSP"
log_info "Plateforme: $PI_MODEL"
log_info "OS: Raspberry Pi OS Trixie (64-bit)"
log_info "======================================"

# Update package list (soft fail - may already be updated)
log_info "Mise à jour des paquets..."
apt-get update -qq 2>/dev/null || log_warn "Impossible de mettre à jour les paquets (peut être déjà fait)"

# Wait for any dpkg locks (common after large installs like GStreamer)
log_info "Attente de la libération des locks dpkg..."
wait_count=0
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || fuser /var/lib/apt/lists/lock >/dev/null 2>&1; do
    wait_count=$((wait_count + 1))
    if [[ $wait_count -gt 60 ]]; then
        log_warn "Timeout attente lock dpkg après 60s, tentative de nettoyage"
        rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock /var/cache/apt/archives/lock 2>/dev/null
        dpkg --configure -a 2>/dev/null || true
        break
    fi
    sleep 1
done
log_success "Locks dpkg disponibles"

# Install Python and dependencies (with retry logic for Trixie/Debian 13)
log_info "Installation de Python et des dépendances..."
install_success=false
for attempt in 1 2 3; do
    if apt-get install -y python3 python3-pip python3-venv 2>&1; then
        install_success=true
        break
    fi
    log_warn "Tentative $attempt échouée, dpkg --configure -a et retry..."
    dpkg --configure -a 2>/dev/null || true
    apt-get install -f -y 2>/dev/null || true
    sleep 2
done

if ! $install_success; then
    # Check if packages are actually installed despite error
    if command -v python3 &>/dev/null && dpkg -l python3-pip 2>/dev/null | grep -q "^ii"; then
        log_warn "apt-get retourne erreur mais Python est déjà installé, on continue"
    else
        log_error "Impossible d'installer Python après 3 tentatives"
        exit 1
    fi
fi
log_success "Python et dépendances installés"

# Create directories
log_info "Création des répertoires..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$RECORD_DIR"

# Check if web-manager directory exists (search multiple locations)
WEB_MANAGER_SRC=""
if [[ -d "$PROJECT_ROOT/web-manager" ]]; then
    WEB_MANAGER_SRC="$PROJECT_ROOT/web-manager"
elif [[ -d "$SCRIPT_DIR/web-manager" ]]; then
    WEB_MANAGER_SRC="$SCRIPT_DIR/web-manager"
elif [[ -d "$SCRIPT_DIR/../web-manager" ]]; then
    # If SCRIPT_DIR is inside a temp folder but web-manager is sibling
    WEB_MANAGER_SRC="$SCRIPT_DIR/../web-manager"
elif [[ -d "./web-manager" ]]; then
    WEB_MANAGER_SRC="./web-manager"
fi

if [[ -z "$WEB_MANAGER_SRC" ]] || [[ ! -d "$WEB_MANAGER_SRC" ]]; then
    log_error "Le dossier web-manager est introuvable"
    log_error "Emplacements vérifiés:"
    log_error "  - $PROJECT_ROOT/web-manager"
    log_error "  - $SCRIPT_DIR/web-manager"
    log_error "  - $SCRIPT_DIR/../web-manager"
    log_error "  - ./web-manager"
    log_error "Assurez-vous que la structure du projet est complète."
    exit 1
fi

# Copy web application files
log_info "Copie des fichiers de l'application depuis ${WEB_MANAGER_SRC}..."
cp -r "${WEB_MANAGER_SRC}/"* "$INSTALL_DIR/"

# Copy VERSION file from project root
VERSION_FILE=""
if [[ -f "$PROJECT_ROOT/VERSION" ]]; then
    VERSION_FILE="$PROJECT_ROOT/VERSION"
elif [[ -f "$SCRIPT_DIR/../VERSION" ]]; then
    VERSION_FILE="$SCRIPT_DIR/../VERSION"
fi

if [[ -n "$VERSION_FILE" ]]; then
    log_info "Copie du fichier VERSION..."
    cp "$VERSION_FILE" "$INSTALL_DIR/VERSION"
else
    log_warn "Fichier VERSION non trouvé, création avec version par défaut"
    echo "2.30.45" > "$INSTALL_DIR/VERSION"
fi

# Create Python virtual environment
log_info "Création de l'environnement virtuel Python..."
python3 -m venv "$INSTALL_DIR/venv" || {
    log_error "Impossible de créer l'environnement virtuel Python"
    exit 1
}

# Create requirements.txt if not exists
if [[ ! -f "$INSTALL_DIR/requirements.txt" ]]; then
    log_info "Création du fichier requirements.txt..."
    cat > "$INSTALL_DIR/requirements.txt" << 'EOF'
Flask>=2.3.0
gunicorn>=21.0.0
EOF
fi

# Install Python dependencies
log_info "Installation des dépendances Python..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip 2>/dev/null || true
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" || {
    log_error "Impossible d'installer les dépendances Python"
    exit 1
}

# Create default config if not exists
if [[ ! -f "$CONFIG_DIR/config.env" ]]; then
    log_info "Création de la configuration par défaut..."
    cat > "$CONFIG_DIR/config.env" << 'EOF'
# RTSP Recorder Configuration
# Generated by install_web_manager.sh

# RTSP Settings
RTSP_PORT="8554"
RTSP_PATH="stream"

# Video Settings
VIDEO_WIDTH="1280"
VIDEO_HEIGHT="960"
VIDEO_FPS="20"
VIDEO_DEVICE="/dev/video0"
CSI_ENABLE="auto"
USB_ENABLE="auto"

# Recording Settings
RECORD_ENABLE="yes"
RECORD_DIR="/var/cache/rpi-cam/recordings"
SEGMENT_SECONDS="300"
MIN_FREE_DISK_MB="1000"

# Audio Settings
AUDIO_ENABLE="auto"
AUDIO_RATE="48000"
AUDIO_CHANNELS="1"
AUDIO_BITRATE_KBPS="64"
AUDIO_DEVICE="auto"

# Advanced Settings
GST_DEBUG_LEVEL="2"
LOG_DIR="/var/log/rpi-cam"
LOW_LATENCY="1"
EOF
fi

# Create default WiFi failover config if not exists
if [[ ! -f "$CONFIG_DIR/wifi_failover.json" ]]; then
    log_info "Création de la configuration WiFi failover par défaut..."
    cat > "$CONFIG_DIR/wifi_failover.json" << 'EOF'
{
  "hardware_failover_enabled": true,
  "network_failover_enabled": false,
  "primary_interface": "wlan1",
  "secondary_interface": "wlan0",
  "primary_ssid": "",
  "secondary_ssid": "",
  "primary_password": "",
  "secondary_password": "",
  "ip_mode": "dhcp",
  "static_ip": "",
  "gateway": "",
  "dns": "8.8.8.8",
  "check_interval": 30
}
EOF
    chmod 664 "$CONFIG_DIR/wifi_failover.json"
    chown root:$WEB_USER "$CONFIG_DIR/wifi_failover.json" 2>/dev/null || true
fi

# Set permissions
log_info "Configuration des permissions..."
chown -R root:$WEB_USER "$INSTALL_DIR" 2>/dev/null || chown -R root:root "$INSTALL_DIR"
chmod -R 750 "$INSTALL_DIR"
chown -R root:$WEB_USER "$CONFIG_DIR" 2>/dev/null || chown -R root:root "$CONFIG_DIR"
chmod 775 "$CONFIG_DIR"
chmod 664 "$CONFIG_DIR/config.env"
chmod 755 "$LOG_DIR"
chmod 755 "$RECORD_DIR"

# Create systemd service for web manager
log_info "Création du service systemd..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=RTSP Recorder Web Manager
After=network.target
Documentation=https://github.com/your-repo/rtsp-recorder

[Service]
Type=simple
User=root
Group=$WEB_USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$INSTALL_DIR/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:$WEB_PORT --timeout 120 app:app
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# NOTE: Le script RTSP recorder et son service sont installés par install_rpi_av_rtsp_recorder.sh
# On ne les duplique pas ici pour éviter les conflits

# Reload systemd and enable services
log_info "Activation des services..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" 2>/dev/null || true
systemctl restart "$SERVICE_NAME" || {
    log_warn "Impossible de démarrer le service web manager"
    log_info "Vérifiez avec: journalctl -u $SERVICE_NAME -f"
}

# Check if service is running
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log_success "Service web manager démarré avec succès"
else
    log_warn "Le service web manager n'est pas actif"
    log_info "Essayez: systemctl status $SERVICE_NAME"
fi

# Get IP address for display
IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
log_success "======================================"
log_success "Installation terminée !"
log_success "======================================"
echo ""
log_info "Plateforme: $PI_MODEL"
log_info "Interface web accessible à:"
echo -e "  ${GREEN}http://${IP_ADDR}:${WEB_PORT}${NC}"
echo ""
log_info "Commandes utiles:"
echo "  - Voir les logs: journalctl -u $SERVICE_NAME -f"
echo "  - Redémarrer: sudo systemctl restart $SERVICE_NAME"
echo "  - Stopper: sudo systemctl stop $SERVICE_NAME"
echo ""

log_info "Fonctionnalités Raspberry Pi:"
echo "  - Contrôle des LEDs: Disponible"
echo "  - Mémoire GPU: Configurable"
echo "  - Caméra CSI: Détection automatique"
echo "  - Caméra USB: Détection automatique"
echo "  - Configuration WiFi: Disponible"
echo ""

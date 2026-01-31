#!/usr/bin/env bash
#
# install_onvif_server.sh - Install ONVIF Server for RTSP Cameras
# Version: 1.0.1
#
# Target: Raspberry Pi OS Trixie (64-bit)
#

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_NAME="install_onvif_server.sh"
VERSION="1.0.0"

# Installation paths
INSTALL_DIR="/opt/rpi-cam-webmanager/onvif-server"
CONFIG_DIR="/etc/rpi-cam"
SERVICE_FILE="/etc/systemd/system/rpi-cam-onvif.service"
CONFIG_FILE="${CONFIG_DIR}/onvif.conf"

# Default configuration
DEFAULT_PORT=8080
DEFAULT_NAME="RPI-CAM"
DEFAULT_RTSP_PORT=8554
DEFAULT_RTSP_PATH="/stream"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# Logging Functions
# ============================================================================

log() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_err() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

die() {
    log_err "$*"
    exit 1
}

# ============================================================================
# Helper Functions
# ============================================================================

check_root() {
    if [[ $EUID -ne 0 ]]; then
        die "This script must be run as root (use sudo)"
    fi
}

get_script_dir() {
    cd "$(dirname "${BASH_SOURCE[0]}")" && pwd
}

# ============================================================================
# Installation Functions
# ============================================================================

install_dependencies() {
    log "Checking Python dependencies..."
    
    # Python 3 should already be installed
    if ! command -v python3 &>/dev/null; then
        die "Python 3 is required but not installed"
    fi
    
    log "Python $(python3 --version) found"

    # GPIO tools for relay outputs (optional)
    if command -v apt-get &>/dev/null; then
        log "Installing gpiod (GPIO tools) if available..."
        apt-get install -y gpiod >/dev/null 2>&1 || log_warn "gpiod not installed (relay may fallback to sysfs)"
    fi
}

install_onvif_server() {
    local script_dir
    script_dir="$(get_script_dir)"
    local source_dir=""
    
    # Search for onvif-server in multiple locations
    if [[ -f "${script_dir}/../onvif-server/onvif_server.py" ]]; then
        source_dir="${script_dir}/../onvif-server"
    elif [[ -f "${script_dir}/onvif-server/onvif_server.py" ]]; then
        source_dir="${script_dir}/onvif-server"
    elif [[ -f "./onvif-server/onvif_server.py" ]]; then
        source_dir="./onvif-server"
    elif [[ -f "${script_dir}/onvif_server.py" ]]; then
        # Script is directly in setup folder
        source_dir="${script_dir}"
    fi
    
    log "Installing ONVIF server to ${INSTALL_DIR}..."
    
    # Create installation directory
    mkdir -p "${INSTALL_DIR}"
    
    # Copy Python script
    if [[ -n "$source_dir" ]] && [[ -f "${source_dir}/onvif_server.py" ]]; then
        cp "${source_dir}/onvif_server.py" "${INSTALL_DIR}/"
        chmod 755 "${INSTALL_DIR}/onvif_server.py"
        log "Installed onvif_server.py from ${source_dir}"
    else
        die "Source file not found. Searched: ${script_dir}/../onvif-server, ${script_dir}/onvif-server, ./onvif-server, ${script_dir}"
    fi
}

create_default_config() {
    log "Creating configuration directory..."
    mkdir -p "${CONFIG_DIR}"
    
    if [[ ! -f "${CONFIG_FILE}" ]]; then
        log "Creating default configuration..."
        cat > "${CONFIG_FILE}" << EOF
{
    "enabled": false,
    "port": ${DEFAULT_PORT},
    "name": "${DEFAULT_NAME}",
    "username": "",
    "password": "",
    "rtsp_port": ${DEFAULT_RTSP_PORT},
    "rtsp_path": "${DEFAULT_RTSP_PATH}"
}
EOF
        chmod 600 "${CONFIG_FILE}"
        log "Created ${CONFIG_FILE}"
    else
        log "Configuration already exists: ${CONFIG_FILE}"
    fi
}

install_systemd_service() {
    local script_dir
    script_dir="$(get_script_dir)"
    
    log "Installing systemd service..."
    
    if [[ -f "${script_dir}/rpi-cam-onvif.service" ]]; then
        cp "${script_dir}/rpi-cam-onvif.service" "${SERVICE_FILE}"
    else
        # Create service file inline
        cat > "${SERVICE_FILE}" << 'EOF'
[Unit]
Description=ONVIF Server for RTSP Cameras
Documentation=https://github.com/sn8k/RTSP-Full
After=network-online.target rpi-av-rtsp-recorder.service
Wants=network-online.target
PartOf=rpi-av-rtsp-recorder.service

[Service]
Type=simple
User=root
Group=root
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 /opt/rpi-cam-webmanager/onvif-server/onvif_server.py
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=300
StartLimitBurst=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rpi-cam-onvif
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/etc/rpi-cam /tmp
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
    fi
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable and start the service by default
    systemctl enable rpi-cam-onvif
    systemctl start rpi-cam-onvif
    
    log "Systemd service installed and enabled: rpi-cam-onvif"
}

# ============================================================================
# Status/Check Functions
# ============================================================================

check_installation() {
    log "Checking ONVIF server installation..."
    
    local status=0
    
    # Check Python script
    if [[ -f "${INSTALL_DIR}/onvif_server.py" ]]; then
        log "  ✓ ONVIF server script installed"
    else
        log_err "  ✗ ONVIF server script not found"
        status=1
    fi
    
    # Check configuration
    if [[ -f "${CONFIG_FILE}" ]]; then
        log "  ✓ Configuration file exists"
    else
        log_warn "  - Configuration file not found (will be created)"
    fi
    
    # Check systemd service
    if [[ -f "${SERVICE_FILE}" ]]; then
        log "  ✓ Systemd service installed"
        
        if systemctl is-enabled --quiet rpi-cam-onvif 2>/dev/null; then
            log "  ✓ Service is enabled"
        else
            log "  - Service is not enabled"
        fi
        
        if systemctl is-active --quiet rpi-cam-onvif 2>/dev/null; then
            log "  ✓ Service is running"
        else
            log "  - Service is not running"
        fi
    else
        log_warn "  - Systemd service not installed"
    fi
    
    return $status
}

show_status() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   ONVIF Server Status${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    
    check_installation || true
    
    echo ""
    
    # Show configuration
    if [[ -f "${CONFIG_FILE}" ]]; then
        log "Configuration (${CONFIG_FILE}):"
        python3 -c "
import json
with open('${CONFIG_FILE}', 'r') as f:
    cfg = json.load(f)
    print(f'  Enabled: {cfg.get(\"enabled\", False)}')
    print(f'  Port: {cfg.get(\"port\", 8080)}')
    print(f'  Name: {cfg.get(\"name\", \"RPI-CAM\")}')
    print(f'  Username: {cfg.get(\"username\", \"\") or \"(none)\"}')
    print(f'  Password: {\"***\" if cfg.get(\"password\") else \"(none)\"}')
    print(f'  RTSP Port: {cfg.get(\"rtsp_port\", 8554)}')
    print(f'  RTSP Path: {cfg.get(\"rtsp_path\", \"/stream\")}')
" 2>/dev/null || log_warn "Could not read configuration"
    fi
    
    echo ""
}

# ============================================================================
# Uninstall Function
# ============================================================================

uninstall() {
    log "Uninstalling ONVIF server..."
    
    # Stop and disable service
    if systemctl is-active --quiet rpi-cam-onvif 2>/dev/null; then
        log "Stopping service..."
        systemctl stop rpi-cam-onvif
    fi
    
    if systemctl is-enabled --quiet rpi-cam-onvif 2>/dev/null; then
        log "Disabling service..."
        systemctl disable rpi-cam-onvif
    fi
    
    # Remove service file
    if [[ -f "${SERVICE_FILE}" ]]; then
        log "Removing service file..."
        rm -f "${SERVICE_FILE}"
        systemctl daemon-reload
    fi
    
    # Remove installation
    if [[ -d "${INSTALL_DIR}" ]]; then
        log "Removing installation directory..."
        rm -rf "${INSTALL_DIR}"
    fi
    
    # Keep configuration (user data)
    if [[ -f "${CONFIG_FILE}" ]]; then
        log_warn "Configuration file preserved: ${CONFIG_FILE}"
        log_warn "Remove manually if needed: sudo rm ${CONFIG_FILE}"
    fi
    
    log "ONVIF server uninstalled"
}

# ============================================================================
# Main
# ============================================================================

show_help() {
    cat << EOF
${SCRIPT_NAME} v${VERSION} - Install ONVIF Server for RTSP Cameras

Usage: sudo $0 [command]

Commands:
  install     Install ONVIF server (default)
  uninstall   Remove ONVIF server
  status      Show installation status
  check       Check if installation is complete
  help        Show this help message

Examples:
  sudo $0                 # Install ONVIF server
  sudo $0 install         # Install ONVIF server
  sudo $0 status          # Show status
  sudo $0 uninstall       # Remove ONVIF server
EOF
}

main() {
    local command="${1:-install}"
    
    case "$command" in
        install)
            check_root
            log "Installing ONVIF Server v${VERSION}..."
            echo ""
            install_dependencies
            install_onvif_server
            create_default_config
            install_systemd_service
            echo ""
            log "Installation complete! ONVIF service is enabled and running."
            echo ""
            show_status
            ;;
        uninstall)
            check_root
            uninstall
            ;;
        status)
            show_status
            ;;
        check)
            check_installation
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_err "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"

#!/usr/bin/env bash
#===============================================================================
# Install RTSP Watchdog and Camera Recovery
# Ensures high availability of the streaming service
#===============================================================================

set -euo pipefail

#---------------------------
# Configuration
#---------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# File locations - search in multiple places
if [[ -f "$PROJECT_ROOT/rtsp_watchdog.sh" ]]; then
    WATCHDOG_SCRIPT="$PROJECT_ROOT/rtsp_watchdog.sh"
elif [[ -f "$SCRIPT_DIR/rtsp_watchdog.sh" ]]; then
    WATCHDOG_SCRIPT="$SCRIPT_DIR/rtsp_watchdog.sh"
elif [[ -f "./rtsp_watchdog.sh" ]]; then
    WATCHDOG_SCRIPT="./rtsp_watchdog.sh"
else
    WATCHDOG_SCRIPT=""
fi

WATCHDOG_SERVICE="$SCRIPT_DIR/rtsp-watchdog.service"
RECOVERY_SERVICE="$SCRIPT_DIR/rtsp-camera-recovery.service"
UDEV_RULES="$SCRIPT_DIR/99-rtsp-camera.rules"

# Target locations
BIN_DIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
UDEV_DIR="/etc/udev/rules.d"
LOG_DIR="/var/log/rpi-cam"

#---------------------------
# Helpers
#---------------------------
ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*"; }
log_err() { echo "[$(ts)] ERROR: $*" >&2; }
die() { log_err "$*"; exit 1; }

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root: sudo $0"
  fi
}

#---------------------------
# Installation
#---------------------------
install_watchdog() {
    log "Installing RTSP Watchdog..."
    
    # Create log directory
    mkdir -p "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    
    # Install watchdog script
    if [[ -n "$WATCHDOG_SCRIPT" ]] && [[ -f "$WATCHDOG_SCRIPT" ]]; then
        # Remove BOM and CRLF if present
        sed -i '1s/^\xEF\xBB\xBF//' "$WATCHDOG_SCRIPT" 2>/dev/null || true
        sed -i 's/\r$//' "$WATCHDOG_SCRIPT"
        
        cp "$WATCHDOG_SCRIPT" "$BIN_DIR/rtsp_watchdog.sh"
        chmod +x "$BIN_DIR/rtsp_watchdog.sh"
        log "  Installed: $BIN_DIR/rtsp_watchdog.sh"
    else
        die "Watchdog script not found. Searched: $PROJECT_ROOT/rtsp_watchdog.sh, $SCRIPT_DIR/rtsp_watchdog.sh, ./rtsp_watchdog.sh"
    fi
    
    # Install watchdog service
    if [[ -f "$WATCHDOG_SERVICE" ]]; then
        sed -i '1s/^\xEF\xBB\xBF//' "$WATCHDOG_SERVICE" 2>/dev/null || true
        sed -i 's/\r$//' "$WATCHDOG_SERVICE"
        
        cp "$WATCHDOG_SERVICE" "$SYSTEMD_DIR/rtsp-watchdog.service"
        log "  Installed: $SYSTEMD_DIR/rtsp-watchdog.service"
    else
        die "Watchdog service file not found: $WATCHDOG_SERVICE"
    fi
    
    # Install camera recovery service
    if [[ -f "$RECOVERY_SERVICE" ]]; then
        sed -i '1s/^\xEF\xBB\xBF//' "$RECOVERY_SERVICE" 2>/dev/null || true
        sed -i 's/\r$//' "$RECOVERY_SERVICE"
        
        cp "$RECOVERY_SERVICE" "$SYSTEMD_DIR/rtsp-camera-recovery.service"
        log "  Installed: $SYSTEMD_DIR/rtsp-camera-recovery.service"
    else
        log "  Warning: Camera recovery service not found (optional)"
    fi
    
    # Install udev rules
    if [[ -f "$UDEV_RULES" ]]; then
        sed -i '1s/^\xEF\xBB\xBF//' "$UDEV_RULES" 2>/dev/null || true
        sed -i 's/\r$//' "$UDEV_RULES"
        
        cp "$UDEV_RULES" "$UDEV_DIR/99-rtsp-camera.rules"
        log "  Installed: $UDEV_DIR/99-rtsp-camera.rules"
    else
        log "  Warning: Udev rules not found (optional)"
    fi
}

enable_services() {
    log "Enabling services..."
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable and start watchdog
    systemctl enable rtsp-watchdog.service
    systemctl start rtsp-watchdog.service
    log "  Enabled and started: rtsp-watchdog.service"
    
    # Reload udev rules
    if [[ -f "$UDEV_DIR/99-rtsp-camera.rules" ]]; then
        udevadm control --reload-rules
        udevadm trigger
        log "  Reloaded udev rules"
    fi
}

show_status() {
    log ""
    log "Installation complete!"
    log ""
    log "Services status:"
    systemctl status rtsp-watchdog.service --no-pager || true
    log ""
    log "The watchdog will:"
    log "  - Check streaming health every 30 seconds"
    log "  - Auto-restart if camera disconnects and reconnects"
    log "  - Auto-restart if stream becomes unresponsive"
    log ""
    log "Logs: $LOG_DIR/rtsp_watchdog.log"
}

#---------------------------
# Main
#---------------------------
main() {
    log "=========================================="
    log "RTSP Watchdog Installation"
    log "=========================================="
    
    need_root
    install_watchdog
    enable_services
    show_status
    
    log "Done!"
}

main "$@"

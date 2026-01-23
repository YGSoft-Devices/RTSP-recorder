#!/usr/bin/env bash
#===============================================================================
# File: install.sh
# Purpose: Master installation script for RTSP Recorder system
# Target: Raspberry Pi OS Trixie (64-bit)
#
# This script installs all components:
#   1. GStreamer + RTSP server dependencies
#   2. Main RTSP recorder service
#   3. Recording service (ffmpeg-based)
#   4. Web management interface
#
# Usage:
#   sudo ./setup/install.sh [options]
#
# Options:
#   --all         Install all components (default)
#   --gstreamer   Install GStreamer only
#   --rtsp        Install RTSP service only
#   --recorder    Install recording service only
#   --webui       Install web interface only
#   --onvif       Install ONVIF server only
#   --watchdog    Install watchdog service only
#   --provision   Configure device (hostname, timezone) - interactive
#   --hostname X  Set hostname to X (non-interactive)
#   --timezone X  Set timezone to X (default: Europe/Paris)
#   --check       Check installation status
#   --repair      Repair/reinstall all components
#   --help        Show this help
#
# Version: 1.4.2
#===============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }
log_header()  { echo -e "\n${CYAN}========================================${NC}"; echo -e "${CYAN} $*${NC}"; echo -e "${CYAN}========================================${NC}\n"; }

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default: install all
INSTALL_GSTREAMER=false
INSTALL_RTSP=false
INSTALL_RECORDER=false
INSTALL_WEBUI=false
INSTALL_ONVIF=false
INSTALL_WATCHDOG=false
INSTALL_ALL=true
CHECK_ONLY=false
REPAIR_MODE=false
DO_PROVISION=false
PROVISION_HOSTNAME=""
PROVISION_TIMEZONE="Europe/Paris"

show_help() {
    cat << 'EOF'
RTSP Recorder - Installation Script v1.4.0

Usage: sudo ./setup/install.sh [options]

Options:
  --all         Install all components (default)
  --gstreamer   Install GStreamer and dependencies only
  --rtsp        Install RTSP streaming service only
  --recorder    Install recording service only  
  --webui       Install web management interface only
  --onvif       Install ONVIF server only
  --watchdog    Install watchdog service only
  --provision   Configure device (hostname, timezone) - interactive
  --hostname X  Set hostname to X (non-interactive provisioning)
  --timezone X  Set timezone to X (default: Europe/Paris)
  --check       Check installation status (no changes)
  --repair      Repair/reinstall all components
  --help        Show this help

Components:
  1. GStreamer  - Video/audio processing framework
  2. RTSP       - RTSP streaming server (test-launch)
  3. Recorder   - Segmented video recording (ffmpeg)
  4. WebUI      - Web management interface (Flask)
  5. ONVIF      - ONVIF device discovery server
  6. Watchdog   - Auto-recovery and monitoring

Examples:
  sudo ./setup/install.sh                          # Install everything
  sudo ./setup/install.sh --provision              # Install + configure interactively
  sudo ./setup/install.sh --hostname camera-salon  # Install + set hostname
  sudo ./setup/install.sh --check                  # Check installation status
  sudo ./setup/install.sh --repair                 # Repair/reinstall
  sudo ./setup/install.sh --gstreamer              # GStreamer only
  sudo ./setup/install.sh --rtsp --webui           # RTSP + Web UI

EOF
}

parse_args() {
    if [[ $# -eq 0 ]]; then
        INSTALL_ALL=true
        return
    fi

    INSTALL_ALL=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all)
                INSTALL_ALL=true
                ;;
            --gstreamer)
                INSTALL_GSTREAMER=true
                ;;
            --rtsp)
                INSTALL_RTSP=true
                ;;
            --recorder)
                INSTALL_RECORDER=true
                ;;
            --webui)
                INSTALL_WEBUI=true
                ;;
            --onvif)
                INSTALL_ONVIF=true
                ;;
            --watchdog)
                INSTALL_WATCHDOG=true
                ;;
            --provision)
                DO_PROVISION=true
                ;;
            --hostname)
                shift
                PROVISION_HOSTNAME="$1"
                DO_PROVISION=true
                ;;
            --timezone)
                shift
                PROVISION_TIMEZONE="$1"
                DO_PROVISION=true
                ;;
            --check)
                CHECK_ONLY=true
                ;;
            --repair)
                REPAIR_MODE=true
                INSTALL_ALL=true
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done
}

check_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        log_error "This script must be run as root"
        echo "Usage: sudo $0"
        exit 1
    fi
}

check_platform() {
    log_info "Checking platform..."
    
    if [[ -f /proc/device-tree/model ]]; then
        PI_MODEL="$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')"
        log_success "Platform: $PI_MODEL"
    else
        log_warn "Not running on Raspberry Pi - some features may not work"
    fi

    # Check OS
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        log_info "OS: $PRETTY_NAME"
    fi
}

provision_device() {
    log_header "Device Provisioning"
    
    local current_hostname
    current_hostname=$(hostname)
    local new_hostname="$PROVISION_HOSTNAME"
    local new_timezone="$PROVISION_TIMEZONE"
    
    log_info "Current hostname: $current_hostname"
    log_info "Current timezone: $(timedatectl show --property=Timezone --value 2>/dev/null || echo 'unknown')"
    
    # Interactive mode if no hostname provided
    if [[ -z "$new_hostname" ]]; then
        echo ""
        echo -e "${CYAN}========================================${NC}"
        echo -e "${CYAN} Device Provisioning (optional)${NC}"
        echo -e "${CYAN}========================================${NC}"
        echo ""
        echo -e "Press Enter to keep current values, or type new value."
        echo ""
        
        # Hostname
        read -r -p "New hostname [$current_hostname]: " input_hostname
        if [[ -n "$input_hostname" ]]; then
            new_hostname="$input_hostname"
        fi
        
        # Timezone
        read -r -p "Timezone [$new_timezone]: " input_timezone
        if [[ -n "$input_timezone" ]]; then
            new_timezone="$input_timezone"
        fi
        
        echo ""
    fi
    
    # Apply hostname if changed
    if [[ -n "$new_hostname" && "$new_hostname" != "$current_hostname" ]]; then
        log_info "Setting hostname to: $new_hostname"
        
        # Set hostname
        hostnamectl set-hostname "$new_hostname"
        
        # Update /etc/hosts
        if grep -q "127.0.1.1" /etc/hosts; then
            sed -i "s/127.0.1.1.*/127.0.1.1\t$new_hostname/" /etc/hosts
        else
            echo -e "127.0.1.1\t$new_hostname" >> /etc/hosts
        fi
        
        log_success "Hostname set to: $new_hostname"
    else
        log_info "Hostname unchanged: $current_hostname"
    fi
    
    # Apply timezone
    log_info "Setting timezone to: $new_timezone"
    if timedatectl set-timezone "$new_timezone" 2>/dev/null; then
        log_success "Timezone set to: $new_timezone"
    else
        log_warn "Failed to set timezone (invalid timezone?)"
    fi
    
    # Enable NTP
    log_info "Enabling NTP synchronization..."
    timedatectl set-ntp true 2>/dev/null || true
    log_success "NTP enabled"
    
    echo ""
}

prepare_system() {
    log_header "Preparing System"
    
    # Disable cloud-init hostname management (required for Meeting provisioning)
    log_info "Configuring cloud-init for hostname persistence..."
    
    CLOUD_CFG="/etc/cloud/cloud.cfg"
    if [[ -f "$CLOUD_CFG" ]]; then
        # Backup original
        if [[ ! -f "${CLOUD_CFG}.orig" ]]; then
            cp "$CLOUD_CFG" "${CLOUD_CFG}.orig"
            log_info "Backed up original cloud.cfg"
        fi
        
        # Add preserve_hostname: true if not present
        if grep -q "preserve_hostname:" "$CLOUD_CFG"; then
            sed -i 's/preserve_hostname:.*/preserve_hostname: true/' "$CLOUD_CFG"
        else
            echo -e "\n# Added by RTSP Recorder installer\npreserve_hostname: true" >> "$CLOUD_CFG"
        fi
        
        # Add manage_etc_hosts: false if not present
        if grep -q "manage_etc_hosts:" "$CLOUD_CFG"; then
            sed -i 's/manage_etc_hosts:.*/manage_etc_hosts: false/' "$CLOUD_CFG"
        else
            echo "manage_etc_hosts: false" >> "$CLOUD_CFG"
        fi
        
        # CRITICAL: Comment out set_hostname and update_hostname modules
        # These modules override hostname at boot even with preserve_hostname: true
        sed -i 's/^[[:space:]]*- set_hostname/#  - set_hostname  # Disabled by RTSP installer/' "$CLOUD_CFG"
        sed -i 's/^[[:space:]]*- update_hostname/#  - update_hostname  # Disabled by RTSP installer/' "$CLOUD_CFG"
        
        # Clear cloud-init's previous hostname cache
        rm -f /var/lib/cloud/data/previous-hostname 2>/dev/null || true
        
        log_success "Cloud-init configured: hostname will persist across reboots"
    else
        log_info "No cloud-init found (not a cloud image) - skipping"
    fi
    
    # Ensure avahi-daemon is installed for .local hostname resolution
    log_info "Checking mDNS (avahi) service..."
    if ! command -v avahi-daemon &>/dev/null; then
        log_info "Installing avahi-daemon for .local hostname resolution..."
        apt-get update -qq
        apt-get install -y -qq avahi-daemon avahi-utils
    fi
    
    if systemctl is-enabled avahi-daemon &>/dev/null; then
        log_success "Avahi (mDNS) service is enabled"
    else
        systemctl enable avahi-daemon
        systemctl start avahi-daemon
        log_success "Avahi (mDNS) service enabled and started"
    fi
    
    # Install hostapd and dnsmasq for Access Point mode
    log_info "Installing Access Point dependencies (hostapd, dnsmasq)..."
    if ! command -v hostapd &>/dev/null || ! command -v dnsmasq &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq hostapd dnsmasq
    fi
    
    # Stop and disable hostapd/dnsmasq by default (will be started on demand by web manager)
    log_info "Configuring hostapd and dnsmasq (disabled by default)..."
    systemctl stop hostapd 2>/dev/null || true
    systemctl disable hostapd 2>/dev/null || true
    systemctl mask hostapd 2>/dev/null || true  # Mask to prevent auto-start
    
    # Create AP config directory
    mkdir -p /etc/rpi-cam
    chmod 755 /etc/rpi-cam
    
    # Configure dnsmasq to not start automatically for DHCP
    if [[ -f /etc/dnsmasq.conf ]]; then
        # Ensure dnsmasq doesn't interfere with normal operation
        if ! grep -q "# RTSP Recorder AP mode marker" /etc/dnsmasq.conf; then
            cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
            echo -e "\n# RTSP Recorder AP mode marker - dnsmasq configured for AP mode only" >> /etc/dnsmasq.conf
        fi
    fi
    
    log_success "Access Point dependencies installed (hostapd, dnsmasq)"
}

install_gstreamer() {
    log_header "Installing GStreamer and dependencies"
    
    if [[ -f "$SCRIPT_DIR/install_gstreamer_rtsp.sh" ]]; then
        chmod +x "$SCRIPT_DIR/install_gstreamer_rtsp.sh"
        "$SCRIPT_DIR/install_gstreamer_rtsp.sh"
    else
        log_error "install_gstreamer_rtsp.sh not found in $SCRIPT_DIR"
        return 1
    fi
}

install_rtsp_service() {
    log_header "Installing RTSP Streaming Service"
    
    if [[ -f "$SCRIPT_DIR/install_rpi_av_rtsp_recorder.sh" ]]; then
        chmod +x "$SCRIPT_DIR/install_rpi_av_rtsp_recorder.sh"
        "$SCRIPT_DIR/install_rpi_av_rtsp_recorder.sh"
    else
        log_error "install_rpi_av_rtsp_recorder.sh not found in $SCRIPT_DIR"
        return 1
    fi
}

install_recorder_service() {
    log_header "Installing Recording Service"
    
    if [[ -f "$SCRIPT_DIR/install_rtsp_recorder.sh" ]]; then
        chmod +x "$SCRIPT_DIR/install_rtsp_recorder.sh"
        "$SCRIPT_DIR/install_rtsp_recorder.sh"
    else
        log_error "install_rtsp_recorder.sh not found in $SCRIPT_DIR"
        return 1
    fi
}

install_webui() {
    log_header "Installing Web Management Interface"
    
    if [[ -f "$SCRIPT_DIR/install_web_manager.sh" ]]; then
        chmod +x "$SCRIPT_DIR/install_web_manager.sh"
        "$SCRIPT_DIR/install_web_manager.sh"
    else
        log_error "install_web_manager.sh not found in $SCRIPT_DIR"
        return 1
    fi
}

install_onvif() {
    log_header "Installing ONVIF Server"
    
    if [[ -f "$SCRIPT_DIR/install_onvif_server.sh" ]]; then
        chmod +x "$SCRIPT_DIR/install_onvif_server.sh"
        "$SCRIPT_DIR/install_onvif_server.sh"
    else
        log_error "install_onvif_server.sh not found in $SCRIPT_DIR"
        return 1
    fi
}

install_watchdog() {
    log_header "Installing Watchdog Service"
    
    if [[ -f "$SCRIPT_DIR/install_rtsp_watchdog.sh" ]]; then
        chmod +x "$SCRIPT_DIR/install_rtsp_watchdog.sh"
        "$SCRIPT_DIR/install_rtsp_watchdog.sh"
    else
        log_error "install_rtsp_watchdog.sh not found in $SCRIPT_DIR"
        return 1
    fi
}

check_installation() {
    log_header "Checking Installation Status"
    
    local all_ok=true
    
    # Check directories
    echo -e "${CYAN}Directories:${NC}"
    for dir in /var/cache/rpi-cam/recordings /var/log/rpi-cam /etc/rpi-cam /opt/rpi-cam-webmanager; do
        if [[ -d "$dir" ]]; then
            echo -e "  ${GREEN}✓${NC} $dir"
        else
            echo -e "  ${RED}✗${NC} $dir (missing)"
            all_ok=false
        fi
    done
    
    # Check scripts
    echo -e "\n${CYAN}Scripts:${NC}"
    for script in /usr/local/bin/rpi_av_rtsp_recorder.sh /usr/local/bin/rtsp_recorder.sh /usr/local/bin/rtsp_watchdog.sh /usr/local/bin/test-launch; do
        if [[ -x "$script" ]]; then
            echo -e "  ${GREEN}✓${NC} $script"
        else
            echo -e "  ${RED}✗${NC} $script (missing or not executable)"
            all_ok=false
        fi
    done
    
    # Check services
    echo -e "\n${CYAN}Services:${NC}"
    for svc in rpi-av-rtsp-recorder rtsp-recorder rpi-cam-webmanager rtsp-watchdog; do
        if systemctl is-enabled "${svc}.service" &>/dev/null; then
            local status=$(systemctl is-active "${svc}.service" 2>/dev/null || echo "inactive")
            if [[ "$status" == "active" ]]; then
                echo -e "  ${GREEN}✓${NC} $svc (enabled, running)"
            else
                echo -e "  ${YELLOW}○${NC} $svc (enabled, $status)"
            fi
        else
            echo -e "  ${RED}✗${NC} $svc (not enabled)"
            all_ok=false
        fi
    done
    
    # ONVIF is optional, don't fail if not enabled
    echo -e "\n${CYAN}Optional Services:${NC}"
    if systemctl is-enabled rpi-cam-onvif.service &>/dev/null; then
        local status=$(systemctl is-active rpi-cam-onvif.service 2>/dev/null || echo "inactive")
        echo -e "  ${GREEN}✓${NC} rpi-cam-onvif (enabled, $status)"
    else
        echo -e "  ${YELLOW}○${NC} rpi-cam-onvif (not enabled - optional)"
    fi
    
    # Check config files
    echo -e "\n${CYAN}Configuration:${NC}"
    for cfg in /etc/rpi-cam/config.env /etc/rpi-cam/recorder.conf; do
        if [[ -f "$cfg" ]]; then
            echo -e "  ${GREEN}✓${NC} $cfg"
        else
            echo -e "  ${RED}✗${NC} $cfg (missing)"
            all_ok=false
        fi
    done
    
    # Check GStreamer
    echo -e "\n${CYAN}GStreamer:${NC}"
    if command -v gst-launch-1.0 &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} gst-launch-1.0 available"
    else
        echo -e "  ${RED}✗${NC} gst-launch-1.0 not found"
        all_ok=false
    fi
    
    if gst-inspect-1.0 v4l2src &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} v4l2src plugin"
    else
        echo -e "  ${RED}✗${NC} v4l2src plugin missing"
        all_ok=false
    fi
    
    # Python venv
    echo -e "\n${CYAN}Python Environment:${NC}"
    if [[ -f /opt/rpi-cam-webmanager/venv/bin/python ]]; then
        echo -e "  ${GREEN}✓${NC} Virtual environment"
    else
        echo -e "  ${RED}✗${NC} Virtual environment missing"
        all_ok=false
    fi
    
    echo ""
    if $all_ok; then
        log_success "All components installed correctly!"
        return 0
    else
        log_warn "Some components are missing. Run with --repair to fix."
        return 1
    fi
}

show_summary() {
    log_header "Installation Complete!"
    
    echo -e "${GREEN}Installed components:${NC}"
    
    if systemctl is-enabled rpi-av-rtsp-recorder.service &>/dev/null; then
        echo "  ✓ RTSP Streaming Service"
    fi
    
    if systemctl is-enabled rtsp-recorder.service &>/dev/null; then
        echo "  ✓ Recording Service"
    fi
    
    if systemctl is-enabled rpi-cam-webmanager.service &>/dev/null; then
        echo "  ✓ Web Management Interface"
    fi
    
    if systemctl is-enabled rpi-cam-onvif.service &>/dev/null 2>&1; then
        echo "  ✓ ONVIF Server"
    fi
    
    if systemctl is-enabled rtsp-watchdog.service &>/dev/null 2>&1; then
        echo "  ✓ Watchdog Service"
    fi
    
    echo ""
    echo -e "${CYAN}Quick Start:${NC}"
    echo "  # Start all services"
    echo "  sudo systemctl start rpi-av-rtsp-recorder"
    echo "  sudo systemctl start rtsp-recorder"
    echo "  sudo systemctl start rpi-cam-webmanager"
    echo "  sudo systemctl start rtsp-watchdog"
    echo ""
    echo "  # Access web interface"
    echo "  http://<raspberry-pi-ip>:5000"
    echo ""
    echo "  # RTSP stream URL"
    echo "  rtsp://<raspberry-pi-ip>:8554/stream"
    echo ""
    echo -e "${CYAN}Configuration:${NC}"
    echo "  /etc/rpi-cam/config.env    - Main configuration"
    echo "  /etc/rpi-cam/recorder.conf - RTSP recorder config"
    echo ""
    echo -e "${CYAN}Logs:${NC}"
    echo "  /var/log/rpi-cam/           - All service logs"
    echo ""
    echo -e "${CYAN}Recordings:${NC}"
    echo "  /var/cache/rpi-cam/recordings/"
    echo ""
}

main() {
    parse_args "$@"
    
    # Handle check mode (no root required for basic check)
    if $CHECK_ONLY; then
        check_installation
        exit $?
    fi
    
    check_root
    
    log_header "RTSP Recorder Installation"
    log_info "Project root: $PROJECT_ROOT"
    log_info "Setup dir: $SCRIPT_DIR"
    
    if $REPAIR_MODE; then
        log_warn "REPAIR MODE: Reinstalling all components"
    fi
    
    check_platform
    
    # Provisioning (optional, non-blocking)
    if $DO_PROVISION; then
        provision_device
    fi
    
    # Always prepare system first (cloud-init, avahi)
    prepare_system
    
    if $INSTALL_ALL; then
        # Continue even if one component fails (|| true prevents set -e from stopping)
        install_gstreamer || { log_warn "GStreamer installation had issues, continuing..."; }
        install_rtsp_service || { log_warn "RTSP service installation had issues, continuing..."; }
        install_recorder_service || { log_warn "Recorder service installation had issues, continuing..."; }
        install_webui || { log_warn "WebUI installation had issues, continuing..."; }
        install_onvif || { log_warn "ONVIF installation had issues, continuing..."; }
        install_watchdog || { log_warn "Watchdog installation had issues, continuing..."; }
    else
        $INSTALL_GSTREAMER && install_gstreamer
        $INSTALL_RTSP && install_rtsp_service
        $INSTALL_RECORDER && install_recorder_service
        $INSTALL_WEBUI && install_webui
        $INSTALL_ONVIF && install_onvif
        $INSTALL_WATCHDOG && install_watchdog
    fi
    
    show_summary
    
    # Final check
    echo ""
    log_info "Running installation check..."
    check_installation || true
}

main "$@"

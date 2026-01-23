#!/usr/bin/env bash
################################################################################
# Energy Manager Helper Script for Raspberry Pi
# 
# Purpose: Manage power consumption settings for Raspberry Pi 3B+/4/5
# Version: 1.0.0
#
# This script provides functions for managing:
# - Bluetooth (dtoverlay=disable-bt)
# - HDMI (hdmi_blanking)
# - Audio (dtparam=audio=off)
# - CPU frequency scaling (requires cpufrequtils)
#
# Target: Raspberry Pi OS Trixie (Debian 13) / Bookworm
# Maintainer: RTSP-Full Web Manager
################################################################################

set -euo pipefail

# ============================================================================
# Logging Functions
# ============================================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $*"
}

log_err() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2
}

log_warn() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] $*"
}

die() {
    log_err "$*"
    exit 1
}

# ============================================================================
# Boot Config Paths
# ============================================================================

# Determine boot config path (Trixie/Bookworm uses /boot/firmware/)
find_boot_config() {
    if [[ -f /boot/firmware/config.txt ]]; then
        echo /boot/firmware/config.txt
    elif [[ -f /boot/config.txt ]]; then
        echo /boot/config.txt
    else
        return 1
    fi
}

BOOT_CONFIG_FILE=$(find_boot_config) || die "Boot config file not found"

# ============================================================================
# Bluetooth Management
# ============================================================================

enable_bluetooth() {
    log "Enabling Bluetooth..."
    
    # Remove disable-bt overlay from boot config
    sed -i '/dtoverlay.*disable-bt/d' "$BOOT_CONFIG_FILE"
    
    # Enable systemd bluetooth service
    if systemctl is-enabled bluetooth &>/dev/null; then
        log "Bluetooth service already enabled"
    else
        systemctl enable bluetooth
        log "Bluetooth service enabled"
    fi
    
    systemctl start bluetooth || log_warn "Could not start bluetooth service"
    
    log "Bluetooth enabled (reboot required for boot-time effect)"
}

disable_bluetooth() {
    log "Disabling Bluetooth..."
    
    # Remove any existing dtoverlay=disable-bt line
    sed -i '/dtoverlay.*disable-bt/d' "$BOOT_CONFIG_FILE"
    
    # Add disable-bt overlay
    echo "" >> "$BOOT_CONFIG_FILE"
    echo "# Disable Bluetooth (energy saving)" >> "$BOOT_CONFIG_FILE"
    echo "dtoverlay=disable-bt" >> "$BOOT_CONFIG_FILE"
    
    # Disable systemd bluetooth service
    systemctl disable bluetooth || true
    systemctl stop bluetooth || true
    
    log "Bluetooth disabled (reboot required for boot-time effect)"
}

get_bluetooth_status() {
    if grep -q "dtoverlay.*disable-bt" "$BOOT_CONFIG_FILE" 2>/dev/null; then
        echo "disabled"
    else
        echo "enabled"
    fi
}

# ============================================================================
# HDMI Management
# ============================================================================

enable_hdmi() {
    log "Enabling HDMI..."
    
    # Remove HDMI blanking settings
    sed -i '/hdmi_blanking/d' "$BOOT_CONFIG_FILE"
    
    log "HDMI enabled (reboot required for boot-time effect)"
}

disable_hdmi() {
    log "Disabling HDMI..."
    
    # Remove any existing hdmi_blanking line
    sed -i '/hdmi_blanking/d' "$BOOT_CONFIG_FILE"
    
    # Add HDMI blanking (2 = complete off)
    echo "" >> "$BOOT_CONFIG_FILE"
    echo "# Disable HDMI output (energy saving)" >> "$BOOT_CONFIG_FILE"
    echo "hdmi_blanking=2" >> "$BOOT_CONFIG_FILE"
    
    log "HDMI disabled (reboot required for boot-time effect)"
}

get_hdmi_status() {
    if grep -q "hdmi_blanking\s*=\s*2" "$BOOT_CONFIG_FILE" 2>/dev/null; then
        echo "disabled"
    else
        echo "enabled"
    fi
}

# ============================================================================
# Audio Management
# ============================================================================

enable_audio() {
    log "Enabling Audio..."
    
    # Remove audio=off parameter
    sed -i '/dtparam.*audio.*=.*off/d' "$BOOT_CONFIG_FILE"
    
    log "Audio enabled (reboot required for boot-time effect)"
}

disable_audio() {
    log "Disabling Audio..."
    
    # Remove any existing audio parameter lines
    sed -i '/dtparam.*audio/d' "$BOOT_CONFIG_FILE"
    
    # Add audio=off parameter
    echo "" >> "$BOOT_CONFIG_FILE"
    echo "# Disable audio (energy saving)" >> "$BOOT_CONFIG_FILE"
    echo "dtparam=audio=off" >> "$BOOT_CONFIG_FILE"
    
    log "Audio disabled (reboot required for boot-time effect)"
}

get_audio_status() {
    if grep -q "dtparam.*audio\s*=\s*off" "$BOOT_CONFIG_FILE" 2>/dev/null; then
        echo "disabled"
    else
        echo "enabled"
    fi
}

# ============================================================================
# CPU Frequency Management
# ============================================================================

set_cpu_frequency() {
    local freq_mhz=$1
    
    # Validate range (600-1500 MHz for Pi 3B+)
    if (( freq_mhz < 600 || freq_mhz > 1500 )); then
        die "CPU frequency must be between 600 and 1500 MHz"
    fi
    
    log "Setting CPU frequency to ${freq_mhz}MHz..."
    
    # Check if cpufreq-set is available
    if ! command -v cpufreq-set &>/dev/null; then
        die "cpufreq-set not found. Install with: sudo apt install cpufrequtils"
    fi
    
    cpufreq-set -f "${freq_mhz}MHz" || die "Failed to set CPU frequency"
    
    log "CPU frequency set to ${freq_mhz}MHz (immediate effect)"
}

get_cpu_frequency() {
    local cpu_freq_file=/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
    
    if [[ -f $cpu_freq_file ]]; then
        local freq_khz
        freq_khz=$(cat "$cpu_freq_file")
        echo $((freq_khz / 1000))
    else
        echo "unknown"
    fi
}

# ============================================================================
# Query/Status Functions
# ============================================================================

show_status() {
    log "Current power management status:"
    echo ""
    echo "  Bluetooth: $(get_bluetooth_status)"
    echo "  HDMI:      $(get_hdmi_status)"
    echo "  Audio:     $(get_audio_status)"
    echo "  CPU Freq:  $(get_cpu_frequency) MHz"
    echo ""
    echo "Boot config: $BOOT_CONFIG_FILE"
}

show_estimated_savings() {
    local savings=0
    
    if [[ $(get_bluetooth_status) == "disabled" ]]; then
        savings=$((savings + 20))
    fi
    
    if [[ $(get_hdmi_status) == "disabled" ]]; then
        savings=$((savings + 40))
    fi
    
    if [[ $(get_audio_status) == "disabled" ]]; then
        savings=$((savings + 10))
    fi
    
    echo "${savings}mA"
}

# ============================================================================
# Configuration Functions
# ============================================================================

# Set multiple power settings at once
configure_power() {
    local bluetooth_enabled=$1
    local hdmi_enabled=$2
    local audio_enabled=$3
    
    log "Configuring power settings..."
    
    if [[ $bluetooth_enabled == "true" ]]; then
        enable_bluetooth
    else
        disable_bluetooth
    fi
    
    if [[ $hdmi_enabled == "true" ]]; then
        enable_hdmi
    else
        disable_hdmi
    fi
    
    if [[ $audio_enabled == "true" ]]; then
        enable_audio
    else
        disable_audio
    fi
    
    log "Power configuration complete"
    show_status
}

# ============================================================================
# Main / Usage
# ============================================================================

usage() {
    cat << EOF
Usage: $0 <command> [options]

Commands:
  status                    Show current power management status
  savings                   Show estimated energy savings
  
  bluetooth enable|disable  Control Bluetooth
  hdmi enable|disable       Control HDMI output
  audio enable|disable      Control audio subsystem
  
  cpu-freq <MHz>           Set CPU frequency (600-1500 MHz)
  cpu-freq-get             Get current CPU frequency
  
  configure-power <bt> <hdmi> <audio>
                           Configure all power settings at once
                           (use true/false for each)

Examples:
  $0 status
  $0 bluetooth disable
  $0 hdmi disable
  $0 audio disable
  $0 cpu-freq 800
  $0 configure-power false false false  # Ultra low power mode
  $0 configure-power true true true     # Normal operation

Note: Most commands require sudo for boot config modifications.
      Reboot required for boot config changes to take effect.
EOF
}

# ============================================================================
# Script Entry Point
# ============================================================================

if [[ $# -eq 0 ]]; then
    usage
    exit 1
fi

case "$1" in
    status)
        show_status
        ;;
    savings)
        show_estimated_savings
        ;;
    bluetooth)
        [[ $# -lt 2 ]] && die "bluetooth: missing argument (enable|disable)"
        case "$2" in
            enable) enable_bluetooth ;;
            disable) disable_bluetooth ;;
            get|status) get_bluetooth_status ;;
            *) die "Invalid bluetooth command: $2" ;;
        esac
        ;;
    hdmi)
        [[ $# -lt 2 ]] && die "hdmi: missing argument (enable|disable)"
        case "$2" in
            enable) enable_hdmi ;;
            disable) disable_hdmi ;;
            get|status) get_hdmi_status ;;
            *) die "Invalid hdmi command: $2" ;;
        esac
        ;;
    audio)
        [[ $# -lt 2 ]] && die "audio: missing argument (enable|disable)"
        case "$2" in
            enable) enable_audio ;;
            disable) disable_audio ;;
            get|status) get_audio_status ;;
            *) die "Invalid audio command: $2" ;;
        esac
        ;;
    cpu-freq)
        [[ $# -lt 2 ]] && die "cpu-freq: missing frequency argument"
        set_cpu_frequency "$2"
        ;;
    cpu-freq-get)
        get_cpu_frequency
        ;;
    configure-power)
        [[ $# -lt 4 ]] && die "configure-power: missing arguments (bluetooth hdmi audio)"
        configure_power "$2" "$3" "$4"
        ;;
    *)
        log_err "Unknown command: $1"
        usage
        exit 1
        ;;
esac

exit 0

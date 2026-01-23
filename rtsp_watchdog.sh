#!/usr/bin/env bash
#===============================================================================
# File: rtsp_watchdog.sh
# Location: /usr/local/bin/rtsp_watchdog.sh
#
# Purpose:
#   - Monitor RTSP streaming service health
#   - Auto-restart if camera disconnects/reconnects
#   - Monitor audio device and ALSA errors
#   - Ensure maximum availability of the streaming service
#
# Version: 1.2.0
# Changelog:
#   - 1.2.0: Support CSI mode (rpi_csi_rtsp_server.py) in addition to USB (test-launch)
#   - 1.1.0: Added audio device monitoring
#            - Monitors ALSA errors in logs
#            - Detects audio device disconnection
#            - Auto-restart when USB devices reconnect after crash
#   - 1.0.0: Initial release
#
# Usage:
#   Run as a systemd service (rtsp-watchdog.service)
#   Checks every 30 seconds if the stream is healthy
#
#===============================================================================

set -euo pipefail

#---------------------------
# Configuration
#---------------------------
: "${CHECK_INTERVAL:=30}"           # Seconds between health checks
: "${RTSP_SERVICE:=rpi-av-rtsp-recorder}"
: "${RECORDER_SERVICE:=rtsp-recorder}"
: "${VIDEO_DEVICE:=/dev/video0}"
: "${RTSP_PORT:=8554}"
: "${RTSP_PATH:=stream}"
: "${LOG_FILE:=/var/log/rpi-cam/rtsp_watchdog.log}"
: "${MAX_FAILURES:=3}"              # Consecutive failures before restart
: "${CAMERA_WAIT_TIME:=10}"         # Wait time after camera appears
: "${ALSA_ERROR_THRESHOLD:=50}"     # Max ALSA errors in recent log before restart
: "${AUDIO_ENABLE:=auto}"           # Check audio only if enabled

# Load config if exists
CONFIG_FILE="/etc/rpi-cam/config.env"
[[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE"

# Alternative config location
CONFIG_FILE2="/etc/rpi-cam/recorder.conf"
[[ -f "$CONFIG_FILE2" ]] && source "$CONFIG_FILE2"

#---------------------------
# Globals
#---------------------------
FAILURE_COUNT=0
CAMERA_WAS_MISSING=false
AUDIO_WAS_MISSING=false
LAST_ALSA_CHECK=0

#---------------------------
# Helpers
#---------------------------
ts() { date "+%Y-%m-%d %H:%M:%S"; }

# Log to file only (systemd captures stdout separately)
log() { echo "[$(ts)] [WATCHDOG] $*" >> "$LOG_FILE"; }
log_warn() { echo "[$(ts)] [WATCHDOG] WARNING: $*" >> "$LOG_FILE"; }
log_err() { echo "[$(ts)] [WATCHDOG] ERROR: $*" >> "$LOG_FILE"; }

#---------------------------
# Audio Check Functions
#---------------------------

# Check if audio device exists
check_audio_exists() {
    # Only check if audio is enabled
    if [[ "$AUDIO_ENABLE" == "no" ]]; then
        return 0  # No audio = no problem
    fi
    
    # Check for any USB audio capture device
    if arecord -l 2>/dev/null | grep -q "card"; then
        return 0
    fi
    return 1
}

# Count ALSA errors in recent logs (last 100 lines)
count_alsa_errors() {
    local rtsp_log="/var/log/rpi-cam/rpi_av_rtsp_recorder.log"
    local count
    if [[ -f "$rtsp_log" ]]; then
        count=$(tail -100 "$rtsp_log" 2>/dev/null | grep -c "No such device" 2>/dev/null) || count=0
    else
        count=0
    fi
    # Ensure single line, single number
    count="${count%%[^0-9]*}"
    [[ -z "$count" ]] && count=0
    printf '%d' "$count"
}

# Check if GStreamer process is stuck in error loop
check_alsa_error_loop() {
    local error_count
    error_count=$(count_alsa_errors)
    # Default to 0 if not a number
    [[ "$error_count" =~ ^[0-9]+$ ]] || error_count=0
    
    if [[ "$error_count" -gt "$ALSA_ERROR_THRESHOLD" ]]; then
        log_err "Detected ALSA error loop ($error_count errors in recent logs)"
        return 1
    fi
    return 0
}

#---------------------------
# Check Functions
#---------------------------

# Check if camera device exists
check_camera_exists() {
    if [[ -e "$VIDEO_DEVICE" ]]; then
        return 0
    else
        return 1
    fi
}

# Check if camera is accessible (can be opened)
check_camera_accessible() {
    if [[ -e "$VIDEO_DEVICE" ]]; then
        # Try to query the device
        if v4l2-ctl --device="$VIDEO_DEVICE" --all >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Check if RTSP service is running
check_service_running() {
    local service="$1"
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        return 0
    fi
    return 1
}

# Check if RTSP stream is accessible (can connect)
check_rtsp_stream() {
    # Check if port is listening
    if ! ss -tlnp 2>/dev/null | grep -q ":${RTSP_PORT}"; then
        return 1
    fi
    
    # Check for streaming process (test-launch for USB, rpi_csi_rtsp_server for CSI)
    if pgrep -f "test-launch" >/dev/null 2>&1 || pgrep -f "rpi_csi_rtsp_server" >/dev/null 2>&1; then
        # Also verify no ALSA error loop (GStreamer stuck)
        if check_alsa_error_loop; then
            return 0
        else
            log_warn "Stream appears up but ALSA is in error loop"
            return 1
        fi
    fi
    
    return 1
}

# Restart the RTSP service
restart_rtsp_service() {
    log "Restarting RTSP service..."
    
    # Stop cleanly first
    systemctl stop "$RTSP_SERVICE" 2>/dev/null || true
    sleep 2
    
    # Kill any orphan processes (USB mode)
    pkill -9 -f "test-launch" 2>/dev/null || true
    pkill -9 -f "gst-launch" 2>/dev/null || true
    # Kill CSI mode processes
    pkill -9 -f "rpi_csi_rtsp_server" 2>/dev/null || true
    sleep 1
    
    # Truncate the log file to clear ALSA errors (prevents immediate re-trigger)
    local rtsp_log="/var/log/rpi-cam/rpi_av_rtsp_recorder.log"
    if [[ -f "$rtsp_log" ]]; then
        # Keep last 1000 lines, remove the rest
        tail -1000 "$rtsp_log" > "${rtsp_log}.tmp" 2>/dev/null && mv "${rtsp_log}.tmp" "$rtsp_log" || true
    fi
    
    # Start fresh
    if systemctl start "$RTSP_SERVICE"; then
        log "RTSP service restarted successfully"
        
        # Also restart recorder if it exists and is enabled
        if systemctl is-enabled --quiet "$RECORDER_SERVICE" 2>/dev/null; then
            log "Restarting recorder service..."
            systemctl restart "$RECORDER_SERVICE" 2>/dev/null || true
        fi
        
        return 0
    else
        log_err "Failed to restart RTSP service"
        return 1
    fi
}

# Wait for camera to stabilize after reconnection
wait_for_camera_stable() {
    log "Waiting ${CAMERA_WAIT_TIME}s for camera to stabilize..."
    sleep "$CAMERA_WAIT_TIME"
    
    # Verify camera is still there after wait
    if check_camera_accessible; then
        log "Camera is stable and accessible"
        return 0
    else
        log_warn "Camera not stable after wait"
        return 1
    fi
}

# Wait for audio device to stabilize after reconnection
wait_for_audio_stable() {
    log "Waiting ${CAMERA_WAIT_TIME}s for audio device to stabilize..."
    sleep "$CAMERA_WAIT_TIME"
    
    # Verify audio is still there after wait
    if check_audio_exists; then
        log "Audio device is stable and accessible"
        return 0
    else
        log_warn "Audio device not stable after wait"
        return 1
    fi
}

#---------------------------
# Main Health Check
#---------------------------
perform_health_check() {
    local camera_ok=false
    local service_ok=false
    local stream_ok=false
    local audio_ok=false
    
    # 1. Check camera exists
    if check_camera_exists; then
        # Camera came back after being missing?
        if [[ "$CAMERA_WAS_MISSING" == "true" ]]; then
            log "Camera device reappeared at $VIDEO_DEVICE"
            CAMERA_WAS_MISSING=false
            
            # Wait for camera to stabilize
            if wait_for_camera_stable; then
                log "Camera stabilized, triggering service restart"
                restart_rtsp_service
                FAILURE_COUNT=0
                return 0
            fi
        fi
        
        # Check if camera is accessible
        if check_camera_accessible; then
            camera_ok=true
        else
            log_warn "Camera exists but not accessible"
        fi
    else
        if [[ "$CAMERA_WAS_MISSING" == "false" ]]; then
            log_warn "Camera device $VIDEO_DEVICE has disappeared!"
        fi
        CAMERA_WAS_MISSING=true
        # Don't count as failure - camera is physically missing
        return 0
    fi
    
    # 2. Check audio device (if audio is enabled)
    if [[ "$AUDIO_ENABLE" != "no" ]]; then
        if check_audio_exists; then
            # Audio came back after being missing?
            if [[ "$AUDIO_WAS_MISSING" == "true" ]]; then
                log "Audio device reappeared!"
                AUDIO_WAS_MISSING=false
                
                # Wait for audio to stabilize then restart
                if wait_for_audio_stable; then
                    log "Audio stabilized, triggering service restart"
                    restart_rtsp_service
                    FAILURE_COUNT=0
                    return 0
                fi
            fi
            audio_ok=true
        else
            if [[ "$AUDIO_WAS_MISSING" == "false" ]]; then
                log_warn "Audio device has disappeared!"
            fi
            AUDIO_WAS_MISSING=true
            # Audio loss is recoverable, don't bail out
        fi
    else
        audio_ok=true  # Audio disabled = not a problem
    fi
    
    # 3. Check service is running
    if check_service_running "$RTSP_SERVICE"; then
        service_ok=true
    else
        log_warn "RTSP service is not running"
    fi
    
    # 4. Check stream is accessible (only if service running)
    if [[ "$service_ok" == "true" ]]; then
        if check_rtsp_stream; then
            stream_ok=true
        else
            log_warn "RTSP stream not responding"
        fi
    fi
    
    # Decision logic
    if [[ "$camera_ok" == "true" && "$service_ok" == "true" && "$stream_ok" == "true" ]]; then
        # Everything OK
        if [[ $FAILURE_COUNT -gt 0 ]]; then
            log "Service recovered, resetting failure count"
        fi
        FAILURE_COUNT=0
        return 0
    fi
    
    # Something is wrong
    ((FAILURE_COUNT++)) || true
    log_warn "Health check failed (attempt $FAILURE_COUNT/$MAX_FAILURES)"
    log_warn "  Camera OK: $camera_ok, Service OK: $service_ok, Stream OK: $stream_ok, Audio OK: $audio_ok"
    
    if [[ $FAILURE_COUNT -ge $MAX_FAILURES ]]; then
        log_err "Max failures reached, forcing restart"
        restart_rtsp_service
        FAILURE_COUNT=0
    fi
    
    return 1
}

#---------------------------
# Cleanup
#---------------------------
cleanup() {
    log "Watchdog stopping..."
    exit 0
}

trap cleanup SIGTERM SIGINT SIGHUP

#---------------------------
# Main Loop
#---------------------------
main() {
    log "=========================================="
    log "RTSP Watchdog starting (v1.1.0)"
    log "  Check interval: ${CHECK_INTERVAL}s"
    log "  Video device: $VIDEO_DEVICE"
    log "  Audio enabled: $AUDIO_ENABLE"
    log "  RTSP port: $RTSP_PORT"
    log "  Max failures before restart: $MAX_FAILURES"
    log "  ALSA error threshold: $ALSA_ERROR_THRESHOLD"
    log "=========================================="
    
    # Initial delay to let services start
    sleep 10
    
    while true; do
        perform_health_check || true
        sleep "$CHECK_INTERVAL"
    done
}

main "$@"

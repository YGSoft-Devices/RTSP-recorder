#!/usr/bin/env bash
#===============================================================================
# File: rtsp_recorder.sh
# Location: /usr/local/bin/rtsp_recorder.sh
#
# Purpose:
#   - Record RTSP stream to segmented files using ffmpeg
#   - Runs as a separate service from the RTSP server
#   - Auto-prunes old recordings to maintain minimum free disk space
#   - Enforces maximum recordings folder size (MAX_DISK_MB)
#
# Version: 1.7.0
# Changelog:
#   - 1.7.0: Added MAX_DISK_MB support to limit recordings folder size
#===============================================================================

set -euo pipefail

#---------------------------
# Load configuration
#---------------------------
CONFIG_FILE="/etc/rpi-cam/config.env"
if [[ -f "$CONFIG_FILE" ]]; then
    set -a
    source "$CONFIG_FILE"
    set +a
fi

#---------------------------
# Defaults (can be overridden via config)
#---------------------------
: "${RECORD_ENABLE:=yes}"
: "${RTSP_PORT:=8554}"
: "${RTSP_PATH:=stream}"
: "${RTSP_USER:=}"
: "${RTSP_PASSWORD:=}"
: "${RECORD_DIR:=/var/cache/rpi-cam/recordings}"
: "${SEGMENT_SECONDS:=300}"
: "${MIN_FREE_DISK_MB:=1000}"  # Minimum free space to maintain (default 1GB)
: "${MAX_DISK_MB:=0}"          # Maximum recordings folder size (0 = no limit)
: "${LOG_DIR:=/var/log/rpi-cam}"
: "${PRUNE_CHECK_INTERVAL:=60}"  # Check disk space every 60 seconds

LOG_FILE="${LOG_DIR}/rtsp_recorder.log"
PRUNE_PID=""

#---------------------------
# Build RTSP URL with optional auth
#---------------------------
build_rtsp_url() {
    local url="rtsp://"
    if [[ -n "$RTSP_USER" && -n "$RTSP_PASSWORD" ]]; then
        url+="${RTSP_USER}:${RTSP_PASSWORD}@"
    fi
    url+="127.0.0.1:${RTSP_PORT}/${RTSP_PATH}"
    echo "$url"
}

#---------------------------
# Helpers
#---------------------------
ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_FILE"; }
log_err() { echo "[$(ts)] ERROR: $*" | tee -a "$LOG_FILE" >&2; }
die() { log_err "$*"; exit 1; }

cmd_exists() { command -v "$1" >/dev/null 2>&1; }

setup_fs() {
    mkdir -p "$RECORD_DIR" "$LOG_DIR" 2>/dev/null || true
    touch "$LOG_FILE" 2>/dev/null || true
}

#---------------------------
# Disk space management
# Maintains minimum free disk space by deleting oldest recordings
# Also enforces maximum recordings folder size (MAX_DISK_MB)
#---------------------------
get_free_disk_mb() {
    # Get free space in MB for the partition containing RECORD_DIR
    df -BM "$RECORD_DIR" 2>/dev/null | awk 'NR==2 {gsub(/M/,"",$4); print $4}'
}

get_recordings_size_mb() {
    # Get total size of recordings folder in MB
    du -sm "$RECORD_DIR" 2>/dev/null | awk '{print $1}'
}

#---------------------------
# Log management
# Truncate/rotate large log files to free space
#---------------------------
: "${LOG_MAX_SIZE_MB:=10}"  # Max size for individual log files

prune_logs() {
    local freed=0
    
    # 1. GStreamer/RTSP logs (highest priority - can grow very fast)
    for logfile in "$LOG_DIR"/*.log; do
        [[ -f "$logfile" ]] || continue
        local size_mb
        size_mb="$(du -sm "$logfile" 2>/dev/null | awk '{print $1}')"
        size_mb="${size_mb:-0}"
        
        if [[ "$size_mb" -gt "$LOG_MAX_SIZE_MB" ]]; then
            log "Truncating large log: $logfile (${size_mb}MB > ${LOG_MAX_SIZE_MB}MB)"
            # Keep last 1000 lines, truncate the rest
            tail -n 1000 "$logfile" > "${logfile}.tmp" 2>/dev/null && \
                mv "${logfile}.tmp" "$logfile" 2>/dev/null || \
                : > "$logfile"  # If that fails, just truncate
            freed=$((freed + size_mb - 1))
        fi
    done
    
    # 2. Journald logs (can grow unbounded)
    if command -v journalctl >/dev/null 2>&1; then
        local journal_mb
        journal_mb="$(journalctl --disk-usage 2>/dev/null | grep -oP '\d+\.?\d*M' | head -1 | tr -d 'M' | cut -d. -f1)"
        journal_mb="${journal_mb:-0}"
        
        if [[ "$journal_mb" -gt 50 ]]; then
            log "Vacuuming journald: ${journal_mb}MB > 50MB"
            journalctl --vacuum-size=20M --vacuum-time=3d >/dev/null 2>&1 || true
            freed=$((freed + journal_mb - 20))
        fi
    fi
    
    # 3. APT cache (can be large and is regenerable)
    local apt_cache_mb
    apt_cache_mb="$(du -sm /var/cache/apt 2>/dev/null | awk '{print $1}')"
    apt_cache_mb="${apt_cache_mb:-0}"
    
    if [[ "$apt_cache_mb" -gt 100 ]]; then
        log "Cleaning APT cache: ${apt_cache_mb}MB"
        # Remove downloaded package files directly
        rm -rf /var/cache/apt/archives/*.deb 2>/dev/null || true
        rm -rf /var/cache/apt/archives/partial/* 2>/dev/null || true
        rm -f /var/cache/apt/*.bin 2>/dev/null || true
        freed=$((freed + apt_cache_mb - 1))
    fi
    
    # 4. Old log files (*.log.1, *.log.gz, etc.)
    find /var/log -type f \( -name "*.gz" -o -name "*.1" -o -name "*.old" \) -delete 2>/dev/null || true
    
    # 5. Temporary files older than 1 day
    find /tmp -type f -mtime +1 -delete 2>/dev/null || true
    
    if [[ "$freed" -gt 0 ]]; then
        log "Freed approximately ${freed}MB from logs/cache"
    fi
}

prune_if_needed() {
    if [[ "$MIN_FREE_DISK_MB" -le 0 ]]; then
        return 0
    fi

    local free_mb
    free_mb="$(get_free_disk_mb)" || free_mb=0
    free_mb="${free_mb:-0}"
    # Ensure it's a number
    [[ "$free_mb" =~ ^[0-9]+$ ]] || free_mb=0

    if [[ "$free_mb" -ge "$MIN_FREE_DISK_MB" ]]; then
        return 0
    fi

    log "Disk space low: ${free_mb}MB free < ${MIN_FREE_DISK_MB}MB required"
    
    # Step 1: Try cleaning logs and cache first (non-destructive)
    prune_logs || true
    
    free_mb="$(get_free_disk_mb)" || free_mb=0
    free_mb="${free_mb:-0}"
    [[ "$free_mb" =~ ^[0-9]+$ ]] || free_mb=0
    
    if [[ "$free_mb" -ge "$MIN_FREE_DISK_MB" ]]; then
        log "Space recovered from logs/cache: ${free_mb}MB free"
        return 0
    fi
    
    # Step 2: Delete oldest recordings if still not enough
    log "Still need more space, pruning recordings..."

    while [[ "$free_mb" -lt "$MIN_FREE_DISK_MB" ]]; do
        local oldest
        # Find oldest file by modification time
        oldest="$(find "$RECORD_DIR" \( -name "*.ts" -o -name "*.mp4" -o -name "*.mkv" \) -type f 2>/dev/null | \
                  xargs -r ls -1t 2>/dev/null | tail -1)" || oldest=""
        
        if [[ -z "$oldest" ]]; then
            log_err "No more recordings to delete, but free space still low: ${free_mb}MB"
            break
        fi

        local file_size
        file_size="$(du -sm "$oldest" 2>/dev/null | awk '{print $1}')" || file_size=0
        file_size="${file_size:-0}"
        log "Deleting oldest recording: $oldest (${file_size}MB)"
        rm -f "$oldest" || true

        free_mb="$(get_free_disk_mb)" || free_mb=0
        free_mb="${free_mb:-0}"
        [[ "$free_mb" =~ ^[0-9]+$ ]] || free_mb=0
    done

    log "After pruning: ${free_mb}MB free"
}

#---------------------------
# Max disk size enforcement
# Deletes oldest recordings when folder exceeds MAX_DISK_MB
#---------------------------
prune_if_max_exceeded() {
    if [[ "$MAX_DISK_MB" -le 0 ]]; then
        return 0
    fi

    local used_mb
    used_mb="$(get_recordings_size_mb)" || used_mb=0
    used_mb="${used_mb:-0}"
    [[ "$used_mb" =~ ^[0-9]+$ ]] || used_mb=0

    if [[ "$used_mb" -le "$MAX_DISK_MB" ]]; then
        return 0
    fi

    log "Recordings folder size exceeded: ${used_mb}MB > ${MAX_DISK_MB}MB limit"

    while [[ "$used_mb" -gt "$MAX_DISK_MB" ]]; do
        local oldest
        # Find oldest file by modification time
        oldest="$(find "$RECORD_DIR" \( -name "*.ts" -o -name "*.mp4" -o -name "*.mkv" \) -type f 2>/dev/null | \
                  xargs -r ls -1t 2>/dev/null | tail -1)" || oldest=""
        
        if [[ -z "$oldest" ]]; then
            log_err "No more recordings to delete, but folder still exceeds limit: ${used_mb}MB"
            break
        fi

        local file_size
        file_size="$(du -sm "$oldest" 2>/dev/null | awk '{print $1}')" || file_size=0
        file_size="${file_size:-0}"
        log "Deleting oldest recording (max size limit): $oldest (${file_size}MB)"
        rm -f "$oldest" || true

        used_mb="$(get_recordings_size_mb)" || used_mb=0
        used_mb="${used_mb:-0}"
        [[ "$used_mb" =~ ^[0-9]+$ ]] || used_mb=0
    done

    log "After max-size pruning: ${used_mb}MB used (limit: ${MAX_DISK_MB}MB)"
}

#---------------------------
# Background pruning loop
# Runs in background during recording to check disk space periodically
#---------------------------
start_prune_loop() {
    (
        # Redirect stdin from /dev/null to prevent blocking on read
        exec </dev/null
        while true; do
            sleep "$PRUNE_CHECK_INTERVAL"
            prune_if_needed       # Check MIN_FREE_DISK_MB (free space)
            prune_if_max_exceeded # Check MAX_DISK_MB (folder size limit)
        done
    ) &
    PRUNE_PID=$!
    log "Started background pruning loop (PID: $PRUNE_PID, interval: ${PRUNE_CHECK_INTERVAL}s)"
}

stop_prune_loop() {
    if [[ -n "$PRUNE_PID" ]] && kill -0 "$PRUNE_PID" 2>/dev/null; then
        kill "$PRUNE_PID" 2>/dev/null || true
        wait "$PRUNE_PID" 2>/dev/null || true
        log "Stopped background pruning loop"
    fi
    PRUNE_PID=""
}

#---------------------------
# Wait for RTSP server
#---------------------------
wait_for_rtsp() {
    local rtsp_url
    rtsp_url="$(build_rtsp_url)"
    local max_wait=60
    local waited=0

    # Log URL without password for security
    local log_url="rtsp://127.0.0.1:${RTSP_PORT}/${RTSP_PATH}"
    [[ -n "$RTSP_USER" ]] && log_url="rtsp://${RTSP_USER}:***@127.0.0.1:${RTSP_PORT}/${RTSP_PATH}"
    log "Waiting for RTSP server at $log_url..."

    while [[ $waited -lt $max_wait ]]; do
        # Try to probe the stream
        if ffprobe -v quiet -rtsp_transport tcp "$rtsp_url" -show_streams 2>/dev/null | grep -q "codec_type"; then
            log "RTSP server is ready"
            return 0
        fi
        sleep 2
        waited=$((waited + 2))
    done

    log_err "RTSP server not available after ${max_wait}s"
    return 1
}

#---------------------------
# Record stream
#---------------------------
record_stream() {
    local rtsp_url
    rtsp_url="$(build_rtsp_url)"
    
    # Log URL without password for security
    local log_url="rtsp://127.0.0.1:${RTSP_PORT}/${RTSP_PATH}"
    [[ -n "$RTSP_USER" ]] && log_url="rtsp://${RTSP_USER}:***@127.0.0.1:${RTSP_PORT}/${RTSP_PATH}"
    log "Starting recording from: $log_url"
    log "Output directory: $RECORD_DIR"
    log "Segment duration: ${SEGMENT_SECONDS}s"
    log "Disk limits: MIN_FREE=${MIN_FREE_DISK_MB}MB, MAX_FOLDER=${MAX_DISK_MB}MB (0=unlimited)"
    
    # Use ffmpeg with segment muxer for robust recordings
    # - segment_time: duration of each segment
    # - segment_format: output format (mpegts for robustness)
    # - reset_timestamps: reset pts/dts for each segment
    # - strftime: use timestamp in filename
    
    local output_pattern="${RECORD_DIR}/rec_%Y%m%d_%H%M%S.ts"
    
    # ffmpeg options:
    # -rtsp_transport tcp: use TCP for more reliable transport
    # -analyzeduration: analyze longer to properly detect audio codec parameters
    # -probesize: read more data for codec detection (helps with audio)
    # -fflags +genpts: generate presentation timestamps (fixes audio sync issues)
    # -use_wallclock_as_timestamps 1: use system time for timestamps
    # -map 0:v -map 0:a?: map video (required) and audio (optional with ?)
    # -c:v copy: copy video without re-encoding
    # -c:a aac -b:a 64k: re-encode audio as AAC 64kbps (fixes RTSP AAC metadata issues)
    # -f segment: segment muxer
    # -segment_time: segment duration
    # -segment_format mpegts: use MPEG-TS (robust against power loss)
    # -strftime 1: use strftime patterns in output filename
    # -reset_timestamps 1: reset timestamps at segment boundaries
    
    ffmpeg -hide_banner -loglevel warning \
        -rtsp_transport tcp \
        -analyzeduration 10000000 \
        -probesize 10000000 \
        -fflags +genpts \
        -use_wallclock_as_timestamps 1 \
        -i "$rtsp_url" \
        -map 0:v -map 0:a? \
        -c:v copy \
        -c:a aac -b:a 64k \
        -f segment \
        -segment_time "$SEGMENT_SECONDS" \
        -segment_format mpegts \
        -strftime 1 \
        -reset_timestamps 1 \
        "$output_pattern" \
        2>&1 | while read -r line; do
            log "ffmpeg: $line"
        done

    local exit_code=${PIPESTATUS[0]}
    log "ffmpeg exited with code: $exit_code"
    return $exit_code
}

#---------------------------
# Main
#---------------------------
main() {
    setup_fs
    
    log "=========================================="
    log "RTSP Recorder v1.6.0"
    log "=========================================="
    
    # Check if recording is enabled
    if [[ "$RECORD_ENABLE" != "yes" ]]; then
        log "Recording disabled (RECORD_ENABLE=${RECORD_ENABLE})"
        log "Exiting. Set RECORD_ENABLE=yes to enable recording."
        exit 0
    fi

    # Check ffmpeg
    cmd_exists ffmpeg || die "ffmpeg not found. Install with: sudo apt install ffmpeg"
    cmd_exists ffprobe || die "ffprobe not found. Install with: sudo apt install ffmpeg"

    log "Recording enabled"
    log "Config: RTSP=:${RTSP_PORT}/${RTSP_PATH}"
    log "Config: RECORD_DIR=${RECORD_DIR}"
    log "Config: SEGMENT_SECONDS=${SEGMENT_SECONDS}"
    log "Config: MIN_FREE_DISK_MB=${MIN_FREE_DISK_MB}"
    log "Config: PRUNE_CHECK_INTERVAL=${PRUNE_CHECK_INTERVAL}s"

    # Wait for RTSP server
    if ! wait_for_rtsp; then
        die "RTSP server not available"
    fi

    # Prune old recordings if needed (initial cleanup)
    prune_if_needed
    
    # Start background pruning loop
    start_prune_loop

    # Main recording loop - restart on failure
    while true; do
        log "Starting recording session..."
        
        if record_stream; then
            log "Recording ended normally"
        else
            log_err "Recording failed, will retry in 10s..."
        fi

        # Small delay before restart
        sleep 10
    done
}

# Handle signals for clean shutdown
cleanup() {
    log "Received shutdown signal, stopping..."
    stop_prune_loop
    exit 0
}
trap cleanup SIGTERM SIGINT

main "$@"

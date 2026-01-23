#!/usr/bin/env bash
#===============================================================================
# File: rpi_av_rtsp_recorder.sh
# Location: /usr/local/bin/rpi_av_rtsp_recorder.sh
#
# Target: Raspberry Pi OS Trixie (64-bit) - Raspberry Pi 3B+/4/5
#
# Purpose:
#   - Auto-detect camera source (CSI/libcamera OR USB/V4L2)
#   - Auto-detect USB microphone (ALSA) 
#   - Serve RTSP stream (H264 video + optional AAC audio)
#   - Record locally in segments (robust against power loss)
#
# Version: 2.12.8
# Changelog:
#   - 2.12.8: Export overlay config to CSI RTSP server
#   - 2.12.7: Disable overlay gracefully when textoverlay/clockoverlay missing
#   - 2.12.6: Fix overlay crash when OVERLAY_SUPPORTED not initialized
#   - 2.12.5: Added configurable RTSP overlay (text + datetime) for USB/legacy CSI
#   - 2.12.4: Added VIDEO_FORMAT to force MJPG/YUYV/H264 when desired
#   - 2.12.3: v4l2h264enc now honors H264_BITRATE_KBPS (no hardcoded 4 Mbps)
#   - 2.12.2: Export H264_PROFILE/H264_QP for CSI encoder tuning
#   - 2.11.2: Added timeout to arecord --dump-hw-params to prevent blocking when device is busy
#   - 2.11.1: Fixed USB camera detection when v4l2-ctl returns multiple Driver lines
#            - Added head -1 to usb_cam_present() driver extraction
#   - 2.11.0: Audio gain/amplification support
#            - New AUDIO_GAIN config (0.0 to 3.0, 1.0 = no change)
#            - Uses GStreamer volume element in audio pipeline
#            - Allows boosting weak microphones or reducing loud sources
#   - 2.10.0: CSI camera tuning support
#            - Reads saved tuning from /etc/rpi-cam/csi_tuning.json
#            - Applies Brightness, Contrast, Saturation, Sharpness to libcamerasrc
#            - Maps Picamera2 control names to libcamerasrc properties
#   - 2.9.0: Unified CAMERA_TYPE selector
#            - New CAMERA_TYPE config (auto/usb/csi) replaces USB_ENABLE/CSI_ENABLE
#            - Legacy support: USB_ENABLE and CSI_ENABLE still work for compatibility
#   - 2.8.1: Fixed audio detection with set -e
#            - detect_audio_dev now uses || true to prevent script exit
#            - Allows script to continue when no audio device is found
#   - 2.8.0: Improved CSI/USB camera detection
#            - Fixed unicam driver being detected as USB camera
#            - Now properly distinguishes uvcvideo (USB) from unicam (CSI)
#            - Added support for rpicam-hello (replaces libcamera-hello)
#            - CSI cameras now correctly use libcamerasrc pipeline
#   - 2.7.0: USB bus optimization for Pi 3B+ stability
#            - v4l2src: added io-mode=2 (mmap) and do-timestamp=true
#            - alsasrc: added buffer-time=200ms, latency-time=25ms
#            - Added queue elements to absorb USB bandwidth variations
#            - Prefer voaacenc (lighter) over avenc_aac for audio encoding
#   - 2.6.0: Added RTSP authentication support (Basic auth)
#            - RTSP_USER and RTSP_PASSWORD environment variables
#            - If both are set, authentication is required to access the stream
#            - Requires recompiled test-launch with auth support
#   - 2.5.0: Fixed hardware encoding detection (v4l2h264enc)
#            - videotestsrc test was giving false negatives on Pi 3B+
#            - Now checks for /dev/video11 and bcm2835_codec module
#            - Changed pixel format from NV12 to I420 for MJPEG camera compatibility
#            - Hardware encoding now works: ~17% CPU vs ~170% with software!
#   - 2.4.0: Log cleanup at boot (especially GStreamer debug logs)
#            - Prevents log files from growing indefinitely
#   - 2.3.0: Dynamic audio device detection by name pattern (AUDIO_DEVICE_NAME)
#            - Fixes random device ID changes on Debian Bookworm/Trixie
#   - 2.2.0: Read config from config.env (web manager) with fallback to recorder.conf
#   - 2.1.0: Hardware H264 encoding via v4l2h264enc (VideoCore IV GPU)
#            - Prioritizes hardware encoder over software (x264enc)
#            - Higher resolution possible with low CPU usage
#   - 2.0.0: Rewrite for Trixie compatibility + better USB camera support
#   - 1.0.0: Initial release
#
# Notes:
#   - v4l2h264enc uses VideoCore IV GPU = very low CPU, high quality
#   - USB cameras outputting MJPEG work best (lower CPU for decode)
#   - If hardware encoder unavailable, falls back to x264enc (high CPU!)
#   - CSI cameras with libcamera are preferred when available
#===============================================================================

set -euo pipefail

#---------------------------
# Defaults (override via env or /etc/rpi-cam/recorder.conf)
#---------------------------
: "${RTSP_PORT:=8554}"
: "${RTSP_PATH:=stream}"
# RTSP Authentication (optional)
# If both RTSP_USER and RTSP_PASSWORD are set, authentication is required
# If either is empty, the stream is accessible without authentication
: "${RTSP_USER:=}"
: "${RTSP_PASSWORD:=}"

# Default to safe resolution for software encoding (Pi 3B+)
# If hardware encoding works, you can increase to 1280x720@20fps
: "${VIDEO_WIDTH:=640}"
: "${VIDEO_HEIGHT:=480}"
: "${VIDEO_FPS:=15}"
: "${VIDEO_DEVICE:=/dev/video0}"
# Preferred USB format: auto, MJPG, YUYV, H264 (optional)
: "${VIDEO_FORMAT:=auto}"

# Overlay settings (USB/legacy CSI only)
: "${VIDEO_OVERLAY_ENABLE:=no}"
: "${VIDEO_OVERLAY_TEXT:=}"
: "${VIDEO_OVERLAY_POSITION:=top-left}"
: "${VIDEO_OVERLAY_SHOW_DATETIME:=no}"
: "${VIDEO_OVERLAY_DATETIME_FORMAT:=%Y-%m-%d %H:%M:%S}"
: "${VIDEO_OVERLAY_CLOCK_POSITION:=bottom-right}"
: "${VIDEO_OVERLAY_FONT_SIZE:=24}"

# Track overlay compatibility for current pipeline
OVERLAY_SUPPORTED=1
# Camera type: auto, usb, csi
: "${CAMERA_TYPE:=auto}"
# Legacy support (deprecated, use CAMERA_TYPE instead)
: "${CSI_ENABLE:=}"
: "${USB_ENABLE:=}"

: "${RECORD_ENABLE:=yes}"
: "${RECORD_DIR:=/var/cache/rpi-cam/recordings}"
: "${SEGMENT_SECONDS:=300}"
: "${MAX_DISK_MB:=0}"

: "${AUDIO_ENABLE:=auto}"
: "${AUDIO_RATE:=48000}"
: "${AUDIO_CHANNELS:=1}"
: "${AUDIO_BITRATE_KBPS:=64}"
: "${AUDIO_DEVICE:=auto}"
# Audio device name pattern for dynamic detection (avoids ID changes between reboots)
# Example: "LifeCam" or "HD5000" or "USB" for any USB audio
: "${AUDIO_DEVICE_NAME:=}"
# Audio gain/amplification (0.0 to 3.0, 1.0 = no change)
# Use this to boost weak microphones or reduce too loud sources
: "${AUDIO_GAIN:=1.0}"

# H264 software encoding settings (x264enc)
# Optimized for Pi 3B+ - keep bitrate low to reduce CPU load
: "${H264_BITRATE_KBPS:=1200}"
: "${H264_KEYINT:=30}"
: "${H264_PROFILE:=}"
: "${H264_QP:=}"

: "${GST_DEBUG_LEVEL:=2}"
: "${LOG_DIR:=/var/log/rpi-cam}"
: "${LOG_FILE:=${LOG_DIR}/rpi_av_rtsp_recorder.log}"

#---------------------------
# Helpers
#---------------------------
ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*"; }
log_err() { echo "[$(ts)] ERROR: $*" >&2; }
die() { log_err "$*"; exit 1; }

cmd_exists() { command -v "$1" >/dev/null 2>&1; }

# Load config file if exists (try both locations)
# Priority: config.env (web manager) > recorder.conf (legacy)
CONFIG_FILE="/etc/rpi-cam/config.env"
if [[ ! -f "$CONFIG_FILE" ]]; then
  CONFIG_FILE="/etc/rpi-cam/recorder.conf"
fi
if [[ -f "$CONFIG_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  log "Loaded config from: $CONFIG_FILE"
fi

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Run as root: sudo $0"
  fi
}

overlay_alignment_from_position() {
  local pos="$1"
  case "$pos" in
    top-left) echo "top left" ;;
    top-right) echo "top right" ;;
    bottom-left) echo "bottom left" ;;
    bottom-right) echo "bottom right" ;;
    *) echo "top left" ;;
  esac
}

build_video_overlay() {
  if [[ "${VIDEO_OVERLAY_ENABLE}" != "yes" ]]; then
    echo ""
    return 0
  fi

  if [[ "${OVERLAY_SUPPORTED}" -ne 1 ]]; then
    log "Overlay enabled but source is H264 direct; overlay disabled (would require re-encode)" >&2
    echo ""
    return 0
  fi

  local overlay_chain=""
  local font_desc="Sans ${VIDEO_OVERLAY_FONT_SIZE}"

  if [[ "${VIDEO_OVERLAY_SHOW_DATETIME}" == "yes" ]]; then
    if ! gst-inspect-1.0 clockoverlay >/dev/null 2>&1; then
      log "Overlay clockoverlay not available; date/time overlay disabled" >&2
    else
      read -r clock_valign clock_halign <<<"$(overlay_alignment_from_position "${VIDEO_OVERLAY_CLOCK_POSITION}")"
      overlay_chain="clockoverlay time-format=\"${VIDEO_OVERLAY_DATETIME_FORMAT}\" valignment=${clock_valign} halignment=${clock_halign} shaded-background=true font-desc=\"${font_desc}\""
    fi
  fi

  local overlay_text="${VIDEO_OVERLAY_TEXT}"
  if [[ -n "${overlay_text}" ]]; then
    if ! gst-inspect-1.0 textoverlay >/dev/null 2>&1; then
      log "Overlay textoverlay not available; text overlay disabled" >&2
    else
      overlay_text="${overlay_text//\{CAMERA_TYPE\}/${CAM_MODE}}"
      overlay_text="${overlay_text//\{VIDEO_DEVICE\}/${VIDEO_DEVICE}}"
      overlay_text="${overlay_text//\{VIDEO_RESOLUTION\}/${VIDEO_WIDTH}x${VIDEO_HEIGHT}}"
      overlay_text="${overlay_text//\{VIDEO_FPS\}/${VIDEO_FPS}}"
      overlay_text="${overlay_text//\{VIDEO_FORMAT\}/${VIDEO_FORMAT}}"
      overlay_text="${overlay_text//\"/ }"
      overlay_text="${overlay_text//\'/ }"
      read -r text_valign text_halign <<<"$(overlay_alignment_from_position "${VIDEO_OVERLAY_POSITION}")"
      if [[ -n "${overlay_chain}" ]]; then
        overlay_chain="${overlay_chain} ! "
      fi
      overlay_chain="${overlay_chain}textoverlay text=\"${overlay_text}\" valignment=${text_valign} halignment=${text_halign} shaded-background=true font-desc=\"${font_desc}\""
    fi
  fi

  echo "${overlay_chain}"
}

setup_fs() {
  mkdir -p "$RECORD_DIR" "$LOG_DIR" 2>/dev/null || true
  touch "$LOG_FILE" 2>/dev/null || true
  chmod 755 "$RECORD_DIR" "$LOG_DIR" 2>/dev/null || true
  chmod 640 "$LOG_FILE" 2>/dev/null || true
}

setup_logging() {
  exec > >(tee -a "$LOG_FILE") 2>&1
}

# Cleanup old/large logs at boot to prevent disk filling
# GStreamer debug logs can grow very quickly (100MB+ per day)
cleanup_logs() {
  local max_log_size_mb=10  # Maximum log file size in MB
  local max_log_age_days=7  # Maximum log age in days
  
  log "Cleaning up old logs..."
  
  # Truncate main log if too large (keep last 1000 lines)
  if [[ -f "$LOG_FILE" ]]; then
    local size_kb=$(du -k "$LOG_FILE" 2>/dev/null | cut -f1)
    if [[ ${size_kb:-0} -gt $((max_log_size_mb * 1024)) ]]; then
      log "Log file too large (${size_kb}KB), truncating..."
      tail -n 1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
    fi
  fi
  
  # Remove old log files
  find "$LOG_DIR" -type f -name "*.log" -mtime +${max_log_age_days} -delete 2>/dev/null || true
  find "$LOG_DIR" -type f -name "*.log.*" -mtime +${max_log_age_days} -delete 2>/dev/null || true
  
  # Clean GStreamer debug output (these can be HUGE)
  find "$LOG_DIR" -type f -name "gstreamer*.log" -delete 2>/dev/null || true
  find "$LOG_DIR" -type f -name "gst_*.log" -delete 2>/dev/null || true
  
  # Clean any core dumps
  find "$LOG_DIR" -type f -name "core.*" -delete 2>/dev/null || true
  find /tmp -type f -name "gst-*" -mtime +1 -delete 2>/dev/null || true
  
  # Truncate journald logs for this service (keep last 10MB)
  journalctl --vacuum-size=50M 2>/dev/null || true
  
  log "Log cleanup complete"
}

#---------------------------
# Camera detection
#---------------------------
# Check if USB camera is present and working (NOT CSI/unicam)
usb_cam_present() {
  # First check if device exists
  [[ ! -e "$VIDEO_DEVICE" ]] && return 1
  
  # Check the driver - unicam/bcm2835-* are CSI, not USB
  # Use head -1 because v4l2-ctl can output multiple "Driver name" lines
  local driver
  driver=$(v4l2-ctl -d "$VIDEO_DEVICE" --info 2>/dev/null | grep "Driver name" | head -1 | awk -F: '{print $2}' | tr -d ' ')
  
  case "$driver" in
    unicam|bcm2835-isp|bcm2835-codec)
      # This is a CSI camera or ISP device, NOT USB
      return 1
      ;;
    uvcvideo|gspca*|pwc)
      # Real USB camera drivers
      return 0
      ;;
    *)
      # Unknown driver, check if it appears on USB bus
      if lsusb 2>/dev/null | grep -qi "camera\|webcam\|video"; then
        return 0
      fi
      return 1
      ;;
  esac
}

# Check if CSI camera is available via libcamera
csi_cam_possible() {
  local output
  # Check if rpicam-hello or libcamera-hello exists
  if cmd_exists rpicam-hello; then
    # Verify a camera is actually detected (with timeout)
    output=$(timeout 5 rpicam-hello --list-cameras 2>&1 || true)
    if echo "$output" | grep -q "Available cameras"; then
      log "CSI camera detected via rpicam-hello" >&2
      return 0
    fi
  elif cmd_exists libcamera-hello; then
    output=$(timeout 5 libcamera-hello --list-cameras 2>&1 || true)
    if echo "$output" | grep -q "Available cameras"; then
      log "CSI camera detected via libcamera-hello" >&2
      return 0
    fi
  fi
  log "No CSI camera detected" >&2
  return 1
}

# Get camera formats
get_camera_formats() {
  v4l2-ctl -d "$VIDEO_DEVICE" --list-formats-ext 2>/dev/null || true
}

# Check if camera supports specific format
camera_supports_format() {
  local format="$1"
  get_camera_formats | grep -qi "$format"
}

# Select camera mode: "usb" or "csi" or "none"
select_camera_mode() {
  # New unified CAMERA_TYPE takes priority
  if [[ "$CAMERA_TYPE" == "usb" ]]; then
    echo "usb"
    return
  elif [[ "$CAMERA_TYPE" == "csi" ]]; then
    echo "csi"
    return
  fi
  
  # Legacy support: check USB_ENABLE and CSI_ENABLE if CAMERA_TYPE is auto
  local usb_ok=0 csi_ok=0

  # Legacy USB_ENABLE handling
  if [[ "$USB_ENABLE" == "yes" ]]; then
    usb_ok=1
  elif [[ "$USB_ENABLE" == "no" ]]; then
    usb_ok=0
  else
    usb_cam_present && usb_ok=1
  fi

  # Legacy CSI_ENABLE handling
  if [[ "$CSI_ENABLE" == "yes" ]]; then
    csi_ok=1
  elif [[ "$CSI_ENABLE" == "no" ]]; then
    csi_ok=0
  else
    csi_cam_possible && csi_ok=1
  fi

  # Priority: USB if present, else CSI
  if [[ $usb_ok -eq 1 ]]; then
    echo "usb"
  elif [[ $csi_ok -eq 1 ]]; then
    echo "csi"
  else
    echo "none"
  fi
}

#---------------------------
# Audio detection
#---------------------------
# Detect audio device dynamically by name pattern
# This handles the random device ID changes on Debian Bookworm/Trixie
detect_audio_dev() {
  # If explicit device path given (not "auto"), use it directly
  if [[ "$AUDIO_DEVICE" != "auto" && -n "$AUDIO_DEVICE" ]]; then
    # Verify the device exists (timeout to prevent blocking if device is busy)
    if timeout 3 arecord -D "$AUDIO_DEVICE" --dump-hw-params 2>/dev/null | grep -q "ACCESS:"; then
      log "Using configured audio device: $AUDIO_DEVICE" >&2
      echo "$AUDIO_DEVICE"
      return 0
    else
      log "Configured audio device $AUDIO_DEVICE not available, falling back to auto-detection" >&2
    fi
  fi

  if ! cmd_exists arecord; then
    echo ""
    return 1
  fi

  local card=""
  local arecord_output
  arecord_output="$(arecord -l 2>/dev/null)"

  # Priority 1: Search by device name pattern (AUDIO_DEVICE_NAME)
  if [[ -n "${AUDIO_DEVICE_NAME:-}" ]]; then
    card="$(echo "$arecord_output" | awk -v pattern="$AUDIO_DEVICE_NAME" '
      /card [0-9]+:/ && tolower($0) ~ tolower(pattern) {
        gsub("card ",""); gsub(":.*",""); print $1; exit
      }')"
    if [[ -n "$card" ]]; then
      log "Found audio device by name pattern '$AUDIO_DEVICE_NAME': card $card" >&2
      echo "plughw:${card},0"
      return 0
    fi
    log "Warning: Audio device pattern '$AUDIO_DEVICE_NAME' not found, trying USB fallback" >&2
  fi

  # Priority 2: Any USB audio device
  card="$(echo "$arecord_output" | awk '/card [0-9]+:.*USB/{gsub("card ",""); gsub(":.*",""); print $1; exit}')"
  if [[ -n "$card" ]]; then
    log "Found USB audio device: card $card" >&2
    echo "plughw:${card},0"
    return 0
  fi

  # Priority 3: Any capture device (fallback)
  card="$(echo "$arecord_output" | awk '/card [0-9]+:/{gsub("card ",""); gsub(":.*",""); print $1; exit}')"
  if [[ -n "$card" ]]; then
    log "Found audio capture device (fallback): card $card" >&2
    echo "plughw:${card},0"
    return 0
  fi

  log "No audio capture device found" >&2
  echo ""
  return 1
}

#---------------------------
# CSI Camera Tuning
#---------------------------

# Mapping from Picamera2 control names to libcamerasrc property names
# Format: "PicameraName:libcameraProperty"
CSI_CONTROL_MAPPING=(
  "Brightness:brightness"
  "Contrast:contrast"
  "Saturation:saturation"
  "Sharpness:sharpness"
  "ExposureTime:exposure-time"
  "ExposureValue:exposure-value"
  "AnalogueGain:analogue-gain"
  "AeEnable:ae-enable"
  "AwbEnable:awb-enable"
  "AwbMode:awb-mode"
  "AeMeteringMode:ae-metering-mode"
  "AeExposureMode:ae-exposure-mode"
  "AeConstraintMode:ae-constraint-mode"
  "NoiseReductionMode:noise-reduction-mode"
)

# Build libcamerasrc options from saved CSI tuning
build_csi_libcamerasrc_options() {
  local tuning_file="/etc/rpi-cam/csi_tuning.json"
  local options=""
  
  if [[ ! -f "$tuning_file" ]]; then
    echo ""
    return 0
  fi
  
  # Read JSON and extract values
  local json_content
  json_content=$(cat "$tuning_file" 2>/dev/null) || return 0
  
  for mapping in "${CSI_CONTROL_MAPPING[@]}"; do
    local picam_name="${mapping%%:*}"
    local libcam_prop="${mapping##*:}"
    
    # Extract value from JSON using grep/sed (simple parsing)
    local value
    value=$(echo "$json_content" | grep -o "\"${picam_name}\"[[:space:]]*:[[:space:]]*[^,}]*" | sed 's/.*:[[:space:]]*//' | tr -d '"' | head -1)
    
    if [[ -n "$value" && "$value" != "null" ]]; then
      # Boolean handling
      if [[ "$value" == "true" ]]; then
        value="1"
      elif [[ "$value" == "false" ]]; then
        value="0"
      fi
      
      options+="${libcam_prop}=${value} "
      log "CSI tuning: ${libcam_prop}=${value}" >&2
    fi
  done
  
  echo "$options"
}

#---------------------------
# Pipeline building
#---------------------------
build_video_source() {
  local mode="$1"
  OVERLAY_SUPPORTED=1
  
  if [[ "$mode" == "usb" ]]; then
    # USB camera - check supported formats
    # io-mode=2 (mmap) is more efficient for USB cameras
    # do-timestamp=true ensures proper frame timing
    local requested_format="${VIDEO_FORMAT:-auto}"
    requested_format=$(echo "$requested_format" | tr '[:lower:]' '[:upper:]')

    if [[ -n "$requested_format" && "$requested_format" != "AUTO" ]]; then
      case "$requested_format" in
        MJPG|MJPEG|MOTION-JPEG)
          if camera_supports_format "MJPG\|Motion-JPEG"; then
            log "USB camera: forcing MJPEG format" >&2
            echo "v4l2src device=${VIDEO_DEVICE} io-mode=2 do-timestamp=true ! image/jpeg,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! jpegdec ! videoconvert"
            return 0
          fi
          log "Requested MJPEG not supported, falling back to auto" >&2
          ;;
        H264|H.264)
          if camera_supports_format "H264\|H.264"; then
            log "USB camera: forcing H264 format" >&2
            OVERLAY_SUPPORTED=0
            echo "v4l2src device=${VIDEO_DEVICE} ! video/x-h264,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1"
            return 0
          fi
          log "Requested H264 not supported, falling back to auto" >&2
          ;;
        YUYV|YUY2)
          if camera_supports_format "YUYV"; then
            log "USB camera: forcing YUYV format" >&2
            echo "v4l2src device=${VIDEO_DEVICE} ! video/x-raw,format=YUY2,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! videoconvert"
            return 0
          fi
          log "Requested YUYV not supported, falling back to auto" >&2
          ;;
        *)
          log "Unknown VIDEO_FORMAT '${VIDEO_FORMAT}', falling back to auto" >&2
          ;;
      esac
    fi

    if camera_supports_format "MJPG\|Motion-JPEG"; then
      log "USB camera supports MJPEG - using it (recommended)" >&2
      # MJPEG is more efficient to decode than raw YUYV
      echo "v4l2src device=${VIDEO_DEVICE} io-mode=2 do-timestamp=true ! image/jpeg,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! jpegdec ! videoconvert"
    elif camera_supports_format "H264\|H.264"; then
      log "USB camera supports H264 output (best performance)" >&2
      OVERLAY_SUPPORTED=0
      echo "v4l2src device=${VIDEO_DEVICE} ! video/x-h264,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1"
    elif camera_supports_format "YUYV"; then
      log "USB camera supports YUYV raw - using it (CPU intensive)" >&2
      echo "v4l2src device=${VIDEO_DEVICE} ! video/x-raw,format=YUY2,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! videoconvert"
    else
      log "Unknown camera format - trying auto caps" >&2
      echo "v4l2src device=${VIDEO_DEVICE} ! videoconvert"
    fi
  elif [[ "$mode" == "csi" ]]; then
    # CSI camera via libcamera
    if gst-inspect-1.0 libcamerasrc >/dev/null 2>&1; then
      log "CSI camera: using libcamerasrc" >&2
      
      # Build libcamerasrc options from saved tuning
      local csi_opts=""
      csi_opts=$(build_csi_libcamerasrc_options)
      
      if [[ -n "$csi_opts" ]]; then
        log "Applying CSI tuning: $csi_opts" >&2
        echo "libcamerasrc ${csi_opts} ! video/x-raw,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! videoconvert"
      else
        echo "libcamerasrc ! video/x-raw,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! videoconvert"
      fi
    else
      die "CSI camera selected but libcamerasrc not available"
    fi
  else
    die "No camera source available"
  fi
}

# Check if source already outputs H264
source_outputs_h264() {
  local mode="$1"
  if [[ "$mode" == "usb" ]] && camera_supports_format "H264\|H.264"; then
    return 0
  fi
  return 1
}

# Test if v4l2h264enc actually works (not just exists)
# Note: Testing with videotestsrc often fails on Pi 3B+ due to memory allocation
# even when the encoder works fine with real camera input.
# We now check for the encoder device and required modules instead.
test_hw_encoder_works() {
  log "Testing if v4l2h264enc is available..." >&2
  
  # Check 1: v4l2h264enc plugin must exist
  if ! gst-inspect-1.0 v4l2h264enc >/dev/null 2>&1; then
    log "v4l2h264enc plugin not found" >&2
    return 1
  fi
  
  # Check 2: /dev/video11 (bcm2835-codec-encode) must exist
  if [[ ! -e /dev/video11 ]]; then
    log "Hardware encoder device /dev/video11 not found" >&2
    return 1
  fi
  
  # Check 3: Required kernel modules must be loaded
  if ! lsmod | grep -q "bcm2835_codec"; then
    log "bcm2835_codec kernel module not loaded" >&2
    return 1
  fi
  
  # Check 4: Verify it's the encoder (not decoder)
  local encoder_info
  encoder_info=$(v4l2-ctl -d /dev/video11 --info 2>/dev/null || true)
  if ! echo "$encoder_info" | grep -qi "encode"; then
    log "Warning: /dev/video11 may not be encoder, trying anyway" >&2
  fi
  
  log "v4l2h264enc hardware encoder is available (bcm2835-codec)" >&2
  return 0
}

build_video_encoder() {
  local mode="$1"
  
  # If camera outputs H264 directly, just parse it (best case - zero encoding)
  if source_outputs_h264 "$mode"; then
    log "Camera outputs H264 directly - no encoding needed (optimal)" >&2
    echo "h264parse config-interval=1"
    return 0
  fi
  
  # Check if hardware encoder exists AND actually works
  # Many Pi setups have v4l2h264enc detected but broken due to driver/memory issues
  local use_hw_encoder=0
  
  if gst-inspect-1.0 v4l2h264enc >/dev/null 2>&1; then
    if test_hw_encoder_works; then
      use_hw_encoder=1
    else
      log "WARNING: v4l2h264enc exists but doesn't work - falling back to software" >&2
    fi
  fi
  
  if [[ $use_hw_encoder -eq 1 ]]; then
    log "Using v4l2h264enc (HARDWARE) - low CPU usage" >&2
    # Use I420 (YUV420p) format - compatible with jpegdec output via videoconvert
    # Force level 4 for proper caps negotiation (fixes "level too low" issues)
    # extra-controls for proper stream headers (needed for RTSP)
    # video_bitrate in bits/sec
    local bitrate_bps=$((H264_BITRATE_KBPS * 1000))
    echo "video/x-raw,format=I420 ! v4l2h264enc extra-controls=\"controls,repeat_sequence_header=1,video_bitrate=${bitrate_bps}\" ! video/x-h264,level=(string)4 ! h264parse config-interval=1"
  elif gst-inspect-1.0 x264enc >/dev/null 2>&1; then
    log "Using x264enc (SOFTWARE) - CPU intensive on Pi 3B+" >&2
    log "Tip: For Pi 3B+, keep resolution at 640x480@15fps or lower" >&2
    # Optimized settings for Pi 3B+:
    # - ultrafast preset: minimal CPU usage
    # - zerolatency: no buffering delay
    # - low bitrate: reduces CPU load
    # - no B-frames: simpler encoding
    # - threads=2: don't overload the 4 cores
    echo "x264enc tune=zerolatency speed-preset=ultrafast bitrate=${H264_BITRATE_KBPS} key-int-max=${H264_KEYINT} bframes=0 threads=2 ! h264parse config-interval=1"
  elif gst-inspect-1.0 openh264enc >/dev/null 2>&1; then
    log "Using openh264enc (SOFTWARE) - CPU intensive" >&2
    echo "openh264enc bitrate=$((H264_BITRATE_KBPS * 1000)) ! h264parse config-interval=1"
  else
    die "No H264 encoder available. Need x264enc or openh264enc."
  fi
}

build_audio_source() {
  local audio_dev="$1"
  
  if [[ -z "$audio_dev" ]]; then
    echo ""
    return 0
  fi
  
  # Prefer ALSA direct - more reliable when running as root/systemd
  # PulseAudio often doesn't work correctly under root
  # buffer-time: larger buffers (200ms) reduce USB interrupts and improve stability
  # latency-time: minimum read size (25ms) - smaller = more responsive but more CPU
  if gst-inspect-1.0 alsasrc >/dev/null 2>&1; then
    log "Using alsasrc for audio (device: $audio_dev, gain: ${AUDIO_GAIN}) with optimized buffers" >&2
    # volume element applies gain: 1.0 = no change, >1.0 = amplify, <1.0 = attenuate
    echo "alsasrc device=${audio_dev} buffer-time=200000 latency-time=25000 ! audio/x-raw,rate=${AUDIO_RATE},channels=${AUDIO_CHANNELS} ! queue max-size-buffers=0 max-size-time=500000000 max-size-bytes=0 ! audioconvert ! volume volume=${AUDIO_GAIN} ! audioresample"
  elif gst-inspect-1.0 pulsesrc >/dev/null 2>&1; then
    # Fallback to PulseAudio (may not work under root)
    log "Using pulsesrc for audio (may not work under root)" >&2
    echo "pulsesrc ! audio/x-raw,rate=${AUDIO_RATE},channels=${AUDIO_CHANNELS} ! queue max-size-buffers=0 max-size-time=500000000 max-size-bytes=0 ! audioconvert ! volume volume=${AUDIO_GAIN} ! audioresample"
  else
    log "No audio source available" >&2
    echo ""
  fi
}

build_audio_encoder() {
  # AAC is standard for RTSP compatibility
  # voaacenc (VisualOn) is lighter than avenc_aac (FFmpeg)
  if gst-inspect-1.0 voaacenc >/dev/null 2>&1; then
    log "Using voaacenc (VisualOn AAC - optimized)" >&2
    echo "voaacenc bitrate=$((AUDIO_BITRATE_KBPS * 1000)) ! aacparse"
  elif gst-inspect-1.0 avenc_aac >/dev/null 2>&1; then
    log "Using avenc_aac (FFmpeg AAC)" >&2
    echo "avenc_aac bitrate=$((AUDIO_BITRATE_KBPS * 1000)) ! aacparse"
  elif gst-inspect-1.0 faac >/dev/null 2>&1; then
    echo "faac bitrate=$((AUDIO_BITRATE_KBPS * 1000)) ! aacparse"
  else
    log "No AAC encoder available - audio disabled" >&2
    echo ""
  fi
}

#---------------------------
# test-launch detection
#---------------------------
find_test_launch() {
  # Check PATH first
  local p
  p="$(command -v test-launch 2>/dev/null || true)"
  if [[ -n "$p" ]]; then
    echo "$p"
    return 0
  fi
  
  # Check /usr/local/bin
  if [[ -x /usr/local/bin/test-launch ]]; then
    echo "/usr/local/bin/test-launch"
    return 0
  fi
  
  # Search system
  p="$(find /usr/lib -name 'test-launch' -type f 2>/dev/null | head -n 1 || true)"
  if [[ -n "$p" && -x "$p" ]]; then
    echo "$p"
    return 0
  fi
  
  echo ""
}

#---------------------------
# Recording management
#---------------------------
prune_if_needed() {
  if [[ "$MAX_DISK_MB" -le 0 ]]; then
    return 0
  fi
  
  local used_mb
  used_mb="$(du -sm "$RECORD_DIR" 2>/dev/null | awk '{print $1}')"
  used_mb="${used_mb:-0}"
  
  if [[ "$used_mb" -le "$MAX_DISK_MB" ]]; then
    return 0
  fi

  log "Pruning recordings: ${used_mb}MB > ${MAX_DISK_MB}MB limit"
  # Delete oldest files
  # shellcheck disable=SC2012
  ls -1t "$RECORD_DIR"/*.ts 2>/dev/null | tail -n +10 | while read -r f; do
    rm -f "$f" || true
    used_mb="$(du -sm "$RECORD_DIR" 2>/dev/null | awk '{print $1}')"
    used_mb="${used_mb:-0}"
    [[ "$used_mb" -le "$MAX_DISK_MB" ]] && break
  done
}

#---------------------------
# Main
#---------------------------
need_root
setup_fs
setup_logging

log "=========================================="
log "Starting rpi_av_rtsp_recorder v2.12.8"
log "=========================================="
log "Config: RTSP=:${RTSP_PORT}/${RTSP_PATH} Video=${VIDEO_WIDTH}x${VIDEO_HEIGHT}@${VIDEO_FPS}fps"
log "Recording: ${RECORD_ENABLE} -> ${RECORD_DIR} (${SEGMENT_SECONDS}s segments)"
log "Audio: ${AUDIO_ENABLE} device=${AUDIO_DEVICE} gain=${AUDIO_GAIN}"
if [[ -n "$RTSP_USER" && -n "$RTSP_PASSWORD" ]]; then
  log "Authentication: ENABLED (user: ${RTSP_USER})"
else
  log "Authentication: DISABLED"
fi

# Verify GStreamer is installed
cmd_exists gst-launch-1.0 || die "gst-launch-1.0 not found. Run install_gstreamer_rtsp.sh first."
cmd_exists gst-inspect-1.0 || die "gst-inspect-1.0 not found."

# Find test-launch
TEST_LAUNCH="$(find_test_launch)"
if [[ -z "$TEST_LAUNCH" ]]; then
  die "RTSP server 'test-launch' not found. Run install_gstreamer_rtsp.sh to compile it."
fi
log "Using RTSP server: $TEST_LAUNCH"

# Detect camera
CAM_MODE="$(select_camera_mode)"
log "Camera mode: $CAM_MODE"
[[ "$CAM_MODE" != "none" ]] || die "No camera detected. Check USB connection or CSI ribbon."

# ---------------------------------------------------------
# CSI Mode Delegation (Picamera2 / Python Implementation)
# ---------------------------------------------------------
if [[ "$CAM_MODE" == "csi" ]]; then
  log "CSI Camera Mode selected. Delegating to rpi_csi_rtsp_server.py (Picamera2 Native)..."
  if [[ "${VIDEO_OVERLAY_ENABLE}" == "yes" ]]; then
    log "Overlay enabled for CSI (software re-encode in RTSP server)." >&2
  fi
  
  # Define path to Python server
  # Check local div (dev mode) then install path
  CSI_SERVER_SCRIPT="./rpi_csi_rtsp_server.py"
  if [[ ! -f "$CSI_SERVER_SCRIPT" ]]; then
    CSI_SERVER_SCRIPT="/usr/local/bin/rpi_csi_rtsp_server.py"
  fi
  
  if [[ ! -f "$CSI_SERVER_SCRIPT" ]]; then
     # Fallback to old behavior if script missing, but warn
     log_err "rpi_csi_rtsp_server.py not found at $CSI_SERVER_SCRIPT. Falling back to legacy gst-launch (may be unstable/limited)."
  else
     # Export environment variables for the Python script
     export RTSP_PORT
     export RTSP_PATH
     export VIDEO_WIDTH
     export VIDEO_HEIGHT
     export VIDEO_FPS
     export H264_BITRATE_KBPS="$((H264_BITRATE_KBPS))"
     export H264_KEYINT
     export H264_PROFILE
     export H264_QP
     export VIDEO_OVERLAY_ENABLE
     export VIDEO_OVERLAY_TEXT
     export VIDEO_OVERLAY_POSITION
     export VIDEO_OVERLAY_SHOW_DATETIME
     export VIDEO_OVERLAY_DATETIME_FORMAT
     export VIDEO_OVERLAY_CLOCK_POSITION
     export VIDEO_OVERLAY_FONT_SIZE
     export AUDIO_ENABLE
     # Detect audio info for Python script if specific device wasn't set
     if [[ "$AUDIO_ENABLE" != "no" ]]; then
        AUDIO_DEV="$(detect_audio_dev || true)"
        export AUDIO_DEVICE="${AUDIO_DEVICE:-$AUDIO_DEV}"
     else
        export AUDIO_DEVICE
     fi
     export AUDIO_RATE
     
     # Execute the Python server (replaces this process)
     exec python3 "$CSI_SERVER_SCRIPT"
  fi
fi

# Show camera info
if [[ "$CAM_MODE" == "usb" ]]; then
  log "Camera device: $VIDEO_DEVICE"
  v4l2-ctl -d "$VIDEO_DEVICE" --info 2>/dev/null | grep -E "Driver|Card|Bus" || true
fi

# Detect audio
AUDIO_DEV=""
AUDIO_OK=0
if [[ "$AUDIO_ENABLE" != "no" ]]; then
  # detect_audio_dev returns 1 if no device found, which is not an error
  AUDIO_DEV="$(detect_audio_dev || true)"
  if [[ -n "$AUDIO_DEV" ]]; then
    AUDIO_OK=1
    log "Audio device detected: $AUDIO_DEV"
  else
    [[ "$AUDIO_ENABLE" == "yes" ]] && die "AUDIO_ENABLE=yes but no audio device found"
    log "No audio device found - audio disabled"
  fi
else
  log "Audio disabled by configuration"
fi

# Build pipeline components
log "Building video source for mode: $CAM_MODE"
VIDEO_SRC="$(build_video_source "$CAM_MODE")"
if [[ -z "$VIDEO_SRC" ]]; then
  die "Failed to build video source"
fi
VIDEO_OVERLAY="$(build_video_overlay)"
if [[ -n "$VIDEO_OVERLAY" ]]; then
  log "Overlay enabled: ${VIDEO_OVERLAY}" >&2
  VIDEO_SRC="${VIDEO_SRC} ! ${VIDEO_OVERLAY}"
fi
log "Building video encoder for mode: $CAM_MODE"
VIDEO_ENC="$(build_video_encoder "$CAM_MODE")"
if [[ -z "$VIDEO_ENC" ]]; then
  die "Failed to build video encoder"
fi

log "Video source: $VIDEO_SRC"
log "Video encoder: $VIDEO_ENC"

AUDIO_SRC=""
AUDIO_ENC=""
if [[ $AUDIO_OK -eq 1 ]]; then
  AUDIO_SRC="$(build_audio_source "$AUDIO_DEV")"
  AUDIO_ENC="$(build_audio_encoder)"
  if [[ -z "$AUDIO_ENC" ]]; then
    AUDIO_OK=0
    log "Audio encoding not available - audio disabled"
  fi
fi

# Build complete pipeline for RTSP streaming
# Note: test-launch works best with simple pipelines
# Recording with splitmuxsink inside RTSP pipeline causes issues
# For now: RTSP streaming only. Recording can be done externally via VLC/ffmpeg

# Simple video-only pipeline for RTSP
# Build pipeline - video + audio if available
# queue elements help absorb USB bandwidth variations on Pi 3B+
if [[ $AUDIO_OK -eq 1 ]]; then
  # Video + Audio pipeline with queues for USB stability
  PIPELINE="${VIDEO_SRC} ! queue max-size-buffers=3 max-size-time=0 max-size-bytes=0 leaky=downstream ! ${VIDEO_ENC} ! rtph264pay name=pay0 pt=96 config-interval=1"
  PIPELINE="${PIPELINE} ${AUDIO_SRC} ! ${AUDIO_ENC} ! rtpmp4gpay name=pay1 pt=97"
  log "Audio enabled: ${AUDIO_DEV}"
else
  # Video only with queue
  PIPELINE="${VIDEO_SRC} ! queue max-size-buffers=3 max-size-time=0 max-size-bytes=0 leaky=downstream ! ${VIDEO_ENC} ! rtph264pay name=pay0 pt=96 config-interval=1"
  log "Audio disabled"
fi

# Wrap for test-launch
LAUNCH="( ${PIPELINE} )"

log "=========================================="
log "Starting RTSP server..."
log "=========================================="
# Build RTSP URL for display
if [[ -n "$RTSP_USER" && -n "$RTSP_PASSWORD" ]]; then
  log "RTSP URL: rtsp://${RTSP_USER}:****@<PI_IP>:${RTSP_PORT}/${RTSP_PATH} (authenticated)"
  log "Authentication: ENABLED (user: ${RTSP_USER})"
else
  log "RTSP URL: rtsp://<PI_IP>:${RTSP_PORT}/${RTSP_PATH}"
  log "Authentication: DISABLED (set RTSP_USER and RTSP_PASSWORD to enable)"
fi
log ""
log "Pipeline: ${LAUNCH}"
log ""

# Cleanup logs at boot to prevent disk filling
cleanup_logs

# Prune old recordings if needed
prune_if_needed

# Set GStreamer debug level
export GST_DEBUG="${GST_DEBUG_LEVEL}"

# Export RTSP configuration for test-launch
export RTSP_PORT
export RTSP_PATH="/${RTSP_PATH}"
export RTSP_USER
export RTSP_PASSWORD
export RTSP_REALM="RPi Camera"

# Launch RTSP server directly
log "Launching test-launch..."
exec "$TEST_LAUNCH" "$LAUNCH"

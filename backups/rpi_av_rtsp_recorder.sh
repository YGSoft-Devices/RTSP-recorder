#!/usr/bin/env bash
#===============================================================================
# File: rpi_av_rtsp_recorder.sh
# Location: /usr/local/bin/rpi_av_rtsp_recorder.sh
#
# Target: Raspberry Pi OS Lite (Bookworm) - Raspberry Pi 3B+/4
#
# Purpose:
#   - Auto-detect camera source (CSI/libcamera OR USB/V4L2)
#   - Auto-detect USB microphone (ALSA) and prefer plughw for robustness
#   - Serve RTSP (H264 video + optional AAC audio)
#   - Record locally to SD in short segments (robust against power loss)
#   - Provide sensible defaults but everything configurable via env vars
#
# Version: 1.0.0
# Changelog:
#   - 1.0.0: Initial release (auto-detect + RTSP + segmented recording)
#
# Notes:
#   - Best performance is achieved when the camera provides H.264 directly (USB UVC H264).
#   - If USB camera is MJPEG/YUYV only, software H264 encoding may be heavy on Pi 3B+.
#   - RTSP audio support depends on client/NVR. AAC is chosen for broad compatibility.
#===============================================================================

set -euo pipefail

#---------------------------
# Defaults (override via env)
#---------------------------
: "${RTSP_PORT:=8554}"
: "${RTSP_PATH:=stream}"
: "${VIDEO_WIDTH:=1280}"
: "${VIDEO_HEIGHT:=960}"
: "${VIDEO_FPS:=20}"                  # You said 20fps is OK
: "${VIDEO_DEVICE:=/dev/video0}"      # USB camera device (if present)
: "${CSI_ENABLE:=auto}"               # auto|yes|no
: "${USB_ENABLE:=auto}"               # auto|yes|no

: "${RECORD_DIR:=/var/cache/rpi-cam/recordings}"
: "${SEGMENT_SECONDS:=300}"           # 5 minutes per file
: "${MAX_DISK_MB:=0}"                 # 0 = do not auto-prune here (use cron/logrotate if desired)

: "${AUDIO_ENABLE:=auto}"             # auto|yes|no
: "${AUDIO_RATE:=48000}"
: "${AUDIO_CHANNELS:=1}"
: "${AUDIO_BITRATE_KBPS:=64}"         # AAC bitrate target
: "${AUDIO_DEVICE:=auto}"             # auto or explicit ALSA dev string (e.g. plughw:1,0)

: "${GST_DEBUG_LEVEL:=2}"             # 0..6 (2=WARNING-ish, 3=INFO)
: "${LOG_DIR:=/var/log/rpi-cam}"
: "${LOG_FILE:=${LOG_DIR}/rpi_av_rtsp_recorder.log}"

# Prefer lower latency for live RTSP
: "${LOW_LATENCY:=1}"                # 1=on, 0=off

#---------------------------
# Helpers
#---------------------------
ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*"; }
die() { log "ERROR: $*"; exit 1; }

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "Run as root: sudo $0"
  fi
}

cmd_exists() { command -v "$1" >/dev/null 2>&1; }

# Make dirs and log
setup_fs() {
  mkdir -p "$RECORD_DIR" "$LOG_DIR"
  touch "$LOG_FILE"
  chmod 755 "$RECORD_DIR" "$LOG_DIR" || true
  chmod 640 "$LOG_FILE" || true
}

# Redirect all stdout/stderr to log + console
setup_logging() {
  exec > >(tee -a "$LOG_FILE") 2>&1
}

# Detect ALSA mic and return a robust device name (plughw)
detect_audio_dev() {
  # If user specified AUDIO_DEVICE explicitly, use it
  if [[ "$AUDIO_DEVICE" != "auto" ]]; then
    echo "$AUDIO_DEVICE"
    return 0
  fi

  # Try to find a USB capture card number from arecord -l
  if ! cmd_exists arecord; then
    echo ""
    return 0
  fi

  local card
  card="$(arecord -l 2>/dev/null | awk '
    /card [0-9]+:.*USB/ {gsub("card ",""); gsub(":",""); print $1; exit}
    /card [0-9]+:.*Device/ && /USB/ {gsub("card ",""); gsub(":",""); print $1; exit}
  ')"

  if [[ -n "${card}" ]]; then
    echo "plughw:${card},0"
    return 0
  fi

  # Fallback: look for any capture card (first one)
  card="$(arecord -l 2>/dev/null | awk '
    /card [0-9]+:/ {gsub("card ",""); gsub(":",""); print $1; exit}
  ')"
  if [[ -n "${card}" ]]; then
    echo "plughw:${card},0"
    return 0
  fi

  echo ""
}

# Detect whether USB camera exists
usb_cam_present() {
  [[ -e "$VIDEO_DEVICE" ]]
}

# Detect CSI camera capability (libcamera)
csi_cam_possible() {
  cmd_exists libcamera-hello || cmd_exists libcamera-vid
}

# Determine camera mode: "usb" or "csi"
select_camera_mode() {
  local usb_ok=0 csi_ok=0

  if [[ "$USB_ENABLE" == "yes" ]]; then usb_ok=1
  elif [[ "$USB_ENABLE" == "no" ]]; then usb_ok=0
  else
    usb_cam_present && usb_ok=1 || usb_ok=0
  fi

  if [[ "$CSI_ENABLE" == "yes" ]]; then csi_ok=1
  elif [[ "$CSI_ENABLE" == "no" ]]; then csi_ok=0
  else
    csi_cam_possible && csi_ok=1 || csi_ok=0
  fi

  # Priority: USB if present; else CSI
  if [[ $usb_ok -eq 1 ]]; then
    echo "usb"
  elif [[ $csi_ok -eq 1 ]]; then
    echo "csi"
  else
    echo "none"
  fi
}

# Check if USB camera supports H264 directly
usb_cam_supports_h264() {
  if ! cmd_exists v4l2-ctl; then
    return 1
  fi
  v4l2-ctl -d "$VIDEO_DEVICE" --list-formats-ext 2>/dev/null | grep -qiE 'H264|H\.264'
}

# Optional simple pruning (not enabled by default)
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

  log "Pruning recordings: ${used_mb}MB > ${MAX_DISK_MB}MB"
  # delete oldest files until under limit
  # shellcheck disable=SC2012
  ls -1t "$RECORD_DIR"/*.ts 2>/dev/null | tail -n +1 | tac | while read -r f; do
    rm -f "$f" || true
    used_mb="$(du -sm "$RECORD_DIR" 2>/dev/null | awk '{print $1}')"
    used_mb="${used_mb:-0}"
    [[ "$used_mb" -le "$MAX_DISK_MB" ]] && break
  done
}

# Build GStreamer launch string for RTSP server (test-launch) if available
find_test_launch() {
  local p
  p="$(command -v test-launch || true)"
  if [[ -n "$p" ]]; then
    echo "$p"
    return 0
  fi
  p="$(ls /usr/lib/*/gstreamer-1.0/test-launch 2>/dev/null | head -n 1 || true)"
  if [[ -n "$p" ]]; then
    echo "$p"
    return 0
  fi
  echo ""
}

#---------------------------
# Main
#---------------------------
need_root
setup_fs
setup_logging

log "Starting rpi_av_rtsp_recorder v1.0.0"
log "Config: RTSP_PORT=$RTSP_PORT RTSP_PATH=$RTSP_PATH ${VIDEO_WIDTH}x${VIDEO_HEIGHT}@${VIDEO_FPS} RECORD_DIR=$RECORD_DIR SEGMENT_SECONDS=$SEGMENT_SECONDS"
log "Audio: AUDIO_ENABLE=$AUDIO_ENABLE AUDIO_DEVICE=$AUDIO_DEVICE RATE=$AUDIO_RATE CH=$AUDIO_CHANNELS BR=${AUDIO_BITRATE_KBPS}kbps"

# Ensure required commands
cmd_exists gst-launch-1.0 || die "gstreamer not installed (gst-launch-1.0 missing). Run your install script first."
cmd_exists gst-inspect-1.0 || die "gstreamer not installed (gst-inspect-1.0 missing)."

TEST_LAUNCH="$(find_test_launch)"
[[ -n "$TEST_LAUNCH" ]] || die "RTSP example server 'test-launch' not found. Install gstreamer1.0-rtsp / libgstrtspserver examples."

CAM_MODE="$(select_camera_mode)"
log "Camera mode selected: $CAM_MODE"

[[ "$CAM_MODE" != "none" ]] || die "No camera detected. USB: $VIDEO_DEVICE absent; CSI/libcamera tools missing."

# Audio detection
AUDIO_DEV=""
AUDIO_OK=0
if [[ "$AUDIO_ENABLE" == "no" ]]; then
  AUDIO_OK=0
else
  AUDIO_DEV="$(detect_audio_dev)"
  if [[ -n "$AUDIO_DEV" ]]; then
    AUDIO_OK=1
  else
    [[ "$AUDIO_ENABLE" == "yes" ]] && die "AUDIO_ENABLE=yes but no ALSA capture device detected."
    AUDIO_OK=0
  fi
fi

if [[ $AUDIO_OK -eq 1 ]]; then
  log "Audio capture device: $AUDIO_DEV"
else
  log "Audio disabled (no device or AUDIO_ENABLE=no)."
fi

# Recording segment ns
SEG_NS="$((SEGMENT_SECONDS * 1000000000))"

# Build pipeline parts
# Video source:
# - USB: Prefer H264 if camera supports it; else MJPEG->x264 (CPU heavy)
# - CSI: Use libcamerasrc if present; else fallback to libcamera-vid piping is possible but not used here
VIDEO_SRC=""
VIDEO_ENC=""
VIDEO_PARSE="h264parse config-interval=1"

if [[ "$CAM_MODE" == "usb" ]]; then
  log "USB camera detected at $VIDEO_DEVICE"
  if usb_cam_supports_h264; then
    log "USB camera supports H264 output. Using it (best performance)."
    VIDEO_SRC="v4l2src device=${VIDEO_DEVICE}"
    VIDEO_ENC="video/x-h264,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1"
  else
    log "USB camera does NOT advertise H264. Will use MJPEG->H264 (CPU heavy on Pi 3B+)."
    # Try MJPEG first; if camera doesn't support MJPEG, user must adapt.
    VIDEO_SRC="v4l2src device=${VIDEO_DEVICE}"
    # decode + software x264
    # NOTE: This can be too heavy for 1280x960@20 on Pi 3B+. If it struggles, drop resolution or fps.
    VIDEO_ENC="image/jpeg,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! jpegdec ! videoconvert ! \
x264enc tune=zerolatency speed-preset=ultrafast bitrate=2500 key-int-max=${VIDEO_FPS} bframes=0"
    VIDEO_PARSE="h264parse config-interval=1"
  fi
else
  # CSI
  # Prefer libcamerasrc (GStreamer plugin). On some installs the element exists as libcamerasrc.
  if gst-inspect-1.0 libcamerasrc >/dev/null 2>&1; then
    log "CSI camera: using libcamerasrc"
    VIDEO_SRC="libcamerasrc"
    # libcamerasrc outputs raw; encode to H264
    VIDEO_ENC="video/x-raw,width=${VIDEO_WIDTH},height=${VIDEO_HEIGHT},framerate=${VIDEO_FPS}/1 ! videoconvert ! \
x264enc tune=zerolatency speed-preset=ultrafast bitrate=2500 key-int-max=${VIDEO_FPS} bframes=0"
    VIDEO_PARSE="h264parse config-interval=1"
  else
    die "CSI camera selected but GStreamer element 'libcamerasrc' not available. Install gstreamer1.0-libcamera (or adjust)."
  fi
fi

# Audio chain (optional): ALSA -> AAC -> RTP pay -> record mux
# We will keep audio simple and compatible: AAC LC using avenc_aac (from libav).
AUDIO_CHAIN=""
AUDIO_RTP_PAY=""
AUDIO_REC=""

if [[ $AUDIO_OK -eq 1 ]]; then
  # Build audio encode chain
  # audioconvert/audioresample ensure we feed encoder correct format
  # We choose avenc_aac for availability; it requires gstreamer1.0-libav
  AUDIO_CHAIN="alsasrc device=${AUDIO_DEV} ! audio/x-raw,rate=${AUDIO_RATE},channels=${AUDIO_CHANNELS} ! audioconvert ! audioresample ! \
avenc_aac bitrate=$((AUDIO_BITRATE_KBPS * 1000)) ! aacparse"
  AUDIO_RTP_PAY="rtpmp4gpay pt=97"
fi

# Recording: We record MPEG-TS segments (robust).
# For A/V MPEG-TS: use mpegtsmux. We feed H264 + (optional) AAC into it.
# splitmuxsink handles segmentation. Use 'max-size-time' to segment.
REC_SINK="splitmuxsink location=${RECORD_DIR}/seg_%05d.ts muxer=mpegtsmux max-size-time=${SEG_NS}"

# RTSP: use pay0 for video; pay1 for audio if present.
# We must create a single launch string for test-launch.
# We'll tee the parsed H264 to RTSP pay and to recorder.
#
# NOTE: test-launch expects pay0 (mandatory) and pay1 (optional).
#
# Latency tweaks:
# - queue leaky can help avoid buildup if consumer lags
QUEUE_OPTS="queue"
if [[ "$LOW_LATENCY" == "1" ]]; then
  QUEUE_OPTS="queue leaky=downstream max-size-buffers=0 max-size-time=0 max-size-bytes=0"
fi

# Build final launch string:
# Video pipeline produces:
#   vsrc -> (either caps h264 OR decode->x264) -> h264parse -> tee
#   tee -> queue -> rtph264pay name=pay0
#   tee -> queue -> mux/segments
#
# Audio, if enabled:
#   asrc -> aac -> aacparse -> queue -> rtpmp4gpay name=pay1
#   also feed same audio into mux/segments
#
# For mux, we use "mpegtsmux name=mux ! splitmuxsink ..." and link both video/audio to mux.
#
LAUNCH=""

if [[ "$CAM_MODE" == "usb" ]] && usb_cam_supports_h264; then
  # USB H264 direct
  LAUNCH="( \
${VIDEO_SRC} ! ${VIDEO_ENC} ! ${VIDEO_PARSE} ! tee name=vtee \
vtee. ! ${QUEUE_OPTS} ! rtph264pay name=pay0 pt=96 config-interval=1 \
vtee. ! ${QUEUE_OPTS} ! mpegtsmux name=mux ! ${REC_SINK} \
"
else
  # Raw or MJPEG->x264
  LAUNCH="( \
${VIDEO_SRC} ! ${VIDEO_ENC} ! ${VIDEO_PARSE} ! tee name=vtee \
vtee. ! ${QUEUE_OPTS} ! rtph264pay name=pay0 pt=96 config-interval=1 \
vtee. ! ${QUEUE_OPTS} ! mpegtsmux name=mux ! ${REC_SINK} \
"
fi

if [[ $AUDIO_OK -eq 1 ]]; then
  LAUNCH="${LAUNCH} \
${AUDIO_CHAIN} ! tee name=atee \
atee. ! ${QUEUE_OPTS} ! ${AUDIO_RTP_PAY} name=pay1 \
atee. ! ${QUEUE_OPTS} ! mux. \
"
fi

LAUNCH="${LAUNCH} )"

log "RTSP will be available at: rtsp://<PI_IP>:${RTSP_PORT}/${RTSP_PATH}"
log "Recording segments to: ${RECORD_DIR} (every ${SEGMENT_SECONDS}s)"

# Ensure recording dir exists and optionally prune
prune_if_needed

# Set GST_DEBUG globally for this run
export GST_DEBUG="${GST_DEBUG_LEVEL}"

# test-launch binds to 8554 by default; support setting RTSP port via env var if supported.
# On Debian examples, you can set port using --port and mount-point using --mount-point.
# We'll use args if available; otherwise fallback.
#
# Try to detect if test-launch supports --port / --mount-point
if "$TEST_LAUNCH" --help 2>&1 | grep -q -- '--port'; then
  exec "$TEST_LAUNCH" --port "$RTSP_PORT" --mount-point "/${RTSP_PATH}" "$LAUNCH"
elif "$TEST_LAUNCH" --help 2>&1 | grep -q -- '--path'; then
  # Some variants differ; keep simple
  exec "$TEST_LAUNCH" "$LAUNCH"
else
  # Fallback: just run it, likely at 8554/test
  log "WARNING: test-launch does not expose --port/--mount-point in help; using defaults."
  exec "$TEST_LAUNCH" "$LAUNCH"
fi

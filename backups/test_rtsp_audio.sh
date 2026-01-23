#!/usr/bin/env bash
#===============================================================================
# Test RTSP avec audio - vidéo + audio ALSA
# Usage: sudo ./test_rtsp_audio.sh
#===============================================================================

set -euo pipefail

# Find test-launch
TEST_LAUNCH=""
for p in /usr/local/bin/test-launch /usr/bin/test-launch; do
  [[ -x "$p" ]] && TEST_LAUNCH="$p" && break
done

if [[ -z "$TEST_LAUNCH" ]]; then
  echo "ERREUR: test-launch non trouvé"
  exit 1
fi

# Detect audio device
AUDIO_DEV=""
if command -v arecord >/dev/null 2>&1; then
  card="$(arecord -l 2>/dev/null | awk '/card [0-9]+:.*USB/{gsub("card ",""); gsub(":.*",""); print $1; exit}')"
  [[ -n "$card" ]] && AUDIO_DEV="plughw:${card},0"
fi

if [[ -z "$AUDIO_DEV" ]]; then
  echo "ERREUR: Aucun périphérique audio USB trouvé"
  exit 1
fi

echo "============================================"
echo " Test RTSP avec Audio"
echo "============================================"
echo ""
echo "Video: MJPEG -> x264enc -> RTSP (pay0)"
echo "Audio: ALSA ($AUDIO_DEV) -> AAC -> RTSP (pay1)"
echo ""
echo "URL: rtsp://<IP>:8554/stream"
echo ""
echo "Connectez VLC à cette URL pour tester"
echo "Ctrl+C pour arrêter"
echo ""
echo "============================================"

# Pipeline avec vidéo ET audio
PIPELINE="( v4l2src device=/dev/video0 ! image/jpeg,width=640,height=480,framerate=15/1 ! jpegdec ! videoconvert ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=1200 key-int-max=30 ! h264parse config-interval=1 ! rtph264pay name=pay0 pt=96 config-interval=1 alsasrc device=${AUDIO_DEV} ! audio/x-raw,rate=48000,channels=1 ! audioconvert ! audioresample ! avenc_aac bitrate=64000 ! aacparse ! rtpmp4gpay name=pay1 pt=97 )"

echo "Pipeline: $PIPELINE"
echo ""

exec "$TEST_LAUNCH" "$PIPELINE"

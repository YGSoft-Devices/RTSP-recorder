#!/usr/bin/env bash
#===============================================================================
# Test RTSP simple - vidéo seule avec x264enc
# Usage: sudo ./test_rtsp_simple.sh
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

echo "============================================"
echo " Test RTSP simple - Vidéo seule"
echo "============================================"
echo ""
echo "Pipeline: MJPEG -> x264enc -> RTSP"
echo ""
echo "URL: rtsp://<IP>:8554/stream"
echo ""
echo "Connectez VLC à cette URL pour tester"
echo "Ctrl+C pour arrêter"
echo ""
echo "============================================"

# Pipeline simple: MJPEG -> decode -> x264enc -> RTSP
PIPELINE='( v4l2src device=/dev/video0 ! image/jpeg,width=640,height=480,framerate=15/1 ! jpegdec ! videoconvert ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=1200 key-int-max=30 ! h264parse config-interval=1 ! rtph264pay name=pay0 pt=96 config-interval=1 )'

echo "Lancement: $TEST_LAUNCH \"$PIPELINE\""
echo ""

exec "$TEST_LAUNCH" "$PIPELINE"

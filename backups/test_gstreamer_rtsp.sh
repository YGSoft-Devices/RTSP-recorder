#!/usr/bin/env bash
#===============================================================================
# File: test_gstreamer_rtsp.sh
# Purpose: Test GStreamer pipelines for RTSP streaming
#          Run this script to diagnose camera/audio/RTSP issues
#
# Usage: sudo ./test_gstreamer_rtsp.sh
#===============================================================================

set -uo pipefail

VIDEO_DEVICE="${VIDEO_DEVICE:-/dev/video0}"
VIDEO_WIDTH="${VIDEO_WIDTH:-640}"
VIDEO_HEIGHT="${VIDEO_HEIGHT:-480}"
VIDEO_FPS="${VIDEO_FPS:-15}"

msg() { echo -e "\033[1;34m[TEST]\033[0m $*"; }
msg_ok() { echo -e "\033[1;32m[OK]\033[0m $*"; }
msg_err() { echo -e "\033[1;31m[ERREUR]\033[0m $*"; }
msg_warn() { echo -e "\033[1;33m[ATTENTION]\033[0m $*"; }

run_test() {
    local name="$1"
    local cmd="$2"
    local timeout_sec="${3:-10}"
    
    msg "Test: $name"
    echo "  Commande: $cmd"
    
    if timeout "$timeout_sec" bash -c "$cmd" 2>&1; then
        msg_ok "$name - RÉUSSI"
        return 0
    else
        msg_err "$name - ÉCHOUÉ"
        return 1
    fi
}

echo ""
echo "========================================"
echo " Test GStreamer + RTSP"
echo " Raspberry Pi OS Trixie"
echo "========================================"
echo ""

# Check root
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    msg_warn "Exécutez en tant que root pour tous les tests: sudo $0"
fi

# ==============================================================================
# Test 1: GStreamer installation
# ==============================================================================
echo ""
msg "=== 1. Vérification de GStreamer ==="

if command -v gst-launch-1.0 >/dev/null 2>&1; then
    msg_ok "gst-launch-1.0 trouvé"
    gst-launch-1.0 --version | head -2
else
    msg_err "gst-launch-1.0 non trouvé - GStreamer n'est pas installé"
    exit 1
fi

# ==============================================================================
# Test 2: Essential plugins
# ==============================================================================
echo ""
msg "=== 2. Plugins GStreamer essentiels ==="

PLUGINS_OK=0
PLUGINS_FAIL=0

check_plugin() {
    local plugin="$1"
    if gst-inspect-1.0 "$plugin" >/dev/null 2>&1; then
        msg_ok "$plugin"
        ((PLUGINS_OK++))
    else
        msg_err "$plugin - MANQUANT"
        ((PLUGINS_FAIL++))
    fi
}

msg "Plugins vidéo:"
check_plugin v4l2src
check_plugin videoconvert
check_plugin jpegdec

msg "Encodeur H264 HARDWARE (VideoCore IV):"
HW_ENCODER_DETECTED=0
HW_ENCODER_WORKS=0
if gst-inspect-1.0 v4l2h264enc >/dev/null 2>&1; then
    msg_ok "v4l2h264enc détecté"
    HW_ENCODER_DETECTED=1
    ((PLUGINS_OK++))
    
    # Test if it actually works (many systems have it but broken)
    msg "  → Test fonctionnel v4l2h264enc..."
    HW_TEST=$(timeout 8 gst-launch-1.0 videotestsrc num-buffers=5 ! \
        video/x-raw,format=NV12,width=320,height=240,framerate=10/1 ! \
        v4l2h264enc ! fakesink 2>&1)
    
    if echo "$HW_TEST" | grep -qE "EOS|Execution ended"; then
        msg_ok "  → v4l2h264enc FONCTIONNE ✓"
        HW_ENCODER_WORKS=1
    else
        msg_err "  → v4l2h264enc DÉTECTÉ MAIS NE FONCTIONNE PAS"
        msg_warn "  → Erreur: $(echo "$HW_TEST" | grep -i "error\|failed" | head -1)"
    fi
else
    msg_warn "v4l2h264enc (HARDWARE) - non disponible"
fi

msg "Encodeur H264 SOFTWARE (fallback):"
check_plugin x264enc

msg "Plugins audio:"
check_plugin alsasrc
check_plugin pulsesrc
check_plugin audioconvert
check_plugin avenc_aac

msg "Plugins RTSP/mux:"
check_plugin rtph264pay
check_plugin rtpmp4gpay
check_plugin h264parse
check_plugin mpegtsmux

echo ""
msg "Résultat: $PLUGINS_OK plugins OK, $PLUGINS_FAIL manquants"

if [[ $HW_ENCODER_WORKS -eq 1 ]]; then
    msg_ok "Encodeur HARDWARE FONCTIONNEL → CPU tranquille, haute résolution possible"
elif [[ $HW_ENCODER_DETECTED -eq 1 ]]; then
    msg_warn "Encodeur HARDWARE détecté mais CASSÉ → fallback vers x264enc (SOFTWARE)"
else
    msg_warn "Encodeur HARDWARE non disponible → x264enc (SOFTWARE) sera utilisé"
    msg_warn "  Sur Pi 3B+, utilisez une résolution réduite (640x480@15fps)"
fi

if [[ $PLUGINS_FAIL -gt 0 ]]; then
    msg_warn "Certains plugins sont manquants. Le streaming peut ne pas fonctionner."
fi

# ==============================================================================
# Test 3: Video device
# ==============================================================================
echo ""
msg "=== 3. Périphérique vidéo ==="

if [[ -e "$VIDEO_DEVICE" ]]; then
    msg_ok "Périphérique $VIDEO_DEVICE existe"
    
    # Get device info
    echo ""
    msg "Informations caméra:"
    v4l2-ctl -d "$VIDEO_DEVICE" --info 2>/dev/null | grep -E "Driver|Card|Bus" || true
    
    # Check formats
    echo ""
    msg "Formats supportés:"
    v4l2-ctl -d "$VIDEO_DEVICE" --list-formats 2>/dev/null || true
    
    # Detect best format
    FORMATS=$(v4l2-ctl -d "$VIDEO_DEVICE" --list-formats-ext 2>/dev/null)
    
    if echo "$FORMATS" | grep -qi "MJPG\|Motion-JPEG"; then
        msg_ok "Format MJPEG supporté (recommandé)"
        CAM_FORMAT="mjpeg"
    elif echo "$FORMATS" | grep -qi "H264\|H.264"; then
        msg_ok "Format H264 supporté (optimal)"
        CAM_FORMAT="h264"
    elif echo "$FORMATS" | grep -qi "YUYV"; then
        msg_warn "Format YUYV uniquement (charge CPU élevée)"
        CAM_FORMAT="yuyv"
    else
        msg_err "Aucun format compatible détecté"
        CAM_FORMAT="unknown"
    fi
else
    msg_err "Périphérique $VIDEO_DEVICE n'existe pas"
    msg "Caméras disponibles:"
    v4l2-ctl --list-devices 2>/dev/null || echo "  Aucune caméra détectée"
    CAM_FORMAT="none"
fi

# ==============================================================================
# Test 4: Audio device
# ==============================================================================
echo ""
msg "=== 4. Périphérique audio ==="

if command -v arecord >/dev/null 2>&1; then
    AUDIO_CARDS=$(arecord -l 2>/dev/null)
    if echo "$AUDIO_CARDS" | grep -q "card"; then
        msg_ok "Périphériques audio trouvés:"
        echo "$AUDIO_CARDS"
        
        # Detect USB mic
        USB_CARD=$(echo "$AUDIO_CARDS" | awk '/card [0-9]+:.*USB/{gsub("card ",""); gsub(":.*",""); print $1; exit}')
        if [[ -n "$USB_CARD" ]]; then
            AUDIO_DEV="plughw:${USB_CARD},0"
            msg_ok "Microphone USB détecté: $AUDIO_DEV"
        else
            AUDIO_DEV=""
            msg_warn "Pas de microphone USB détecté"
        fi
    else
        msg_warn "Aucun périphérique de capture audio"
        AUDIO_DEV=""
    fi
else
    msg_warn "arecord non disponible"
    AUDIO_DEV=""
fi

# ==============================================================================
# Test 5: Video pipeline tests
# ==============================================================================
echo ""
msg "=== 5. Tests de pipeline vidéo ==="

# Test basic video test source
run_test "Pipeline videotestsrc" \
    "gst-launch-1.0 videotestsrc num-buffers=30 ! videoconvert ! fakesink" \
    10

if [[ "$CAM_FORMAT" != "none" ]] && [[ -e "$VIDEO_DEVICE" ]]; then
    
    # Test V4L2 capture
    echo ""
    msg "Test capture V4L2 depuis $VIDEO_DEVICE..."
    
    if [[ "$CAM_FORMAT" == "mjpeg" ]]; then
        run_test "Capture V4L2 MJPEG" \
            "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=30 ! image/jpeg,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! fakesink" \
            15
            
        run_test "Capture MJPEG + décodage" \
            "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=30 ! image/jpeg,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! jpegdec ! videoconvert ! fakesink" \
            15
    elif [[ "$CAM_FORMAT" == "yuyv" ]]; then
        run_test "Capture V4L2 YUYV" \
            "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=30 ! video/x-raw,format=YUY2,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! videoconvert ! fakesink" \
            15
    elif [[ "$CAM_FORMAT" == "h264" ]]; then
        run_test "Capture V4L2 H264" \
            "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=30 ! video/x-h264,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! fakesink" \
            15
    fi
    
    # Test H264 HARDWARE encoding (v4l2h264enc - VideoCore IV)
    if gst-inspect-1.0 v4l2h264enc >/dev/null 2>&1; then
        echo ""
        msg "Test encodage H264 HARDWARE (v4l2h264enc - VideoCore IV)..."
        
        # Test with videotestsrc first
        run_test "videotestsrc -> v4l2h264enc (HARDWARE)" \
            "gst-launch-1.0 videotestsrc num-buffers=30 ! video/x-raw,width=640,height=480 ! v4l2h264enc ! fakesink" \
            15
        
        if [[ "$CAM_FORMAT" == "mjpeg" ]]; then
            run_test "MJPEG -> v4l2h264enc (HARDWARE)" \
                "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=30 ! image/jpeg,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! jpegdec ! videoconvert ! v4l2h264enc extra-controls=\"controls,repeat_sequence_header=1\" ! fakesink" \
                20
        elif [[ "$CAM_FORMAT" == "yuyv" ]]; then
            run_test "YUYV -> v4l2h264enc (HARDWARE)" \
                "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=30 ! video/x-raw,format=YUY2,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! videoconvert ! v4l2h264enc extra-controls=\"controls,repeat_sequence_header=1\" ! fakesink" \
                20
        fi
    else
        msg_warn "v4l2h264enc (HARDWARE) non disponible"
    fi
    
    # Test H264 SOFTWARE encoding (x264enc - fallback)
    if gst-inspect-1.0 x264enc >/dev/null 2>&1; then
        echo ""
        msg "Test encodage H264 SOFTWARE (x264enc - CPU)..."
        
        if [[ "$CAM_FORMAT" == "mjpeg" ]]; then
            run_test "MJPEG -> x264enc (SOFTWARE)" \
                "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=20 ! image/jpeg,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! jpegdec ! videoconvert ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=1500 ! fakesink" \
                25
        elif [[ "$CAM_FORMAT" == "yuyv" ]]; then
            run_test "YUYV -> x264enc (SOFTWARE)" \
                "gst-launch-1.0 v4l2src device=$VIDEO_DEVICE num-buffers=15 ! video/x-raw,format=YUY2,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT ! videoconvert ! x264enc tune=zerolatency speed-preset=ultrafast bitrate=1500 ! fakesink" \
                30
        fi
    else
        msg_warn "x264enc (SOFTWARE) non disponible"
    fi
fi

# ==============================================================================
# Test 6: Audio pipeline tests
# ==============================================================================
echo ""
msg "=== 6. Tests de pipeline audio ==="

run_test "Pipeline audiotestsrc" \
    "gst-launch-1.0 audiotestsrc num-buffers=30 ! audioconvert ! fakesink" \
    10

if [[ -n "$AUDIO_DEV" ]]; then
    # Test ALSA capture
    run_test "Capture ALSA" \
        "gst-launch-1.0 alsasrc device=$AUDIO_DEV num-buffers=30 ! audio/x-raw,rate=48000,channels=1 ! fakesink" \
        15
    
    # Test AAC encoding
    if gst-inspect-1.0 avenc_aac >/dev/null 2>&1; then
        run_test "ALSA -> AAC" \
            "gst-launch-1.0 alsasrc device=$AUDIO_DEV num-buffers=30 ! audio/x-raw,rate=48000,channels=1 ! audioconvert ! avenc_aac bitrate=64000 ! fakesink" \
            15
    else
        msg_warn "avenc_aac non disponible"
    fi
fi

# ==============================================================================
# Test 7: test-launch availability
# ==============================================================================
echo ""
msg "=== 7. Serveur RTSP (test-launch) ==="

TEST_LAUNCH=""
if command -v test-launch >/dev/null 2>&1; then
    TEST_LAUNCH="$(command -v test-launch)"
    msg_ok "test-launch trouvé: $TEST_LAUNCH"
elif [[ -x /usr/local/bin/test-launch ]]; then
    TEST_LAUNCH="/usr/local/bin/test-launch"
    msg_ok "test-launch trouvé: $TEST_LAUNCH"
else
    msg_err "test-launch non trouvé"
    msg "  Exécutez: sudo ./install_gstreamer_rtsp.sh"
fi

# ==============================================================================
# Test 8: Full RTSP pipeline test
# ==============================================================================
echo ""
msg "=== 8. Test du pipeline RTSP complet ==="

if [[ -n "$TEST_LAUNCH" ]] && [[ "$CAM_FORMAT" != "none" ]] && [[ -e "$VIDEO_DEVICE" ]]; then
    
    # Determine encoder to use
    ENCODER=""
    ENCODER_TYPE=""
    if gst-inspect-1.0 v4l2h264enc >/dev/null 2>&1; then
        ENCODER='v4l2h264enc extra-controls="controls,repeat_sequence_header=1" ! video/x-h264,level=(string)4'
        ENCODER_TYPE="HARDWARE (v4l2h264enc)"
    elif gst-inspect-1.0 x264enc >/dev/null 2>&1; then
        ENCODER="x264enc tune=zerolatency speed-preset=ultrafast bitrate=1500"
        ENCODER_TYPE="SOFTWARE (x264enc)"
    else
        msg_err "Aucun encodeur H264 disponible"
        ENCODER=""
    fi
    
    if [[ -n "$ENCODER" ]]; then
        # Build test pipeline based on camera format
        if [[ "$CAM_FORMAT" == "mjpeg" ]]; then
            PIPELINE="v4l2src device=$VIDEO_DEVICE ! image/jpeg,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT,framerate=$VIDEO_FPS/1 ! jpegdec ! videoconvert ! $ENCODER ! h264parse config-interval=1 ! rtph264pay name=pay0 pt=96"
        elif [[ "$CAM_FORMAT" == "h264" ]]; then
            PIPELINE="v4l2src device=$VIDEO_DEVICE ! video/x-h264,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT,framerate=$VIDEO_FPS/1 ! h264parse config-interval=1 ! rtph264pay name=pay0 pt=96"
        elif [[ "$CAM_FORMAT" == "yuyv" ]]; then
            PIPELINE="v4l2src device=$VIDEO_DEVICE ! video/x-raw,format=YUY2,width=$VIDEO_WIDTH,height=$VIDEO_HEIGHT,framerate=$VIDEO_FPS/1 ! videoconvert ! $ENCODER ! h264parse config-interval=1 ! rtph264pay name=pay0 pt=96"
        fi
        
        msg "Test du serveur RTSP pendant 10 secondes..."
        msg "Encodeur: $ENCODER_TYPE"
        msg "Pipeline: $PIPELINE"
        echo ""
        msg "Connectez-vous avec VLC à: rtsp://<IP>:8554/stream"
        echo ""
        
        timeout 10 "$TEST_LAUNCH" "( $PIPELINE )" 2>&1 || true
        
        msg_ok "Test RTSP terminé"
    fi
else
    msg_warn "Impossible de tester le pipeline RTSP complet"
    [[ -z "$TEST_LAUNCH" ]] && msg "  - test-launch manquant"
    [[ "$CAM_FORMAT" == "none" ]] && msg "  - Aucune caméra détectée"
fi

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "========================================"
msg "=== RÉSUMÉ ==="
echo "========================================"
echo ""
echo "Caméra: $VIDEO_DEVICE"
echo "  Format: $CAM_FORMAT"
echo "  Résolution: ${VIDEO_WIDTH}x${VIDEO_HEIGHT}@${VIDEO_FPS}fps"
echo ""

# Check encoder - prioritize actual functionality, not just detection
if [[ $HW_ENCODER_WORKS -eq 1 ]]; then
    echo "Encodeur H264: v4l2h264enc (HARDWARE - VideoCore IV) ✓"
    echo "  → CPU tranquille, haute résolution possible (1280x720@20fps)"
elif [[ $HW_ENCODER_DETECTED -eq 1 ]]; then
    echo "Encodeur H264: v4l2h264enc DÉTECTÉ MAIS CASSÉ ⚠"
    echo "  → Sera ignoré, fallback vers x264enc"
    if gst-inspect-1.0 x264enc >/dev/null 2>&1; then
        echo "Encodeur fallback: x264enc (SOFTWARE - CPU)"
        echo "  → Charge CPU élevée, utilisez 640x480@15fps"
    else
        echo "  ✗ ATTENTION: Aucun encodeur H264 fonctionnel!"
    fi
elif gst-inspect-1.0 x264enc >/dev/null 2>&1; then
    echo "Encodeur H264: x264enc (SOFTWARE - CPU) ⚠"
    echo "  → Charge CPU élevée, utilisez 640x480@15fps"
else
    echo "Encodeur H264: NON DISPONIBLE ✗"
fi
echo ""

if [[ -n "$AUDIO_DEV" ]]; then
    echo "Audio: $AUDIO_DEV"
else
    echo "Audio: Non détecté"
fi
echo ""
if [[ -n "$TEST_LAUNCH" ]]; then
    echo "RTSP Server: $TEST_LAUNCH"
else
    echo "RTSP Server: NON DISPONIBLE"
fi
echo ""

if [[ "$CAM_FORMAT" != "none" ]] && [[ -n "$TEST_LAUNCH" ]]; then
    msg_ok "Le système semble prêt pour le streaming RTSP"
    echo ""
    echo "Pour lancer le serveur RTSP:"
    echo "  sudo systemctl start rpi-av-rtsp-recorder"
    echo ""
    echo "Ou manuellement:"
    echo "  sudo ./rpi_av_rtsp_recorder_v2.sh"
else
    msg_err "Le système n'est pas prêt pour le streaming RTSP"
    echo ""
    echo "Actions requises:"
    [[ "$CAM_FORMAT" == "none" ]] && echo "  - Connectez une caméra USB ou CSI"
    [[ -z "$TEST_LAUNCH" ]] && echo "  - Installez test-launch: sudo ./install_gstreamer_rtsp.sh"
    [[ $PLUGINS_FAIL -gt 0 ]] && echo "  - Installez les plugins manquants"
fi

echo ""

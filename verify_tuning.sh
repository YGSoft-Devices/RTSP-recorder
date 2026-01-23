#!/bin/bash
# Compare saved vs current tunings

echo "=== COMPARISON ==="
echo ""

# Extract saved tunings
SAVED_SAT=$(cat /etc/rpi-cam/csi_tuning.json | python3 -c "import sys, json; print(json.load(sys.stdin).get('Saturation', 'N/A'))")
SAVED_BRIGHT=$(cat /etc/rpi-cam/csi_tuning.json | python3 -c "import sys, json; print(json.load(sys.stdin).get('Brightness', 'N/A'))")
SAVED_GAIN=$(cat /etc/rpi-cam/csi_tuning.json | python3 -c "import sys, json; print(json.load(sys.stdin).get('AnalogueGain', 'N/A'))")

# Extract current values
CURR_SAT=$(curl -s http://localhost:8085/controls | python3 -c "import sys, json; print(json.load(sys.stdin)['controls']['Saturation']['value'])")
CURR_BRIGHT=$(curl -s http://localhost:8085/controls | python3 -c "import sys, json; print(json.load(sys.stdin)['controls']['Brightness']['value'])")
CURR_GAIN=$(curl -s http://localhost:8085/controls | python3 -c "import sys, json; print(json.load(sys.stdin)['controls']['AnalogueGain']['value'])")

echo "Saturation:   Saved=$SAVED_SAT  Current=$CURR_SAT  $([ "$SAVED_SAT" = "$CURR_SAT" ] && echo "✓ MATCH" || echo "✗ MISMATCH")"
echo "Brightness:   Saved=$SAVED_BRIGHT  Current=$CURR_BRIGHT  $([ "$SAVED_BRIGHT" = "$CURR_BRIGHT" ] && echo "✓ MATCH" || echo "✗ MISMATCH")"
echo "AnalogueGain: Saved=$SAVED_GAIN  Current=$CURR_GAIN  $([ "$SAVED_GAIN" = "$CURR_GAIN" ] && echo "✓ MATCH" || echo "✗ MISMATCH")"

echo ""
echo "=== Recent server output ==="
sudo journalctl -u rpi-av-rtsp-recorder -n 10 --no-pager | tail -5

#!/bin/bash
# Check if CSI server has loaded saved tunings

echo "=== SAVED TUNINGS (config file) ==="
cat /etc/rpi-cam/csi_tuning.json | python3 -c "import sys, json; t=json.load(sys.stdin); print(f'Saturation: {t.get(\"Saturation\")}\nBrightness: {t.get(\"Brightness\")}\nAnalogueGain: {t.get(\"AnalogueGain\")}')"

echo ""
echo "=== CURRENT VALUES (API) ==="
curl -s http://localhost:8085/controls | python3 -c "import sys, json; c=json.load(sys.stdin)['controls']; print(f'Saturation: {c[\"Saturation\"][\"value\"]}\nBrightness: {c[\"Brightness\"][\"value\"]}\nAnalogueGain: {c[\"AnalogueGain\"][\"value\"]}')"

echo ""
echo "=== SERVER LOGS (last 5 lines) ==="
sudo journalctl -u rpi-av-rtsp-recorder -n 5 --no-pager

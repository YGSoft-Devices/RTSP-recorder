#!/bin/bash
# Deployment script pour camera_bp.py

set -e

DEST_HOST="device@192.168.1.4"
SOURCE_FILE="web-manager/blueprints/camera_bp.py"
DEST_FILE="/opt/rpi-cam-webmanager/blueprints/camera_bp.py"

echo "[*] Transferring $SOURCE_FILE to $DEST_HOST:/tmp/"
scp -o StrictHostKeyChecking=no "$SOURCE_FILE" "$DEST_HOST:/tmp/camera_bp.py"

echo "[*] Installing and restarting service..."
ssh -o StrictHostKeyChecking=no "$DEST_HOST" << 'EOF'
sudo cp /tmp/camera_bp.py /opt/rpi-cam-webmanager/blueprints/
sudo systemctl restart rpi-cam-webmanager
sleep 2
echo "OK"
EOF

echo "[+] Deployment complete!"

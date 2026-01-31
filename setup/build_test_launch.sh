#!/bin/bash
set -e
export PATH=/usr/bin:/bin:/usr/local/bin:/sbin:/usr/sbin:$PATH

echo "[BUILD] Compilation de test-launch v2.2.0 avec support Digest+Basic auth + protocols..."

cd /tmp/rtsp-server-build

CFLAGS=$(pkg-config --cflags gstreamer-1.0 gstreamer-rtsp-server-1.0)
LIBS=$(pkg-config --libs gstreamer-1.0 gstreamer-rtsp-server-1.0)

echo "[BUILD] CFLAGS: $CFLAGS"
echo "[BUILD] LIBS: $LIBS"

gcc -o test-launch test-launch.c $CFLAGS $LIBS

echo "[BUILD] Compilation réussie!"
echo "[BUILD] Copie vers /usr/local/bin..."

sudo cp test-launch /usr/local/bin/test-launch
sudo chmod +x /usr/local/bin/test-launch

echo "[BUILD] test-launch v2.2.0 avec Digest+Basic auth installé!"

# Test
/usr/local/bin/test-launch 2>&1 | head -10 || true

#!/usr/bin/env bash
#===============================================================================
# File: install_gstreamer_rtsp_rpi3bplus_bookworm.sh
# Target: Raspberry Pi OS Lite (Bookworm) - Raspberry Pi 3B+
# Purpose:
#   - Install GStreamer + RTSP server dependencies
#   - Install camera/audio tooling (V4L2, ALSA) + libcamera stack
#   - Create sane folders for recordings/logs
#   - Provide quick post-install checks (non-destructive)
#
# Version: 1.0.1
# Changelog:
#   - 1.0.1: Fixed silent exit issue with logging setup
#   - 1.0.0: Initial release (deps install + folders + basic checks)
#===============================================================================

# Don't use set -e at the start - we'll handle errors manually
set -uo pipefail

SCRIPT_NAME="$(basename "$0")"
LOG_DIR="/var/log/rpi-cam"
LOG_FILE="${LOG_DIR}/install.log"

RECORD_DIR="/var/cache/rpi-cam/recordings"
TMP_DIR="/var/cache/rpi-cam/tmp"

#---------------------------
# Helpers
#---------------------------
msg() { printf "[%s] %s\n" "$SCRIPT_NAME" "$*"; }
msg_ok() { printf "[%s] \033[0;32m✓\033[0m %s\n" "$SCRIPT_NAME" "$*"; }
msg_warn() { printf "[%s] \033[0;33m⚠\033[0m %s\n" "$SCRIPT_NAME" "$*"; }
msg_err() { printf "[%s] \033[0;31m✗\033[0m %s\n" "$SCRIPT_NAME" "$*"; }
die() { msg_err "ERROR: $*"; exit 1; }

need_root() {
  if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    die "Ce script doit être exécuté en tant que root: sudo ./${SCRIPT_NAME}"
  fi
  msg_ok "Exécution en tant que root"
}

setup_logs() {
  # Create log directory
  if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    msg_warn "Impossible de créer $LOG_DIR - les logs seront uniquement sur la console"
    return 0
  fi
  
  # Create/touch log file
  if ! touch "$LOG_FILE" 2>/dev/null; then
    msg_warn "Impossible de créer $LOG_FILE - les logs seront uniquement sur la console"
    return 0
  fi
  
  chmod 640 "$LOG_FILE" 2>/dev/null || true
  
  # Setup logging to file + console (with fallback if it fails)
  if command -v tee >/dev/null 2>&1; then
    # Test if process substitution works
    if exec 3>&1 && exec > >(tee -a "$LOG_FILE") 2>&1; then
      msg_ok "Logging activé vers $LOG_FILE"
    else
      exec 1>&3 2>&1  # Restore stdout
      msg_warn "Redirection de log échouée - logs console uniquement"
    fi
    exec 3>&- 2>/dev/null || true
  fi
}

apt_install() {
  local pkgs=("$@")
  msg "Installation: ${pkgs[*]}"
  if ! DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${pkgs[@]}"; then
    msg_warn "Certains paquets n'ont pas pu être installés: ${pkgs[*]}"
    return 1
  fi
  return 0
}

#---------------------------
# Main
#---------------------------
echo "========================================"
echo " Installation GStreamer + RTSP Server"
echo " Raspberry Pi OS Bookworm (64-bit)"
echo "========================================"
echo ""

need_root
setup_logs

msg "Démarrage de l'installation sur: $(uname -a)"
msg "Version OS:"
cat /etc/os-release 2>/dev/null || msg_warn "Impossible de lire /etc/os-release"

msg "Création des répertoires..."
mkdir -p "$RECORD_DIR" "$TMP_DIR" || die "Impossible de créer les répertoires"
chmod 755 /var/cache/rpi-cam 2>/dev/null || true
chmod 755 "$RECORD_DIR" "$TMP_DIR" 2>/dev/null || true
msg_ok "Répertoires créés"

msg "Mise à jour des index apt..."
if ! apt-get update -y; then
  die "Échec de apt-get update"
fi
msg_ok "Index apt mis à jour"

msg "Mise à niveau des paquets de base..."
apt-get upgrade -y || msg_warn "Certains paquets n'ont pas pu être mis à niveau"

msg "Installation des outils de base..."
apt_install \
  ca-certificates \
  curl \
  wget \
  git \
  jq \
  nano \
  vim \
  htop \
  tmux \
  unzip \
  lsof \
  net-tools \
  iproute2 \
  psmisc \
  usbutils || true

msg "Installation des outils de diagnostic vidéo/audio..."
apt_install \
  v4l-utils \
  ffmpeg \
  alsa-utils || true

# GStreamer stack:
# - base/good/bad/ugly/libav give broad codec/plugin coverage
# - gstreamer1.0-rtsp installs RTSP server libs and examples on Debian/RPi OS
#   (package names can vary slightly by distro; Bookworm uses these)
msg "Installation de GStreamer + serveur RTSP..."
apt_install \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav \
  gstreamer1.0-rtsp \
  libgstrtspserver-1.0-0 || msg_warn "Certains paquets GStreamer n'ont pas pu être installés"

# libcamera stack (CSI camera support on modern Pi OS)
# On Bookworm, libcamera is the default camera stack.
msg "Installation de la stack libcamera (support caméra CSI)..."
apt_install \
  libcamera-apps \
  libcamera0 \
  gstreamer1.0-libcamera || msg_warn "Paquets libcamera non installés (normal si pas de caméra CSI)"

msg "Installation des paquets optionnels (systemd, logrotate)..."
apt_install \
  systemd \
  logrotate || true

msg "Nettoyage du cache apt..."
apt-get autoremove -y 2>/dev/null || true
apt-get clean 2>/dev/null || true
msg_ok "Cache apt nettoyé"

msg_ok "Cache apt nettoyé"

echo ""
msg "========================================"
msg "Vérifications post-installation"
msg "========================================"

msg "1) Périphériques USB:"
lsusb 2>/dev/null || msg_warn "Impossible de lister les périphériques USB"

msg "2) Périphériques vidéo:"
if ls -l /dev/video* 2>/dev/null; then
  msg_ok "Périphériques vidéo trouvés"
else
  msg_warn "Aucun /dev/video* trouvé (caméra USB non branchée ou non détectée)"
fi

msg "3) Formats V4L2 (si /dev/video0 existe):"
if [[ -e /dev/video0 ]]; then
  v4l2-ctl -d /dev/video0 --all 2>/dev/null || true
  v4l2-ctl -d /dev/video0 --list-formats-ext 2>/dev/null || true
  msg_ok "Informations V4L2 récupérées"
else
  msg_warn "Vérification V4L2 ignorée - /dev/video0 absent"
fi

msg "4) Périphériques de capture ALSA:"
arecord -l 2>/dev/null || msg_warn "Aucun périphérique de capture ALSA trouvé"

msg "5) Présence de libcamera:"
if command -v libcamera-hello >/dev/null 2>&1; then
  msg_ok "libcamera-hello trouvé"
else
  msg_warn "libcamera-hello non trouvé"
fi
if command -v libcamera-vid >/dev/null 2>&1; then
  msg_ok "libcamera-vid trouvé"
else
  msg_warn "libcamera-vid non trouvé"
fi

msg "6) Version GStreamer:"
if gst-launch-1.0 --version 2>/dev/null; then
  msg_ok "GStreamer installé"
else
  msg_err "GStreamer non installé correctement!"
fi

msg "7) Recherche du binaire test-launch (serveur RTSP):"
TEST_LAUNCH_PATH="$(command -v test-launch 2>/dev/null || true)"
if [[ -n "${TEST_LAUNCH_PATH}" ]]; then
  msg_ok "test-launch trouvé: ${TEST_LAUNCH_PATH}"
else
  # Try common Debian paths
  CANDIDATE="$(ls /usr/lib/*/gstreamer-1.0/test-launch 2>/dev/null | head -n 1 || true)"
  if [[ -n "${CANDIDATE}" ]]; then
    msg_ok "test-launch trouvé: ${CANDIDATE}"
  else
    msg_warn "test-launch non trouvé dans PATH ou emplacements standards."
    msg "   Vous pouvez quand même utiliser libgstrtspserver pour votre serveur RTSP."
  fi
fi

cat <<'EOF'

================================================================================
 ✓ Installation terminée avec succès !
================================================================================

Répertoires créés:
  - /var/cache/rpi-cam/recordings   (stockage des enregistrements)
  - /var/cache/rpi-cam/tmp          (fichiers temporaires)

Log d'installation:
  - /var/log/rpi-cam/install.log

Étapes suivantes:
  1) Branchez votre microphone USB et votre caméra USB/CSI
  2) Vérifiez les formats disponibles:
       v4l2-ctl -d /dev/video0 --list-formats-ext
       arecord -l
  3) Si votre caméra USB supporte la sortie H.264, préférez-la
     (moins de charge CPU, meilleure stabilité)

Conseil:
  Pour la longévité de la carte SD, enregistrez en segments courts (1-5 min)
  et supprimez/rotez les anciens fichiers régulièrement.

================================================================================

EOF

msg_ok "Installation terminée!"
exit 0

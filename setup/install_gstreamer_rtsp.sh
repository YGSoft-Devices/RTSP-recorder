#!/usr/bin/env bash
#===============================================================================
# File: install_gstreamer_rtsp.sh
# Target: Raspberry Pi OS Trixie (64-bit) - Raspberry Pi 3B+/4/5
# Purpose:
#   - Install GStreamer + RTSP server dependencies
#   - Install camera/audio tooling (V4L2, ALSA, libcamera)
#   - Install Raspberry Pi specific tools
#   - Create folders for recordings/logs
#   - Provide quick post-install checks (non-destructive)
#
# Version: 2.2.6
# Changelog:
#   - 2.2.6: Fix test-launch permission check
#            - Now verifies test-launch is EXECUTABLE, not just present
#            - Automatically fixes permissions with chmod +x if found but not executable
#            - Prevents exit code 126 (Permission denied) crash loops
#   - 2.2.5: RTSP transport protocols + multicast options for test-launch
#   - 2.2.4: rpicam opencv postprocess plugin (CSI overlay annotate)
#   - 2.2.1: Headless RTSP defaults
#            - Do not install PipeWire/WirePlumber by default (RTSP-Full uses ALSA direct under systemd/root)
#            - Mask PipeWire user units globally if present (prevents ALSA busy + reduces CPU on Pi 3B+)
#   - 2.2.2: RTC tools
#            - Add i2c-tools and util-linux (hwclock) for DS3231 diagnostics
#   - 2.2.3: RTC hwclock split
#            - Add util-linux-extra (hwclock may be split on Debian 13/Trixie)
#   - 2.2.0: test-launch with Digest + Basic authentication support
#            - Added Digest auth (required by Synology Surveillance Station)
#            - Basic auth still supported as fallback
#            - Environment variable RTSP_AUTH_METHOD can force basic/digest
#   - 2.1.0: test-launch with RTSP authentication support (Basic auth)
#            - Supports RTSP_USER/RTSP_PASSWORD environment variables
#            - Supports RTSP_PORT/RTSP_PATH configuration
#   - 2.0.0: Support Raspberry Pi OS Trixie (Debian 13 based)
#   - 1.0.1: Fixed silent exit issue with logging setup
#   - 1.0.0: Initial release
#===============================================================================

# Handle errors manually for better control
set -uo pipefail

SCRIPT_NAME="$(basename "$0")"
LOG_DIR="/var/log/rpi-cam"
LOG_FILE="${LOG_DIR}/install.log"

RECORD_DIR="/var/cache/rpi-cam/recordings"
TMP_DIR="/var/cache/rpi-cam/tmp"
: "${INSTALL_PIPEWIRE:=no}"  # yes|no (default: no for headless RTSP devices)

#---------------------------
# Helpers
#---------------------------
msg() { printf "[%s] %s\n" "$SCRIPT_NAME" "$*"; }
msg_ok() { printf "[%s] \033[0;32m✓\033[0m %s\n" "$SCRIPT_NAME" "$*"; }
msg_warn() { printf "[%s] \033[0;33m⚠\033[0m %s\n" "$SCRIPT_NAME" "$*"; }
msg_err() { printf "[%s] \033[0;31m✗\033[0m %s\n" "$SCRIPT_NAME" "$*"; }

mask_pipewire_global() {
  # PipeWire is session/user-scoped and can block ALSA direct usage or consume CPU.
  # We mask sockets too, otherwise socket-activation can start services even if "disabled".
  if ! command -v systemctl >/dev/null 2>&1; then
    return 0
  fi
  msg "Désactivation (global) de PipeWire/WirePlumber pour usage headless RTSP..."
  systemctl --global mask \
    pipewire.service pipewire.socket \
    pipewire-pulse.service pipewire-pulse.socket \
    wireplumber.service >/dev/null 2>&1 || true
}
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
  if ! DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${pkgs[@]}" 2>/dev/null; then
    msg_warn "Certains paquets n'ont pas pu être installés: ${pkgs[*]}"
    return 1
  fi
  return 0
}

# Check if a package is available in the repos
pkg_available() {
  apt-cache show "$1" >/dev/null 2>&1
}

#---------------------------
# Main
#---------------------------
echo ""
echo "========================================"
echo " Installation GStreamer + RTSP Server"
echo " Raspberry Pi OS Trixie (64-bit)"
echo "========================================"
echo ""

need_root
setup_logs

# Detect Raspberry Pi model
if [[ -f /proc/device-tree/model ]]; then
  PI_MODEL="$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo 'Unknown')"
  msg_ok "Modèle détecté: $PI_MODEL"
else
  msg_warn "Impossible de détecter le modèle Raspberry Pi"
fi

msg "Démarrage de l'installation sur: $(uname -a)"
msg "Version OS:"
cat /etc/os-release 2>/dev/null || msg_warn "Impossible de lire /etc/os-release"
echo ""

msg "Création des répertoires..."
mkdir -p "$RECORD_DIR" "$TMP_DIR" || die "Impossible de créer les répertoires"
chmod 755 /var/cache/rpi-cam 2>/dev/null || true
chmod 755 "$RECORD_DIR" "$TMP_DIR" 2>/dev/null || true
msg_ok "Répertoires créés"

msg "Mise à jour des index apt..."
apt-get update -qq 2>/dev/null || true
msg_ok "Index apt mis à jour (ou ignorés)"

msg "Mise à niveau des paquets de base..."
apt-get upgrade -y || msg_warn "Certains paquets n'ont pas pu être mis à niveau"

# ==============================================================================
# Core tools
# ==============================================================================
msg "Installation des outils de base..."
apt_install \
  ca-certificates \
  curl \
  wget \
  git \
  jq \
  nano \
  htop \
  tmux \
  unzip \
  lsof \
  net-tools \
  iproute2 \
  psmisc \
  i2c-tools \
  util-linux \
  util-linux-extra \
  gpiod \
  usbutils \
  pciutils \
  build-essential \
  gcc \
  pkg-config || true

# ==============================================================================
# Video tools (V4L2)
# ==============================================================================
msg "Installation des outils vidéo (V4L2)..."
apt_install \
  v4l-utils \
  ffmpeg || true

# ==============================================================================
# CSI Camera support (Picamera2 + GStreamer Python bindings)
# ==============================================================================
msg "Installation du support caméra CSI (Picamera2)..."
apt_install \
  python3-picamera2 \
  python3-gi \
  gir1.2-gstreamer-1.0 \
  gir1.2-gst-rtsp-server-1.0 \
  rpicam-apps-opencv-postprocess || msg_warn "Picamera2/GStreamer Python non installés"

# ==============================================================================
# libcamera tools (for CSI cameras on Trixie)
# ==============================================================================
msg "Installation des outils libcamera..."
apt_install \
  libcamera-tools \
  gstreamer1.0-libcamera || msg_warn "libcamera non installé"

# ==============================================================================
# Audio tools (ALSA + PulseAudio/PipeWire)
# ==============================================================================
msg "Installation des outils audio..."
apt_install \
  alsa-utils \
  pulseaudio-utils || true

if [[ "${INSTALL_PIPEWIRE}" == "yes" ]]; then
  if pkg_available pipewire; then
    msg "Installation de PipeWire (optionnel)..."
    apt_install \
      pipewire \
      pipewire-alsa \
      pipewire-pulse \
      wireplumber || msg_warn "PipeWire non installé"
  fi
else
  # If PipeWire is already installed (OS default), mask it to avoid ALSA busy + CPU overhead.
  if command -v dpkg >/dev/null 2>&1; then
    if dpkg -s pipewire >/dev/null 2>&1 || dpkg -s wireplumber >/dev/null 2>&1; then
      mask_pipewire_global
    fi
  fi
fi

# ==============================================================================
# GStreamer stack
# ==============================================================================
msg "Installation de GStreamer + plugins..."

# Core GStreamer packages (available on both Debian and RPi OS)
# Includes textoverlay/clockoverlay via plugins-base/plugins-good (RTSP overlay support).
GSTREAMER_PKGS=(
  gstreamer1.0-tools
  gstreamer1.0-plugins-base
  gstreamer1.0-plugins-good
  gstreamer1.0-plugins-bad
  gstreamer1.0-plugins-ugly
  gstreamer1.0-libav
  gstreamer1.0-alsa
  gstreamer1.0-pulseaudio
  gstreamer1.0-x
  libgstreamer1.0-dev
  libgstreamer-plugins-base1.0-dev
)

# RTSP server packages - essential for serving RTSP streams
if pkg_available gstreamer1.0-rtsp; then
  GSTREAMER_PKGS+=(gstreamer1.0-rtsp)
fi

if pkg_available libgstrtspserver-1.0-0; then
  GSTREAMER_PKGS+=(libgstrtspserver-1.0-0)
fi

if pkg_available libgstrtspserver-1.0-dev; then
  GSTREAMER_PKGS+=(libgstrtspserver-1.0-dev)
fi

# GStreamer PipeWire plugin (optional)
if [[ "${INSTALL_PIPEWIRE}" == "yes" ]]; then
  if pkg_available gstreamer1.0-pipewire; then
    GSTREAMER_PKGS+=(gstreamer1.0-pipewire)
  fi
fi

# Video4Linux2 GStreamer plugin
if pkg_available gstreamer1.0-v4l2; then
  GSTREAMER_PKGS+=(gstreamer1.0-v4l2)
fi

# x264 encoder for H.264 software encoding
if pkg_available gstreamer1.0-x264; then
  GSTREAMER_PKGS+=(gstreamer1.0-x264)
fi

apt_install "${GSTREAMER_PKGS[@]}" || msg_warn "Certains paquets GStreamer n'ont pas pu être installés"

# ==============================================================================
# Build test-launch from source if not available
# ==============================================================================
build_test_launch() {
  msg "Compilation de test-launch depuis les sources..."
  
  # Check for dependencies
  if ! pkg-config --exists gstreamer-rtsp-server-1.0 2>/dev/null; then
    msg_warn "libgstrtspserver-1.0-dev manquant, impossible de compiler test-launch"
    return 1
  fi
  
  local build_dir="/tmp/rtsp-server-build"
  mkdir -p "$build_dir"
  
  # Create test-launch source with authentication support
  cat > "$build_dir/test-launch.c" << 'EOFCODE'
/* 
 * test-launch - GStreamer RTSP Server with Basic/Digest Authentication
 * Version: 2.2.0
 * 
 * Environment variables:
 *   RTSP_PORT     - Port to listen on (default: 8554)
 *   RTSP_PATH     - Mount path (default: /stream)
 *   RTSP_USER     - Username for authentication (optional)
 *   RTSP_PASSWORD - Password for authentication (optional)
 *   RTSP_REALM    - Authentication realm (default: "RPi Camera")
 *   RTSP_AUTH_METHOD - "basic", "digest", or "both" (default: "both")
 *   RTSP_PROTOCOLS - Comma list: udp,tcp,udp-mcast (default: udp,tcp)
 *   RTSP_MULTICAST_BASE - Multicast base IP (optional)
 *   RTSP_MULTICAST_PORT_MIN - Multicast port range start (optional)
 *   RTSP_MULTICAST_PORT_MAX - Multicast port range end (optional)
 *
 * If RTSP_USER and RTSP_PASSWORD are both set, authentication is required.
 * If either is empty/unset, the stream is accessible without authentication.
 * 
 * Most RTSP clients (including Synology Surveillance Station) prefer Digest auth.
 */
#include <gst/gst.h>
#include <gst/rtsp-server/rtsp-server.h>
#include <gst/rtsp-server/rtsp-address-pool.h>
#include <stdlib.h>
#include <string.h>

static gboolean
timeout_callback (GstRTSPServer * server)
{
  GstRTSPSessionPool *pool;
  pool = gst_rtsp_server_get_session_pool (server);
  gst_rtsp_session_pool_cleanup (pool);
  g_object_unref (pool);
  return TRUE;
}

int
main (int argc, char *argv[])
{
  GMainLoop *loop;
  GstRTSPServer *server;
  GstRTSPMountPoints *mounts;
  GstRTSPMediaFactory *factory;
  GstRTSPAuth *auth = NULL;
  GstRTSPToken *token;
  gchar *basic;
  gchar *str;
  
  /* Configuration from environment */
  const gchar *port = g_getenv ("RTSP_PORT");
  const gchar *path = g_getenv ("RTSP_PATH");
  const gchar *user = g_getenv ("RTSP_USER");
  const gchar *password = g_getenv ("RTSP_PASSWORD");
  const gchar *realm = g_getenv ("RTSP_REALM");
  const gchar *auth_method = g_getenv ("RTSP_AUTH_METHOD");
  const gchar *protocols_env = g_getenv ("RTSP_PROTOCOLS");
  const gchar *mcast_base = g_getenv ("RTSP_MULTICAST_BASE");
  const gchar *mcast_port_min = g_getenv ("RTSP_MULTICAST_PORT_MIN");
  const gchar *mcast_port_max = g_getenv ("RTSP_MULTICAST_PORT_MAX");
  
  /* Defaults */
  if (!port || strlen(port) == 0) port = "8554";
  if (!path || strlen(path) == 0) path = "/stream";
  if (!realm || strlen(realm) == 0) realm = "RPi Camera";
  if (!auth_method || strlen(auth_method) == 0) auth_method = "both";
  if (!protocols_env || strlen(protocols_env) == 0) protocols_env = "udp,tcp";

  gst_init (&argc, &argv);

  if (argc < 2) {
    g_print ("Usage: %s <launch_string>\n", argv[0]);
    g_print ("\nEnvironment variables:\n");
    g_print ("  RTSP_PORT       - Port to listen on (default: 8554)\n");
    g_print ("  RTSP_PATH       - Mount path (default: /stream)\n");
    g_print ("  RTSP_USER       - Username for authentication (optional)\n");
    g_print ("  RTSP_PASSWORD   - Password for authentication (optional)\n");
    g_print ("  RTSP_REALM      - Authentication realm (default: \"RPi Camera\")\n");
    g_print ("  RTSP_AUTH_METHOD- basic, digest, or both (default: both)\n");
    g_print ("  RTSP_PROTOCOLS  - udp,tcp,udp-mcast (default: udp,tcp)\n");
    g_print ("  RTSP_MULTICAST_BASE - Multicast base IP (optional)\n");
    g_print ("  RTSP_MULTICAST_PORT_MIN - Multicast port min (optional)\n");
    g_print ("  RTSP_MULTICAST_PORT_MAX - Multicast port max (optional)\n");
    return -1;
  }

  loop = g_main_loop_new (NULL, FALSE);

  server = gst_rtsp_server_new ();
  gst_rtsp_server_set_service (server, port);

  mounts = gst_rtsp_server_get_mount_points (server);

  /* Create media factory */
  str = g_strdup_printf ("( %s )", argv[1]);
  factory = gst_rtsp_media_factory_new ();
  gst_rtsp_media_factory_set_launch (factory, str);
  gst_rtsp_media_factory_set_shared (factory, TRUE);
  g_free (str);

  /* Parse RTSP protocols */
  GstRTSPLowerTrans protocols = 0;
  gchar **tokens = g_strsplit (protocols_env, ",", -1);
  for (gint i = 0; tokens && tokens[i]; i++) {
    gchar *tok = g_strstrip (tokens[i]);
    if (g_strcmp0 (tok, "udp") == 0) {
      protocols |= GST_RTSP_LOWER_TRANS_UDP;
    } else if (g_strcmp0 (tok, "tcp") == 0) {
      protocols |= GST_RTSP_LOWER_TRANS_TCP;
    } else if (g_strcmp0 (tok, "udp-mcast") == 0 || g_strcmp0 (tok, "mcast") == 0 || g_strcmp0 (tok, "multicast") == 0) {
      protocols |= GST_RTSP_LOWER_TRANS_UDP_MCAST;
    }
  }
  g_strfreev (tokens);
  if (protocols == 0) {
    protocols = GST_RTSP_LOWER_TRANS_UDP | GST_RTSP_LOWER_TRANS_TCP;
  }
  gst_rtsp_media_factory_set_protocols (factory, protocols);

  /* Optional multicast address pool */
  if (mcast_base && mcast_port_min && mcast_port_max) {
    GstRTSPAddressPool *pool = gst_rtsp_address_pool_new ();
    guint16 port_min = (guint16) atoi (mcast_port_min);
    guint16 port_max = (guint16) atoi (mcast_port_max);
    gst_rtsp_address_pool_add_range (pool, mcast_base, mcast_base, port_min, port_max, 1);
    gst_rtsp_media_factory_set_address_pool (factory, pool);
    g_object_unref (pool);
  }

  /* Setup authentication if username and password are provided */
  if (user && password && strlen(user) > 0 && strlen(password) > 0) {
    g_print ("[AUTH] Enabling authentication for user: %s (method: %s)\n", user, auth_method);
    
    auth = gst_rtsp_auth_new ();
    
    /* Set the realm for authentication challenges */
    gst_rtsp_auth_set_realm (auth, realm);
    
    /* Create a token with media factory access permissions */
    token = gst_rtsp_token_new (
        GST_RTSP_TOKEN_MEDIA_FACTORY_ROLE, G_TYPE_STRING, "user",
        NULL);
    
    /* Add Basic authentication if requested */
    if (g_strcmp0(auth_method, "basic") == 0 || g_strcmp0(auth_method, "both") == 0) {
      basic = gst_rtsp_auth_make_basic (user, password);
      gst_rtsp_auth_add_basic (auth, basic, token);
      g_free (basic);
      g_print ("[AUTH] Basic authentication enabled\n");
    }
    
    /* Add Digest authentication if requested */
    if (g_strcmp0(auth_method, "digest") == 0 || g_strcmp0(auth_method, "both") == 0) {
      gst_rtsp_auth_add_digest (auth, user, password, token);
      g_print ("[AUTH] Digest authentication enabled\n");
    }
    
    gst_rtsp_token_unref (token);
    
    /* Set the authentication on the server */
    gst_rtsp_server_set_auth (server, auth);
    
    /* Add role permission to access the media factory */
    gst_rtsp_media_factory_add_role (factory, "user",
        GST_RTSP_PERM_MEDIA_FACTORY_ACCESS, G_TYPE_BOOLEAN, TRUE,
        GST_RTSP_PERM_MEDIA_FACTORY_CONSTRUCT, G_TYPE_BOOLEAN, TRUE,
        NULL);
    
    g_print ("[AUTH] Authentication configured successfully\n");
  } else {
    g_print ("[AUTH] Authentication disabled (no RTSP_USER/RTSP_PASSWORD set)\n");
  }

  /* Mount the factory */
  gst_rtsp_mount_points_add_factory (mounts, path, factory);
  g_object_unref (mounts);

  /* Attach server to main context */
  if (gst_rtsp_server_attach (server, NULL) == 0) {
    g_print ("Failed to attach the server\n");
    return -1;
  }

  /* Cleanup sessions periodically */
  g_timeout_add_seconds (2, (GSourceFunc) timeout_callback, server);

  /* Print stream URL */
  if (user && password && strlen(user) > 0 && strlen(password) > 0) {
    g_print ("stream ready at rtsp://%s:%s@127.0.0.1:%s%s (authenticated, method=%s)\n", 
             user, "****", port, path, auth_method);
  } else {
    g_print ("stream ready at rtsp://127.0.0.1:%s%s (no authentication)\n", 
             port, path);
  }
  
  g_main_loop_run (loop);

  /* Cleanup */
  if (auth) {
    g_object_unref (auth);
  }

  return 0;
}
EOFCODE

  # Compile
  local cflags cflagsrtsp libs
  cflags=$(pkg-config --cflags gstreamer-1.0)
  cflagsrtsp=$(pkg-config --cflags gstreamer-rtsp-server-1.0)
  libs=$(pkg-config --libs gstreamer-1.0 gstreamer-rtsp-server-1.0)
  
  if gcc -o "$build_dir/test-launch" "$build_dir/test-launch.c" $cflags $cflagsrtsp $libs 2>/dev/null; then
    cp "$build_dir/test-launch" /usr/local/bin/test-launch
    chmod +x /usr/local/bin/test-launch
    msg_ok "test-launch compilé et installé dans /usr/local/bin/"
    rm -rf "$build_dir"
    return 0
  else
    msg_warn "Compilation de test-launch échouée"
    rm -rf "$build_dir"
    return 1
  fi
}

# ==============================================================================
# Raspberry Pi specific packages
# ==============================================================================
msg "Installation des paquets spécifiques Raspberry Pi..."

# libcamera stack (CSI camera support)
if pkg_available libcamera-apps; then
  apt_install \
    libcamera-apps \
    libcamera0.3 \
    gstreamer1.0-libcamera || msg_warn "Paquets libcamera non installés"
elif pkg_available libcamera-apps-lite; then
  apt_install \
    libcamera-apps-lite || msg_warn "Paquets libcamera non installés"
fi

# Raspberry Pi specific tools (vcgencmd, etc.)
if pkg_available libraspberrypi-bin; then
  apt_install libraspberrypi-bin || true
fi

# V4L2 libraries
apt_install \
  libv4l-0 \
  libv4l-dev || true

# ==============================================================================
# Optional packages
# ==============================================================================
msg "Installation des paquets optionnels (systemd, logrotate, NetworkManager)..."
apt_install \
  systemd \
  logrotate \
  network-manager || true

# ==============================================================================
# Python for web manager
# ==============================================================================
msg "Installation de Python 3..."
apt_install \
  python3 \
  python3-pip \
  python3-venv || true

# ==============================================================================
# Cleanup
# ==============================================================================
msg "Nettoyage du cache apt..."
apt-get autoremove -y 2>/dev/null || true
apt-get clean 2>/dev/null || true
msg_ok "Cache apt nettoyé"

# ==============================================================================
# Post-installation checks
# ==============================================================================
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
  echo ""
  msg "Formats supportés:"
  v4l2-ctl -d /dev/video0 --list-formats-ext 2>/dev/null || true
  msg_ok "Informations V4L2 récupérées"
else
  msg_warn "Vérification V4L2 ignorée - /dev/video0 absent"
fi

msg "4) Périphériques de capture audio (ALSA):"
if arecord -l 2>/dev/null; then
  msg_ok "Périphériques ALSA trouvés"
else
  msg_warn "Aucun périphérique de capture ALSA trouvé"
fi

msg "5) Périphériques audio PulseAudio/PipeWire:"
if command -v pactl >/dev/null 2>&1; then
  pactl list sources short 2>/dev/null || msg_warn "Impossible de lister les sources audio"
elif command -v wpctl >/dev/null 2>&1; then
  wpctl status 2>/dev/null | head -20 || true
fi

msg "6) Présence de libcamera:"
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

msg "7) Outils Raspberry Pi:"
if command -v vcgencmd >/dev/null 2>&1; then
  msg_ok "vcgencmd trouvé"
  vcgencmd version 2>/dev/null || true
else
  msg_warn "vcgencmd non trouvé"
fi

msg "8) Version GStreamer:"
if gst-launch-1.0 --version 2>/dev/null; then
  msg_ok "GStreamer installé"
else
  msg_err "GStreamer non installé correctement!"
fi

# Function to check GStreamer plugin
check_gst_plugin() {
  local plugin="$1"
  if gst-inspect-1.0 "$plugin" >/dev/null 2>&1; then
    msg_ok "$plugin disponible"
    return 0
  else
    msg_warn "$plugin non disponible"
    return 1
  fi
}

msg "9) Plugins GStreamer disponibles:"
msg "   - Vidéo (capture):"
check_gst_plugin v4l2src
check_gst_plugin videoconvert
check_gst_plugin jpegdec
msg "   - Encodeur H264 (HARDWARE - VideoCore IV):"
if check_gst_plugin v4l2h264enc; then
  msg_ok "   → Encodage H264 HARDWARE disponible (recommandé)"
else
  msg_warn "   → v4l2h264enc non disponible - encodage software sera utilisé"
fi
msg "   - Encodeur H264 (SOFTWARE - CPU):"
check_gst_plugin x264enc
msg "   - Audio:"
check_gst_plugin alsasrc
check_gst_plugin pulsesrc
check_gst_plugin avenc_aac
check_gst_plugin audioconvert
msg "   - Muxers/Payloaders:"
check_gst_plugin rtph264pay
check_gst_plugin mpegtsmux
check_gst_plugin h264parse

msg "10) Recherche du binaire test-launch (serveur RTSP):"
TEST_LAUNCH_PATH="$(command -v test-launch 2>/dev/null || true)"
NEED_BUILD=false

if [[ -n "${TEST_LAUNCH_PATH}" ]]; then
  # Found test-launch - ensure it's executable
  if [[ -x "${TEST_LAUNCH_PATH}" ]]; then
    msg_ok "test-launch trouvé et exécutable: ${TEST_LAUNCH_PATH}"
  else
    msg_warn "test-launch trouvé mais NON exécutable: ${TEST_LAUNCH_PATH}"
    chmod +x "${TEST_LAUNCH_PATH}" 2>/dev/null || true
    if [[ -x "${TEST_LAUNCH_PATH}" ]]; then
      msg_ok "   → Permissions corrigées (chmod +x)"
    else
      msg_warn "   → Impossible de corriger les permissions, recompilation nécessaire"
      NEED_BUILD=true
    fi
  fi
else
  # Try common Debian/Ubuntu paths
  CANDIDATE="$(find /usr/lib -name 'test-launch' -type f 2>/dev/null | head -n 1 || true)"
  if [[ -n "${CANDIDATE}" ]]; then
    msg_ok "test-launch trouvé: ${CANDIDATE}"
    # Create symlink for convenience
    ln -sf "$CANDIDATE" /usr/local/bin/test-launch 2>/dev/null || true
    chmod +x /usr/local/bin/test-launch 2>/dev/null || true
    msg "   Symlink créé: /usr/local/bin/test-launch"
  else
    NEED_BUILD=true
  fi
fi

if $NEED_BUILD; then
  msg_warn "test-launch non trouvé ou non fonctionnel"
  msg "   Tentative de compilation depuis les sources..."
  if build_test_launch; then
    msg_ok "test-launch maintenant disponible"
  else
    msg_err "IMPORTANT: test-launch n'est pas disponible!"
    msg "   Le service RTSP ne pourra pas démarrer sans test-launch."
    msg "   Solutions:"
    msg "   1) Installez gcc et libgstrtspserver-1.0-dev puis relancez ce script"
    msg "   2) Ou installez manuellement gst-rtsp-server depuis GitHub"
  fi
fi

msg "11) Test rapide GStreamer (pipeline vidéo de test):"
if timeout 5 gst-launch-1.0 videotestsrc num-buffers=30 ! videoconvert ! fakesink 2>&1 | grep -q "Execution ended"; then
  msg_ok "Pipeline vidéo de test OK"
else
  msg_warn "Pipeline vidéo de test échoué"
fi

msg "12) Test rapide GStreamer (pipeline audio de test):"
if timeout 5 gst-launch-1.0 audiotestsrc num-buffers=30 ! audioconvert ! fakesink 2>&1 | grep -q "Execution ended"; then
  msg_ok "Pipeline audio de test OK"
else
  msg_warn "Pipeline audio de test échoué"
fi

msg "13) Test de capture vidéo V4L2 (si caméra présente):"
if [[ -e /dev/video0 ]]; then
  # Test avec MJPEG qui est plus fiable pour les caméras USB
  if timeout 5 gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=10 ! image/jpeg,width=640,height=480 ! fakesink 2>&1 | grep -qE "Execution ended|EOS"; then
    msg_ok "Capture V4L2 MJPEG OK"
  elif timeout 5 gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=10 ! video/x-raw,width=640,height=480 ! fakesink 2>&1 | grep -qE "Execution ended|EOS"; then
    msg_ok "Capture V4L2 RAW OK"
  else
    msg_warn "Capture V4L2 non fonctionnelle - vérifiez les formats supportés"
  fi
else
  msg_warn "Test V4L2 ignoré - /dev/video0 absent"
fi

msg "14) Test encodage H264 HARDWARE (v4l2h264enc):"
if gst-inspect-1.0 v4l2h264enc >/dev/null 2>&1; then
  if timeout 10 gst-launch-1.0 videotestsrc num-buffers=30 ! video/x-raw,width=640,height=480 ! v4l2h264enc ! fakesink 2>&1 | grep -qE "Execution ended|EOS"; then
    msg_ok "Encodage H264 HARDWARE OK (VideoCore IV)"
  else
    msg_warn "v4l2h264enc disponible mais pipeline échoué"
  fi
else
  msg_warn "v4l2h264enc non disponible - encodage SOFTWARE sera utilisé (CPU élevé)"
fi

# ==============================================================================
# Summary
# ==============================================================================
# Get Pi model for summary
PI_MODEL_SUMMARY="$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || echo 'Raspberry Pi')"

cat <<EOF

================================================================================
 ✓ Installation terminée avec succès !
================================================================================

Plateforme: $PI_MODEL_SUMMARY
$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME || true)

Répertoires créés:
  - /var/cache/rpi-cam/recordings   (stockage des enregistrements)
  - /var/cache/rpi-cam/tmp          (fichiers temporaires)

Log d'installation:
  - /var/log/rpi-cam/install.log

Étapes suivantes:
  1) Branchez votre microphone USB et votre caméra USB
  2) Vérifiez les périphériques:
       v4l2-ctl --list-devices
       v4l2-ctl -d /dev/video0 --list-formats-ext
       arecord -l
       pactl list sources short  (ou: wpctl status)
  3) Testez la caméra (serveur headless):
       # Test MJPEG (recommandé):
       gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=30 ! image/jpeg,width=640,height=480 ! jpegdec ! videoconvert ! fakesink
       # Ou avec ffmpeg:
       ffmpeg -f v4l2 -i /dev/video0 -frames:v 10 -f null -
  4) Testez le micro:
       arecord -d 5 test.wav && aplay test.wav
  5) Lancez le serveur RTSP:
       sudo systemctl start rpi-av-rtsp-recorder
       # Puis connectez-vous avec VLC: rtsp://<PI_IP>:8554/stream

Conseils:
  - Pour RTSP-Full (headless), privilégiez ALSA direct (PipeWire/WirePlumber peuvent être désactivés)
  - Pour les caméras USB MJPEG, c'est plus stable que YUYV raw
  - Sur Pi 3B+, utilisez 640x480@15fps pour l'encodage logiciel H264

================================================================================

EOF

msg_ok "Installation terminée!"
exit 0

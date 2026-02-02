#!/usr/bin/env python3
"""
RTSP Recorder Web Manager - Configuration
Central configuration file for constants, defaults, and metadata.

Version: 1.2.0
"""

import os

# ============================================================================
# Application Version (read from VERSION file)
# ============================================================================
def _read_version():
    """Read version from VERSION file at project root."""
    # Try multiple locations (dev vs installed)
    version_paths = [
        '/opt/rpi-cam-webmanager/VERSION',  # Installed location
        os.path.join(os.path.dirname(__file__), '..', 'VERSION'),  # Relative to config.py
        os.path.join(os.path.dirname(__file__), 'VERSION'),  # Same dir
    ]
    for path in version_paths:
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return '2.30.20'  # Fallback

APP_VERSION = _read_version()
GITHUB_REPO = 'YGSoft-Devices/RTSP-recorder'

# ============================================================================
# File Paths
# ============================================================================
CONFIG_FILE = "/etc/rpi-cam/config.env"
SERVICE_NAME = "rpi-av-rtsp-recorder"
SCRIPT_PATH = "/usr/local/bin/rpi_av_rtsp_recorder.sh"
WPA_SUPPLICANT_FILE = "/etc/wpa_supplicant/wpa_supplicant.conf"

# WiFi/Network Configuration Files
WIFI_FAILOVER_CONFIG_FILE = '/etc/rpi-cam/wifi_failover.json'
AP_CONFIG_FILE = '/etc/rpi-cam/ap_mode.json'

# Camera Profiles
CAMERA_PROFILES_FILE = '/etc/rpi-cam/camera_profiles.json'
SCHEDULER_STATE_FILE = '/tmp/rpi-cam-scheduler-state.json'

# Recordings
LOCKED_FILES_PATH = '/etc/rpi-cam/locked_recordings.json'
THUMBNAIL_CACHE_DIR = '/var/cache/rpi-cam/thumbnails'

# ONVIF
ONVIF_CONFIG_FILE = '/etc/rpi-cam/onvif.conf'
ONVIF_SERVICE_NAME = 'rpi-cam-onvif'

# Meeting API
MEETING_CONFIG_FILE = '/etc/rpi-cam/meeting.json'

# Watchdog
WATCHDOG_STATE_FILE = '/tmp/rpi-cam-watchdog-state.json'

# Log Files
LOG_FILES = {
    'rtsp': '/var/log/rpi-cam/rtsp.log',
    'recorder': '/var/log/rpi-cam/recorder.log',
    'webmanager': '/var/log/rpi-cam/webmanager.log'
}

# ============================================================================
# Platform Detection
# ============================================================================

def detect_platform():
    """Detect Raspberry Pi model and available features."""
    platform_info = {
        'is_raspberry_pi': True,
        'model': 'Raspberry Pi',
        'has_vcgencmd': False,
        'has_led_control': False,
        'has_libcamera': False,
        'boot_config': None
    }
    
    # Get Raspberry Pi model
    if os.path.exists('/proc/device-tree/model'):
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read().strip().rstrip('\x00')
                platform_info['model'] = model
        except:
            pass
    
    # Check for vcgencmd (Raspberry Pi tools)
    platform_info['has_vcgencmd'] = os.path.exists('/usr/bin/vcgencmd')
    
    # Check for LED control (always available on Pi)
    platform_info['has_led_control'] = (
        os.path.exists('/sys/class/leds/PWR') or 
        os.path.exists('/sys/class/leds/ACT') or
        os.path.exists('/sys/class/leds/led0') or
        os.path.exists('/sys/class/leds/led1')
    )
    
    # Check for libcamera
    platform_info['has_libcamera'] = (
        os.path.exists('/usr/bin/libcamera-hello') or
        os.path.exists('/usr/bin/libcamera-vid')
    )
    
    # Find boot config file (Trixie uses /boot/firmware/)
    boot_config_paths = [
        '/boot/firmware/config.txt',  # Raspberry Pi OS Trixie/Bookworm
        '/boot/config.txt',           # Raspberry Pi OS legacy
    ]
    for path in boot_config_paths:
        if os.path.exists(path):
            platform_info['boot_config'] = path
            break
    
    return platform_info


# Initialize platform info at startup
PLATFORM = detect_platform()

# Dynamic paths based on platform
BOOT_CONFIG_FILE = PLATFORM['boot_config'] or "/boot/firmware/config.txt"
NETWORK_MANAGER_AVAILABLE = os.path.exists("/usr/bin/nmcli")

# ============================================================================
# Default Configuration Values (matching bash script)
# ============================================================================
DEFAULT_CONFIG = {
    # RTSP Settings
    "RTSP_PORT": "8554",
    "RTSP_PATH": "stream",
    "RTSP_PROTOCOLS": "udp,tcp",
    # RTSP Authentication (optional - both required for auth to be enabled)
    "RTSP_USER": "",
    "RTSP_PASSWORD": "",
    
    # Camera INPUT Settings (VIDEOIN_* - what the camera captures)
    # These are the physical camera parameters and should NOT be modified by ONVIF/NVR
    "VIDEOIN_WIDTH": "640",
    "VIDEOIN_HEIGHT": "480",
    "VIDEOIN_FPS": "15",
    "VIDEOIN_DEVICE": "/dev/video0",
    "VIDEOIN_FORMAT": "auto",
    
    # RTSP OUTPUT Settings (VIDEOOUT_* - what the stream outputs)
    # These can be modified by ONVIF/NVR to scale/transcode the output
    "VIDEOOUT_WIDTH": "",   # Empty = same as input
    "VIDEOOUT_HEIGHT": "",  # Empty = same as input  
    "VIDEOOUT_FPS": "",     # Empty = same as input
    
    # Legacy aliases (for backwards compatibility with old configs)
    # Prefer VIDEOIN_* for input, VIDEOOUT_* for output
    "VIDEO_WIDTH": "640",
    "VIDEO_HEIGHT": "480",
    "VIDEO_FPS": "15",
    "VIDEO_DEVICE": "/dev/video0",
    "VIDEO_FORMAT": "auto",
    "STREAM_SOURCE_MODE": "camera",
    "STREAM_SOURCE_URL": "",
    "RTSP_PROXY_TRANSPORT": "auto",
    "RTSP_PROXY_AUDIO": "auto",
    "RTSP_PROXY_LATENCY_MS": "100",
    "SCREEN_DISPLAY": ":0.0",
    "VIDEO_OVERLAY_ENABLE": "no",
    "VIDEO_OVERLAY_TEXT": "",
    "VIDEO_OVERLAY_POSITION": "top-left",
    "VIDEO_OVERLAY_SHOW_DATETIME": "no",
    "VIDEO_OVERLAY_DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "VIDEO_OVERLAY_CLOCK_POSITION": "bottom-right",
    "VIDEO_OVERLAY_FONT_SIZE": "24",
    "CSI_OVERLAY_MODE": "software",
    "CAMERA_TYPE": "auto",
    "CAMERA_DEVICE": "/dev/video0",
    "CSI_ENABLE": "auto",
    "USB_ENABLE": "auto",
    
    # Camera Settings
    "CAMERA_AUTOFOCUS": "yes",  # yes, no, or auto (don't change)
    "CAMERA_PROFILES_ENABLED": "no",  # Enable camera profiles scheduler
    "CAMERA_PROFILES_FILE": "/etc/rpi-cam/camera_profiles.json",  # Profiles storage
    
    # H264 Encoding Settings (for x264enc on Pi 3B+)
    "H264_BITRATE_KBPS": "1200",
    "H264_BITRATE_MODE": "cbr",  # cbr = constant, vbr = variable (for Synology)
    "H264_KEYINT": "30",
    "H264_PROFILE": "",
    "H264_QP": "",
    
    # Stream Quality Level (1-5 like Synology, or 'custom')
    "STREAM_QUALITY": "3",  # 1=very low, 2=low, 3=medium, 4=high, 5=very high, custom=manual

    # Relay / GPIO
    "RELAY_ENABLE": "no",
    "RELAY_GPIO_PIN": "0",
    "RELAY_GPIO_CHIP": "gpiochip0",
    "RELAY_ACTIVE_HIGH": "true",
    "RELAY_OUTPUT_NAME": "RelayOutput",
    "RELAY_OUTPUT_TOKEN": "RelayOutput1",
    
    # Recording (disabled - use external recording via ffmpeg)
    "RECORD_ENABLE": "no",
    "RECORD_DIR": "/var/cache/rpi-cam/recordings",
    "SEGMENT_SECONDS": "300",
    "MIN_FREE_DISK_MB": "1000",
    "MAX_DISK_MB": "0",  # 0 = no limit, otherwise max storage in MB
    
    # Audio Settings
    "AUDIO_ENABLE": "auto",
    "AUDIO_RATE": "48000",
    "AUDIO_CHANNELS": "1",
    "AUDIO_BITRATE_KBPS": "64",
    "AUDIO_DEVICE": "auto",
    "AUDIO_GAIN": "1.0",  # Audio amplification (0.0-3.0, 1.0 = no change)
    
    # Advanced Settings
    "GST_DEBUG_LEVEL": "2",
    "LOG_DIR": "/var/log/rpi-cam",
    "LOW_LATENCY": "1",
    
    # Meeting API Integration
    "MEETING_ENABLED": "no",
    "MEETING_API_URL": "https://meeting.ygsoft.fr/api",
    "MEETING_DEVICE_KEY": "",
    "MEETING_TOKEN_CODE": "",
    "MEETING_HEARTBEAT_INTERVAL": "60",
    "MEETING_PROVISIONED": "no",  # Set to "yes" after successful provisioning (locks config)

    # Monitoring / SNMP (optional)
    "SNMP_ENABLED": "no",
    "SNMP_SERVER_HOST": "",
    "SNMP_SERVER_PORT": "162",
     
    # Network Settings
    "NETWORK_MODE": "dhcp",  # dhcp, static
    "NETWORK_STATIC_IP": "",
    "NETWORK_GATEWAY": "",
    "NETWORK_DNS": "8.8.8.8",
    "NETWORK_INTERFACE_PRIORITY": "eth0,wlan1,wlan0",  # Order of preference
}

# ============================================================================
# System Configuration (not in config.env, managed separately)
# ============================================================================
SYSTEM_DEFAULTS = {
    # WiFi settings (primary network)
    "WIFI_SSID": "",
    "WIFI_PASSWORD": "",
    "WIFI_COUNTRY": "FR",
    # Fallback WiFi (secondary network)
    "WIFI_FALLBACK_SSID": "",
    "WIFI_FALLBACK_PASSWORD": "",
    # WiFi interface assignments
    "WIFI_PRIMARY_INTERFACE": "wlan0",  # Built-in WiFi
    "WIFI_SECONDARY_INTERFACE": "wlan1",  # USB dongle 5GHz
    # LED settings (Pi only)
    "LED_PWR_ENABLE": "1",
    "LED_ACT_ENABLE": "1",
    # GPU Memory (Pi only)
    "GPU_MEM": "256",
}

# ============================================================================
# Configuration Metadata for UI
# ============================================================================
CONFIG_METADATA = {
    "RTSP_PORT": {
        "label": "Port RTSP",
        "type": "number",
        "min": 1,
        "max": 65535,
        "help": "Port d'écoute du serveur RTSP",
        "category": "rtsp"
    },
    "RTSP_PATH": {
        "label": "Chemin RTSP",
        "type": "text",
        "help": "Chemin du flux (ex: rtsp://IP:port/stream)",
        "category": "rtsp"
    },
    "RTSP_PROTOCOLS": {
        "label": "Protocoles RTSP",
        "type": "text",
        "help": "Liste séparée par virgules: udp,tcp,udp-mcast",
        "category": "rtsp"
    },
    "RTSP_USER": {
        "label": "Utilisateur RTSP",
        "type": "text",
        "help": "Nom d'utilisateur pour l'authentification RTSP (optionnel)",
        "category": "rtsp"
    },
    "RTSP_PASSWORD": {
        "label": "Mot de passe RTSP",
        "type": "password",
        "help": "Mot de passe pour l'authentification RTSP (optionnel)",
        "category": "rtsp"
    },
    # Camera INPUT settings (VIDEOIN_*) - physical camera capture parameters
    "VIDEOIN_WIDTH": {
        "label": "Largeur entrée caméra",
        "type": "number",
        "min": 320,
        "max": 4096,
        "help": "Largeur en pixels capturée par la caméra",
        "category": "video"
    },
    "VIDEOIN_HEIGHT": {
        "label": "Hauteur entrée caméra",
        "type": "number",
        "min": 240,
        "max": 2160,
        "help": "Hauteur en pixels capturée par la caméra",
        "category": "video"
    },
    "VIDEOIN_FPS": {
        "label": "FPS entrée caméra",
        "type": "number",
        "min": 1,
        "max": 60,
        "help": "Images par seconde capturées par la caméra",
        "category": "video"
    },
    "VIDEOIN_DEVICE": {
        "label": "Périphérique caméra",
        "type": "text",
        "help": "Chemin du périphérique USB (ex: /dev/video0)",
        "category": "video"
    },
    "VIDEOIN_FORMAT": {
        "label": "Format entrée caméra",
        "type": "select",
        "options": ["auto", "MJPG", "YUYV", "H264"],
        "help": "Format préféré pour les caméras USB (auto = sélection automatique)",
        "category": "video"
    },
    # RTSP OUTPUT settings (VIDEOOUT_*) - stream output parameters (can be modified by ONVIF/NVR)
    "VIDEOOUT_WIDTH": {
        "label": "Largeur sortie RTSP",
        "type": "text",
        "help": "Largeur de sortie du flux RTSP (vide = même que l'entrée). Peut être modifié par ONVIF/NVR.",
        "category": "video"
    },
    "VIDEOOUT_HEIGHT": {
        "label": "Hauteur sortie RTSP",
        "type": "text",
        "help": "Hauteur de sortie du flux RTSP (vide = même que l'entrée). Peut être modifié par ONVIF/NVR.",
        "category": "video"
    },
    "VIDEOOUT_FPS": {
        "label": "FPS sortie RTSP",
        "type": "text",
        "help": "FPS de sortie du flux RTSP (vide = même que l'entrée). Peut être modifié par ONVIF/NVR.",
        "category": "video"
    },
    # Legacy aliases for backwards compatibility
    "VIDEO_WIDTH": {
        "label": "Largeur vidéo (legacy)",
        "type": "number",
        "min": 320,
        "max": 4096,
        "help": "Alias pour VIDEOIN_WIDTH",
        "category": "video"
    },
    "VIDEO_HEIGHT": {
        "label": "Hauteur vidéo (legacy)",
        "type": "number",
        "min": 240,
        "max": 2160,
        "help": "Alias pour VIDEOIN_HEIGHT",
        "category": "video"
    },
    "VIDEO_FPS": {
        "label": "Images par seconde (legacy)",
        "type": "number",
        "min": 1,
        "max": 60,
        "help": "Alias pour VIDEOIN_FPS",
        "category": "video"
    },
    "VIDEO_DEVICE": {
        "label": "Périphérique vidéo (legacy)",
        "type": "text",
        "help": "Alias pour VIDEOIN_DEVICE",
        "category": "video"
    },
    "VIDEO_FORMAT": {
        "label": "Format vidéo (legacy)",
        "type": "select",
        "options": ["auto", "MJPG", "YUYV", "H264"],
        "help": "Alias pour VIDEOIN_FORMAT",
        "category": "video"
    },
    "STREAM_SOURCE_MODE": {
        "label": "Mode source",
        "type": "select",
        "options": ["camera", "rtsp", "mjpeg", "screen"],
        "help": "Source du flux: caméra locale, proxy RTSP, MJPEG, ou capture écran",
        "category": "video"
    },
    "STREAM_SOURCE_URL": {
        "label": "URL source",
        "type": "text",
        "help": "URL de la source RTSP/MJPEG (si mode proxy)",
        "category": "video"
    },
    "RTSP_PROXY_TRANSPORT": {
        "label": "Transport RTSP source",
        "type": "select",
        "options": ["auto", "tcp", "udp"],
        "help": "Transport RTSP côté source (proxy)",
        "category": "video"
    },
    "RTSP_PROXY_AUDIO": {
        "label": "Audio proxy RTSP",
        "type": "select",
        "options": ["auto", "yes", "no"],
        "help": "Relayer l'audio du flux RTSP source",
        "category": "video"
    },
    "RTSP_PROXY_LATENCY_MS": {
        "label": "Latence RTSP source (ms)",
        "type": "number",
        "min": 0,
        "max": 1000,
        "help": "Buffer de latence pour rtspsrc",
        "category": "video"
    },
    "SCREEN_DISPLAY": {
        "label": "Display écran",
        "type": "text",
        "help": "Display X11 pour capture écran (ex: :0.0)",
        "category": "video"
    },
    "VIDEO_OVERLAY_ENABLE": {
        "label": "Overlay RTSP",
        "type": "select",
        "options": ["yes", "no"],
        "help": "Afficher un overlay texte/date sur le flux RTSP (USB + CSI)",
        "category": "video"
    },
    "VIDEO_OVERLAY_TEXT": {
        "label": "Texte overlay",
        "type": "text",
        "help": "Texte libre. Tokens: {CAMERA_TYPE}, {VIDEO_DEVICE}, {VIDEO_RESOLUTION}, {VIDEO_FPS}, {VIDEO_FORMAT}",
        "category": "video"
    },
    "VIDEO_OVERLAY_POSITION": {
        "label": "Position overlay texte",
        "type": "select",
        "options": ["top-left", "top-right", "bottom-left", "bottom-right"],
        "help": "Position du texte sur le flux",
        "category": "video"
    },
    "VIDEO_OVERLAY_SHOW_DATETIME": {
        "label": "Overlay date/heure",
        "type": "select",
        "options": ["yes", "no"],
        "help": "Afficher la date/heure sur le flux RTSP",
        "category": "video"
    },
    "VIDEO_OVERLAY_DATETIME_FORMAT": {
        "label": "Format date/heure",
        "type": "text",
        "help": "Format strftime (ex: %Y-%m-%d %H:%M:%S)",
        "category": "video"
    },
    "VIDEO_OVERLAY_CLOCK_POSITION": {
        "label": "Position date/heure",
        "type": "select",
        "options": ["top-left", "top-right", "bottom-left", "bottom-right"],
        "help": "Position de la date/heure sur le flux",
        "category": "video"
    },
    "VIDEO_OVERLAY_FONT_SIZE": {
        "label": "Taille police overlay",
        "type": "number",
        "min": 1,
        "max": 64,
        "help": "Taille de police (Sans)",
        "category": "video"
    },
    "CSI_OVERLAY_MODE": {
        "label": "Mode overlay CSI",
        "type": "select",
        "options": ["software", "libcamera"],
        "help": "software = overlay GStreamer (decode/encode), libcamera = rpicam-vid annotate (date/heure non supportee)",
        "category": "video"
    },
    "CSI_ENABLE": {
        "label": "Caméra CSI",
        "type": "select",
        "options": ["auto", "yes", "no"],
        "help": "Activer la caméra CSI (Raspberry Pi Camera)",
        "category": "video"
    },
    "USB_ENABLE": {
        "label": "Caméra USB",
        "type": "select",
        "options": ["auto", "yes", "no"],
        "help": "Activer la caméra USB",
        "category": "video"
    },
    "CAMERA_AUTOFOCUS": {
        "label": "Autofocus",
        "type": "select",
        "options": ["yes", "no", "auto"],
        "help": "Activer l'autofocus au démarrage (auto = ne pas modifier)",
        "category": "video"
    },
    "CAMERA_PROFILES_ENABLED": {
        "label": "Scheduler profils caméra",
        "type": "select",
        "options": ["yes", "no"],
        "help": "Activer le changement automatique de profil selon l'heure",
        "category": "video"
    },
    "CAMERA_PROFILES_FILE": {
        "label": "Fichier des profils",
        "type": "text",
        "help": "Chemin du fichier JSON des profils caméra",
        "category": "video"
    },
    "RECORD_DIR": {
        "label": "Répertoire d'enregistrement",
        "type": "text",
        "help": "Chemin où stocker les enregistrements",
        "category": "recording"
    },
    "SEGMENT_SECONDS": {
        "label": "Durée des segments",
        "type": "number",
        "min": 30,
        "max": 3600,
        "help": "Durée de chaque fichier en secondes",
        "category": "recording"
    },
    "MIN_FREE_DISK_MB": {
        "label": "Espace libre minimum (Mo)",
        "type": "number",
        "min": 0,
        "max": 1000000,
        "help": "Espace disque libre à conserver en permanence. 0 = pas de limite. Les anciens enregistrements sont supprimés automatiquement.",
        "category": "recording"
    },
    "AUDIO_ENABLE": {
        "label": "Audio",
        "type": "select",
        "options": ["auto", "yes", "no"],
        "help": "Activer la capture audio",
        "category": "audio"
    },
    "AUDIO_RATE": {
        "label": "Fréquence d'échantillonnage",
        "type": "select",
        "options": ["22050", "44100", "48000"],
        "help": "Fréquence audio en Hz",
        "category": "audio"
    },
    "AUDIO_CHANNELS": {
        "label": "Canaux audio",
        "type": "select",
        "options": ["1", "2"],
        "help": "1 = Mono, 2 = Stéréo",
        "category": "audio"
    },
    "AUDIO_BITRATE_KBPS": {
        "label": "Débit audio (kbps)",
        "type": "number",
        "min": 32,
        "max": 320,
        "help": "Débit audio AAC en kbps",
        "category": "audio"
    },
    "AUDIO_DEVICE": {
        "label": "Périphérique audio",
        "type": "text",
        "help": "auto ou périphérique ALSA (ex: plughw:1,0)",
        "category": "audio"
    },
    "GST_DEBUG_LEVEL": {
        "label": "Niveau de debug GStreamer",
        "type": "select",
        "options": ["0", "1", "2", "3", "4", "5", "6"],
        "help": "0=aucun, 2=warnings, 3=info, 6=tout",
        "category": "advanced"
    },
    "LOG_DIR": {
        "label": "Répertoire des logs",
        "type": "text",
        "help": "Chemin pour stocker les fichiers de log",
        "category": "advanced"
    },
    "LOW_LATENCY": {
        "label": "Mode faible latence",
        "type": "select",
        "options": ["1", "0"],
        "help": "1 = activé, 0 = désactivé",
        "category": "advanced"
    },
    "H264_BITRATE_KBPS": {
        "label": "Débit H264 (kbps)",
        "type": "number",
        "min": 500,
        "max": 8000,
        "help": "Débit vidéo H264 (défaut: 1200 kbps pour Pi 3B+)",
        "category": "video"
    },
    "H264_KEYINT": {
        "label": "Intervalle keyframes",
        "type": "number",
        "min": 1,
        "max": 120,
        "help": "Intervalle entre images clés (défaut: 30)",
        "category": "video"
    },
    "H264_PROFILE": {
        "label": "Profil H264 (CSI)",
        "type": "select",
        "options": ["", "baseline", "constrained baseline", "main", "high"],
        "help": "Profil H264 pour le serveur CSI (vide = auto)",
        "category": "video"
    },
    "H264_QP": {
        "label": "Quantizer H264 (CSI)",
        "type": "text",
        "help": "QP fixe 1-51 (vide = auto)",
        "category": "video"
    },
    "RECORD_ENABLE": {
        "label": "Enregistrement local",
        "type": "select",
        "options": ["yes", "no"],
        "help": "Note: Désactivé via RTSP, utilisez ffmpeg externe",
        "category": "recording"
    },
    # Meeting API Configuration
    "MEETING_ENABLED": {
        "label": "Activer Meeting",
        "type": "select",
        "options": ["yes", "no"],
        "help": "Active l'intégration avec l'API Meeting",
        "category": "meeting"
    },
    "MEETING_API_URL": {
        "label": "URL de l'API Meeting",
        "type": "text",
        "help": "URL de base de l'API Meeting (ex: https://meeting.example.com/api)",
        "category": "meeting"
    },
    "MEETING_DEVICE_KEY": {
        "label": "Device Key",
        "type": "text",
        "help": "Clé unique du device fournie par Meeting",
        "category": "meeting"
    },
    "MEETING_TOKEN_CODE": {
        "label": "Token Code",
        "type": "password",
        "help": "Code d'authentification du device",
        "category": "meeting"
    },
    "MEETING_HEARTBEAT_INTERVAL": {
        "label": "Intervalle Heartbeat",
        "type": "number",
        "min": 10,
        "max": 300,
        "help": "Fréquence d'envoi du heartbeat en secondes",
        "category": "meeting"
    },
    "MEETING_PROVISIONED": {
        "label": "Provisionné",
        "type": "select",
        "options": ["yes", "no"],
        "help": "Indique si le device a été provisionné (verrouille la config Meeting)",
        "category": "meeting"
    },
    # Network Configuration
    "NETWORK_MODE": {
        "label": "Mode IP",
        "type": "select",
        "options": ["dhcp", "static"],
        "help": "DHCP automatique ou IP statique",
        "category": "network"
    },
    "NETWORK_STATIC_IP": {
        "label": "Adresse IP statique",
        "type": "text",
        "help": "Ex: 192.168.1.100/24",
        "category": "network"
    },
    "NETWORK_GATEWAY": {
        "label": "Passerelle",
        "type": "text",
        "help": "Ex: 192.168.1.1",
        "category": "network"
    },
    "NETWORK_DNS": {
        "label": "Serveur DNS",
        "type": "text",
        "help": "Ex: 8.8.8.8",
        "category": "network"
    },
    "NETWORK_INTERFACE_PRIORITY": {
        "label": "Priorité des interfaces",
        "type": "text",
        "help": "Ordre de priorité (ex: eth0,wlan1,wlan0)",
        "category": "network"
    },
    "RELAY_ENABLE": {
        "label": "Relais GPIO",
        "type": "select",
        "options": ["yes", "no"],
        "help": "Active le relais ONVIF (GPIO)",
        "category": "onvif"
    },
    "RELAY_GPIO_PIN": {
        "label": "GPIO relais",
        "type": "number",
        "min": 0,
        "max": 40,
        "help": "Numéro de GPIO (BCM) pour le relais",
        "category": "onvif"
    },
    "RELAY_GPIO_CHIP": {
        "label": "GPIO chip",
        "type": "text",
        "help": "GPIO chip (ex: gpiochip0)",
        "category": "onvif"
    },
    "RELAY_ACTIVE_HIGH": {
        "label": "Relais actif à 1",
        "type": "select",
        "options": ["true", "false"],
        "help": "true = niveau haut active le relais",
        "category": "onvif"
    },
    "RELAY_OUTPUT_NAME": {
        "label": "Nom relais",
        "type": "text",
        "help": "Nom affiché du relais",
        "category": "onvif"
    },
    "RELAY_OUTPUT_TOKEN": {
        "label": "Token relais",
        "type": "text",
        "help": "Token ONVIF du relais",
        "category": "onvif"
    },
}

# ============================================================================
# Services that can be safely disabled for power savings
# ============================================================================
OPTIONAL_SERVICES = {
    'modemmanager': {
        'unit': 'ModemManager.service',
        'description': 'Gestion modems 3G/4G',
        'savings_ma': 15,
        'safe_to_disable': True
    },
    'avahi': {
        'unit': 'avahi-daemon.service', 
        'description': 'mDNS/Bonjour discovery',
        'savings_ma': 5,
        'safe_to_disable': True,
        'warning': 'Peut affecter la découverte ONVIF'
    },
    'cloudinit': {
        'units': [
            'cloud-init-local.service',
            'cloud-init-network.service', 
            'cloud-init-main.service',
            'cloud-config.service',
            'cloud-final.service'
        ],
        'description': 'Provisioning cloud',
        'savings_ma': 0,  # RAM only, no direct power
        'safe_to_disable': True
    },
    'serial': {
        'unit': 'serial-getty@ttyAMA0.service',
        'description': 'Console série',
        'savings_ma': 2,
        'safe_to_disable': True
    },
    'tty1': {
        'unit': 'getty@tty1.service',
        'description': 'Console TTY1',
        'savings_ma': 2,
        'safe_to_disable': True
    },
    'udisks2': {
        'unit': 'udisks2.service',
        'description': 'Automontage USB',
        'savings_ma': 5,
        'safe_to_disable': True,
        'warning': 'Désactive l\'automontage des clés USB'
    }
}

# ============================================================================
# Default Camera Profiles
# ============================================================================
DEFAULT_CAMERA_PROFILES = {
    'day': {
        'name': 'Jour',
        'description': 'Profil pour conditions diurnes normales',
        'schedule': {'start': '07:00', 'end': '19:00'},
        'controls': {
            # Will be populated with current camera values on first save
        },
        'enabled': True
    },
    'night': {
        'name': 'Nuit (IR)',
        'description': 'Profil pour caméra IR en conditions nocturnes',
        'schedule': {'start': '19:00', 'end': '07:00'},
        'controls': {
            # Typical night/IR settings - will vary by camera
        },
        'enabled': True
    }
}

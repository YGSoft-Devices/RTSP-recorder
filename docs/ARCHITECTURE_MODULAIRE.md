# Architecture Modulaire - Guide de Refactoring

Version: 1.0.0  
Date: Janvier 2026

Ce document décrit l'architecture modulaire du web-manager après le refactoring de `app.py` (8350 lignes monolithique) vers une structure Flask Blueprints + Services.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Structure des dossiers](#2-structure-des-dossiers)
3. [Fichiers principaux](#3-fichiers-principaux)
4. [Services (Logique métier)](#4-services-logique-métier)
5. [Blueprints (Routes HTTP)](#5-blueprints-routes-http)
6. [Conventions de développement](#6-conventions-de-développement)
7. [Ajout d'une nouvelle fonctionnalité](#7-ajout-dune-nouvelle-fonctionnalité)
8. [Mapping ancien → nouveau](#8-mapping-ancien--nouveau)

---

## 1. Vue d'ensemble

### Avant (Monolithique)
```
web-manager/
├── app.py              # 8350 lignes - TOUT dedans
├── templates/
└── static/
```

### Après (Modulaire)
```
web-manager/
├── app.py              # ~450 lignes - Orchestrateur Flask
├── config.py           # ~130 lignes - Configuration centralisée
├── services/           # 10 modules - Logique métier
├── blueprints/         # 15 modules - Routes HTTP
├── templates/
└── static/
```

### Principes architecturaux

1. **Séparation des responsabilités**
   - `services/` : Logique métier, accès données, commandes système
   - `blueprints/` : Routes HTTP, validation requêtes, formatage réponses

2. **Services réutilisables**
   - Un service peut être utilisé par plusieurs blueprints
   - Les services ne dépendent jamais de Flask (pas de `request`, `jsonify`)

3. **Blueprints minces**
   - Les blueprints ne contiennent que le routage
   - Toute la logique est déléguée aux services

---

## 2. Structure des dossiers

```
web-manager/
├── app.py                      # Point d'entrée Flask
├── config.py                   # Configuration centralisée
├── requirements.txt            # Dépendances Python
├── config.env.example          # Template configuration
│
├── services/                   # === LOGIQUE MÉTIER ===
│   ├── __init__.py             # Exports publics
│   ├── platform_service.py     # Détection plateforme Pi, commandes système
│   ├── config_service.py       # Gestion config.env, services systemd
│   ├── camera_service.py       # Contrôles caméra v4l2, profils
│   ├── network_service.py      # Interfaces réseau, WiFi, failover
│   ├── power_service.py        # LED, GPU, HDMI, économie d'énergie
│   ├── recording_service.py    # Enregistrements, espace disque
│   ├── meeting_service.py      # Meeting API, heartbeat
│   ├── system_service.py       # Diagnostics, logs, mises à jour
│   ├── watchdog_service.py     # RTSP health check, WiFi failover
│   └── media_cache_service.py  # Cache SQLite métadonnées/thumbnails
│
├── blueprints/                 # === ROUTES HTTP ===
│   ├── __init__.py             # Exports publics
│   ├── config_bp.py            # /api/config, /api/service, /api/status
│   ├── camera_bp.py            # /api/camera/*
│   ├── recordings_bp.py        # /api/recordings/*
│   ├── network_bp.py           # /api/network/*
│   ├── system_bp.py            # /api/system/*
│   ├── meeting_bp.py           # /api/meeting/*
│   ├── logs_bp.py              # /api/logs/*
│   ├── video_bp.py             # /api/video/*
│   ├── power_bp.py             # /api/leds/*, /api/power/*
│   ├── onvif_bp.py             # /api/onvif/*
│   ├── detect_bp.py            # /api/detect/*, /api/platform
│   ├── watchdog_bp.py          # /api/rtsp/watchdog/*
│   ├── wifi_bp.py              # /api/wifi/*
│   ├── debug_bp.py             # /api/debug/*
│   └── legacy_bp.py            # Routes rétrocompatibilité
│
├── templates/
│   └── index.html              # Frontend HTML unique
│
└── static/
    ├── css/style.css           # Styles
    └── js/app.js               # JavaScript frontend
```

---

## 3. Fichiers principaux

### 3.1 app.py - Orchestrateur Flask

**Rôle:** Point d'entrée, enregistrement des blueprints, routes globales.

**Contenu attendu:**
```python
# -*- coding: utf-8 -*-
"""
Flask Application - Main orchestrator
Version: X.X.X
"""

from flask import Flask, render_template, jsonify
from config import APP_NAME, APP_VERSION, DEBUG_MODE

# Import all blueprints
from blueprints import (
    config_bp, camera_bp, recordings_bp, network_bp,
    system_bp, meeting_bp, logs_bp, video_bp, power_bp,
    onvif_bp, detect_bp, watchdog_bp, wifi_bp, debug_bp,
    legacy_bp
)

# Import services for initialization
from services.meeting_service import init_meeting_service
from services.watchdog_service import start_watchdog_threads

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# ============================================================================
# BLUEPRINT REGISTRATION
# ============================================================================

blueprints = [
    config_bp, camera_bp, recordings_bp, network_bp,
    system_bp, meeting_bp, logs_bp, video_bp, power_bp,
    onvif_bp, detect_bp, watchdog_bp, wifi_bp, debug_bp,
    legacy_bp
]

for bp in blueprints:
    app.register_blueprint(bp)

# ============================================================================
# GLOBAL ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main page - renders the SPA."""
    return render_template('index.html', ...)

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

# ============================================================================
# BACKGROUND TASKS INITIALIZATION
# ============================================================================

_background_tasks_started = False

@app.before_request
def init_background_tasks():
    """Initialize background tasks on first request (Gunicorn compatible)."""
    global _background_tasks_started
    if not _background_tasks_started:
        _background_tasks_started = True
        init_meeting_service()
        start_watchdog_threads()

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=DEBUG_MODE)
```

**Points clés:**
- Ne contient PAS de logique métier
- Enregistre tous les blueprints
- Initialise les tâches background via `@app.before_request` (compatible Gunicorn)
- Route principale `/` pour le SPA
- Gestionnaire d'erreurs global

---

### 3.2 config.py - Configuration centralisée

**Rôle:** Constantes, chemins, métadonnées de l'application.

**Contenu attendu:**
```python
# -*- coding: utf-8 -*-
"""
Application Configuration
Version: X.X.X
"""

import os

# ============================================================================
# APPLICATION METADATA
# ============================================================================

APP_NAME = "RTSP Camera Manager"
APP_VERSION = "2.30.3"  # Ou lu depuis fichier VERSION
DEBUG_MODE = os.environ.get('DEBUG', 'false').lower() == 'true'

# ============================================================================
# PATHS
# ============================================================================

# Configuration
CONFIG_DIR = '/etc/rpi-cam'
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.env')
MEETING_CONFIG_FILE = os.path.join(CONFIG_DIR, 'meeting.json')
WIFI_FAILOVER_FILE = os.path.join(CONFIG_DIR, 'wifi_failover.json')
CAMERA_PROFILES_FILE = os.path.join(CONFIG_DIR, 'camera_profiles.json')
ONVIF_CONFIG_FILE = os.path.join(CONFIG_DIR, 'onvif.conf')
AP_MODE_FILE = os.path.join(CONFIG_DIR, 'ap_mode.json')
LOCKED_RECORDINGS_FILE = os.path.join(CONFIG_DIR, 'locked_recordings.json')

# Data
CACHE_DIR = '/var/cache/rpi-cam'
RECORDINGS_DIR = os.path.join(CACHE_DIR, 'recordings')
THUMBNAILS_DIR = os.path.join(CACHE_DIR, 'thumbnails')
MEDIA_CACHE_DB = os.path.join(CACHE_DIR, 'media_cache.db')

# ============================================================================
# SERVICE NAMES
# ============================================================================

SERVICES = {
    'rtsp': 'rpi-av-rtsp-recorder',
    'recorder': 'rtsp-recorder',
    'webmanager': 'rpi-cam-webmanager',
    'onvif': 'rpi-cam-onvif',
    'watchdog': 'rtsp-watchdog'
}

# ============================================================================
# DEFAULTS
# ============================================================================

DEFAULT_CONFIG = {
    'RTSP_PORT': '8554',
    'RTSP_PATH': '/stream',
    'VIDEO_DEVICE': '/dev/video0',
    'VIDEO_WIDTH': '1280',
    'VIDEO_HEIGHT': '720',
    'VIDEO_FPS': '15',
    'AUDIO_ENABLED': 'no',
    'RECORDING_ENABLED': 'no',
    'RECORDING_SEGMENT_DURATION': '300',
    'RECORDING_MIN_FREE_SPACE': '500',
    # ... autres valeurs par défaut
}
```

**Points clés:**
- Toutes les constantes au même endroit
- Chemins absolus
- Valeurs par défaut
- Pas de logique, juste des déclarations

---

## 4. Services (Logique métier)

### 4.1 Structure d'un service

Chaque service suit ce template:

```python
# -*- coding: utf-8 -*-
"""
[Nom] Service - [Description courte]
Version: X.X.X
"""

import os
import subprocess
import json
from typing import Dict, List, Optional, Any

from config import CONFIG_FILE, ...  # Import des constantes
from .platform_service import run_command  # Import d'autres services si besoin

# ============================================================================
# CONSTANTS (locales au service)
# ============================================================================

LOCAL_CONSTANT = "value"

# ============================================================================
# INTERNAL HELPERS
# ============================================================================

def _private_helper():
    """Fonction interne, non exportée."""
    pass

# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================

def public_function(param: str) -> Dict[str, Any]:
    """
    Description de la fonction.
    
    Args:
        param: Description du paramètre
    
    Returns:
        dict: Description du retour
    """
    # Implémentation
    return {'success': True, 'data': ...}
```

### 4.2 Détail de chaque service

#### `platform_service.py` (~210 lignes)

**Responsabilité:** Détection plateforme Raspberry Pi, exécution de commandes système.

**Fonctions exportées:**
```python
def detect_platform() -> Dict[str, Any]:
    """Détecte le modèle Pi, architecture, version kernel."""

def is_raspberry_pi() -> bool:
    """Vérifie si on est sur un Raspberry Pi."""

def run_command(cmd: str, shell: bool = True, timeout: int = 30) -> Dict[str, Any]:
    """Exécute une commande système et retourne stdout/stderr/returncode."""

def run_command_async(cmd: str, shell: bool = True) -> subprocess.Popen:
    """Lance une commande en background."""

def check_command_exists(cmd_name: str) -> bool:
    """Vérifie si une commande existe dans le PATH."""

def get_service_path(service_name: str) -> Optional[str]:
    """Retourne le chemin du fichier service systemd."""
```

---

#### `config_service.py` (~400 lignes)

**Responsabilité:** Gestion de config.env, services systemd, templates de config.

**Fonctions exportées:**
```python
def load_config() -> Dict[str, str]:
    """Charge config.env dans un dictionnaire."""

def save_config(config: Dict[str, str]) -> Dict[str, Any]:
    """Sauvegarde un dictionnaire dans config.env."""

def get_config_value(key: str, default: str = '') -> str:
    """Récupère une valeur de config.env."""

def set_config_value(key: str, value: str) -> bool:
    """Modifie une valeur dans config.env."""

def get_service_status(service_name: str) -> Dict[str, Any]:
    """Retourne le status d'un service systemd."""

def control_service(service_name: str, action: str) -> Dict[str, Any]:
    """start/stop/restart/enable/disable un service."""

def get_all_services_status() -> Dict[str, Dict[str, Any]]:
    """Status de tous les services RTSP."""
```

---

#### `camera_service.py` (~650 lignes)

**Responsabilité:** Contrôles caméra v4l2, profils, autofocus.

**Fonctions exportées:**
```python
def detect_cameras() -> List[Dict[str, Any]]:
    """Liste les caméras disponibles (/dev/videoX)."""

def get_camera_controls(device: str) -> List[Dict[str, Any]]:
    """Liste les contrôles v4l2 d'une caméra."""

def set_camera_control(device: str, control: str, value: int) -> Dict[str, Any]:
    """Modifie un contrôle v4l2."""

def get_camera_formats(device: str) -> List[Dict[str, Any]]:
    """Liste les formats et résolutions supportés."""

def get_autofocus_status(device: str) -> Dict[str, Any]:
    """Retourne le status de l'autofocus."""

def set_autofocus(device: str, enabled: bool) -> Dict[str, Any]:
    """Active/désactive l'autofocus."""

def oneshot_focus(device: str) -> Dict[str, Any]:
    """Déclenche un focus ponctuel."""

# Profils
def list_profiles() -> List[Dict[str, Any]]:
    """Liste les profils caméra sauvegardés."""

def get_profile(name: str) -> Optional[Dict[str, Any]]:
    """Récupère un profil par son nom."""

def save_profile(name: str, controls: Dict[str, int]) -> Dict[str, Any]:
    """Sauvegarde un profil."""

def apply_profile(name: str, device: str) -> Dict[str, Any]:
    """Applique un profil à une caméra."""

def capture_profile(name: str, device: str) -> Dict[str, Any]:
    """Capture les réglages actuels dans un profil."""
```

---

#### `network_service.py` (~800 lignes)

**Responsabilité:** Interfaces réseau, IP statique/DHCP, WiFi, failover.

**Fonctions exportées:**
```python
def get_network_interfaces() -> List[Dict[str, Any]]:
    """Liste toutes les interfaces avec leur config (IP, MAC, état)."""

def get_interface_priority() -> List[str]:
    """Retourne l'ordre de priorité des interfaces."""

def set_interface_priority(priority: List[str]) -> Dict[str, Any]:
    """Définit l'ordre de priorité."""

def configure_static_ip(interface: str, ip: str, gateway: str, dns: str) -> Dict[str, Any]:
    """Configure une IP statique."""

def configure_dhcp(interface: str) -> Dict[str, Any]:
    """Configure DHCP sur une interface."""

def scan_wifi_networks(interface: str = 'wlan0') -> List[Dict[str, Any]]:
    """Scanne les réseaux WiFi disponibles."""

def connect_wifi(ssid: str, password: str, interface: str = 'wlan0') -> Dict[str, Any]:
    """Connecte à un réseau WiFi."""

def disconnect_wifi(interface: str = 'wlan0') -> Dict[str, Any]:
    """Déconnecte du WiFi."""

def get_wifi_status(interface: str = 'wlan0') -> Dict[str, Any]:
    """Retourne le status WiFi (SSID connecté, signal, etc.)."""

# WiFi Failover
def get_failover_config() -> Dict[str, Any]:
    """Retourne la config du failover WiFi."""

def save_failover_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Sauvegarde la config failover."""

def get_failover_status() -> Dict[str, Any]:
    """Status complet du failover (interface active, IPs, etc.)."""
```

---

#### `power_service.py` (~700 lignes)

**Responsabilité:** LED PWR/ACT, mémoire GPU, HDMI, économie d'énergie.

**Fonctions exportées:**
```python
def get_led_status() -> Dict[str, Any]:
    """Status des LEDs PWR et ACT."""

def set_led(led: str, brightness: int) -> Dict[str, Any]:
    """Modifie la luminosité d'une LED (0-255)."""

def get_boot_led_config() -> Dict[str, Any]:
    """Lit la config des LEDs dans config.txt."""

def get_gpu_memory() -> Dict[str, Any]:
    """Retourne la mémoire GPU allouée."""

def set_gpu_memory(size_mb: int) -> Dict[str, Any]:
    """Modifie la mémoire GPU (nécessite reboot)."""

def get_hdmi_status() -> Dict[str, Any]:
    """Status HDMI (actif/inactif, résolution)."""

def set_hdmi(enabled: bool) -> Dict[str, Any]:
    """Active/désactive HDMI."""

def get_power_status() -> Dict[str, Any]:
    """Status complet: bluetooth, audio, CPU freq, économies."""

def get_boot_power_config() -> Dict[str, Any]:
    """Config boot: bluetooth, wifi, hdmi, audio, led."""

def reboot_system(delay: int = 0) -> Dict[str, Any]:
    """Redémarre le système."""

def shutdown_system(delay: int = 0) -> Dict[str, Any]:
    """Éteint le système."""
```

---

#### `recording_service.py` (~500 lignes)

**Responsabilité:** Gestion des enregistrements, espace disque, verrouillage.

**Fonctions exportées:**
```python
def get_recording_dir() -> str:
    """Retourne le répertoire d'enregistrement."""

def get_recordings_list(
    config: Dict = None,
    pattern: str = '*.*',
    sort_by: str = 'date',
    reverse: bool = True
) -> List[Dict[str, Any]]:
    """Liste les fichiers d'enregistrement avec métadonnées."""

def get_recording_info(filename: str) -> Dict[str, Any]:
    """Informations détaillées d'un fichier (durée, codecs, etc.)."""

def delete_recording(filename: str, force: bool = False) -> Dict[str, Any]:
    """Supprime un fichier (respecte le verrouillage sauf si force=True)."""

def delete_old_recordings(max_age_days: int = 30) -> Dict[str, Any]:
    """Supprime les anciens enregistrements non verrouillés."""

def cleanup_recordings(min_free_mb: int = 500) -> Dict[str, Any]:
    """Nettoie jusqu'à atteindre l'espace libre minimum."""

def get_disk_usage(config: Dict = None) -> Dict[str, Any]:
    """Usage disque du répertoire d'enregistrement."""

# Verrouillage
def get_locked_recordings() -> List[str]:
    """Liste des fichiers verrouillés."""

def lock_recording(filename: str) -> Dict[str, Any]:
    """Verrouille un fichier."""

def unlock_recording(filename: str) -> Dict[str, Any]:
    """Déverrouille un fichier."""

def is_recording_locked(filename: str) -> bool:
    """Vérifie si un fichier est verrouillé."""
```

---

#### `meeting_service.py` (~700 lignes)

**Responsabilité:** Intégration Meeting API, heartbeat, provisioning.

**Fonctions exportées:**
```python
def load_meeting_config() -> Dict[str, Any]:
    """Charge la config Meeting (meeting.json ou config.env)."""

def save_meeting_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Sauvegarde la config Meeting."""

def get_meeting_status() -> Dict[str, Any]:
    """Status complet: enabled, connected, provisioned, etc."""

def validate_credentials(api_url: str, device_key: str, token_code: str) -> Dict[str, Any]:
    """Valide des credentials sans les sauvegarder."""

def provision_device(api_url: str, device_key: str, token_code: str) -> Dict[str, Any]:
    """Provisionne le device (consomme un token, change hostname)."""

def send_heartbeat() -> Dict[str, Any]:
    """Envoie un heartbeat à l'API Meeting."""

def get_meeting_device_info() -> Dict[str, Any]:
    """Récupère les infos du device depuis Meeting."""

def request_tunnel(tunnel_type: str = 'ssh', port: int = 22) -> Dict[str, Any]:
    """Demande un tunnel SSH/HTTP."""

def enable_meeting_service(api_url: str, device_key: str, token_code: str, interval: int = 30) -> Dict[str, Any]:
    """Active l'intégration Meeting."""

def disable_meeting_service() -> Dict[str, Any]:
    """Désactive l'intégration Meeting."""

def init_meeting_service() -> Dict[str, Any]:
    """Initialise le service (appelé au démarrage)."""
```

---

#### `system_service.py` (~500 lignes)

**Responsabilité:** Diagnostics, logs, mises à jour système.

**Fonctions exportées:**
```python
def get_diagnostic_info() -> Dict[str, Any]:
    """Informations de diagnostic complètes."""

def get_recent_logs(lines: int = 100, source: str = 'all') -> Dict[str, Any]:
    """Récupère les logs récents de journald."""

def get_service_logs(service_name: str, lines: int = 50, since: str = None) -> Dict[str, Any]:
    """Logs d'un service spécifique."""

def clean_old_logs(max_size_mb: int = 100) -> Dict[str, Any]:
    """Nettoie les anciens logs."""

def check_for_updates() -> Dict[str, Any]:
    """Vérifie les mises à jour de l'application (GitHub)."""

def perform_update(backup: bool = True) -> Dict[str, Any]:
    """Télécharge et applique une mise à jour."""

def get_apt_updates() -> Dict[str, Any]:
    """Liste les paquets APT à mettre à jour."""

def perform_apt_upgrade(packages: List[str] = None, security_only: bool = False) -> Dict[str, Any]:
    """Met à jour les paquets APT."""

def restart_service(service_name: str) -> Dict[str, Any]:
    """Redémarre un service."""

def restart_all_services() -> Dict[str, Any]:
    """Redémarre tous les services RTSP."""
```

---

#### `watchdog_service.py` (~570 lignes)

**Responsabilité:** Surveillance RTSP, health check, WiFi failover automatique.

**Fonctions exportées:**
```python
def get_rtsp_health() -> Dict[str, Any]:
    """Vérifie la santé du serveur RTSP."""

def get_watchdog_status() -> Dict[str, Any]:
    """Status du watchdog (actif, dernière vérification, compteurs)."""

def start_watchdog() -> Dict[str, Any]:
    """Démarre le thread watchdog."""

def stop_watchdog() -> Dict[str, Any]:
    """Arrête le watchdog."""

def restart_rtsp_service() -> Dict[str, Any]:
    """Force le redémarrage du service RTSP."""

def start_watchdog_threads() -> None:
    """Démarre tous les threads de surveillance (appelé au boot)."""

# WiFi failover automatique
def check_wifi_failover() -> Dict[str, Any]:
    """Vérifie et exécute le failover WiFi si nécessaire."""

def get_wifi_failover_status() -> Dict[str, Any]:
    """Status du failover WiFi."""
```

---

#### `media_cache_service.py` (~300 lignes)

**Responsabilité:** Cache SQLite pour métadonnées et thumbnails.

**Fonctions exportées:**
```python
def init_cache() -> None:
    """Initialise la base SQLite."""

def get_cached_metadata(filename: str) -> Optional[Dict[str, Any]]:
    """Récupère les métadonnées cachées d'un fichier."""

def cache_metadata(filename: str, metadata: Dict[str, Any]) -> None:
    """Stocke les métadonnées en cache."""

def invalidate_cache(filename: str) -> None:
    """Invalide le cache d'un fichier."""

def get_thumbnail_path(filename: str) -> str:
    """Retourne le chemin du thumbnail (génère si besoin)."""

def generate_thumbnail(video_path: str, output_path: str) -> bool:
    """Génère un thumbnail pour une vidéo."""

def cleanup_orphan_cache() -> int:
    """Supprime les entrées de cache orphelines."""
```

---

### 4.3 services/__init__.py

Ce fichier exporte les fonctions publiques pour faciliter les imports:

```python
# -*- coding: utf-8 -*-
"""
Services Package - Public exports
Version: 2.30.2
"""

# Platform
from .platform_service import (
    detect_platform, is_raspberry_pi, run_command,
    run_command_async, check_command_exists
)

# Config
from .config_service import (
    load_config, save_config, get_config_value, set_config_value,
    get_service_status, control_service, get_all_services_status
)

# Camera
from .camera_service import (
    detect_cameras, get_camera_controls, set_camera_control,
    get_camera_formats, get_autofocus_status, set_autofocus,
    list_profiles, get_profile, save_profile, apply_profile
)

# ... etc pour chaque service
```

---

## 5. Blueprints (Routes HTTP)

### 5.1 Structure d'un blueprint

```python
# -*- coding: utf-8 -*-
"""
[Nom] Blueprint - [Description courte]
Version: X.X.X
"""

from flask import Blueprint, request, jsonify, Response

from services.xxx_service import (
    function1, function2, function3
)

xxx_bp = Blueprint('xxx', __name__, url_prefix='/api/xxx')

# ============================================================================
# [SECTION] ROUTES
# ============================================================================

@xxx_bp.route('', methods=['GET'])
def list_items():
    """Description de la route."""
    result = function1()
    return jsonify({'success': True, **result})

@xxx_bp.route('/<item_id>', methods=['GET'])
def get_item(item_id):
    """Description de la route."""
    result = function2(item_id)
    
    if not result:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    
    return jsonify({'success': True, 'item': result})

@xxx_bp.route('', methods=['POST'])
def create_item():
    """Description de la route."""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Data required'}), 400
    
    # Validation
    if 'required_field' not in data:
        return jsonify({'success': False, 'error': 'required_field is required'}), 400
    
    result = function3(data)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code
```

### 5.2 Détail de chaque blueprint

#### `config_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/config` | GET | Récupère toute la configuration |
| `/api/config` | POST | Met à jour la configuration |
| `/api/status` | GET | Status général de l'application |
| `/api/service/<action>` | POST | start/stop/restart un service |

#### `camera_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/camera/controls` | GET | Liste les contrôles v4l2 |
| `/api/camera/control` | POST | Modifie un contrôle |
| `/api/camera/autofocus` | GET/POST | Get/set autofocus |
| `/api/camera/focus` | POST | Focus manuel |
| `/api/camera/oneshot-focus` | POST | Focus ponctuel |
| `/api/camera/formats` | GET | Formats supportés |
| `/api/camera/all-controls` | GET | Tous les contrôles |
| `/api/camera/profiles` | GET/POST | Liste/crée profil |
| `/api/camera/profiles/<name>` | GET/PUT/DELETE | CRUD profil |
| `/api/camera/profiles/<name>/apply` | POST | Applique un profil |
| `/api/camera/profiles/<name>/capture` | POST | Capture réglages |

#### `recordings_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/recordings` | GET | Liste basique |
| `/api/recordings/list` | GET | Liste paginée avec filtres |
| `/api/recordings/recent` | GET | Derniers enregistrements |
| `/api/recordings/<filename>` | GET | Info d'un fichier |
| `/api/recordings/<filename>` | DELETE | Supprime un fichier |
| `/api/recordings/download/<filename>` | GET | Télécharge |
| `/api/recordings/stream/<filename>` | GET | Stream avec Range |
| `/api/recordings/lock` | POST | Verrouille fichiers |
| `/api/recordings/delete` | POST | Suppression par lot |

#### `network_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/network/interfaces` | GET | Liste interfaces |
| `/api/network/config` | GET | Config réseau complète |
| `/api/network/priority` | POST | Priorité interfaces |
| `/api/network/static` | POST | IP statique |
| `/api/network/dhcp` | POST | Configure DHCP |
| `/api/network/wifi/override` | GET/POST | Override manuel WiFi |
| `/api/network/ap/status` | GET | Status point d'accès |
| `/api/network/ap/config` | POST | Configure AP |
| `/api/network/ap/start` | POST | Démarre AP |
| `/api/network/ap/stop` | POST | Arrête AP |

#### `system_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/system/info` | GET | Infos système complètes |
| `/api/system/diagnostic` | GET | Diagnostic détaillé |
| `/api/system/health` | GET | Health check simple |
| `/api/system/logs` | GET | Logs récents |
| `/api/system/logs/<service>` | GET | Logs d'un service |
| `/api/system/logs/stream` | GET | SSE logs temps réel |
| `/api/system/logs/clean` | POST | Nettoie les logs |
| `/api/system/ntp` | GET/POST | Config NTP |
| `/api/system/ntp/sync` | POST | Force sync NTP |
| `/api/system/update/check` | GET | Vérifie mises à jour |
| `/api/system/update/perform` | POST | Applique mise à jour |
| `/api/system/reboot` | POST | Redémarre |
| `/api/system/shutdown` | POST | Éteint |
| `/api/system/restart/<service>` | POST | Redémarre service |
| `/api/system/restart-all` | POST | Redémarre tout |

#### `meeting_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/meeting/config` | GET/POST | Config Meeting |
| `/api/meeting/status` | GET | Status connexion |
| `/api/meeting/validate` | POST | Valide credentials |
| `/api/meeting/provision` | GET/POST | Provisioning |
| `/api/meeting/enable` | POST | Active Meeting |
| `/api/meeting/disable` | POST | Désactive Meeting |
| `/api/meeting/heartbeat` | POST | Heartbeat manuel |
| `/api/meeting/device` | GET | Info device |
| `/api/meeting/availability` | GET | Disponibilité |
| `/api/meeting/tunnel` | POST | Demande tunnel |

#### `wifi_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/wifi/scan` | GET | Scanne réseaux |
| `/api/wifi/status` | GET | Status WiFi |
| `/api/wifi/connect` | POST | Connexion WiFi |
| `/api/wifi/disconnect` | POST | Déconnexion |
| `/api/wifi/failover/status` | GET | Status failover |
| `/api/wifi/failover/config` | GET/POST | Config failover |
| `/api/wifi/failover/apply` | POST | Applique config |
| `/api/wifi/failover/interfaces` | GET | Interfaces WiFi |
| `/api/wifi/failover/watchdog` | GET/POST | Watchdog WiFi |

#### `power_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/leds/status` | GET | Status LEDs |
| `/api/leds/set` | POST | Modifie LED |
| `/api/leds/boot-config` | GET | Config boot LEDs |
| `/api/gpu/mem` | GET/POST | Mémoire GPU |
| `/api/power/status` | GET | Status power complet |
| `/api/power/boot-config` | GET | Config boot power |

#### `onvif_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/onvif/status` | GET | Status ONVIF |
| `/api/onvif/config` | GET/POST | Config ONVIF |
| `/api/onvif/restart` | POST | Redémarre ONVIF |

#### `detect_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/detect/cameras` | GET | Détecte caméras |
| `/api/detect/audio` | GET | Détecte audio |
| `/api/platform` | GET | Info plateforme |

#### `watchdog_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/rtsp/watchdog/status` | GET | Status watchdog |
| `/api/rtsp/watchdog` | POST | Contrôle watchdog |

#### `logs_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/logs` | GET | Logs avec filtres |
| `/api/logs/stream` | GET | SSE temps réel |
| `/api/logs/clean` | POST | Nettoie logs |

#### `video_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/video/preview/stream` | GET | Stream MJPEG |
| `/api/video/preview/snapshot` | GET | Capture image |
| `/api/video/preview/status` | GET | Status preview |

#### `debug_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/debug/firmware/check` | GET | Vérifie firmware |
| `/api/debug/firmware/update` | POST | Met à jour firmware |
| `/api/debug/apt/update` | POST | apt update |
| `/api/debug/apt/upgradable` | GET | Paquets à jour |
| `/api/debug/apt/upgrade` | POST | apt upgrade |
| `/api/debug/system/uptime` | GET | Uptime |

#### `legacy_bp.py`
| Route | Méthode | Description |
|-------|---------|-------------|
| `/api/diagnostic` | GET | → /api/system/diagnostic |
| `/api/wifi/current` | GET | → /api/network/wifi |

---

### 5.3 blueprints/__init__.py

```python
# -*- coding: utf-8 -*-
"""
Blueprints Package - Public exports
Version: 2.30.2
"""

from .config_bp import config_bp
from .camera_bp import camera_bp
from .recordings_bp import recordings_bp
from .network_bp import network_bp
from .system_bp import system_bp
from .meeting_bp import meeting_bp
from .logs_bp import logs_bp
from .video_bp import video_bp
from .power_bp import power_bp
from .onvif_bp import onvif_bp
from .detect_bp import detect_bp
from .watchdog_bp import watchdog_bp
from .wifi_bp import wifi_bp
from .debug_bp import debug_bp
from .legacy_bp import legacy_bp

__all__ = [
    'config_bp', 'camera_bp', 'recordings_bp', 'network_bp',
    'system_bp', 'meeting_bp', 'logs_bp', 'video_bp', 'power_bp',
    'onvif_bp', 'detect_bp', 'watchdog_bp', 'wifi_bp', 'debug_bp',
    'legacy_bp'
]
```

---

## 6. Conventions de développement

### 6.1 Nommage

| Type | Convention | Exemple |
|------|------------|---------|
| Service | `xxx_service.py` | `camera_service.py` |
| Blueprint | `xxx_bp.py` | `camera_bp.py` |
| Variable blueprint | `xxx_bp` | `camera_bp` |
| Fonctions service | `snake_case` | `get_camera_controls()` |
| Routes | `/api/domain/action` | `/api/camera/controls` |
| Constantes | `UPPER_SNAKE_CASE` | `CONFIG_FILE` |

### 6.2 Versioning

Chaque fichier contient un header avec la version:
```python
"""
Module Name - Description
Version: X.X.X
"""
```

Incrémenter:
- **Patch** (X.X.1): Bugfix sans changement d'API
- **Minor** (X.1.0): Nouvelle fonctionnalité sans casser l'existant
- **Major** (1.0.0): Changement d'API cassant

### 6.3 Format de retour des services

Tous les services retournent un dictionnaire avec au minimum `success`:
```python
# Succès
return {'success': True, 'data': ..., 'message': '...'}

# Erreur
return {'success': False, 'error': '...'}
```

### 6.4 Format de réponse des blueprints

```python
# Succès
return jsonify({'success': True, ...}), 200

# Erreur client (validation)
return jsonify({'success': False, 'error': '...'}), 400

# Erreur serveur
return jsonify({'success': False, 'error': '...'}), 500

# Non trouvé
return jsonify({'success': False, 'error': 'Not found'}), 404
```

### 6.5 Imports

```python
# Standard library
import os
import json
import subprocess

# Third party
from flask import Blueprint, request, jsonify

# Local - config
from config import CONFIG_FILE, APP_VERSION

# Local - services (from services package)
from services.camera_service import get_camera_controls

# Local - other services (relative import dans services/)
from .platform_service import run_command
```

---

## 7. Ajout d'une nouvelle fonctionnalité

### Exemple: Ajouter la gestion des snapshots périodiques

#### Étape 1: Créer le service

`services/snapshot_service.py`:
```python
# -*- coding: utf-8 -*-
"""
Snapshot Service - Periodic snapshot capture
Version: 1.0.0
"""

import os
import time
from datetime import datetime
from typing import Dict, Any

from config import CACHE_DIR
from .platform_service import run_command

SNAPSHOTS_DIR = os.path.join(CACHE_DIR, 'snapshots')

def capture_snapshot(device: str = '/dev/video0') -> Dict[str, Any]:
    """Capture un snapshot depuis la caméra."""
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    
    filename = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    
    result = run_command(f"ffmpeg -f v4l2 -i {device} -frames:v 1 {filepath}")
    
    if result['returncode'] == 0:
        return {'success': True, 'filename': filename, 'path': filepath}
    else:
        return {'success': False, 'error': result['stderr']}

def list_snapshots() -> list:
    """Liste les snapshots existants."""
    if not os.path.exists(SNAPSHOTS_DIR):
        return []
    
    return sorted(os.listdir(SNAPSHOTS_DIR), reverse=True)

def delete_snapshot(filename: str) -> Dict[str, Any]:
    """Supprime un snapshot."""
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    
    if not os.path.exists(filepath):
        return {'success': False, 'error': 'File not found'}
    
    os.remove(filepath)
    return {'success': True}
```

#### Étape 2: Exporter dans services/__init__.py

```python
# Ajouter:
from .snapshot_service import (
    capture_snapshot, list_snapshots, delete_snapshot
)
```

#### Étape 3: Créer le blueprint

`blueprints/snapshot_bp.py`:
```python
# -*- coding: utf-8 -*-
"""
Snapshot Blueprint - Snapshot management routes
Version: 1.0.0
"""

from flask import Blueprint, request, jsonify, send_file
import os

from services.snapshot_service import (
    capture_snapshot, list_snapshots, delete_snapshot, SNAPSHOTS_DIR
)

snapshot_bp = Blueprint('snapshot', __name__, url_prefix='/api/snapshots')

@snapshot_bp.route('', methods=['GET'])
def get_snapshots():
    """Liste tous les snapshots."""
    snapshots = list_snapshots()
    return jsonify({'success': True, 'snapshots': snapshots})

@snapshot_bp.route('', methods=['POST'])
def take_snapshot():
    """Capture un nouveau snapshot."""
    data = request.get_json() or {}
    device = data.get('device', '/dev/video0')
    
    result = capture_snapshot(device)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@snapshot_bp.route('/<filename>', methods=['GET'])
def get_snapshot(filename):
    """Récupère un snapshot."""
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    
    return send_file(filepath, mimetype='image/jpeg')

@snapshot_bp.route('/<filename>', methods=['DELETE'])
def remove_snapshot(filename):
    """Supprime un snapshot."""
    result = delete_snapshot(filename)
    
    status_code = 200 if result['success'] else 404
    return jsonify(result), status_code
```

#### Étape 4: Enregistrer le blueprint

`blueprints/__init__.py`:
```python
# Ajouter:
from .snapshot_bp import snapshot_bp

__all__ = [..., 'snapshot_bp']
```

`app.py`:
```python
from blueprints import ..., snapshot_bp

blueprints = [..., snapshot_bp]
```

#### Étape 5: Mettre à jour la documentation

- CHANGELOG.md
- AGENTS.md (versions)
- DOCUMENTATION_COMPLETE.md (APIs)

---

## 8. Mapping ancien → nouveau

### Routes principales

| Ancien (app.py) | Nouveau | Blueprint |
|-----------------|---------|-----------|
| `@app.route('/api/config')` | `/api/config` | config_bp |
| `@app.route('/api/diagnostic')` | `/api/system/diagnostic` | system_bp |
| `@app.route('/api/recordings')` | `/api/recordings` | recordings_bp |
| `@app.route('/api/camera/controls')` | `/api/camera/controls` | camera_bp |
| ... | ... | ... |

### Fonctions → Services

| Ancienne fonction | Nouveau service | Fonction |
|-------------------|-----------------|----------|
| `load_config()` | config_service | `load_config()` |
| `detect_cameras()` | camera_service | `detect_cameras()` |
| `get_network_interfaces()` | network_service | `get_network_interfaces()` |
| `send_heartbeat()` | meeting_service | `send_heartbeat()` |
| `get_diagnostic_info()` | system_service | `get_diagnostic_info()` |
| ... | ... | ... |

---

## Annexes

### A. Commandes de déploiement

```powershell
# Déployer un service
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\services\xxx_service.py" -Dest "/opt/rpi-cam-webmanager/services/"

# Déployer un blueprint
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\blueprints\xxx_bp.py" -Dest "/opt/rpi-cam-webmanager/blueprints/"

# Déployer tout le dossier services
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\services\*" -Dest "/opt/rpi-cam-webmanager/services/" -Recursive

# Redémarrer après modifications
.\debug_tools\run_remote.ps1 "sudo systemctl restart rpi-cam-webmanager"

# Voir les logs d'erreur
.\debug_tools\run_remote.ps1 "sudo journalctl -u rpi-cam-webmanager -n 50 --no-pager"
```

### B. Checklist nouveau fichier

- [ ] Header avec version
- [ ] Docstrings pour chaque fonction
- [ ] Import dans `__init__.py`
- [ ] Tests basiques
- [ ] Mise à jour CHANGELOG.md
- [ ] Mise à jour AGENTS.md (versions)
- [ ] Mise à jour DOCUMENTATION_COMPLETE.md si API publique

---

*Version du document: 1.0.0*

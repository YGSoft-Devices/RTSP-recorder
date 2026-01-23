# RTSP Recorder - Interface Web de Gestion

[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)
[![OS](https://img.shields.io/badge/OS-Raspberry%20Pi%20OS%20Trixie-green.svg)](https://www.raspberrypi.com/software/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Interface web complète pour configurer et gérer le service RTSP Recorder sur Raspberry Pi.

**Plateforme cible:**
- Raspberry Pi OS Trixie (64-bit) - basé sur Debian 13
- Raspberry Pi 3B+, 4 ou 5

---

## 🎯 Les 3 Fondements du Projet

Le projet RTSP-Full est conçu pour supporter **3 sources essentielles** :

| Source | Technologie | Exemples |
|--------|-------------|----------|
| 📹 **Caméras USB** | v4l2src (GStreamer) | Microsoft LifeCam, Logitech C920 |
| 📷 **Caméras CSI (PiCam)** | libcamerasrc (GStreamer) | OV5647 (v1), IMX219 (v2), IMX708 (v3) |
| 🎤 **Audio USB** | alsasrc (GStreamer) | Tout microphone USB compatible ALSA |

---

## 📋 Table des matières

- [Fonctionnalités](#-fonctionnalités)
- [Prérequis](#-prérequis)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Utilisation](#-utilisation)
- [API REST](#-api-rest)
- [Architecture](#-architecture)
- [Dépannage](#-dépannage)
- [Changelog](#-changelog)

---

## ✨ Fonctionnalités

### 🎥 Gestion RTSP
- Configuration du port et chemin RTSP
- Affichage de l'URL RTSP complète avec copie en un clic
- Contrôle du service (démarrer/arrêter/redémarrer)

### 📹 Configuration Vidéo
- Résolution configurable (320x240 à 4096x2160)
- Réglage des FPS (1-60)
- **Support caméra USB (V4L2)** avec détection automatique des formats (MJPEG, YUYV, H264)
- **Support caméra CSI (libcamera)** avec détection automatique via rpicam-hello
- Sélection du mode caméra (auto/manuel)
- Encodage hardware H.264 (v4l2h264enc) pour faible consommation CPU

### 🎤 Configuration Audio
- Activation/désactivation de la capture audio
- **Détection automatique des microphones USB** (ALSA)
- Détection par nom de device (`AUDIO_DEVICE_NAME`) pour éviter les changements d'ID
- Fréquence d'échantillonnage configurable (22050/44100/48000 Hz)
- Mode mono ou stéréo
- Débit audio AAC ajustable (32-320 kbps)

### 💾 Enregistrement
- Répertoire d'enregistrement personnalisable
- Segmentation automatique (30s à 1h par fichier)
- Limite d'espace disque avec rotation automatique
- Gestion des fichiers (liste, suppression)
- Affichage de l'espace utilisé

### 📶 Configuration WiFi
- **Réseau principal** : Configuration du WiFi avec scan des réseaux disponibles
- **Réseau de secours (Fallback)** : Second réseau WiFi en cas d'indisponibilité du principal
- Affichage de l'état de connexion en temps réel
- Support NetworkManager (nmcli)

### 💡 Contrôle des LEDs
- **LED Power (Rouge)** : Activation/désactivation de la LED d'alimentation
- **LED Activity (Verte)** : Activation/désactivation de la LED d'activité
- Persistance des paramètres au redémarrage (optionnel)
- Utile pour réduire la consommation ou pour la discrétion

### 🧠 Mémoire GPU
- Configuration de l'allocation mémoire GPU (64-512 Mo)
- Valeurs prédéfinies optimisées pour la vidéo
- Affichage de la valeur actuelle

### ⚙️ Fonctionnalités Avancées
- Niveau de debug GStreamer configurable
- Répertoire de logs personnalisable
- Mode faible latence pour le streaming
- Visualisation des logs en temps réel
- Redémarrage système depuis l'interface
- **Détection automatique de la plateforme**

---

## 📦 Prérequis

### Matériel
- **Debian 13 (Trixie)** sur n'importe quel matériel x86_64 ou ARM64
- **OU Raspberry Pi 3B+/4** avec Raspberry Pi OS Bookworm
- Carte SD ou disque de stockage suffisant
- Caméra USB compatible V4L2
- (Raspberry Pi) Pi Camera (CSI) optionnelle
- (Optionnel) Microphone USB

### Logiciel
- **Debian 13 (Trixie) 64-bit** ou **Raspberry Pi OS Bookworm 64-bit**
- GStreamer 1.0 avec plugins RTSP
- Python 3.11+
- NetworkManager (recommandé) ou wpa_supplicant

### Dépendances système
```bash
# Installation automatique via le script d'installation
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    gstreamer1.0-tools gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    v4l-utils alsa-utils network-manager ffmpeg
```

---

## 🚀 Installation

### Structure du projet

```
RTSP-Full/
├── README.md                    # Ce fichier
├── rpi_av_rtsp_recorder.sh      # Script principal RTSP
├── rtsp_recorder.sh             # Service d'enregistrement ffmpeg
├── web-manager/                 # Interface web Flask
├── esp32/                       # Dérivé ESP32 (caméra only, UI légère)
├── setup/                       # Scripts d'installation
│   ├── install.sh               # Installation complète
│   ├── install_gstreamer_rtsp.sh
│   ├── install_rpi_av_rtsp_recorder.sh
│   ├── install_rtsp_recorder.sh
│   └── install_web_manager.sh
├── docs/                        # Documentation
│   ├── Encyclopedie.md
│   ├── hardware_acceleration_3B+.md
│   └── ...
└── backups/                     # Scripts obsolètes (archive)
```

### Installation rapide (recommandée)

```bash
# Cloner le projet
git clone https://github.com/your-repo/RTSP-Full.git
cd RTSP-Full

# Installation complète (GStreamer + RTSP + Recorder + WebUI)
sudo ./setup/install.sh

# OU installation sélective
sudo ./setup/install.sh --gstreamer   # GStreamer uniquement
sudo ./setup/install.sh --rtsp        # Service RTSP uniquement
sudo ./setup/install.sh --recorder    # Service recording uniquement
sudo ./setup/install.sh --webui       # Interface web uniquement
```

### Installation pas à pas

```bash
# 1. Installer les dépendances GStreamer et compiler test-launch
sudo ./setup/install_gstreamer_rtsp.sh

# 2. Installer le service RTSP streaming
sudo ./setup/install_rpi_av_rtsp_recorder.sh

# 3. Installer le service d'enregistrement (ffmpeg)
sudo ./setup/install_rtsp_recorder.sh

# 4. Installer l'interface web
sudo ./setup/install_web_manager.sh
```

### Démarrage des services

```bash
# Démarrer tous les services
sudo systemctl start rpi-av-rtsp-recorder   # RTSP streaming
sudo systemctl start rtsp-recorder          # Enregistrement
sudo systemctl start rpi-cam-webmanager     # Interface web

# Vérifier le status
sudo systemctl status rpi-av-rtsp-recorder
sudo systemctl status rtsp-recorder
sudo systemctl status rpi-cam-webmanager

# Activer au démarrage
sudo systemctl enable rpi-av-rtsp-recorder
sudo systemctl enable rtsp-recorder
sudo systemctl enable rpi-cam-webmanager
```

### Installation manuelle

```bash
# 1. Créer les répertoires
sudo mkdir -p /opt/rpi-cam-webmanager
sudo mkdir -p /etc/rpi-cam
sudo mkdir -p /var/log/rpi-cam
sudo mkdir -p /var/cache/rpi-cam/recordings

# 2. Copier les fichiers
sudo cp -r web-manager/* /opt/rpi-cam-webmanager/

# 3. Créer l'environnement Python
sudo python3 -m venv /opt/rpi-cam-webmanager/venv
sudo /opt/rpi-cam-webmanager/venv/bin/pip install Flask gunicorn

# 4. Configurer le service systemd
sudo cp install/rpi-cam-webmanager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rpi-cam-webmanager
sudo systemctl start rpi-cam-webmanager
```

---

## ⚙️ Configuration

### Configuration de base

La configuration est stockée dans `/etc/rpi-cam/config.env`:

```bash
# RTSP Settings
RTSP_PORT="8554"
RTSP_PATH="stream"

# Video Settings
VIDEO_WIDTH="1280"
VIDEO_HEIGHT="960"
VIDEO_FPS="20"
VIDEO_DEVICE="/dev/video0"
CSI_ENABLE="auto"
USB_ENABLE="auto"
H264_BITRATE_KBPS="4000"
H264_KEYINT="30"
H264_PROFILE=""
H264_QP=""

# Recording Settings
RECORD_DIR="/var/cache/rpi-cam/recordings"
SEGMENT_SECONDS="300"
MAX_DISK_MB="0"

# Audio Settings
AUDIO_ENABLE="auto"
AUDIO_RATE="48000"
AUDIO_CHANNELS="1"
AUDIO_BITRATE_KBPS="64"
AUDIO_DEVICE="auto"

# Advanced Settings
GST_DEBUG_LEVEL="2"
LOG_DIR="/var/log/rpi-cam"
LOW_LATENCY="1"
```

### Configuration via l'interface web

1. Accédez à `http://<IP>:5000`
2. Naviguez entre les onglets pour configurer
3. Cliquez sur "Sauvegarder" pour appliquer
4. Redémarrez le service si nécessaire

---

## 🖥️ Utilisation

### Accès à l'interface web

```
http://<adresse-ip>:5000
```

### Commandes utiles

```bash
# Voir l'état du service web
sudo systemctl status rpi-cam-webmanager

# Voir les logs en temps réel
journalctl -u rpi-cam-webmanager -f

# Redémarrer le service web
sudo systemctl restart rpi-cam-webmanager

# Voir l'état du service RTSP
sudo systemctl status rpi-av-rtsp-recorder

# Tester la caméra
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext

# Tester l'audio
arecord -l
```

### Tester le flux RTSP

```bash
# Avec VLC
vlc rtsp://<IP>:8554/stream

# Avec ffplay
ffplay rtsp://<IP>:8554/stream

# Avec GStreamer
gst-launch-1.0 rtspsrc location=rtsp://<IP>:8554/stream ! decodebin ! autovideosink
```

---

## 🔌 API REST

L'interface expose une API REST complète:

### Configuration

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/config` | GET | Récupérer la configuration |
| `/api/config` | POST | Sauvegarder la configuration |
| `/api/status` | GET | État du service |
| `/api/platform` | GET | Information sur la plateforme |

### Service Control

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/service/start` | POST | Démarrer le service |
| `/api/service/stop` | POST | Arrêter le service |
| `/api/service/restart` | POST | Redémarrer le service |

### Détection

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/detect/cameras` | GET | Détecter les caméras |
| `/api/detect/audio` | GET | Détecter les périphériques audio |

### WiFi

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/wifi/scan` | GET | Scanner les réseaux WiFi |
| `/api/wifi/status` | GET | État de la connexion WiFi |
| `/api/wifi/connect` | POST | Connecter à un réseau |
| `/api/wifi/disconnect` | POST | Déconnecter |

### LEDs (Raspberry Pi uniquement)

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/leds/status` | GET | État des LEDs |
| `/api/leds/set` | POST | Modifier l'état d'une LED |

### GPU (Raspberry Pi uniquement)

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/gpu/mem` | GET | Mémoire GPU actuelle |
| `/api/gpu/mem` | POST | Modifier la mémoire GPU |

### Enregistrements

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/recordings` | GET | Lister les enregistrements |
| `/api/recordings/delete` | POST | Supprimer des enregistrements |

### Système

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/logs` | GET | Récupérer les logs |
| `/api/system/reboot` | POST | Redémarrer le système |

### Exemples d'utilisation

```bash
# Obtenir la configuration
curl http://localhost:5000/api/config

# Sauvegarder une configuration
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{"VIDEO_WIDTH": "1920", "VIDEO_HEIGHT": "1080"}'

# Démarrer le service
curl -X POST http://localhost:5000/api/service/start

# Scanner les réseaux WiFi
curl http://localhost:5000/api/wifi/scan

# Obtenir les infos de plateforme
curl http://localhost:5000/api/platform
```

---

## 🖥️ Plateforme cible

### Raspberry Pi OS Trixie (64-bit)

Ce projet est conçu pour fonctionner exclusivement sur **Raspberry Pi** avec **Raspberry Pi OS Trixie** (basé sur Debian 13).

| Fonctionnalité | Disponibilité |
|---------------|---------------|
| Configuration RTSP | ✅ |
| Caméra USB (V4L2) | ✅ |
| Caméra CSI (libcamera) | ✅ |
| Audio ALSA | ✅ |
| Configuration WiFi | ✅ |
| Contrôle LEDs | ✅ |
| Mémoire GPU | ✅ |
| Enregistrement | ✅ |

### Fonctionnalités Raspberry Pi

- **Contrôle des LEDs** : PWR (rouge) et ACT (verte) via `/sys/class/leds/`
- **Mémoire GPU** : Configuration via `vcgencmd` et `/boot/firmware/config.txt`
- **Caméra CSI** : Support complet via libcamera
- **Configuration boot** : Modification de `/boot/firmware/config.txt`

### Modèles supportés

- Raspberry Pi 3B+
- Raspberry Pi 4 (toutes versions)
- Raspberry Pi 5

---

## 🏗️ Architecture - partie a mettre a jour -

```
RTSP-Full/
├── install_gstreamer_rtsp.sh      # Installation GStreamer
├── install_web_manager.sh         # Installation interface web
├── rpi_av_rtsp_recorder.sh       # Script principal RTSP
├── README.md                     # Documentation
└── web-manager/
    ├── app.py                    # Backend Flask
    ├── requirements.txt          # Dépendances Python
    ├── templates/
    │   └── index.html           # Interface utilisateur
    └── static/
        ├── css/
        │   └── style.css        # Styles (thème sombre)
        └── js/
            └── app.js           # JavaScript frontend
```

### Flux de données

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Navigateur    │────▶│  Flask/Gunicorn  │────▶│  config.env     │
│   (port 5000)   │◀────│  (app.py)        │◀────│  systemd        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
          ┌─────────────────┐   ┌─────────────────┐
          │ Raspberry Pi    │   │ RTSP Recorder   │
          │ Hardware        │   │ Service         │
          └─────────────────┘   └─────────────────┘
```

---

## 🔧 Dépannage

### L'interface web ne démarre pas

```bash
# Vérifier les logs
journalctl -u rpi-cam-webmanager -n 50

# Vérifier que Python est installé
python3 --version

# Vérifier les dépendances
/opt/rpi-cam-webmanager/venv/bin/pip list

# Tester manuellement
cd /opt/rpi-cam-webmanager
./venv/bin/python app.py
```

### Problème de caméra

```bash
# Lister les périphériques vidéo
v4l2-ctl --list-devices

# Vérifier les formats supportés
v4l2-ctl -d /dev/video0 --list-formats-ext

# Tester la caméra
ffplay /dev/video0
```

### Problème d'audio

```bash
# Lister les périphériques de capture
arecord -l

# Tester l'enregistrement
arecord -d 5 -f cd test.wav && aplay test.wav

# Vérifier PulseAudio/PipeWire
pactl list sources short
```

### WiFi ne fonctionne pas

```bash
# Vérifier NetworkManager
systemctl status NetworkManager

# Scanner manuellement
nmcli dev wifi list

# Connecter manuellement
nmcli dev wifi connect "SSID" password "PASSWORD"
```

### Permissions insuffisantes

```bash
# Corriger les permissions
sudo chown -R root:www-data /etc/rpi-cam
sudo chmod 775 /etc/rpi-cam
sudo chmod 664 /etc/rpi-cam/config.env
```

---

## 📝 Changelog

### Version 2.1.0
- 🔄 Simplification pour Raspberry Pi OS Trixie uniquement
- ✅ Toutes les fonctionnalités Pi toujours disponibles (LEDs, GPU, CSI)
- ✅ Suppression de la logique multi-plateforme inutile
- ✅ Documentation mise à jour

### Version 2.0.0
- ✅ Support multi-plateforme (supprimé en 2.1.0)
- ✅ Détection automatique de la plateforme
- ✅ Amélioration de l'interface (bannière plateforme)
- ✅ Scripts d'installation universels
- ✅ Documentation mise à jour

### Version 1.0.1
- 🐛 Correction du bug de sortie silencieuse du script d'installation
- ✅ Amélioration de la gestion des logs

### Version 1.0.0
- ✅ Interface web Flask complète
- ✅ Configuration RTSP/Vidéo/Audio/Enregistrement
- ✅ Configuration WiFi avec fallback
- ✅ Contrôle des LEDs
- ✅ Configuration mémoire GPU

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🤝 Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir des issues ou des pull requests.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/rtsp-recorder/issues)
- **Documentation**: Ce fichier README

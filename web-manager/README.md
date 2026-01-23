# RTSP Recorder Web Management Interface

Interface web pour configurer et gérer le service RTSP Recorder sur Raspberry Pi.

## Fonctionnalités

- 🎛️ **Configuration complète** : Modifiez tous les paramètres RTSP, vidéo, audio et enregistrement
- 📊 **Tableau de bord** : Visualisez l'état du service, l'espace disque et les enregistrements
- 🔧 **Contrôle du service** : Démarrer/Arrêter/Redémarrer le service directement depuis l'interface
- 🔍 **Détection automatique** : Détection des caméras USB/CSI et des microphones disponibles
- 📁 **Gestion des enregistrements** : Liste et suppression des fichiers enregistrés
- 📜 **Visualisation des logs** : Consultez les logs en temps réel
- 📶 **Configuration WiFi** : Réseau principal + fallback automatique
- 💡 **Contrôle LEDs** : Activer/désactiver les LEDs Power et Activity
- 🎮 **Mémoire GPU** : Configurer l'allocation mémoire GPU

## Installation

### Prérequis

- Raspberry Pi 3B+, 4 ou 5
- Raspberry Pi OS Trixie (64-bit) - basé sur Debian 13
- GStreamer installé (voir `install_gstreamer_rtsp.sh`)
- Script RTSP recorder installé (voir `install_rpi_av_rtsp_recorder.sh`)

### Installation automatique

```bash
sudo ./install_web_manager.sh
```

L'interface sera accessible sur le port 5000 : `http://<IP_DU_PI>:5000`

### Installation manuelle

1. Installer les dépendances :
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
```

2. Créer l'environnement virtuel :
```bash
cd web-manager
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Lancer l'application :
```bash
# Mode développement
python app.py

# Mode production avec gunicorn
gunicorn --workers 2 --bind 0.0.0.0:5000 app:app
```

## Structure des fichiers

```
web-manager/
├── app.py                 # Backend Flask
├── requirements.txt       # Dépendances Python
├── config.env.example     # Exemple de configuration
├── templates/
│   └── index.html         # Template HTML principal
└── static/
    ├── css/
    │   └── style.css      # Styles CSS
    └── js/
        └── app.js         # JavaScript frontend
```

## Configuration

Le fichier de configuration est stocké dans `/etc/rpi-cam/config.env`. Il contient toutes les variables d'environnement utilisées par le script RTSP recorder.

### Paramètres disponibles

| Paramètre | Défaut | Description |
|-----------|--------|-------------|
| `RTSP_PORT` | 8554 | Port du serveur RTSP |
| `RTSP_PATH` | stream | Chemin du flux |
| `VIDEO_WIDTH` | 1280 | Largeur vidéo |
| `VIDEO_HEIGHT` | 960 | Hauteur vidéo |
| `VIDEO_FPS` | 20 | Images par seconde |
| `VIDEO_DEVICE` | /dev/video0 | Périphérique USB |
| `CSI_ENABLE` | auto | Caméra CSI (auto/yes/no) |
| `USB_ENABLE` | auto | Caméra USB (auto/yes/no) |
| `RECORD_DIR` | /var/cache/rpi-cam/recordings | Répertoire d'enregistrement |
| `SEGMENT_SECONDS` | 300 | Durée des segments (5 min) |
| `MAX_DISK_MB` | 0 | Limite d'espace disque (0=illimité) |
| `AUDIO_ENABLE` | auto | Capture audio (auto/yes/no) |
| `AUDIO_RATE` | 48000 | Fréquence audio (Hz) |
| `AUDIO_CHANNELS` | 1 | Canaux (1=mono, 2=stéréo) |
| `AUDIO_BITRATE_KBPS` | 64 | Débit audio AAC |
| `AUDIO_DEVICE` | auto | Périphérique ALSA |
| `GST_DEBUG_LEVEL` | 2 | Niveau de debug (0-6) |
| `LOG_DIR` | /var/log/rpi-cam | Répertoire des logs |
| `LOW_LATENCY` | 1 | Mode faible latence |

## API REST

L'interface expose une API REST pour l'intégration avec d'autres outils :

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/config` | GET | Récupérer la configuration |
| `/api/config` | POST | Sauvegarder la configuration |
| `/api/status` | GET | État du service |
| `/api/service/<action>` | POST | Contrôler le service (start/stop/restart) |
| `/api/logs` | GET | Récupérer les logs |
| `/api/recordings` | GET | Liste des enregistrements |
| `/api/recordings/delete` | POST | Supprimer des enregistrements |
| `/api/detect/cameras` | GET | Détecter les caméras |
| `/api/detect/audio` | GET | Détecter les périphériques audio |

## Sécurité

⚠️ **Note de sécurité** : Cette interface est conçue pour un usage en réseau local. Pour une exposition sur Internet, ajoutez :

- Authentification (nginx basic auth ou modification du code Flask)
- HTTPS (certificat SSL via Let's Encrypt)
- Pare-feu configuré

## Dépannage

### L'interface ne démarre pas
```bash
sudo systemctl status rpi-cam-webmanager
sudo journalctl -u rpi-cam-webmanager -f
```

### Le service RTSP ne répond pas aux commandes
Vérifiez que le service systemd est correctement configuré :
```bash
sudo systemctl status rpi-av-rtsp-recorder
```

### Les modifications ne sont pas prises en compte
Redémarrez le service RTSP après avoir sauvegardé :
```bash
sudo systemctl restart rpi-av-rtsp-recorder
```

## Licence

Ce projet est fourni tel quel, sans garantie.

# RTSP-Full — Encyclopédie technique

Version: 2.36.09

Objectif: fournir une documentation exhaustive et installable pour un nouvel appareil (Raspberry Pi OS Trixie / Debian 13), sans zones d’ombre.

---

## 1) Vue d’ensemble

RTSP-Full est un système complet pour:

- streamer une caméra en RTSP (GStreamer + `test-launch`)
- (optionnel) enregistrer le flux RTSP en segments (ffmpeg)
- (optionnel) fournir une interface web de gestion (Flask/Gunicorn)
- (optionnel) exposer la caméra via ONVIF (découverte + Media)
- (optionnel) haute disponibilité caméra (watchdog + udev)

### Les 3 Fondements du Projet

Le projet supporte **3 sources essentielles** :

| Source | Technologie GStreamer | Détection | Exemples |
|--------|----------------------|-----------|----------|
| Caméras USB | `v4l2src` | `v4l2-ctl --list-devices` | Microsoft LifeCam, Logitech C920 |
| Caméras CSI (PiCam) | `libcamerasrc` | `rpicam-hello --list-cameras` | OV5647 (v1), IMX219 (v2), IMX708 (v3) |
| Audio USB | `alsasrc` | `arecord -l` | Tout microphone USB compatible ALSA |

**Paquets requis pour le support complet:**
- USB : `v4l-utils`, `gstreamer1.0-v4l2`
- CSI : `rpicam-apps`, `gstreamer1.0-libcamera`
- Audio : `alsa-utils`, `gstreamer1.0-alsa`
- CSI overlay (libcamera) : `rpicam-apps-opencv-postprocess`
- Relay GPIO (ONVIF DeviceIO) : `gpiod`

Composants (source → cible sur le device):

- RTSP runtime: `rpi_av_rtsp_recorder.sh` → `/usr/local/bin/rpi_av_rtsp_recorder.sh`
- Recorder: `rtsp_recorder.sh` → `/usr/local/bin/rtsp_recorder.sh`
- Watchdog: `rtsp_watchdog.sh` → `/usr/local/bin/rtsp_watchdog.sh`
- Web UI: `web-manager/*` → `/opt/rpi-cam-webmanager/*`
- ONVIF: `onvif-server/onvif_server.py` → `/opt/rpi-cam-webmanager/onvif-server/onvif_server.py`
- (optionnel) Dérivé ESP32: `esp32/*` (projet firmware séparé, non déployé sur le Raspberry Pi)

---

## 2) Pré-requis et hypothèses

### OS / Matériel
- OS cible: Raspberry Pi OS Trixie 64-bit (Debian 13), testé Pi 3B+
- Caméra: USB (V4L2) et/ou CSI (libcamera)
- Audio: micro USB (ALSA). Sous systemd/root, privilégier ALSA.

### Ports utilisés (par défaut)
- RTSP: `8554/tcp` (service `rpi-av-rtsp-recorder`)
- Web UI: `5000/tcp` (service `rpi-cam-webmanager`)
- ONVIF: `8080/tcp` (service `rpi-cam-onvif`) + WS-Discovery (multicast UDP)

---

## 3) Installation (recommandée)

Le projet est conçu pour être réinstallé proprement sur une nouvelle machine via `setup/install.sh`.

### 3.1 Installation complète

Depuis la racine du projet:

```bash
sudo ./setup/install.sh --all
```

Options:
- `--all`: installe tous les composants (par défaut)
- `--gstreamer`: installe GStreamer + outils + `test-launch`
- `--rtsp`: installe le service RTSP (`rpi-av-rtsp-recorder`)
- `--recorder`: installe l'enregistreur (`rtsp-recorder`)
- `--webui`: installe l'interface web (`rpi-cam-webmanager`)
- `--onvif`: installe ONVIF (`rpi-cam-onvif`)
- `--watchdog`: installe le watchdog de haute disponibilité
- `--check`: vérifie l'état de l'installation (sans modifier)
- `--repair`: réinstalle/répare tous les composants

**Note:** Le watchdog est maintenant inclus dans `--all`.

### 3.2 Vérifier/Réparer l'installation

Vérifier l'état de l'installation:
```bash
sudo ./setup/install.sh --check
```

Réparer/réinstaller tous les composants:
```bash
sudo ./setup/install.sh --repair
```

### 3.3 Installation minimale (headless RTSP)

```bash
sudo ./setup/install.sh --gstreamer --rtsp
sudo systemctl enable --now rpi-av-rtsp-recorder
```

### 3.4 Installation depuis Windows (install_device.ps1 v1.4.4)

Pour une installation automatisée depuis un poste Windows vers un Pi fraîchement flashé :

```powershell
# Installation complète avec Meeting API (RECOMMANDÉ)
.\debug_tools\install_device.ps1 192.168.1.124 -DeviceKey "ABC123..." -Token "89915f"

# Sans brûler le token (pour tests répétés)
.\debug_tools\install_device.ps1 192.168.1.124 -DeviceKey "ABC123..." -Token "89915f" -NoBurnToken

# Vérifier la connectivité uniquement
.\debug_tools\install_device.ps1 -IP 192.168.1.124 -CheckOnly
```

**Fonctionnalités v1.4.4:**
- Hostname automatiquement défini sur la DeviceKey
- Token burning automatique après installation réussie
- Détection et configuration automatique de la caméra (USB ou CSI)
- Provisionnement Meeting API (meeting.json + config.env)
- Reboot automatique et vérification post-reboot
- **Nettoyage automatique des `__pycache__` et `.pyc`** après transfert

**Prérequis Windows:** WSL + sshpass (installés automatiquement si manquants)

**Durée estimée:** 15-30 minutes sur Pi 3B+

---

### 3.5 Installation depuis Windows (GUI)

Une version GUI (Windows) v1.1.0 est disponible pour lancer `install_device.ps1` avec une interface sombre et guidée (aucune modification du script CLI).

```powershell
.\debug_tools\install_device_gui.ps1
```

Caractéristiques clés:
- IP saisie par l'utilisateur (aucune auto-détection via Meeting API)
- Barre de progression + étiquette d'étape (prérequis → transfert → installation → reboot)
- Logs temps réel + sauvegarde automatique dans `debug_tools/logs/install_gui_<ip>_<timestamp>.log`
- Mode standard: IP + timezone + user/password + DeviceKey/Token optionnels
- Mode utilisateur avancé: expose CheckOnly, SkipInstall, Monitor, NoProvision, NoReboot, NoBurnToken
- Post-install: envoie un heartbeat Meeting API et vérifie que l'IP retournée correspond à l'IP saisie

Flux recommandé (utilisateur standard):
1. Saisir l'IP du device, le fuseau horaire et les identifiants SSH (device/meeting par défaut)
2. Renseigner DeviceKey/Token si Meeting API est utilisée
3. Cliquer sur "Lancer" et suivre la barre d'avancement; les logs restent visibles
4. En fin d'installation, le heartbeat est vérifié automatiquement; un message indique si l'IP retournée correspond
5. Le bouton "Stop" force l'arrêt du process si nécessaire; "Copier" permet de récupérer la commande générée

## 4) Arborescence attendue sur le device

### 4.1 Binaries
- `/usr/local/bin/rpi_av_rtsp_recorder.sh`
- `/usr/local/bin/rtsp_recorder.sh`
- `/usr/local/bin/rtsp_watchdog.sh`
- `/usr/local/bin/test-launch` (installé/compilé par `setup/install_gstreamer_rtsp.sh`)

### 4.2 Services systemd
- `/etc/systemd/system/rpi-av-rtsp-recorder.service`
- `/etc/systemd/system/rtsp-recorder.service`
- `/etc/systemd/system/rtsp-watchdog.service`
- `/etc/systemd/system/rtsp-camera-recovery.service`
- `/etc/systemd/system/rpi-cam-webmanager.service`
- `/etc/systemd/system/rpi-cam-onvif.service`

### 4.3 Configuration

Configuration principale (recommandée):
- `/etc/rpi-cam/config.env`

Configuration legacy (utilisée si `config.env` absent):
- `/etc/rpi-cam/recorder.conf`

Autres fichiers:
- `/etc/rpi-cam/onvif.conf` (JSON, contient potentiellement un mot de passe)
- `/etc/rpi-cam/wifi_failover.json` (JSON, configuration du failover WiFi - voir section détaillée ci-dessous)
- `/etc/rpi-cam/camera_profiles.json` (JSON, profils caméra sauvegardés)
- `/etc/rpi-cam/csi_tuning.json` (JSON, réglages caméra CSI via Picamera2) [NOUVEAU]
- `/etc/rpi-cam/ap_mode.json` (JSON, configuration du mode Access Point)
  - Lu par le Web UI pour afficher SSID/mot de passe/canal
  - Si vide, l'UI affiche "(non configuré dans Meeting)"
- `/etc/rpi-cam/meeting.json` (JSON, configuration Meeting API avec token)

### 4.5 Internationalisation (Web UI)

**Traductions intégrées (repo):**
- `web-manager/static/locales/fr.json`
- `web-manager/static/locales/en.json`

**Traductions personnalisées (device):**
- `/etc/rpi-cam/locales/<lang>.json`

**Priorité de sélection (serveur):**
1. Query param `?lang=fr`
2. Cookie `language`
3. Header `Accept-Language`
4. Variable d’environnement `WEB_LANGUAGE` (optionnel)
5. Clé `WEB_LANGUAGE` dans `/etc/rpi-cam/config.env`
6. Défaut: `fr`

**Notes:**
- Le sélecteur de langue côté frontend enregistre la préférence (cookie + localStorage).
- Les traductions personnalisées surchargent les traductions intégrées.
- Tous les fichiers de traduction doivent rester en UTF-8.

**Structure de `/etc/rpi-cam/wifi_failover.json` :**
```json
{
  "hardware_failover_enabled": true,       // Failover auto entre interfaces (wlan1 → wlan0)
  "network_failover_enabled": false,       // Failover auto entre réseaux (SSID1 → SSID2)
  "primary_interface": "wlan1",            // Interface principale (USB dongle 5GHz)
  "secondary_interface": "wlan0",          // Interface secondaire (WiFi intégré 2.4GHz)
  "primary_ssid": "MonReseau-5G",          // SSID du réseau principal
  "secondary_ssid": "MonReseau-2.4GHz",    // SSID du réseau de secours
  "primary_password": "",                  // Mot de passe réseau principal (optionnel si NM a un profil)
  "secondary_password": "motdepasse",      // Mot de passe réseau secondaire
  "ip_mode": "dhcp",                       // "dhcp" ou "static"
  "static_ip": "192.168.1.100/24",         // IP statique (si ip_mode=static)
  "gateway": "192.168.1.254",              // Passerelle (si ip_mode=static)
  "dns": "8.8.8.8",                        // DNS (si ip_mode=static)
  "check_interval": 30                     // Intervalle de vérification en secondes
}
```

**Structure de `/etc/rpi-cam/meeting.json` :**
```json
{
  "enabled": true,              // Active l'envoi de heartbeat Meeting
  "api_url": "https://meeting.ygsoft.fr/api",
  "device_key": "ABCDEF...",
  "token_code": "xxxxxx",
  "heartbeat_interval": 60,     // Intervalle en secondes (60s recommandé)
  "auto_connect": true,         // Envoi automatique au démarrage
  "provisioned": true           // Indique si le device est provisionné
}
```

**Priorité du failover réseau :**
1. `eth0` (Ethernet) - Priorité maximale si connecté
2. `wlan1` (USB Dongle) - Utilisé si eth0 absent/déconnecté
3. `wlan0` (WiFi intégré) - Fallback si wlan1 indisponible

**IP Commune (Partagée) :** Quand `ip_mode=static`, la même configuration IP est appliquée à l'interface WiFi active. Lors du failover, si l'interface déjà connectée a une IP différente (ex: DHCP d'un profil NM sauvegardé), le failover corrige automatiquement en appliquant l'IP statique configurée via `_ensure_static_ip_on_interface()` (v2.30.17).

**Transition Make-Before-Break (v2.30.18) :** Le failover utilise une approche "make-before-break" pour les transitions wlan0→wlan1 : quand wlan1 redevient disponible, wlan0 reste actif pendant la tentative de connexion de wlan1. wlan0 n'est déconnecté qu'APRÈS confirmation que wlan1 est connecté avec une IP valide. Si wlan1 échoue, wlan0 reste intact (zéro perte de connectivité).

**Note:** Le mot de passe `primary_password` peut rester vide si NetworkManager a déjà un profil sauvegardé pour ce SSID (ex: configuré via RPi Imager). L'interface web affichera "(enregistré)" au lieu de "Aucun mot de passe" si un profil NM existe.

**Permissions requises:**
Le dossier `/etc/rpi-cam/` doit être accessible en écriture par le groupe `www-data` :
```bash
sudo chmod 775 /etc/rpi-cam/
sudo chown root:www-data /etc/rpi-cam/
```

### 4.4 Données et logs
- Enregistrements: `/var/cache/rpi-cam/recordings`
- Cache métadonnées SQLite: `/var/cache/rpi-cam/media_cache.db`
- Cache thumbnails: `/var/cache/rpi-cam/thumbnails/`
- Logs: `/var/log/rpi-cam/*.log`
- Logs dnsmasq AP: `/var/log/rpi-cam/dnsmasq.log`
- État scheduler (partagé entre workers Gunicorn): `/tmp/rpi-cam-scheduler-state.json`

---

## 5) Fonctionnement RTSP (GStreamer + test-launch)

### 5.1 Service
- Nom systemd: `rpi-av-rtsp-recorder`
- Exécutable: `/usr/local/bin/rpi_av_rtsp_recorder.sh`

### 5.2 Détection caméra

Le script choisit automatiquement:
- USB/V4L2 si un `/dev/videoX` fonctionnel est présent (prioritaire)
- sinon CSI/libcamera si disponible

### 5.3 Encodage H.264

Ordre de préférence:
1) caméra USB qui sort déjà du H.264 → pas d’encodage (idéal)
2) `v4l2h264enc` (hardware) si présent et fonctionnel
3) `x264enc` (software) en fallback (Pi 3B+: rester à `640x480@15fps`)

Note importante (Pi 3B+ / Trixie): `v4l2h264enc` peut être présent mais cassé; le script teste et bascule automatiquement.
Note: `H264_BITRATE_KBPS` s'applique aux encodeurs hardware (`v4l2h264enc`) et software.

### 5.4 Audio (optionnel)
- Détection automatique d’un micro USB via `arecord -l`
- Source GStreamer: `alsasrc` (préféré sous systemd/root), fallback `pulsesrc`
- Encodage AAC: `avenc_aac` ou `faac` si disponible
- **Amplification audio** (v2.11.0+): paramètre `AUDIO_GAIN` pour ajuster le volume
  - `0.0` = muet
  - `1.0` = volume normal (défaut)
  - `2.0` = amplification x2
  - `3.0` = amplification x3 (attention à la saturation)

### 5.5 URL RTSP

Par défaut (sans authentification):
- `rtsp://<IP_DU_DEVICE>:8554/stream`

Avec authentification (si `RTSP_USER` et `RTSP_PASSWORD` sont configurés):
- `rtsp://USER:PASSWORD@<IP_DU_DEVICE>:8554/stream`

### 5.6 Authentification RTSP/ONVIF (partagée) (v2.6.0+)

L'authentification RTSP est supportée via les variables d'environnement et **partagée** avec ONVIF (WS-Security):
- `RTSP_USER`: nom d'utilisateur (optionnel)
- `RTSP_PASSWORD`: mot de passe (optionnel)

**Comportement:**
- Si les deux variables sont définies et non-vides: authentification requise
- Si l'une des deux est vide ou absente: accès sans authentification

**Configuration dans `/etc/rpi-cam/config.env` (unique point de configuration):**
```bash
# Authentification RTSP (optionnel)
RTSP_USER="admin"
RTSP_PASSWORD="monMotDePasse"

# Méthode d'authentification: basic, digest, ou both (défaut: both)
RTSP_AUTH_METHOD="both"
```

**Méthodes d'authentification (v2.1.0+):**
- `basic`: HTTP Basic Authentication uniquement
- `digest`: HTTP Digest Authentication uniquement (plus sécurisé)
- `both`: Les deux méthodes acceptées (défaut, recommandé pour compatibilité)

**Compatibilité NVR/VMS:**
- **Synology Surveillance Station**: Utilise Digest auth → `RTSP_AUTH_METHOD=both` ou `digest`
- **Blue Iris**: Supporte Basic et Digest → `RTSP_AUTH_METHOD=both`
- **ffmpeg/VLC**: Supportent les deux → `RTSP_AUTH_METHOD=both`

**Synchronisation ONVIF:** si `RTSP_USER` et `RTSP_PASSWORD` sont définis, ils sont automatiquement utilisés par le serveur ONVIF (v1.5.3+) pour la génération de l'URL RTSP et WS-Security.

**Important:** Après un changement de mot de passe RTSP:
1. Redémarrer le service RTSP: `sudo systemctl restart rpi-av-rtsp-recorder`
2. Sur le NVR (Synology, etc.): **supprimer et recréer** la caméra (le cache des credentials peut persister)

**Note:** Le binaire `test-launch` doit être recompilé avec le support authentification (v2.1.0+):
```bash
sudo ./setup/install_gstreamer_rtsp.sh
```

### 5.7 Modes source (caméra / proxy RTSP / MJPEG / écran) (v2.13.0+)

Le serveur RTSP peut diffuser autre chose qu'une caméra locale grâce au mode source.

**Variables clés (config.env):**
- `STREAM_SOURCE_MODE` : `camera` (défaut) | `rtsp` | `mjpeg` | `screen`
- `STREAM_SOURCE_URL` : URL de la source (obligatoire pour `rtsp` / `mjpeg`)
- `RTSP_PROXY_TRANSPORT` : `auto` | `tcp` | `udp` (transport côté source RTSP)
- `RTSP_PROXY_AUDIO` : `auto` | `yes` | `no` (relai audio source RTSP)
- `RTSP_PROXY_LATENCY_MS` : buffer rtspsrc (ms)
- `SCREEN_DISPLAY` : display X11 (ex: `:0.0`) pour `screen`

**Comportements:**
- `camera` : pipeline local (USB/CSI) inchangé.
- `rtsp` : proxy RTSP (H264 + AAC pass-through si disponibles).
- `mjpeg` : récupère un MJPEG HTTP et ré-encode en H264.
- `screen` : capture d'écran X11 et ré-encode en H264.

**Limites:**
- `rtsp` : nécessite un flux H264 (et AAC pour audio), pas de transcodage.
- `screen` : nécessite un environnement X11 actif.

### 5.8 Transports RTSP (UDP/TCP/Multicast) (v2.13.0+)

Le serveur RTSP GStreamer peut forcer les transports côté client :
- `RTSP_PROTOCOLS=udp,tcp` (défaut)
- `RTSP_PROTOCOLS=tcp` (TCP uniquement)
- `RTSP_PROTOCOLS=udp` (UDP uniquement)
- `RTSP_PROTOCOLS=udp-mcast` (multicast)

**Option multicast avancée:**
- `RTSP_MULTICAST_BASE` (ex: `239.255.12.1`)
- `RTSP_MULTICAST_PORT_MIN` / `RTSP_MULTICAST_PORT_MAX`

Ces variables sont lues par `test-launch` (v2.2.0+) si recompilé via `install_gstreamer_rtsp.sh`.

### 5.9 Serveur RTSP CSI natif (Python) - v1.4.14

Pour les caméras CSI (PiCam), un serveur RTSP dédié en Python utilise **Picamera2** au lieu de `test-launch`.

**Fichiers:**
- Source: `rpi_csi_rtsp_server.py` → `/usr/local/bin/rpi_csi_rtsp_server.py`
- Version: 1.4.14

**Architecture:**
```
Picamera2 (H264Encoder hardware) 
    ↓ H.264 Annex B frames
  appsrc → h264parse → rtph264pay → GStreamer RTSP Server
                                          ↓
                                   RTSP @ port 8554
```

**Avantages vs test-launch + libcamerasrc:**
- **Encodage hardware** via `Picamera2.H264Encoder` (V4L2 M2M)
- **Contrôles dynamiques** via API IPC sur `127.0.0.1:8085`
- **Pas de conflit buffer** entre libcamera et GStreamer

**API IPC (interne, port 8085):**
| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/controls` | GET | Liste tous les contrôles avec valeurs actuelles |
| `/set_controls` | POST | Applique des contrôles (JSON) |

**Contrôles array supportés (v1.2.0+):**

Certains contrôles attendent un tableau de valeurs :

| Contrôle | Type | Format | Description |
|----------|------|--------|-------------|
| `ColourGains` | `[float, float]` | `[red_gain, blue_gain]` | Gains couleur manuel |
| `FrameDurationLimits` | `[int, int]` | `[min_µs, max_µs]` | Limites durée frame |
| `ScalerCrop` | `[int, int, int, int]` | `[x, y, width, height]` | Région de recadrage |

**Validation automatique:**
- Si une valeur scalaire est envoyée pour un contrôle array, elle est automatiquement dupliquée
- Exemple: `ColourGains: 2.0` devient `ColourGains: [2.0, 2.0]`

**Démarrage:**
Le script `rpi_av_rtsp_recorder.sh` détecte automatiquement le type de caméra et lance soit `test-launch` (USB) soit `rpi_csi_rtsp_server.py` (CSI).

**Encodage H.264 (CSI):**
- `H264_PROFILE` permet de forcer le profil H.264 (ex: `baseline` pour compatibilité)
- `H264_QP` fixe la quantification (1-51) pour ajuster qualité/latence

**A/V Sync (CSI) - Fix (v1.4.10 / v2.32.51+):**
- Si l'audio est en retard de ~2-3s sur certains clients, la cause peut être des offsets RTP aléatoires.
- Correction: `timestamp-offset=0` / `seqnum-offset=0` forcés sur les payloaders audio/vidéo.

**Délai d'affichage RTSP (NVR / Synology) - Amélioration (v1.4.11 / v2.32.52+):**
- Certains clients attendent un keyframe (IDR) pour afficher l'image après (re)connexion.
- Le serveur CSI demande un keyframe à la reconnexion d'un consommateur (best-effort) pour réduire l'attente.

---

## 6) Enregistrement (ffmpeg)

### 6.1 Service
- Nom systemd: `rtsp-recorder`
- Script: `/usr/local/bin/rtsp_recorder.sh`

### 6.2 Principe

L’enregistrement se fait en dehors du pipeline RTSP (contrainte `test-launch`):
- source: `rtsp://127.0.0.1:${RTSP_PORT}/${RTSP_PATH}`
- `ffmpeg -c copy` (pas de ré-encodage)
- segments `.ts` horodatés (robustes en cas de coupure)

**Codecs utilisés (v1.6.0+):**
- Vidéo: `-c:v copy` (pas de ré-encodage, copie directe)
- Audio: `-c:a aac -b:a 64k` (ré-encodage AAC 64kbps)

**Note importante sur l'audio:** L'audio est ré-encodé au lieu d'être copié directement car ffmpeg ne capture pas correctement les métadonnées AAC du flux RTSP en mode copy. Le ré-encodage garantit un audio fonctionnel dans les fichiers .ts avec un surcoût CPU minimal.

### 6.3 Gestion intelligente de l'espace disque (v1.3.0)

`rtsp_recorder.sh` maintient un espace libre minimum via un système de pruning intelligent en 2 étapes.

**Configuration:**
| Variable | Défaut | Description |
|----------|--------|-------------|
| `MIN_FREE_DISK_MB` | 1000 | Espace minimum à maintenir (0=désactivé) |
| `MAX_DISK_MB` | 0 | Taille max du dossier d'enregistrements en Mo (0=illimité) [v1.7.0+] |
| `PRUNE_CHECK_INTERVAL` | 60 | Intervalle de vérification en secondes |
| `LOG_MAX_SIZE_MB` | 10 | Taille max des logs avant troncature |

**Limite MAX_DISK_MB (v1.7.0+):**
En plus de la limite d'espace libre, une nouvelle limite `MAX_DISK_MB` permet de fixer une taille maximale pour le dossier d'enregistrements.
- Si `MAX_DISK_MB=5000`, le dossier ne dépassera jamais 5 Go
- Les fichiers les plus anciens sont supprimés automatiquement quand la limite est atteinte
- L'interface web affiche un indicateur visuel :
  - Bleu : normal
  - Orange : warning (90% de la limite)
  - Rouge clignotant : limite dépassée

**Étape 1 - Nettoyage logs/cache (non-destructif):**
| Cible | Seuil | Action |
|-------|-------|--------|
| `/var/log/rpi-cam/*.log` | >10MB | Troncature (garde 1000 lignes) |
| Journald | >50MB | `journalctl --vacuum-size=50M` |
| `/var/cache/apt/archives/` | >100MB | Suppression des `.deb` |
| Logs rotatés | tout | Suppression `*.gz`, `*.1`, `*.old` |
| `/tmp/` | >1 jour | Suppression fichiers anciens |

**Étape 2 - Suppression enregistrements (si espace toujours insuffisant):**
- Supprime les fichiers `.ts` les plus anciens dans `$RECORD_PATH`
- Boucle jusqu'à atteindre `MIN_FREE_DISK_MB`

**Surveillance continue:**
Une boucle de fond vérifie l'espace disque toutes les 60 secondes pendant l'enregistrement ffmpeg.

**Exemple de logs:**
```
[INFO] Checking disk space... Current: 227MB free, Required: 1000MB
[INFO] Cleaning APT cache: 132MB
[INFO] Freed approximately 132MB from logs/cache
[INFO] Started background pruning loop (PID: 33051, interval: 60s)
```

---

## 7) Haute disponibilité caméra (watchdog + udev)

Deux mécanismes existent:

1) Watchdog systemd (bash): `rtsp-watchdog.service` + `rtsp_watchdog.sh`
- vérifie caméra, service, stream (via port/processus)
- redémarre `rpi-av-rtsp-recorder` (et `rtsp-recorder` si activé)

2) Watchdog interne (Web UI): thread python démarré au lancement du Web Manager.
- Service: `watchdog_service.py` (v2.30.4)
- Vérifie toutes les 30 secondes : caméra, service systemd, port RTSP ouvert, processus `test-launch`
- Redémarre automatiquement après 3 échecs consécutifs (~90 secondes)

### 7.1 Health Check du Watchdog interne (v2.30.4+)

**Méthode de vérification :**
- **Port RTSP** : `ss -tuln | grep :8554` - vérifie que le serveur écoute
- **Processus** : `pgrep -f test-launch` - vérifie que GStreamer tourne
- **Caméra** : Vérifie la présence de `/dev/video0`

**Note importante sur ffprobe:** Les versions antérieures (< v2.30.4) utilisaient `ffprobe` pour tester le flux RTSP. Cependant, `ffprobe` **ne supporte pas l'authentification Digest**, ce qui causait des faux positifs (stream considéré comme non accessible) et des redémarrages intempestifs toutes les ~90 secondes. La vérification par port et processus est plus fiable.

Recommandation:
- avec Web UI en prod: le watchdog interne est actif; le watchdog systemd est optionnel (éviter le double auto-restart si vous n’en avez pas besoin)
- sans Web UI: installer le watchdog systemd via `setup/install_rtsp_watchdog.sh`

Udev (réaction immédiate sur replug USB):
- règle: `/etc/udev/rules.d/99-rtsp-camera.rules`
- service oneshot: `rtsp-camera-recovery.service` (restart RTSP + recorder)

---

## 8) ONVIF (découverte + Media)

### 8.1 Service
- Nom: `rpi-cam-onvif`
- Script: `/opt/rpi-cam-webmanager/onvif-server/onvif_server.py`
- Version: 1.6.0

### 8.2 Configuration

Fichier: `/etc/rpi-cam/onvif.conf` (JSON)

Champs principaux:
- `enabled` (bool)
- `port` (int, défaut 8080)
- `username` / `password` (WS-Security) — gérés automatiquement via `RTSP_USER` / `RTSP_PASSWORD`
- `rtsp_port` / `rtsp_path` (doit correspondre au RTSP réel)

**Synchronisation des identifiants (v2.6.0+)**
- Si `RTSP_USER` et `RTSP_PASSWORD` sont définis dans `/etc/rpi-cam/config.env`, ils sont automatiquement recopiés dans `/etc/rpi-cam/onvif.conf` (WS-Security).
- Objectif: avoir les mêmes identifiants pour le flux RTSP et pour ONVIF.
- Si les identifiants RTSP sont vides, aucune synchronisation n'est faite (ONVIF reste inchangé).
- Dans l'interface web, les identifiants ONVIF sont éditables si RTSP auth est vide; sinon ils sont forcés par RTSP.

**Note:** Le champ `name` dans `onvif.conf` est ignoré depuis la v1.5.0. Le nom est récupéré depuis l'API Meeting (voir section 8.4).

Le serveur lit aussi les paramètres vidéo depuis `/etc/rpi-cam/config.env` pour annoncer des settings cohérents.

#### 8.2.1 Séparation INPUT/OUTPUT (v2.36.00+)

**Architecture VIDEOIN_* / VIDEOOUT_* :**

| Variables | Rôle | Contrôlable par | Alias legacy |
|-----------|------|-----------------|--------------|
| `VIDEOIN_WIDTH/HEIGHT/FPS` | Capture caméra (input) | Frontend uniquement | VIDEO_* |
| `VIDEOIN_DEVICE/FORMAT` | Device et format caméra | Frontend uniquement | VIDEO_* |
| `VIDEOOUT_WIDTH/HEIGHT/FPS` | Stream RTSP (output) | ONVIF + Frontend | OUTPUT_* |

**Compatibilité :**
- Les variables `VIDEO_*` et `OUTPUT_*` restent supportées via fallback automatique
- `config_service.py` expose les deux noms pour la rétro-compatibilité des templates

**Comportement :**
- Si `VIDEOOUT_*` non défini → utilise `VIDEOIN_*` (rétro-compatible)
- Si `VIDEOOUT_*` défini et différent de `VIDEOIN_*` → scaling/conversion automatique via `videoscale`/`videorate`

**Exemple concret :**
```bash
# Caméra capture en 1280x720@30fps (seul format supporté par la caméra USB)
VIDEOIN_WIDTH=1280
VIDEOIN_HEIGHT=720
VIDEOIN_FPS=30
VIDEOIN_DEVICE=/dev/video0
VIDEOIN_FORMAT=MJPG

# ONVIF/Synology configure la sortie à 20fps (le scaler s'active automatiquement)
VIDEOOUT_FPS=20
```

**Logs de démarrage :**
```
Input (camera):  1280x720@30fps
Output (stream): 1280x720@20fps
Output framerate differs from input - will convert
Output scaler: videoconvert ! videorate ! video/x-raw,framerate=20/1
```

**Pourquoi cette séparation ?**
- Les caméras USB supportent souvent UN SEUL framerate à une résolution donnée (ex: 30fps only à 720p)
- Sans cette séparation, ONVIF pouvait définir un FPS invalide → crash GStreamer (`not-negotiated`)
- Maintenant, la caméra capture en mode natif, et le stream est converti si nécessaire

#### 8.2.2 Contrôle caméra via ONVIF (SetVideoEncoderConfiguration)

Depuis v1.8.0, `SetVideoEncoderConfiguration` écrit sur `VIDEOOUT_*` (pas `VIDEOIN_*`) :
- `VIDEOOUT_WIDTH/HEIGHT/FPS` contrôle la sortie RTSP
- `H264_BITRATE_KBPS` et `H264_KEYINT` sont mis à jour
- Le service RTSP est redémarré pour appliquer les changements

**Note:** `SetVideoSourceConfiguration` est maintenant un NO-OP (protège la caméra).

#### 8.2.3 Imaging (Brightness / Focus)

Le service Imaging est exposé (Profile T minimal) :
- `GetImagingSettings`, `SetImagingSettings`, `GetImagingOptions`
- Brightness via V4L2 (USB) ou IPC Picamera2 (CSI)
- Focus auto/manual si disponible (USB V4L2)

#### 8.2.3 Relay Outputs (DeviceIO)

Le service DeviceIO expose un relais ONVIF (digital output) si configuré.

Configuration dans `/etc/rpi-cam/config.env` :
```
RELAY_ENABLE=yes
RELAY_GPIO_PIN=17
RELAY_GPIO_CHIP=gpiochip0
RELAY_ACTIVE_HIGH=true
RELAY_OUTPUT_NAME=RelayOutput
RELAY_OUTPUT_TOKEN=RelayOutput1
```

Si `RELAY_ENABLE=no`, aucun relais n'est annoncé.

### 8.3 Nom du device (intégration Meeting API)

**Depuis la version 1.5.0**, le serveur ONVIF récupère automatiquement le nom du device depuis l'API Meeting.

**Comportement:**
- Si le device est **provisionné** dans Meeting → utilise le nom Meeting (ex: `V1-S01-00030`)
- Si le device n'est **pas provisionné** ou API non configurée → utilise `UNPROVISIONNED`

**Configuration requise dans `/etc/rpi-cam/config.env`:**
```bash
MEETING_API_URL="https://meeting.example.com/api"
MEETING_DEVICE_KEY="votre-device-key"
MEETING_TOKEN_CODE="votre-token"  # optionnel selon l'API
```

**Logs au démarrage:**
```
[ONVIF] Device name from Meeting API: V1-S01-00030
# ou si non provisionné:
[ONVIF] Meeting API not configured, using default name: UNPROVISIONNED
```

**Note:** Le nom ONVIF est utilisé dans les scopes WS-Discovery (name/serial) et dans `GetHostname`. Il est automatiquement encodé en URL pour assurer une détection correcte dans les NVR (ex: Surveillance Station).

### 8.4 Priorité des interfaces réseau

Le serveur ONVIF détermine automatiquement l'IP à annoncer via RTSP/ONVIF selon la priorité des interfaces :

**Ordre de priorité par défaut:**
1. `eth0` (Ethernet filaire) — priorité maximale
2. `wlan1` (WiFi USB 5GHz)
3. `wlan0` (WiFi intégré)
4. `enp0s3`, `end0` (autres interfaces Ethernet)

**Comportement:**
- Si Ethernet (`eth0`) est connecté avec une IP valide → utilise l'IP Ethernet
- Si Ethernet déconnecté → bascule automatiquement vers WiFi
- WS-Discovery (auto-détection) répond avec l'IP du même sous-réseau que le client

**Configuration personnalisée:**
Ajouter dans `/etc/rpi-cam/config.env`:
```bash
NETWORK_INTERFACE_PRIORITY="eth0,wlan1,wlan0"
```

**Note:** Le serveur RTSP (GStreamer `test-launch`) écoute sur `0.0.0.0` donc est accessible via toutes les interfaces. Seule l'URL annoncée via ONVIF change.

### 8.5 IP préférée dans l'interface web

L'interface web (app.py v2.10.0+) utilise également la logique de priorité des interfaces pour afficher :
- L'**URL RTSP** dans l'en-tête de la page
- L'**URL ONVIF** dans l'onglet RTSP

L'API `/api/onvif/status` retourne un champ `preferred_ip` qui contient l'IP de l'interface prioritaire active.

### 8.6 Mode Point d'Accès (Access Point)

Le système peut transformer wlan0 en point d'accès WiFi, permettant aux appareils de se connecter directement au Raspberry Pi sans routeur intermédiaire.

**Dépendances:**
- `hostapd` - Serveur de point d'accès WiFi
- `dnsmasq` - Serveur DHCP (distribue les IPs aux clients)

Ces dépendances sont installées automatiquement par `setup/install.sh`.

**Configuration:**
- Fichier de config: `/etc/rpi-cam/ap_mode.json`
- hostapd config: `/etc/hostapd/hostapd.conf` (généré automatiquement)
- dnsmasq config: `/etc/dnsmasq.d/rpi-cam-ap.conf` (généré automatiquement)
- Logs dnsmasq: `/var/log/rpi-cam/dnsmasq.log`

**Paramètres par défaut:**
```json
{
  "enabled": false,
  "interface": "wlan0",
  "ssid": "",
  "password": "",
  "channel": 11,
  "ap_ip": "192.168.4.1",
  "dhcp_range_start": "192.168.4.10",
  "dhcp_range_end": "192.168.4.100",
  "dhcp_lease_time": "24h"
}
```

**IMPORTANT:** Le canal WiFi est fixé à **11** (2462 MHz) selon les spécifications du projet.

**Intégration Meeting:**
- Les paramètres AP (SSID, mot de passe) sont récupérés depuis l'API Meeting
- L'API Meeting retourne `ap_ssid` et `ap_password` dans les données du device
- Endpoint: `POST /api/network/ap/config` avec `{ "from_meeting": true }`

**Configuration dnsmasq générée:**
```
interface=wlan0
bind-interfaces
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
server=8.8.4.4
log-facility=/var/log/rpi-cam/dnsmasq.log
log-dhcp
```

**Impact sur le failover:**
- En mode AP, wlan0 est occupé → le failover **hardware** WiFi est désactivé
- wlan1 (dongle USB) reste disponible pour le failover **réseau** vers un autre WiFi

### 8.7 Gestion automatique WiFi/Ethernet

Le système gère automatiquement la priorité entre Ethernet et WiFi:

**Comportement par défaut:**
- Si Ethernet (eth0) est connecté → WiFi (wlan0) est désactivé automatiquement
- Économise de l'énergie et évite les conflits de routage
- Appliqué au démarrage du Web Manager via `manage_wifi_based_on_ethernet()`

**Forçage manuel:**
- Option "Forcer WiFi actif" dans l'interface web (onglet Réseau)
- **Bouton "Appliquer"** pour confirmer le changement (pas d'application automatique)
- Configuration: `WIFI_MANUAL_OVERRIDE=yes` dans config.env
- Quand activé, WiFi reste actif même si Ethernet est connecté

**Configuration WiFi simple (1 seul adaptateur):**
- Si un seul adaptateur WiFi détecté, affiche section "Configuration WiFi Simple"
- Pré-remplit le SSID depuis :
  1. Configuration locale (`wifi_ssid` dans config.env)
  2. Profil NetworkManager (configuré via RPi Imager)
- Permet connexion à un réseau WiFi sans configuration complexe

**Exception mode AP:**
- En mode AP, la gestion automatique WiFi/Ethernet est suspendue pour wlan0

---

## 9) Web Manager (Flask/Gunicorn)

### 9.1 Service et emplacement
- Nom systemd: `rpi-cam-webmanager`
- Install: `/opt/rpi-cam-webmanager`
- Port: `5000`
- Lance Gunicorn sur `0.0.0.0:5000`

### 9.1.1 Architecture Modulaire (v2.30.0+)

**Structure de fichiers sur le device:**
```
/opt/rpi-cam-webmanager/
├── app.py                  # Orchestrateur Flask (~450 lignes)
├── config.py               # Configuration centralisée (~130 lignes)
├── services/               # Logique métier (11 modules)
│   ├── __init__.py
│   ├── platform_service.py    # Détection plateforme Pi
│   ├── config_service.py      # Gestion config, services systemd
│   ├── camera_service.py      # Contrôles caméra USB v4l2, profils
│   ├── csi_camera_service.py  # Contrôles caméra CSI via Picamera2 (v1.0.0) [NOUVEAU]
│   ├── network_service.py     # Interfaces réseau, WiFi, failover
│   ├── power_service.py       # LED, GPU, HDMI, énergie
│   ├── recording_service.py   # Enregistrements, espace disque (v2.30.2)
│   ├── media_cache_service.py # Cache SQLite métadonnées + thumbnails (v1.0.0)
│   ├── meeting_service.py     # Meeting API, heartbeat
│   ├── system_service.py      # Diagnostics, logs, mises à jour
│   └── watchdog_service.py    # RTSP health, WiFi failover
├── blueprints/             # Routes HTTP (15 modules)
│   ├── __init__.py
│   ├── config_bp.py           # /api/config, /api/service, /api/status
│   ├── camera_bp.py           # /api/camera/*
│   ├── recordings_bp.py       # /api/recordings/*, /api/recordings/cache/* (v2.30.4)
│   ├── network_bp.py          # /api/network/*
│   ├── system_bp.py           # /api/system/*
│   ├── meeting_bp.py          # /api/meeting/*
│   ├── logs_bp.py             # /api/logs/*
│   ├── video_bp.py            # /api/video/*
│   ├── power_bp.py            # /api/leds/*, /api/power/*
│   ├── onvif_bp.py            # /api/onvif/*
│   ├── detect_bp.py           # /api/detect/*, /api/platform
│   ├── watchdog_bp.py         # /api/rtsp/watchdog/*
│   ├── wifi_bp.py             # /api/wifi/*
│   ├── debug_bp.py            # /api/debug/*, /api/system/ntp
│   └── legacy_bp.py           # Routes rétrocompatibilité
├── templates/index.html    # Frontend HTML
└── static/
    ├── css/style.css
    └── js/app.js
```

**Avantages de l'architecture modulaire:**
- Code 10x plus maintenable (fichiers <750 lignes)
- Séparation claire logique métier / routes HTTP
- Services réutilisables entre blueprints
- Tests unitaires simplifiés
- Ajout de fonctionnalités facilité

**Déploiement individuel (maintenance):**
```powershell
# Déployer un seul service modifié
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\services\power_service.py" -Dest "/opt/rpi-cam-webmanager/services/"

# Déployer un blueprint
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\blueprints\power_bp.py" -Dest "/opt/rpi-cam-webmanager/blueprints/"

# Redémarrer après modifications
.\debug_tools\run_remote.ps1 "sudo systemctl restart rpi-cam-webmanager"
```

### 9.2 Fichiers gérés
- charge/sauvegarde la config RTSP dans `/etc/rpi-cam/config.env`
- gère des JSON système (`wifi_failover.json`, `camera_profiles.json`, `csi_tuning.json`, `onvif.conf`, `ap_mode.json`, `locked_recordings.json`)

### 9.2.0 Contrôles caméra CSI (Picamera2) - NOUVEAU v2.30.57

Les caméras CSI (PiCam v1/v2/v3) sont contrôlées via **Picamera2** au lieu de v4l2-ctl.

#### Configuration sauvegardée
- Fichier: `/etc/rpi-cam/csi_tuning.json`
- Exemple:
```json
{
  "Brightness": 0.1,
  "Contrast": 1.2,
  "Saturation": 1.0
}
```

#### Contrôles disponibles (OV5647)
| Contrôle | Plage | Description |
|----------|-------|-------------|
| Brightness | -1.0 → 1.0 | Luminosité |
| Contrast | 0 → 32 | Contraste |
| Saturation | 0 → 32 | Intensité des couleurs |
| Sharpness | 0 → 16 | Netteté |
| ExposureTime | 130 → 3066985 µs | Temps d'exposition |
| ExposureValue | -8 → +8 EV | Correction d'exposition |
| AnalogueGain | 1.0 → 63.9 | Gain du capteur |
| AeEnable | true/false | Auto-exposition activée |
| AwbEnable | true/false | Balance des blancs auto |
| NoiseReductionMode | 0-4 | Réduction de bruit |

#### Application au pipeline RTSP
Le script `rpi_av_rtsp_recorder.sh` lit automatiquement `/etc/rpi-cam/csi_tuning.json` et applique les valeurs à libcamerasrc :
```bash
# Exemple de pipeline généré :
libcamerasrc brightness=0.1 contrast=1.2 ! video/x-raw,width=1296,height=972,framerate=30/1 ...
```

#### Limitations
- La caméra ne peut être configurée que si le flux RTSP est arrêté (exclusivité)
- L'interface web affiche un message "Caméra occupée" quand le flux RTSP est actif
- Le bouton "Arrêter le flux temporairement" permet de configurer les paramètres

### 9.2.1 Onglets de l'interface web

| Onglet | ID URL | Description |
|--------|--------|-------------|
| **Accueil** | `home` | Dashboard avec état des services (RTSP, ONVIF, Recording, Meeting), URLs de streaming, infos device |
| **Vidéo** | `video` | Résolution, FPS, device caméra, profils caméra |
| **Réseau** | `network` | Priorité interfaces, IP statique/DHCP |
| **WiFi** | `wifi` | Configuration WiFi, failover, mode AP |
| **Énergie** | `power` | LEDs, GPU, HDMI, composants, services |
| **ONVIF** | `onvif` | Configuration du serveur ONVIF (port, nom, identifiants) |
| **Meeting** | `meeting` | Intégration Meeting API, provisioning, tunnel SSH |
| **Logs** | `logs` | Consultation et nettoyage des logs |
| **Enregistrements** | `recordings` | **Gestion des fichiers enregistrés** (voir section 9.4) |
| **Système** | `system` | NTP, mises à jour, debug, redémarrage |

### 9.2.1bis Navigation par URL (v2.30.48+)

L'interface web supporte la navigation directe vers un onglet via l'URL. Cette fonctionnalité permet notamment à Meeting d'accéder directement à un onglet spécifique.

#### Format recommandé : Hash (`#`)

```
http://192.168.1.202:5000/#home        → Onglet Accueil
http://192.168.1.202:5000/#video       → Onglet Vidéo
http://192.168.1.202:5000/#network     → Onglet Réseau
http://192.168.1.202:5000/#wifi        → Onglet WiFi
http://192.168.1.202:5000/#power       → Onglet Énergie
http://192.168.1.202:5000/#onvif       → Onglet ONVIF
http://192.168.1.202:5000/#meeting     → Onglet Meeting
http://192.168.1.202:5000/#logs        → Onglet Logs
http://192.168.1.202:5000/#recordings  → Onglet Enregistrements
http://192.168.1.202:5000/#system      → Onglet Système
```

#### Formats alternatifs (compatibilité)

Deux autres formats sont supportés mais le hash (`#`) reste recommandé :

| Format | Exemple | Note |
|--------|---------|------|
| Hash (recommandé) | `#onvif` | Standard web, ne recharge pas la page |
| Query param nommé | `?tab=onvif` | Alternative explicite |
| Query param seul | `?onvif` | Raccourci |

#### Alias supportés

Pour simplifier l'usage, des alias sont disponibles :

| Alias | Onglet réel |
|-------|-------------|
| `camera` | `video` |
| `rec` | `recordings` |
| `energy` | `power` |
| `led` / `leds` | `power` |
| `update` | `system` |
| `diag` | `system` |

#### Comportement

- L'URL se met à jour automatiquement quand on clique sur un onglet
- Les boutons Précédent/Suivant du navigateur fonctionnent
- Si un onglet invalide est passé, l'onglet `home` est affiché par défaut
- Compatible avec les liens depuis Meeting ou tout autre système externe

### 9.2.2 Overlays visuels (v2.30.28+)

L'interface web utilise des overlays plein écran pour les opérations longues :

#### Overlay de redémarrage (`#reboot-overlay`)
- **Déclencheur:** Bouton "Redémarrer le Raspberry Pi" ou confirmation après sauvegarde paramètres
- **Affichage:**
  - Spinner bleu animé avec icône de redémarrage
  - Compte à rebours de 90 secondes
  - Barre de progression
  - Phases affichées : "Arrêt du système", "Redémarrage du noyau", "Démarrage des services"
- **Comportement:**
  - Détection automatique du retour en ligne (ping `/api/system/info` toutes les secondes après 30s)
  - Animation verte de succès quand le Pi est accessible
  - Rechargement automatique de la page

#### Overlay des paramètres d'énergie (`#power-settings-overlay`)
- **Déclencheur:** Bouton "Appliquer les changements" dans l'onglet Système
- **Affichage:**
  - Spinner orange avec icône d'engrenage animée
  - Message "Application des paramètres"
  - Indication "Cette opération peut prendre quelques secondes"
- **Raison:** L'API `/api/power/apply-all` exécute plusieurs commandes `systemctl` synchrones (~5-15 secondes)

### 9.2.2bis Backup / Restore (v2.32.41+)

Cette section est disponible dans l'onglet **Système** et permet de sauvegarder/restaurer la configuration locale.

#### Boutons disponibles
- **Backup configuration** : demande si les logs doivent etre inclus, puis telecharge une archive `.tar.gz`
- **Check backup** : valide une archive fournie et propose de restaurer
- **Restore configuration** : restaure la configuration puis redemarre le systeme

#### Structure de l'archive
```
backup_manifest.json
etc/rpi-cam/...
var/log/rpi-cam/... (optionnel)
```

#### Notes
- La version du backup est lue depuis `backup_manifest.json` (pas depuis le nom du fichier)
- La restauration applique uniquement `etc/rpi-cam/*` (les logs restent des copies d'analyse)

### 9.2.2ter Update depuis repo (v2.32.91+)

L'onglet **Systeme** propose un bouton **Update depuis repo** qui ouvre une modale de mise a jour.

#### Flux utilisateur
- Verifie la derniere version disponible (VERSION du repo)
- Telecharge l'archive du repo (branche par defaut)
- Applique les fichiers sur le device
- Installe les dependances Python si `requirements.txt` existe
- Redemarre les services (web manager en dernier, apres reponse)
- Options dans la modale:
  - Forcer la reinstallation (meme version)
  - Reset settings (reinitialiser la configuration)

#### Fichiers mis a jour
- `/opt/rpi-cam-webmanager/*` (UI + backend)
- `/opt/rpi-cam-webmanager/onvif-server/*`
- `/usr/local/bin/rpi_av_rtsp_recorder.sh`
- `/usr/local/bin/rpi_csi_rtsp_server.py`
- `/usr/local/bin/rtsp_recorder.sh`
- `/usr/local/bin/rtsp_watchdog.sh`
- `/opt/rpi-cam-webmanager/VERSION`

#### Backup
- Un backup est cree dans `/tmp/rpi-cam-backup-<timestamp>.tar.gz` si l'option est activee
- La configuration `/etc/rpi-cam/*` n'est pas modifiee

#### Notes
- Necessite un acces Internet
- Compare le fichier `VERSION` du repo (branche par defaut)
- Utilise le repo defini dans `web-manager/config.py` (`GITHUB_REPO`)

### 9.2.2quater Update from file (v2.32.42+)

L'onglet **Systeme** propose un bouton **Update from file** qui applique un package local.

#### Flux utilisateur
- Selection d'un fichier update (.tar.gz)
- Verification complete (version, integrite, chemins autorises)
- Option "forcer" pour reinstaller la meme version si necessaire
- Option "reset settings" pour repartir sur une configuration propre
- Verification des dependances APT via `DEPENDENCIES.json` + requirements.txt Python
- Installation automatique des dependances manquantes
- Application et relance des services (statut affiche en continu)
- Redemarrage automatique si de nouvelles dependances sont installees

#### Format du package
```
update_manifest.json
payload/opt/rpi-cam-webmanager/...
payload/usr/local/bin/...
```

#### Champs optionnels du manifest
- `required_packages`: liste de paquets APT requis
- `requires_reboot`: force un redemarrage apres update

#### Fichier de dependances (obligatoire)
- `web-manager/DEPENDENCIES.json` (installe dans `/opt/rpi-cam-webmanager/DEPENDENCIES.json`)
- Contient la liste **complete** des paquets APT requis + le fichier Python requirements
- Toute dependance ajoutee/supprimee doit etre reflechee ici

#### Logs
- **Fichier** : `/var/log/rpi-cam/update_from_file.log`

#### Rappels de securite
- Les chemins `etc/` sont refuses (pas d'ecrasement config)
- La version dans `update_manifest.json` doit etre **superieure** a la version courante
  - Exception: reinstallation autorisee si option "forcer" activee

### 9.2.2quater RTC DS3231 (v2.32.58+)

L'onglet **Système** propose la prise en charge des modules RTC **DS3231**.

#### Modes
- `auto` : active la RTC si elle est détectée
- `enabled` : force l'activation
- `disabled` : désactive la RTC

#### Fichiers et boot config
- **Etat** : `/etc/rpi-cam/rtc_config.json`
- **Boot config** : `dtoverlay=i2c-rtc,ds3231` + `dtparam=i2c_arm=on`
- **Module I2C** : `/etc/modules-load.d/rpi-cam-i2c.conf` (charge `i2c-dev`)
- Un **redémarrage est requis** après application
- **Outils requis** : `i2c-tools` (i2cdetect), `util-linux` (hwclock)
- **Note Trixie** : `hwclock` peut être dans `util-linux-extra` (installer les deux).
- En mode `auto`, l'activation I2C est appliquée même sans détection (permet un scan au reboot).

#### API
- `GET /api/system/rtc` - Status RTC (mode, detected, overlay_configured, i2c_enabled)
- `POST /api/system/rtc` - Configure le mode RTC (body: `{ "mode": "auto|enabled|disabled" }`)
- `GET /api/debug/rtc` - Diagnostics détaillés (timedatectl, hwclock, i2cdetect)

### 9.2.3 Fichier de verrous des enregistrements

**Emplacement:** `/etc/rpi-cam/locked_recordings.json`

Ce fichier JSON contient la liste des fichiers d'enregistrement verrouillés (protégés contre la suppression automatique).

```json
["rec_20260117_143025.ts", "rec_20260115_091500.ts"]
```

### 9.2.3 Onglet Vidéo (Configuration source et résolution)

L'onglet **Vidéo** permet de configurer la source caméra, la résolution et les paramètres du flux RTSP.

#### Structure (ordre logique v2.30.34+)

1. **Périphérique vidéo**
   - Sélection de la source (USB ou CSI)
   - Détection automatique des caméras connectées
   - Option `USB_ENABLE` / `CSI_ENABLE` (auto/yes/no)
   
2. **Résolution vidéo**
   - Dropdown de résolution détectée avec format, résolution et FPS max
   - Indication du type d'encodage (hardware/software/direct) dans le menu déroulant
   - Le format sélectionné (MJPG/YUYV/H264) est mémorisé via `VIDEO_FORMAT`
   - Affichage des détails (mégapixels, FPS disponibles)
   - Mode manuel : configuration personnalisée (largeur, hauteur)
   - **Auto-remplissage FPS** : sélectionner une résolution remplit automatiquement le champ Images/seconde avec le FPS max
   
3. **Paramètres RTSP** (onglet RTSP)
   - Images/seconde (FPS) : framerate du flux RTSP (indépendant de la caméra)
   - Débit H264 (kbps) : bitrate vidéo de l'encodeur (défaut: 1200 kbps pour Pi 3B+)
   - **Overlay RTSP** : texte + date/heure (USB + CSI, decode/encode software sur CSI)
   - **Note:** Ces réglages contrôlent le flux RTSP et l'enregistrement, pas la caméra elle-même
   
4. **Bouton Appliquer** : Sauvegarde la config et redémarre le service RTSP

#### Rôle des paramètres RTSP

- **Images/seconde (FPS):** Nombre d'images transmises par seconde dans le flux RTSP
  - Valeur typique : 20-30 fps pour streaming stable
  - Limité par le FPS max de la résolution sélectionnée
  
- **Débit H264 (kbps):** Compression vidéo de l'encodeur matériel (v4l2h264enc)
  - Valeur typique : 1200-5000 kbps pour Raspberry Pi 3B+
  - Plus élevé = meilleure qualité mais plus de bande passante
  - L'encodeur hardware utilise la majorité du GPU (VideoCore)

- **Overlay RTSP:** Affichage d'un texte et/ou de la date/heure sur le flux
  - `VIDEO_OVERLAY_ENABLE=yes` pour activer (USB + CSI)
  - `VIDEO_OVERLAY_TEXT` supporte des tokens: `{CAMERA_TYPE}`, `{VIDEO_DEVICE}`, `{VIDEO_RESOLUTION}`, `{VIDEO_FPS}`, `{VIDEO_FORMAT}`
  - `VIDEO_OVERLAY_SHOW_DATETIME=yes` + `VIDEO_OVERLAY_DATETIME_FORMAT` (strftime)
  - `VIDEO_OVERLAY_FONT_SIZE` (1-64)
  - `CSI_OVERLAY_MODE=software|libcamera` (CSI uniquement)
    - `software`: overlay GStreamer (decode/encode software)
    - `libcamera`: overlay rpicam-vid (H264 hardware), **pas de date/heure**
  - **Limites:** pour CSI en `software`, l'overlay force un decodage/encodage software (CPU plus élevé) ; non supporté pour les sources USB en H264 direct
  - **Dépendances:** nécessite `clockoverlay`/`textoverlay` (GStreamer plugins). Installer `gstreamer1.0-x` si absents.
  - **Dépendance CSI (libcamera):** `rpicam-apps-opencv-postprocess`

#### Profils caméra (Contrôles avancés)

La section **Contrôles Caméra** permet d'ajuster les paramètres en temps réel (autofocus, exposition, balance des blancs, etc.) sans redémarrer le service.

- **Bouton ghost-fix (CSI uniquement)** : corrige les oscillations d'image en désactivant AE/AWB et en recentrant la luminosité, puis sauvegarde les valeurs dans le profil.
- **Scheduler de profils** : applique automatiquement le profil actif au démarrage et met en surbrillance le profil effectivement appliqué. Le thread scheduler est protégé par try/except et survit aux erreurs (v2.30.11). Il log les transitions de profils et attend 5s au boot pour stabilisation.

### 9.3 API REST (résumé)

Tous les retours sont JSON avec `success`.

Configuration / statut:
- `GET /api/config`
- `POST /api/config`
- `GET /api/status`
- `POST /api/service/<start|stop|restart>`
- `GET /api/logs?lines=100&source=all`
  - `source`: `all|rtsp|webmanager|recorder|watchdog|onvif|system|journald|file-rtsp|file-recorder|file-watchdog|file-dnsmasq|file-gstreamer|file-all`
- `GET /api/logs/stream` (SSE)
- `GET /api/diagnostic`

Enregistrements (onglet Enregistrements):
- `GET /api/recordings` - Liste basique (ancien, conservé pour compatibilité)
- `GET /api/recordings/list?page=1&per_page=20&filter=all&sort=date-desc&search=` - Liste paginée complète avec détails
- `POST /api/recordings/delete` - Suppression (body: `{ "files": ["rec_....ts"], "force": false }`)
- `POST /api/recordings/lock` - Verrouillage/Déverrouillage (body: `{ "files": ["..."], "lock": true }`)
- `GET /api/recordings/download/<filename>` - Téléchargement du fichier
- `GET /api/recordings/stream/<filename>` - Streaming vidéo (avec support Range pour seeking)
- `GET /api/recordings/info/<filename>` - Informations détaillées (durée, taille, etc.)
- `GET /api/recordings/thumbnail/<filename>` - Thumbnail JPEG (généré/caché automatiquement)

Cache média (v2.30.18+):
- `GET /api/recordings/cache/stats` - Statistiques du cache (entrées, taille, worker status)
- `POST /api/recordings/cache/refresh` - Rafraîchir le cache (scan + nettoyage)
- `POST /api/recordings/cache/cleanup` - Nettoyer les entrées orphelines (fichiers supprimés)

Système:
- `GET /api/system/info` - Informations système (platform, cpu, memory, disk, temp, uptime, network, hostname)
- `GET /api/system/diagnostic` - Informations de diagnostic complètes
- `GET /api/system/ntp` - Status NTP (ntp_enabled, ntp_synchronized, timezone, local_time, utc_time)
- `POST /api/system/ntp` - Configuration NTP (body: `{ "ntp_enabled": true, "timezone": "Europe/Paris" }`)
- `POST /api/system/ntp/sync` - Force synchronisation NTP immédiate
- `GET /api/system/rtc` - Status RTC DS3231 (mode, detected, overlay_configured, i2c_enabled)
- `POST /api/system/rtc` - Configuration RTC (body: `{ "mode": "auto|enabled|disabled" }`)
- `GET /api/system/snmp` - Configuration SNMP (enabled, host, port)
- `POST /api/system/snmp` - Sauvegarde SNMP (body: `{ "enabled": true, "host": "192.168.1.10", "port": 162 }`)
- `POST /api/system/snmp/test` - Test SNMP (résolution + envoi UDP best-effort)
- `GET /api/system/reboot/schedule` - Récupère le redémarrage planifié
- `POST /api/system/reboot/schedule` - Configure le redémarrage planifié (body: `{ "enabled": true, "hour": 3, "minute": 0, "days": ["all"] }`)
- `POST /api/system/update/file/check` - Verifie un update local (multipart: `update`, option `force=1`)
- `POST /api/system/update/file/apply` - Applique un update local (multipart: `update`, option `force=1`)
- `GET /api/system/update/file/status` - Suivi de l'update local
- `POST /api/system/backup` - Genere un backup (body: `{ "include_logs": true }`, reponse binaire)
- `POST /api/system/backup/check` - Verifie un backup (multipart: `backup`)
- `POST /api/system/backup/restore` - Restaure un backup (multipart: `backup`, reboot automatique)
- `GET /api/system/update/check` - Vérifie les mises à jour de l'application
- `POST /api/system/update/perform` - Applique la mise à jour
- `POST /api/system/reboot` - Redémarrage système
- `POST /api/system/shutdown` - Arrêt système
- `POST /api/system/restart/<service_name>` - Redémarre un service
- `POST /api/system/restart-all` - Redémarre tous les services RTSP

Détection:
- `GET /api/detect/cameras`
- `GET /api/detect/audio`

Caméra (V4L2):
- `GET /api/camera/controls`
- `GET|POST /api/camera/autofocus`
- `POST /api/camera/focus`
- `POST /api/camera/control`
- `GET /api/camera/formats`
- `POST /api/camera/oneshot-focus`
- `GET /api/camera/all-controls`
- `POST /api/camera/controls/set-multiple`

Contrôles CSI (Picamera2):
- `GET /api/camera/csi/available` - Vérifie si Picamera2 est disponible
- `GET /api/camera/csi/info` - Informations capteur (modèle, résolution native)
- `GET /api/camera/csi/controls` - Liste tous les contrôles avec min/max/default/valeur sauvegardée
- `POST /api/camera/csi/control` - Modifie un contrôle et le sauvegarde
- `POST /api/camera/csi/tuning/reset` - Réinitialise aux valeurs par défaut

Profils caméra:
- `GET|POST /api/camera/profiles`
- `GET|PUT|DELETE /api/camera/profiles/<name>`
- `POST /api/camera/profiles/<name>/apply`
- `POST /api/camera/profiles/<name>/capture`
- `POST /api/camera/profiles/<name>/ghost-fix`
- `POST /api/camera/profiles/scheduler/start`
- `POST /api/camera/profiles/scheduler/stop`
- `GET /api/camera/profiles/scheduler/status`

Plateforme / Preview:
- `GET /api/platform`
- `GET /api/video/preview/stream`
- `GET /api/video/preview/snapshot`
- `GET /api/video/preview/status`

WiFi / réseau:
- `GET /api/wifi/scan`
- `GET /api/wifi/status`
- `POST /api/wifi/connect`
- `POST /api/wifi/disconnect`
- `GET /api/network/interfaces`
- `GET /api/network/config`
- `POST /api/network/priority`
- `POST /api/network/static`
- `POST /api/network/dhcp`

WiFi configuration simple (1 adaptateur):
- `GET /api/wifi/simple/status` - Statut WiFi simple
  - Retour: `{ success, status: { connected, ssid, saved_ssid, has_saved_password, ip } }`
  - `saved_ssid`: SSID pré-configuré (RPi Imager ou config locale)
- `GET /api/wifi/simple/config` - Config WiFi enregistrée (SSID, masqué password)
- `POST /api/wifi/simple/connect` - Connexion WiFi simple
  - Body: `{ "ssid": "MonWifi", "password": "secret" }`
  - Sauvegarde en config locale + connexion via nmcli

WiFi failover (2+ adaptateurs):
- `GET /api/wifi/failover/status`
- `GET|POST /api/wifi/failover/config`
- `POST /api/wifi/failover/apply`
- `GET /api/wifi/failover/interfaces`
- `POST /api/wifi/failover/disconnect`
- `GET|POST /api/wifi/failover/watchdog`

WiFi / Ethernet auto-gestion:
- `GET /api/network/wifi/override` - Statut de la priorité Ethernet/WiFi
- `POST /api/network/wifi/override` - Forcer/libérer WiFi (body: `{ "enabled": true|false }`)

Mode Access Point (AP):
- `GET /api/network/ap/status` - Statut du point d'accès (actif, SSID, clients, config)
  - Retour: `{ success, status: { active, ssid, ip, clients }, config: { ap_ssid, ap_password, ap_channel, ap_ip } }`
- `POST /api/network/ap/config` - Récupère la configuration AP (local + optionnel Meeting)
  - Body optionnel: `{ "from_meeting": true }`
  - Retour: `{ success, config: { ap_ssid, ap_password, ap_channel, ap_ip } }`
- `POST /api/network/ap/start` - Démarrer le point d'accès
  - Body: `{ "ssid": "...", "password": "...", "channel": 11 }`
- `POST /api/network/ap/stop` - Arrêter le point d'accès

RTSP watchdog (interne):
- `GET /api/rtsp/watchdog/status`
- `POST /api/rtsp/watchdog` (body: `{ "action": "start|stop|restart_service" }`)

Gestion des logs:
- `GET /api/logs?lines=100&source=all` - Récupère les logs récents
  - `source`: `all|rtsp|webmanager|recorder|watchdog|onvif|system|journald|file-rtsp|file-recorder|file-watchdog|file-dnsmasq|file-gstreamer|file-all`
- `GET /api/logs/stream` - Streaming SSE des logs en temps réel
- `POST /api/logs/clean` - Nettoie les fichiers de logs sur le serveur

LEDs / GPU / système:
- `GET /api/leds/status`
- `POST /api/leds/set`
- `GET /api/leds/boot-config`
- `GET|POST /api/gpu/mem`
- `POST /api/system/update/file/check`
- `POST /api/system/update/file/apply`
- `GET /api/system/update/file/status`
- `POST /api/system/backup`
- `POST /api/system/backup/check`
- `POST /api/system/backup/restore`
- `POST /api/system/reboot`
- `GET|POST /api/system/ntp`
- `POST /api/system/ntp/sync`

Updater GitHub:
- `GET /api/system/update/check`
- `POST /api/system/update/perform`

Intégration Meeting (optionnel):
- `POST /api/meeting/test`
- `POST /api/meeting/heartbeat`
- `GET /api/meeting/availability`
- `GET /api/meeting/device`
- `POST /api/meeting/tunnel`
- `GET /api/meeting/status`
- `POST /api/meeting/validate` - Valide les credentials sans provisionner
- `POST /api/meeting/provision` - Provisionne le device (brûle un token, change hostname)
- `POST /api/meeting/master-reset` - Réinitialise la config Meeting (nécessite code master)

ONVIF (gestion):
- `GET /api/onvif/status`
- `GET|POST /api/onvif/config`
- `POST /api/onvif/restart`

Debug (maintenance système):
- `GET /api/debug/rtc` - Diagnostics RTC (timedatectl, hwclock, i2cdetect)
- `GET /api/debug/firmware/check` - Vérifie les mises à jour firmware (rpi-update sur Pi 3, rpi-eeprom-update sur Pi 4/5)
- `POST /api/debug/firmware/update` - Applique la mise à jour firmware
- `POST /api/debug/apt/update` - Rafraîchit les listes de paquets apt
- `GET /api/debug/apt/upgradable` - Liste des paquets à mettre à jour
- `POST /api/debug/apt/upgrade` - Applique les mises à jour de paquets
- `GET /api/debug/system/uptime` - Uptime du système

### 9.4 Onglet Enregistrements (Gestion des fichiers)

L'onglet **Fichiers** permet de gérer les enregistrements vidéo depuis l'interface web.

#### Fonctionnalités

| Fonction | Description |
|----------|-------------|
| **Lecture** | Player vidéo intégré avec seeking (requêtes Range HTTP) |
| **Verrouillage** | Protection des fichiers contre la suppression automatique/manuelle |
| **Téléchargement** | Export des fichiers vers le PC client |
| **Suppression** | Individuelle ou par lot (fichiers verrouillés protégés) |
| **Filtres** | Par statut (tous/verrouillés/non verrouillés) + recherche textuelle |
| **Tri** | Par date, nom ou taille (croissant/décroissant) |

#### Interface utilisateur

- **Bandeau stockage** : Nombre de fichiers, espace utilisé, espace disponible, chemin du répertoire
- **Barre d'actions** : Actualiser, sélectionner tout, verrouiller/déverrouiller/supprimer la sélection
- **Liste des fichiers** : Checkbox, icône de verrouillage, nom, date, taille, boutons d'actions
- **Barre de sélection** : Compteur de fichiers sélectionnés et taille totale

#### Formats supportés

- `.ts` (MPEG Transport Stream) - Format principal des enregistrements
- `.mp4` (MPEG-4)
- `.mkv` (Matroska)
- `.avi` (Audio Video Interleave)

#### API Endpoints détaillés

```
GET /api/recordings/list
```
Liste complète des fichiers avec métadonnées.
**Réponse:**
```json
{
  "success": true,
  "recordings": [
    {
      "name": "rec_20260117_143025.ts",
      "size_bytes": 52428800,
      "size_mb": 50.0,
      "size_display": "50.0 Mo",
      "modified": 1737125425.0,
      "modified_iso": "2026-01-17T14:30:25",
      "modified_display": "17/01/2026 14:30",
      "locked": false,
      "extension": ".ts"
    }
  ],
  "total_count": 15,
  "total_size": 786432000,
  "total_size_display": "750.0 Mo",
  "directory": "/var/cache/rpi-cam/recordings",
  "disk_info": {
    "total": 31457280000,
    "available": 20971520000,
    "total_display": "29.3 Go",
    "available_display": "19.5 Go"
  }
}
```

```
POST /api/recordings/lock
```
Verrouiller ou déverrouiller des fichiers.
**Body:**
```json
{
  "files": ["rec_001.ts", "rec_002.ts"],
  "lock": true
}
```

```
POST /api/recordings/delete
```
Supprimer des fichiers.
**Body:**
```json
{
  "files": ["rec_003.ts"],
  "force": false
}
```
**Note:** Si `force=false`, les fichiers verrouillés sont ignorés.

```
GET /api/recordings/download/<filename>
```
Téléchargement direct du fichier (Content-Disposition: attachment).

```
GET /api/recordings/stream/<filename>
```
Streaming du fichier pour lecture dans le player. Supporte les requêtes Range pour le seeking.

```
GET /api/recordings/info/<filename>
```
Informations détaillées sur un fichier (inclut la durée si ffprobe est disponible).

### 9.4.1 Système de Cache Média SQLite (v2.30.18+)

Le système de cache média optimise la galerie d'enregistrements en réduisant drastiquement les appels `ffprobe` et l'usure de la carte SD.

#### Architecture

```
/var/cache/rpi-cam/
├── media_cache.db          # Base SQLite (métadonnées vidéo)
└── thumbnails/             # Miniatures JPEG générées
    ├── rec_20260118_040938.jpg
    └── ...
```

**Composants:**
- **Base SQLite** (`media_cache.db`) : ~100 Ko pour 100+ fichiers
- **Cache thumbnails** : ~2-3 Mo pour 100 fichiers (320px de large)
- **Worker background** : Thread dédié pour extraction asynchrone

#### Fonctionnement

1. **Premier chargement** (fichier non caché)
   - L'API retourne immédiatement les métadonnées de fichier (taille, date)
   - Le worker background extrait les métadonnées vidéo (durée, codec, résolution)
   - Le prochain appel API aura toutes les informations

2. **Chargements suivants** (fichier caché)
   - Métadonnées lues depuis SQLite (<1ms)
   - Pas d'appel ffprobe

3. **Thumbnails**
   - Générés à la demande via `/api/recordings/thumbnail/<filename>`
   - Cachés sur disque, régénérés si le fichier source change
   - Extraction via ffmpeg à t=2s (ou t=0s pour vidéos courtes)

4. **Invalidation automatique**
   - Quand un fichier est supprimé, l'entrée cache est supprimée
   - Le thumbnail associé est également supprimé

#### API de gestion du cache

```
GET /api/recordings/cache/stats
```
Retourne les statistiques du cache :
```json
{
  "success": true,
  "total_entries": 82,
  "with_thumbnails": 80,
  "missing_thumbnails": 2,
  "total_duration_seconds": 6177.15,
  "total_duration_human": "1:42:57",
  "database_size": 94208,
  "database_size_human": "92.0 Ko",
  "thumbnail_cache_size": 1946706,
  "thumbnail_cache_size_human": "1.9 Mo",
  "worker_status": {
    "running": true,
    "queue_size": 0,
    "thumbnails_generated": 15,
    "metadata_extracted": 82,
    "errors": 0
  }
}
```

```
POST /api/recordings/cache/refresh
```
Scanne le dossier d'enregistrements et met à jour le cache :
- Nettoie les entrées orphelines (fichiers supprimés)
- Ajoute les nouveaux fichiers au cache
- Queue les thumbnails manquants pour génération background

```
POST /api/recordings/cache/cleanup
```
Nettoie uniquement les entrées orphelines (fichiers supprimés).

### 9.4.2 Génération automatique des thumbnails (v2.36.04+)

Depuis la version 2.36.04, les miniatures sont générées **automatiquement** dès qu'un nouvel enregistrement est terminé, au lieu d'être générées à la demande lors de la consultation de la galerie.

#### Fonctionnement

1. **Watcher inotify** : Le script `rtsp_recorder.sh` utilise `inotifywait` pour surveiller le dossier d'enregistrements
2. **Détection** : Quand un fichier `.ts` est complètement écrit (événement `close_write`)
3. **Notification** : Le recorder appelle l'API `/api/recordings/thumbnail/notify`
4. **Génération** : L'API génère immédiatement le thumbnail et l'ajoute au cache SQLite

#### Architecture

```
rtsp_recorder.sh
    │
    ├── ffmpeg (enregistrement RTSP → segments .ts)
    │
    └── inotifywait (surveillance dossier)
            │
            └── notify_new_recording()
                    │
                    └── curl → /api/recordings/thumbnail/notify
                                │
                                └── generate_thumbnail() + cache_metadata()
```

#### API Notification

```
POST /api/recordings/thumbnail/notify
```
Notifie la création d'un nouvel enregistrement pour génération immédiate du thumbnail.

**Body:**
```json
{
  "filepath": "/var/cache/rpi-cam/recordings/rec_20260202_164200.ts"
}
```

**Réponse (succès):**
```json
{
  "success": true,
  "message": "Thumbnail generated",
  "filepath": "/var/cache/rpi-cam/recordings/rec_20260202_164200.ts",
  "thumbnail": "/var/cache/rpi-cam/thumbnails/rec_20260202_164200.jpg"
}
```

**Réponse (file en queue):**
```json
{
  "success": true,
  "message": "Thumbnail queued for generation",
  "filepath": "/var/cache/rpi-cam/recordings/rec_20260202_164200.ts"
}
```
HTTP 202 - Le fichier est trop récent ou la génération synchrone a échoué, mais il est en queue pour traitement background.

**Codes d'erreur:**
- 400 : Chemin manquant ou invalide
- 404 : Fichier non trouvé
- 500 : Erreur interne

#### Prérequis

Le paquet `inotify-tools` doit être installé :
```bash
sudo apt install inotify-tools
```

Si non installé, le recorder fonctionne normalement mais les thumbnails seront générés à la demande (comportement classique).

#### Logs

Les notifications sont loguées dans `/var/log/rpi-cam/rtsp_recorder.log` :
```
[2026-02-02 16:43:29] Thumbnail notification sent for: rec_20260202_164230.ts
```

En cas d'échec :
```
[2026-02-02 16:43:35] ERROR: Failed to notify thumbnail generation for: rec_20260202_164230.ts
```

#### Optimisations techniques

- **ffprobe optimisé** : `-read_intervals %+5` (ne lit que les 5 premières secondes)
- **Timeout réduit** : 10s au lieu de 30s pour éviter de bloquer Gunicorn
- **Mode WAL SQLite** : Meilleure performance en écriture concurrente
- **Worker thread daemon** : S'arrête proprement avec l'application

### 9.5 Onglet Debug (Maintenance système)

L'onglet **Debug** permet d'effectuer des opérations de maintenance avancées sur le système.

⚠️ **Avertissement** : Les opérations de cet onglet peuvent affecter la stabilité du système. À utiliser avec précaution.

#### Accès conditionnel (v2.30.50)

L'onglet Debug n'est visible et accessible **que si le service 'vnc' ou 'debug' est déclaré** pour ce device dans Meeting.

**Comportement :**
- Si le service est déclaré → L'onglet apparaît dans la barre de navigation
- Si le service n'est pas déclaré → L'onglet est masqué et les APIs retournent 403

**Protection API :**
Toutes les routes `/api/debug/*` sont protégées par le décorateur `@require_debug_access`. Si non autorisé :
```json
{
  "success": false,
  "error": "Debug access not authorized",
  "message": "This feature requires the 'vnc' or 'debug' service to be declared in Meeting."
}
```

**Note :** Les routes `/api/system/ntp/*` (NTP, synchronisation temps) restent accessibles sans restriction.

**Fonctions Meeting utilisées :**
- `is_service_declared(service_name)` : Vérifie si un service est déclaré dans `device_info.declared_services` ou `device_info.services`
- `is_debug_enabled()` : Raccourci qui vérifie 'vnc' OU 'debug'

#### Firmware Raspberry Pi

Vérifie et installe les mises à jour firmware. La méthode dépend du modèle de Pi et de la configuration système :

| Modèle | Système | Outil | Type de mise à jour |
|--------|---------|-------|---------------------|
| **Pi 4, Pi 5** | Tous | `rpi-eeprom-update` | EEPROM bootloader uniquement |
| **Pi 3, Pi 2, Zero** | Sans initramfs | `rpi-update` | Kernel + firmware VideoCore (⚠️ expérimental) |
| **Pi 3, Pi 2, Zero** | **Avec initramfs** (Debian 13/Trixie) | `apt upgrade` | Via paquets linux-image et raspberrypi-kernel |

**Détection automatique initramfs :**

Sur Raspberry Pi OS Trixie (Debian 13), le système utilise `initramfs` par défaut. Dans ce cas :
- `rpi-update` **n'est pas supporté** (erreur "initramfs configured is not supported")
- L'API retourne `method: "apt"` et `can_update: false`
- Le message indique d'utiliser **apt upgrade** pour les mises à jour kernel/firmware

**Processus :**
1. **Vérifier** : Détecte le modèle et la présence d'initramfs
2. **Mettre à jour** : 
   - Systèmes avec initramfs → Utiliser la section "apt upgrade" ci-dessous
   - Systèmes sans initramfs → Bouton de mise à jour direct (nécessite redémarrage)

**Note importante :**
`rpi-update` installe un firmware **expérimental** (bleeding edge). En production, les mises à jour via `apt upgrade` sont recommandées car elles apportent des versions stables testées.

#### Mise à jour des paquets (apt)

| Action | Description |
|--------|-------------|
| **Rafraîchir les sources** | Équivalent à `apt update` - synchronise les listes de paquets |
| **Vérifier mises à jour** | Liste les paquets avec une mise à jour disponible |
| **Mettre à jour les paquets** | Équivalent à `apt upgrade -y` - installe les mises à jour |

#### Redémarrage système

- Affiche l'**uptime** actuel du système
- Bouton de **redémarrage** avec confirmation obligatoire
- Écran de **reconnexion automatique** après redémarrage

#### Terminal Web (v2.30.52)

Interface de commandes sécurisée pour exécuter des commandes shell directement depuis l'interface web.

**Fonctionnalités :**
- Historique des commandes (flèches haut/bas)
- Commandes spéciales : `clear` (efface), `help` (aide)
- Timeout configurable (max 120s)
- Support `sudo` pour les commandes autorisées

**Commandes autorisées (whitelist) :**
- **Système** : ls, cat, head, tail, grep, find, df, du, free, top, ps, uptime, date, hostname, uname, whoami, id, pwd
- **Journaux** : journalctl, dmesg
- **Services** : systemctl, service
- **Réseau** : ip, ifconfig, iwconfig, nmcli, netstat, ss, ping, traceroute, curl, wget
- **Matériel** : vcgencmd, pinctrl, lsusb, lspci, lsblk, lscpu, lshw, lsmod, v4l2-ctl
- **Média** : ffprobe, ffmpeg, gst-launch-1.0, gst-inspect-1.0, test-launch
- **Paquets** : apt, apt-get, apt-cache, dpkg
- **Utilitaires** : echo, which, whereis, file, stat, wc, sort, uniq, awk, sed, cut, tr, tee

**APIs Terminal :**
- `POST /api/debug/terminal/exec` - Exécute une commande (body: `{command, timeout}`)
- `GET /api/debug/terminal/allowed` - Liste des commandes autorisées

**Exemple :**
```json
// POST /api/debug/terminal/exec
{"command": "df -h", "timeout": 30}

// Réponse
{
  "success": true,
  "stdout": "Filesystem      Size  Used Avail Use% Mounted on\n...",
  "stderr": "",
  "returncode": 0
}
```

#### API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/debug/firmware/check` | GET | Vérifie les mises à jour firmware disponibles |
| `/api/debug/firmware/update` | POST | Applique la mise à jour firmware |
| `/api/debug/apt/update` | POST | Rafraîchit les sources apt |
| `/api/debug/apt/upgradable` | GET | Liste les paquets à mettre à jour |
| `/api/debug/apt/upgrade` | POST | Applique les mises à jour de paquets |
| `/api/debug/system/uptime` | GET | Retourne l'uptime formaté |
| `/api/debug/terminal/exec` | POST | Exécute une commande shell |
| `/api/debug/terminal/allowed` | GET | Liste des commandes autorisées |

**Exemple de réponse `/api/debug/firmware/check` :**
```json
{
  "success": true,
  "method": "rpi-update",
  "model": "Pi 3/2/Zero",
  "update_available": true,
  "message": "Mise à jour firmware disponible"
}
```

---

## 10) Configuration: `/etc/rpi-cam/config.env`

Format `KEY="VALUE"` ou `KEY=VALUE`.

RTSP / vidéo:
- `RTSP_PORT`, `RTSP_PATH`
- `RTSP_PROTOCOLS` (`udp,tcp,udp-mcast`) - transports RTSP côté client
- `RTSP_USER`, `RTSP_PASSWORD` (authentification, optionnel - les deux requis pour activer)

Paramètres d'entrée caméra (VIDEOIN_*) - **contrôlés par l'utilisateur uniquement** :
- `VIDEOIN_WIDTH`, `VIDEOIN_HEIGHT`, `VIDEOIN_FPS`, `VIDEOIN_DEVICE`
- `VIDEOIN_FORMAT` (`auto|MJPG|YUYV|H264`) - format USB préféré
- Alias legacy: `VIDEO_WIDTH`, `VIDEO_HEIGHT`, `VIDEO_FPS`, `VIDEO_DEVICE`, `VIDEO_FORMAT`

Paramètres de sortie RTSP (VIDEOOUT_*) - **contrôlables par ONVIF** (v2.36.00+) :
- `VIDEOOUT_WIDTH`, `VIDEOOUT_HEIGHT`, `VIDEOOUT_FPS` (optionnels, fallback sur VIDEOIN_*)
- Alias legacy: `OUTPUT_WIDTH`, `OUTPUT_HEIGHT`, `OUTPUT_FPS`
- Si définis et différents de VIDEOIN_*, le pipeline ajoute `videoscale`/`videorate`
- `STREAM_SOURCE_MODE` (`camera|rtsp|mjpeg|screen`)
- `STREAM_SOURCE_URL` (URL source RTSP/MJPEG)
- `RTSP_PROXY_TRANSPORT` (`auto|tcp|udp`)
- `RTSP_PROXY_AUDIO` (`auto|yes|no`)
- `RTSP_PROXY_LATENCY_MS` (ms)
- `SCREEN_DISPLAY` (ex: `:0.0`)
- `CAMERA_TYPE` (`auto|usb|csi`)
- `CAMERA_DEVICE` (legacy, fallback du périphérique caméra)
- `CSI_ENABLE` (`auto|yes|no`), `USB_ENABLE` (`auto|yes|no`)
- `H264_BITRATE_KBPS`, `H264_KEYINT`
- `H264_PROFILE` (`baseline|constrained baseline|main|high`) - profil H.264 (CSI RTSP Server)
- `H264_QP` (1-51, optionnel) - quantizer fixe (CSI RTSP Server)
- `VIDEO_OVERLAY_ENABLE` (`yes|no`) - active l'overlay texte/date (USB + CSI)
- `VIDEO_OVERLAY_TEXT` - texte overlay (tokens: `{CAMERA_TYPE}`, `{VIDEO_DEVICE}`, `{VIDEO_RESOLUTION}`, `{VIDEO_FPS}`, `{VIDEO_FORMAT}`)
- `VIDEO_OVERLAY_POSITION` (`top-left|top-right|bottom-left|bottom-right`)
- `VIDEO_OVERLAY_SHOW_DATETIME` (`yes|no`)
- `VIDEO_OVERLAY_DATETIME_FORMAT` (strftime)
- `VIDEO_OVERLAY_CLOCK_POSITION` (`top-left|top-right|bottom-left|bottom-right`)
- `VIDEO_OVERLAY_FONT_SIZE` (1-64)
- `CSI_OVERLAY_MODE` (`software|libcamera`) - overlay CSI (libcamera = pas de date/heure)

Audio:
- `AUDIO_ENABLE` (`auto|yes|no`)
- `AUDIO_RATE`, `AUDIO_CHANNELS`, `AUDIO_BITRATE_KBPS`
- `AUDIO_DEVICE` (`auto` ou `plughw:X,0`)
- `AUDIO_GAIN` (0.0 à 3.0, défaut 1.0 = pas de changement)

Enregistrement:
- `RECORD_ENABLE` (`yes|no`)
- `RECORD_DIR`
- `SEGMENT_SECONDS`
- `MIN_FREE_DISK_MB`
- `MAX_DISK_MB` (0 = illimité)

Logs:
- `LOG_DIR`
- `GST_DEBUG_LEVEL`

Meeting (optionnel):
- `MEETING_ENABLED` (`yes|no`)
- `MEETING_API_URL`
- `MEETING_DEVICE_KEY`
- `MEETING_TOKEN_CODE`
- `MEETING_HEARTBEAT_INTERVAL`
- `MEETING_PROVISIONED` (`yes|no`) - Indique si le device est provisionné (verrouille la config)

SNMP (optionnel):
- `SNMP_ENABLED` (`yes|no`)
- `SNMP_SERVER_HOST` (IP/host)
- `SNMP_SERVER_PORT` (1-65535, défaut 162)

Profils caméra:
- `CAMERA_AUTOFOCUS` (`yes|no|auto`)
- `CAMERA_PROFILES_ENABLED` (`yes|no`)
- `CAMERA_PROFILES_FILE` (par défaut `/etc/rpi-cam/camera_profiles.json`)

Relais ONVIF (DeviceIO):
- `RELAY_ENABLE` (`yes|no`)
- `RELAY_GPIO_PIN` (GPIO BCM)
- `RELAY_GPIO_CHIP` (ex: `gpiochip0`)
- `RELAY_ACTIVE_HIGH` (`true|false`)
- `RELAY_OUTPUT_NAME`
- `RELAY_OUTPUT_TOKEN`

---

## 11) Gestion des logs

### 11.1 Fichiers de logs

| Fichier | Description |
|---------|-------------|
| `/var/log/rpi-cam/rpi_av_rtsp_recorder.log` | Logs du service RTSP principal |
| `/var/log/rpi-cam/rtsp_recorder.log` | Logs du service d'enregistrement |
| `/var/log/rpi-cam/rtsp_watchdog.log` | Logs du watchdog RTSP |
| `/var/log/rpi-cam/dnsmasq.log` | Logs du mode AP (dnsmasq) |
| `/var/log/rpi-cam/gstreamer*.log` | Logs debug GStreamer (si GST_DEBUG_LEVEL > 2) |
| journald (`rpi-av-rtsp-recorder`) | Logs systemd du service RTSP |
| journald (`rpi-cam-webmanager`) | Logs systemd de l'interface web |
| journald (`rtsp-recorder`) | Logs systemd de l'enregistreur |
| journald (`rtsp-watchdog`) | Logs systemd du watchdog |
| journald (`rpi-cam-onvif`) | Logs systemd du serveur ONVIF |

### 11.2 Problème des logs GStreamer

**Attention:** Les logs GStreamer peuvent devenir TRÈS volumineux (100+ Mo/jour) si `GST_DEBUG_LEVEL` > 2.

Recommandation:
- Production: `GST_DEBUG_LEVEL=2` (erreurs + warnings)
- Debug: `GST_DEBUG_LEVEL=4` ou `GST_DEBUG_LEVEL=6` temporairement

### 11.3 Nettoyage automatique au boot

Le script `rpi_av_rtsp_recorder.sh` (v2.4.0+) effectue un nettoyage automatique à chaque démarrage:
- Tronque le log principal s'il dépasse 10 Mo (garde 1000 dernières lignes)
- Supprime les fichiers de logs > 7 jours
- Supprime tous les logs GStreamer debug
- Nettoie les fichiers temporaires GStreamer dans `/tmp`
- Vacuum journald (limite 50 Mo)

### 11.4 Nettoyage manuel via l'interface web

L'onglet "Logs" de l'interface web propose un bouton **"Nettoyer les logs serveur"** qui:
- Tronque le fichier log principal (garde 100 dernières lignes)
- Supprime les logs GStreamer
- Supprime les vieux fichiers de log (> 7 jours)
- Vacuum journald

L'onglet "Logs" propose aussi **"Export Logs"** pour télécharger un extrait des logs selon la source choisie.

---

## 12) Performance (Pi 3B+) / Anti-surcharge

### 12.1 Thumbnails (galerie)

L'affichage de la galerie peut déclencher de la génération de thumbnails (`ffmpeg`) et d'extraction de métadonnées (`ffprobe`).

Mesures anti-surcharge (v2.32.50+):
- La route `GET /api/recordings/thumbnail/<file>` **ne génère plus** de thumbnail en mode bloquant.
- Les jobs thumbnails sont **mis en queue** via `Media Cache Worker` (1 thread) avec **déduplication** (évite plusieurs `ffmpeg` en parallèle pour le même fichier).
- `ffmpeg` / `ffprobe` sont lancés en **basse priorité** (best-effort `nice` + `ionice`) pour protéger le flux RTSP.

### 12.2 PipeWire/WirePlumber

RTSP-Full utilise ALSA direct sous systemd/root (`alsasrc`). PipeWire/WirePlumber peut:
- capturer le device audio (ALSA “busy”),
- ajouter du CPU,
- et n'est généralement pas nécessaire sur un device headless RTSP.

Installation (v2.2.1+ de `setup/install_gstreamer_rtsp.sh`):
- `INSTALL_PIPEWIRE=no` par défaut
- si PipeWire est présent, il est masqué globalement (services **et sockets**) pour éviter la socket-activation.

### 11.5 Nettoyage manuel via API

```bash
curl -X POST http://<IP>:5000/api/logs/clean
```

Réponse:
```json
{
  "success": true,
  "message": "Logs nettoyés: rpi_av_rtsp_recorder.log (truncated), journald (vacuumed)",
  "freed_bytes": 52428800
}
```

### 11.6 Nettoyage manuel (CLI)

```bash
# Tronquer le log principal
sudo tail -n 100 /var/log/rpi-cam/rpi_av_rtsp_recorder.log > /tmp/log.tmp && sudo mv /tmp/log.tmp /var/log/rpi-cam/rpi_av_rtsp_recorder.log

# Supprimer les logs GStreamer
sudo rm -f /var/log/rpi-cam/gstreamer*.log /var/log/rpi-cam/gst_*.log

# Vacuum journald
sudo journalctl --vacuum-size=50M
```

---

## 12) Commandes utiles (ops)

Services:
```bash
systemctl status rpi-av-rtsp-recorder
systemctl status rtsp-recorder
systemctl status rpi-cam-webmanager
systemctl status rpi-cam-onvif
```

Logs:
```bash
journalctl -u rpi-av-rtsp-recorder -f
journalctl -u rpi-cam-webmanager -f
tail -f /var/log/rpi-cam/rpi_av_rtsp_recorder.log
```

Périphériques:
```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
arecord -l
```

---

## 13) Dépannage (checklist)

RTSP ne démarre pas:
- vérifier `test-launch`: `command -v test-launch` ou `/usr/local/bin/test-launch`
- vérifier les plugins: `gst-inspect-1.0 rtph264pay h264parse`
- vérifier caméra: `/dev/video0` et `v4l2-ctl -d /dev/video0 --all`

**Configuration vidéo non appliquée (CORRIGÉ v2.15.2):**
- **Symptôme** : Le stream RTSP utilise 640x480@15fps malgré config.env à 1280x720@30fps
- **Cause** : Bug d'ordre de chargement dans `rpi_av_rtsp_recorder.sh` < v2.15.2
- **Vérification** : `ps aux | grep test-launch` doit montrer les bonnes valeurs width/height/framerate
- **Solution** : Mettre à jour `rpi_av_rtsp_recorder.sh` vers v2.15.2+
- **Note** : Le fichier config.env doit utiliser `VIDEO_WIDTH/HEIGHT/FPS` (pas `VIDEOIN_*`)

CPU trop élevé (Pi 3B+):
- réduire `VIDEOIN_WIDTH/HEIGHT/FPS` (ex: `640x480@15`)
- préférer une caméra USB MJPEG
- si `v4l2h264enc` est cassé, rester sur paramètres “safe” pour `x264enc`

Audio absent:
- sous systemd/root, utiliser ALSA (`AUDIO_DEVICE=plughw:X,0`)
- vérifier `arecord -l` et `gst-inspect-1.0 alsasrc`

Logs trop volumineux:
- vérifier `GST_DEBUG_LEVEL` dans `/etc/rpi-cam/config.env` (recommandé: 2)
- utiliser le bouton "Nettoyer les logs serveur" dans l'interface web
- ou appeler `POST /api/logs/clean`

---

## 14) Provisioning Meeting

### 14.1 Concept

Le provisioning Meeting permet de lier un device à la plateforme IoT Meeting.
Une fois provisionné, la configuration Meeting est **verrouillée** et le hostname du device est changé vers la `device_key`.

### 14.2 Workflow de provisioning

1. **Entrer les credentials**
   - URL API Meeting (ex: `https://cluster.meeting.ygsoft.fr/api`)
   - Device Key (clé unique 32 caractères)
   - Token Code (code d'authentification)

2. **Valider les credentials**
   - Le système contacte l'API Meeting pour vérifier la validité
   - Vérifie que le device est **autorisé** (`authorized=true`)
   - Vérifie le nombre de **tokens disponibles** (`token_count > 0`)

3. **Provisionner le device** (si validation OK)
   - Consomme un token via `POST /api/devices/{device_key}/flash-request`
   - Change le hostname du Raspberry vers la device_key
   - Sauvegarde la configuration avec `MEETING_PROVISIONED=yes`
   - Active le heartbeat automatique

### 14.3 État provisionné

Une fois provisionné:
- La configuration Meeting est en **lecture seule** dans l'interface web
- Le heartbeat est envoyé automatiquement selon l'intervalle configuré
- L'URL RTSP est affichée avec le hostname (ex: `rtsp://ABC123.local:8554/stream`)
- L'URL IP est affichée comme "accès de secours"

### 14.4 Master Reset

Pour réinitialiser un device provisionné:
1. Cliquer sur le bouton **"Master Reset"** dans l'onglet Meeting
2. Entrer le **code master** (par défaut: `meeting`)
3. Confirmer la réinitialisation

⚠️ **Attention**: Le Master Reset:
- Supprime la configuration Meeting
- Désactive le heartbeat
- **Ne change pas** le hostname (le device garde son nom)
- **Ne restaure pas** le token consommé

### 14.5 API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/meeting/validate` | POST | Valide credentials sans provisionner |
| `/api/meeting/provision` | POST | Provisionne le device (brûle un token) |
| `/api/meeting/master-reset` | POST | Réinitialise la config (nécessite code) |
| `/api/meeting/services` | GET | Retourne les services déclarés (ssh, http, etc.) |
| `/api/meeting/ssh/key` | GET | Récupère la clé publique SSH du device |
| `/api/meeting/ssh/key/generate` | POST | Génère une paire de clés SSH ed25519 |
| `/api/meeting/ssh/key/publish` | POST | Publie la clé SSH sur le serveur Meeting |
| `/api/meeting/ssh/hostkey/sync` | POST | Synchronise les hostkeys du serveur Meeting |
| `/api/meeting/ssh/setup` | POST | Setup SSH complet (génère + sync + publie) |
| `/api/meeting/ssh/keys/status` | GET | Status des clés SSH (device + Meeting) |
| `/api/meeting/ssh/keys/ensure` | POST | Auto-configuration des clés SSH (v2.35.18+) |

### 14.5.1 Heartbeat (implémentation conforme au guide Meeting)

Le heartbeat envoie régulièrement (par défaut 60s) l'état du device au serveur Meeting.

**Endpoint Meeting appelé:** `POST /api/devices/{device_key}/online`

**Payload envoyé (v2.35.11+):**
```json
{
    "ip_address": "192.168.1.202",
    "ip_lan": "192.168.1.202",
    "ip_public": "82.65.xx.xx",
    "mac": "AA:BB:CC:DD:EE:FF",
    "note": "RTSP Recorder - Raspberry Pi 3 Model B Rev 1.2"
}
```

**Champs réseau (v2.35.11+):**
- `ip_address` : IP de l'interface principale (ethernet ou WiFi actif)
- `ip_lan` : Alias de ip_address (rétrocompatibilité)
- `ip_public` : IP publique détectée via services externes (ipify, ipinfo, amazonaws)
- `mac` : Adresse MAC de l'interface principale (format AA:BB:CC:DD:EE:FF)

**Note:** Le champ `services` n'est plus envoyé dans le heartbeat (depuis v2.35.08). Les services sont gérés côté admin Meeting, les devices ne doivent pas les envoyer.

**Services (lecture seule via API):**
- `ssh` : actif si service SSH/SSHD démarré
- `http` : actif si Web Manager démarré
- `scp` : actif si SSH actif
- `vnc` : actif si un serveur VNC tourne
- `debug` : actif si DEBUG_MODE=yes dans config.env

### 14.5.2 Gestion des clés SSH

Lors du provisioning, le système effectue automatiquement:
1. Génération d'une paire de clés SSH ed25519 (`/root/.ssh/id_ed25519`)
2. Synchronisation des hostkeys du serveur Meeting (`GET /api/ssh-hostkey`)
3. Publication de la clé publique sur Meeting (`PUT /api/devices/{device_key}/ssh-key`)
4. Installation de la clé publique Meeting dans `authorized_keys` (root ET device)

**Fichiers SSH:**
- `/root/.ssh/id_ed25519` : clé privée device
- `/root/.ssh/id_ed25519.pub` : clé publique device
- `/root/.ssh/known_hosts` : hostkeys du serveur Meeting
- `/root/.ssh/authorized_keys` : clé publique Meeting (pour connexion SSH entrante)
- `/home/device/.ssh/authorized_keys` : clé publique Meeting (utilisateur SSH principal)

**Auto-configuration SSH (v2.35.18+):**
L'agent tunnel configure automatiquement les clés au démarrage:
1. Génère la clé device si absente
2. Installe la clé publique Meeting dans authorized_keys (root + device)
3. Publie la clé device vers l'API Meeting

**Endpoint auto-config:**
```bash
POST /api/meeting/ssh/keys/ensure
# Retourne: { "success": true, "message": "...", "details": [...] }
```

**Vérification du status:**
```bash
GET /api/meeting/ssh/keys/status
# Retourne: { "success": true, "device_key_exists": bool, "meeting_key_installed": bool }
```

### 14.5.3 Agent Tunnel Inversé

L'agent tunnel permet des connexions SSH/SCP distantes via le proxy Meeting.

**Fichiers:**
- `/opt/rpi-cam-webmanager/tunnel_agent.py` : agent Python
- `/etc/systemd/system/meeting-tunnel-agent.service` : service systemd

**Protocole:**
1. Connexion TCP vers `meeting.ygsoft.fr:9001`
2. Handshake: `{"token":"<TOKEN>","name":"<device_key>"}\n`
3. Frames multiplexées: `[type:1][streamId:4][length:4][payload:N]`
   - `N` (New): ouvre une connexion locale vers `127.0.0.1:localPort`
   - `D` (Data): transfère des données
   - `C` (Close): ferme un stream

**Contrôle via API:**
```bash
# État de l'agent
GET /api/meeting/tunnel/agent/status

# Démarrer/Arrêter
POST /api/meeting/tunnel/agent/start
POST /api/meeting/tunnel/agent/stop

# Auto-démarrage
POST /api/meeting/tunnel/agent/enable
POST /api/meeting/tunnel/agent/disable
```

**Activation manuelle:**
```bash
sudo systemctl enable --now meeting-tunnel-agent
sudo systemctl status meeting-tunnel-agent
```

**Configuration:**
L'agent lit sa configuration depuis `/etc/rpi-cam/meeting.json`:
```json
{
    "device_key": "ABC123...",
    "token_code": "secret",
    "tunnel_host": "meeting.ygsoft.fr",
    "tunnel_port": 9001,
    "tunnel_ssl": false
}
```

**Note importante (v1.4.1):** Le proxy Meeting port 9001 utilise **TCP pur**, pas SSL/TLS. Le paramètre `tunnel_ssl` doit être `false` (c'est le défaut depuis v1.4.1).

**Exemple validation:**
```json
POST /api/meeting/validate
{
    "api_url": "https://cluster.meeting.ygsoft.fr/api",
    "device_key": "ABC123456789",
    "token_code": "secret_token"
}

Response:
{
    "success": true,
    "valid": true,
    "device": {
        "name": "Camera Bureau",
        "authorized": true,
        "token_count": 5,
        "online": false
    }
}
```

**Exemple provisioning:**
```json
POST /api/meeting/provision
{
    "api_url": "https://cluster.meeting.ygsoft.fr/api",
    "device_key": "ABC123456789",
    "token_code": "secret_token"
}

Response:
{
    "success": true,
    "message": "Device provisionné avec succès !",
    "hostname": "ABC123456789",
    "tokens_left": 4,
    "rebooting": true
}
```

⚠️ **Note**: Après un provisioning réussi, le device **redémarre automatiquement** après 5 secondes pour appliquer le changement de hostname.

### 14.6 Champs de réponse Device Info

Après validation ou pour `/api/meeting/device`:

| Champ | Source API Meeting | Description |
|-------|-------------------|-------------|
| `name` | `product_serial` | Nom/numéro de série du produit |
| `ip` | `ip_address` | Adresse IP enregistrée |
| `note` | `note` | Description/note du device |
| `services` | `services` | Tableau de services (ex: `["ssh"]`) |
| `authorized` | `authorized` | Si le device est autorisé |
| `token_count` | `token_count` | Nombre de tokens disponibles |
| `online` | `availability.status` | Si le device est connecté |
| `last_seen` | `availability.last_heartbeat` | Dernier heartbeat reçu |

---

## 15) Sécurité

Le Web Manager exécute des commandes système (systemctl, nmcli, reboot) et peut tourner en root.

Recommandations:
- exposition LAN uniquement
- si exposition WAN: reverse proxy + auth + HTTPS + firewall
- sécuriser les fichiers contenant des secrets (`/etc/rpi-cam/onvif.conf`, `wifi_failover.json`)

---

## 16) Gestion Énergétique (Energy Management)

### 16.1 Objectif

Réduire la consommation d'énergie du Raspberry Pi 3B+/4/5 en désactivant les composants non essentiels pour le streaming RTSP.

**Contexte:** Un Pi 3B+ en mode streaming vidéo avec tous les composants consomme ~600-800 mA. En désactivant HDMI, audio et Bluetooth, la consommation peut descendre à ~500-550 mA.

### 16.2 Composants gérés

#### LEDs (PWR et ACT)
- **LED PWR (rouge):**
  - **Économies:** ~5 mA
  - **Utilité:** Indicateur d'alimentation, non essentiel en fonctionnement normal
  - **Paramètre boot:** `dtparam=pwr_led_trigger=none` + `dtparam=pwr_led_activelow=off`
- **LED ACT (verte):**
  - **Économies:** ~3 mA (moyenne, car clignote)
  - **Utilité:** Activité SD/CPU, utile pour debug mais pas indispensable
  - **Paramètre boot:** `dtparam=act_led_trigger=none` + `dtparam=act_led_activelow=off`

#### LED Ethernet (RJ45)
- **Contrôlabilité:** Dépend du modèle de Raspberry Pi
  - **Pi 3B/3B+ (smsc95xx/lan78xx):** **Non contrôlable** - LEDs gérées par le PHY hardware
  - **Pi 4B (bcmgenet):** Partiellement contrôlable selon le firmware
  - **Pi 5 (RP1):** Contrôlable via `/sys/class/leds/`
- **Économies potentielles:** ~5 mA (si contrôlable)
- **Interface web:** Affiche "Non supporté" sur Pi 3B/3B+ avec explication
- **Note technique:** Le Pi 3B utilise un contrôleur Ethernet USB (smsc95xx) qui intègre son propre PHY avec LEDs autonomes. Ces LEDs indiquent le lien (Link) et l'activité (Activity) directement au niveau hardware, sans intervention du système d'exploitation.

#### Bluetooth (dtoverlay=disable-bt)
- **Économies:** ~20 mA
- **Utilité:** Rarement utilisé dans un système de surveillance
- **Paramètre boot:** `dtoverlay=disable-bt` dans `/boot/firmware/config.txt`
- **Contrôle runtime:** Via systemd `bluetooth` service

#### HDMI (hdmi_blanking=2)
- **Économies:** ~40 mA
- **Utilité:** Non nécessaire en mode headless RTSP
- **Paramètre boot:** `hdmi_blanking=2` dans `/boot/firmware/config.txt`
  - Valeurs: `0`=allumé, `1`=blanking, `2`=off complet
- **Note:** Changement effectif au redémarrage (pas de contrôle runtime sur Pi 3B+)

#### Audio (dtparam=audio=off)
- **Économies:** ~10 mA
- **Utilité:** Optionnel si un micro USB est utilisé
- **Paramètre boot:** `dtparam=audio=off` dans `/boot/firmware/config.txt`
- **Contrôle ALSA:** Possible via `amixer` au runtime

#### WiFi Intégré (dtoverlay=disable-wifi)
- **Économies:** ~40 mA
- **Utilité:** Non nécessaire si Ethernet uniquement
- **Paramètre boot:** `dtoverlay=disable-wifi` dans `/boot/firmware/config.txt`
- **Attention:** Désactive complètement wlan0; pas de contrôle runtime
- **Conseil:** Ne pas désactiver si accès WiFi requis pour la maintenance

#### Fréquence CPU (underclocking)
- **Économies:** ~50-100 mA pour 600 MHz vs 1200 MHz
- **Performance:** Réduit les performances vidéo; recommandé pour applications légères
- **Outil:** `cpufreq-set` (nécessite `cpufrequtils`)
- **Commande:** `sudo cpufreq-set -f 600MHz` (600-1500 MHz sur Pi 3B+)

#### GPU Memory
- **Existing:** Déjà géré via interface web
- **Recommandé:** 64 Mo minimum pour RTSP, 128-256 Mo pour encodage H.264

### 16.3 Services Linux Optionnels

Ces services peuvent être désactivés pour économiser de l'énergie et de la RAM. Les changements sont immédiats (pas de redémarrage requis).

#### ModemManager
- **Économies:** ~15 mA + RAM
- **Utilité:** Gestion des modems 3G/4G/LTE
- **Conseil:** Désactiver si pas de modem cellulaire
- **Commande:** `sudo systemctl disable --now ModemManager.service`

#### Avahi (mDNS/Bonjour)
- **Économies:** ~5 mA
- **Utilité:** Découverte réseau automatique (Zeroconf/Bonjour)
- **Attention:** Peut affecter la découverte ONVIF
- **Commande:** `sudo systemctl disable --now avahi-daemon.service`

#### Cloud-Init (5 services)
- **Économies:** RAM uniquement + démarrage plus rapide
- **Utilité:** Provisioning pour environnements cloud (AWS, GCP, etc.)
- **Conseil:** Désactiver sur Raspberry Pi physique
- **Commandes:**
  ```bash
  sudo systemctl disable cloud-init-local.service
  sudo systemctl disable cloud-init-network.service
  sudo systemctl disable cloud-init-main.service
  sudo systemctl disable cloud-config.service
  sudo systemctl disable cloud-final.service
  ```

#### Console Série (serial-getty@ttyAMA0)
- **Économies:** ~2 mA
- **Utilité:** Console de debug sur port série GPIO
- **Conseil:** Désactiver si pas d'accès série
- **Commande:** `sudo systemctl disable serial-getty@ttyAMA0.service`

#### Console TTY1 (getty@tty1)
- **Économies:** ~2 mA
- **Utilité:** Login sur écran HDMI
- **Conseil:** Désactiver si mode headless
- **Commande:** `sudo systemctl disable getty@tty1.service`

#### UDisks2
- **Économies:** ~5 mA
- **Utilité:** Automontage des périphériques USB
- **Attention:** Désactiver uniquement si pas de clé USB à monter automatiquement
- **Commande:** `sudo systemctl disable --now udisks2.service`

### 16.4 Interface Web

**Onglet:** Système → Section "Gestion Énergétique & LEDs"

**Contrôles:**
- **LEDs:** Toggles pour LED PWR (~5 mA) et LED ACT (~3 mA)
- **Composants:** Bluetooth (~20 mA), WiFi (~40 mA), HDMI (~40 mA), Audio (~10 mA)
- **Services:** ModemManager, Avahi, Cloud-Init, Console Série, TTY1, UDisks2
- Affichage de l'état actuel (boot config pour hardware, systemctl pour services)
- Badges indiquant les économies par composant
- Estimation des économies totales en mA
- Bouton "Appliquer (redémarrage requis)" avec indicateur de modifications
- Confirmation de redémarrage après sauvegarde (uniquement pour changements hardware)

**API Endpoints:**
```
GET  /api/power/status           → État actuel + boot config + estimations
POST /api/power/apply-all        → Appliquer tous les paramètres d'un coup
POST /api/power/bluetooth        → Enable/disable Bluetooth
POST /api/power/hdmi             → Enable/disable HDMI
POST /api/power/audio            → Enable/disable Audio
POST /api/power/cpu-freq         → Définir fréquence CPU
GET  /api/power/boot-config      → Lire configuration boot
```

### 16.4 Script CLI Helper

**Emplacement:** `scripts/energy_manager.sh`

**Installation:**
```bash
sudo chmod +x scripts/energy_manager.sh
sudo ln -s /path/to/scripts/energy_manager.sh /usr/local/bin/energy-manager
```

**Utilisation:**
```bash
# Afficher le statut
sudo energy-manager status

# Estimation des économies
sudo energy-manager savings

# Gérer Bluetooth
sudo energy-manager bluetooth disable
sudo energy-manager bluetooth enable
sudo energy-manager bluetooth get

# Gérer HDMI
sudo energy-manager hdmi disable
sudo energy-manager hdmi enable

# Gérer Audio
sudo energy-manager audio disable
sudo energy-manager audio enable

# Définir fréquence CPU
sudo energy-manager cpu-freq 800

# Lire fréquence CPU actuelle
sudo energy-manager cpu-freq-get

# Configuration complète (ultra low power)
sudo energy-manager configure-power false false false
```

### 16.5 Profils d'énergie recommandés

#### 1) Mode Ultra Low Power (Surveillance passive)
```bash
energy-manager configure-power false false false
energy-manager cpu-freq 600
```
**Économies:** ~180 mA  
**Cas d'usage:** Caméra IP passive, enregistrement seul, peu de réaction temps réel  
**Drawback:** Encodage vidéo très limité (vérifier le débit RTSP)

#### 2) Mode Balanced (Défaut)
```bash
energy-manager configure-power true true false
# CPU par défaut
```
**Économies:** ~50 mA  
**Cas d'usage:** Streaming stable + compression vidéo standard

#### 3) Mode Haute Performance (Streaming haute définition)
```bash
energy-manager configure-power true true true
energy-manager cpu-freq 1200
```
**Économies:** Aucune (tous composants actifs, CPU max)  
**Cas d'usage:** Encodage H.264 temps réel, haute résolution

### 16.6 Configuration persistante

Toutes les modifications via l'interface web ou le script sont persistantes dans `/boot/firmware/config.txt`.

**Format des paramètres:**
```ini
# === Power Management (managed by web interface) ===
dtoverlay=disable-bt
hdmi_blanking=2
dtparam=audio=off
```

**Application au démarrage:** Automatique (grâce aux paramètres `dtparam` et `dtoverlay`)

**Redémarrage requis:** Oui, pour que les changements prennent effet au boot

### 16.7 Monitoring consommation

#### Mesures disponibles nativement

**Raspberry Pi 3B+/4:**
- **Voltage uniquement** via `vcgencmd`:
  ```bash
  vcgencmd measure_volts core   # Voltage cœur CPU
  vcgencmd measure_volts sdram_c # Voltage SDRAM controller
  vcgencmd measure_volts sdram_i # Voltage SDRAM I/O
  vcgencmd measure_volts sdram_p # Voltage SDRAM PHY
  ```
- **Throttling status** (indique si alimentation insuffisante):
  ```bash
  vcgencmd get_throttled
  # 0x0 = OK, bits set = problèmes (under-voltage, throttling, etc.)
  ```
- **Température** (indicateur indirect de consommation):
  ```bash
  vcgencmd measure_temp
  ```

**Raspberry Pi 5 uniquement:**
- Possède un PMIC avec capteur de courant intégré:
  ```bash
  cat /sys/class/hwmon/hwmon*/curr1_input  # Current (mA) - Pi 5 only
  ```

#### Mesure réelle de consommation

**Le Pi 3B+/4 n'a PAS de capteur de courant intégré.** Pour mesurer la consommation réelle, utiliser:

1. **Testeur USB / Wattmètre USB** (~10-15€)
   - Brancher entre le chargeur et le Pi
   - Affiche Voltage, Courant (mA), Puissance (W)
   - Exemples: PortaPow, Atorch, FNIRSI

2. **Module INA219/INA226** (~5-10€)
   - Capteur de courant I2C
   - Nécessite câblage et pilote:
     ```bash
     sudo modprobe ina219
     ```

3. **Comparaison avant/après**
   - Mesurer avec tous composants activés
   - Désactiver progressivement via interface web
   - Noter les différences

#### Valeurs typiques de consommation (Pi 3B+)

| Configuration | Consommation approx. |
|--------------|---------------------|
| Idle (tous composants actifs) | ~500-600 mA |
| Streaming RTSP (640x480@15fps) | ~600-800 mA |
| Avec HDMI désactivé | -40 mA |
| Avec Bluetooth désactivé | -20 mA |
| Avec WiFi désactivé | -40 mA |
| Avec Audio désactivé | -10 mA |
| Avec LEDs désactivées | -8 mA |
| Mode ultra low power | ~400-450 mA |

**Avec un testeur USB/multimètre:**
```bash
# Consommation instantanée (lit depuis `/sys/class/hwmon/`)
cat /sys/class/hwmon/hwmon0/in0_input  # Voltage (mV)
cat /sys/class/hwmon/hwmon0/curr0_input  # Current (mA) - Pi 5 only
```

**Note:** Le Pi 3B+ n'a pas de capteur de courant intégré; utiliser un testeur USB externe.

### 16.8 Limitations connues

**Pi 3B+ (Trixie):**
- `v4l2h264enc` (hardware encoding) **fonctionne** depuis v2.5.0 (CPU ~24% vs ~170%)
- Format pixel I420 requis (pas NV12) pour compatibilité avec jpegdec
- CPU underclocking peut être limité par le firmware (tester avec `cpufreq-set`)
- GPIO brightness (LED) possible mais pas de capteur de puissance interne

**Pi 4/5:**
- Plus de flexibilité; underclocking jusqu'à 600 MHz généralement stable
- Meilleure gestion thermique (possibilité de throttling si trop chaud)
- Sensible aux variations de qualité d'alimentation

### 16.9 Dépannage

**Changements ne prennent pas effet au redémarrage:**
- Vérifier `/boot/firmware/config.txt` pour les bonnes syntaxes
- Redémarrer avec `sudo reboot`
- Vérifier les droits d'accès du fichier config (doit être root-readable)

**Bluetooth ne démarre plus après modification:**
- Réinstaller le package: `sudo apt reinstall bluez`
- Ou editer manuellement `/boot/firmware/config.txt` et supprimer `dtoverlay=disable-bt`

**CPU underclocking avec CPU throttling:**
- Vérifier la température: `vcgencmd measure_temp`
- Ajouter un ventilateur si >70°C
- Relever la fréquence CPU minimale

---

## 16bis) Onglet DEBUG (Interface Web)

L'onglet Debug fournit des outils de maintenance avancés directement depuis l'interface web.

### 16bis.1 Fonctionnalités

#### Mise à jour Firmware Raspberry Pi
- **Pi 4/5 uniquement**: Utilise `rpi-eeprom-update` pour gérer le firmware EEPROM
- **Pi 3B/3B+**: Non supporté (firmware intégré au bootloader SD)
- Vérifie et applique les mises à jour du bootloader
- Nécessite un redémarrage après mise à jour
- **Dernière vérification** affichée sous le statut

#### apt update
- Rafraîchit les listes de paquets depuis les dépôts
- Affiche le nombre de sources vérifiées et mises à jour trouvées
- Ne modifie aucun paquet installé
- **Dernière exécution** affichée sous le statut

#### apt upgrade
- **Voir paquets**: Liste tous les paquets pouvant être mis à jour
- **Mettre à jour**: Installe toutes les mises à jour disponibles
- Utilise `DEBIAN_FRONTEND=noninteractive` pour éviter les prompts
- Timeout: 30 minutes maximum
- **Dernière exécution** affichée sous le statut

#### Scheduler APT (Mises à jour automatiques) - v2.30.49+
- **Toggle ON/OFF** pour activer/désactiver les mises à jour automatiques
- **apt update quotidien**: Configure l'heure d'exécution (défaut: 03:00)
- **apt upgrade hebdomadaire** (optionnel): Choix du jour de la semaine
- Crée automatiquement le fichier cron `/etc/cron.d/rpi-cam-apt-autoupdate`
- Logs disponibles dans `/var/log/rpi-cam/apt-autoupdate.log`
- Configuration persistante dans `/etc/rpi-cam/debug_state.json`

#### Redémarrage système
- Affiche l'uptime actuel du système
- Redémarre le Raspberry Pi avec confirmation
- Affiche un écran de reconnexion automatique

### 16bis.2 API REST Debug

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/debug/firmware/check` | GET | Vérifie les mises à jour firmware |
| `/api/debug/firmware/update` | POST | Applique la mise à jour firmware |
| `/api/debug/apt/update` | POST | Exécute apt update |
| `/api/debug/apt/upgradable` | GET | Liste les paquets à mettre à jour |
| `/api/debug/apt/upgrade` | POST | Exécute apt upgrade -y |
| `/api/debug/apt/scheduler` | GET | Récupère la config du scheduler |
| `/api/debug/apt/scheduler` | POST | Configure le scheduler auto-update |
| `/api/debug/last-actions` | GET | Récupère les dates de dernière action |
| `/api/debug/system/uptime` | GET | Retourne l'uptime système |

---

## 17) Outils de Débogage (debug_tools/)

Le dossier `debug_tools/` contient des outils pour faciliter le développement et les tests, utilisables par les humains ET les agents IA.

### 17.1 Prérequis Windows

Pour une connexion SSH automatique sans mot de passe interactif:
```powershell
wsl sudo apt install sshpass -y
```

### 17.2 Outils Windows (PowerShell)

#### `debug_tools_gui.ps1` - GUI Windows (debug_tools)
Interface graphique unique (Windows 10/11 x64) pour lancer les outils du dossier `debug_tools/`.
```powershell
.\debug_tools\debug_tools_gui.ps1
```
Inclut un assistant au démarrage (DeviceKey → IP via Meeting, sinon IP obligatoire), une mémoire locale des devices, et un onglet Update.

#### `config_tool.ps1` - Configuration globale (IA)
Outil pour modifier la configuration sur le device (config.env + JSON `/etc/rpi-cam`).
```powershell
.\debug_tools\config_tool.ps1 -Action list -File "/etc/rpi-cam/config.env"
.\debug_tools\config_tool.ps1 -Action set -File "/etc/rpi-cam/config.env" -Key "RTSP_PORT" -Value "8554"
.\debug_tools\config_tool.ps1 -Action get -File "/etc/rpi-cam/wifi_failover.json" -JsonPath "backup_ssid"
```

#### `run_remote.ps1` - Exécuter une commande distante
```powershell
# Commande simple
.\debug_tools\run_remote.ps1 "hostname"

# Commande sudo
.\debug_tools\run_remote.ps1 "sudo systemctl status rpi-cam-webmanager"

# Via WiFi (192.168.1.124)
.\debug_tools\run_remote.ps1 -Wifi "hostname"
```

#### `smoke_web_manager.ps1` - Smoke test Web Manager (device)
Script de non-regression pour verifier le demarrage du service et quelques routes clefs.
```powershell
# Smoke test par defaut (wlan1: 192.168.1.124)
.\debug_tools\smoke_web_manager.ps1

# IP/port personnalises
.\debug_tools\smoke_web_manager.ps1 -IP "192.168.1.124" -Port 5000

# Ne pas demarrer le service avant test
.\debug_tools\smoke_web_manager.ps1 -NoStart
```

#### `get_logs.ps1` - Boite à outils de déboggage (logs + diagnostics)
```powershell
# Logs (tous les services)
.\debug_tools\get_logs.ps1

# Logs d'un service
.\debug_tools\get_logs.ps1 -Service "rpi-cam-webmanager" -Lines 200

# Suivi temps réel
.\debug_tools\get_logs.ps1 -Service "rtsp-watchdog" -Follow

# Export ZIP logs + diagnostics
.\debug_tools\get_logs.ps1 -Tool collect -OutputDir "./logs_backup"

# Auto-détection IP via Meeting API (DeviceKey optionnelle)
.\debug_tools\get_logs.ps1 -Auto
.\debug_tools\get_logs.ps1 -Auto -DeviceKey "ABC123..." -Token "89915f"
```

#### `deploy_scp.ps1` - Déployer des fichiers
```powershell
# Fichier unique
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\app.py" -Dest "/opt/rpi-cam-webmanager/"

# Dossier entier
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\*" -Dest "/opt/rpi-cam-webmanager/" -Recursive

# Mode dry-run (test sans transfert)
.\debug_tools\deploy_scp.ps1 -Source ".\file.txt" -Dest "/tmp/" -DryRun
```

#### `update_device.ps1` - Mise à jour légère (v2.0.1)

Déploiement rapide sur un device déjà installé (24-30 secondes). **Ne réinstalle rien** - juste les mises à jour de code.

**Workflow simple 4 étapes:**
1. Arrêter les services systemd
2. Déployer les fichiers modifiés via SCP
3. Vérifier/installer requirements Python
4. Redémarrer les services

```powershell
# Mise à jour rapide via IP
.\debug_tools\update_device.ps1 -IP "192.168.1.202"

# Mise à jour via Meeting API (DeviceKey)
.\debug_tools\update_device.ps1 -DeviceKey "7F334701F08E904D796A83C6C26ADAF3"

# Aperçu des changements (dry-run, sans déploiement)
.\debug_tools\update_device.ps1 -IP "192.168.1.202" -DryRun

# Mise à jour sans redémarrer les services (test seulement)
.\debug_tools\update_device.ps1 -IP "192.168.1.202" -NoRestart

#### `package_update.ps1` - Packaging update local (v1.0.1)

Genere une archive update compatible avec "Update from file".

```powershell
.\debug_tools\package_update.ps1
.\debug_tools\package_update.ps1 -OutputDir ".\dist\updates"
.\debug_tools\package_update.ps1 -OverrideVersion "2.32.99"
.\debug_tools\package_update.ps1 -RequiredPackages "i2c-tools","util-linux-extra" -RequiresReboot
```
```

**Fichiers déployés:**
- `rpi_av_rtsp_recorder.sh` → `/usr/local/bin/`
- `rpi_csi_rtsp_server.py` → `/usr/local/bin/`
- `rtsp_recorder.sh` → `/usr/local/bin/`
- `rtsp_watchdog.sh` → `/usr/local/bin/`
- `VERSION` → `/opt/rpi-cam-webmanager/`
- `setup/` (complet) → `/opt/rpi-cam-webmanager/setup/`
- `onvif-server/` (complet) → `/opt/rpi-cam-webmanager/onvif-server/`
- `web-manager/` (complet) → `/opt/rpi-cam-webmanager/web-manager/`

**Configuration:**
- `/etc/rpi-cam/config.env` : **100% préservé** (aucune modification)
- Services : Redémarrés automatiquement après déploiement

**Durée estimée:** 24-30 secondes (vs 5-15 minutes avant)

**SSH Keepalive:** Supporte les longues opérations (ServerAliveInterval=60s)

#### `ssh_device.ps1` - Connexion SSH interactive
```powershell
# Session interactive
.\debug_tools\ssh_device.ps1

# Exécuter une commande
.\debug_tools\ssh_device.ps1 -Command "ls -la"
```

#### `Get-DeviceIP.ps1` - Récupérer l'IP via Meeting
Ce module est utilisé par `run_remote.ps1 -Auto`, `deploy_scp.ps1 -Auto` et `get_logs.ps1 -Auto`.

### 17.3 Outils Raspberry Pi (Bash)

#### `stop_services.sh` - Gestion des services
Permet d'arrêter/démarrer tous les services du projet, utile pour libérer la caméra lors de tests.

```bash
# Arrêter tous les services (libère la caméra)
sudo ./stop_services.sh

# Afficher le status des services et de la caméra
sudo ./stop_services.sh --status

# Redémarrer les services
sudo ./stop_services.sh --start

# Redémarrage complet
sudo ./stop_services.sh --restart
```

**Déploiement de l'outil sur le device:**
```powershell
.\debug_tools\deploy_scp.ps1 -Source ".\debug_tools\stop_services.sh" -Dest "/tmp/"
.\debug_tools\run_remote.ps1 "chmod +x /tmp/stop_services.sh"
```

### 17.4 Services gérés par stop_services.sh

| Service | Description |
|---------|-------------|
| `rpi-cam-webmanager.service` | Interface web Flask |
| `rpi-av-rtsp-recorder.service` | Serveur RTSP GStreamer |
| `rtsp-recorder.service` | Enregistrement ffmpeg |
| `rtsp-watchdog.service` | Watchdog haute disponibilité |
| `rpi-cam-onvif.service` | Serveur ONVIF |
| `rtsp-camera-recovery.service` | Récupération caméra USB |

### 17.5 Configuration des outils

Les outils utilisent ces paramètres par défaut (modifiables via arguments):
- **IP Ethernet (eth0):** 192.168.1.202
- **IP WiFi (wlan1):** 192.168.1.124
- **IP WiFi (wlan0):** 192.168.1.127
- **User:** device
- **Password:** meeting

**Meeting / auto-détection IP:**
- Les scripts supportant `-Auto` interrogent l'API Meeting (si configurée) pour récupérer l'IP actuelle du device, puis retombent sur les IPs connues.
- `get_logs.ps1` permet aussi de forcer la `DeviceKey` (et optionnellement `Token`/`ApiUrl`) directement en arguments.

---

## 18) Références internes

- Installation: `setup/install.sh`
- RTSP runtime: `rpi_av_rtsp_recorder.sh`
- Recorder: `rtsp_recorder.sh`
- Web Manager: `web-manager/app.py`
- ONVIF: `onvif-server/onvif_server.py`
- Debug tools: `debug_tools/README.md`
- Accélération Pi 3B+: `docs/hardware_acceleration_3B+.md`
- Benchmark maintenabilité: `docs/BENCHMARK_MAINTENABILITE.md`
- TODO: `docs/TODO.md`

---

## 19) Dérivé ESP32 (caméra only)

Ce dépôt contient aussi un dérivé **ESP32** dans `esp32/`, conçu pour:
- **ESP32-CAM avec PSRAM**
- capteur **OV2640** (support direct)
- capteur **OV5640** (prévu, pinout à confirmer)
- une **interface web légère** (sans audio, sans enregistrements)

### 19.1 Fonctionnement

- Serveur HTTP embarqué (Arduino) + UI statique (LittleFS)
- Streaming **MJPEG** sur `GET /stream`
- API JSON:
  - `GET /api/status` (IP, heap, PSRAM, capteur, réglages caméra)
  - `GET /api/config` / `POST /api/config` (WiFi + réglages caméra)
  - `GET /api/meeting/status` (config + état Meeting)
  - `POST /api/meeting/heartbeat` (heartbeat Meeting manuel)
  - `POST /api/reboot`
  - `POST /api/factory_reset` (efface le WiFi)

### 19.2 Build & flash (PlatformIO)

Dans `esp32/firmware/` :
- Build: `pio run`
- Upload firmware: `pio run -t upload`
- Upload Web UI (LittleFS): `pio run -t uploadfs`
- Monitor: `pio device monitor -b 115200`

### 19.3 WiFi (premier boot)

Si aucun SSID n’est configuré, l’ESP démarre en AP:
- SSID: `RTSP-Full-ESP32`
- Password: `rtsp-full`
- UI: `http://192.168.4.1/`

Pour activer le mode STA:
- Renseigner SSID + mot de passe dans l’UI
- Reboot (bouton “Reboot”)

### 19.4 OV5640 (à finaliser)

Le support OV5640 nécessite le mapping exact des GPIO.
Le template est dans `esp32/firmware/include/boards/ov5640_template.h`.

### 19.5 Meeting (ESP32)

Le heartbeat Meeting utilise l’endpoint:
- `POST /api/devices/{device_key}/online` (côté Meeting API)

Configuration côté ESP32 (UI onglet “Meeting” ou `POST /api/config`):
- `meeting.enabled` (bool)
- `meeting.api_url` (ex: `https://meeting.ygsoft.fr/api`)
- `meeting.device_key`
- `meeting.heartbeat_interval` (secondes)




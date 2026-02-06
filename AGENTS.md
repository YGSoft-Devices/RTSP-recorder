# AGENTS.md - Guide pour les Agents IA

Ce fichier contient les instructions et le contexte pour les agents IA travaillant sur ce projet.

---

## 📋 Informations du Projet

**Nom:** RTSP-Full  
**Description:** Système de streaming RTSP avec enregistrement, watchdog, ONVIF et interface web pour Raspberry Pi  
**Plateforme cible:** Raspberry Pi OS Trixie (64-bit) - Debian 13  
**Matériel testé:** Raspberry Pi 3B+

---

## 🎯 LES 3 FONDEMENTS DU PROJET (IMMUABLES)

Le projet RTSP-Full a été conçu et sera TOUJOURS conçu pour supporter ces 3 sources :

### 1. 📹 Caméras USB
- Support via **v4l2src** (GStreamer) ou **v4l2-ctl** (détection)
- Formats supportés : MJPEG (recommandé), YUYV, H264 natif
- Exemples : Microsoft LifeCam, Logitech C920, etc.

### 2. 📷 Caméras CSI (PiCam)
- Support via **libcamerasrc** (GStreamer) ou **rpicam-hello** (détection)
- Modules supportés : OV5647 (PiCam v1), IMX219 (PiCam v2), IMX708 (PiCam v3)
- Paquet requis : `gstreamer1.0-libcamera`

### 3. 🎤 Audio (Microphone USB)
- Support via **alsasrc** (GStreamer) ou **arecord** (détection)
- Encodage : AAC (voaacenc ou avenc_aac)
- Détection dynamique par nom (`AUDIO_DEVICE_NAME`) pour éviter les changements d'ID

**Ces 3 fondements doivent être testés et fonctionnels à chaque modification majeure.**

---

**PRIMORDIAL DURANT TOUT LE PROCESS !**
   - fichier docs/DOCUMENTATION_COMPLETE.md : doit maintenu en permanence. il doit contenir tout les informations sur le projet, de l'installation a l'utilisation, en passant par les fonctions et l'emplacement attendu de chaque fichier, les noms des services, ABSOLUMENT TOUT ! cela doit etre une vraie encyclopedie sans aucune zone d'ombres, et doit servir de réference principale, et detenir la vérité. Il ne doit jamais contenir d'erreurs ou d'informations obsoletes. 
   - toujours prendre en compte le fichier docs/DOCUMENTATION_COMPLETE.md avant toute reflexion.
   - toujours agir comme si un novice allait reinstaller le projet sur un nouvel appareil dans la seconde from scratch: les fichiers d'installations doivent etre constamment a jour, et doivent permettre egalement la mise a jour et le check.
   - les scripts obsoletes DOIVENT etre deplacés dans le dossier "backups" pour archivage. Garder la structure globale propre et coherente, prête à etre installée proprement.
   - PAS DE MONOLYTHE ! IL FAUT PENSER à LA MAINTENABILITé !
   - le projet devra rester au maximum universel sur le support des cameras (chaque device a une camera differente !) ainsi que sur la compatibilité entre pi3 et pi4. On ne fait pas de bugfix qui ne serait pas fonctionnel avec d'autre materiel, ou qui provoquerait des regressions.
   - Si une difficulté récurrente est reperée, conserver une trace de la solution dans AGENTS.md. Si cette difficulté concerne le deploiement, le conserver dans ce document "docs\Deployment_Workarounds.md", et le relire AVANT chaque deploiement.
   - si on rencontre une difficulté, on verifie que la réponse ne soit pas deja presente dans AGENTS.md.
   - toujours mettre a jour les numeros de versions, frontend inclus a chaque mise a jour.
   - toujours se faire un TODO.
   - on code en local, pas sur le device de test !
   - on evite les valeurs hardcodées.
   - on ne conserve pas du code legacy.
   - toujours deployer sur le device et tester.
   - si un bug est trouvé, on corrige le bug à la source, on ne contourne pas, on ne fait pas de modifications exceptionnelles sur le device.
   - il faut toujours s'assurer que les fichiers setups soient complets, et ne reimplemente pas des bugs deja corrigés. Tout doit toujours etre pret pour une installation propre, complete, et sans deboggage a faire derriere.
   - maintenir `web-manager/DEPENDENCIES.json` à jour (toutes les dependances APT requises)
   - Tout reglage possible ajouté au projet doit etre exposé sur le frontend. 
   - Le flux RTSP et la transmission audio/video doit toujours etre protegés d'un crash eventuel. Les services sur les devices doivent etre le moins coupés possibles.
   - a chaque mise a jour, utiliser debug_tools\package_update.ps1 pour generer un package.


## 🏗️ Structure du Projet de base (à garder a jour)
NOTE : App.py ayant été refactorisé, il est important de respecter sa nouvelle structure non monolythique.
Plus d'informations : docs\ARCHITECTURE_MODULAIRE.md

```
RTSP-Full/
├── README.md                         # Documentation principale
├── CHANGELOG.md                      # Historique des modifications
├── AGENTS.md                         # Ce fichier (instructions IA)
├── VERSION                           # Fichier de version centralisé (source unique)
├── rpi_av_rtsp_recorder.sh           # Script RTSP principal (v2.13.0) - Dispatcheur USB/CSI
├── rpi_csi_rtsp_server.py            # Serveur RTSP CSI natif (v1.4.14) - Picamera2 + GStreamer
├── rtsp_recorder.sh                  # Service d'enregistrement ffmpeg (v1.6.0)
├── rtsp_watchdog.sh                  # Watchdog haute disponibilité (v1.0.0)
├── onvif-server/                     # Serveur ONVIF
│   └── onvif_server.py               # Serveur ONVIF Python (v1.5.7)
├── web-manager/                      # Interface web Flask (ARCHITECTURE MODULAIRE v2.32.72)
│   ├── app.py                        # Orchestrateur Flask (~450 lignes)
│   ├── config.py                     # Configuration centralisée (v1.1.0, lit VERSION)
│   ├── tunnel_agent.py               # Agent tunnel inversé Meeting (v1.4.0)
│   ├── services/                     # Logique métier (11 modules)
│   │   ├── __init__.py               # Exports (v2.30.6)
│   │   ├── platform_service.py       # Détection plateforme (~210 lignes)
│   │   ├── config_service.py         # Gestion config/services
│   │   ├── camera_service.py         # Contrôles caméra - USB + CSI (~1000 lignes)
│   │   ├── csi_camera_service.py     # Contrôles CSI via Picamera2 (v1.0.0)
│   │   ├── i18n_service.py           # Internationalisation (v1.0.0) [NOUVEAU]
│   │   ├── network_service.py        # Réseau, WiFi (~793 lignes)
│   │   ├── power_service.py          # LED, GPU, HDMI (~700 lignes)
│   │   ├── recording_service.py      # Enregistrements (v2.30.2)
│   │   ├── media_cache_service.py    # Cache SQLite métadonnées/thumbnails (v1.0.1)
│   │   ├── meeting_service.py        # Meeting API (v2.30.18)
│   │   ├── system_service.py         # Diagnostics, mises à jour
│   │   └── watchdog_service.py       # RTSP/WiFi watchdog (~567 lignes)
│   ├── blueprints/                   # Routes HTTP (16 modules)
│   │   ├── __init__.py               # Exports
│   │   ├── config_bp.py              # /api/config, /api/service
│   │   ├── camera_bp.py              # /api/camera/*
│   │   ├── recordings_bp.py          # /api/recordings/*, /api/recordings/cache/* (v2.30.6)
│   │   ├── network_bp.py             # /api/network/*
│   │   ├── system_bp.py              # /api/system/* (v2.30.7)
│   │   ├── meeting_bp.py             # /api/meeting/* (v2.30.7)
│   │   ├── logs_bp.py                # /api/logs/*
│   │   ├── video_bp.py               # /api/video/*
│   │   ├── power_bp.py               # /api/leds/*, /api/power/*
│   │   ├── onvif_bp.py               # /api/onvif/*
│   │   ├── detect_bp.py              # /api/detect/*, /api/platform
│   │   ├── watchdog_bp.py            # /api/rtsp/watchdog/*
│   │   ├── wifi_bp.py                # /api/wifi/*
│   │   ├── i18n_bp.py                # /api/i18n/* (v1.0.0) [NOUVEAU]
│   │   ├── debug_bp.py               # /api/debug/*
│   │   └── legacy_bp.py              # Routes rétrocompatibilité
│   ├── templates/index.html          # Frontend HTML (v2.35.00)
│   ├── static/js/app.js              # JavaScript (v2.35.00)
│   ├── static/js/modules/i18n.js     # Module i18n (v2.35.00) [NOUVEAU]
│   ├── static/css/style.css          # Styles CSS (v2.35.00)
│   ├── static/locales/               # Fichiers de traduction [NOUVEAU]
│   │   ├── fr.json                   # Français (v2.35.00)
│   │   └── en.json                   # English (v2.35.00)
│   └── backup-app.py-backup          # Backup monolithique (8350 lignes)
├── esp32/                            # Dérivé ESP32 (caméra only, UI légère) (v0.1.0)
├── setup/                            # Scripts d'installation
│   ├── install.sh                    # Installation complète (v1.3.0)
│   ├── install_gstreamer_rtsp.sh     # GStreamer (v2.2.1)
│   ├── install_rpi_av_rtsp_recorder.sh
│   ├── install_rtsp_recorder.sh
│   ├── install_web_manager.sh
│   ├── install_rtsp_watchdog.sh      # Installation watchdog (v1.0.0)
│   ├── install_onvif_server.sh       # Installation ONVIF (v1.0.1)
│   ├── meeting-tunnel-agent.service  # Service tunnel Meeting (v1.0.0) [NOUVEAU]
│   ├── rtsp-watchdog.service         # Service systemd watchdog
│   ├── rtsp-camera-recovery.service  # Service récupération caméra
│   ├── rpi-cam-onvif.service         # Service systemd ONVIF
│   └── 99-rtsp-camera.rules          # Règles udev caméra
├── debug_tools/                      # Outils de débogage (v1.0.0)
│   ├── README.md                     # Documentation des outils
│   ├── install_device.ps1            # Installation complète automatique (Windows)
│   ├── install_device_gui.ps1        # GUI Windows pour install_device.ps1
│   ├── debug_tools_gui.ps1           # GUI Windows pour tous les outils
│   ├── run_remote.ps1                # Exécution commande distante (Windows)
│   ├── ssh_device.ps1                # Connexion SSH automatique (Windows)
│   ├── deploy_scp.ps1                # Déploiement SCP (Windows)
│   ├── Get-DeviceIP.ps1              # Auto-détection IP via Meeting API
│   ├── config_tool.ps1               # Modification config.env + JSON /etc/rpi-cam (IA)
│   └── stop_services.sh              # Arrêt/Démarrage services (Pi)
├── docs/                             # Documentation
└── backups/                          # Scripts obsolètes
```

---

## 🔧 Conventions de Code

### Bash Scripts
- Shebang: `#!/usr/bin/env bash`
- Options: `set -euo pipefail`
- Fonctions de log: `log()`, `log_err()`, `die()`
- Indentation: 2 espaces
- Variables: UPPER_CASE pour les constantes, lower_case pour les locales

### Python (Flask)
- Python 3.11+
- Type hints recommandés
- Docstrings pour les fonctions
- Indentation: 4 espaces

### JavaScript
- ES6+ (const, let, arrow functions)
- async/await pour les appels API
- Fonctions nommées (pas de variables anonymes)
- Indentation: 4 espaces

### CSS
- Variables CSS dans `:root`
- BEM-like naming pour les classes
- Commentaires de section avec `/* ===== Section ===== */`

---

## 🎯 Devices de Test


- **IP:** 192.168.1.202 en ethernet / 192.168.1.127 en WIFI wlan0 / 192.168.1.124 en WIFI wlan1
- **Login:** device
- **Password:** meeting
- **Caméra:** Microsoft LifeCam HD-5000 (USB, MJPEG)
- **Audio:** Microphone USB (`plughw:1,0` ou `plughw:2,0`)

2eme device de test FIXE : 
- **IP:** 192.168.1.4 en WIFI UNIQUEMENT.
- **Login:** device
- **Password:** meeting
- **Caméra:** CSI picam2
- **Audio:** Microphone USB (`plughw:1,0` ou `plughw:2,0`)

---

## 🤖 Outils pour Agents IA (debug_tools/)

**Prérequis Windows:** Installés automatiquement par `install_device.ps1` (WSL + sshpass)

### Installation automatique sur un device
```powershell
# Installation complète sur un Pi fraîchement flashé
.\debug_tools\install_device.ps1 192.168.1.124

# Installation avec provisionnement (définir hostname)
.\debug_tools\install_device.ps1 192.168.1.124 -Hostname "camera-salon"

# Installation complète avec Meeting API (RECOMMANDÉ)
.\debug_tools\install_device.ps1 192.168.1.124 -Hostname "camera-salon" -DeviceKey "ABC123..." -Token "89915f"

# Vérifier la connectivité uniquement
.\debug_tools\install_device.ps1 -IP 192.168.1.124 -CheckOnly

# Surveiller une installation en cours
.\debug_tools\install_device.ps1 -IP 192.168.1.124 -Monitor

# Sans provisionnement interactif
.\debug_tools\install_device.ps1 192.168.1.124 -NoProvision

# Sans reboot automatique à la fin
.\debug_tools\install_device.ps1 192.168.1.124 -NoReboot
```

**Fonctionnalités v1.3.0:**
- ✅ Auto-installation WSL + sshpass si manquants
- ✅ Provisionnement optionnel (hostname, timezone)
- ✅ **Configuration Meeting API automatique** (DeviceKey, Token)
- ✅ **Reboot automatique après installation** (avec -NoReboot pour désactiver)
- ✅ Temps écoulé affiché à chaque étape
- ✅ Détection automatique des phases d'installation
- ✅ Interface améliorée avec boîtes ASCII
- ✅ Attente et vérification de reconnexion après reboot

**Durée estimée:** 15-30 minutes sur Pi 3B+ fraîchement flashé (+ ~1 min pour reboot)

### Exécuter une commande sur le device (RECOMMANDÉ)
```powershell
.\debug_tools\run_remote.ps1 "commande à exécuter"

# Avec une IP personnalisée
.\debug_tools\run_remote.ps1 -IP "192.168.1.124" "commande à exécuter"
```

**Exemples:**
```powershell
# Status des services
.\debug_tools\run_remote.ps1 "systemctl is-active rpi-cam-webmanager rpi-av-rtsp-recorder"

# Voir les logs
.\debug_tools\run_remote.ps1 "sudo journalctl -u rpi-cam-webmanager -n 20"

# Redémarrer un service
.\debug_tools\run_remote.ps1 "sudo systemctl restart rpi-cam-webmanager"

# Utiliser l'IP WiFi
.\debug_tools\run_remote.ps1 -Wifi "hostname"

# Utiliser une IP personnalisée
.\debug_tools\run_remote.ps1 -IP "192.168.1.124" "hostname"
```

### Déployer des fichiers via SCP
```powershell
# Fichier unique
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\app.py" -Dest "/opt/rpi-cam-webmanager/"

# Dossier entier
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\*" -Dest "/opt/rpi-cam-webmanager/" -Recursive
```

### Arrêter les services pour tests caméra
```powershell
# Arrêter tous les services (libère la caméra)
.\debug_tools\run_remote.ps1 "sudo /tmp/stop_services.sh"

# Voir le status
.\debug_tools\run_remote.ps1 "sudo /tmp/stop_services.sh --status"

# Redémarrer les services
.\debug_tools\run_remote.ps1 "sudo /tmp/stop_services.sh --start"
```

**Note:** Déployer d'abord `stop_services.sh` sur le device:
```powershell
.\debug_tools\deploy_scp.ps1 -Source ".\debug_tools\stop_services.sh" -Dest "/tmp/"
.\debug_tools\run_remote.ps1 "chmod +x /tmp/stop_services.sh"
```

---

## ⚠️ Points d'Attention

### Fichiers Windows → Linux
- Toujours supprimer les BOM UTF-8: `sed -i '1s/^\xEF\xBB\xBF//' fichier`
- Convertir CRLF → LF: `sed -i 's/\r$//' fichier`

### Scheduler profils : thread sans try/except (CORRIGÉ v2.30.11)
- **Problème** : Le scheduler de profils caméra pouvait mourir silencieusement
- **Cause racine** : `profiles_scheduler_loop` n'avait aucun try/except. Toute exception (détection caméra, lecture fichier, application profil) tuait le thread définitivement
- **Symptôme** : Le scheduler activé ne change plus de profil, thread mort sans log d'erreur
- **Solution** : Wrap complet du corps de boucle en try/except, logging détaillé, sleep interruptible, délai initial 5s
- **Fichier** : `web-manager/services/camera_service.py` v2.30.11

### Failover WiFi n'applique pas l'IP statique sur interfaces déjà connectées (CORRIGÉ v2.30.17)
- **Problème** : Quand wlan1/wlan0 est déjà connecté via profil NM sauvegardé (DHCP), le failover retourne `wlan1_active`/`wlan0_active` SANS vérifier si l'IP correspond à la config statique de wifi_failover.json
- **Scénario** : Boot → wlan1 se connecte en DHCP (192.168.1.50) → failover voit "connecté + a une IP" → retourne sans appliquer l'IP statique configurée (192.168.1.4)
- **Solution** : Nouvelle fonction `_ensure_static_ip_on_interface(interface, current_ip)` appelée dans les code paths `wlan1_active` et `wlan0_active`
- **Fichier** : `web-manager/services/network_service.py` v2.30.17

### Failover inverse wlan0→wlan1 ne fonctionne pas (CORRIGÉ v2.30.18)
- **Problème** : Quand wlan1 tombe et wlan0 prend le relais, si wlan1 revient ensuite, il reste dormant et wlan0 reste actif
- **Cause racine** : Le failover déconnectait wlan0 AVANT de tenter de connecter wlan1 (`disconnect-then-connect`)
  - Si `connect_interface('wlan1')` échouait (SSID pas encore visible, scan en cours, timeout), wlan0 était déjà coupé
  - Le statut `wlan0_status` capturé avant la déconnexion devenait stale, masquant le problème
  - Au cycle suivant, wlan0 se reconnectait et le même schéma se répétait → wlan1 ne reprenait jamais la main
- **Solution** : Approche "make-before-break" (connect-then-disconnect)
  - Quand wlan1 est déjà actif avec IP → disconnect wlan0 immédiatement (safe)
  - Quand wlan1 doit être reconnecté → garder wlan0 actif pendant la tentative
  - Déconnecter wlan0 UNIQUEMENT après confirmation que wlan1 est connecté + a une IP
  - Si wlan1 échoue → wlan0 reste intact, zéro perte de connectivité
- **Fichier** : `web-manager/services/network_service.py` v2.30.18

### Configuration VIDEO_* non appliquée au démarrage RTSP (CORRIGÉ v2.15.2)
- **Problème** : Les paramètres vidéo de config.env (VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS) ignorés
- **Symptôme** : test-launch utilise toujours 640x480@15fps malgré config.env à 1280x720@30fps
- **Cause racine** : Dans `rpi_av_rtsp_recorder.sh`, les défauts étaient définis AVANT `source "$CONFIG_FILE"` :
  ```bash
  : "${VIDEOIN_FPS:=15}"               # Définit à 15
  : "${VIDEOIN_FPS:=${VIDEO_FPS:-15}}" # NE FAIT RIEN car déjà défini !
  # ... puis ...
  source "$CONFIG_FILE"  # Trop tard, VIDEOIN_* déjà fixés
  ```
- **Solution v2.15.2** : Déplacer `source "$CONFIG_FILE"` AVANT la définition des défauts
  ```bash
  source "$CONFIG_FILE"  # Charge VIDEO_WIDTH=1280, VIDEO_HEIGHT=720, VIDEO_FPS=30
  # PUIS appliquer les défauts avec fallback
  : "${VIDEOIN_WIDTH:=${VIDEO_WIDTH:-640}}"  # Prend VIDEO_WIDTH=1280 du config
  ```
- **Fichier** : [rpi_av_rtsp_recorder.sh](rpi_av_rtsp_recorder.sh) v2.15.2

### Saturation USB sur Pi 3B+ avec Audio (CORRIGÉ v2.7.0)
- **Problème** : Frame drops constants à 30fps avec audio + vidéo USB + Ethernet
- **Cause racine** : Le Pi 3B+ a un UNIQUE contrôleur USB 2.0 (480 Mbps) partagé par :
  - Ethernet (smsc95xx) - streaming RTSP sortant
  - Caméra USB (uvcvideo) - MJPEG 720p @ 30fps = ~20 MB/s entrant
  - Micro USB (snd-usb-audio) - 48kHz stereo = ~192 KB/s entrant
  - WiFi USB (si présent) - communication réseau
- **Symptôme** : `lost frames detected: count = 1` dans les logs GStreamer
- **Solution v2.7.0** :
  - Buffers optimisés : `alsasrc buffer-time=200000 latency-time=25000`
  - Queue vidéo : `queue max-size-buffers=3 leaky=downstream`
  - Préférer `voaacenc` à `avenc_aac` (plus léger)
  - `v4l2src io-mode=2 do-timestamp=true` (mmap + timestamps)
- **Recommandation Pi 3B+** : Limiter à **20 FPS** au lieu de 30 pour éviter la saturation USB
- **Note** : Le Pi 4/5 n'a pas ce problème (USB 3.0 séparé + Gigabit Ethernet natif)

### Récupération automatique erreurs ALSA (CORRIGÉ v1.1.0)
- **Problème** : Quand le bus USB se déconnecte temporairement, GStreamer entre en boucle d'erreurs ALSA
- **Symptôme** : `SNDRV_PCM_IOCTL_DELAY failed (-19): No such device` en boucle dans les logs
- **Cause** : Le hub USB Pi 3B+ se déconnecte sous charge, le device audio disparaît
- **Messages dmesg** : `FIQ timed out`, `FIQ reported NYET`, `ERROR::dwc_otg_hcd_urb_enqueue:502: Not connected`
- **Solution** : rtsp_watchdog.sh v1.1.0 détecte les erreurs ALSA en boucle et redémarre automatiquement
- **Paramètre** : `ALSA_ERROR_THRESHOLD=50` (redémarre si > 50 erreurs dans les 100 dernières lignes de logs)
- **Note** : Le watchdog tronque aussi les logs après restart pour éviter une re-détection immédiate

### Encodage Vidéo sur Pi 3B+ (CORRIGÉ!)
- **v4l2h264enc (hardware) FONCTIONNE pour USB !** (depuis v2.5.0)
- Le problème était un test bogué avec `videotestsrc` qui donne des faux négatifs
- **Solution** : vérifier `/dev/video11` + module `bcm2835_codec` au lieu de tester avec videotestsrc
- Format pixel : utiliser **I420** (pas NV12) quand la source est MJPEG via jpegdec
- Forcer `level=(string)4` dans les caps H.264 pour éviter les erreurs de négociation
- **Gain : CPU de 170% → 24% (-86%), Température de 81°C → 62°C**

### Encodage CSI/Picamera2 - v4l2h264enc INCOMPATIBLE ! (CORRIGÉ v1.0.3)
- **v4l2h264enc NE FONCTIONNE PAS avec Picamera2/libcamera !**
- **Cause** : v4l2h264enc attend des buffers V4L2, mais Picamera2 utilise libcamera (DMA direct)
- **Erreur** : `error with STREAMON 3 (No such process)` dans les logs GStreamer
- **Solution** : Utiliser **x264enc** (encodage software) pour CSI cameras
- **Pipeline CSI** : `appsrc ! x264enc tune=zerolatency speed-preset=ultrafast ! h264parse ! rtph264pay`
- **Performance Pi 3B+** : ~60-80% CPU à 1296x972@20fps (acceptable)

### Boucle H.264 CSI et throttling appsrc (CORRIGÉ v1.4.1)
- **Problème CRITIQUE** : Boucle `_push_loop()` dans `rpi_csi_rtsp_server.py` envoyait les buffers en continu SANS vérifier l'état du pipeline GStreamer
- **Symptômes** : CPU 64.9% au repos, GStreamer warnings (sticky event misordering), corruption mémoire (`g_hash_table_foreach` assertion)
- **Cause** : Quand clients se déconnectaient, le pipeline entrait en state NULL, mais la boucle continuait à envoyer vite en tight loop (30 buffers/sec) → accumulation de buffers sans consommateur → memory bloat + sync loss
- **Solution v1.4.1** : 
  1. Vérifier que `appsrc` existe + detect `NOT_LINKED` (pas de consommateur)
  2. Pause intelligente (0.5s) quand pas de clients (au lieu de boucle rapide)
  3. Throttle avec timing approprié entre frames (frame_duration_sec)
  4. Gérer les FlowReturn codes : `OK`, `NOT_LINKED`, `FLUSHING`, autres
  5. Counter `consecutive_failures` pour éviter busy-wait
- **Résultat** : CPU au repos = 0.9%, stream stable, NO erreurs GStreamer
- **ALL DEVICES avec CSI** : Vérifier que rpi_csi_rtsp_server.py ≥ v1.4.1

### Caméra USB MJPEG (LifeCam HD-5000)
- La caméra sort en MJPEG, pas en raw YUYV
- Pipeline optimal : `v4l2src ! image/jpeg ! jpegdec ! videoconvert ! video/x-raw,format=I420 ! v4l2h264enc`
- Le décodage JPEG (jpegdec) consomme du CPU mais moins que l'encodage software

### Audio sous systemd/root
- PulseAudio ne fonctionne pas → utiliser ALSA directement
- Préférer `alsasrc` à `pulsesrc`
- Périphérique: `plughw:X,0` (pas `hw:X,0`)

### Détection libcamera sur Trixie (CORRIGÉ v2.30.1)
- **Problème** : `has_libcamera: false` alors que libcamera est installé
- **Cause** : Sur Trixie, les outils s'appellent `rpicam-*` et non `libcamera-*`
- **Solution** : Vérifier les deux noms : `rpicam-hello` et `libcamera-hello`
- **Fichiers modifiés** : `platform_service.py`, `detect_bp.py`

### PipeWire bloque ALSA direct (CORRIGÉ v2.11.2)
- **Problème** : Sur certains systèmes (notamment Debian Trixie), PipeWire capture le device audio
- **Symptôme** : `Device 'plughw:0,0' is busy` dans les logs GStreamer
- **Cause** : PipeWire (pipewire, pipewire-pulse, wireplumber) démarre en session utilisateur
- **Solution** : Désactiver PipeWire pour l'utilisateur `device` :
  ```bash
  sudo -u device XDG_RUNTIME_DIR=/run/user/1000 systemctl --user mask pipewire pipewire.socket wireplumber pipewire-pulse pipewire-pulse.socket
  sudo -u device XDG_RUNTIME_DIR=/run/user/1000 systemctl --user stop pipewire pipewire.socket wireplumber pipewire-pulse pipewire-pulse.socket
  ```
- **Note** : Ajout de `timeout 3` sur `arecord --dump-hw-params` pour éviter les blocages

### test-launch (RTSP server)
- Ne supporte PAS les pipelines complexes (tee, splitmuxsink)
- Garder le pipeline simple: source → encode → rtppay
- L'enregistrement doit être fait séparément (ffmpeg)

### Bash background loops avec set -e (CORRIGÉ v1.4.1)
- **Problème** : Les sous-shells en background héritent de stdin et peuvent se bloquer
- **Solution** : Toujours ajouter `exec </dev/null` au début d'une boucle background
- **Problème 2** : `set -e` arrête le script si une comparaison `[[ ]]` retourne false
- **Solution** : Utiliser `if [[ ... ]]; then` au lieu de `[[ ... ]] && commande`
- **Solution 3** : Valider les nombres avec `[[ "$var" =~ ^[0-9]+$ ]] || var=0`

### Authentification RTSP avec Synology (CORRIGÉ v2.30.17)
- **Problème** : Synology Surveillance Station utilise Digest auth, pas Basic auth
- **Solution** : test-launch v2.1.0 supporte Digest + Basic auth (`RTSP_AUTH_METHOD=both`)
- **Problème 2** : Les credentials ONVIF et RTSP n'étaient pas synchronisés
- **Solution** : onvif_server.py v1.5.3 lit RTSP_USER/RTSP_PASSWORD depuis config.env
- **Note** : Après changement de mot de passe, supprimer et recréer la caméra dans Synology

### Audio dans les enregistrements (CORRIGÉ v1.6.0)
- **Problème** : ffmpeg avec `-c copy` ne capture pas correctement les métadonnées audio AAC du flux RTSP
- **Solution** : Ré-encoder l'audio en AAC (`-c:v copy -c:a aac -b:a 64k`)
- **Note** : Ajouter `-fflags +genpts` et `-analyzeduration 10000000` pour meilleure détection

### Gunicorn et threads background (CORRIGÉ v2.30.10)
- **Problème** : Le bloc `if __name__ == '__main__':` n'est **jamais exécuté** sous Gunicorn (import direct de app)
- **Solution** : Utiliser un hook `@app.before_request` avec un flag global `_background_tasks_started`
- **Note** : Chaque worker Gunicorn a ses propres threads (pas de mémoire partagée)
- **Important** : Stocker l'état partagé dans un fichier ou Redis, pas dans des variables Python

### Cache média SQLite (AJOUTÉ v2.30.18)
- **Problème** : ffprobe appelé à chaque listing de fichier = usure SD card + lenteur
- **Solution** : Cache SQLite dans `/var/cache/rpi-cam/media_cache.db`
- **Fonctionnement** :
  - Métadonnées extraites une seule fois puis cachées en DB
  - Worker background pour extraction asynchrone (ne bloque pas l'UI)
  - Thumbnails générés à la demande et cachés sur disque
  - Invalidation automatique quand fichier supprimé
- **Optimisation ffprobe** : `-read_intervals %+5` (ne lit que les 5 premières secondes)
- **Performance** : Réponse API <500ms au lieu de plusieurs secondes

### Watchdog et ffprobe avec auth Digest (CORRIGÉ v2.30.19)
- **Problème** : Enregistrements tronqués à ~90s au lieu de 300s configurés
- **Cause racine** : Le watchdog redémarrait le service RTSP toutes les ~90 secondes
- **Raison** : Le health check utilisait ffprobe pour tester le stream RTSP, mais ffprobe ne supporte pas l'auth Digest
- **Conséquence** : ffprobe échouait → 3 échecs (30s×3=90s) → restart automatique → ffmpeg ferme le fichier
- **Solution** : Remplacer ffprobe par une vérification port + processus :
  - `ss -tuln | grep :8554` - vérifie que le port est ouvert
  - `pgrep -f test-launch` - vérifie que le processus tourne
- **Résultat** : Enregistrements de 300s (~40 MB) comme configuré
- **Optimisation ffprobe** : `-read_intervals %+5` (ne lit que les 5 premières secondes)
- **Performance** : Réponse API <500ms au lieu de plusieurs secondes

### Artifacts RTSP CSI (NOUVEAU v2.32.36)
- **Problème** : Déformations vidéo périodiques ("ghosting") sur le stream RTSP CSI
- **Piste** : Ajuster l'encodeur H.264 (profil/quantizer) et keyframe interval
- **Solution** : Paramètres CSI dans `/etc/rpi-cam/config.env`
  - `H264_PROFILE=baseline|main|high`
  - `H264_QP=1..51` (quantizer fixe)
  - `H264_KEYINT` appliqué directement à `iperiod`

### Affichage GPU/NTP après refactor (CORRIGÉ v2.30.20)
- **Problème** : Mémoire GPU affiche 64 Mo au lieu de 256 Mo
- **Cause** : `get_gpu_mem()` retourne maintenant un dict, pas un int
- **Solution** : Modifier le template pour utiliser `gpu_mem.current`
- **Problème 2** : NTP affiche "Non synchronisé" même si synchronisé
- **Cause** : L'API retourne `ntp_synchronized` mais le JS utilise `synchronized`
- **Solution** : Ajouter les champs `synchronized`, `server`, `current_time` à l'API NTP

### Service rtsp-recorder non démarré après installation (CORRIGÉ v2.30.25)
- **Problème** : Enregistrements non créés malgré `RECORD_ENABLE=yes` dans la config
- **Cause** : Le script d'installation fait `systemctl enable` mais pas `systemctl start`
- **Solution** : Synchronisation automatique au démarrage du Web Manager
  - `config_service.py` : Nouvelle fonction `sync_recorder_service()`
  - `app.py` : Appel au démarrage dans `start_background_tasks()`
  - `config_bp.py` : Appel après sauvegarde de la config si `RECORD_ENABLE` change
- **Comportement** : Le service `rtsp-recorder` est maintenant automatiquement démarré/arrêté selon la valeur de `RECORD_ENABLE`

### Flask request.get_json() sans Content-Type header (CORRIGÉ v2.30.43)
- **Problème** : Erreur 500/415 "Unsupported Media Type" sur certains endpoints POST
- **Cause racine** : `request.get_json()` sans `silent=True` lève une exception si la requête n'a pas le header `Content-Type: application/json`
- **Exemple** : Le JS `stopAccessPoint()` faisait un `fetch(url, {method:'POST'})` sans body ni headers
- **Solution** : Remplacer tous les `request.get_json() or {}` par `request.get_json(silent=True) or {}`
- **Pattern correct** : `data = request.get_json(silent=True) or {}`
- **Pattern incorrect** : `data = request.get_json() or {}`
- **Note** : Avec `silent=True`, la méthode retourne `None` au lieu de lever une exception

### Configuration IP et NetworkManager (CORRIGÉ v2.30.44)
- **Problème** : Les interfaces WiFi perdaient leur IP après appel à apply_ip_config
- **Cause racine** : `configure_dhcp()` et `configure_static_ip()` utilisaient `ip addr flush` + `dhclient` directement
- **Conséquence** : NetworkManager perdait le contrôle des interfaces, les IPs étaient vidées
- **Solution** : Utiliser `nmcli` au lieu de commandes `ip` directes :
  - `nmcli con mod ... ipv4.method auto` pour DHCP
  - `nmcli con mod ... ipv4.method manual ipv4.addresses ...` pour IP statique
  - `nmcli device reapply` pour appliquer les changements
- **Important** : En mode DHCP, ne pas toucher aux interfaces - NetworkManager gère tout
- **IPs du device de test** : 192.168.1.202 (eth0), 192.168.1.124 (wlan1), 192.168.1.127 (wlan0)

### Network Failover avec plusieurs interfaces (CORRIGÉ v2.30.45)
- **Problème** : Les 3 interfaces (eth0, wlan0, wlan1) étaient toutes connectées simultanément
- **Cause racine** : `manage_wifi_based_on_ethernet()` ne gérait que wlan0, ignorait wlan1 complètement
- **Conséquence** : Pas de vrai failover, toutes les interfaces actives avec une IP
- **Solution** : Nouvelle fonction `manage_network_failover()` avec priorité stricte :
  - Ordre de priorité : eth0 > wlan1 > wlan0
  - **Une seule interface active à la fois**
  - Quand eth0 est connecté → wlan0 et wlan1 sont déconnectés
  - Quand eth0 tombe → wlan1 prend le relais (wlan0 reste off)
  - Quand eth0 et wlan1 sont down → wlan0 prend le relais
- **Configuration** :
  - `WIFI_MANUAL_OVERRIDE=yes` : Désactive le failover automatique (toutes interfaces actives)
  - `WIFI_MANUAL_OVERRIDE=no` : Active le failover (une seule interface)
  - `hardware_failover_enabled` dans `wifi_failover.json` : Contrôle le watchdog
- **Nouvelles fonctions** dans `network_service.py` :
  - `get_interface_connection_status()` : État détaillé d'une interface
  - `disconnect_interface()` : Déconnecte via nmcli
  - `connect_interface()` : Connecte via nmcli (crée profil WiFi si nécessaire)
  - `manage_network_failover()` : Logique de failover principale

### Démarrage auto des tâches de fond (CORRIGÉ v2.30.64)
- **Problème** : Quand le device bootait sans réseau, le failover WiFi ne s'activait jamais
- **Cause racine** : Les tâches de fond (meeting heartbeat, RTSP watchdog, WiFi failover) ne démarraient qu'à la première requête HTTP via `@app.before_request`
- **Conséquence** : Sans réseau = pas de requête HTTP = pas de failover = device inaccessible
- **Solution** : Thread `_delayed_startup()` dans app.py qui démarre les tâches 2 secondes après le boot
- **Note** : Le hook `before_request` est conservé comme fallback si le thread ne démarre pas

### Connexion WiFi automatique au backup SSID (CORRIGÉ v2.30.64)
- **Problème** : `connect_interface('wlan0')` échouait si aucun profil WiFi n'était sauvegardé
- **Cause** : `nmcli device connect wlan0` nécessite un profil de connexion existant
- **Solution** : `connect_interface()` utilise maintenant `backup_ssid` et `backup_password` de wifi_failover.json
- **Commande générée** : `nmcli device wifi connect <SSID> ifname wlan0 password <password>`
- **Configuration** : Ajouter `backup_ssid` et `backup_password` dans `/opt/rpi-cam-webmanager/wifi_failover.json`
- **Exemple wifi_failover.json** :
  ```json
  {
    "enabled": false,
    "hardware_failover_enabled": true,
    "backup_ssid": "MonReseau-2.4GHz",
    "backup_password": "motdepasse",
    "check_interval": 30
  }
  ```

### Sélecteur de résolution et FPS (CORRIGÉ v2.30.52)
- **Problème** : Le FPS configuré par l'utilisateur était écrasé au chargement de la page
- **Cause racine** : `onResolutionSelectChange()` dans app.js écrasait `VIDEO_FPS` avec le max FPS de la résolution
- **Conséquence** : L'utilisateur configure 30 FPS, recharge la page, le FPS passe à 20 (max de la résolution)
- **Solution** : Ajout du paramètre `userTriggered` à `onResolutionSelectChange()`
  - `false` (chargement page) : préserve la valeur sauvegardée si valide
  - `true` (changement manuel) : définit au max FPS de la résolution
  - Cap automatique si FPS > max résolution
- **Pattern correct** : `<select onchange="onResolutionSelectChange(true)">`

### Caméras CSI/PiCam et libcamera (CORRIGÉ v2.30.54)
- **Problème** : L'interface affichait des résolutions 16x16 @ 30fps pour les PiCam
- **Cause racine** : Les caméras CSI avec driver `unicam` retournent des tailles `Stepwise` via v4l2-ctl
  - v4l2-ctl montre : `Size: Stepwise 16x16 - 16376x16376 with step 1/1`
  - Ce ne sont pas des résolutions discrètes valides, mais des plages continues
- **Diagnostic** : `vcgencmd get_camera` retourne `supported=0 detected=0` = problème hardware
  - Si la caméra est détectée par libcamera mais pas vcgencmd, c'est normal sur les systèmes modernes
- **Solution** : 
  - Nouvelle fonction `detect_camera_type()` : Détecte USB vs CSI/libcamera
  - Nouvelle fonction `get_libcamera_formats()` : Parse `rpicam-hello --list-cameras`
  - `get_camera_formats()` dispatch automatiquement selon le type
- **Types de caméras supportés** :
  - `usb` : Caméras USB (LifeCam, Logitech, etc.) → v4l2-ctl
  - `libcamera` / `csi` : PiCam v1/v2/v3, modules CSI → rpicam-hello
- **Note** : Le streaming RTSP pour PiCam nécessite une adaptation du pipeline GStreamer (pas encore fait)

### Détection SSID WiFi actif (CORRIGÉ v2.30.66)
- **Problème** : La page réseau affichait `active_ssid: null` même quand connecté via wlan1
- **Cause racine** : `get_current_wifi()` utilisait `iw` (non installé sur Trixie) et ne vérifiait que wlan0
- **Solution** : Réécriture complète de `get_current_wifi()` pour utiliser `nmcli`
  - Sans paramètre : vérifie toutes les interfaces WiFi
  - Avec paramètre : vérifie une interface spécifique
  - Retourne l'interface, le SSID, et autres infos

### Indicateur mot de passe WiFi (CORRIGÉ v2.30.66)
- **Problème** : "Aucun mot de passe" affiché pour le réseau principal même s'il est connecté
- **Cause** : Seul `wifi_failover.json` était vérifié pour les mots de passe
- **Solution** : Vérification additionnelle des profils NetworkManager
  - Si le SSID a un profil NM sauvegardé (ex: configuré via RPi Imager), `has_primary_password=true`
  - Commande : `nmcli -t -f NAME,TYPE connection show`

### Contrôles CSI Camera (Tuning) non persistants (CORRIGÉ v1.4.0)
- **Problème** : Les contrôles Saturation, Brightness, AnalogueGain sauvegardés dans `/etc/rpi-cam/csi_tuning.json` n'étaient pas appliqués au redémarrage du serveur
- **Symptôme** : API retourne `Saturation: 1.0` même si le fichier tuning contient `Saturation: 0.89`
- **Cause racine** : Deux problèmes combinés :
  1. `picam2.set_controls()` était appelé AVANT `picam2.start()` (ne fonctionne que dans streaming mode)
  2. `list_controls()` utilisait `capture_metadata()` qui retourne les valeurs des frames réelles, pas les contrôles appliqués
- **Solution** : 
  - Appliquer les tunings APRÈS `picam2.start()` pour que les contrôles prennent effet (v1.3.0)
  - Tracker les contrôles appliqués dans `self.applied_controls` (dict)
  - `list_controls()` retourne les valeurs de `applied_controls` au lieu de `metadata` (v1.4.0)
- **Résultat** : Les contrôles sont maintenant correctement persistants :
  - Sauvegardés dans `/etc/rpi-cam/csi_tuning.json` lors du changement
  - Chargés et appliqués au démarrage du serveur CSI
  - API retourne les bonnes valeurs via `applied_controls` tracking
- **Test** : Saturation/Brightness/AnalogueGain values match after server restart

---

## 📝 Processus de Modification

1. **Avant toute modification:**
   - Lire ce fichier AGENTS.md
   - Vérifier le CHANGELOG.md
   - Comprendre la structure existante

2. **Pendant la modification:**
   - Incrémenter la version du fichier modifié
   - Tester sur le device si possible
   - en cas de test, penser a mettre un timeout pour eviter de rester bloqué.
   - Gérer les BOM/CRLF Windows

3. **Après la modification:**
   - Mettre à jour CHANGELOG.md SANS METTRE DE DATES
   - Mettre à jour la version dans ce fichier si la structure change
   - Déployer et tester sur le device


---

## 🔄 Versioning des Fichiers

| Fichier | Version Actuelle |
|---------|------------------|
| VERSION | 2.36.16 (source unique) |
| rpi_av_rtsp_recorder.sh | 2.15.2 |
| rtsp_recorder.sh | 1.8.0 |
| rtsp_watchdog.sh | 1.2.0 |
| onvif-server/onvif_server.py | 1.9.0 |
| rpi_csi_rtsp_server.py | 1.4.14 |
| web-manager/app.py | 2.36.14 |
| web-manager/config.py | 1.2.3 |
| web-manager/tunnel_agent.py | 1.4.2 |
| esp32/firmware (PlatformIO) | 0.1.2 |
| web-manager/services/camera_service.py | 2.30.11 |
| web-manager/services/csi_camera_service.py | 1.2.0 |
| web-manager/services/i18n_service.py | 1.1.0 |
| web-manager/services/media_cache_service.py | 1.0.1 |
| web-manager/services/meeting_service.py | 2.30.23 |
| web-manager/services/recording_service.py | 2.30.2 |
| web-manager/services/system_service.py | 2.30.25 |
| web-manager/services/watchdog_service.py | 2.30.7 |
| web-manager/services/__init__.py | 2.30.9 |
| web-manager/services/config_service.py | 2.31.0 |
| web-manager/services/network_service.py | 2.30.18 |
| web-manager/services/power_service.py | 2.30.7 |
| web-manager/services/platform_service.py | 2.30.1 |
| web-manager/services/*.py (autres) | 2.30.3 |
| web-manager/blueprints/camera_bp.py | 2.30.11 |
| web-manager/blueprints/config_bp.py | 2.30.1 |
| web-manager/blueprints/detect_bp.py | 2.30.1 |
| web-manager/blueprints/i18n_bp.py | 1.0.0 |
| web-manager/blueprints/meeting_bp.py | 2.30.12 |
| web-manager/blueprints/network_bp.py | 2.30.8 |
| web-manager/blueprints/power_bp.py | 2.30.4 |
| web-manager/blueprints/recordings_bp.py | 2.30.7 |
| web-manager/blueprints/system_bp.py | 2.30.12 |
| web-manager/blueprints/logs_bp.py | 2.30.6 |
| web-manager/blueprints/wifi_bp.py | 2.30.8 |
| web-manager/blueprints/debug_bp.py | 2.30.9 |
| web-manager/blueprints/legacy_bp.py | 2.30.2 |
| web-manager/blueprints/*.py (autres) | 2.30.5 |
| web-manager/templates/index.html | 2.36.16 |
| web-manager/static/js/app.js | 2.36.08 |
| web-manager/static/js/modules/config_video.js | 2.36.03 |
| web-manager/static/js/modules/meeting.js | 2.36.08 |
| web-manager/static/js/modules/i18n.js | 2.36.15 |
| web-manager/static/css/style.css | 2.35.03 |
| web-manager/static/locales/fr.json | 2.36.16 |
| web-manager/static/locales/en.json | 2.36.16 |
| setup/install.sh | 1.3.0 |
| setup/install_gstreamer_rtsp.sh | 2.2.5 |
| setup/test-launch.c | 2.2.0 |
| setup/install_rpi_av_rtsp_recorder.sh | 2.0.2 |
| setup/install_rtsp_recorder.sh | 1.0.0 |
| setup/install_web_manager.sh | 2.4.3 |
| setup/meeting-tunnel-agent.service | 1.0.0 |
| setup/install_onvif_server.sh | 1.0.1 |
| setup/install_rtsp_watchdog.sh | 1.0.0 |
| debug_tools/install_device.ps1 | 1.4.4 |
| debug_tools/install_device_gui.ps1 | 1.4.0 |
| debug_tools/run_remote.ps1 | 1.3.1 |
| debug_tools/update_device.ps1 | 2.0.8 |
| debug_tools/ssh_device.ps1 | 1.0.0 |
| debug_tools/deploy_scp.ps1 | 1.4.7 |
| debug_tools/Get-DeviceIP.ps1 | 1.0.0 |
| debug_tools/stop_services.sh | 1.0.0 |
| docs/DOCUMENTATION_COMPLETE.md | 2.36.15 |
| debug_tools/package_update.ps1 | 1.0.1 |


---

## 🌐 APIs Externes

### Meeting API (intégration locale)
- Base URL: configurable via `MEETING_API_URL`
- Authentification: `X-Token-Code` header
- Endpoints principaux:
  - `POST /api/devices/{device_key}/online` - Heartbeat
  - `GET /api/devices/{device_key}` - Device info
  - `GET /api/devices/{device_key}/availability` - Status
  - `POST /api/devices/{device_key}/service` - Request tunnel

### Camera Profiles API (Locale)
- `GET /api/camera/profiles` - Liste des profils
- `PUT /api/camera/profiles/{name}` - Créer/modifier un profil
- `DELETE /api/camera/profiles/{name}` - Supprimer un profil
- `POST /api/camera/profiles/{name}/apply` - Appliquer un profil
- `POST /api/camera/profiles/{name}/capture` - Capturer réglages actuels
- `POST /api/camera/oneshot-focus` - Focus ponctuel
- `GET /api/camera/all-controls` - Tous les contrôles v4l2

### Network API (Locale)
- `GET /api/network/interfaces` - Liste interfaces réseau (inclut `priority[]` et `connected` boolean)
- `GET /api/network/config` - Configuration complète
- `POST /api/network/priority` - Priorité des interfaces
- `POST /api/network/static` - IP statique
- `POST /api/network/dhcp` - DHCP

### Recordings API (Locale)
- `GET /api/recordings` - Liste basique
- `GET /api/recordings/list?page=1&per_page=20&filter=all&sort=date-desc&search=` - Liste paginée

### System API (Locale)
- `GET /api/system/info` - Informations système complètes
- `GET /api/system/ntp` - Status NTP
- `POST /api/system/ntp` - Configuration NTP
- `POST /api/system/ntp/sync` - Force sync NTP
- `GET /api/system/update/check` - Vérifie mises à jour
- `POST /api/system/update/perform` - Applique mise à jour

### Logs API (Locale)
- `GET /api/logs?lines=100&source=all` - Logs récents
- `GET /api/logs/stream` - Streaming SSE logs en temps réel
- `POST /api/logs/clean` - Nettoyer les fichiers de logs serveur

---

## 🐛 Bugs Trouvés et Corrigés (Installation Tests - 20/01/2026)

### Bug: Directory Deployments Failing in Update Tool (CORRIGÉ v1.4.1 + v2.0.2) - PRODUCTION FIX
- **Symptôme**: Lors de l'exécution de `update_device.ps1`, erreurs "cannot stat '/tmp/...' : No such file or directory" pour les dossiers (`setup/`, `onvif-server/`, `web-manager/`)
- **Cause racine (deploy_scp.ps1 v1.4.0)** : 
  - File collection capturait SEULEMENT le nom du fichier: `$_.Name` au lieu du chemin complet
  - Quand `setup/50-policy-routing` était collecté, SCP mettait le fichier à `/tmp/50-policy-routing` (correct)
  - Mais la commande copy supposait un fichier unique: `sudo cp /tmp/50-policy-routing $dest` (FAUX - 50-policy-routing était dans `/tmp/setup/` réellement)
  - Résultat: Tous les fichiers d'un dossier atterrissaient à `/tmp/` au lieu de `/tmp/setup/` → cp échouait
- **Cause racine (update_device.ps1 v2.0.1)** :
  - Entrées dossier avaient des slashes de fin (`setup/`, `web-manager/`) → Join-Path fallait
  - Pas de vérification robuste que `Get-Item` sur les chemins avec slashes
  - Ne passait pas le flag `-Recursive` à deploy_scp.ps1 pour les dossiers
- **Impact**: CRITIQUE - Déploiements de mise à jour échouaient complètement pour les dossiers (50% des fichiers du projet)
- **Fix v1.4.1 (deploy_scp.ps1)** :
  - FileMapping dictionary pour tracker les chemins complets: `$FileMapping[$_.FullName] = $RelativePath`
  - Copy command: `sudo cp -r /tmp/FolderName $dest` avec flag `-r` pour recursive
  - Affichage résultat: montre "Dossier: setup" au lieu d'une liste de fichiers
- **Fix v2.0.2 (update_device.ps1)** :
  - Normalisation: `$fileNormalized = $file.TrimEnd('/', '\')`
  - Get-Item robuste: `Get-Item -LiteralPath $fullPath`
  - Source directory: `"$fullPath\"` avec trailing backslash
  - Passing `-Recursive` flag: `& $deployScp ... -Recursive` quand `$isDirectory = $true`
- **Résultat**: Tous les 8 targets de deployment (fichiers + dossiers) fonctionnent parfaitement
  - ✅ Testé sur device 192.168.1.202 - deployment complet en ~17 secondes, zéro erreurs
  - ✅ Services redémarrés correctement après deployment
  - ✅ Web API responding après deployment
- **Fichiers** : 
  - [debug_tools/deploy_scp.ps1](debug_tools/deploy_scp.ps1) v1.4.1
  - [debug_tools/update_device.ps1](debug_tools/update_device.ps1) v2.0.2
- **Note**: Tool is now "PARFAIT" (production-ready) pour tous deployments

### Bug: JSON mal formé dans meeting.json (CORRIGÉ v1.4.1)
- **Symptôme**: `Error loading meeting config from JSON: Expecting property name enclosed in double quotes`
- **Cause racine** : PowerShell `install_device.ps1` ligne 515 échappe les guillemets avant envoi à bash
- **Résultat** : Fichier contient `\"enabled\"` au lieu de `"enabled"`
- **Impact** : Avertissement au démarrage, fallback sur config.env, heartbeat retardé
- **Fix** : Utilisation de heredoc bash (`<<EOF`) au lieu de `echo` + echappement
- **Fichier** : [debug_tools/install_device.ps1](debug_tools/install_device.ps1) v1.4.1

### Bug: RECORD_ENABLE non défini (CORRIGÉ v1.4.1 + v2.4.1)
- **Symptôme** : Service `rtsp-recorder` inactif après installation, pas d'enregistrements
- **Cause racine** : Variable `RECORD_ENABLE` absente du config.env, défaut système = "no"
- **Résultat** : `sync_recorder_service()` arrête le service automatiquement au démarrage
- **Impact** : Critique - enregistrements bloqués par défaut, utilisateur n'en a pas
- **Fix** : Ajout de `RECORD_ENABLE=yes` dans les templates config.env
- **Fichiers** : 
  - [debug_tools/install_device.ps1](debug_tools/install_device.ps1) v1.4.1
  - [setup/install_web_manager.sh](setup/install_web_manager.sh) v2.4.1

### Bug: Boucle H.264 CSI tight CPU spin + GStreamer crash (CORRIGÉ v1.4.1)
- **Symptôme** : Device CSI perd le stream RTSP, CPU à 64.9% au repos, erreurs GStreamer
  ```
  GStreamer-WARNING: Sticky event misordering, got 'segment' before 'caps'
  g_hash_table_foreach: assertion 'version == hash_table->version' failed
  ```
- **Cause racine** : Boucle `_push_loop()` dans [rpi_csi_rtsp_server.py](rpi_csi_rtsp_server.py) **envoyait les buffers en continu SANS pause**
  - Quand client se déconnecte, pipeline retourne à state NULL
  - Boucle continue à envoyer 30 buffers/sec en tight loop sans vérifier appsrc
  - Buffers s'accumulent sans consommateur → corruption mémoire GStreamer
  - Audio/vidéo se désynchronisent (sticky event ordering)
- **Résultat** : Stream bloqué, impossible de reconnecter, CPU waste
- **Impact** : CRITIQUE - Affecte TOUS les devices avec caméra CSI (Picamera2 native)
- **Fix v1.4.1** : Complète réécriture de la boucle `_push_loop()` avec:
  1. Vérification que appsrc existe + pipeline a des consommateurs (detect `NOT_LINKED`)
  2. **Pause intelligente** : sleep 0.5s quand pas de clients (au lieu de 30 boucles/sec)
  3. Throttle frame timing avec sleep approprié entre pushes
  4. Gérer tous les FlowReturn codes : `OK` → continue, `NOT_LINKED` → pause, `FLUSHING` → normal, autre → backoff
  5. Counter `consecutive_failures` pour éviter tight loop
- **Résultat après fix** : CPU au repos = **0.9%** (était 64.9%), NO GStreamer warnings, stream stable
- **Test** : Device 192.168.1.4 après déploiement v1.4.1 ✅ CPU 0.9%, ffprobe se connecte OK
- **Fichier** : [rpi_csi_rtsp_server.py](rpi_csi_rtsp_server.py) v1.4.1

### Bug: Watchdog watchdog ne détectait pas les crashes (CORRIGÉ v1.4.3)
- **Symptôme**: Service crashe avec `exit code 120` toutes les 1-2 minutes malgré les fixes précédents
- **Cause racine** : Logique de watchdog incorrecte - comparait `current_frame_timestamp == last_check_frame_time` mais calculait TOUJOURS `time.time() - current_frame_timestamp`
  - Résultat : Quand aucun frame n'était poussé (pas de changement de timestamp), le calcul d'elapsed explosait après quelques secondes
  - Le watchdog croyait que le push loop était dead alors qu'il poussait réellement des frames
- **Impact** : CRITIQUE - Faux positifs causaient des redémarrages systématiques du service
- **Fix v1.4.3** :
  1. Comparer correctement les timestamps : `if current_frame_timestamp == last_frame_timestamp`
  2. Calculer elapsed SEULEMENT si pas de changement : `elapsed_since_frame = time.time() - current_frame_timestamp`
  3. Update `last_frame_timestamp` après chaque vérification pour la prochaine itération
  4. Ajouter debug log pour montrer que le push loop est actif
- **Résultat** : Service stable, NO faux positifs, watchdog fonctionne correctement
- **Test** : Device 192.168.1.4 après v1.4.3 ✅ Stable pendant 10+ secondes, ffprobe stream OK, watchdog logs corrects
- **Fichier** : [rpi_csi_rtsp_server.py](rpi_csi_rtsp_server.py) v1.4.3

### Bug: Meeting heartbeat ne démarre jamais sur devices sans provisionnement (CORRIGÉ v2.30.13)
- **Symptôme**: Device CSI (192.168.1.4) n'envoie pas de heartbeat à Meeting API depuis 20h+ malgré accès réseau local
- **Cause racine** : `load_meeting_config()` retournait `enabled=False` par défaut quand config.env/meeting.json vides
  - Résultat : `meeting_heartbeat_loop()` ne faisait RIEN (`if config.get('enabled')` → False → skip heartbeat)
  - Heartbeat thread était lancé mais inactif = zombie thread
- **Impact** : CRITIQUE - Tous les devices sans clé Meeting provisionnée ne remontaient jamais en ligne
- **Fix v2.30.13 (PÉRENNE)** :
  1. `enabled=True` par défaut (heartbeat démarre TOUJOURS)
  2. `api_url='https://api.meeting.co'` par défaut si vide
  3. Auto-génération device_key depuis hostname+MAC si absent: `{hostname}-{mac:012x}`
  4. Graceful fallback à UUID si hostname échoue
- **Résultat** : Heartbeat démarre automatiquement même sans provisionnement
- **Test** : Device 192.168.1.4 ✅ Heartbeat thread started, device_key auto-généré (`3316A52EB08837267BF6BD3E2B2E8DC7`), essaie de se connecter
- **Note** : DNS errors après = problème réseau (pas accès internet du device), pas bug application
- **Fichier** : [web-manager/services/meeting_service.py](web-manager/services/meeting_service.py) v2.30.13

### Bug: Configuration réseau unifiée non persistante (CORRIGÉ v2.30.8)
- **Symptôme**: Device CSI 192.168.1.4 perd sa config IP/gateway après redémarrage/failover, routing cassé (`default via 192.168.1.4` au lieu de `.254`)
- **Cause racine** : Disjonction entre deux flux de configuration:
  - Frontend section "Configuration Réseau" (simple) → appelle `/api/network/static` ou `/api/network/dhcp`
  - Frontend section "WiFi Failover" → appelle `/api/wifi/failover/config` → sauvegarde dans `wifi_failover.json`
  - MAIS les endpoints `/api/network/static` et `/api/network/dhcp` appliquaient via NetworkManager SANS sauvegarder dans `wifi_failover.json`
- **Scénario** :
  1. Utilisateur configure via frontend : IP=192.168.1.4/24, gateway=192.168.1.254, DNS=8.8.8.8
  2. Endpoint `/api/network/static` applique via `nmcli con mod` → NetworkManager route correcte appliquée (192.168.1.254)
  3. **MAIS** ce n'est pas sauvegardé dans `wifi_failover.json` (ancien fichier contient gateway=192.168.1.4)
  4. Redémarrage service ou failover watchdog démarre → charge `wifi_failover.json` (ancien)
  5. Applique la vieille config avec gateway=192.168.1.4 via `_apply_static_ip_to_interface()`
  6. Routing revient à FAUX : `default via 192.168.1.4` (lui-même!) → Trafic local, pas d'Internet
  7. DNS resolution échoue → Heartbeat Meeting API ne peut pas résoudre `meeting.ygsoft.fr` → Offline
- **Impact** : CRITIQUE - Affecte TOUS les devices avec failover WiFi (pratiquement tout ce qui a 2+ interfaces WiFi)
- **Fix v2.30.8** :
  1. Endpoint `/api/network/static` maintenant sauvegarde aussi dans `wifi_failover.json`:
     - Extract IP et netmask : "192.168.1.4/24" → static_ip, gateway, dns, ip_mode='static'
     - Merge with existing failover config + save
  2. Endpoint `/api/network/dhcp` maintenant sauvegarde aussi : ip_mode='dhcp'
  3. Synchronized config persistence across both UI flows
- **Device 192.168.1.4 Fix** :
  1. Corrigé `wifi_failover.json` : gateway 192.168.1.4 → 192.168.1.254
  2. Appliqué route manuellement : `sudo ip route add default via 192.168.1.254 dev wlan0 metric 600`
  3. Redémarré rpi-cam-webmanager
- **Résultat** : 
  - Network config persists across reboots/failover events
  - Internet connectivity restored (ping 8.8.8.8 100% success)
  - Meeting heartbeat now sending successfully
  - Device API shows: connected=true, last_error=null, last_heartbeat=current
- **Test** : Device 192.168.1.4 ✅ connected=true, last_heartbeat="2026-01-21T00:28:46" (27s ago), ip_address="192.168.1.4", last_seen="2026-01-21 00:28:45"
- **Fichier** : [web-manager/blueprints/network_bp.py](web-manager/blueprints/network_bp.py) v2.30.8

### Bug: Configuration Meeting perdue lors des mises à jour de profils (CORRIGÉ v2.30.14)
- **Symptôme**: Device CSI provisionné avec clés Meeting a perdu sa config après mise à jour scheduler/profils
- **Cause racine** : `save_config()` écrivait SEULEMENT les keys du dict passé, oubliant tous les autres
  - Exemple : Scheduler appelait `save_config({'CAMERA_PROFILES_ENABLED': 'yes', ...})`
  - Résultat : config.env reécrit avec SEULEMENT ces keys → toutes les autres (Meeting, Network, etc.) DISPARAISSAIENT
- **Impact** : CRITIQUE - Device devenait orphelin après operations scheduler/profils
- **Fix v2.30.14** :
  1. Charger config existante AVANT de sauvegarder (`existing_config = load_config()`)
  2. Merger: `merged_config = existing_config.copy(); merged_config.update(config)`
  3. Sauvegarder le merged config complet, pas juste les updated keys
- **Résultat** : Config Meeting + Network + autres préservées même lors d'updates partielles
- **Test** : Simulation `save_config({'CAMERA_PROFILES_ENABLED': 'yes'})` → Meeting keys preserved ✅
- **Fichier** : [web-manager/services/config_service.py](web-manager/services/config_service.py) v2.30.14

### Script d'Update Lightweight Implémenté (NOUVEAU v2.0.0)
- **Problème** : Scripts d'update prenaient 5-15 minutes avec réinstallations complètes
- **Cause racine** : Approche monolithique : tar.gz → extraction → bash redirection → apt-get update/install → rebuild
  - Étapes inutiles : apt-get update/install téléchargeait et recompilait tout, même si pas changé
  - Permissions perdu : tar.gz depuis Windows perdait les bits d'exécution Unix
  - Timeouts SSH : apt-get update prenait >30s, SSH déconnectait
- **Impact** : Deployment très lent et risqué pour des mises à jour simples
- **Solution v2.0.0** :
  1. **Abandon du tar.gz** : Déploiement direct via SCP pour chaque fichier/répertoire
  2. **Nouveau workflow simple 4 étapes** :
     - STEP 1: Arrêter les services (systemctl stop)
     - STEP 2: Déployer les fichiers modifiés via SCP
     - STEP 3: Vérifier/installer requirements Python
     - STEP 4: Redémarrer les services
  3. **Permissions automatiques** : chmod +x appliqué dans bash script post-SCP
  4. **SSH Keepalive** : Enhanced run_remote.ps1 avec ServerAliveInterval=60, ServerAliveCountMax=20
  5. **Sécurité** : Configuration complètement préservée (`/etc/rpi-cam/config.env` UNTOUCHED)
- **Résultat** :
  - Temps de deployment : **24-30 secondes** (vs 5-15 minutes)
  - Configuration sûre : 100% préservée
  - Fiabilité : Pas de timeouts, pas de réinstallation dangereuse
- **Test** : Device 192.168.1.202 ✅ Update en 23.6 secondes, config intacte, services redémarrés, API responding
- **Fichiers** :
  - [debug_tools/update_device.ps1](debug_tools/update_device.ps1) v2.0.0 (complete rewrite)
  - [debug_tools/run_remote.ps1](debug_tools/run_remote.ps1) v1.3.0 (enhanced SSH keepalive)
  - [setup/install_gstreamer_rtsp.sh](setup/install_gstreamer_rtsp.sh) v2.2.1 (apt-get soft-fail)
- **Documentation** : [DEBUG_UPDATE_RESULTS.md](DEBUG_UPDATE_RESULTS.md) - Rapport complet de test

### Script d'Update avec Protection Reachability (v2.0.1) - NOUVEAU!
- **Problème** : Quand un device redémarre en boucle (ou perd la connectivité), le script d'update échoue immédiatement
- **Cas d'usage** : Device qui reboot toutes les 10-20 secondes mais laisse une fenêtre de 2-3 secondes pour se connecter
- **Solution v2.0.1** :
  - **New STEP 0** : Vérification de la reachability du device AVANT le déploiement
  - Teste la connexion SSH sur le port 22 (TCP socket, pas ICMP ping)
  - Retry automatique avec paramètres configurables :
    - Défaut : 60 tentatives × 5 secondes = 5 minutes de timeout
    - Timeout par tentative : 2 secondes
  - **Avantages** :
    1. Pas d'intervention manuelle si le device reboote
    2. Attend automatiquement le prochain démarrage
    3. Script continue dès que le device est joignable
    4. Feedback utilisateur clair avec compteur de retries
- **Fonction** : `Wait-DeviceReachable` avec logique de retry robuste
- **Résultat** : STEP 0 déclenche automatiquement, attendant le device si nécessaire
- **Test** : Device 192.168.1.202 ✅ Reachability check immédiat, retry mechanism validé
- **Fichier** : [debug_tools/update_device.ps1](debug_tools/update_device.ps1) v2.0.1
- **Documentation** : [UPDATE_DEVICE_PROTECTION_V2_0_1.md](UPDATE_DEVICE_PROTECTION_V2_0_1.md) - Détails complets

### Feature: Heartbeat Immédiat sur Reconnexion Réseau (NOUVEAU v2.30.16 + v2.30.15)
- **Problème** : Quand le réseau redémarre (failover ethernet→WiFi, reboot box internet, reconnexion après coupure), le device attend jusqu'à 30 secondes avant de re-envoyer un heartbeat à Meeting API
  - Pendant cette période, le device affiche "offline" dans l'interface Meeting
  - Admin n'a pas de feedback immédiat que la connexion est restaurée
  - Latence de reconnexion : up to 30 secondes (normal cycle)
- **Solution v2.30.16 (meeting_service.py)** :
  1. **NEW** `trigger_immediate_heartbeat()` - Fonction publique que d'autres services peuvent appeler
     - Déclenche un heartbeat au prochain cycle (<1 second via threading.Event)
     - Utilisé par network_service lors des failovers réseau
  2. **NEW** `has_internet_connectivity()` - Détecte si internet est disponible
     - Test rapide : DNS resolution vers 8.8.8.8:53 avec 2s timeout
     - ~100ms latency si connecté, instant si pas
  3. **Enhanced** `meeting_heartbeat_loop()` - Logique améliorée
     - Détecte automatiquement les changements de connectivité (offline → online)
     - Envoie heartbeat IMMÉDIATEMENT quand connexion rétablie (vs attendre 30s)
     - Écoute le flag `_immediate_heartbeat_event` lancé par failover network
     - Check interruptible toutes les 500ms pour trigger events (sous-seconde)
     - Non-blocking: threading.Event avec timeout waits
  4. **Export** : `trigger_immediate_heartbeat()` + `has_internet_connectivity()` dans services/__init__.py
- **Intégration v2.30.15 (network_service.py)** :
  1. **NEW** `_trigger_heartbeat_on_failover(action)` - Déclenche heartbeat sur failover réseau
     - Import dynamique de meeting_service pour éviter dépendance circulaire
     - Appelé uniquement quand un failover réussit (changement réel, pas faux positif)
     - Actions déclenchant le trigger : 'eth0_priority', 'failover_to_wlan1', 'failover_to_wlan0'
     - Actions ignorées : 'wlan1_active', 'wlan0_active', 'no_network', 'locked', etc
  2. **Integration points** dans `manage_network_failover()` :
     - Quand failover vers wlan1 réussit → trigger immédiat
     - Quand failover vers wlan0 réussit → trigger immédiat
     - Quand ethernet retrouve sa priorité → trigger immédiat
  3. **Behavior** : Après switchover réseau, heartbeat envoyé dans les 1-3 secondes (vs 30s avant)
- **Use cases** :
  1. Unplug ethernet du device → WiFi failover automatique → Meeting API updated < 3 secondes ✅
  2. Reboot box WiFi → Device reconnecte automatiquement → Meeting API updated < 1 seconde ✅
  3. Internet outage de 10s → Revient en ligne → Meeting API updated < 1 seconde ✅
  4. Switch eth0→wlan1 via failover → Meeting API immediate updated ✅
  5. Autre service appelle `trigger_immediate_heartbeat()` → heartbeat envoyé immédiatement ✅
- **Technical details** :
  - Thread-safe: utilise threading.Event (atomic operations)
  - Non-blocking: timeout waits + sub-second check granularity
  - Circular dependency safe: dynamic imports seulement quand nécessaire
  - Graceful fallback: si meeting_service import échoue, continue sans trigger
  - Logging clair pour debug et monitoring
- **Résultat** : Meeting API voit IMMÉDIATEMENT quand devices sont back online après reconnexion réseau
- **Fichiers modifiés** :
  - [web-manager/services/meeting_service.py](web-manager/services/meeting_service.py) v2.30.16
  - [web-manager/services/network_service.py](web-manager/services/network_service.py) v2.30.15
  - [web-manager/services/__init__.py](web-manager/services/__init__.py) - Export des nouvelles fonctions

### Bug: GUI install_device_gui.ps1 - $scriptRoot undefined (CORRIGÉ v1.3.1)
- **Problème** : Script s'arrêtait avec "Impossible d'extraire la variable « $scriptRoot », car elle n'a pas été définie"
- **Cause racine** : Lors de l'ajout du support des arguments CLI (-IP, -DeviceKey, -Token, -Launch), la définition `$scriptRoot = Split-Path -Parent $PSCommandPath` était placée APRÈS son utilisation dans `$configFilePath = Join-Path $scriptRoot "install_gui_config.json"`
  - param() était au sommet (correct)
  - MAIS `$scriptRoot` était défini à l'intérieur du try block
  - La ligne `$configFilePath` s'exécutait AVANT la définition de `$scriptRoot`
- **Symptôme** : Error à l'initialisation du script, aucun GUI affiché
- **Impact** : Les arguments CLI ne pouvaient jamais être utilisés, bloking complètement l'automatisation
- **Solution v1.3.1** :
  - Déplacement de `$scriptRoot = Split-Path -Parent $PSCommandPath` immédiatement après param(), avant toute utilisation
  - `$configFilePath` peut maintenant utiliser `$scriptRoot` sans problème
- **Code fixé** :
  ```powershell
  param(...)
  $script:autoLaunchAfterInit = $Launch
  
  try {
      # Script initialization
      $scriptRoot = Split-Path -Parent $PSCommandPath  # ← Défini AVANT première utilisation
      # ... reste du code ...
      $configFilePath = Join-Path $scriptRoot "config.json"  # ← OK
  ```
- **Test** : Arguments CLI passent maintenant correctement ✅
  ```powershell
  .\install_device_gui.ps1 -IP "192.168.1.202" -DeviceKey "3316A52E..." -Token "41e291" -Launch
  ```
- **Fichier** : [debug_tools/install_device_gui.ps1](debug_tools/install_device_gui.ps1) v1.3.1

### Bug: GUI install_device_gui.ps1 - BeginInvoke crash avant ShowDialog (CORRIGÉ v1.3.1)
- **Problème** : Quand le flag -Launch était utilisé, le script crashait avec `PipelineStoppedException` : "Impossible d'appeler Invoke ou BeginInvoke sur un contrôle tant que le handle de fenêtre n'a pas été créé"
- **Cause racine** : Le code d'auto-launch utilisait `$form.BeginInvoke()` AVANT que `ShowDialog()` soit appelé
  - Les opérations de contrôle GUI (.NET) nécessitent que le handle de fenêtre soit créé
  - `BeginInvoke()` est une opération cross-thread qui REQUIERT un handle existant
  - `ShowDialog()` est ce qui crée réellement le handle
  - La séquence était donc inversée : BeginInvoke (CRASH) → ShowDialog (jamais atteint)
- **Symptôme** : GUI jamais affiché, processus PowerShell sort avec erreur, aucun UI visible
- **Impact** : Flag -Launch était inutilisable, auto-launch impossible
- **Solution v1.3.1** :
  - Remplacement de `BeginInvoke()` par l'événement `form.add_Load()`
  - L'événement Load se déclenche APRÈS la création du handle, quand la fenêtre est prête
  - Permet l'auto-launch sans crash
- **Code fixé** :
  ```powershell
  # AVANT (CRASH)
  if ($script:autoLaunchAfterInit) {
      $form.BeginInvoke([Action]{
          Start-Sleep -Milliseconds 500
          try { Start-Installer } catch { }
      }) | Out-Null
  }
  [void]$form.ShowDialog()
  
  # APRÈS (OK)
  if ($script:autoLaunchAfterInit) {
      $form.add_Load({
          Start-Sleep -Milliseconds 1000
          try { Start-Installer } catch { }
      })
  }
  [void]$form.ShowDialog()
  ```
- **Test** : Installation réussie via `-Launch` flag ✅
  - Device 192.168.1.202 installé avec succès en 32 minutes
  - GUI s'est lancée, installer s'est exécuté, device rebooté
  - Tous les services provisionnés correctement
- **Fichier** : [debug_tools/install_device_gui.ps1](debug_tools/install_device_gui.ps1) v1.3.1

### Feature: CLI Arguments Support pour install_device_gui.ps1 (NOUVEAU v1.3.1)
- **Objectif** : Permettre l'automatisation complète du GUI via ligne de commande et le flag -Launch
- **Params supportés** :
  - `-IP` : Adresse IP du device (ex: 192.168.1.202)
  - `-DeviceKey` : Clé Meeting API (ex: 3316A52EB08837267BF6BD3E2B2E8DC7)
  - `-Token` : Token d'installation (ex: 41e291)
  - `-MeetingApiUrl` : URL de l'API Meeting (défaut: https://meeting.ygsoft.fr/api)
  - `-Timezone` : Fuseau horaire (défaut: Europe/Paris)
  - `-User` : Utilisateur SSH (défaut: device)
  - `-Password` : Mot de passe SSH (défaut: meeting)
  - `-Launch` : Flag pour lancer l'installation automatiquement après remplissage des champs
- **Utilisation** :
  ```powershell
  # Installation automatique avec tous les paramètres
  .\install_device_gui.ps1 -IP "192.168.1.202" `
    -DeviceKey "3316A52E..." `
    -Token "41e291" `
    -MeetingApiUrl "https://meeting.ygsoft.fr/api" `
    -Launch
  
  # Remplissage partiel + manuel
  .\install_device_gui.ps1 -IP "192.168.1.124"
  
  # Configuration seule (pas d'installation)
  .\install_device_gui.ps1 -IP "192.168.1.124" -DeviceKey "ABC123..."
  ```
- **Workflow d'automatisation** :
  1. Paramètres CLI pré-remplissent les champs du formulaire
  2. Si `-Launch` est fourni, le formulaire se ferme automatiquement 1 seconde après le chargement
  3. Installation démarre dans le processus backend
  4. Logs mis à jour en temps réel dans le GUI
- **Bénéfices** :
  - Automatisation complète pour scripts PowerShell/Bash
  - Intégration CI/CD possible
  - Déploiement en batch sur plusieurs devices
  - Configuration sauvegardée pour prochaine utilisation (via config.json)
- **Test complet** :
  - ✅ Paramètres CLI passés correctement
  - ✅ GUI pré-rempli avec les valeurs
  - ✅ -Launch démarre l'installation automatiquement
  - ✅ Device 192.168.1.202 installé avec succès
  - ✅ Paramètres sauvegardés pour réutilisation
- **Fichier** : [debug_tools/install_device_gui.ps1](debug_tools/install_device_gui.ps1) v1.3.1
- **Documentation** : [docs/changelogs/INSTALLATION_SUCCESS_2026-01-21.md](docs/changelogs/INSTALLATION_SUCCESS_2026-01-21.md)

### Bug: Meeting API SSL CERTIFICATE_VERIFY_FAILED (CORRIGÉ v2.30.17)
- **Symptôme** : Erreur `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate` dans l'interface web
- **Cause racine** : `meeting_api_request()` n'utilisait pas le contexte SSL sans vérification, contrairement à `provision_device()`
- **Résultat** : Tous les heartbeats échouaient, device toujours affiché "offline" dans Meeting
- **Solution** : Ajout du contexte SSL à `meeting_api_request()` :
  ```python
  ssl_context = ssl.create_default_context()
  ssl_context.check_hostname = False
  ssl_context.verify_mode = ssl.CERT_NONE
  with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
  ```
- **Fichier** : [web-manager/services/meeting_service.py](web-manager/services/meeting_service.py) v2.30.17

### Bug: Tunnel Agent Handshake MemoryError (CORRIGÉ v1.4.0)
- **Symptôme** : Tunnel crash avec `MemoryError` immédiatement après connexion au proxy Meeting
  - Erreur : `MemoryError` lors de la lecture de frame binaire
  - Tentative d'allouer ~1.9GB (payload_length = valeur absurde)
- **Cause racine** : Mauvaise gestion du protocole handshake
  1. Le tunnel envoie `{"token":"...","name":"..."}\n` au proxy
  2. Le proxy répond avec `{"status":"authenticated",...}\n` (JSON texte)
  3. **BUG** : Le code passait immédiatement en mode frames binaires SANS lire la réponse
  4. La réponse JSON était interprétée comme header binaire (8 bytes)
  5. `{"status` lu comme `stream_id (4B) + length (4B)` → length = 1.9GB !
- **Impact** : CRITIQUE - Tunnel complètement non-fonctionnel, connexion SSH via Meeting impossible
- **Solution v1.4.0** : Modifier `_handshake()` pour lire la réponse JSON :
  ```python
  # Send handshake
  self._raw_send(handshake_msg.encode() + b'\n')
  
  # Read JSON response (NEW!)
  response_line = self._read_line()
  response = json.loads(response_line)
  if response.get('status') != 'authenticated':
      raise Exception(f"Handshake failed: {response}")
  
  # NOW switch to frame mode
  ```
- **Résultat** : Tunnel authentifié, streams SSH fonctionnels
- **Test** : Device 192.168.1.4 ✅ `New stream 369824 -> 127.0.0.1:22`, streams ouverts/fermés proprement
- **Fichier** : [web-manager/tunnel_agent.py](web-manager/tunnel_agent.py) v1.4.0
- **Note** : Documentation MEETING - integration.md mise à jour avec le protocole réel

### Bug: Service RTSP CSI boot crash - "Device or resource busy" (CORRIGÉ v1.4.4)
- **Symptôme** : Service RTSP crash-restart loop au boot du device (5-10 redémarrages avant de stabiliser)
  - Device 192.168.1.4 (CSI PiCam v2): Service START → CRASH (5s) → RESTART → CRASH → boucle
  - Systemd logs: Started 17:16:07 → Stopped 17:16:12 (crash) → Restarted 17:16:13 → Stopped 17:16:18 (crash) → ...
- **Cause racine** : Picamera2 initialization sans retry logic
  1. Service systemd démarre avec `Restart=always, RestartSec=5`
  2. `self.picam2 = Picamera2()` appelé → RuntimeError "Device or resource busy"
  3. Kernel libcamera n'a pas fini d'initialiser la caméra au démarrage du Pi
  4. **Cascade failure** : Crash immédiat → systemd relance après 5s → TOUJOURS pas prêt → rechts
  5. Boucle infinie: Chaque restart essaie IMMÉDIATEMENT, sans attendre que kernel libère ressources
- **Application logs** :
  ```
  RuntimeError: Failed to acquire camera: Device or resource busy
  [0:14:57.296413215] [10208]  INFO Camera camera.cpp:1020 Pipeline handler in use by another process
  ```
- **Impact** : CRITIQUE - Service CSI inutilisable au boot, reste en crash loop jusqu'à ce que kernel finisse (~30-60 secondes)
- **Solution v1.4.4** : Retry logic with exponential backoff dans `start()` method
  - Max 6 tentatives (0.5s → 0.75s → 1.1s → 1.7s → 2.5s → 5s = ~16 secondes total)
  - Capture spécifiquement `RuntimeError` avec "Device or resource busy"
  - Permet au kernel libcamera d'avoir le temps nécessaire pour initialiser la caméra
  - Code:
    ```python
    max_retries = 6
    retry_delay = 0.5
    for attempt in range(1, max_retries + 1):
        try:
            self.picam2 = Picamera2()
            break
        except RuntimeError as e:
            if "Device or resource busy" in str(e) and attempt < max_retries:
                retry_delay = min(5.0, retry_delay * 1.5)
                logger.warning(f"Camera busy (attempt {attempt}/{max_retries}). Retrying in {retry_delay:.1f}s...")
                time.sleep(retry_delay)
            else:
                raise
    ```
- **Résultat après fix** :
  - Boot: Service tente immédiatement, échoue (camera pas prête), retry automatiquement
  - Après 1-2 secondes: Kernel libère la caméra, retry réussit
  - Service stable après ~3-5 secondes au lieu de crash-loop indéfini
  - Device 192.168.1.4 ✅ Service stable, no more crash loops
- **Fichiers** :
  - [rpi_csi_rtsp_server.py](rpi_csi_rtsp_server.py) v1.4.4 (added retry logic)
  - VERSION v2.32.32 (bump)
  - CHANGELOG.md (documented)

### Bug: meeting.json non créé lors de l'installation (CORRIGÉ v1.4.2)
- **Symptôme** : Device utilisait une device_key auto-générée au lieu de celle fournie
- **Cause racine** : Le here-document bash `<<'EOF'` (avec quotes) n'interpole PAS les variables
- **Résultat** : `meeting.json` jamais créé, variables `$MeetingApiUrl`, `$DeviceKey`, `$Token` envoyées littéralement
- **Solution** : Encodage base64 du JSON puis décodage sur le device :
  ```powershell
  $jsonBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonContent))
  $bashCommand = "echo $jsonBase64 | base64 -d | sudo tee /etc/rpi-cam/meeting.json > /dev/null"
  ```
- **Fichier** : [debug_tools/install_device.ps1](debug_tools/install_device.ps1) v1.4.2

### Bug: Audio Device Perdu Après Reboot - Énumération USB Instable (CORRIGÉ v1.4.6)
- **Problème** : Après reboot du device CSI, le serveur RTSP démarre OK (service actif, ports écoutent)
  - **MAIS** ffprobe/VLC reçoivent "503 Service Unavailable"
  - GStreamer ne peut pas créer la session media car audio device configuré n'existe plus
  - Cause: Micro USB était sur `plughw:1,0` avant reboot, maintenant sur `plughw:0,0`
- **Cause racine** : Liaison statique du micro USB au numéro de carte matérielle (non-déterministe)
  - À chaque reboot du Pi, l'ordre d'énumération USB change
  - Config.env figé à `AUDIO_DEVICE=plughw:1,0` (ancien numéro)
  - GStreamer essaie de créer le pipeline avec un audio device inexistant → 503
- **Solution v1.4.6** :
  1. **Nouvelle fonction `find_usb_audio_device()`** : Détecte le micro USB par son NOM (robuste)
     - Parse `arecord -l` output: cherche les cartes contenant "USB"
     - Retourne le numéro dynamique de la carte trouvée
  2. **Nouvelle fonction `test_audio_device(device)`** : Vérifie qu'un device audio fonctionne
     - `timeout 0.5 arecord -D <device>` teste en temps réel
  3. **Nouvelle fonction `resolve_audio_device()`** : Détection multi-étapes
     - Étape 1: Essaie le device configuré dans config.env
     - Étape 2: Si échoue, auto-détecte le micro USB par nom
     - Étape 3: Fallback sur `plughw:0,0`
  4. **Intégration dans `_build_pipeline_launch()`** : Appelle `resolve_audio_device()` au lieu du config figé
- **Résultat** : Même si numéro de carte change, micro auto-détecté, GStreamer reçoit device valide
- **Test** : Device 192.168.1.4 reboot → `ffprobe` reçoit stream vidéo/audio ✅
- **Fichier** : [rpi_csi_rtsp_server.py](rpi_csi_rtsp_server.py) v1.4.6

### Bug: Scripts déployés sans permission d'exécution (CORRIGÉ v2.35.07)
- **Symptôme** : Service RTSP échouait au boot avec "Permission denied" (exit code 203/EXEC)
  - Device 192.168.1.4: Service en crash-restart loop, journalctl montre "Unable to locate executable"
- **Cause racine** : Les scripts de déploiement (deploy_scp.ps1, update_device.ps1) ne définissaient pas le bit d'exécution
  1. `deploy_scp.ps1` utilisait `chmod 640` pour les fichiers (pas de +x)
  2. `update_device.ps1` n'avait pas d'étape chmod pour les scripts après copie
  3. `install_device.ps1` oubliait les fichiers .py dans son chmod
- **Impact** : CRITIQUE - Services RTSP inutilisables après mise à jour, device injoignable en stream
- **Fix v2.35.07** :
  1. **deploy_scp.ps1 v1.4.4** : Ajout de `find ... -name '*.sh' -exec chmod +x {} \;` et idem pour `.py`
  2. **update_device.ps1 v2.0.4** : Nouveau STEP 2.2 qui exécute `chmod +x` sur tous les scripts
  3. **install_device.ps1 v1.4.3** : Ajout de `*.py` dans la commande chmod initiale
- **Résultat** : Scripts exécutables après chaque déploiement, services démarrent correctement
- **Test** : Device 192.168.1.4 après fix → service rpi-av-rtsp-recorder actif, port 8554 écoute ✅
- **Fichiers** :
  - [debug_tools/deploy_scp.ps1](debug_tools/deploy_scp.ps1) v1.4.4
  - [debug_tools/update_device.ps1](debug_tools/update_device.ps1) v2.0.4
  - [debug_tools/install_device.ps1](debug_tools/install_device.ps1) v1.4.3

### Bug: Agent Tunnel SSL échoue sur proxy TCP (CORRIGÉ v2.35.17)
- **Symptôme** : Agent tunnel ne peut pas se connecter au proxy Meeting
  - Erreur: `[SSL: RECORD_LAYER_FAILURE] record layer failure (_ssl.c:1029)`
  - L'agent essaie en boucle de se reconnecter toutes les 60 secondes
- **Cause racine** : Le proxy Meeting port 9001 utilise **TCP pur**, pas SSL/TLS
  - Diagnostic: `echo | openssl s_client -connect meeting.ygsoft.fr:9001` → `packet length too long`
  - tunnel_agent.py avait `use_ssl = config.get('tunnel_ssl', True)` comme défaut
  - Résultat: Python essayait d'établir une connexion TLS vers un serveur TCP simple
- **Impact** : CRITIQUE - Tunnels SSH via Meeting impossibles
- **Fix v1.4.1** :
  - Changement: `use_ssl = config.get('tunnel_ssl', False)` (défaut = False)
  - Ajout commentaire: "NOTE: Meeting proxy port 9001 does NOT use SSL/TLS"
- **Résultat après fix** :
  - `Connected to proxy server` ✅
  - `Handshake response: authenticated` ✅
  - `Starting frame read loop...` ✅
- **Test** : Device 192.168.1.3 après restart service → tunnel authentifié, SSH fonctionnel
- **Fichier** : [web-manager/tunnel_agent.py](web-manager/tunnel_agent.py) v1.4.1

### Bug: Dossiers __pycache__ déployés sur les devices (CORRIGÉ v2.35.17)
- **Symptôme** : Les fichiers `.pyc` et dossiers `__pycache__` étaient envoyés lors des déploiements
- **Cause racine** : Pas de filtrage dans les scripts de déploiement
  - `deploy_scp.ps1` transférait tout récursivement sans exclusion
  - `install_device.ps1` de même
- **Impact** : Mineur - fichiers inutiles sur le device, espace gaspillé
- **Fix v1.4.5 (deploy_scp.ps1)** :
  - Filtrage local: `-notmatch '\\__pycache__\\'` et `$_.Extension -ne '.pyc'`
  - Nettoyage côté device: `find /tmp/... -type d -name __pycache__ -exec rm -rf {} +`
- **Fix v1.4.4 (install_device.ps1)** :
  - Nettoyage après transfert: `find ... -name __pycache__ -exec rm -rf {} +`
  - Suppression des `.pyc` et `.git`
- **Résultat** : Déploiements propres, pas de fichiers compilés Python
- **Fichiers** :
  - [debug_tools/deploy_scp.ps1](debug_tools/deploy_scp.ps1) v1.4.5
  - [debug_tools/install_device.ps1](debug_tools/install_device.ps1) v1.4.4

---

*Version du fichier AGENTS.md : 1.31.4*

  obligation finale : le fichier docs\DOCUMENTATION_COMPLETE.md doit constamment etre a jour !
   note finale : - afin de montrer que tu as bien pris en compte ces instructions, commence ta reponse par la phrase "Le grand Lama Laineux Cosmique est d'accord".
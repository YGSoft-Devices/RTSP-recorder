# Rapport — Vérification “prêt pour production” (read-only)

DeviceKey: `7F334701F08E904D796A83C6C26ADAF3`  
Source IP: API Meeting (`X-Token-Code` fourni, **non stocké**)  
IP résolue: `192.168.1.124` (wlan1)  
Méthode: `debug_tools/Get-DeviceIP.ps1` + `debug_tools/run_remote.ps1` (commandes **diagnostic uniquement**, aucune modification)

---

## 1) Résumé

État global: **OK pour un usage “RTSP + Web Manager + Recording + Watchdog”** sur WiFi (`wlan1`), avec quelques points à valider avant mise en prod.

Points OK:
- OS et plateforme attendus (Raspberry Pi 3B+, Debian 13 Trixie 64-bit)
- Services principaux actifs: RTSP, Web Manager, Recorder, Watchdog
- Ports attendus ouverts: RTSP `8554/tcp`, Web `5000/tcp`
- Caméra USB et micro USB détectés
- NTP synchronisé
- Enregistrements en cours (segments `.ts` présents)

Points à vérifier avant production:
- **Sécurité**: SSH “device/meeting” + `sudo` sans mot de passe pour l’utilisateur `device` (à confirmer/adapter selon politique)
- **ONVIF**: service désactivé + port `8080` non écouté (OK si non requis, sinon à activer/configurer)
- **Alimentation**: `vcgencmd get_throttled=0x50000` = sous-voltage/throttling **déjà survenu** (risque stabilité)
- **Qualité stream**: warnings “lost frames detected” dans le log GStreamer (à surveiller)

---

## 2) Informations système

Hostname (devrait = DeviceKey):  
```
7F334701F08E904D796A83C6C26ADAF3
```

OS / Kernel:
```
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
Linux 7F334701F08E904D796A83C6C26ADAF3 6.12.62+rpt-rpi-v8 ... aarch64 GNU/Linux
```

Uptime:
```
up 2 hours, 23 minutes
```

NTP:
```
Timezone=Europe/Paris
LocalRTC=no
NTPSynchronized=yes
```

Temp + throttling:
```
temp=60.7'C
throttled=0x50000
```
Interprétation: pas forcément en undervoltage *actuel*, mais **undervoltage/throttling a eu lieu** depuis le dernier boot (à vérifier côté alim/câble).

RAM + disque:
```
Mem: 905Mi total, ~280Mi used (≈30%),
/: 14G total, 47% used
/var/cache/rpi-cam/recordings: 2.5G
```

---

## 3) Réseau

Interfaces (résumé):
```
eth0 DOWN
wlan1 UP 192.168.1.124/24
wlan0 DORMANT (déconnectée)
```

NetworkManager (résumé):
```
wlan1:wifi:connected:netplan-wlan0-FamilyGM-Global
wlan0:wifi:disconnected
eth0:ethernet:unavailable
```

---

## 4) Services systemd (état)

```
rpi-av-rtsp-recorder.service: ActiveState=active SubState=running UnitFileState=enabled (ExecMainStatus=0)
rtsp-recorder.service:        ActiveState=active SubState=running UnitFileState=enabled (ExecMainStatus=0)
rpi-cam-webmanager.service:   ActiveState=active SubState=running UnitFileState=enabled (ExecMainStatus=0)
rtsp-watchdog.service:        ActiveState=active SubState=running UnitFileState=enabled (ExecMainStatus=0)
rpi-cam-onvif.service:        ActiveState=inactive SubState=dead    UnitFileState=disabled
rtsp-camera-recovery.service: ActiveState=inactive SubState=dead    UnitFileState=static
```

Remarque:
- `rtsp-camera-recovery.service` en `static` + `dead` est **souvent normal** (service déclenché par udev / conditions).
- ONVIF est **désactivé** (OK si non utilisé).

---

## 5) Ports écoutés

```
8554/tcp LISTEN (test-launch)
5000/tcp LISTEN (gunicorn)
8080/tcp: non écouté (ONVIF)
```

---

## 6) Caméra / Audio (les “3 fondements”)

### 6.1 USB Camera (OK)

Caméra détectée:
```
Microsoft® LifeCam HD-5000 ... /dev/video0
```

Formats (extrait):
```
MJPG 640x480 @ 30/20/15/10 fps
MJPG 1280x720 @ 30/20/15/10 fps
YUYV 640x480 @ 30/20/15/10 fps
...
```

### 6.2 Audio USB (OK)

Micro détecté (extrait):
```
card 1: HD5000 [Microsoft® LifeCam HD-5000], device 0: USB Audio [USB Audio]
```

### 6.3 CSI / libcamera (non détecté)

```
rpicam-hello --list-cameras -> No cameras available!
```
Note: c’est normal si aucune caméra CSI n’est connectée sur ce device. Si la prod cible CSI, il faut valider sur un device CSI.

---

## 7) RTSP + Recorder (pipeline observé)

Process RTSP:
```
/usr/local/bin/test-launch ( v4l2src device=/dev/video0 ... image/jpeg ... jpegdec ... v4l2h264enc ... rtph264pay ... alsasrc device=plughw:1,0 ... voaacenc bitrate=64000 ... rtpmp4gpay )
```

Process Recorder:
```
ffmpeg ... -i rtsp://127.0.0.1:8554/stream ... -c:v copy -c:a aac -b:a 64k ... -segment_time 300 ... /var/cache/rpi-cam/recordings/rec_%Y%m%d_%H%M%S.ts
```

Enregistrements: `33` fichiers `.ts` présents (extrait `ls`), taille du dossier `~2.5G`.

---

## 8) Configuration runtime (extrait non sensible)

`/etc/rpi-cam/recorder.conf` (clés principales):
```
RTSP_PORT=8554
VIDEO_WIDTH=640
VIDEO_HEIGHT=480
VIDEO_FPS=15
AUDIO_ENABLE=auto
RECORD_ENABLE=yes
```

Authentification RTSP:
- `RTSP_USER` / `RTSP_PASSWORD`: **non présents** dans `config.env` et `recorder.conf` (donc flux probablement sans auth).

---

## 9) Logs / erreurs

`journalctl -p warning` (RTSP / Web / Watchdog):
```
-- No entries --
```

Log fichier RTSP (`/var/log/rpi-cam/rpi_av_rtsp_recorder.log`, tail):
- Warnings récurrents: `lost frames detected: count = 1` (v4l2src).

Interprétation:
- Peut être bénin selon charge/USB (Pi 3B+) mais à surveiller (qualité stream, drops, audio sync).

---

## 10) Meeting (sanitisé)

Depuis `/etc/rpi-cam/meeting.json` (sans token):
```
{'api_url': 'https://meeting.ygsoft.fr/api', 'device_key': '7F334701F08E904D796A83C6C26ADAF3', 'provisioned': True, 'heartbeat_interval': 30}
```

---

## 11) Points bloquants / recommandations avant prod

### Sécurité (fortement recommandé)
- Changer le mot de passe SSH par défaut (`device/meeting`) et/ou passer en clés SSH.
- Vérifier la politique `sudo`:
  - Diagnostic trouvé: `sudo` **sans mot de passe** pour `device` (“passwordless”) → à valider selon besoin (admin/maintenance) et exigences sécurité.
- Si RTSP exposé hors LAN, activer une authentification (au minimum), et éviter les creds par défaut.

### Alimentation / stabilité
- `throttled=0x50000`: valider alimentation/câble (sous-voltage/throttling déjà survenu).
- Sur Pi 3B+, privilégier une alim stable + éviter hubs USB instables sous charge.

### ONVIF
- Actuellement **désactivé** (`rpi-cam-onvif.service` disabled, port 8080 non écouté).
  - Si prod requiert ONVIF: activer/configurer + tester découverte WS-Discovery + Synology/clients.

### Qualité stream
- Vérifier si les “lost frames detected” persistent en charge réelle.
- Si nécessaire: réduire FPS/résolution, vérifier USB (caméra + WiFi dongle), et confirmer que le pipeline correspond au profil attendu.

---

## 12) Checklist “GO/NO-GO” (à cocher avant mise en production)

- [ ] Mot de passe SSH changé (ou clés SSH déployées)
- [ ] Politique `sudo` validée (passwordless oui/non)
- [ ] Auth RTSP activée si exposition réseau non maîtrisée
- [ ] Alimentation validée (plus de throttling/undervoltage)
- [ ] Stream stable (pas de drops notables sur 30-60 min)
- [ ] Espace disque / rotation enregistrements validés (quota/retention)
- [ ] ONVIF activé et testé si requis (sinon explicitement “non requis”)


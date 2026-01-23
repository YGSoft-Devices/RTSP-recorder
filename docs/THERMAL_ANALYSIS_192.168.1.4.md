# Analyse chauffe / charge — Device 192.168.1.4 (CSI + audio USB)

## Mise à jour — capture approfondie

Date de capture: **Ven 23 Jan 2026 00:52:14 CET**  
Device: `3316A52EB08837267BF6BD3E2B2E8DC7`  
Objectif: approfondir l’analyse thermique (sans modification).

---

## 1) Résumé (TL;DR) — état actuel

- Température CPU: **80.6°C** (élevée).
- `vcgencmd get_throttled`: **`0x60002`** → **cap CPU actif** + événements de throttling depuis boot.
- Charge moyenne: **1.00 / 1.50 / 1.74** (1, 5, 15 min).
- Mémoire: **731 MB total**, **58 MB free**, **swap 33 MB utilisée** → pression mémoire légère.
- Stockage `/` toujours **93%** utilisé.
- Processus lourds (snapshot):
  - **`python3 /usr/local/bin/rpi_csi_rtsp_server.py` ~46% CPU**.
  - **`ffmpeg` ~19% CPU** (rtsp-recorder).
  - **`ffmpeg` ~65% CPU** (processus ponctuel → génération thumbnail / extraction).
- **PipeWire/WirePlumber non observés** dans les services actifs ni dans le top (différence majeure vs précédente capture).

Conclusion: la chauffe reste élevée principalement à cause de **RTSP CSI + enregistrement + tâches ffmpeg ponctuelles** (thumbnails/scan). Les services audio desktop (PipeWire/WirePlumber) ne semblent plus charger la machine sur cette capture.

---

## 2) Comparatif avec la capture précédente (22 Jan 2026)

### Changements notables
- ✅ **WirePlumber/PipeWire**: **non présents** dans les services actifs (auparavant ~50% CPU).
- ⚠️ **Température identique** (80.6°C) → la charge principale reste la chaîne RTSP + enregistrement.
- ⚠️ **Swap en usage** (33 MB), signe de pression mémoire.
- ⚠️ **Stockage toujours à 93%**, risque d’IO/latence.
- ⚠️ **Pics `ffmpeg`** visibles (thumbnails) → point chaud ponctuel.

---

## 3) Preuves (commandes / extraits)

### Température & throttling
```
temp=80.6'C
throttled=0x60002
```

### Charge / mémoire
```
load average: 1.00, 1.50, 1.74
Mem: 731 total / 58 free
Swap: 33 used
```

### Top CPU (snapshot)
```
python3 /usr/local/bin/rpi_csi_rtsp_server.py  ~46% CPU
ffmpeg (rtsp-recorder)                         ~19% CPU
ffmpeg (thumbnail/extraction)                  ~65% CPU
```

### Services actifs (hors projet)
- `avahi-daemon` (mDNS)
- `dnsmasq` (AP/DHCP local)
- `wpa_supplicant`
- `getty@tty1` / `serial-getty@ttyAMA0`
- `systemd-timesyncd`
- `NetworkManager`
- `ssh`

---

## 4) Services système “possiblement inutiles” (analyse uniquement)

> **Note**: aucune désactivation appliquée ici. Les tests/changes système doivent être faits sur `192.168.1.124`.

### Candidats à évaluer
- **`bluetooth.service`** (activé, souvent inutile en headless RTSP).
- **`avahi-daemon.service`** (mDNS, utile seulement si discovery locale nécessaire).
- **`dnsmasq.service`** (utile si AP/Hotspot ; sinon peut être désactivé).
- **`getty@tty1` / `serial-getty@ttyAMA0`** (console locale/serial, inutiles en headless).
- **`cloud-init*`** (souvent inutile après provisionnement).
- **`NetworkManager-wait-online`** (ralentit boot; pas nécessaire si pas de dépendance stricte).
- **`rpi-eeprom-update`** (update firmware automatique, pas toujours nécessaire en prod).

### Services **probablement nécessaires** pour le projet
- `rpi-av-rtsp-recorder`, `rtsp-recorder`, `rtsp-watchdog`, `rpi-cam-webmanager`, `rpi-cam-onvif`
- `ssh` (debug)
- `NetworkManager` (WiFi failover)
- `systemd-timesyncd` (NTP)

---

## 5) Pistes de mitigation (sans appliquer maintenant)

### Priorité A — CPU ponctuel (thumbnails)
1) Réduire les pics `ffmpeg` (thumbnails):
   - limiter la concurrence,
   - retarder les générations,
   - réduire la taille des thumbs si besoin.

### Priorité B — Services système inutiles
2) Auditer et **désactiver les services non requis** (bluetooth, avahi, getty, cloud-init, etc.).

### Priorité C — Ressources
3) Libérer de l’espace disque (objectif > 2–3 GB free).
4) Évaluer un profil “Eco” (FPS/résolution).

Date de capture: **Jeu 22 Jan 2026 14:52:38 CET**  
Device: `3316A52EB08837267BF6BD3E2B2E8DC7`  
Objectif: identifier les sources probables de chauffe **sans appliquer de modification**.

---

## 1) Résumé (TL;DR)

- Température CPU observée: **80.6°C** (niveau élevé).
- `vcgencmd get_throttled`: **`0x60002`** → **fréquence CPU capée actuellement** + événements de cap/throttle déjà survenus depuis le boot.
- Les plus gros consommateurs CPU au moment du snapshot:
  - **`python3 /usr/local/bin/rpi_csi_rtsp_server.py` ~66% CPU** (serveur RTSP CSI).
  - **`ffmpeg` (rtsp-recorder) ~22% CPU** (copie vidéo + ré-encodage audio AAC).
  - **`wireplumber` ~50% CPU** + **`pipewire`** actifs (hors besoin “headless RTSP”, probablement superflu et coûteux sur Pi 3B+).
- Stockage: root à **93%** utilisé, recordings ≈ **8.9G** (62 fichiers), ce qui augmente le risque de comportements dégradés (IO, scans, etc.).

Conclusion: sur ce device CSI, la chauffe est cohérente avec un **flux RTSP CSI + enregistrement + pile PipeWire/WirePlumber** qui ajoute une charge non-triviale.

---

## 2) Thermique / throttling (preuves)

### Température & état SoC
- `temp=80.6'C`
- `frequency(48)=1141118000` (ARM ~1.14 GHz mesuré)
- Governor: `ondemand`

### Throttling
- `throttled=0x60002`
  - Interprétation pratique:
    - **bit “freq capped” présent** → CPU actuellement limité.
    - **bits “occurred”** présents → il y a déjà eu cap/throttling depuis le dernier boot.

Impact attendu: perte de marge de performance, plus de risques de frame drops / instabilités si la charge augmente.

---

## 3) CPU / Processus dominants

### Snapshot `top`
Processus les plus lourds:
- `python3 /usr/local/bin/rpi_csi_rtsp_server.py` : ~**66% CPU**
- `ffmpeg ... /var/cache/rpi-cam/recordings/rec_%Y%m%d_%H%M%S.ts` : ~**22% CPU**
- `wireplumber` : ~**46–53% CPU**
- `pipewire` : ~**9–15% CPU**

Remarque: sur un Pi multi-core, `66%` correspond à ~0.66 cœur. La somme de plusieurs “gros” processus chauffe quand même fortement (surtout avec boîtier/ventilation limités).

---

## 4) RTSP CSI — config et observations

### Config active (extrait `/etc/rpi-cam/config.env`)
- `CAMERA_TYPE=csi`
- `VIDEO_WIDTH=1296`, `VIDEO_HEIGHT=972`, `VIDEO_FPS=30`
- `H264_BITRATE_KBPS=4000`, `H264_KEYINT=30`
- Audio:
  - `AUDIO_ENABLE=yes`
  - `AUDIO_DEVICE=plughw:1,0`
  - `AUDIO_GAIN=2` (amplification)

### Logs
Le log indique:
- démarrage de `rpi_csi_rtsp_server.py`
- libcamera OV5647 détectée (`ov5647.json`)
- mention “**HARDWARE H.264 Encoder**” côté serveur CSI

Même avec encodeur “hardware”, le process Python reste un poste CPU important (capture + préparation + push + RTSP stack + conversions éventuelles).

---

## 5) Services/éléments système probablement “inutiles” pour un device headless RTSP

### PipeWire / WirePlumber (constaté actifs)
Sur ce device, `wireplumber` et `pipewire` tournent dans la session user `device` et consomment du CPU.

Pour un setup RTSP sous systemd/root avec capture ALSA directe, ces services sont généralement:
- inutiles en production headless,
- susceptibles de causer des conflits ALSA (“device busy”),
- et ici clairement coûteux en CPU.

---

## 6) Stockage

- `/` à **93%** (≈ **1.1G** libres)
- `/var/cache/rpi-cam/recordings`: **8.9G** (≈ **62 fichiers**)
- `/var/cache/rpi-cam/thumbnails`: **1.2M**

Ce n’est pas la cause directe de chauffe, mais un disque très plein augmente les risques d’à-coups (IO, purge, scans), donc de charge indirecte.

---

## 7) Pistes de mitigation (sans appliquer maintenant)

### Priorité A — côté OS (gain rapide, hors projet)
1) **Désactiver PipeWire/WirePlumber pour l’utilisateur `device`** (headless RTSP).
   - Réduit la charge CPU de fond.
   - Réduit les risques ALSA “busy”.

### Priorité B — côté projet / configuration RTSP
2) Ajouter/activer un preset “Eco” (frontend) pour CSI:
   - `VIDEO_FPS=20` (au lieu de 30),
   - ou baisse de résolution (ex: 1296x972 → 640x480) selon besoin,
   - objectif: réduire le traitement par frame.
3) Réduire le coût de l’enregistrement:
   - si possible, baisser la charge audio (ex: bitrate AAC plus faible),
   - ou rendre l’enregistrement optionnel si non requis.
4) Encadrer les tâches secondaires (thumbnails/scan fichiers) si elles génèrent des pics CPU.

### Priorité C — matériel / refroidissement
5) Améliorer le refroidissement (boîtier ventilé, dissipateurs, airflow).
   - À 80°C, un Pi 3B+ est proche de sa zone de limitation.

---

## 8) Annexes — sorties de commandes (extraits)

### `vcgencmd`
```
temp=80.6'C
throttled=0x60002
frequency(48)=1141118000
```

### `ps` (top CPU)
```
python3 /usr/local/bin/rpi_csi_rtsp_server.py         ~66% CPU
ffmpeg (rtsp-recorder)                                ~22% CPU
/usr/bin/wireplumber                                  ~50% CPU
/usr/bin/pipewire                                      ~9% CPU
```

### Caméra CSI détectée
```
0 : ov5647 [2592x1944 10-bit GBRG] (/base/soc/i2c0mux/i2c@1/ov5647@36)
Modes: 640x480@30, 1296x972@30, 1920x1080@30, 2592x1944@30
```

---

# Synthèse chauffe / charge — Device 192.168.1.124 (USB + audio)

Date de capture: **Jeu 22 Jan 2026 14:48:23 CET**  
Device: `F743F2371A834C31B56B3B47708064FF`  
Objectif: identifier les sources probables de chauffe **sans appliquer de modification**.

---

## 1) Résumé (TL;DR)

- Température CPU observée: **74.7°C** (élevée mais moins critique que `192.168.1.4`).
- `vcgencmd get_throttled`: **`0x0`** (pas de throttling/cap détecté au moment du snapshot).
- La chauffe est principalement due à la chaîne RTSP USB en **MJPEG 1280x720@30fps** avec **décodage JPEG software (`jpegdec`)**:
  - `test-launch` observé à **~72% CPU**.
- Charges additionnelles:
  - `ffmpeg` (rtsp-recorder) à **~21% CPU** (copie vidéo + ré-encodage audio AAC).
  - pics `ffmpeg` pour thumbnails (observé à ~100% CPU ponctuellement).
  - `wireplumber/pipewire` actifs côté user `device` (superflu en headless RTSP, et ajoute de la charge CPU).
- Logs RTSP: multiples warnings `lost frames detected` côté `v4l2src` → charge trop élevée / pipeline à la limite.

Conclusion: ce device USB chauffe surtout à cause du coût de **decode MJPEG software** + enregistrement + services audio desktop (PipeWire) inutiles.

---

## 2) Thermique / throttling (preuves)

### `vcgencmd`
```
temp=74.7'C
throttled=0x0
frequency(48)=1200126000
```

---

## 3) CPU / Processus dominants

### Pipeline RTSP (processus principal)
Processus dominant:
- `/usr/local/bin/test-launch (...)` ~**72% CPU**

Pipeline complet observé (extrait):
```
v4l2src device=/dev/video0 io-mode=2 do-timestamp=true !
image/jpeg,width=1280,height=720,framerate=30/1 !
jpegdec ! videoconvert ! queue ... leaky=downstream !
video/x-raw,format=I420 !
v4l2h264enc ... video_bitrate=4000000 !
... rtph264pay ...
alsasrc device=plughw:0,0 ... ! voaacenc bitrate=64000 ! ... rtpmp4gpay ...
```

### Enregistrement
- `ffmpeg` (rtsp-recorder) ~**21% CPU**

### Audio desktop (hors besoin projet, constaté)
- `wireplumber`, `pipewire`, `pipewire-pulse` actifs côté user `device` et visibles dans le top CPU.

---

## 4) Caméra USB et décodage MJPEG

La caméra USB expose `YUYV` et `MJPG`. Le mode sélectionné est MJPEG (recommandé pour limiter le débit USB entrant), mais il impose un décodage JPEG.

Formats caméra (extrait `v4l2-ctl --list-formats-ext`):
- `MJPG` disponible en **1280x720 @ 30 fps**
- `YUYV` disponible en 1280x720 mais limité à **10 fps** → peu adapté si 30 fps souhaité

Plugins GStreamer importants (extraits):
- `jpegdec` disponible (software)
- `v4l2jpegdec` disponible (**hardware JPEG decode via V4L2**)

Conclusion: un levier d’optimisation projet très probable est de **préférer `v4l2jpegdec`** quand la source est MJPEG, au lieu de `jpegdec`.

---

## 5) Logs et symptômes de saturation

Le log `/var/log/rpi-cam/rpi_av_rtsp_recorder.log` contient des warnings récurrents:
- `lost frames detected` (v4l2src)

Interprétation: le pipeline est “à la limite” (CPU/USB), ce qui augmente la chauffe et réduit la stabilité.

---

## 6) Stockage

- `/` à **93%** (≈ **1.1G** libres)
- `/var/cache/rpi-cam/recordings`: **8.6G** (≈ **61 fichiers**)
- `/var/cache/rpi-cam/thumbnails`: ≈ **1.0M**

Comme sur `192.168.1.4`, ce n’est pas la cause directe de chauffe, mais un disque très plein augmente les risques d’à-coups.

---

## 7) Pistes de mitigation (sans appliquer maintenant)

### Priorité A — côté projet
1) **Basculer MJPEG decode vers `v4l2jpegdec`** (au lieu de `jpegdec`) quand disponible.
2) Exposer un preset “Eco (Pi 3B+)” dans le frontend:
   - ex: 1280x720@20fps ou 640x480@30fps, selon priorité qualité/stabilité.
3) Limiter l’impact des thumbnails (pics `ffmpeg`):
   - option/limitation de concurrence / baisse de priorité / désactivation auto si besoin.

### Priorité B — côté OS
4) **Désactiver PipeWire/WirePlumber** pour `device` (headless, ALSA direct).
5) Désactiver services non nécessaires (selon usage), pour gratter CPU/IO de fond.

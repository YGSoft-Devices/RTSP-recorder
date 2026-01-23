# Accélération matérielle H.264 — Raspberry Pi 3B+ (Trixie/Debian 13)

Objectif: comprendre *quand* RTSP-Full utilise du hardware, et comment éviter un encodage CPU trop coûteux sur Pi 3B+.

---

## Ce que RTSP-Full fait

Le script `rpi_av_rtsp_recorder.sh` construit un pipeline GStreamer et choisit un encodage H.264 dans cet ordre:

1) Caméra USB qui fournit déjà du H.264 → pas d’encodage (optimal)
2) `v4l2h264enc` (hardware) si présent **et réellement fonctionnel**
3) `x264enc` (software) en fallback

Sur Pi 3B+ sous Trixie, `v4l2h264enc` peut être présent mais cassé: RTSP-Full exécute un test rapide et bascule automatiquement sur `x264enc` si nécessaire.

---

## Vérifier le format de sortie de la caméra (USB)

```bash
v4l2-ctl -d /dev/video0 --list-formats-ext
```

Cas idéaux:
- `H264` (la caméra encode déjà)
- `MJPG` (moins coûteux à décoder que du RAW)

---

## Vérifier la disponibilité des plugins GStreamer

```bash
gst-inspect-1.0 v4l2h264enc
gst-inspect-1.0 x264enc
```

---

## Recommandations “safe” (Pi 3B+)

Si vous tombez en `x264enc` (software), rester sur:
- `VIDEO_WIDTH=640`
- `VIDEO_HEIGHT=480`
- `VIDEO_FPS=15`

Pour améliorer la stabilité:
- préférer une caméra USB MJPEG (décodage plus léger)
- éviter les résolutions élevées en software

---

## Conseils de diagnostic

CPU élevé:
- confirmer le pipeline effectif dans les logs du service `rpi-av-rtsp-recorder`
- vérifier si `v4l2h264enc` est utilisé ou si fallback `x264enc`

RTSP ne démarre pas:
- vérifier `test-launch` (`command -v test-launch`)
- vérifier `rtph264pay`, `h264parse` (`gst-inspect-1.0 rtph264pay h264parse`)

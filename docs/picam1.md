OK. Cas B = **Picamera2 pilote la caméra en maître**, et RTSP n’est qu’une “sortie”. C’est la bonne approche si tu veux des **contrôles d’image vraiment dynamiques** (sans redémarrer le stream), surtout sur PiCam1 (OV5647).

Je te donne une architecture **production-friendly** + un pipeline concret. Pas de magie, que du solide.

---

## 1) Pourquoi Cas B marche vraiment (et Cas A pas toujours)

Avec `libcamerasrc` (cas A), tu dépends des propriétés exposées par le plugin GStreamer et du moment où libcamera verrouille les controls. Souvent, ce qui doit être appliqué au sensor doit être fixé au démarrage.

Avec **Picamera2**, tu appelles directement l’API libcamera via Python :

* `set_controls()` → change AE/AWB/exposition/gain/NR/etc **pendant que la capture tourne**.
* Et ça marche sur OV5647.

Donc : tu gardes une capture active, tu ajustes en live.

---

## 2) Architecture “propre” recommandée

### Vue d’ensemble

* **Picamera2** capture en continu
* Tu récupères des frames (YUV/RGB) en Python
* Tu les envoies à un encodeur et un serveur RTSP

Il y a deux variantes principales (je te donne les deux) :

### Variante B1 — “Tout GStreamer” (recommandé si tu veux rester GStreamer)

Python fournit des frames à **GStreamer appsrc**, ensuite :

* convert
* encode H.264 (matériel si possible)
* RTP payloader
* RTSP server (gst-rtsp-server)

**Avantages**

* RTSP robuste
* latence maîtrisable
* architecture cohérente avec ton projet
* tu peux réutiliser tes options RTSP/auth plus tard

**Inconvénient**

* appsrc en Python demande un peu de soin (timestamps, caps, format)

### Variante B2 — “Picamera2 encode H264 + RTSP server”

Picamera2 peut sortir du H.264 (avec encoder matériel) et tu fais RTSP avec un serveur adapté.
**Mais** RTSP “simple” côté serveur est souvent plus galère à intégrer proprement que GStreamer RTSP server, selon ton existant.

---

## 3) Ce qu’il te faut côté paquets (Pi OS Trixie)

En pratique (à adapter selon ton install), vise :

* `python3-picamera2`
* `python3-numpy` (souvent requis)
* `gstreamer1.0-tools`
* `gstreamer1.0-plugins-base`
* `gstreamer1.0-plugins-good`
* `gstreamer1.0-plugins-bad`
* `gstreamer1.0-plugins-ugly`
* `gstreamer1.0-libav`
* `python3-gi` + `gir1.2-gstreamer-1.0` + `gir1.2-gst-rtsp-server-1.0`

(Je ne te balance pas une liste “apt” figée sans vérifier sur ta machine, parce que les noms exacts varient un peu. Mais ces familles sont celles qui comptent.)

---

## 4) Pipeline RTSP “appsrc → H264 → RTSP” (GStreamer)

### Format de frame conseillé

Pour Pi 3B+, vise un format simple et léger :

* capture Picamera2 en **YUV420** si possible (I420)
* sinon RGB → conversion (plus coûteux)

Picamera2 te donne souvent du **YUV420** via `main` config.

### Pipeline GStreamer typique (dans gst-rtsp-server)

Chaîne inside RTSP factory :

* `appsrc name=src is-live=true do-timestamp=true format=time caps=video/x-raw,format=I420,width=...,height=...,framerate=...`
* `queue leaky=2 max-size-buffers=2`
* `videoconvert` (si besoin)
* `v4l2h264enc` **ou** `x264enc tune=zerolatency speed-preset=ultrafast bitrate=... key-int-max=...`
* `h264parse config-interval=1`
* `rtph264pay name=pay0 pt=96`

Sur Pi 3B+, si `v4l2h264enc` est instable : tu fallback en x264enc.

---

## 5) Exemple complet “serveur RTSP Picamera2” (Python)

Ce script :

* démarre Picamera2
* démarre un RTSP server GStreamer
* pousse des frames via appsrc
* expose une fonction pour changer les controls **en live**

⚠️ Je le mets en bloc complet. Il faut ajuster width/height/fps selon ton matos et charge CPU.

```python
#!/usr/bin/env python3
"""
picam2_rtsp_server.py
RTSP server (gst-rtsp-server) fed by Picamera2 frames via appsrc.
Supports live camera control updates via Picamera2.set_controls().

Test:
  rtsp://<ip>:8554/stream

Notes:
- Designed for Raspberry Pi OS (Trixie) with Picamera2 + GStreamer.
- On Pi 3B+, keep resolution/fps modest if using x264enc.
"""

import time
import threading
from typing import Dict, Any, Optional

from picamera2 import Picamera2

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer, GLib


class Picam2RtspServer:
    def __init__(
        self,
        width: int = 1296,
        height: int = 972,
        fps: int = 20,
        port: int = 8554,
        path: str = "stream",
        bitrate_kbps: int = 1200,
        keyint: int = 40,
        prefer_hw: bool = True,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.port = port
        self.path = path
        self.bitrate_kbps = bitrate_kbps
        self.keyint = keyint
        self.prefer_hw = prefer_hw

        self.picam2: Optional[Picamera2] = None
        self.appsrc = None

        self._running = False
        self._push_thread: Optional[threading.Thread] = None
        self._frame_interval = 1.0 / float(self.fps)

        Gst.init(None)

    def _build_pipeline_launch(self) -> str:
        # HW encoder branch (if v4l2h264enc works) else SW x264enc fallback.
        # We keep both strings here; runtime selection is simple. In prod, you can self-test and choose.
        hw = (
            f"appsrc name=src is-live=true do-timestamp=true format=time "
            f"caps=video/x-raw,format=I420,width={self.width},height={self.height},framerate={self.fps}/1 "
            f"! queue leaky=2 max-size-buffers=2 "
            f"! v4l2h264enc extra-controls=\"controls,video_bitrate={self.bitrate_kbps*1000}\" "
            f"! h264parse config-interval=1 "
            f"! rtph264pay name=pay0 pt=96 config-interval=1"
        )

        sw = (
            f"appsrc name=src is-live=true do-timestamp=true format=time "
            f"caps=video/x-raw,format=I420,width={self.width},height={self.height},framerate={self.fps}/1 "
            f"! queue leaky=2 max-size-buffers=2 "
            f"! x264enc tune=zerolatency speed-preset=ultrafast bitrate={self.bitrate_kbps} key-int-max={self.keyint} "
            f"! h264parse config-interval=1 "
            f"! rtph264pay name=pay0 pt=96 config-interval=1"
        )

        return hw if self.prefer_hw else sw

    def _on_media_configure(self, factory, media):
        element = media.get_element()
        self.appsrc = element.get_child_by_name("src")
        # If you want, you can force caps here too.
        # self.appsrc.set_property("caps", Gst.Caps.from_string(...))
        self.appsrc.set_property("block", False)

    def _push_loop(self):
        assert self.picam2 is not None
        assert self.appsrc is not None

        # We'll capture as bytes in I420 (YUV420 planar) to match caps.
        # Picamera2 can output YUV420 directly if configured.
        next_ts = time.monotonic()

        while self._running:
            now = time.monotonic()
            if now < next_ts:
                time.sleep(max(0, next_ts - now))
            next_ts += self._frame_interval

            # Capture frame from Picamera2
            # "main" stream returns a numpy array or bytes depending on config; we use capture_buffer for speed.
            buf = self.picam2.capture_buffer("main")
            if buf is None:
                continue

            gst_buf = Gst.Buffer.new_allocate(None, len(buf), None)
            gst_buf.fill(0, buf)

            # Push buffer
            ret = self.appsrc.emit("push-buffer", gst_buf)
            if ret != Gst.FlowReturn.OK:
                # If client disconnects etc, flow can change.
                time.sleep(0.1)

    def start(self):
        if self._running:
            return

        # 1) Start Picamera2
        self.picam2 = Picamera2()

        # Configure main stream in YUV420 so appsrc caps match I420.
        # Lower res/fps if CPU is tight.
        video_config = self.picam2.create_video_configuration(
            main={"size": (self.width, self.height), "format": "YUV420"},
            controls={"FrameRate": self.fps},
        )
        self.picam2.configure(video_config)
        self.picam2.start()

        # 2) Start RTSP server
        server = GstRtspServer.RTSPServer()
        server.set_service(str(self.port))

        mounts = server.get_mount_points()
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(f"({self._build_pipeline_launch()})")
        factory.set_shared(True)
        factory.connect("media-configure", self._on_media_configure)

        mounts.add_factory(f"/{self.path}", factory)

        loop = GLib.MainLoop()
        server.attach(None)

        # 3) Start push thread after appsrc exists (media-configure happens on first client).
        # We'll start loop in a thread, then wait for first client to create media/appsrc.
        self._running = True

        def _run_loop():
            loop.run()

        t = threading.Thread(target=_run_loop, daemon=True)
        t.start()

        # Wait for first client connection to create appsrc
        print(f"[RTSP] Listening: rtsp://0.0.0.0:{self.port}/{self.path}")
        print("[RTSP] Waiting for first client to connect to initialize pipeline...")

        while self._running and self.appsrc is None:
            time.sleep(0.1)

        if not self._running:
            return

        print("[RTSP] Client connected, starting frame push loop.")
        self._push_thread = threading.Thread(target=self._push_loop, daemon=True)
        self._push_thread.start()

    def stop(self):
        self._running = False
        time.sleep(0.2)
        if self.picam2:
            self.picam2.stop()
            self.picam2.close()
            self.picam2 = None

    # ---- Live controls ----
    def set_controls(self, controls: Dict[str, Any]):
        """
        Example:
          set_controls({"AeEnable": True, "AwbEnable": True})
          set_controls({"AeEnable": False, "ExposureTime": 15000, "AnalogueGain": 2.0})
        """
        if not self.picam2:
            raise RuntimeError("Camera not started")
        self.picam2.set_controls(controls)

    def list_controls(self) -> Dict[str, Any]:
        if not self.picam2:
            raise RuntimeError("Camera not started")
        return self.picam2.camera_controls


if __name__ == "__main__":
    srv = Picam2RtspServer(
        width=1296,
        height=972,
        fps=20,
        port=8554,
        path="stream",
        bitrate_kbps=1200,
        keyint=40,
        prefer_hw=False,  # start safe on Pi 3B+: set True only if you've validated v4l2h264enc
    )
    try:
        srv.start()
        # Example dynamic changes:
        time.sleep(2)
        print("[CTRL] Enabling AE/AWB")
        srv.set_controls({"AeEnable": True, "AwbEnable": True})

        # Keep running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
```

### Ce que tu gagnes avec ça

* RTSP stable
* contrôle live via `srv.set_controls(...)`
* possibilité de brancher ton Web UI pour appeler un endpoint qui fait `set_controls()`

### Ce que tu dois gérer proprement

* **caps + format** (I420/YUV420)
* **timing / timestamps** (ici on fait simple et correct)
* **latence** (queue leaky + buffers limités)
* encodeur : HW vs SW selon stabilité

---

## 6) Contrôles “dynamiques” utiles en pratique (PiCam1)

Sur OV5647, les contrôles typiques à modifier en live :

### Auto mode (recommandé 90% du temps)

```python
set_controls({"AeEnable": True, "AwbEnable": True})
```

### Mode manuel (éclairage fixe)

```python
set_controls({
  "AeEnable": False,
  "ExposureTime": 15000,      # microsecondes
  "AnalogueGain": 2.0,
  "AwbEnable": False
})
```

### EV / compensation exposition (si dispo)

```python
set_controls({"ExposureValue": -1})  # ou +1 selon plage
```

### Image “perçue” (post-ish)

```python
set_controls({"Contrast": 1.2, "Saturation": 1.1, "Sharpness": 1.0})
```

(La disponibilité exacte dépend de ce que `camera_controls` expose. Le script de listing te donne la vérité.)

---

## 7) Intégration avec ton Web UI / ton fichier csi_tuning.json

Tu as déjà `csi_tuning.json`. En cas B, ton web manager devient encore plus simple :

* `/api/camera/csi/control` :

  * écrit dans `csi_tuning.json`
  * appelle le service RTSP (via socket local, ou HTTP local, ou même un fifo) pour faire `set_controls()` immédiatement.

### Important : architecture process

Pour appliquer des controls sans redémarrer, **le process qui contrôle Picamera2 doit rester vivant** et exposer une API interne.

Tu peux faire :

* un mini serveur HTTP local (127.0.0.1) dans le même process
* ou une socket UNIX `/run/rpi-cam/picam2.sock`
* ou un “control pipe” simple (FIFO) en root

**Je recommande socket/HTTP local**, c’est propre et testable.

---

## 8) Audio (si tu veux l’ajouter dans Cas B)

Tu peux ajouter un deuxième “pay” dans RTSP server :

* vidéo: `pay0` H264
* audio: `pay1` AAC

Et tu feeds l’audio via `alsasrc` directement dans le pipeline (pas besoin de Python pour l’audio).

Exemple (conceptuel) :

* `alsasrc device=plughw:1,0 ! audioconvert ! audioresample ! avenc_aac bitrate=64000 ! rtpmp4gpay name=pay1 pt=97`

Et la vidéo reste appsrc.

---

## 9) Notes perf réalistes Pi 3B+

* Si HW encode KO → x264enc sur Pi 3B+ = **640x480@15–20 fps** “confort”, 720p c’est sport.
* Avec appsrc + conversions, évite RGB si tu peux. YUV420 direct = meilleur.

---

## 10) Checklist “prod-ready” Cas B

* [ ] Un service systemd dédié : `rpi-av-rtsp-picam2.service`
* [ ] L’API interne pour controls (socket/HTTP local)
* [ ] Le Web UI appelle l’API interne (pas systemctl restart)
* [ ] Un “self-test encoder” au boot (HW ok → prefer_hw=True)
* [ ] Limiter buffers/queues pour éviter la latence zombie
* [ ] Logs maîtrisés (debug activable, pas permanent)

---

Si tu suis Cas B, tu passes d’un système “je redémarre pour appliquer” à un système “je contrôle en live”, et ça change tout pour l’usage réel. Tu peux même faire des presets jour/nuit sans couper la vidéo.

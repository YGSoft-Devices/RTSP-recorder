# Comparatif features (code-only) — RTSP-recorder vs docs/another_projet_like_mine.md

Source comparé : `docs/another_projet_like_mine.md`

Méthode : vérification basée **uniquement sur le code** du repo (pas sur la documentation).

| Feature (source) | Présent dans RTSP-recorder | Preuves dans le code |
|---|---|---|
| Implements the ONVIF Standard for a CCTV Camera and NVT | Oui | Device/Media + Imaging + DeviceIO + WS-Discovery. SetVideoEncoderConfiguration appliqué. `onvif-server/onvif_server.py` |
| Streams H264 video over RTSP from the official Raspberry Pi camera (CSI) and some USB cameras | Oui | CSI via Picamera2 → RTSP: `rpi_csi_rtsp_server.py` (H264Encoder + appsrc + RTSP). USB via GStreamer/test-launch: `rpi_av_rtsp_recorder.sh` (v4l2src + H264 pipeline) |
| Uses hardware H264 encoding using the GPU on the Pi | Oui | USB: `rpi_av_rtsp_recorder.sh` (v4l2h264enc). CSI: `rpi_csi_rtsp_server.py` (Picamera2 H264Encoder hardware) |
| Implements Camera control (resolution and framerate) through ONVIF | Oui | `SetVideoEncoderConfiguration` applique VIDEO_WIDTH/HEIGHT/FPS + H264_BITRATE_KBPS et redémarre RTSP. `onvif-server/onvif_server.py` |
| Can set other camera options through a web interface | Oui | API caméra (autofocus/focus/controls) + UI: `web-manager/blueprints/camera_bp.py`, `web-manager/services/csi_camera_service.py` |
| Discoverable (WS-Discovery) on Pi/Linux by CCTV Viewing Software | Oui | WS-Discovery multicast implémenté: `onvif-server/onvif_server.py` (WSDDiscovery, multicast 239.255.255.250:3702) |
| Works with ONVIF Device Manager (Windows) and ONVIF Device Tool (Linux) | Non vérifié | Compatibilité améliorée (Imaging + DeviceIO + SetVideoEncoderConfiguration), mais non testée |
| Works with other CCTV Viewing Software list (Antrica, Avigilon, Bosch, Milestone, iSpy, etc.) | Non vérifié | Compatibilité ONVIF améliorée, tests non réalisés |
| Implements ONVIF Authentication | Oui | WS-Security UsernameToken/digest vérifié: `onvif-server/onvif_server.py` (`verify_wsse_auth`) |
| Implements Absolute, Relative and Continuous PTZ and controls the Pimoroni Pan-Tilt HAT | Non | Aucun code PTZ / HAT / pan-tilt dans le repo |
| Supports Waveshare Pan-Tilt HAT with custom PWM driver | Non | Aucun code PWM/HAT correspondant |
| Converts ONVIF PTZ commands into Pelco D / Visca via UART | Non | Aucun code PTZ / UART / Pelco / Visca |
| Can reference other RTSP servers (proxy/relay) | Oui | Mode proxy RTSP/MJPEG/screen via `STREAM_SOURCE_MODE` + `STREAM_SOURCE_URL`: `rpi_av_rtsp_recorder.sh` |
| Implements Imaging service Brightness and Focus commands (Profile T) | Oui | ONVIF Imaging (Get/SetImagingSettings + Options) avec Brightness/Focus: `onvif-server/onvif_server.py` |
| Implements Relay (digital output) function | Oui | DeviceIO RelayOutputs + SetRelayOutputState (GPIO): `onvif-server/onvif_server.py` |
| Supports Unicast (UDP/TDP) and Multicast using mpromonet's RTSP server | Oui (GStreamer) | `test-launch` supporte RTSP_PROTOCOLS + multicast (udp-mcast) via `install_gstreamer_rtsp.sh` |
| Supports Unicast (UDP/TCP) RTSP using GStreamer | Oui | `RTSP_PROTOCOLS` permet UDP/TCP (test-launch v2.2.0): `rpi_av_rtsp_recorder.sh`, `setup/install_gstreamer_rtsp.sh` |
| Works as a PTZ Proxy | Non | Aucun code PTZ/Proxy |
| USB cameras supported via the GStreamer RTSP server with limited parameters | Oui | USB via v4l2src + formats MJPG/YUYV/H264: `rpi_av_rtsp_recorder.sh` |

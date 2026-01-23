# RTSP-Full — Dérivé ESP32 (caméra only)

Ce dossier contient un dérivé du projet RTSP-Full destiné aux cartes **ESP32-CAM avec PSRAM**.

Objectifs:
- Support caméra **OV2640** (ESP32-CAM “AI Thinker” typique)
- Prévoir un support **OV5640** (pinout à confirmer)
- **Interface web** légère (sans audio, sans enregistrements)
- Intégration **Meeting** (heartbeat)

## Arborescence

`esp32/firmware/` contient le firmware PlatformIO (Arduino) + un frontend embarqué via LittleFS (look & feel aligné sur le Web Manager).

## Démarrage rapide (PlatformIO)

Prérequis:
- VSCode + extension PlatformIO, ou PlatformIO CLI

Commandes (dans `esp32/firmware/`):
- Build: `pio run`
- Upload firmware: `pio run -t upload`
- Upload web UI (LittleFS): `pio run -t uploadfs`
- Monitor série: `pio device monitor -b 115200`

## WiFi

Au premier boot (si aucune config WiFi n’est enregistrée):
- l’ESP démarre en **AP** `RTSP-Full-ESP32` (mot de passe `rtsp-full`)
- l’UI est accessible sur `http://192.168.4.1/`

Après configuration (STA):
- l’UI est accessible sur l’IP obtenue via DHCP.

## Notes matérielles

- OV2640: supporté par défaut (pinout “AI Thinker”).
- OV5640: nécessite un pinout exact (à compléter dans `esp32/firmware/include/boards/ov5640_template.h`).

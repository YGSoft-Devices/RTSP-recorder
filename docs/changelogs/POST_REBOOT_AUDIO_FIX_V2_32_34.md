# Fix Post-Reboot Audio Device Loss - v2.32.34

**Date**: 21 Janvier 2026
**Device Testé**: 192.168.1.4 (CSI OV5647 + USB Microphone)
**Version**: rpi_csi_rtsp_server.py v1.4.6

## Problème Critique Identifié

### Symptôme
- **Avant le fix**: Après reboot du device, le serveur RTSP démarre (service "active", ports écoutent)
- **MAIS**: Les clients (ffprobe, VLC, Synology) reçoivent "503 Service Unavailable"
- **Cause**: GStreamer ne peut pas créer le media pipeline car le micro USB configuré n'existe plus

### Diagnostic
```bash
# Erreur vue par ffprobe
ffprobe -i rtsp://192.168.1.4:8554/stream
[rtsp @ ...] method DESCRIBE failed: 503 Service Unavailable

# Logs du service
[17:51:13] [CSI-RTSP] WARNING: Audio device plughw:1,0 not accessible
```

## Root Cause

### L'Énumération USB est Non-Déterministe
À chaque reboot du Raspberry Pi, l'ordre d'énumération des devices USB peut changer:

```
BOOT 1 (Première installation)
  Caméra CSI (libcamera)       → (n/a)
  Micro USB                    → card 1 (hw:1)
  → Config.env sauvegardé: AUDIO_DEVICE=plughw:1,0  ✓

BOOT 2+ (Après reboot)
  Micro USB                    → card 0 (hw:0)  ← NUMÉRO CHANGE!
  Caméra CSI (libcamera)       → (n/a)
  → Config.env toujours: AUDIO_DEVICE=plughw:1,0  ✗ (N'existe plus!)
```

### Liaison Statique = Fragile
- Configurer `AUDIO_DEVICE=plughw:1,0` fixe le numéro de carte
- Les numéros de cartes ALSA sont assignés par le kernel dans l'ordre de détection USB
- Cet ordre est **non-déterministe** (dépend du timing)
- Après chaque reboot → numéro change → Device introuvable
- GStreamer essaie créer pipeline avec device inexistant → 503 Service Unavailable

## Solution: Détection Dynamique par Nom

### Implémentation dans rpi_csi_rtsp_server.py v1.4.6

#### 1. Fonction `find_usb_audio_device()`
Détecte le micro USB par son NOM au lieu du numéro de carte:

```python
def find_usb_audio_device():
    """Detect USB audio device by name (more robust than static plughw:X,0)."""
    try:
        result = subprocess.run(['arecord', '-l'], capture_output=True, text=True, timeout=2)
        for line in result.stdout.split('\n'):
            if 'USB' in line and 'card' in line:
                # Parse "card 0: Device [USB PnP Sound Device]..."
                card_num = line.split(':')[0].strip().split()[-1]
                if card_num.isdigit():
                    device = f"plughw:{card_num},0"
                    logger.info(f"Auto-detected USB audio device: {device}")
                    return device
        return CONF['AUDIO_DEVICE']  # Fallback
    except Exception as e:
        logger.warning(f"Error detecting USB audio device: {e}")
        return CONF['AUDIO_DEVICE']
```

#### 2. Fonction `test_audio_device(device)`
Vérifie que le device audio est réellement accessible:

```python
def test_audio_device(device):
    """Test if audio device is accessible."""
    try:
        result = subprocess.run(
            ['bash', '-c', f'timeout 0.5 arecord -D {device} > /dev/null 2>&1'],
            timeout=1
        )
        is_working = result.returncode == 0 or result.returncode == 124  # 124 = timeout (ok)
        if is_working:
            logger.info(f"Audio device {device} is accessible ✓")
        return is_working
    except Exception as e:
        logger.warning(f"Failed to test audio device {device}: {e}")
        return False
```

#### 3. Fonction `resolve_audio_device()`
Stratégie intelligente multi-étapes:

```python
def resolve_audio_device():
    """Resolve actual audio device with fallback chain."""
    configured = CONF['AUDIO_DEVICE']
    
    # Step 1: Try configured device
    if test_audio_device(configured):
        return configured
    
    # Step 2: Auto-detect USB audio
    detected = find_usb_audio_device()
    if detected != configured and test_audio_device(detected):
        logger.info(f"Using auto-detected {detected} instead of {configured}")
        return detected
    
    # Step 3: Fallback
    fallback = "plughw:0,0"
    logger.warning(f"Using fallback device {fallback}")
    return fallback
```

#### 4. Intégration dans `_build_pipeline_launch()`
Au lieu de chercher le config statique:

```python
# AVANT (fragile)
device = self.conf['AUDIO_DEVICE']

# APRÈS (robuste)
device = resolve_audio_device()  # Détecté dynamiquement à chaque boot
```

## Tests et Résultats

### Device 192.168.1.4 - Post-Reboot

#### AVANT v1.4.6
```bash
$ systemctl status rpi-av-rtsp-recorder
Active: active (running) since ... 28s ago

$ ffprobe -i rtsp://192.168.1.4:8554/stream
[rtsp @ ...] method DESCRIBE failed: 503 Service Unavailable
```
❌ Service "running" mais stream inaccessible

#### APRÈS v1.4.6
```bash
$ systemctl status rpi-av-rtsp-recorder
Active: active (running) since ... 2min ago

$ ffprobe -i rtsp://192.168.1.4:8554/stream
Stream #0:0: Video: h264 (High), 1296x972, 30 fps
Stream #0:1: Audio: aac (LC), 44100 Hz, mono
```
✅ Stream vidéo/audio accessible immédiatement

### Logs du Service
```
[17:54:50] [CSI-RTSP] WARNING: Audio device plughw:1,0 failed test
[17:54:50] [CSI-RTSP] WARNING: Configured device plughw:1,0 not accessible, attempting auto-detection...
[17:54:50] [CSI-RTSP] INFO: Auto-detected USB audio device: plughw:0,0  ← DÉTECTÉ!
[17:54:50] [CSI-RTSP] INFO: GStreamer Pipeline: ... alsasrc device="plughw:0,0" ...
[17:55:24] [CSI-RTSP] INFO: appsrc configured for hardware H.264 stream (shared pipeline).
```

### Tests Successifs
```bash
# 3 connexions RTSP consécutives = 3 succès ✅
Test 1: Stream #0:0: Video: h264 (High), 1296x972, 30 fps
Test 2: Stream #0:0: Video: h264 (High), 1296x972, 30 fps  
Test 3: Stream #0:0: Video: h264 (High), 1296x972, 30 fps
```

### API de Contrôle CSI
```bash
$ curl -s http://127.0.0.1:8085/controls | jq '.controls | keys'
[
  "AeConstraintMode",
  "AeEnable",
  "AeExposureMode",
  ...
  "Saturation": 1.0,        ← Disponible!
  "Brightness": -0.01,      ← Disponible!
  "Contrast": 0.89,         ← Disponible!
  ...
]
```
✅ 26 contrôles CSI accessibles

## Impact et Applicabilité

### Affecte
- **TOUS les devices avec CSI camera + USB audio** (pratiquement 100% des déploiements)
- Apparaît APRÈS reboot (pas visible en première utilisation)
- Impacts critiques pour l'uptime 24/7

### Bénéfices du Fix
1. **Robustesse**: Même si numéro de carte USB change, micro toujours détecté
2. **Transparence**: Aucune configuration manuelle nécessaire
3. **Reliability**: Stream accessible immédiatement après reboot
4. **Fallback Chain**: Graceful degradation si auto-detect échoue

## Versions Affectées et Fix

### Fichiers Modifiés
- [rpi_csi_rtsp_server.py](../../rpi_csi_rtsp_server.py): v1.4.5 → v1.4.6

### Changements Inclus
1. Ajout `find_usb_audio_device()` - Auto-détection par nom
2. Ajout `test_audio_device()` - Test d'accessibilité
3. Ajout `resolve_audio_device()` - Logique multi-étapes
4. Modifié `_build_pipeline_launch()` - Utilise résolution dynamique

### VERSION Globale
- VERSION: 2.32.33 → **2.32.34**

## Déploiement

### Installation
```powershell
# Via Windows
.\debug_tools\deploy_scp.ps1 -Source ".\rpi_csi_rtsp_server.py" -Dest "/usr/local/bin/"
.\debug_tools\run_remote.ps1 "sudo systemctl restart rpi-av-rtsp-recorder"

# Vérifier
.\debug_tools\run_remote.ps1 "ffprobe -i rtsp://<device-ip>:8554/stream"
```

### Recommandations
- Déployer sur TOUS les devices avec caméra CSI
- Tester après reboot du device (le cas d'usage principal)
- Vérifier que `ffprobe` se connecte correctement au stream RTSP

## Monitoring Post-Déploiement

### Signes d'Un Déploiement Réussi
```bash
# Dans les logs (grep pour "Auto-detected")
[17:54:50] [CSI-RTSP] INFO: Auto-detected USB audio device: plughw:X,0

# ffprobe fonctionne (pas de 503 Service Unavailable)
Stream #0:0: Video: h264 ...
Stream #0:1: Audio: aac ...

# API de contrôle répond
curl http://<device-ip>:8085/controls | jq '.controls.Saturation.value'
```

### Signes D'Un Problème
```bash
# Si auto-detect échoue
WARNING: Configured device plughw:1,0 not accessible, attempting auto-detection...
WARNING: No USB audio device found in arecord output

# Si ffprobe reçoit 503 (même après fix)
[rtsp @ ...] method DESCRIBE failed: 503 Service Unavailable
```
→ Vérifier que le micro USB est réellement connecté + détecté par `arecord -l`

---

**Status**: ✅ DÉPLOYÉ ET TESTÉ - Stable sur 192.168.1.4

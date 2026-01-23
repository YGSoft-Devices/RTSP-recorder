# Debug Tools

Outils de débogage pour faciliter le développement et les tests du projet RTSP-Full.

**Ces outils sont conçus pour être utilisés par les humains ET les agents IA.**

**NE PAS HESITER A COMPLETER OU DEBUGGER, MAIS CONSERVER CE DOCUMENT A JOUR !!**

## Prérequis

### Windows (WSL + sshpass)
Les prérequis sont installés automatiquement par `install_device.ps1`.

Pour installation manuelle:
```powershell
wsl --install              # Si WSL non installé (nécessite redémarrage)
wsl sudo apt install sshpass -y
```

Une fois installé, les connexions SSH sont **100% automatiques** (pas de mot de passe interactif).

---

## Outils Windows (PowerShell)

### `install_device.ps1` ⭐ INSTALLATION AUTOMATIQUE (v1.4.0)
Installe automatiquement le projet sur un Raspberry Pi fraîchement flashé.

**Prérequis:** Installés automatiquement si manquants (WSL + sshpass)

```powershell
# Installation complète (demande l'IP)
.\debug_tools\install_device.ps1

# Installation avec IP en paramètre
.\debug_tools\install_device.ps1 192.168.1.124

# Installation avec Meeting API (RECOMMANDÉ)
# - Le hostname sera automatiquement défini sur la DeviceKey
# - Le token sera "brûlé" (validé) après installation réussie
# - La caméra sera auto-détectée et configurée
.\debug_tools\install_device.ps1 192.168.1.124 -DeviceKey "ABC123..." -Token "89915f"

# Sans brûler le token (pour tests répétés)
.\debug_tools\install_device.ps1 192.168.1.124 -DeviceKey "ABC123..." -Token "89915f" -NoBurnToken

# Vérifier la connectivité uniquement
.\debug_tools\install_device.ps1 -IP 192.168.1.124 -CheckOnly

# Transférer les fichiers sans installer
.\debug_tools\install_device.ps1 -IP 192.168.1.124 -SkipInstall

# Surveiller une installation en cours
.\debug_tools\install_device.ps1 -IP 192.168.1.124 -Monitor

# Sans provisionnement interactif
.\debug_tools\install_device.ps1 192.168.1.124 -NoProvision

# Sans reboot automatique à la fin
.\debug_tools\install_device.ps1 192.168.1.124 -NoReboot
```

**Fonctionnalités v1.4.0:**
- ✅ Vérifie et installe automatiquement WSL + sshpass si manquants
- ✅ **Hostname automatiquement défini sur DeviceKey** (plus de paramètre -Hostname séparé)
- ✅ **Token burning automatique** après installation réussie (désactivable via -NoBurnToken)
- ✅ **Détection et configuration automatique de la caméra** (USB ou CSI)
- ✅ Provisionnement optionnel (timezone)
- ✅ Affichage du temps écoulé et de la phase en cours
- ✅ Détection automatique des phases d'installation

**Workflow v1.4.0:**
1. Connexion SSH au device
2. Provisionnement (hostname=DeviceKey, timezone, Meeting API config)
3. Transfert des fichiers du projet
4. Installation (~15-30 min)
5. **Post-installation:** Détection caméra, token burn
6. Reboot automatique (optionnel)

**Durée estimée:** 15-30 minutes sur Pi 3B+

---

### `install_device_gui.ps1` ⭐ GUI (Windows) (v1.0.0)
Interface graphique pour lancer `install_device.ps1` sans modifier le script CLI.

```powershell
.\debug_tools\install_device_gui.ps1
```

Fonctions:
- Génère une commande PowerShell équivalente (bouton "Copier")
- Lance l'installation dans un process séparé
- Affiche les logs stdout/stderr en temps réel

### `package_update.ps1` ⭐ Packaging update (Windows) (v1.0.1)
Génère une archive de mise à jour compatible avec "Update from file".

```powershell
.\debug_tools\package_update.ps1
.\debug_tools\package_update.ps1 -OutputDir ".\dist\updates"
.\debug_tools\package_update.ps1 -OverrideVersion "2.32.99"
.\debug_tools\package_update.ps1 -RequiredPackages "i2c-tools","util-linux-extra" -RequiresReboot
```

Sortie:
- Archive `rpi-cam-update_<version>_<timestamp>.tar.gz` dans le dossier choisi

### `debug_tools_gui.ps1` ⭐ GUI (Windows) (v1.2.8)
Interface graphique **unique** (Windows 10/11 x64) pour lancer la plupart des outils du dossier `debug_tools/`.

```powershell
.\debug_tools\debug_tools_gui.ps1
```

Onglets:
- Meeting/IP (édition de `meeting_config.json`)
- Install (lance `install_device.ps1` + bouton pour `install_device_gui.ps1`)
- Run remote (lance `run_remote.ps1`)
- Deploy (SCP) (lance `deploy_scp.ps1`)
- Update (lance `update_device.ps1`)
- SSH (lance `ssh_device.ps1`)
- Logs/Diag (lance `get_logs.ps1`)
- Config (lance `config_tool.ps1`)
- Stop services (helper `stop_services.sh` via `deploy_scp.ps1` + `run_remote.ps1`)

Fonctions:
- Assistant au démarrage (DeviceKey → IP via Meeting, sinon IP obligatoire)
- Champ **Token (optionnel)** dans l'assistant (lookup Meeting possible sans token si l'API l'autorise)
- Mémoire locale des devices (DeviceKey/IP + status online/offline) dans `debug_tools/device_memory.json`
- Bouton **Ouvrir SSH (fenetre)** dans l'onglet SSH
- Onglet Config: bouton **Récupérer paramètres**

### `config_tool.ps1` ⭐ NOUVEAU v1.0.0 - Configuration globale
Outil IA pour modifier **tous les parametres** du projet (config.env + JSON dans `/etc/rpi-cam`).

**Utilisation:**
```powershell
# Lister config.env
.\debug_tools\config_tool.ps1 -Action list -File "/etc/rpi-cam/config.env"

# Lire une cle
.\debug_tools\config_tool.ps1 -Action get -File "/etc/rpi-cam/config.env" -Key "RTSP_PORT"

# Modifier une cle
.\debug_tools\config_tool.ps1 -Action set -File "/etc/rpi-cam/config.env" -Key "RTSP_PORT" -Value "8554"

# JSON: lire / modifier
.\debug_tools\config_tool.ps1 -Action get -File "/etc/rpi-cam/wifi_failover.json" -JsonPath "backup_ssid"
.\debug_tools\config_tool.ps1 -Action set -File "/etc/rpi-cam/wifi_failover.json" -JsonPath "backup_ssid" -Value "MySSID"

# Export / Import
.\debug_tools\config_tool.ps1 -Action export -File "/etc/rpi-cam/config.env" -OutputFile ".\\config.env"
.\debug_tools\config_tool.ps1 -Action import -File "/etc/rpi-cam/config.env" -InputFile ".\\config.env"
```

**Notes:**
- Backups automatiques sur le device (suffixe `.bak-YYYYmmddHHMMSS`)
- Compatible Meeting `-Auto` (DeviceKey/Token/ApiUrl optionnels)

### `update_device.ps1` ⭐ v2.0.1 - Update rapide
Outil IA pour mettre a jour **rapidement** les fichiers du projet sur un device deja installe (sans reinstall).

**Utilisation:**
```powershell
# Mise a jour via IP directe
.\debug_tools\update_device.ps1 -IP "192.168.1.202"

# Mise a jour via Meeting (DeviceKey + Token)
.\debug_tools\update_device.ps1 -DeviceKey "ABC123..." -Token "89915f"

# Meeting sans token (si l'API l'autorise)
.\debug_tools\update_device.ps1 -DeviceKey "ABC123..."

# Dry run (aucune action)
.\debug_tools\update_device.ps1 -DeviceKey "ABC123..." -DryRun

# Sans restart des services
.\debug_tools\update_device.ps1 -DeviceKey "ABC123..." -NoRestart
```

**Notes:**
- Update rapide: stop services → deploy fichiers → requirements → restart
- Configuration `/etc/rpi-cam` preservée

### `run_remote.ps1` ⭐ RECOMMANDÉ POUR LES AGENTS IA
Exécute une commande sur le device sans interaction utilisateur.

```powershell
# Commande simple
.\debug_tools\run_remote.ps1 "hostname"

# Commande avec sudo
.\debug_tools\run_remote.ps1 "sudo systemctl status rpi-cam-webmanager"

# Status de tous les services
.\debug_tools\run_remote.ps1 "systemctl is-active rpi-cam-webmanager rpi-av-rtsp-recorder"

# Voir les logs
.\debug_tools\run_remote.ps1 "sudo journalctl -u rpi-cam-webmanager -n 20"

# Via WiFi (192.168.1.127)
.\debug_tools\run_remote.ps1 -Wifi "hostname"

# IP personnalisée
.\debug_tools\run_remote.ps1 -IP "192.168.1.124" "hostname"

# Auto-détection IP via Meeting API (nouveau v1.2.0)
.\debug_tools\run_remote.ps1 -Auto "hostname"

# Avec timeout personnalisé (défaut: 30s)
.\debug_tools\run_remote.ps1 -Timeout 60 "commande longue"
```

### `deploy_scp.ps1`
Déploiement de fichiers via SCP avec redémarrage automatique du service.

**Fonctionnalités v1.4.0:**
- ✅ Destinations protégées (`/opt/*`, `/etc/*`) automatiquement gérées via `/tmp` + `sudo cp`
- ✅ Détection automatique des fichiers frontend (.js, .css, .html)
- ✅ Redémarrage automatique de `rpi-cam-webmanager` pour les fichiers web
- ✅ Détection des fichiers Python pour redémarrage
- ✅ Option `-NoRestart` pour désactiver le redémarrage automatique
- ✅ **Option `-Auto` pour auto-détection IP via Meeting API** (nouveau)

```powershell
# Déployer un fichier (destinations /opt/* automatiquement gérées)
.\debug_tools\deploy_scp.ps1 -Source ".\app.py" -Dest "/opt/rpi-cam-webmanager/"

# Déployer avec auto-détection IP via Meeting API
.\debug_tools\deploy_scp.ps1 -Source ".\app.py" -Dest "/opt/rpi-cam-webmanager/" -Auto

# Déployer un fichier frontend (redémarre automatiquement le service)
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\static\css\style.css" -Dest "/opt/rpi-cam-webmanager/static/css/" -UseWifi

# Déployer sans redémarrer le service
.\debug_tools\deploy_scp.ps1 -Source ".\file.js" -Dest "/opt/rpi-cam-webmanager/static/js/" -NoRestart

# Déployer un dossier entier
.\debug_tools\deploy_scp.ps1 -Source ".\web-manager\*" -Dest "/opt/rpi-cam-webmanager/" -Recursive

# Mode dry-run (test sans transfert)
.\debug_tools\deploy_scp.ps1 -Source ".\file.txt" -Dest "/tmp/" -DryRun

# Via WiFi
.\debug_tools\deploy_scp.ps1 -Source ".\file.txt" -Dest "/tmp/" -UseWifi
```

### `ssh_device.ps1`
Connexion SSH interactive au device.

```powershell
# Connexion interactive
.\debug_tools\ssh_device.ps1

# Exécuter une commande unique
.\debug_tools\ssh_device.ps1 -Command "ls -la"

# Via WiFi
.\debug_tools\ssh_device.ps1 -UseWifi
```

### `Get-DeviceIP.ps1` ⭐ NOUVEAU v1.0.0
Module PowerShell pour récupérer l'IP du device via l'API Meeting.

**Configuration:**
Copier `meeting_config.example.json` en `meeting_config.json` et remplir:
```json
{
    "api_url": "https://meeting.ygsoft.fr/api",
    "device_key": "VOTRE_DEVICE_KEY",
    "token_code": "VOTRE_TOKEN_CODE"
}
```

**Utilisation directe:**
```powershell
# Charger le module
. .\debug_tools\Get-DeviceIP.ps1

# Récupérer l'IP depuis Meeting API
$ip = Get-DeviceIPFromMeeting

# Trouver l'IP accessible (Meeting + IPs connues)
$ip = Find-DeviceIP

# Tester la connectivité
Test-DeviceConnection -IP "192.168.1.202"
```

### `get_logs.ps1` ⭐ v1.1.0 - Boite à outils de déboggage (logs + diagnostics)
Outil complet pour récupérer les logs **et** exécuter des diagnostics rapides (réseau, RTSP, caméra, audio, dmesg, status services).

**Utilisation:**
```powershell
# Logs (affichage console)
.\debug_tools\get_logs.ps1

# Logs d'un service spécifique
.\debug_tools\get_logs.ps1 -Service "rpi-av-rtsp-recorder"

# Dernières N lignes
.\debug_tools\get_logs.ps1 -Lines 500

# Suivi en temps réel (tail -f)
.\debug_tools\get_logs.ps1 -Service "rpi-cam-webmanager" -Follow

# Export ZIP logs + diagnostics (recommandé)
.\debug_tools\get_logs.ps1 -Tool collect -OutputDir "./logs_backup"

# Diagnostics rapides
.\debug_tools\get_logs.ps1 -Tool status
.\debug_tools\get_logs.ps1 -Tool rtsp
.\debug_tools\get_logs.ps1 -Tool camera
.\debug_tools\get_logs.ps1 -Tool audio
.\debug_tools\get_logs.ps1 -Tool network
.\debug_tools\get_logs.ps1 -Tool dmesg -Lines 200

# Combiner options
.\debug_tools\get_logs.ps1 -Service "rpi-av-rtsp-recorder" -Lines 100 -IP "192.168.1.124"

# Via WiFi
.\debug_tools\get_logs.ps1 -UseWifi -Service "rtsp-watchdog"

# Auto-détection IP via Meeting API (DeviceKey optionnelle)
.\debug_tools\get_logs.ps1 -Auto
.\debug_tools\get_logs.ps1 -Auto -DeviceKey "ABC123..."
.\debug_tools\get_logs.ps1 -Auto -DeviceKey "ABC123..." -Token "89915f" -ApiUrl "https://meeting.ygsoft.fr/api"
```

**Services supportés:**
- `rpi-av-rtsp-recorder` - Serveur RTSP CSI
- `rpi-cam-webmanager` - Interface web Flask
- `rtsp-recorder` - Enregistrements ffmpeg
- `rtsp-watchdog` - Watchdog haute disponibilité
- `rpi-cam-onvif` - Serveur ONVIF

**Résultat `-Tool collect -OutputDir`:**
- Archive ZIP contenant:
  - Logs systemd de chaque service (500 dernières lignes)
  - Fichiers de log locaux (/var/log/rpi-cam/*)
  - `diagnostics.txt` (réseau, RTSP, erreurs systemd, dmesg, etc.)
  - Timestamp dans le nom: `device-logs_2026-01-20_183045.zip`

### `get-log.ps1` (alias)
Alias compat pour `get_logs.ps1`.
```powershell
.\debug_tools\get-log.ps1 -Auto -DeviceKey "ABC123..." -Tool collect -OutputDir "./logs_backup"
```

**Utilisation avec les autres scripts:**
```powershell
# Auto-détection dans run_remote.ps1
.\debug_tools\run_remote.ps1 -Auto "hostname"

# Auto-détection dans deploy_scp.ps1
.\debug_tools\deploy_scp.ps1 -Source ".\file.py" -Dest "/opt/..." -Auto
```

---

## Outils Raspberry Pi (Bash)

### `stop_services.sh`
Arrête/démarre tous les services du projet pour libérer la caméra et les ressources.

**Déploiement initial:**
```powershell
.\debug_tools\deploy_scp.ps1 -Source ".\debug_tools\stop_services.sh" -Dest "/tmp/"
.\debug_tools\run_remote.ps1 "chmod +x /tmp/stop_services.sh"
```

**Utilisation:**
```bash
# Arrêter tous les services (libère la caméra)
sudo /tmp/stop_services.sh

# Afficher le status des services et de la caméra
sudo /tmp/stop_services.sh --status

# Redémarrer les services
sudo /tmp/stop_services.sh --start

# Redémarrage complet (stop + start)
sudo /tmp/stop_services.sh --restart
```

**Depuis Windows:**
```powershell
# Arrêter
.\debug_tools\run_remote.ps1 "sudo /tmp/stop_services.sh"

# Status
.\debug_tools\run_remote.ps1 "sudo /tmp/stop_services.sh --status"

# Redémarrer
.\debug_tools\run_remote.ps1 "sudo /tmp/stop_services.sh --start"
```

---

## Configuration

Les scripts utilisent les paramètres par défaut du projet:

| Paramètre | Valeur | Description |
|-----------|--------|-------------|
| IP Ethernet | 192.168.1.202 | eth0 |
| IP WiFi wlan1 | 192.168.1.124 | Interface WiFi primaire |
| IP WiFi wlan0 | 192.168.1.127 | Interface WiFi secondaire |
| User | device | Utilisateur SSH |
| Password | meeting | Mot de passe SSH |

**Auto-détection (nouveau):**
Avec l'option `-Auto`, les scripts interrogent l'API Meeting pour obtenir l'IP actuelle du device, puis testent la connectivité sur les IPs connues.

Ces valeurs peuvent être modifiées via les paramètres des scripts ou le fichier `meeting_config.json`.

---

## Services gérés

| Service | Description |
|---------|-------------|
| `rpi-cam-webmanager` | Interface web Flask |
| `rpi-av-rtsp-recorder` | Serveur RTSP GStreamer |
| `rtsp-recorder` | Enregistrement ffmpeg |
| `rtsp-watchdog` | Watchdog haute disponibilité |
| `rpi-cam-onvif` | Serveur ONVIF |
| `rtsp-camera-recovery` | Récupération caméra USB |

---

*Version: 1.4.8*

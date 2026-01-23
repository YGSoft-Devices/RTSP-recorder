# install_device.ps1 - Installation automatique du projet sur un Raspberry Pi
# Version: 1.4.2
#
# Ce script déploie et installe automatiquement le projet RTSP-Full sur un device
# depuis Windows. Il vérifie et installe automatiquement les prérequis (WSL, sshpass).
#
# Usage:
#   .\debug_tools\install_device.ps1 192.168.1.124 -DeviceKey "XXX" -Token "YYY"  # Installation complète
#   .\debug_tools\install_device.ps1 192.168.1.124                                # Sans Meeting API
#   .\debug_tools\install_device.ps1 -Help              # Aide
#   .\debug_tools\install_device.ps1 -Monitor           # Surveiller installation en cours
#
# IMPORTANT: Quand DeviceKey est fournie, elle devient automatiquement le hostname.
#
# Prérequis (installés automatiquement si manquants):
#   - WSL (Windows Subsystem for Linux)
#   - sshpass dans WSL
#
# Étapes effectuées:
#   1. Vérification/Installation des prérequis (WSL, sshpass)
#   2. Vérification de la connectivité SSH
#   3. Provisionnement (hostname = DeviceKey si fournie, timezone)
#   4. Configuration Meeting API (devicekey, token) si fournie
#   5. Transfert des fichiers du projet via SCP
#   6. Nettoyage des locks apt si nécessaire
#   7. Lancement de l'installation en arrière-plan
#   8. Surveillance de l'avancement avec temps écoulé
#   9. Token burning via API Meeting (consomme un token)
#  10. Détection et configuration automatique de la caméra
#  11. Reboot automatique à la fin (sauf si -NoReboot)
#  12. Affichage du statut final
#
# Durée estimée: 15-30 minutes sur un Pi 3B+ fraîchement flashé

param(
    [Parameter(Position=0)]
    [string]$IP,
    
    [switch]$Help,
    [switch]$CheckOnly,
    [switch]$SkipInstall,
    [switch]$Monitor,
    [string]$Timezone = "Europe/Paris",
    [switch]$NoProvision,
    [string]$User = "device",
    [string]$Password = "meeting",
    [int]$Timeout = 10,
    
    # Meeting API Provisioning (DeviceKey becomes hostname automatically)
    [string]$DeviceKey,
    [string]$Token,
    [string]$MeetingApiUrl = "https://meeting.ygsoft.fr/api",
    
    # Auto-reboot
    [switch]$NoReboot,
    
    # Skip token burning (for testing)
    [switch]$NoBurnToken
)

# ============================================================================
# Configuration
# ============================================================================
$script:ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$script:RemoteTempDir = "/tmp/rtsp-full-install"
$script:RemoteInstallDir = "/opt/rtsp-full"
$script:StartTime = $null
$script:CurrentPhase = ""
$script:PhaseStartTime = $null

# Fichiers/dossiers à transférer
$FilesToTransfer = @(
    "VERSION",
    "rpi_av_rtsp_recorder.sh",
    "rpi_csi_rtsp_server.py",
    "rtsp_recorder.sh",
    "rtsp_watchdog.sh",
    "setup",
    "onvif-server",
    "web-manager",
    "scripts"
)

# ============================================================================
# Fonctions utilitaires - Affichage
# ============================================================================
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║ " -ForegroundColor Cyan -NoNewline
    Write-Host $Text.PadRight(62) -ForegroundColor White -NoNewline
    Write-Host " ║" -ForegroundColor Cyan
    Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-SubHeader {
    param([string]$Text, [string]$Duration = "")
    Write-Host ""
    Write-Host "┌────────────────────────────────────────────────────────────────┐" -ForegroundColor DarkCyan
    $displayText = if ($Duration) { "$Text ($Duration)" } else { $Text }
    Write-Host "│ " -ForegroundColor DarkCyan -NoNewline
    Write-Host $displayText.PadRight(62) -ForegroundColor Cyan -NoNewline
    Write-Host " │" -ForegroundColor DarkCyan
    Write-Host "└────────────────────────────────────────────────────────────────┘" -ForegroundColor DarkCyan
}

function Write-Step {
    param([string]$Text, [string]$Status = "...")
    $elapsed = Get-ElapsedTime
    $prefix = if ($elapsed) { "[$elapsed] " } else { "" }
    
    Write-Host "${prefix}[" -NoNewline -ForegroundColor DarkGray
    switch ($Status) {
        "OK"    { Write-Host "OK" -ForegroundColor Green -NoNewline }
        "FAIL"  { Write-Host "!!" -ForegroundColor Red -NoNewline }
        "SKIP"  { Write-Host "--" -ForegroundColor Yellow -NoNewline }
        "WAIT"  { Write-Host ".." -ForegroundColor Cyan -NoNewline }
        "..."   { Write-Host ".." -ForegroundColor Gray -NoNewline }
        default { Write-Host $Status -ForegroundColor Gray -NoNewline }
    }
    Write-Host "] $Text"
}

function Write-Info {
    param([string]$Text)
    Write-Host "        $Text" -ForegroundColor DarkGray
}

function Write-Progress-Bar {
    param(
        [int]$Percent,
        [string]$Label = "",
        [int]$Width = 40
    )
    
    $filled = [math]::Floor($Width * $Percent / 100)
    $empty = $Width - $filled
    
    $bar = ([char]9608).ToString() * $filled + ([char]9617).ToString() * $empty
    $color = if ($Percent -lt 30) { "Red" } elseif ($Percent -lt 70) { "Yellow" } else { "Green" }
    
    Write-Host "`r        [$bar] $Percent% $Label    " -NoNewline -ForegroundColor $color
}

function Get-ElapsedTime {
    if ($null -eq $script:StartTime) { return "" }
    $elapsed = (Get-Date) - $script:StartTime
    return "{0:mm}:{0:ss}" -f $elapsed
}

function Get-PhaseElapsedTime {
    if ($null -eq $script:PhaseStartTime) { return "" }
    $elapsed = (Get-Date) - $script:PhaseStartTime
    return "{0:mm}:{0:ss}" -f $elapsed
}

function Start-Phase {
    param([string]$Name)
    $script:CurrentPhase = $Name
    $script:PhaseStartTime = Get-Date
}

function Format-Duration {
    param([int]$Seconds)
    if ($Seconds -lt 60) { return "${Seconds}s" }
    $min = [math]::Floor($Seconds / 60)
    $sec = $Seconds % 60
    return "${min}m ${sec}s"
}

function Show-Help {
    Write-Host @"

+================================================================+
|     RTSP-Full - Installation automatique sur Raspberry Pi      |
|                        Version 1.4.0                           |
+================================================================+

USAGE:
    .\install_device.ps1 [IP] [OPTIONS]

PARAMETRES:
    IP                  Adresse IP du Raspberry Pi (ex: 192.168.1.124)

OPTIONS GENERALES:
    -Help               Affiche cette aide
    -CheckOnly          Verifie la connectivite sans installer
    -SkipInstall        Transfere les fichiers sans lancer l'installation
    -Monitor            Surveille une installation en cours
    -NoReboot           Ne pas redemarrer automatiquement apres l'installation

OPTIONS DE PROVISIONNEMENT:
    -Timezone <tz>      Definit le fuseau horaire (defaut: Europe/Paris)
    -NoProvision        Desactive le provisionnement interactif

OPTIONS MEETING API (RECOMMANDE):
    -DeviceKey <key>    Cle du device Meeting (devient automatiquement le hostname)
    -Token <token>      Token d'authentification Meeting (sera brule apres install)
    -MeetingApiUrl <u>  URL de l'API Meeting (defaut: https://meeting.ygsoft.fr/api)
    -NoBurnToken        Ne pas bruler le token (pour tests)

OPTIONS SSH:
    -User <user>        Nom d'utilisateur SSH (defaut: device)
    -Password <pass>    Mot de passe SSH (defaut: meeting)
    -Timeout <sec>      Timeout connexion en secondes (defaut: 10)

EXEMPLES:
    # Installation complete avec Meeting API (RECOMMANDE)
    .\install_device.ps1 192.168.1.124 -DeviceKey "BB78EFB24186E95CDAB3EE82708999A8" -Token "89915f"

    # Installation sans Meeting API
    .\install_device.ps1 192.168.1.124

    # Sans reboot automatique
    .\install_device.ps1 192.168.1.124 -DeviceKey "XXX" -Token "YYY" -NoReboot

    # Verifier la connectivite uniquement
    .\install_device.ps1 -IP 192.168.1.124 -CheckOnly

    # Surveiller une installation en cours
    .\install_device.ps1 -IP 192.168.1.124 -Monitor

IMPORTANT:
    - Quand DeviceKey est fournie, elle devient automatiquement le hostname
    - Le token est brule (consomme) apres une installation reussie
    - La camera est detectee automatiquement pour un fonctionnement out-of-the-box

PREREQUIS (installes automatiquement):
    - WSL (Windows Subsystem for Linux)
    - sshpass dans WSL

DUREES ESTIMEES:
    - Prerequis WSL/sshpass : ~1-5 minutes (si installation necessaire)
    - Transfert des fichiers : ~2 minutes
    - Installation GStreamer : ~10 minutes
    - Installation services  : ~5-10 minutes
    - Reboot final           : ~30 secondes
    - TOTAL                  : ~15-30 minutes

"@
}

# ============================================================================
# Fonctions - Prérequis
# ============================================================================
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-WSL {
    Write-SubHeader "Verification de WSL" "~2-5 min si install"
    
    Write-Step "Verification de WSL"
    
    # Vérifier si WSL est disponible
    $wslInstalled = Get-Command wsl -ErrorAction SilentlyContinue
    
    if ($wslInstalled) {
        # Vérifier si une distribution est installée
        try {
            $distros = wsl --list --quiet 2>$null
            if ($distros -and $distros.Trim()) {
                Write-Step "WSL est installe et configure" "OK"
                return $true
            }
        } catch {
            # WSL existe mais pas de distro
        }
    }
    
    Write-Step "WSL non configure - installation requise" "WAIT"
    Write-Info "Cette operation necessite les droits administrateur"
    
    if (-not (Test-Administrator)) {
        Write-Host ""
        Write-Host "+================================================================+" -ForegroundColor Yellow
        Write-Host "|  ATTENTION: Installation de WSL requise                        |" -ForegroundColor Yellow
        Write-Host "+================================================================+" -ForegroundColor Yellow
        Write-Host "|  WSL n'est pas installe ou configure.                          |" -ForegroundColor Yellow
        Write-Host "|                                                                |" -ForegroundColor Yellow
        Write-Host "|  Pour l'installer, executez dans un PowerShell ADMINISTRATEUR: |" -ForegroundColor Yellow
        Write-Host "|                                                                |" -ForegroundColor Yellow
        Write-Host "|    wsl --install                                               |" -ForegroundColor Cyan
        Write-Host "|                                                                |" -ForegroundColor Yellow
        Write-Host "|  Puis redemarrez votre ordinateur et relancez ce script.       |" -ForegroundColor Yellow
        Write-Host "+================================================================+" -ForegroundColor Yellow
        Write-Host ""
        
        $response = Read-Host "Voulez-vous ouvrir un PowerShell administrateur maintenant? (o/N)"
        if ($response -eq 'o' -or $response -eq 'O') {
            Start-Process powershell -Verb RunAs -ArgumentList "-NoExit", "-Command", "wsl --install"
            Write-Host "PowerShell administrateur ouvert. Apres l'installation et le redemarrage, relancez ce script." -ForegroundColor Cyan
        }
        return $false
    }
    
    # Si on est admin, installer WSL
    Write-Step "Installation de WSL en cours..." "WAIT"
    Write-Info "Cela peut prendre plusieurs minutes..."
    
    try {
        $process = Start-Process -FilePath "wsl" -ArgumentList "--install", "--no-launch" -Wait -PassThru -NoNewWindow
        if ($process.ExitCode -eq 0) {
            Write-Step "WSL installe - redemarrage requis" "OK"
            Write-Host ""
            Write-Host "IMPORTANT: Redemarrez votre ordinateur puis relancez ce script." -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Step "Erreur lors de l'installation de WSL" "FAIL"
        Write-Info $_.Exception.Message
        return $false
    }
    
    return $false
}

function Install-Sshpass {
    Write-Step "Verification de sshpass dans WSL"
    
    try {
        $check = wsl which sshpass 2>$null
        if ($check -and $check.Trim()) {
            Write-Step "sshpass est installe" "OK"
            return $true
        }
    } catch {
        # sshpass non trouvé
    }
    
    Write-Step "Installation de sshpass dans WSL" "WAIT"
    Write-Info "Mise a jour apt et installation..."
    
    # Installer sshpass
    try {
        wsl bash -c "sudo apt-get update -qq && sudo apt-get install -y -qq sshpass" 2>&1 | Out-Null
        
        # Vérifier l'installation
        $check = wsl which sshpass 2>$null
        if ($check -and $check.Trim()) {
            Write-Step "sshpass installe avec succes" "OK"
            return $true
        } else {
            Write-Step "Echec de l'installation de sshpass" "FAIL"
            Write-Info "Essayez manuellement: wsl sudo apt install sshpass"
            return $false
        }
    } catch {
        Write-Step "Erreur installation sshpass" "FAIL"
        Write-Info $_.Exception.Message
        return $false
    }
}

function Test-Prerequisites {
    Write-SubHeader "Verification des prerequis" "~30s"
    Start-Phase "prerequisites"
    
    # Vérifier/Installer WSL
    if (-not (Install-WSL)) {
        return $false
    }
    
    # Vérifier/Installer sshpass
    if (-not (Install-Sshpass)) {
        return $false
    }
    
    Write-Step "Tous les prerequis sont satisfaits" "OK"
    return $true
}

# ============================================================================
# Fonctions - SSH et Remote
# ============================================================================
function Invoke-RemoteCommand {
    param(
        [string]$Command,
        [switch]$Silent,
        [switch]$ReturnOutput
    )
    
    $SshOptions = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=$Timeout"
    $EscapedCmd = $Command -replace "'", "'\\''"
    $WslCmd = "sshpass -p '$Password' ssh $SshOptions $User@$IP '$EscapedCmd'"
    
    if ($ReturnOutput) {
        $output = wsl bash -c $WslCmd 2>&1
        return @{
            Output = $output
            ExitCode = $LASTEXITCODE
        }
    } else {
        if ($Silent) {
            wsl bash -c $WslCmd 2>&1 | Out-Null
        } else {
            wsl bash -c $WslCmd
        }
        return $LASTEXITCODE
    }
}

function Test-DeviceConnectivity {
    Write-SubHeader "Test de connectivite" "~10s"
    Start-Phase "connectivity"
    
    Write-Step "Connexion SSH vers $IP" "WAIT"
    
    $result = Invoke-RemoteCommand -Command "echo 'OK'" -ReturnOutput
    
    if ($result.ExitCode -eq 0 -and $result.Output -match "OK") {
        Write-Step "Connexion SSH etablie" "OK"
        
        # Récupérer infos device
        $hostname = (Invoke-RemoteCommand -Command "hostname" -ReturnOutput).Output
        $model = (Invoke-RemoteCommand -Command "cat /proc/device-tree/model 2>/dev/null | tr -d '\0'" -ReturnOutput).Output
        $uptime = (Invoke-RemoteCommand -Command "uptime -p 2>/dev/null || uptime" -ReturnOutput).Output
        
        Write-Info "Hostname actuel: $($hostname.Trim())"
        if ($model) { Write-Info "Modele: $($model.Trim())" }
        Write-Info "Uptime: $($uptime.Trim())"
        
        return $true
    } else {
        Write-Step "Connexion SSH impossible" "FAIL"
        Write-Info "Verifiez:"
        Write-Info "  - L'adresse IP ($IP) est correcte"
        Write-Info "  - Le Pi est allume et connecte au reseau"
        Write-Info "  - Les credentials (user: $User, pass: $Password)"
        return $false
    }
}

# ============================================================================
# Fonctions - Provisionnement
# ============================================================================
function Invoke-Provisioning {
    Write-SubHeader "Provisionnement du device" "~20s"
    Start-Phase "provision"
    
    # Si DeviceKey est fournie, elle devient automatiquement le hostname
    $newHostname = $null
    if ($DeviceKey) {
        $newHostname = $DeviceKey
        Write-Step "Hostname sera: $DeviceKey (= DeviceKey)" "..."
    }
    
    $newTimezone = $Timezone
    
    # Appliquer le hostname si fourni (DeviceKey)
    if ($newHostname) {
        Write-Step "Configuration du hostname: $newHostname" "WAIT"
        
        $result = Invoke-RemoteCommand -Command "sudo hostnamectl set-hostname '$newHostname'" -ReturnOutput
        if ($result.ExitCode -eq 0) {
            # Mettre à jour /etc/hosts aussi
            Invoke-RemoteCommand -Command "sudo sed -i 's/127.0.1.1.*/127.0.1.1\t$newHostname/' /etc/hosts" -Silent
            Write-Step "Hostname configure: $newHostname" "OK"
        } else {
            Write-Step "Erreur configuration hostname" "FAIL"
        }
    } else {
        Write-Step "Hostname: conserve (pas de DeviceKey)" "SKIP"
    }
    
    # Configurer le timezone
    Write-Step "Configuration timezone: $newTimezone" "WAIT"
    Invoke-RemoteCommand -Command "sudo timedatectl set-timezone '$newTimezone' 2>/dev/null || true" -Silent
    Write-Step "Timezone configure: $newTimezone" "OK"
    
    # Synchroniser l'heure
    Write-Step "Synchronisation NTP" "WAIT"
    Invoke-RemoteCommand -Command "sudo timedatectl set-ntp true 2>/dev/null || true" -Silent
    Write-Step "NTP active" "OK"
    
    return $true
}

function Invoke-MeetingProvisioning {
    if (-not $DeviceKey -or -not $Token) {
        Write-Step "Configuration Meeting API: non fournie" "SKIP"
        return $true
    }
    
    Write-SubHeader "Configuration Meeting API" "~10s"
    Start-Phase "meeting"
    
    $deviceKeyPreview = if ($DeviceKey.Length -gt 8) { "$($DeviceKey.Substring(0, 8))..." } else { $DeviceKey }
    Write-Step "DeviceKey: $deviceKeyPreview" "..."
    Write-Step "Token: $Token" "..."
    Write-Step "API URL: $MeetingApiUrl" "..."
    
    # Créer le répertoire de configuration sur le device
    Write-Step "Creation du repertoire de configuration" "WAIT"
    Invoke-RemoteCommand -Command "sudo mkdir -p /etc/rpi-cam" -Silent
    
    # Créer le fichier meeting.json
    Write-Step "Configuration de l'API Meeting" "WAIT"
    
    # Créer le JSON et l'encoder en base64 pour éviter les problèmes d'échappement
    $jsonContent = @"
{
    "enabled": true,
    "api_url": "$MeetingApiUrl",
    "device_key": "$DeviceKey",
    "token_code": "$Token",
    "heartbeat_interval": 30,
    "auto_connect": true,
    "provisioned": true
}
"@
    # Encoder en base64 pour transmission sans problème d'échappement
    $jsonBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($jsonContent))
    $bashCommand = "echo $jsonBase64 | base64 -d | sudo tee /etc/rpi-cam/meeting.json > /dev/null && sudo chmod 644 /etc/rpi-cam/meeting.json"
    
    $result = Invoke-RemoteCommand -Command $bashCommand -ReturnOutput
    if ($result.ExitCode -eq 0) {
        Write-Step "Fichier meeting.json cree" "OK"
    } else {
        Write-Step "Erreur creation meeting.json" "FAIL"
        return $false
    }
    
    # Ajouter aussi les variables dans config.env si le fichier existe
    Write-Step "Mise a jour de config.env" "WAIT"
    $configEnvUpdate = @"
# Meeting API Configuration (ajouté par install_device.ps1)
MEETING_ENABLED=yes
MEETING_API_URL=$MeetingApiUrl
MEETING_DEVICE_KEY=$DeviceKey
MEETING_TOKEN_CODE=$Token
MEETING_PROVISIONED=yes
# Recording Configuration (enabled by default)
RECORD_ENABLE=yes
"@
    
    $escapedConfigEnv = $configEnvUpdate -replace '"', '\"'
    
    # Vérifier si config.env existe, sinon le créer
    Invoke-RemoteCommand -Command "if [ ! -f /etc/rpi-cam/config.env ]; then sudo touch /etc/rpi-cam/config.env; fi" -Silent
    
    # Supprimer les anciennes entrées MEETING_* et RECORD_ENABLE si elles existent
    Invoke-RemoteCommand -Command "sudo sed -i '/^MEETING_/d' /etc/rpi-cam/config.env 2>/dev/null || true" -Silent
    Invoke-RemoteCommand -Command "sudo sed -i '/^# Meeting API/d' /etc/rpi-cam/config.env 2>/dev/null || true" -Silent
    Invoke-RemoteCommand -Command "sudo sed -i '/^RECORD_ENABLE=/d' /etc/rpi-cam/config.env 2>/dev/null || true" -Silent
    Invoke-RemoteCommand -Command "sudo sed -i '/^# Recording Configuration/d' /etc/rpi-cam/config.env 2>/dev/null || true" -Silent
    
    # Ajouter les nouvelles entrées
    Invoke-RemoteCommand -Command "echo '$escapedConfigEnv' | sudo tee -a /etc/rpi-cam/config.env > /dev/null" -Silent
    Write-Step "Variables Meeting et Recording ajoutees a config.env" "OK"
    
    Write-Host ""
    Write-Host "  [OK] Meeting API et Recording configure avec succes" -ForegroundColor Green
    Write-Host "       Le device pourra se connecter a l'API apres l'installation" -ForegroundColor DarkGray
    
    return $true
}
# ============================================================================
# Fonctions - Token Burning (Post-installation)
# ============================================================================
function Invoke-TokenBurn {
    param(
        [Parameter(Mandatory=$true)]
        [string]$DeviceKey,
        
        [Parameter(Mandatory=$true)]
        [string]$Token,
        
        [Parameter(Mandatory=$false)]
        [string]$MeetingApiUrl = "https://meeting.ygsoft.fr/api"
    )
    
    Write-SubHeader "Validation du Token (Burn)" "~5 sec"
    
    Write-Step "Appel API flash-request"
    
    try {
        # Construire l'URL
        $url = "$MeetingApiUrl/devices/$DeviceKey/flash-request"
        
        # Headers avec le token
        $headers = @{
            "X-Token-Code" = $Token
            "Content-Type" = "application/json"
            "Accept" = "application/json"
        }
        
        # Body vide (l'API n'a besoin que du token en header)
        $body = @{} | ConvertTo-Json
        
        # Appel API
        $response = Invoke-RestMethod -Uri $url -Method POST -Headers $headers -Body $body -TimeoutSec 30
        
        Write-Step "Token brule avec succes" "OK"
        Write-Host ""
        Write-Host "  [OK] Token $Token valide et brule sur l'API Meeting" -ForegroundColor Green
        Write-Host "       Le device est maintenant provisionne officiellement" -ForegroundColor DarkGray
        
        return $true
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $errorMessage = $_.Exception.Message
        
        if ($statusCode -eq 404) {
            Write-Step "DeviceKey non trouve sur l'API" "FAIL"
            Write-Host "  [!] La DeviceKey '$DeviceKey' n'existe pas sur l'API Meeting" -ForegroundColor Red
        }
        elseif ($statusCode -eq 401 -or $statusCode -eq 403) {
            Write-Step "Token invalide ou deja utilise" "FAIL"
            Write-Host "  [!] Le token '$Token' est invalide ou a deja ete utilise" -ForegroundColor Red
        }
        elseif ($statusCode -eq 400) {
            Write-Step "Requete invalide" "FAIL"
            Write-Host "  [!] Requete invalide: $errorMessage" -ForegroundColor Red
        }
        else {
            Write-Step "Erreur API: $errorMessage" "FAIL"
            Write-Host "  [!] Erreur lors de l'appel API: $errorMessage" -ForegroundColor Red
        }
        
        Write-Host ""
        Write-Host "  Le token n'a pas ete brule. Vous pouvez:" -ForegroundColor Yellow
        Write-Host "    1. Verifier la DeviceKey et le Token" -ForegroundColor Gray
        Write-Host "    2. Reessayer manuellement via l'interface web" -ForegroundColor Gray
        Write-Host "    3. Continuer sans validation (le device fonctionnera)" -ForegroundColor Gray
        
        return $false
    }
}

# ============================================================================
# Fonctions - Detection Camera (Post-installation)
# ============================================================================
function Invoke-CameraDetection {
    Write-SubHeader "Detection de la camera" "~10 sec"
    
    $cameraType = "none"
    $cameraDevice = ""
    $cameraInfo = ""
    
    # 1. Detecter camera USB via v4l2-ctl
    # On cherche spécifiquement les caméras USB (pas les encoders bcm2835)
    Write-Step "Recherche camera USB (v4l2)"
    
    # Trouver une camera USB (grep -A1 affiche la ligne suivante avec le device)
    $result = Invoke-RemoteCommand -Command "v4l2-ctl --list-devices 2>/dev/null | grep -A1 'usb-' | head -2" -ReturnOutput
    
    if ($result.ExitCode -eq 0 -and $result.Output -match "/dev/video") {
        # Parser les 2 lignes: nom camera + device
        $lines = $result.Output -split "`n" | Where-Object { $_.Trim() -ne "" }
        if ($lines.Count -ge 2) {
            # Ligne 1: "Microsoft® LifeCam HD-5000: Mi (usb-3f980000.usb-1.4):"
            $cameraInfo = ($lines[0] -replace '\s*\(usb-[^)]+\):\s*$', '').Trim()
            # Ligne 2: "        /dev/video0"
            $cameraDevice = $lines[1].Trim()
            
            # Verifier que c'est bien une camera (pas un encoder/decoder)
            $checkResult = Invoke-RemoteCommand -Command "v4l2-ctl -d $cameraDevice --all 2>/dev/null | grep -i 'video capture' | head -1" -ReturnOutput
            
            if ($checkResult.ExitCode -eq 0 -and $checkResult.Output -match "video capture") {
                $cameraType = "usb"
                Write-Step "Camera USB detectee: $cameraInfo ($cameraDevice)" "OK"
            }
        }
    }
    
    # 2. Si pas de camera USB, chercher camera CSI/libcamera
    if ($cameraType -eq "none") {
        Write-Step "Recherche camera CSI (libcamera)"
        
        $result = Invoke-RemoteCommand -Command "rpicam-hello --list-cameras 2>/dev/null | head -10" -ReturnOutput
        
        if ($result.ExitCode -eq 0 -and $result.Output -match "Available cameras") {
            # Parser la sortie pour trouver une camera
            if ($result.Output -match "\d+ : (\w+)") {
                $cameraType = "csi"
                $cameraInfo = $matches[1]
                $cameraDevice = "/dev/video0"
                
                Write-Step "Camera CSI detectee: $cameraInfo" "OK"
            }
        }
    }
    
    # 3. Mettre a jour la configuration si une camera est detectee
    if ($cameraType -ne "none") {
        Write-Step "Configuration de la camera dans config.env"
        
        # Mettre a jour les variables dans config.env
        $configUpdates = @"
# Camera Configuration (auto-detected by install_device.ps1)
CAMERA_TYPE=$cameraType
CAMERA_DEVICE=$cameraDevice
"@
        
        # Supprimer les anciennes entrees CAMERA_TYPE/CAMERA_DEVICE si elles existent
        Invoke-RemoteCommand -Command "sudo sed -i '/^CAMERA_TYPE=/d' /etc/rpi-cam/config.env 2>/dev/null || true" -Silent
        Invoke-RemoteCommand -Command "sudo sed -i '/^CAMERA_DEVICE=/d' /etc/rpi-cam/config.env 2>/dev/null || true" -Silent
        Invoke-RemoteCommand -Command "sudo sed -i '/^# Camera Configuration/d' /etc/rpi-cam/config.env 2>/dev/null || true" -Silent
        
        # Ajouter les nouvelles entrees
        $escapedConfig = $configUpdates -replace '"', '\"'
        Invoke-RemoteCommand -Command "echo '$escapedConfig' | sudo tee -a /etc/rpi-cam/config.env > /dev/null" -Silent
        
        Write-Step "Camera configuree (${cameraType}: ${cameraInfo})" "OK"
        
        Write-Host ""
        Write-Host "  [OK] Camera detectee et configuree automatiquement" -ForegroundColor Green
        Write-Host "       Type: $cameraType" -ForegroundColor DarkGray
        Write-Host "       Info: $cameraInfo" -ForegroundColor DarkGray
        Write-Host "       Device: $cameraDevice" -ForegroundColor DarkGray
        
        return @{
            Type = $cameraType
            Device = $cameraDevice
            Info = $cameraInfo
            Success = $true
        }
    }
    else {
        Write-Step "Aucune camera detectee" "WARN"
        
        Write-Host ""
        Write-Host "  [!] Aucune camera detectee" -ForegroundColor Yellow
        Write-Host "      Connectez une camera USB ou CSI puis configurez via l'interface web" -ForegroundColor Gray
        
        return @{
            Type = "none"
            Device = ""
            Info = ""
            Success = $false
        }
    }
}

# ============================================================================
# Fonctions - Transfert
# ============================================================================
function Copy-ProjectFiles {
    Write-SubHeader "Transfert des fichiers" "~2 min"
    Start-Phase "transfer"
    
    # Créer dossier temporaire sur le device
    Write-Step "Creation du dossier temporaire sur le device"
    $result = Invoke-RemoteCommand -Command "rm -rf $RemoteTempDir && mkdir -p $RemoteTempDir" -Silent
    if ($result -ne 0) {
        Write-Step "Impossible de creer le dossier temporaire" "FAIL"
        return $false
    }
    Write-Step "Dossier $RemoteTempDir cree" "OK"
    
    # Préparer les options SCP
    $ScpOptions = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -r"
    
    # Compter les fichiers pour la progression
    $totalItems = $FilesToTransfer.Count
    $currentItem = 0
    
    # Transférer chaque élément
    foreach ($item in $FilesToTransfer) {
        $currentItem++
        $percent = [math]::Floor(($currentItem / $totalItems) * 100)
        $sourcePath = Join-Path $ProjectRoot $item
        
        if (-not (Test-Path $sourcePath)) {
            Write-Step "Fichier/dossier manquant: $item" "SKIP"
            continue
        }
        
        Write-Progress-Bar -Percent $percent -Label $item
        
        # Convertir en chemin WSL
        $WslSource = wsl wslpath -u "'$sourcePath'" 2>$null
        if (-not $WslSource) {
            $WslSource = "/mnt/" + $sourcePath.Substring(0,1).ToLower() + $sourcePath.Substring(2).Replace('\', '/')
        }
        
        $ScpCmd = "sshpass -p '$Password' scp $ScpOptions '$WslSource' '$User@${IP}:$RemoteTempDir/'"
        wsl bash -c $ScpCmd 2>&1 | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Step "Transfert: $item" "FAIL"
            return $false
        }
    }
    
    Write-Host ""
    Write-Step "Tous les fichiers transferes ($totalItems elements)" "OK"
    
    return $true
}

# ============================================================================
# Fonctions - Installation
# ============================================================================
function Start-Installation {
    Write-SubHeader "Installation sur le device" "~15-25 min"
    Start-Phase "preparation"
    
    # Rendre les scripts exécutables
    Write-Step "Configuration des permissions"
    Invoke-RemoteCommand -Command "chmod +x $RemoteTempDir/setup/*.sh $RemoteTempDir/*.sh 2>/dev/null" -Silent
    Write-Step "Permissions configurees" "OK"
    
    # Convertir CRLF -> LF (fichiers Windows)
    Write-Step "Conversion des fins de ligne (CRLF -> LF)"
    Invoke-RemoteCommand -Command "find $RemoteTempDir -type f \( -name '*.sh' -o -name '*.py' -o -name '*.service' \) -exec sed -i 's/\r$//' {} \;" -Silent
    Write-Step "Fins de ligne converties" "OK"
    
    # Supprimer BOM UTF-8 si présent
    Write-Step "Suppression des BOM UTF-8"
    Invoke-RemoteCommand -Command "find $RemoteTempDir -type f \( -name '*.sh' -o -name '*.py' \) -exec sed -i '1s/^\xEF\xBB\xBF//' {} \;" -Silent
    Write-Step "BOM supprimes" "OK"
    
    # Nettoyer les locks apt si présents
    Write-Step "Nettoyage des locks apt"
    Invoke-RemoteCommand -Command "sudo rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock /var/cache/apt/archives/lock 2>/dev/null; sudo dpkg --configure -a 2>/dev/null || true" -Silent
    Write-Step "Locks apt nettoyes" "OK"
    
    # Créer le script d'installation sur le device
    Write-Step "Creation du script d'installation distant"
    $createScriptCmd = "echo '#!/bin/bash' > /tmp/do_rtsp_install.sh && echo 'cd $RemoteTempDir && ./setup/install.sh --all' >> /tmp/do_rtsp_install.sh && chmod +x /tmp/do_rtsp_install.sh"
    Invoke-RemoteCommand -Command $createScriptCmd -Silent
    Write-Step "Script d'installation cree" "OK"
    
    # Afficher le panneau d'information
    Write-Host ""
    Write-Host "+================================================================+" -ForegroundColor Magenta
    Write-Host "|            INSTALLATION EN COURS SUR LE DEVICE                 |" -ForegroundColor Magenta
    Write-Host "+================================================================+" -ForegroundColor Magenta
    Write-Host "|                                                                |" -ForegroundColor Magenta
    Write-Host "|  Duree estimee: 15-25 minutes                                  |" -ForegroundColor Magenta
    Write-Host "|                                                                |" -ForegroundColor Magenta
    Write-Host "|  Phases:                                                       |" -ForegroundColor Magenta
    Write-Host "|    * GStreamer + dependances     ~10 min                       |" -ForegroundColor Magenta
    Write-Host "|    * Service RTSP                ~1 min                        |" -ForegroundColor Magenta
    Write-Host "|    * Service d'enregistrement    ~2 min                        |" -ForegroundColor Magenta
    Write-Host "|    * Interface Web               ~3 min                        |" -ForegroundColor Magenta
    Write-Host "|    * ONVIF + Watchdog            ~2 min                        |" -ForegroundColor Magenta
    Write-Host "|                                                                |" -ForegroundColor Magenta
    Write-Host "|  Ctrl+C pour continuer sans attendre                           |" -ForegroundColor Magenta
    Write-Host "|  (l'installation continuera en arriere-plan)                   |" -ForegroundColor Magenta
    Write-Host "|                                                                |" -ForegroundColor Magenta
    Write-Host "+================================================================+" -ForegroundColor Magenta
    Write-Host ""
    
    # Lancer l'installation en arrière-plan avec nohup
    Invoke-RemoteCommand -Command "sudo nohup /tmp/do_rtsp_install.sh > /tmp/install.log 2>&1 &" -Silent
    Start-Sleep -Seconds 3
    
    # Vérifier que l'installation a démarré
    $result = Invoke-RemoteCommand -Command "pgrep -f install.sh" -ReturnOutput
    if ($result.ExitCode -ne 0) {
        Write-Host "ERREUR: L'installation n'a pas demarre" -ForegroundColor Red
        return $false
    }
    
    Write-Step "Installation lancee en arriere-plan" "OK"
    Write-Host ""
    
    # Surveiller la progression avec affichage amélioré
    $installStartTime = Get-Date
    $lastLines = ""
    $stillRunning = $true
    $checkCount = 0
    $maxChecks = 180  # 30 minutes max
    $lastPhase = ""
    
    # Définition des phases par mots-clés dans les logs
    $phases = @{
        "GStreamer" = @{ Name = "Installation GStreamer"; Duration = 600 }
        "RTSP Streaming" = @{ Name = "Service RTSP"; Duration = 60 }
        "Recording Service" = @{ Name = "Service Enregistrement"; Duration = 120 }
        "Web Management" = @{ Name = "Interface Web"; Duration = 180 }
        "ONVIF" = @{ Name = "Serveur ONVIF"; Duration = 60 }
        "Watchdog" = @{ Name = "Service Watchdog"; Duration = 30 }
        "Installation check" = @{ Name = "Verification finale"; Duration = 30 }
    }
    
    while ($stillRunning -and $checkCount -lt $maxChecks) {
        Start-Sleep -Seconds 10
        $checkCount++
        
        # Calculer le temps écoulé
        $elapsed = (Get-Date) - $installStartTime
        $elapsedStr = "{0:mm}:{0:ss}" -f $elapsed
        
        # Vérifier si toujours en cours
        $procCheck = Invoke-RemoteCommand -Command "pgrep -f install.sh" -ReturnOutput
        $stillRunning = ($procCheck.ExitCode -eq 0)
        
        # Récupérer les dernières lignes du log
        $logResult = Invoke-RemoteCommand -Command "tail -5 /tmp/install.log 2>/dev/null" -ReturnOutput
        $currentLines = $logResult.Output
        
        # Détecter la phase actuelle
        $currentPhase = "Installation..."
        foreach ($key in $phases.Keys) {
            if ($currentLines -match $key) {
                $currentPhase = $phases[$key].Name
                break
            }
        }
        
        # Afficher la progression
        if ($currentPhase -ne $lastPhase) {
            if ($lastPhase) { Write-Host "" }
            Write-Host "  [$elapsedStr] " -NoNewline -ForegroundColor DarkGray
            Write-Host "> $currentPhase" -ForegroundColor Cyan
            $lastPhase = $currentPhase
        }
        
        # Afficher la dernière ligne significative du log
        if ($currentLines -ne $lastLines -and $currentLines) {
            $lastLines = $currentLines
            $logLine = ($currentLines -split "`n" | Where-Object { $_ -match '\S' } | Select-Object -Last 1)
            if ($logLine -and $logLine.Length -gt 0) {
                # Tronquer si trop long
                if ($logLine.Length -gt 60) {
                    $logLine = $logLine.Substring(0, 57) + "..."
                }
                Write-Host "    [$elapsedStr] $logLine" -ForegroundColor DarkGray
            }
        } else {
            # Afficher un indicateur d'activité
            Write-Host "." -NoNewline -ForegroundColor DarkGray
        }
    }
    
    Write-Host ""
    
    # Calculer la durée totale
    $totalElapsed = (Get-Date) - $installStartTime
    $totalStr = "{0:mm}m {0:ss}s" -f $totalElapsed
    
    if (-not $stillRunning) {
        Write-Host ""
        Write-Host "  [OK] Installation terminee en $totalStr" -ForegroundColor Green
        return $true
    } else {
        Write-Host ""
        Write-Host "  [..] Timeout atteint apres $totalStr" -ForegroundColor Yellow
        Write-Host "  L'installation continue peut-etre en arriere-plan." -ForegroundColor Gray
        Write-Host "  Utilisez: .\install_device.ps1 -IP $IP -Monitor" -ForegroundColor Gray
        return $true
    }
}

function Show-FinalStatus {
    Write-SubHeader "Statut final"
    
    # Vérifier les services
    $services = @(
        @{ Name = "rpi-av-rtsp-recorder"; Desc = "Streaming RTSP" },
        @{ Name = "rtsp-recorder"; Desc = "Enregistrement" },
        @{ Name = "rpi-cam-webmanager"; Desc = "Interface Web" },
        @{ Name = "rtsp-watchdog"; Desc = "Surveillance" },
        @{ Name = "rpi-cam-onvif"; Desc = "ONVIF (optionnel)" }
    )
    
    Write-Host "  Services systemd:" -ForegroundColor Yellow
    foreach ($svc in $services) {
        $result = Invoke-RemoteCommand -Command "systemctl is-active $($svc.Name) 2>/dev/null || echo 'inactive'" -ReturnOutput
        $status = ($result.Output -split "`n")[0].Trim()
        
        $icon = switch ($status) {
            "active"   { "[OK]"; $color = "Green" }
            "inactive" { "[--]"; $color = "Yellow" }
            default    { "[!!]"; $color = "Red" }
        }
        
        Write-Host "    $icon " -NoNewline -ForegroundColor $color
        Write-Host "$($svc.Name.PadRight(25))" -NoNewline -ForegroundColor White
        Write-Host " $($svc.Desc)" -ForegroundColor DarkGray
    }
    
    # Afficher les URLs d'accès
    Write-Host ""
    Write-Host "+================================================================+" -ForegroundColor Green
    Write-Host "|                      ACCES AU DEVICE                           |" -ForegroundColor Green
    Write-Host "+================================================================+" -ForegroundColor Green
    Write-Host "|                                                                |" -ForegroundColor Green
    Write-Host "|  Interface Web:                                                |" -ForegroundColor Green
    Write-Host "|    " -NoNewline -ForegroundColor Green
    Write-Host "http://${IP}:5000".PadRight(56) -NoNewline -ForegroundColor Cyan
    Write-Host "    |" -ForegroundColor Green
    Write-Host "|                                                                |" -ForegroundColor Green
    Write-Host "|  Flux RTSP (VLC):                                              |" -ForegroundColor Green
    Write-Host "|    " -NoNewline -ForegroundColor Green
    Write-Host "rtsp://${IP}:8554/stream".PadRight(56) -NoNewline -ForegroundColor Cyan
    Write-Host "    |" -ForegroundColor Green
    Write-Host "|                                                                |" -ForegroundColor Green
    Write-Host "+================================================================+" -ForegroundColor Green
}

function Watch-Installation {
    Write-SubHeader "Surveillance de l'installation en cours"
    
    # Vérifier si une installation est en cours
    $result = Invoke-RemoteCommand -Command "pgrep -f install.sh" -ReturnOutput
    if ($result.ExitCode -ne 0) {
        Write-Host "  Aucune installation en cours detectee." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Dernieres lignes du log:" -ForegroundColor Gray
        Write-Host ""
        Invoke-RemoteCommand -Command "tail -20 /tmp/install.log 2>/dev/null || echo 'Pas de log disponible'"
        return
    }
    
    Write-Host "  Installation en cours detectee. Surveillance..." -ForegroundColor Green
    Write-Host "  Ctrl+C pour arreter la surveillance (l'installation continue)" -ForegroundColor DarkGray
    Write-Host ""
    
    $startTime = Get-Date
    $lastLines = ""
    
    while ($true) {
        $procCheck = Invoke-RemoteCommand -Command "pgrep -f install.sh" -ReturnOutput
        if ($procCheck.ExitCode -ne 0) {
            Write-Host ""
            Write-Host "  [OK] Installation terminee!" -ForegroundColor Green
            break
        }
        
        $elapsed = (Get-Date) - $startTime
        $elapsedStr = "{0:mm}:{0:ss}" -f $elapsed
        
        $logResult = Invoke-RemoteCommand -Command "tail -5 /tmp/install.log 2>/dev/null" -ReturnOutput
        $currentLines = $logResult.Output
        
        if ($currentLines -ne $lastLines -and $currentLines) {
            $lastLines = $currentLines
            $logLine = ($currentLines -split "`n" | Where-Object { $_ -match '\S' } | Select-Object -Last 1)
            if ($logLine) {
                Write-Host "  [$elapsedStr] $logLine" -ForegroundColor Gray
            }
        }
        
        Start-Sleep -Seconds 5
    }
    
    # Afficher le statut final
    Show-FinalStatus
}

# ============================================================================
# Programme principal
# ============================================================================

# Afficher l'aide si demandée
if ($Help) {
    Show-Help
    exit 0
}

# Initialiser le timer global
$script:StartTime = Get-Date

# Afficher le header
Write-Host ""
Write-Header "RTSP-Full - Installation automatique sur Raspberry Pi"

# Vérifier les prérequis (WSL, sshpass)
if (-not (Test-Prerequisites)) {
    exit 1
}

# Demander l'IP si non fournie
if (-not $IP) {
    Write-Host ""
    Write-Host "+================================================================+" -ForegroundColor Yellow
    Write-Host "|  Configuration de l'installation                               |" -ForegroundColor Yellow
    Write-Host "+================================================================+" -ForegroundColor Yellow
    Write-Host ""
    
    $IP = Read-Host "  Adresse IP du Raspberry Pi"
    
    if (-not $IP) {
        Write-Host "  ERREUR: Adresse IP requise" -ForegroundColor Red
        exit 1
    }
}

# Valider le format de l'IP (basique)
if ($IP -notmatch '^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$') {
    Write-Host "  ERREUR: Format d'adresse IP invalide: $IP" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "  Configuration:" -ForegroundColor Yellow
Write-Host "    Device IP:     $IP"
Write-Host "    User:          $User"
Write-Host "    Project Root:  $ProjectRoot"
if ($DeviceKey) {
    $deviceKeyPreview = if ($DeviceKey.Length -gt 8) { "$($DeviceKey.Substring(0, 8))..." } else { $DeviceKey }
    Write-Host "    DeviceKey:     $deviceKeyPreview (sera aussi le hostname)"
}
if ($Token) {
    Write-Host "    Token:         $Token"
}
if (-not $NoReboot) {
    Write-Host "    Auto-Reboot:   Oui (a la fin de l'installation)"
}
Write-Host ""

# Test de connectivité
if (-not (Test-DeviceConnectivity)) {
    exit 1
}

# Mode CheckOnly
if ($CheckOnly) {
    Write-Host ""
    Write-Host "  Mode verification uniquement - arret" -ForegroundColor Yellow
    $elapsed = Get-ElapsedTime
    Write-Host "  Temps total: $elapsed" -ForegroundColor DarkGray
    exit 0
}

# Mode Monitor
if ($Monitor) {
    Watch-Installation
    exit 0
}

# Provisionnement (hostname, timezone)
if (-not $SkipInstall) {
    Invoke-Provisioning
    Invoke-MeetingProvisioning
}

# Transfert des fichiers
if (-not (Copy-ProjectFiles)) {
    Write-Host "  ERREUR: Echec du transfert des fichiers" -ForegroundColor Red
    exit 1
}

# Mode SkipInstall
if ($SkipInstall) {
    Write-Host ""
    Write-Host "  Mode transfert uniquement - installation ignoree" -ForegroundColor Yellow
    Write-Host "  Fichiers disponibles dans: $RemoteTempDir" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Pour installer manuellement:" -ForegroundColor Gray
    Write-Host "    ssh $User@$IP 'cd $RemoteTempDir && sudo ./setup/install.sh'" -ForegroundColor DarkGray
    exit 0
}

# Lancer l'installation
$installSuccess = Start-Installation

# Post-installation: Token burn et detection camera
if ($installSuccess) {
    # Detecter la camera automatiquement
    $cameraResult = Invoke-CameraDetection
    
    # Brûler le token si fourni (et si pas désactivé)
    if ($DeviceKey -and $Token -and -not $NoBurnToken) {
        $tokenBurnSuccess = Invoke-TokenBurn -DeviceKey $DeviceKey -Token $Token -MeetingApiUrl $MeetingApiUrl
        if (-not $tokenBurnSuccess) {
            Write-Host ""
            Write-Host "  [!] Le token n'a pas pu etre brule, mais l'installation continue" -ForegroundColor Yellow
        }
    }
    elseif ($NoBurnToken -and $DeviceKey -and $Token) {
        Write-Host ""
        Write-Host "  [INFO] Token burn desactive par -NoBurnToken" -ForegroundColor DarkGray
    }
}

# Afficher le résultat final
Write-Host ""
$totalElapsed = Get-ElapsedTime

if ($installSuccess) {
    Write-Host "+================================================================+" -ForegroundColor Green
    Write-Host "|            INSTALLATION TERMINEE AVEC SUCCES!                  |" -ForegroundColor Green
    Write-Host "|                                                                |" -ForegroundColor Green
    Write-Host "|  Temps total: $($totalElapsed.PadRight(47)) |" -ForegroundColor Green
    Write-Host "+================================================================+" -ForegroundColor Green
    
    # Afficher le statut final
    Show-FinalStatus
    
    # Reboot automatique si demandé
    if (-not $NoReboot) {
        Write-Host ""
        Write-Host "+================================================================+" -ForegroundColor Cyan
        Write-Host "|                     REDEMARRAGE AUTOMATIQUE                    |" -ForegroundColor Cyan
        Write-Host "+================================================================+" -ForegroundColor Cyan
        Write-Host "|                                                                |" -ForegroundColor Cyan
        Write-Host "|  Le device va redemarrer dans 5 secondes...                    |" -ForegroundColor Cyan
        Write-Host "|  (Ctrl+C pour annuler)                                         |" -ForegroundColor Cyan
        Write-Host "|                                                                |" -ForegroundColor Cyan
        Write-Host "+================================================================+" -ForegroundColor Cyan
        
        # Countdown
        for ($i = 5; $i -gt 0; $i--) {
            Write-Host "  Reboot dans $i secondes..." -ForegroundColor Yellow -NoNewline
            Start-Sleep -Seconds 1
            Write-Host "`r                              `r" -NoNewline
        }
        
        Write-Host "  Envoi de la commande de reboot..." -ForegroundColor Cyan
        Invoke-RemoteCommand -Command "sudo reboot" -Silent
        
        Write-Host ""
        Write-Host "  [OK] Commande de reboot envoyee" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Le device va redemarrer et sera accessible dans ~30 secondes a:" -ForegroundColor Gray
        Write-Host "    - Interface Web: http://${IP}:5000" -ForegroundColor Cyan
        Write-Host "    - Flux RTSP:     rtsp://${IP}:8554/stream" -ForegroundColor Cyan
        if ($DeviceKey) {
            Write-Host "    - Via hostname:  http://${DeviceKey}.local:5000" -ForegroundColor Cyan
        }
        Write-Host ""
        
        # Attendre que le device soit de nouveau accessible
        Write-Host "  Attente du redemarrage..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
        
        $retryCount = 0
        $maxRetries = 12  # ~2 minutes max
        $deviceUp = $false
        
        while ($retryCount -lt $maxRetries -and -not $deviceUp) {
            Start-Sleep -Seconds 10
            $retryCount++
            
            Write-Host "  Tentative de reconnexion ($retryCount/$maxRetries)..." -ForegroundColor DarkGray -NoNewline
            
            $result = Invoke-RemoteCommand -Command "echo 'OK'" -ReturnOutput
            if ($result.ExitCode -eq 0 -and $result.Output -match "OK") {
                $deviceUp = $true
                Write-Host " [OK]" -ForegroundColor Green
            } else {
                Write-Host " [--]" -ForegroundColor Yellow
            }
        }
        
        if ($deviceUp) {
            Write-Host ""
            Write-Host "+================================================================+" -ForegroundColor Green
            Write-Host "|              DEVICE OPERATIONNEL ET PRET A L'EMPLOI!           |" -ForegroundColor Green
            Write-Host "+================================================================+" -ForegroundColor Green
            Write-Host ""
            
            # Vérifier les services
            Show-FinalStatus
        } else {
            Write-Host ""
            Write-Host "  [!] Le device n'a pas repondu dans le temps imparti" -ForegroundColor Yellow
            Write-Host "      Il peut etre encore en cours de demarrage." -ForegroundColor Gray
            Write-Host "      Essayez de vous connecter manuellement dans quelques instants." -ForegroundColor Gray
        }
    }
    
    exit 0
} else {
    Write-Host "+================================================================+" -ForegroundColor Red
    Write-Host "|          INSTALLATION TERMINEE AVEC DES ERREURS                |" -ForegroundColor Red
    Write-Host "+================================================================+" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Consultez les logs pour plus de details:" -ForegroundColor Yellow
    Write-Host "    ssh $User@$IP 'tail -50 /tmp/install.log'" -ForegroundColor DarkGray
    Write-Host "    ssh $User@$IP 'sudo journalctl -xe'" -ForegroundColor DarkGray
    
    exit 1
}

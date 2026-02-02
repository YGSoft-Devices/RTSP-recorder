# deploy_scp.ps1 - Déploiement SCP vers le device
# Version: 1.4.7
#
# SECURITY: Requires explicit IP address or DeviceKey. No hardcoded defaults.
# Validates IP against Meeting API when available.
#
# Usage:
#   .\deploy_scp.ps1 -Source ".\file.txt" -Dest "/tmp/" -IP "192.168.1.202"
#   .\deploy_scp.ps1 -Source ".\folder\" -Dest "/opt/app/" -Recursive -IP "192.168.1.202"
#   .\deploy_scp.ps1 -Source ".\app.py" -Dest "/opt/..." -IP "192.168.1.202"
#   .\deploy_scp.ps1 -Source ".\file.py" -Dest "/opt/..." -DeviceKey "ABC123..."
#
# Note: Les fichiers frontend (.js, .css, .html) dans web-manager déclenchent
#       automatiquement un redémarrage du service pour vider le cache de templates.
# Note: Les destinations /opt/* sont automatiquement gérées via /tmp + sudo cp

param(
    [Parameter(Mandatory=$true)]
    [string]$Source,
    
    [Parameter(Mandatory=$true)]
    [string]$Dest,
    
    [string]$IP,
    [string]$DeviceKey,
    [string]$Token,
    [string]$ApiUrl,
    [switch]$Recursive,
    [switch]$UseWifi,
    [switch]$Auto,
    [switch]$DryRun,
    [switch]$NoRestart,
    [string]$User = "device",
    [string]$Password = "meeting",
    [string]$IpEthernet,
    [string]$IpWifi
)

$ErrorActionPreference = "Stop"

# Helper functions
function Load-MeetingConfig {
    $meetingConfig = Join-Path $PSScriptRoot "meeting_config.json"
    $defaultUrl = "https://meeting.ygsoft.fr/api"
    if (-not (Test-Path -LiteralPath $meetingConfig)) {
        return @{ api_url = $defaultUrl; device_key = ""; token_code = "" }
    }
    try {
        $cfg = Get-Content -LiteralPath $meetingConfig -Raw | ConvertFrom-Json
        $api = if ($cfg.api_url) { [string]$cfg.api_url } else { $defaultUrl }
        return @{
            api_url = $api
            device_key = [string]$cfg.device_key
            token_code = [string]$cfg.token_code
        }
    } catch {
        return @{ api_url = $defaultUrl; device_key = ""; token_code = "" }
    }
}

function Get-MeetingField {
    param([object]$Object,[string]$Name)
    if ($null -eq $Object -or -not $Name) { return $null }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) { return $Object[$Name] }
        return $null
    }
    $prop = $Object.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $null
}

function Resolve-DeviceIP {
    param(
        [string]$IP,
        [string]$DeviceKey,
        [string]$Token,
        [string]$ApiUrl
    )

    if ($IP) { return $IP }

    $cfg = Load-MeetingConfig
    if (-not $DeviceKey) { $DeviceKey = $cfg.device_key }
    if (-not $ApiUrl) { $ApiUrl = $cfg.api_url }
    if (-not $Token) { $Token = $cfg.token_code }

    if ($DeviceKey -and $ApiUrl) {
        try {
            $url = "$($ApiUrl.TrimEnd('/'))/devices/$DeviceKey"
            if ($Token) {
                $headers = @{ "X-Token-Code" = $Token; "Accept" = "application/json" }
                $resp = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 5 -ErrorAction Stop
            } else {
                $resp = Invoke-RestMethod -Uri $url -TimeoutSec 5 -ErrorAction Stop
            }
            $respIp = Get-MeetingField -Object $resp -Name "ip_address"
            if (-not $respIp) { $respIp = Get-MeetingField -Object $resp -Name "ip" }
            if ($respIp) { return [string]$respIp }
        } catch {
            # continue to fallback
        }
    }

    return $null
}

# Résolution de l'IP du device
$DeviceIP = Resolve-DeviceIP -IP $IP -DeviceKey $DeviceKey -Token $Token -ApiUrl $ApiUrl

if (-not $DeviceIP) {
    # Try alternate methods for backward compatibility
    $GetDeviceIPScript = Join-Path $PSScriptRoot "Get-DeviceIP.ps1"
    if ($Auto -and (Test-Path $GetDeviceIPScript)) {
        . $GetDeviceIPScript
        $DeviceIP = Find-DeviceIP -Quiet
    } elseif ($UseWifi -and $IpWifi) {
        $DeviceIP = $IpWifi
    } elseif ($IpEthernet) {
        $DeviceIP = $IpEthernet
    }
}

# Si toujours pas d'IP, demander à l'utilisateur
if (-not $DeviceIP) {
    Write-Host ""
    Write-Host "=== Device IP Resolution Failed ===" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "No device IP could be resolved. Please provide either:" -ForegroundColor Cyan
    Write-Host "  1. Device IP address (e.g., 192.168.1.202)" -ForegroundColor Gray
    Write-Host "  2. Device Key from Meeting API" -ForegroundColor Gray
    Write-Host ""
    
    $userInput = Read-Host "Enter Device IP or DeviceKey"
    
    if (-not $userInput) {
        throw "No IP or DeviceKey provided. Cannot continue."
    }
    
    # Check if it looks like an IP or a DeviceKey
    if ($userInput -match '^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$') {
        $DeviceIP = $userInput
        Write-Host "✓ Using provided IP: $DeviceIP" -ForegroundColor Green
    } else {
        $cfg = Load-MeetingConfig
        $resolvedIp = Resolve-DeviceIP -DeviceKey $userInput -Token $cfg.token_code -ApiUrl $cfg.api_url
        if ($resolvedIp) {
            $DeviceIP = $resolvedIp
            Write-Host "✓ Device Key resolved to IP: $DeviceIP" -ForegroundColor Green
        } else {
            throw "Could not resolve DeviceKey '$userInput' via Meeting API."
        }
    }
}

# Détecter si la destination nécessite sudo (ex: /opt/*)
$NeedsSudo = $Dest -match "^/opt/" -or $Dest -match "^/etc/" -or $Dest -match "^/usr/"
$TempDest = "/tmp/"
# Normalize destination - remove trailing slash to avoid double-slash issues (e.g., /opt/path//* -> /opt/path/*)
$FinalDest = $Dest.TrimEnd('/')

Write-Host "=== SCP Deployment ===" -ForegroundColor Cyan
Write-Host "Source: $Source" -ForegroundColor Gray
Write-Host "Dest:   $User@${DeviceIP}:$Dest" -ForegroundColor Gray
if ($NeedsSudo) {
    Write-Host "Mode:   Via /tmp + sudo cp (destination protégée)" -ForegroundColor DarkYellow
}

# Options SCP communes
$ScpOptions = @(
    "-o", "StrictHostKeyChecking=no",
    "-o", "UserKnownHostsFile=/dev/null",
    "-o", "LogLevel=ERROR"
)

if ($Recursive) {
    $ScpOptions += "-r"
}

# Vérifier que la source existe
$SourcePath = Resolve-Path $Source -ErrorAction SilentlyContinue
if (-not $SourcePath) {
    Write-Host "ERREUR: Source introuvable: $Source" -ForegroundColor Red
    exit 1
}

# Collecter les noms de fichiers et leurs chemins
$FileNames = @()
$FileMapping = @{}  # Map pour tracking des chemins
Write-Host "Fichiers à transférer:" -ForegroundColor Yellow

if ($Recursive) {
    # Pour les dossiers, on doit tracker les chemins complets
    # EXCLUSION: ignorer __pycache__, .pyc, .git, et autres fichiers inutiles
    Get-ChildItem $Source -Recurse -File | Where-Object {
        $_.FullName -notmatch '\\__pycache__\\' -and
        $_.FullName -notmatch '/__pycache__/' -and
        $_.Extension -ne '.pyc' -and
        $_.FullName -notmatch '\\.git\\' -and
        $_.FullName -notmatch '/.git/'
    } | ForEach-Object {
        $relPath = $_.FullName.Substring((Resolve-Path (Split-Path $Source)).Path.Length).TrimStart('\/')
        Write-Host "  - $relPath" -ForegroundColor Gray
        $FileNames += $_.Name
    }
    # Pour les dossiers, garder le nom du dossier source
    $SourceDir = Split-Path $Source
    $FolderName = Split-Path (Resolve-Path $Source) -Leaf
    $FileMapping[$FolderName] = $FolderName
} else {
    # Pour les fichiers simples
    Get-ChildItem $Source -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  - $($_.Name)" -ForegroundColor Gray
        $FileNames += $_.Name
        $FileMapping[$_.Name] = $_.Name
    }
}

if ($DryRun) {
    Write-Host ""
    Write-Host "[DRY RUN] Commande qui serait exécutée:" -ForegroundColor Magenta
    if ($NeedsSudo) {
        Write-Host "1. scp ... $Source $User@${DeviceIP}:/tmp/" -ForegroundColor White
        Write-Host "2. ssh ... 'sudo cp /tmp/<files> $Dest'" -ForegroundColor White
    } else {
        Write-Host "scp $($ScpOptions -join ' ') $Source $User@${DeviceIP}:$Dest" -ForegroundColor White
    }
    exit 0
}

# Vérifier si sshpass est disponible dans WSL
$UseSshpass = $false
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    $WslCheck = wsl which sshpass 2>$null
    if ($WslCheck) {
        $UseSshpass = $true
    }
}

Write-Host ""

# Destination pour SCP (tmp si sudo nécessaire)
$ScpDest = if ($NeedsSudo) { $TempDest } else { $Dest }

if ($UseSshpass) {
    Write-Host "Mode: WSL + sshpass (automatique)" -ForegroundColor Green
    
    # Convertir le chemin Windows en chemin WSL
    $WslSource = $Source -replace '\\', '/'
    $WslSource = wsl wslpath -u "'$((Resolve-Path $Source).Path)'" 2>$null
    if (-not $WslSource) {
        # Fallback: conversion manuelle
        $WinPath = (Resolve-Path $Source).Path
        $WslSource = "/mnt/" + $WinPath.Substring(0,1).ToLower() + $WinPath.Substring(2).Replace('\', '/')
    }
    
    $ScpCmd = "sshpass -p '$Password' scp $($ScpOptions -join ' ') $WslSource $User@${DeviceIP}:$ScpDest"
    Write-Host "Transfert en cours..." -ForegroundColor Yellow
    
    $result = wsl bash -c $ScpCmd 2>&1
    $exitCode = $LASTEXITCODE
    
    if ($result -and $exitCode -ne 0) { Write-Host $result }
    
} else {
    Write-Host "Mode: SCP natif Windows (mot de passe requis)" -ForegroundColor Yellow
    Write-Host "Mot de passe: $Password" -ForegroundColor Cyan
    Write-Host ""
    
    # Exécuter SCP
    & scp @ScpOptions $Source "$User@${DeviceIP}:$ScpDest"
    $exitCode = $LASTEXITCODE
}

# Si SCP réussi et sudo nécessaire, copier vers destination finale
if ($exitCode -eq 0 -and $NeedsSudo) {
    Write-Host "Copie vers destination finale avec sudo..." -ForegroundColor Yellow
    
    # Construire la commande de copie
    if ($Recursive) {
        # Pour les dossiers: copier récursivement LE CONTENU du dossier SOURCE dans la destination finale
        $SourceFolder = Split-Path (Resolve-Path $Source) -Leaf
        # S'assurer que la destination existe et copier le contenu (éviter nested /web-manager/web-manager)
        # Après la copie, supprimer un éventuel dossier imbriqué résiduel (ex: /opt/.../web-manager/web-manager)
        # CLEANUP: Supprimer __pycache__ et .pyc du dossier temporaire AVANT la copie
        # Ajouter chmod +x pour les scripts .sh et .py
        # NOTE: éviter les quotes simples internes pour ne pas casser le quoting lors de l'appel ssh '...'
        $CopyCmd = "sudo find /tmp/$SourceFolder -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; sudo find /tmp/$SourceFolder -name '*.pyc' -delete 2>/dev/null; sudo mkdir -p $FinalDest && sudo cp -r /tmp/$SourceFolder/* $FinalDest && if [ -d $FinalDest$SourceFolder ]; then sudo rm -rf $FinalDest$SourceFolder; fi && sudo chown -R root:www-data $FinalDest && sudo chmod -R 750 $FinalDest && sudo find $FinalDest -name '*.sh' -exec chmod +x {} \; && sudo find $FinalDest -name '*.py' -exec chmod +x {} \;"
    } else {
        # Pour les fichiers: copier chaque fichier puis corriger les permissions
        # Ajouter chmod +x pour les scripts .sh et .py
        $CopyCommands = $FileNames | ForEach-Object { "sudo mkdir -p $FinalDest && sudo cp /tmp/$_ $FinalDest/" }
        $ChownCommands = $FileNames | ForEach-Object { "sudo chown root:www-data $FinalDest/$_" }
        $ChmodCommands = $FileNames | ForEach-Object { "sudo chmod 640 $FinalDest/$_" }
        $ChmodExec = $FileNames | Where-Object { $_ -match '\.(sh|py)$' } | ForEach-Object { "sudo chmod +x $FinalDest/$_" }
        $CopyCmd = ($CopyCommands -join " && ") + " && " + ($ChownCommands -join " && ") + " && " + ($ChmodCommands -join " && ")
        if ($ChmodExec) {
            $CopyCmd += " && " + ($ChmodExec -join " && ")
        }
    }

    $SshCmd = "sshpass -p '$Password' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $User@$DeviceIP '$CopyCmd'"
    $copyResult = wsl bash -c $SshCmd 2>&1
    $exitCode = $LASTEXITCODE

    if ($copyResult -and $exitCode -ne 0) { Write-Host $copyResult }
}

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "✓ Transfert réussi!" -ForegroundColor Green
    if ($Recursive) {
        $SourceFolder = Split-Path (Resolve-Path $Source) -Leaf
        Write-Host "  Dossier: $SourceFolder" -ForegroundColor DarkGray
    } else {
        Write-Host "  Fichiers: $($FileNames -join ', ')" -ForegroundColor DarkGray
    }
    
    # Détecter si c'est un fichier frontend nécessitant un restart
    $IsFrontend = $false
    $FrontendExtensions = @(".js", ".css", ".html")
    
    foreach ($FileName in $FileNames) {
        $ext = [System.IO.Path]::GetExtension($FileName).ToLower()
        if ($FrontendExtensions -contains $ext) {
            $IsFrontend = $true
            break
        }
    }
    
    # Aussi détecter si la destination est dans web-manager/static ou templates
    if ($Dest -match "rpi-cam-webmanager" -or $Dest -match "web-manager") {
        if ($Dest -match "static|templates") {
            $IsFrontend = $true
        }
    }
    
    # Redémarrer le service si frontend et pas -NoRestart
    if ($IsFrontend -and -not $NoRestart) {
        Write-Host ""
        Write-Host "→ Fichier frontend détecté, redémarrage du service..." -ForegroundColor Yellow
        
        $RestartCmd = "sshpass -p '$Password' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $User@$DeviceIP 'sudo systemctl restart rpi-cam-webmanager'"
        $restartResult = wsl bash -c $RestartCmd 2>&1
        $restartCode = $LASTEXITCODE
        
        if ($restartCode -eq 0) {
            Write-Host "✓ Service rpi-cam-webmanager redémarré" -ForegroundColor Green
        } else {
            Write-Host "⚠ Erreur redémarrage service: $restartResult" -ForegroundColor Yellow
        }
    } elseif (-not $NoRestart -and $Dest -match "rpi-cam-webmanager") {
        # Fichier Python backend - redémarrer aussi
        $hasPython = $FileNames | Where-Object { $_ -match "\.py$" }
        if ($hasPython) {
            Write-Host ""
            Write-Host "→ Fichier Python détecté, redémarrage du service..." -ForegroundColor Yellow
            
            $RestartCmd = "sshpass -p '$Password' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $User@$DeviceIP 'sudo systemctl restart rpi-cam-webmanager'"
            $restartResult = wsl bash -c $RestartCmd 2>&1
            $restartCode = $LASTEXITCODE
            
            if ($restartCode -eq 0) {
                Write-Host "✓ Service rpi-cam-webmanager redémarré" -ForegroundColor Green
            } else {
                Write-Host "⚠ Erreur redémarrage service: $restartResult" -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "✗ Erreur lors du transfert (code: $exitCode)" -ForegroundColor Red
}

exit $exitCode

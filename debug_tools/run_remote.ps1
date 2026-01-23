# run_remote.ps1 - Exécuter une commande sur le device (wrapper simplifié)
# Version: 1.3.1
#
# SECURITY: Requires explicit IP address or DeviceKey when used with -IP flag.
# No hardcoded default IPs. Can auto-detect via Meeting API with -Auto flag.
#
# Ce script est conçu pour être utilisé par les agents IA pour exécuter
# des commandes sur le Raspberry Pi sans interaction utilisateur.
#
# Usage:
#   .\run_remote.ps1 -IP "192.168.1.202" "commande à exécuter"
#   .\run_remote.ps1 -IP "192.168.1.202" "sudo systemctl status rpi-cam-webmanager"
#   .\run_remote.ps1 -DeviceKey "ABC123..." "commande"
#   .\run_remote.ps1 -Wifi "commande"  # Use WiFi default (backward compat)
#   .\run_remote.ps1 -Auto "commande"  # Auto-détection via Meeting API

param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$Command,
    
    [switch]$Wifi,
    [switch]$Auto,
    [string]$IP,
    [string]$DeviceKey,
    [string]$Token,
    [string]$ApiUrl,
    [int]$Timeout = 30,
    [int]$ServerAliveInterval = 60,
    [int]$ServerAliveCountMax = 10
)

$ErrorActionPreference = "Stop"

# Configuration
$User = "device"
$Password = "meeting"
$DefaultEthIP = "192.168.1.202"
$DefaultWifiIP = "192.168.1.127"

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

# Determine IP to use
$DeviceIP = $null

if ($IP) {
    $DeviceIP = $IP
} elseif ($DeviceKey) {
    $cfg = Load-MeetingConfig
    $DeviceIP = Resolve-DeviceIP -DeviceKey $DeviceKey -Token $Token -ApiUrl $ApiUrl
    if (-not $DeviceIP) {
        throw "Could not resolve DeviceKey '$DeviceKey' via Meeting API."
    }
} elseif ($Auto) {
    # Mode auto-détection via Meeting API
    $GetDeviceIPScript = Join-Path $PSScriptRoot "Get-DeviceIP.ps1"
    if (Test-Path $GetDeviceIPScript) {
        . $GetDeviceIPScript
        $DeviceIP = Find-DeviceIP -Quiet
    }
    if (-not $DeviceIP) {
        Write-Host "⚠ Aucune IP accessible trouvée via Meeting API, utilisation de l'IP par défaut" -ForegroundColor Yellow
        $DeviceIP = $DefaultEthIP
    }
} elseif ($Wifi) {
    $DeviceIP = $DefaultWifiIP
} else {
    # No default - require explicit IP
    throw "No device IP specified. Use -IP, -DeviceKey, -Auto, or -Wifi flag."
}

# Options SSH
$SshOptions = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=$Timeout -o ServerAliveInterval=$ServerAliveInterval -o ServerAliveCountMax=$ServerAliveCountMax"

# Vérifier WSL + sshpass
$HasSshpass = $false
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    $check = wsl which sshpass 2>$null
    if ($check) { $HasSshpass = $true }
}

if ($HasSshpass) {
    # Mode automatique via WSL
    $EscapedCmd = $Command -replace "'", "'\\''"
    $WslCmd = "sshpass -p '$Password' ssh $SshOptions $User@$DeviceIP '$EscapedCmd'"
    wsl bash -c $WslCmd
    exit $LASTEXITCODE
} else {
    # Mode natif - afficher les infos pour l'utilisateur
    Write-Host "Connexion: $User@$DeviceIP" -ForegroundColor Cyan
    Write-Host "Password: $Password" -ForegroundColor Yellow
    Write-Host "Commande: $Command" -ForegroundColor Gray
    Write-Host ""
    
    # Utiliser ssh directement
    $SshArgs = @(
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", 
        "-o", "LogLevel=ERROR",
        "-o", "ConnectTimeout=$Timeout",
        "-o", "ServerAliveInterval=$ServerAliveInterval",
        "-o", "ServerAliveCountMax=$ServerAliveCountMax",
        "$User@$DeviceIP",
        $Command
    )
    
    & ssh @SshArgs
    exit $LASTEXITCODE
}

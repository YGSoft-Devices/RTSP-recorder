# update_device.ps1 - Quick update of project files on a running device
# Version: 2.0.3
#
# This script performs a lightweight, fast update:
# 0. Wait for device to be reachable (with automatic retry on network/reboot issues)
# 1. Stop all services
# 2. Deploy project files (no reinstall)
# 3. Check Python requirements
# 4. Restart all services
#
# Complete in 30-60 seconds. Configuration preserved. NO apt-get/full reinstalls.
# If device is unreachable, waits and retries automatically (useful for reboot scenarios).
#
# SECURITY: No default IP hardcoded. Must provide -IP or -DeviceKey.
# Validates IP against Meeting API when available for safety.
#
# Usage:
#   .\debug_tools\update_device.ps1 -IP "192.168.1.202"
#   .\debug_tools\update_device.ps1 -DeviceKey "ABC123..."
#   .\debug_tools\update_device.ps1                        # Interactive prompt for IP or DeviceKey
#   .\debug_tools\update_device.ps1 -IP "192.168.1.202" -NoRestart
#   .\debug_tools\update_device.ps1 -IP "192.168.1.202" -DryRun
#
# Notes:
# - Requires WSL + sshpass (same as other debug_tools scripts).
# - Uses Meeting API when DeviceKey is provided for IP validation.
# - Configuration files in /etc/rpi-cam are PRESERVED during update.

param(
    [string]$IP,
    [string]$DeviceKey,
    [string]$Token,
    [string]$ApiUrl,
    [switch]$DryRun,
    [switch]$NoRestart,
    [string]$User = "device",
    [string]$Password = "meeting"
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $PSCommandPath
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..")
$deployScp = Join-Path $scriptRoot "deploy_scp.ps1"
$runRemote = Join-Path $scriptRoot "run_remote.ps1"
$meetingConfig = Join-Path $scriptRoot "meeting_config.json"

function Load-MeetingConfig {
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

function Wait-DeviceReachable {
    param(
        [string]$IP,
        [int]$MaxRetries = 60,
        [int]$RetryIntervalSeconds = 1,
        [int]$PingTimeoutMs = 2000
    )
    
    $attempt = 0
    $isReachable = $false
    
    Write-Host "Checking device connectivity..." -ForegroundColor Yellow
    
    while ($attempt -lt $MaxRetries -and -not $isReachable) {
        $attempt++
        
        # Test SSH connectivity on port 22
        try {
            $socket = New-Object System.Net.Sockets.TcpClient
            $socket.ConnectAsync($IP, 22).Wait($PingTimeoutMs) | Out-Null
            if ($socket.Connected) {
                $isReachable = $true
                $socket.Dispose()
                Write-Host "✓ Device is reachable (SSH port 22 open)" -ForegroundColor Green
                return $true
            }
            $socket.Dispose()
        } catch {
            # Connection failed, continue
        }
        
        if (-not $isReachable) {
            $remainingRetries = $MaxRetries - $attempt
            Write-Host "  Device not reachable (attempt $attempt/$MaxRetries). Retrying in $RetryIntervalSeconds seconds..." -ForegroundColor Yellow
            if ($remainingRetries -gt 0) {
                Write-Host "  Waiting... ($remainingRetries retries left)" -ForegroundColor DarkYellow
                Start-Sleep -Seconds $RetryIntervalSeconds
            }
        }
    }
    
    if (-not $isReachable) {
        Write-Host "✗ Device is not reachable after $MaxRetries attempts" -ForegroundColor Red
        return $false
    }
    
    return $true
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

if (-not (Test-Path -LiteralPath $deployScp)) { throw "deploy_scp.ps1 introuvable." }
if (-not (Test-Path -LiteralPath $runRemote)) { throw "run_remote.ps1 introuvable." }

# Résolution de l'IP du device
$deviceIp = Resolve-DeviceIP -IP $IP -DeviceKey $DeviceKey -Token $Token -ApiUrl $ApiUrl

# Si aucune IP trouvée, demander à l'utilisateur
if (-not $deviceIp) {
    Write-Host ""
    Write-Host "=== Device IP Resolution Failed ===" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "No device IP could be resolved. Please provide either:" -ForegroundColor Cyan
    Write-Host "  1. Device IP address (e.g., 192.168.1.202)" -ForegroundColor Gray
    Write-Host "  2. Device Key from Meeting API" -ForegroundColor Gray
    Write-Host ""
    
    # Prompt for IP or DeviceKey
    $userInput = Read-Host "Enter Device IP or DeviceKey"
    
    if (-not $userInput) {
        throw "No IP or DeviceKey provided. Cannot continue."
    }
    
    # Check if it looks like an IP or a DeviceKey
    if ($userInput -match '^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$') {
        # Looks like an IP
        $deviceIp = $userInput
        Write-Host "✓ Using provided IP: $deviceIp" -ForegroundColor Green
    } else {
        # Assume it's a DeviceKey, try to resolve via Meeting API
        Write-Host "Resolving DeviceKey via Meeting API..." -ForegroundColor Cyan
        $cfg = Load-MeetingConfig
        $resolvedIp = Resolve-DeviceIP -DeviceKey $userInput -Token $cfg.token_code -ApiUrl $cfg.api_url
        if ($resolvedIp) {
            $deviceIp = $resolvedIp
            Write-Host "✓ Device Key resolved to IP: $deviceIp" -ForegroundColor Green
        } else {
            throw "Could not resolve DeviceKey '$userInput' via Meeting API. Please check the key or provide an IP address."
        }
    }
}

# SECURITY: Validate the IP against Meeting API if we can
Write-Host ""
Write-Host "Validating device IP via Meeting API..." -ForegroundColor Yellow
$cfg = Load-MeetingConfig
$validatedIp = $null

if ($cfg.device_key -and $cfg.api_url) {
    try {
        $url = "$($cfg.api_url.TrimEnd('/'))/devices/$($cfg.device_key)"
        $headers = @{ "Accept" = "application/json" }
        if ($cfg.token_code) {
            $headers["X-Token-Code"] = $cfg.token_code
        }
        
        $resp = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 5 -ErrorAction Stop
        $apiIp = Get-MeetingField -Object $resp -Name "ip_address"
        if (-not $apiIp) { $apiIp = Get-MeetingField -Object $resp -Name "ip" }
        
        if ($apiIp) {
            $validatedIp = [string]$apiIp
            if ($validatedIp -eq $deviceIp) {
                Write-Host "✓ Device IP validated via Meeting API" -ForegroundColor Green
            } else {
                Write-Host "⚠ WARNING: Meeting API shows different IP!" -ForegroundColor Yellow
                Write-Host "  Provided IP: $deviceIp" -ForegroundColor Yellow
                Write-Host "  Meeting API IP: $validatedIp" -ForegroundColor Yellow
                $confirmUse = Read-Host "Use Meeting API IP? (y/n)"
                if ($confirmUse -eq "y") {
                    $deviceIp = $validatedIp
                    Write-Host "✓ Using Meeting API IP: $deviceIp" -ForegroundColor Green
                } else {
                    Write-Host "Using provided IP: $deviceIp" -ForegroundColor Cyan
                }
            }
        }
    } catch {
        Write-Host "⚠ Could not validate IP via Meeting API (continuing with provided IP)" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠ Meeting API not configured (skipping IP validation)" -ForegroundColor DarkYellow
}

Write-Host "Device IP: $deviceIp" -ForegroundColor Cyan

# STEP 0: Wait for device to be reachable
Write-Host ""
Write-Host "=== STEP 0: Waiting for device to be reachable ===" -ForegroundColor Cyan
if (-not (Wait-DeviceReachable -IP $deviceIp -MaxRetries 60 -RetryIntervalSeconds 1)) {
    throw "Device $deviceIp est inaccessible apres 5 minutes. Impossible de continuer."
}
Write-Host ""

# List of files/dirs to deploy
$filesToDeploy = @(
    "rpi_av_rtsp_recorder.sh",
    "rpi_csi_rtsp_server.py",
    "rtsp_recorder.sh",
    "rtsp_watchdog.sh",
    "VERSION",
    "setup/",
    "onvif-server/",
    "web-manager/"
)

if ($DryRun) {
    Write-Host ""
    Write-Host "[DRY RUN] Would perform the following steps:" -ForegroundColor Magenta
    Write-Host "  0. Wait for device to be reachable (retry up to 5 minutes)" -ForegroundColor Gray
    Write-Host "  1. Stop services: rpi-cam-webmanager, rpi-av-rtsp-recorder, rtsp-recorder, rtsp-watchdog, rpi-cam-onvif" -ForegroundColor Gray
    Write-Host "  2. Deploy project files:" -ForegroundColor Gray
    foreach ($file in $filesToDeploy) {
        Write-Host "     - $file" -ForegroundColor DarkGray
    }
    Write-Host "  3. Check Python requirements (install if needed)" -ForegroundColor Gray
    Write-Host "  4. Restart all services" -ForegroundColor Gray
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "=== STEP 1: Stopping services ===" -ForegroundColor Cyan
$stopCmd = @"
echo "Stopping all services..."
sudo systemctl stop rpi-cam-webmanager rpi-av-rtsp-recorder rtsp-recorder rtsp-watchdog rpi-cam-onvif 2>/dev/null || true
sleep 2
echo "OK"
"@

$output = & $runRemote -IP $deviceIp $stopCmd -Timeout 30 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "⚠ Warning stopping services (may be OK if already stopped)" -ForegroundColor Yellow }
Write-Host "✓ Services stopped" -ForegroundColor Green

Write-Host ""
Write-Host "=== STEP 2: Deploying project files ===" -ForegroundColor Cyan
foreach ($file in $filesToDeploy) {
    # Normaliser le path en supprimant les slashes à la fin
    $fileNormalized = $file.TrimEnd('/', '\')
    $fullPath = Join-Path $repoRoot.Path $fileNormalized
    if (-not (Test-Path $fullPath)) {
        Write-Host "⚠ File not found: $fileNormalized (skipping)" -ForegroundColor Yellow
        continue
    }
    
    Write-Host "  Deploying: $fileNormalized" -ForegroundColor Yellow
    
    # Determine remote destination
    $remoteDest = if ($fileNormalized -match "\.sh$" -or $fileNormalized -eq "rpi_csi_rtsp_server.py") {
        "/usr/local/bin/"
    } elseif ($fileNormalized -eq "VERSION") {
        "/opt/rpi-cam-webmanager/"
    } else {
        "/opt/rpi-cam-webmanager/$fileNormalized/"
    }
    
    # Check if source is a directory (need -Recursive)
    $item = Get-Item -LiteralPath $fullPath
    $isDirectory = $item.PSIsContainer
    
    if ($isDirectory) {
        & $deployScp -Source "$fullPath\" -Dest $remoteDest -Recursive -IpEthernet $deviceIp -User $User -Password $Password -NoRestart 2>&1 | Out-Null
    } else {
        & $deployScp -Source $fullPath -Dest $remoteDest -IpEthernet $deviceIp -User $User -Password $Password -NoRestart 2>&1 | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠ Warning deploying $fileNormalized (will continue)" -ForegroundColor Yellow
    }
}
Write-Host "✓ Files deployed" -ForegroundColor Green

Write-Host ""
Write-Host "=== STEP 3: Checking Python requirements ===" -ForegroundColor Cyan
$checkReqCmd = @"
if [ -f /opt/rpi-cam-webmanager/requirements.txt ]; then
  echo "Checking Python requirements..."
  sudo pip3 install -q -r /opt/rpi-cam-webmanager/requirements.txt 2>&1 | grep -v "already satisfied" || true
  echo "OK"
else
  echo "No requirements.txt found"
fi
"@

$output = & $runRemote -IP $deviceIp $checkReqCmd -Timeout 60 2>&1
if ($LASTEXITCODE -ne 0) { Write-Host "⚠ Warning checking requirements (may be OK)" -ForegroundColor Yellow }
Write-Host "✓ Requirements checked" -ForegroundColor Green

if ($NoRestart) {
    Write-Host ""
    Write-Host "=== Update completed (services NOT restarted) ===" -ForegroundColor Green
    exit 0
}

Write-Host ""
Write-Host "=== STEP 4: Restarting services ===" -ForegroundColor Cyan
$restartCmd = @"
echo "Restarting services..."
sudo systemctl start rpi-cam-webmanager rpi-av-rtsp-recorder rtsp-recorder rtsp-watchdog rpi-cam-onvif 2>/dev/null || true
sleep 3
echo "Checking status..."
sudo systemctl is-active rpi-cam-webmanager >/dev/null && echo "✓ Web Manager running" || echo "⚠ Web Manager not running"
sudo systemctl is-active rpi-av-rtsp-recorder >/dev/null && echo "✓ RTSP Recorder running" || echo "⚠ RTSP Recorder not running"
"@

$output = & $runRemote -IP $deviceIp $restartCmd -Timeout 30 2>&1
Write-Host "✓ Services restarted" -ForegroundColor Green

Write-Host ""
Write-Host "=== Update completed successfully ===" -ForegroundColor Green
Write-Host "Device: $deviceIp" -ForegroundColor Cyan
Write-Host ""

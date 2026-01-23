# get_logs.ps1 - Boite à outils de déboggage (logs + diagnostics)
# Version: 1.1.0
#
# Usage:
#   .\get_logs.ps1                                       # Logs (tous les services)
#   .\get_logs.ps1 -Service "rpi-cam-webmanager"         # Logs d'un service
#   .\get_logs.ps1 -Follow -Service "rtsp-watchdog"      # Suivi temps réel
#   .\get_logs.ps1 -Tool collect -OutputDir "./logs"     # ZIP logs + diagnostics
#
# IP / Meeting:
#   .\get_logs.ps1 -Auto                                # Auto (Meeting + IPs connues)
#   .\get_logs.ps1 -DeviceKey "ABC123" -Auto            # Force DeviceKey + récup IP via Meeting
#   .\get_logs.ps1 -DeviceKey "ABC123" -Token "89915f" -ApiUrl "https://meeting.ygsoft.fr/api" -Auto
#   .\get_logs.ps1 -IP "192.168.1.124"                  # IP personnalisée (override)
#   .\get_logs.ps1 -UseWifi                             # WiFi (IP: 192.168.1.127)

param(
    [ValidateSet("logs","collect","status","info","dmesg","camera","audio","network","rtsp")]
    [string]$Tool = "logs",

    [string]$IP,
    [switch]$UseWifi,
    [string]$IpWifi = "192.168.1.127",
    [switch]$Auto,

    [string]$DeviceKey,
    [string]$Token,
    [string]$ApiUrl,
    [string]$MeetingConfigFile,

    [string]$Service,  # Ex: "rpi-av-rtsp-recorder", "rpi-cam-webmanager", etc.
    [int]$Lines = 200,
    [switch]$Follow,
    [string]$OutputDir,
    [string]$User = "device",
    [string]$Password = "meeting"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Escape-BashSingleQuotes {
    param([Parameter(Mandatory=$true)][string]$Value)
    return ($Value -replace "'", "'\\''")
}

function Test-WslSshpass {
    if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) { return $false }
    try {
        $check = wsl which sshpass 2>$null
        return [bool]$check
    } catch {
        return $false
    }
}

function Invoke-DeviceSsh {
    param(
        [Parameter(Mandatory=$true)][string]$DeviceIP,
        [Parameter(Mandatory=$true)][string]$Command,
        [int]$Timeout = 10
    )

    $sshOptions = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=$Timeout"

    if (Test-WslSshpass) {
        $escapedCmd = Escape-BashSingleQuotes -Value $Command
        $wslCmd = "sshpass -p '$Password' ssh $sshOptions $User@$DeviceIP '$escapedCmd'"
        wsl bash -c $wslCmd
        return
    }

    $sshArgs = @(
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        "-o", "ConnectTimeout=$Timeout",
        "$User@$DeviceIP",
        $Command
    )
    & ssh @sshArgs
}

function Resolve-DeviceIP {
    $defaultEthIp = "192.168.1.202"
    $knownIPs = @("192.168.1.202","192.168.1.124","192.168.1.127")

    if ($IP) { return $IP }
    if ($UseWifi) { return $IpWifi }

    $shouldUseMeeting = $Auto -or [bool]$DeviceKey -or [bool]$Token -or [bool]$ApiUrl -or [bool]$MeetingConfigFile
    if (-not $shouldUseMeeting) { return $defaultEthIp }

    $getDeviceIPScript = Join-Path $PSScriptRoot "Get-DeviceIP.ps1"
    if (-not (Test-Path $getDeviceIPScript)) { return $defaultEthIp }

    . $getDeviceIPScript
    $resolved = Find-DeviceIP -Quiet -ApiUrl $ApiUrl -DeviceKey $DeviceKey -TokenCode $Token -ConfigFile $MeetingConfigFile -KnownIPs $knownIPs
    if ($resolved) { return $resolved }
    return $defaultEthIp
}

$DeviceIP = Resolve-DeviceIP

Write-Host "=== RTSP-Full Debug Toolbox ===" -ForegroundColor Cyan
Write-Host "Tool:     $Tool" -ForegroundColor DarkGray
Write-Host "DeviceIP: $DeviceIP" -ForegroundColor DarkGray
if ($DeviceKey) { Write-Host "DeviceKey: $DeviceKey" -ForegroundColor DarkGray }
if ($Service) { Write-Host "Service:  $Service" -ForegroundColor DarkGray }

# Services standard
$Services = @(
    "rpi-av-rtsp-recorder"
    "rpi-cam-webmanager"
    "rtsp-recorder"
    "rtsp-watchdog"
    "rpi-cam-onvif"
)

# Logs standard
$LogFiles = @(
    "/var/log/rpi-cam/rpi_av_rtsp_recorder.log"
    "/var/log/rpi-cam/rtsp_recorder.log"
    "/var/log/rpi-cam/rtsp_watchdog.log"
    "/var/log/rpi-cam/web_manager.log"
    "/var/log/rpi-cam/onvif_server.log"
)

function Get-ServiceLogs {
    param(
        [string]$ServiceName,
        [int]$LineCount = 200,
        [switch]$FollowMode
    )
    
    Write-Host "`n[Service: $ServiceName]" -ForegroundColor Yellow
    
    try {
        $cmd = if ($FollowMode) {
            "journalctl -u $ServiceName -f --lines=$LineCount"
        } else {
            "journalctl -u $ServiceName -n $LineCount --no-pager"
        }

        if ($FollowMode) {
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 10
            return
        }

        $output = Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 10 2>&1
        if ($output) { Write-Host $output } else { Write-Host "No logs found" -ForegroundColor DarkGray }
    }
    catch {
        Write-Host "Error retrieving logs: $_" -ForegroundColor Red
    }
}

function Get-FileLogs {
    param(
        [string]$FilePath,
        [int]$LineCount = 200
    )
    
    Write-Host "`n[File: $FilePath]" -ForegroundColor Yellow
    
    try {
        $cmd = "sudo -n tail -n $LineCount $FilePath 2>/dev/null || tail -n $LineCount $FilePath 2>/dev/null || echo 'File not found'"
        $output = Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 10 2>&1
        
        if ($output) {
            Write-Host $output
        }
    }
    catch {
        Write-Host "Error retrieving logs: $_" -ForegroundColor Red
    }
}

function Save-Logs {
    param(
        [string]$OutputDirectory
    )
    
    if (-not (Test-Path $OutputDirectory)) {
        New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    }
    
    $timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
    $zipPath = Join-Path $OutputDirectory "device-logs_${timestamp}.zip"
    
    Write-Host "`nCollecting logs to: $OutputDirectory" -ForegroundColor Cyan
    
    # Créer dossier temporaire
    $tempDir = Join-Path $env:TEMP "rpi-logs-$([guid]::NewGuid().ToString().Substring(0,8))"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    try {
        # Récupérer tous les services
        foreach ($svc in $Services) {
            Write-Host "Collecting $svc..." -ForegroundColor DarkGray
            $logFile = Join-Path $tempDir "${svc}_systemd.log"
            $cmd = "journalctl -u $svc -n 500 --no-pager"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 20 2>&1 | Out-File $logFile -Encoding UTF8
        }
        
        # Récupérer les fichiers log
        foreach ($file in $LogFiles) {
            $fname = Split-Path $file -Leaf
            Write-Host "Collecting $fname..." -ForegroundColor DarkGray
            $logFile = Join-Path $tempDir $fname
            $cmd = "sudo -n tail -n 500 $file 2>/dev/null || tail -n 500 $file 2>/dev/null || true"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 20 2>&1 | Out-File $logFile -Encoding UTF8
        }

        # Diagnostics (léger mais utile)
        $diagFile = Join-Path $tempDir "diagnostics.txt"
        $diagCmds = @(
            "date",
            "hostname",
            "uname -a",
            "cat /etc/os-release 2>/dev/null || true",
            "uptime",
            "df -h",
            "free -h || true",
            "ip -br a || ip addr",
            "nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null || true",
            "ss -tulnp | head -n 200 || ss -tuln | head -n 200",
            "pgrep -af 'test-launch|rpi_av_rtsp_recorder|rpi_csi_rtsp_server|ffmpeg|onvif' || true",
            "systemctl --no-pager --failed || true",
            "journalctl -p err..alert -n 200 --no-pager || true",
            "dmesg -T | tail -n 200 || dmesg | tail -n 200"
        )

        "=== RTSP-Full diagnostics ===" | Out-File $diagFile -Encoding UTF8
        foreach ($diagCmd in $diagCmds) {
            "`n$ $diagCmd" | Out-File $diagFile -Append -Encoding UTF8
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $diagCmd -Timeout 20 2>&1 | Out-File $diagFile -Append -Encoding UTF8
        }
        
        # Créer archive
        Write-Host "Creating archive..." -ForegroundColor DarkGray
        Compress-Archive -Path "$tempDir/*" -DestinationPath $zipPath -Force
        
        Write-Host "`n✓ Logs saved to: $zipPath" -ForegroundColor Green
        Write-Host "  Size: $(((Get-Item $zipPath).Length / 1MB).ToString('F2')) MB" -ForegroundColor DarkGray
    }
    finally {
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-Tool {
    switch ($Tool) {
        "logs" {
            if ($Service) {
                if ($Follow) {
                    Get-ServiceLogs -ServiceName $Service -LineCount $Lines -FollowMode
                } else {
                    Get-ServiceLogs -ServiceName $Service -LineCount $Lines
                }
                return
            }

            if ($OutputDir) {
                Save-Logs -OutputDirectory $OutputDir
                return
            }

            foreach ($svc in $Services) {
                Get-ServiceLogs -ServiceName $svc -LineCount $Lines
            }
            Write-Host "`nTip: Use -Tool collect -OutputDir <dir> to export a ZIP (logs + diagnostics)" -ForegroundColor DarkGray
        }

        "collect" {
            if (-not $OutputDir) {
                throw "Missing -OutputDir for -Tool collect"
            }
            Save-Logs -OutputDirectory $OutputDir
        }

        "status" {
            $cmd = "systemctl is-active $($Services -join ' ') ; echo ; systemctl --no-pager --failed || true"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 15
        }

        "info" {
            $cmd = "hostname; echo; uname -a; echo; cat /etc/os-release 2>/dev/null || true; echo; uptime"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 15
        }

        "dmesg" {
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command "dmesg -T | tail -n $Lines || dmesg | tail -n $Lines" -Timeout 15
        }

        "network" {
            $cmd = "ip -br a || ip addr; echo; nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev status 2>/dev/null || true; echo; nmcli -t -f ACTIVE,SSID,DEVICE dev wifi 2>/dev/null | head -n 30 || true"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 20
        }

        "rtsp" {
            $cmd = "ss -tuln | grep -E ':8554\\b' || true; echo; pgrep -af 'test-launch|rpi_av_rtsp_recorder|rpi_csi_rtsp_server|ffmpeg' || true"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 15
        }

        "camera" {
            $cmd = "ls -l /dev/video* 2>/dev/null || true; echo; v4l2-ctl --list-devices 2>/dev/null || true; echo; (rpicam-hello --list-cameras 2>/dev/null || libcamera-hello --list-cameras 2>/dev/null) || true"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 20
        }

        "audio" {
            $cmd = "arecord -l 2>/dev/null || true; echo; aplay -l 2>/dev/null || true; echo; pgrep -af 'pipewire|wireplumber' || true"
            Invoke-DeviceSsh -DeviceIP $DeviceIP -Command $cmd -Timeout 20
        }
    }
}

Invoke-Tool

Write-Host "`nDone." -ForegroundColor Green

#!/usr/bin/env pwsh
<#
.SYNOPSIS
Deploy v2.32.20 immediate heartbeat feature to device

.DESCRIPTION
Deploys the immediate heartbeat feature files and verifies functionality

.PARAMETER DeviceIP
IP address of the device (default: 192.168.1.202)

.EXAMPLE
.\deploy_immediate_heartbeat.ps1
.\deploy_immediate_heartbeat.ps1 -DeviceIP 192.168.1.124

#>

param(
    [string]$DeviceIP = "192.168.1.202"
)

$ErrorActionPreference = "Continue"

Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Deploy: Immediate Heartbeat on Network Reconnection     ║" -ForegroundColor Cyan
Write-Host "║   Version: 2.32.20                                        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Host "`n[STEP 1] Waiting for device SSH..." -ForegroundColor Yellow
$retries = 30
$connected = $false

for ($i = 0; $i -lt $retries; $i++) {
    if (Test-NetConnection -ComputerName $DeviceIP -Port 22 -InformationLevel Quiet) {
        Write-Host "✓ Device is SSH-ready!" -ForegroundColor Green
        $connected = $true
        break
    }
    $remaining = $retries - $i - 1
    Write-Host "  SSH not ready... retrying ($remaining retries left)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

if (-not $connected) {
    Write-Host "✗ Device not SSH-accessible after $retries retries" -ForegroundColor Red
    exit 1
}

Write-Host "`n[STEP 2] Deploying files..." -ForegroundColor Yellow

$files = @(
    @{src = ".\web-manager\services\meeting_service.py"; dest = "/opt/rpi-cam-webmanager/services/"}
    @{src = ".\web-manager\services\network_service.py"; dest = "/opt/rpi-cam-webmanager/services/"}
    @{src = ".\web-manager\services\__init__.py"; dest = "/opt/rpi-cam-webmanager/services/"}
)

foreach ($file in $files) {
    Write-Host "  Deploying $($file.src)..." -ForegroundColor Cyan
    & ".\debug_tools\deploy_scp.ps1" -Source $file.src -Dest $file.dest 2>&1 | Select-Object -Last 1
}

Write-Host "`n[STEP 3] Restarting web service..." -ForegroundColor Yellow
& ".\debug_tools\run_remote.ps1" "sudo systemctl restart rpi-cam-webmanager" 2>&1 | Select-Object -Last 2

Write-Host "`n[STEP 4] Verifying deployment..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host "  Checking Meeting API status..." -ForegroundColor Cyan
$status = & ".\debug_tools\run_remote.ps1" "curl -s http://localhost:5000/api/meeting/status | head -c 200" 2>&1

if ($status -match 'connected') {
    Write-Host "✓ Meeting API responding!" -ForegroundColor Green
    Write-Host "  Status: $($status.substring(0, [Math]::Min(150, $status.length)))..." -ForegroundColor Gray
} else {
    Write-Host "✗ Meeting API not responding" -ForegroundColor Yellow
}

Write-Host "`n[STEP 5] Checking logs for errors..." -ForegroundColor Yellow
$errors = & ".\debug_tools\run_remote.ps1" "journalctl -u rpi-cam-webmanager -n 5 | grep -i error" 2>&1

if ($errors -and $errors -ne "") {
    Write-Host "⚠ Found errors in logs:" -ForegroundColor Yellow
    Write-Host $errors -ForegroundColor Gray
} else {
    Write-Host "✓ No errors in recent logs" -ForegroundColor Green
}

Write-Host "`n╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   Deployment Complete! v2.32.20                           ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "  1. Test failover: Unplug ethernet to trigger WiFi failover"
Write-Host "  2. Watch logs: journalctl -u rpi-cam-webmanager -f"
Write-Host "  3. Verify Meeting API: Check device online status < 3 seconds"
Write-Host "  4. Check heartbeat: curl http://$($DeviceIP):5000/api/meeting/status"

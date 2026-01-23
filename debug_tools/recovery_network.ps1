# recovery_network.ps1 - Emergency network configuration recovery
# Version: 1.0.0
#
# Resets network configuration on a device with broken network settings.
# Useful when a device becomes unreachable after incorrect network config.
#
# The device connects briefly at startup (within 60 seconds), this script 
# waits for that window and fixes the network configuration.
#
# Usage:
#   .\debug_tools\recovery_network.ps1 -DeviceKey "3316A52EB08837267BF6BD3E2B2E8DC7"
#   .\debug_tools\recovery_network.ps1 -IP "192.168.1.4"
#   .\debug_tools\recovery_network.ps1 -DeviceKey "ABC123..." -Verbose
#
# Notes:
# - Requires WSL + sshpass (same as other debug_tools scripts)
# - Uses Meeting API to retrieve device IP from DeviceKey
# - Ping retry: 60 times, 1 second interval (60 second timeout)
# - Configuration restored to DHCP on all interfaces

param(
    [string]$DeviceKey,
    [string]$IP,
    [string]$ApiUrl,
    [string]$Token,
    [string]$User = "device",
    [string]$Password = "meeting",
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $PSCommandPath
$meetingConfig = Join-Path $scriptRoot "meeting_config.json"
$runRemote = Join-Path $scriptRoot "run_remote.ps1"

function Write-Verbose-Custom {
    param([string]$Message)
    if ($Verbose) {
        Write-Host $Message -ForegroundColor DarkGray
    }
}

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

function Resolve-DeviceIP-FromMeeting {
    param(
        [string]$DeviceKey,
        [string]$ApiUrl,
        [string]$Token
    )

    $cfg = Load-MeetingConfig
    if (-not $ApiUrl) { $ApiUrl = $cfg.api_url }
    if (-not $Token) { $Token = $cfg.token_code }

    if ($DeviceKey -and $ApiUrl) {
        try {
            Write-Verbose-Custom "  Querying Meeting API: $ApiUrl/devices/$DeviceKey"
            $url = "$($ApiUrl.TrimEnd('/'))/devices/$DeviceKey"
            if ($Token) {
                $headers = @{ "X-Token-Code" = $Token; "Accept" = "application/json" }
                $resp = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 5 -ErrorAction Stop
            } else {
                $resp = Invoke-RestMethod -Uri $url -TimeoutSec 5 -ErrorAction Stop
            }
            $respIp = Get-MeetingField -Object $resp -Name "ip_address"
            if (-not $respIp) { $respIp = Get-MeetingField -Object $resp -Name "ip" }
            if ($respIp) { 
                Write-Host "✓ Device IP from Meeting API: $respIp" -ForegroundColor Green
                return [string]$respIp 
            }
        } catch {
            Write-Verbose-Custom "  Meeting API query failed: $_"
        }
    }

    return $null
}

function Wait-DevicePing {
    param(
        [string]$IP,
        [int]$MaxRetries = 60,
        [int]$RetryIntervalSeconds = 1
    )
    
    $attempt = 0
    $isPingable = $false
    
    Write-Host "Waiting for device ($IP) to become reachable..." -ForegroundColor Cyan
    Write-Host "Ping retry: $MaxRetries times, $RetryIntervalSeconds second interval (max $($MaxRetries * $RetryIntervalSeconds) seconds)" -ForegroundColor Gray
    Write-Host ""
    
    while ($attempt -lt $MaxRetries -and -not $isPingable) {
        $attempt++
        
        # Test ping
        try {
            $ping = New-Object System.Net.NetworkInformation.Ping
            $result = $ping.Send($IP, 1000)
            if ($result.Status -eq 'Success') {
                $isPingable = $true
                Write-Host "✓ Device responded to ping (attempt $attempt)" -ForegroundColor Green
                return $true
            }
        } catch {
            # Ping failed, continue
        }
        
        if (-not $isPingable) {
            $remainingRetries = $MaxRetries - $attempt
            Write-Host "  Ping attempt $attempt/$MaxRetries failed. Waiting $RetryIntervalSeconds second..." -ForegroundColor Yellow -NoNewline
            
            if ($remainingRetries -eq 0) {
                Write-Host ""
                Write-Host "✗ Device did not respond after $MaxRetries ping attempts" -ForegroundColor Red
                return $false
            }
            
            Start-Sleep -Seconds $RetryIntervalSeconds
            Write-Host " (retrying...)" -ForegroundColor Yellow
        }
    }
    
    return $isPingable
}

function Reset-NetworkConfiguration {
    param(
        [string]$DeviceIP
    )
    
    Write-Host ""
    Write-Host "=== STEP 1: Resetting network configuration ===" -ForegroundColor Cyan
    
    # Build bash script with proper escaping for remote execution
    $resetCmd = @'
echo "Resetting network configuration to DHCP..."

# Get all NetworkManager connections
connections=$(sudo nmcli -t -f NAME connection show 2>/dev/null | grep -v "^$" || echo "")

if [ -n "$connections" ]; then
  echo "  Found connections. Resetting to DHCP..."
  echo "$connections" | while read conn; do
    echo "  Resetting: $conn"
    sudo nmcli con mod "$conn" ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.dns "" 2>/dev/null || true
  done
else
  echo "  No connections found via nmcli"
fi

# Apply changes
echo "Applying network changes..."
sudo nmcli device reapply 2>/dev/null || true
sleep 2

# Restart networking
echo "Restarting network service..."
sudo systemctl restart networking 2>/dev/null || sudo systemctl restart NetworkManager 2>/dev/null || true
sleep 3

echo "✓ Network configuration reset completed"
'@

    Write-Verbose-Custom "Executing network reset commands on device via SSH..."
    $output = & $runRemote -IP $DeviceIP $resetCmd -Timeout 30 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠ Warning during network reset (continuing)" -ForegroundColor Yellow
    } else {
        Write-Host $output -ForegroundColor Green
    }
}

function Validate-Connectivity {
    param(
        [string]$DeviceIP,
        [int]$MaxRetries = 10
    )
    
    Write-Host ""
    Write-Host "=== STEP 2: Validating connectivity after reset ===" -ForegroundColor Cyan
    
    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        $attempt++
        
        try {
            $ping = New-Object System.Net.NetworkInformation.Ping
            $result = $ping.Send($DeviceIP, 1000)
            if ($result.Status -eq 'Success') {
                Write-Host "✓ Device is responding (attempt $attempt/$MaxRetries)" -ForegroundColor Green
                
                # Try to get device info via SSH
                Write-Host ""
                Write-Host "=== STEP 3: Getting device information ===" -ForegroundColor Cyan
                $infoCmd = @'
echo "Network interfaces:"
ip -br addr show 2>/dev/null || ifconfig
echo ""
echo "NetworkManager connections:"
nmcli -t -f NAME,TYPE,STATE connection show 2>/dev/null || echo "nmcli not available"
'@
                $output = & $runRemote -IP $DeviceIP $infoCmd -Timeout 10 2>&1
                Write-Host $output -ForegroundColor Gray
                
                return $true
            }
        } catch {
            # Continue
        }
        
        if ($attempt -lt $MaxRetries) {
            Write-Host "  Waiting for device to stabilize (attempt $attempt/$MaxRetries)..." -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    }
    
    Write-Host "✗ Device did not stabilize after reset" -ForegroundColor Red
    return $false
}

# Main script

if (-not (Test-Path -LiteralPath $runRemote)) {
    throw "run_remote.ps1 not found in $scriptRoot"
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Network Configuration Recovery - Emergency Script             ║" -ForegroundColor Cyan
Write-Host "║  Version: 1.0.0                                               ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Resolve device IP
$deviceIp = $null

if ($IP) {
    $deviceIp = $IP
    Write-Host "Device IP (from argument): $deviceIp" -ForegroundColor Cyan
} elseif ($DeviceKey) {
    Write-Host "Device Key: $DeviceKey" -ForegroundColor Cyan
    Write-Host "Resolving IP from Meeting API..." -ForegroundColor Yellow
    $deviceIp = Resolve-DeviceIP-FromMeeting -DeviceKey $DeviceKey -ApiUrl $ApiUrl -Token $Token
    
    if (-not $deviceIp) {
        Write-Host "✗ Could not resolve device IP from Meeting API" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please provide IP manually:" -ForegroundColor Yellow
        Write-Host "  .\recovery_network.ps1 -IP 192.168.1.4" -ForegroundColor Gray
        exit 1
    }
} else {
    Write-Host "✗ Device Key or IP required" -ForegroundColor Red
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\recovery_network.ps1 -DeviceKey 3316A52EB08837267BF6BD3E2B2E8DC7" -ForegroundColor Gray
    Write-Host "  .\recovery_network.ps1 -IP 192.168.1.4" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# Wait for device to ping
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
if (-not (Wait-DevicePing -IP $deviceIp -MaxRetries 60 -RetryIntervalSeconds 1)) {
    Write-Host ""
    Write-Host "✗ FAILED: Device did not respond within 60 seconds" -ForegroundColor Red
    Write-Host ""
    Write-Host "Possible causes:" -ForegroundColor Yellow
    Write-Host "  - Device is not powered on" -ForegroundColor Gray
    Write-Host "  - Device has a broken network config and won't come back online" -ForegroundColor Gray
    Write-Host "  - Network connectivity issue" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan

# Device is reachable, execute recovery steps
Reset-NetworkConfiguration -DeviceIP $deviceIp

# Validate after reset
if (Validate-Connectivity -DeviceIP $deviceIp) {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "✓ RECOVERY SUCCESSFUL" -ForegroundColor Green
    Write-Host ""
    Write-Host "Device network configuration has been reset to DHCP." -ForegroundColor Green
    Write-Host "Device should now be accessible via DHCP." -ForegroundColor Green
    Write-Host ""
    exit 0
} else {
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "⚠ RECOVERY INCOMPLETE" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Network reset was executed but device did not stabilize." -ForegroundColor Yellow
    Write-Host "Manual intervention may be required." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

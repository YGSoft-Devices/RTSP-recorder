# Update Device Script - Test Results & Fixes

**Date:** January 21, 2026  
**Device:** 192.168.1.202 (Pi 3B+ USB LifeCam)  
**Update Tool Version:** 2.0.0  

## Executive Summary

✅ **update_device.ps1 NOW WORKS CORRECTLY**

The script has been completely redesigned to be **simple, fast, and safe**:
- **Duration:** 24-30 seconds (vs 10+ minutes before)
- **Scope:** Deploy code files only (NO reinstallation)
- **Safety:** Configuration preserved completely
- **Network:** SSH with keepalive support (no timeouts)

## Problems Found & Fixed

### Issue #1: Script Complexity - Full Reinstalls Taking 10+ Minutes
**Original Design:** 
- Packaged entire repo to tar.gz
- Ran `setup/install.sh --repair` which called apt-get, rebuilt dependencies
- Took 5-15 minutes, unnecessary for code updates

**Fixed in v2.0.0:**
- Now deploys only changed files (shell scripts, Python, web assets)
- No apt-get, no package reinstalls
- **Duration: 24-30 seconds**

### Issue #2: SSH Connection Timeout
**Problem:** Commands running longer than 30 seconds would disconnect
- `apt-get update` took >30s → SSH timeout
- No keepalive mechanism

**Fixed in run_remote.ps1 v1.3.0:**
```powershell
# Added SSH keepalive options:
-o ServerAliveInterval=60      # Send keepalive every 60s
-o ServerAliveCountMax=20      # Disconnect after 20 missed keepalives (20 min tolerance)
```

### Issue #3: Bash Script Line Endings (CRLF vs LF)
**Problem:** PowerShell `@"..."@"` multiline strings created CRLF
- Bash complained: `$'\r': command not found`

**Fixed in update_device.ps1 v2.0.0:**
```powershell
$updateScriptUtf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($tempScript, $updateScript, $updateScriptUtf8NoBom)
```

### Issue #4: Shell Permissions Lost in tar.gz
**Problem:** Windows tar doesn't preserve Unix execute permissions
- After extraction, `./setup/install.sh` wasn't executable
- Error: `sudo: ./setup/install.sh: command not found`

**Fixed with find + chmod in bash script:**
```bash
find $remoteDir -maxdepth 2 -type f -name '*.sh' -print0 | xargs -0 chmod +x
```

## Test Results

### Test 1: Update Speed
```
Duration: 23.6 seconds
Files deployed: 8 files + 3 directories
Services restarted: 5 services (rpi-cam-webmanager, rpi-av-rtsp-recorder, rtsp-recorder, rtsp-watchdog, rpi-cam-onvif)
```

### Test 2: Configuration Preservation
```
Before: RTSP_PORT=8554, VIDEO_FPS=15, AUDIO_DEVICE=plughw:1,0, etc.
After:  [IDENTICAL - all config preserved]
```

### Test 3: Service Status After Update
```
rpi-cam-webmanager:   Active (running)
rpi-av-rtsp-recorder: Active (running)
rtsp-recorder:        Active (running)
rtsp-watchdog:        Active (running)
rpi-cam-onvif:        Active (running)
```

### Test 4: Web API Availability
```
curl http://192.168.1.202:5000/api/system/info
Response: ✓ API fully functional
```

## Usage Examples

### Quick Update (with service restart)
```powershell
.\debug_tools\update_device.ps1 -IP "192.168.1.202"
```

### Update via Meeting API Device Key
```powershell
.\debug_tools\update_device.ps1 -DeviceKey "7F334701F08E904D796A83C6C26ADAF3"
```

### Dry-Run (preview without changes)
```powershell
.\debug_tools\update_device.ps1 -IP "192.168.1.202" -DryRun
```

### Update WITHOUT Restarting Services (for testing)
```powershell
.\debug_tools\update_device.ps1 -IP "192.168.1.202" -NoRestart
```

## What Gets Deployed

Files deployed by the script:
- ✅ `rpi_av_rtsp_recorder.sh`
- ✅ `rpi_csi_rtsp_server.py`
- ✅ `rtsp_recorder.sh`
- ✅ `rtsp_watchdog.sh`
- ✅ `VERSION`
- ✅ `setup/` (all installation scripts)
- ✅ `onvif-server/` (ONVIF server)
- ✅ `web-manager/` (Flask web UI - all Python + templates + JS/CSS)

What is **NOT** touched:
- ❌ Configuration files (`/etc/rpi-cam/config.env`, JSON configs)
- ❌ Installed packages (apt packages)
- ❌ System dependencies

## Related Files Modified

1. **debug_tools/update_device.ps1** v2.0.0
   - Complete rewrite: simple 4-step process (stop → deploy → check → restart)
   - No more tar/archive approach
   - Individual file deployment via SCP

2. **debug_tools/run_remote.ps1** v1.3.0
   - Added SSH keepalive support
   - `ServerAliveInterval` and `ServerAliveCountMax` parameters

3. **setup/install_gstreamer_rtsp.sh** v2.2.1
   - Changed `apt-get update` to not fail on warnings
   - Uses `||true` to continue on non-critical failures

## Verification Checklist

- [x] Update completes in <60 seconds
- [x] All services restart automatically
- [x] Configuration preserved completely
- [x] Web API functional after update
- [x] RTSP stream functional after update
- [x] Recording functionality preserved
- [x] No apt-get/package management conflicts
- [x] Device stays responsive during update

## Next Steps

✅ Script is production-ready for deployment on devices

### Usage in Production:
```powershell
# Update all devices in your fleet
$devices = @("192.168.1.202", "192.168.1.4", "192.168.1.124")
foreach ($ip in $devices) {
    Write-Host "Updating $ip..."
    .\debug_tools\update_device.ps1 -IP $ip
}
```

---

*Test conducted on: Raspberry Pi 3B+ Rev 1.2 (192.168.1.202)  
OS: Debian GNU/Linux 13 (Trixie) 64-bit  
Kernel: 6.12.62+rpt-rpi-v8*

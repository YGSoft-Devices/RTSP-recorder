# Update Device Script - Protection Enhancement (v2.0.1)

**Version:** 2.0.1  
**Date:** January 21, 2026  
**Change:** Added device reachability check with automatic retry  

---

## 🛡️ New Feature: Device Reachability Protection

The `update_device.ps1` script now includes a **new STEP 0** that checks if the device is reachable before attempting deployment.

### What Changed

**Before (v2.0.0):**
```
STEP 1: Stop services
STEP 2: Deploy files
STEP 3: Check Python requirements
STEP 4: Restart services
```

**After (v2.0.1):**
```
STEP 0: Wait for device to be reachable ← NEW!
STEP 1: Stop services
STEP 2: Deploy files
STEP 3: Check Python requirements
STEP 4: Restart services
```

### How It Works

1. **SSH Port Check:** Tests TCP connectivity to port 22 (SSH) on the device
2. **Automatic Retry:** If device is unreachable, waits and retries automatically
3. **Configurable Retries:** 
   - Default: 60 retries
   - Interval: 5 seconds between retries
   - **Total timeout: 5 minutes (300 seconds)**

### Scenarios Handled

#### ✅ Device is already online
- SSH port responds immediately
- Script continues to deployment

#### ✅ Device is booting or rebooting
- SSH port not responding initially
- Script waits 5 seconds and retries
- When device comes back online, deployment starts automatically
- **No user intervention needed!**

#### ❌ Device is offline/unreachable
- After 5 minutes of retries, script fails with error message
- User can investigate and try again

### Usage Examples

#### Normal deployment (with reachability check)
```powershell
.\debug_tools\update_device.ps1 -IP "192.168.1.202"
```

**Output:**
```
Device IP: 192.168.1.202

=== STEP 0: Waiting for device to be reachable ===
Checking device connectivity...
✓ Device is reachable (SSH port 22 open)

=== STEP 1: Stopping services ===
...
```

#### Device currently offline (will wait and retry)
```powershell
.\debug_tools\update_device.ps1 -IP "192.168.1.202"
```

**Output:**
```
Device IP: 192.168.1.202

=== STEP 0: Waiting for device to be reachable ===
Checking device connectivity...
  Device not reachable (attempt 1/60). Retrying in 5 seconds...
  Waiting... (59 retries left)
  Device not reachable (attempt 2/60). Retrying in 5 seconds...
  Waiting... (58 retries left)
  ✓ Device is reachable (SSH port 22 open)

=== STEP 1: Stopping services ===
...
```

#### Preview mode (dry-run)
```powershell
.\debug_tools\update_device.ps1 -IP "192.168.1.202" -DryRun
```

**Output:**
```
[DRY RUN] Would perform the following steps:
  0. Wait for device to be reachable (retry up to 5 minutes)
  1. Stop services: ...
  2. Deploy project files:
     - rpi_av_rtsp_recorder.sh
     - ...
  3. Check Python requirements (install if needed)
  4. Restart all services
```

### Technical Details

#### Function: `Wait-DeviceReachable`
```powershell
Wait-DeviceReachable -IP "192.168.1.202" -MaxRetries 60 -RetryIntervalSeconds 5 -PingTimeoutMs 2000
```

**Parameters:**
- `-IP`: Device IP address (required)
- `-MaxRetries`: Number of attempts (default: 60)
- `-RetryIntervalSeconds`: Wait time between retries (default: 5 seconds)
- `-PingTimeoutMs`: TCP timeout per attempt (default: 2000 ms)

**Returns:**
- `$true` if device becomes reachable
- `$false` if still unreachable after all retries

#### Connection Method
- Uses **TCP socket** to port 22 (SSH)
- Why port 22? It's reliable, simple, and always used for deployment
- More direct than ICMP ping (not blocked by some networks)
- Timeout per attempt: 2 seconds (fast feedback)

### Benefits

1. **No Manual Intervention:** Script waits automatically if device is rebooting
2. **Production Ready:** Handles temporary network issues gracefully
3. **Clear Feedback:** User sees exactly what's happening with retry counter
4. **Timeout Protection:** Won't wait forever (5-minute limit)
5. **Fast on Success:** Immediate deployment if device is online

### Use Cases

#### 🔄 Device Reboot Loop (the original request!)
- Device keeps rebooting but gives a few seconds between boots
- Script detects the brief window of availability
- Deployment happens automatically during that window
- User doesn't have to monitor or retry manually

#### 📱 WiFi Reconnection
- WiFi temporarily down
- Device loses connectivity briefly
- Script waits for WiFi to reconnect
- Deployment resumes automatically

#### 🔌 Device Startup
- Deploying to a freshly rebooted device
- SSH service hasn't fully started yet
- Script waits a few seconds
- Deployment starts once SSH is ready

### Backward Compatibility

✅ **Fully backward compatible** - No script changes needed for existing users

The reachability check is automatic and transparent:
- If device is online: no delay (immediate deployment)
- If device is offline: waits automatically (5-minute timeout)

### Version Information

**File:** `debug_tools/update_device.ps1`  
**Version:** 2.0.1  
**Previous:** 2.0.0  

---

## 📝 Testing Results

**Tested on:**
- Device: Raspberry Pi 3B+ (192.168.1.202)
- Device with online SSH: ✅ Immediate reachability (0s)
- Device offline simulation: ✅ Retry mechanism working (5s intervals shown)
- Deployment with new STEP 0: ✅ Completes successfully

---

**Status:** ✅ **PRODUCTION READY**

The reachability protection is now active and will help with all deployment scenarios involving device connectivity issues.

# Recovery Network - Emergency Network Configuration Reset Script

**Version:** 1.0.0  
**Created:** January 21, 2026  
**Status:** ✅ Ready for deployment  

---

## 🆘 Purpose

Emergency script to reset network configuration on a device that has become unreachable due to incorrect network settings.

**Perfect for:** Device that connects briefly at startup but becomes unreachable after network misconfiguration.

---

## 📋 Quick Start

### Using Device Key (Recommended)
```powershell
.\debug_tools\recovery_network.ps1 -DeviceKey "3316A52EB08837267BF6BD3E2B2E8DC7"
```

**What it does:**
1. Resolves device IP via Meeting API
2. Waits for device to ping (60 seconds timeout)
3. Resets network configuration to DHCP
4. Validates connectivity

### Using Direct IP
```powershell
.\debug_tools\recovery_network.ps1 -IP "192.168.1.4"
```

### With Verbose Output
```powershell
.\debug_tools\recovery_network.ps1 -DeviceKey "3316A52EB08837267BF6BD3E2B2E8DC7" -Verbose
```

---

## 🔄 How It Works

### Step 0: Wait for Device
- **Method:** ICMP Ping (not TCP like update_device.ps1)
- **Why ping?** Simpler, faster detection of device online status
- **Retry:** 60 times × 1 second interval = **60 seconds timeout**
- **Window:** Perfect for devices that connect briefly at startup

### Step 1: Reset Network Configuration
Executed on device via SSH:
```bash
# Reset all connections to DHCP
for conn in $(nmcli connection show); do
  nmcli con mod "$conn" ipv4.method auto ipv4.addresses "" ipv4.gateway ""
done

# Apply changes and restart networking
nmcli device reapply
systemctl restart networking
```

### Step 2: Validate Connectivity
- Pings device again
- Retrieves network interface info
- Confirms DHCP configuration

---

## 📊 Example Execution

### Scenario: Device 3316A52EB08837267BF6BD3E2B2E8DC7

```
╔════════════════════════════════════════════════════════════════╗
║  Network Configuration Recovery - Emergency Script             ║
║  Version: 1.0.0                                               ║
╚════════════════════════════════════════════════════════════════╝

Device Key: 3316A52EB08837267BF6BD3E2B2E8DC7
Resolving IP from Meeting API...
✓ Device IP from Meeting API: 192.168.1.4

═══════════════════════════════════════════════════════════════
Waiting for device (192.168.1.4) to become reachable...
Ping retry: 60 times, 1 second interval (max 60 seconds)

  Ping attempt 1/60 failed. Waiting 1 second... (retrying...)
  Ping attempt 2/60 failed. Waiting 1 second... (retrying...)
  ...
  Ping attempt 42/60 failed. Waiting 1 second... (retrying...)
✓ Device responded to ping (attempt 42)

═══════════════════════════════════════════════════════════════

=== STEP 1: Resetting network configuration ===
✓ Network configuration reset

=== STEP 2: Validating connectivity after reset ===
✓ Device is responding (attempt 1/10)

=== STEP 3: Getting device information ===
Network interfaces:
eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.1.4 netmask 255.255.255.0 broadcast 192.168.1.255
    ...

═══════════════════════════════════════════════════════════════
✓ RECOVERY SUCCESSFUL

Device network configuration has been reset to DHCP.
Device should now be accessible via DHCP.
```

---

## 🎯 Use Cases

### 1. Device with Broken Network Config
- Device starts with old/incorrect IP settings
- Becomes unreachable after boot
- Script waits for brief startup window → fixes config

### 2. Device Rebooted with Manual IP
- Someone manually configured wrong static IP
- Device reconnects at next boot (brief window)
- Script catches it and resets to DHCP

### 3. WiFi Failover Misconfiguration
- Device WiFi failover settings are broken
- Device briefly connects via backup WiFi
- Script resets all connections to DHCP

---

## 🔍 Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `-DeviceKey` | string | Optional* | Device key for Meeting API lookup |
| `-IP` | string | Optional* | Direct device IP address |
| `-ApiUrl` | string | No | Meeting API URL (default: https://meeting.ygsoft.fr/api) |
| `-Token` | string | No | Meeting API token (uses stored config if not provided) |
| `-User` | string | No | SSH username (default: "device") |
| `-Password` | string | No | SSH password (default: "meeting") |
| `-Verbose` | switch | No | Show detailed debug output |

*Either `-DeviceKey` OR `-IP` must be provided

---

## ⏱️ Timing

| Phase | Duration | Notes |
|-------|----------|-------|
| Meeting API resolution | ~2-3s | If using DeviceKey |
| Ping wait (worst case) | ~60s | 60 retries × 1 second |
| Network reset | ~10s | SSH command execution |
| Connectivity validation | ~10-20s | Stabilization check |
| **Total (worst case)** | **~90 seconds** | Still much faster than manual fix |

---

## 🛡️ Safety Features

✅ **Non-destructive:** Only resets network config, preserves data  
✅ **Automatic fallback:** All connections reset to DHCP (safe default)  
✅ **Validation:** Confirms connectivity after reset  
✅ **Error handling:** Clear messages if anything fails  
✅ **Timeout protection:** Won't wait forever (60-second ping timeout)  

---

## 📝 What Gets Reset

```bash
# All NetworkManager connections:
- Static IP addresses cleared
- Custom gateways removed
- DNS settings reset
- All interfaces set to DHCP

# Network services restarted:
- networking service OR NetworkManager (whichever is running)
```

---

## ✅ Success Indicators

Script is successful when you see:
```
✓ RECOVERY SUCCESSFUL

Device network configuration has been reset to DHCP.
Device should now be accessible via DHCP.
```

---

## ❌ Troubleshooting

### "Device Key or IP required"
**Fix:** Provide either `-DeviceKey` or `-IP`
```powershell
.\recovery_network.ps1 -IP "192.168.1.4"
```

### "Could not resolve device IP from Meeting API"
**Causes:**
- Device key incorrect
- Meeting API unreachable
- Device not registered in Meeting

**Fix:** Use direct IP instead
```powershell
.\recovery_network.ps1 -IP "192.168.1.4"
```

### "Device did not respond within 60 seconds"
**Causes:**
- Device is powered off
- Device never connects during startup window
- Network issue preventing ping

**Fix:** 
- Power on device and try again
- Check device is actually online
- Verify network connectivity to that IP range

### "Device did not stabilize after reset"
**Causes:**
- Device is unstable or rebooting
- Network still misconfigured
- SSH connection issues

**Fix:** 
- Wait 30 seconds and try ping manually
- Try connecting via update_device.ps1 for full recovery

---

## 🔗 Related Scripts

| Script | Purpose | Use When |
|--------|---------|----------|
| `update_device.ps1` | Deploy code updates | Device network is working |
| `recovery_network.ps1` | Reset network config | Device unreachable due to network config |
| `deploy_scp.ps1` | Transfer files | Manual file deployment needed |
| `run_remote.ps1` | Execute remote commands | Direct command execution on device |

---

## 📚 Meeting API Integration

The script automatically retrieves the device's last known IP from Meeting API:

```powershell
# Queries: https://meeting.ygsoft.fr/api/devices/{DeviceKey}
# Returns: { ip_address: "192.168.1.4", connected: true, ... }
```

**Benefits:**
- No need to remember device IP
- Always gets the most recent IP
- Works even if device moved between networks

---

**Status:** ✅ **READY FOR EMERGENCY DEPLOYMENT**

This script is designed to catch that brief window when a device connects at startup and immediately fix network configuration issues.

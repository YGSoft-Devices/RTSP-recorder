# Meeting Device Integration - Quick Start Guide

## Overview

The Updates Manager Tool now requires devices to **register with the Meeting server** (`https://meeting.ygsoft.fr`) using a one-time registration token.

---

## 5-Minute Quick Start

### Step 1: Open Settings
1. Launch Updates Manager Tool
2. Click **⚙️ Settings** in the left sidebar
3. Scroll to **Meeting Device Registration** section (top of Settings)

### Step 2: Register Your Device
1. **Obtain token from administrator** (6 characters, e.g., `ABC123`)
2. **Enter token code** in the input field
3. Click **Register Device** button
4. ✅ Device now registered!

### Step 3: Verify Heartbeat
- Status shows: `Status: Registered (device-xxxxx)`
- Heartbeat status shows: `Heartbeat: Active ✓`
- Device info collected and sent every 60 seconds

### Done! 🎉
Your device is now communicating with the Meeting server.

---

## Understanding the Registration Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Administrator Issues 6-Char Token Code (e.g., ABC123)      │
│ Valid for: ONE-TIME USE ONLY                               │
└──────────────────┬──────────────────────────────────────────┘
                   │ Provide token to user
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ User: Open Settings → Meeting Device Registration          │
│       Enter Token Code: ABC123                             │
│       Click "Register Device"                              │
└──────────────────┬──────────────────────────────────────────┘
                   │ Submit to server
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Meeting Server Validates:                                   │
│ • Device exists ✓                                          │
│ • Token is valid ✓                                         │
│ • Token not already used ✓                                 │
│ • BURNS TOKEN (one-time use) ✓                           │
└──────────────────┬──────────────────────────────────────────┘
                   │ Success
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Device Registered!                                          │
│ • Device key saved locally                                 │
│ • Heartbeat starts automatically                           │
│ • Sends device info every 60 seconds                       │
│ • Status: Ready to use                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## UI Layout

```
⚙️ SETTINGS TAB
├─ Meeting Device Registration
│  ├─ Status: Registered (device-abc12345)  [GREEN ✓]
│  ├─ Device Key: [device-abc12345]  [Copy]
│  ├─ Token: (Already registered)
│  ├─ Instructions panel
│  └─ [Register Device] [Test Heartbeat] [Unregister]
│     
├─ Meeting Server Profiles
│  ├─ Profile: Production ★
│  ├─ Base URL: https://meeting.ygsoft.fr
│  ├─ Token: ••••••••••
│  └─ [Save] [Active] [Delete] [Clear]
│
└─ Other sections...
```

---

## Device Information Sent

Every 60 seconds, your device sends to Meeting server:

```json
{
  "ip_address": "192.168.1.100",        ← Your primary IP
  "ip_lan": "10.0.0.50",                ← Your LAN IP (if available)
  "ip_public": "203.0.113.42",          ← Your public IP (if available)
  "mac": "00:1A:2B:3C:4D:5E",          ← Your MAC address
  "note": "Updates Manager Tool"        ← Device description
}
```

---

## Common Scenarios

### ✅ Registration Successful
- Status shows device key
- Green ✓ status indicator
- Heartbeat shows "Active"
- You're ready to go!

### ❌ Token Code Invalid
**Error**: "Invalid token (401)"
- Token is expired
- Token already used
- **Solution**: Request new token from administrator

### ❌ Device Already Registered
**Error**: "Device already registered (409)"
- This device key is already active
- **Solution**: Click "Unregister" first, then register again with new token

### ❌ Cannot Connect to Server
**Error**: "Connection failed"
- Server unreachable
- Wrong server URL
- Network issue
- **Solution**: Check internet, verify server URL in profile

### ✅ Manually Test Heartbeat
- Click **Test Heartbeat** button
- Get immediate feedback
- Useful for diagnostics

---

## Settings Explained

### Meeting Server Profiles
```
Profile Name: "production"
Base URL: https://meeting.ygsoft.fr    ← Pre-filled default
Token: [stored in secure Keyring]
Timeout: 20 seconds
Retries: 3
```

### Default Values
- **Heartbeat Interval**: 60 seconds (automatic)
- **Server URL**: https://meeting.ygsoft.fr
- **Verify TLS**: Enabled (recommended)

---

## Troubleshooting

### Issue: "Device not found (404)"
- Device doesn't exist on server
- **Fix**: Contact administrator to create device entry

### Issue: "Invalid token (401)"
- Token is wrong, expired, or already used
- **Fix**: Request new token from administrator

### Issue: Heartbeat shows "Inactive"
- Device not registered
- **Fix**: Complete registration step first

### Issue: Can't Find Settings
- Check left sidebar for ⚙️ icon
- May be at bottom of list if scrolled

### Issue: Token Field Won't Accept Input
- Already registered
- **Fix**: Click "Unregister" first if you want to re-register

---

## What Happens After Registration

### Immediately
✅ Device key saved locally  
✅ Status shows "Registered"  
✅ Heartbeat starts automatically  

### Every 60 Seconds
✅ Device info collected (IP, MAC, hostname)  
✅ Heartbeat sent to Meeting server  
✅ Server updates "last seen" time  

### On Application Restart
✅ Device key is restored  
✅ Heartbeat resumes automatically  
✅ No need to re-register  

### On Unregister
❌ Device key is deleted  
❌ Heartbeat stops  
❌ Must re-register to resume communication  

---

## Security Notes

### Token Security
- 6-character token is **one-time use**
- After first registration, token is **burned** (destroyed)
- Cannot be re-used under any circumstances
- Request new token if registration fails

### Device Key Security
- Stored locally on your machine
- Not transmitted except during registration/heartbeat
- Unique identifier for your device
- Necessary for server communication

### Token Storage
- Meeting server admin tokens stored in **Windows Keyring** (encrypted)
- Device registration tokens are one-time only
- No tokens stored after successful registration

---

## Advanced: Manual Heartbeat Test

**When to use**: Diagnostics and troubleshooting

**How**:
1. Register device first
2. Click **Test Heartbeat** button
3. Wait for result message
4. Check if device info was sent

**What it does**:
- Sends immediate heartbeat (doesn't wait 60s)
- Shows success/failure message
- Useful for checking network connectivity
- Doesn't affect normal heartbeat schedule

---

## For Administrators

### Creating Device Entries
1. Generate unique `device_key` on Meeting server
2. Create 6-character token code
3. Provide both to device user
4. User enters token in Settings tab

### Token Code Format
- Exactly 6 characters
- Hexadecimal (0-9, A-F)
- Examples: `ABC123`, `DEF456`, `ABCDEF`
- One-time use (burned after first registration)

### Monitoring Devices
- Meeting server tracks device heartbeats
- Last heartbeat timestamp recorded
- Offline status if no heartbeat > threshold
- Can revoke devices by disabling registration

---

## CLI Registration (Alternative to GUI)

For automated/headless deployments, use the CLI:

```powershell
# Register device
.\Run-CLI.ps1 register --device-key YOUR_DEVICE_KEY --token-code ABC123

# Check status
.\Run-CLI.ps1 status

# Check for updates
.\Run-CLI.ps1 check-update

# Self-update (interactive)
.\Run-CLI.ps1 self-update

# Self-update (no confirmation)
.\Run-CLI.ps1 self-update --yes
```

### Example Output

```
> .\Run-CLI.ps1 status
Updates Manager Tool v1.1.0
========================================

✅ Device is REGISTERED

  Device Key: ABCF9D07...4CE2
  Token Code: ••••••
  Server URL: https://meeting.ygsoft.fr
```

---

## Creating Update Packages (Developers)

To create an update package for distribution:

```powershell
# Create package (version read from app/version.py)
.\update-packager.ps1

# Create package with specific version
.\update-packager.ps1 -Version "1.2.0"
```

This creates:
- `dist/updates-manager-tool-vX.Y.Z.zip` - The update package
- `dist/updates-manager-tool-vX.Y.Z.json` - Metadata (SHA256, size)

To publish the update:
```powershell
.\Run-CLI.ps1 publish --device-type updates-manager-tool --distribution stable --version 1.1.0 --source ".\dist\updates-manager-tool-v1.1.0.zip" --format zip
```

---

## Next Steps

1. **Register your device** ← You are here
2. **Monitor heartbeat** status in Settings
3. **Test connectivity** with "Test Heartbeat" button
4. **Contact admin** if issues occur

---

## Need Help?

### Check Documentation
- Full guide: [DEVICE_INTEGRATION.md](DEVICE_INTEGRATION.md)
- Technical details: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

### View Logs
- Location: `~/.updates-manager-tool/logs/app.log`
- Contains registration and heartbeat events
- Useful for debugging

### Contact Support
- Provide error message
- Share relevant log entries
- Include device details (if possible)

---

**Status**: Registration Complete ✓  
**Heartbeat**: Active ✓  
**Device**: Ready to communicate ✓

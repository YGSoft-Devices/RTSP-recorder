# Emergency Commands Reference

Quick reference for device emergency scenarios.

---

## 🆘 Device Unreachable - Network Config Broken

**Symptom:** Device becomes unreachable after config change, but connects briefly at startup

**Command:**
```powershell
# Using device key (auto-resolves IP via Meeting API)
.\debug_tools\recovery_network.ps1 -DeviceKey "3316A52EB08837267BF6BD3E2B2E8DC7"

# OR using direct IP
.\debug_tools\recovery_network.ps1 -IP "192.168.1.4"
```

**What it does:** Waits for device to come online (60-second window), then resets all network config to DHCP

**Expected time:** ~60 seconds

---

## 🔄 Device Rebooting in a Loop

**Symptom:** Device reboots continuously but leaves a few seconds online

**Command:**
```powershell
# Wait for device and update code
.\debug_tools\update_device.ps1 -DeviceKey "3316A52EB08837267BF6BD3E2B2E8DC7"

# OR if you know the IP
.\debug_tools\update_device.ps1 -IP "192.168.1.4"
```

**What it does:** Waits for device (5-minute timeout), then deploys fixes

**Expected time:** 24-60 seconds once device is reachable

---

## 📋 Quick Device Status

```powershell
# Get device info via Meeting API
.\debug_tools\Get-DeviceIP.ps1 -DeviceKey "3316A52EB08837267BF6BD3E2B2E8DC7"

# Check last 20 logs
.\debug_tools\run_remote.ps1 -IP "192.168.1.4" "sudo journalctl -u rpi-cam-webmanager -n 20"

# Check service status
.\debug_tools\run_remote.ps1 -IP "192.168.1.4" "sudo systemctl status rpi-cam-webmanager"

# Restart services
.\debug_tools\run_remote.ps1 -IP "192.168.1.4" "sudo systemctl restart rpi-cam-webmanager"
```

---

## 🚨 Device Keys Reference

**Test Devices:**
- `3316A52EB08837267BF6BD3E2B2E8DC7` - Pi 3B+ with CSI camera (192.168.1.4)
- `7F334701F08E904D796A83C6C26ADAF3` - Pi 3B+ with USB camera (192.168.1.202)

---

## 🔧 On-Device Emergency Commands (via SSH)

```bash
# Reset network to DHCP
sudo nmcli con mod "Wired connection 1" ipv4.method auto
sudo nmcli device reapply
sudo systemctl restart networking

# Restart all services
sudo systemctl restart rpi-cam-webmanager rpi-av-rtsp-recorder rtsp-recorder rtsp-watchdog

# Check if SSH is accessible
sudo systemctl status ssh

# Emergency reboot
sudo reboot
```

---

## 📱 For Device with Broken SSH

If SSH password changed or is broken:

1. **Connect via HDMI** if available
2. **Use serial console** if available
3. **Wait for boot and use recovery_network.ps1** with default credentials

---

## ⏱️ Decision Tree

```
Device unreachable?
│
├─ Can you ping it?
│  ├─ YES: Try update_device.ps1 or run_remote.ps1
│  └─ NO: Go to next step
│
├─ Did it connect briefly?
│  ├─ YES: Use recovery_network.ps1 NOW (60-second window!)
│  └─ NO: Try update_device.ps1 -DryRun (shows what would happen)
│
├─ Nothing worked after 5 minutes?
│  └─ Device is likely offline or broken
│     - Check power supply
│     - Check network connectivity
│     - Connect via HDMI/serial if available
│     - Consider factory reset
```

---

## 📞 Support Info

**If recovery fails:**

1. **Note the device key:** `3316A52EB08837267BF6BD3E2B2E8DC7`
2. **Check Meeting API last status:** Recent IP address and timestamp
3. **Run with -Verbose flag** to see detailed debug output
4. **Check device logs** once connected: `sudo journalctl -xe`

---

**Last updated:** January 21, 2026

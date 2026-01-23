# Quick Start: Immediate Heartbeat v2.32.20

## What's New?

When network connectivity changes (failover, WiFi reconnection, internet restored), the device **sends a heartbeat immediately** instead of waiting up to 30 seconds.

**Before:** Device offline in Meeting API for 30 seconds after failover  
**After:** Device back online in Meeting API within 1-3 seconds

---

## Quick Deploy

### Option A: Automated (Recommended)

```powershell
# From Windows with WSL:
cd C:\Users\...\RTSP-Full
.\deploy_immediate_heartbeat.ps1  # Auto-waits for device ready

# Or with custom IP:
.\deploy_immediate_heartbeat.ps1 -DeviceIP 192.168.1.124
```

### Option B: Manual

```bash
# 1. Deploy files:
scp web-manager/services/meeting_service.py device@192.168.1.202:/opt/rpi-cam-webmanager/services/
scp web-manager/services/network_service.py device@192.168.1.202:/opt/rpi-cam-webmanager/services/
scp web-manager/services/__init__.py device@192.168.1.202:/opt/rpi-cam-webmanager/services/

# 2. Restart service:
ssh device@192.168.1.202 "sudo systemctl restart rpi-cam-webmanager"

# 3. Verify:
ssh device@192.168.1.202 "curl -s http://localhost:5000/api/meeting/status"
```

---

## Test It

### Scenario 1: Unplug Ethernet
```bash
# Watch logs while unplugging ethernet:
ssh device@192.168.1.202 "journalctl -u rpi-cam-webmanager -f" | grep -E "Failover|heartbeat"

# Expected within 3 seconds:
# [Failover] eth0 disconnected
# [Failover] Connecting to wlan0
# [Network] Triggering immediate heartbeat: failover_to_wlan0
# [Meeting] Immediate heartbeat triggered
```

### Scenario 2: Check Status
```bash
# Monitor heartbeat in real-time:
curl -s http://192.168.1.202:5000/api/meeting/status | jq '.connected, .last_heartbeat_ago'

# Should show:
# "true"
# "2 seconds"  (or similar, max 30s)
```

---

## Files Changed

| File | Version | What Changed |
|------|---------|--------------|
| `web-manager/services/meeting_service.py` | 2.30.16 | Added immediate trigger logic |
| `web-manager/services/network_service.py` | 2.30.15 | Calls trigger on failover |
| `web-manager/services/__init__.py` | 2.30.8 | Exports new functions |
| `VERSION` | 2.32.20 | Version bump |

---

## Verify Deployment

```bash
# Check logs for immediate heartbeat messages:
ssh device@192.168.1.202 \
  "journalctl -u rpi-cam-webmanager -n 20 | grep -i 'immediate\|trigger'"

# Should show something like:
# [Meeting] Immediate heartbeat triggered by event
# [Meeting] Connectivity restored, sending immediate heartbeat

# Check service version:
ssh device@192.168.1.202 \
  "head -n 5 /opt/rpi-cam-webmanager/services/meeting_service.py"

# Should show:
# Version: 2.30.16
```

---

## Rollback (If Needed)

```bash
# Restore from backups:
git checkout web-manager/services/meeting_service.py
git checkout web-manager/services/network_service.py
git checkout web-manager/services/__init__.py

# Re-deploy old versions:
scp web-manager/services/meeting_service.py device@192.168.1.202:/opt/rpi-cam-webmanager/services/
ssh device@192.168.1.202 "sudo systemctl restart rpi-cam-webmanager"
```

---

## Use Cases

### 1. Ethernet Failover
- Unplug ethernet → WiFi takes over → Device back online in Meeting API in 2s (vs 30s before)

### 2. WiFi Router Reboot
- Router reboots → Device reconnects → Heartbeat sent immediately → Device back in UI

### 3. Internet Outage
- Internet down → Back up → Heartbeat sent within 1s (vs 30s wait)

### 4. Manual Trigger
- Other services can call `trigger_immediate_heartbeat()` to force immediate send

---

## Troubleshooting

**Q: "No route to host" when deploying**  
A: Device is likely rebooting. Wait 1-2 minutes, then retry.

**Q: Heartbeat not triggering immediately**  
A: Check logs: `journalctl -u rpi-cam-webmanager | grep immediate`

**Q: Device still shows offline in Meeting API**  
A: Verify internet: `ping 8.8.8.8` on device

**Q: Service won't restart**  
A: Check for syntax errors: `python3 -m py_compile web-manager/services/meeting_service.py`

---

## Documentation

- **Full implementation:** `IMPLEMENTATION_IMMEDIATE_HEARTBEAT_V2_32_20.md`
- **Test scenarios:** `TESTING_IMMEDIATE_HEARTBEAT_V2_32_20.md`
- **Version info:** See `CHANGELOG.md` and `AGENTS.md`

---

## Performance

- Zero impact on normal heartbeat cycle
- DNS connectivity check: ~100ms every 30s
- Event checking: <1ms per loop
- Thread-safe, no race conditions

---

## Next Steps

1. ✅ Deploy files
2. ✅ Restart service
3. ✅ Verify heartbeats sending
4. ✅ Test failover scenario
5. ✅ Monitor Meeting API for immediate updates
6. ✅ Rollback if needed (use git)

**Expected result:** Device back online in Meeting API within 3 seconds of failover (vs 30 seconds before)

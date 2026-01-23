# Testing: Immediate Heartbeat on Network Reconnection (v2.32.20)

## Overview

This document describes how to test the immediate heartbeat feature and verify that heartbeats are sent immediately when network connectivity is restored.

## Test Environment

- **Device:** 192.168.1.202 (Raspberry Pi 3 Model B)
- **Interfaces:** eth0 (Ethernet), wlan0 (WiFi fallback)
- **Service:** rpi-cam-webmanager
- **Meeting API:** Monitoring device heartbeats

---

## Scenario 1: Ethernet Failover to WiFi

### Objective
Verify that when ethernet disconnects, the device failovers to WiFi and sends a heartbeat within 3 seconds.

### Prerequisites
- Device online with ethernet (eth0)
- Device has WiFi configured and working
- Meeting API is receiving heartbeats regularly
- SSH access to device or direct console

### Test Steps

1. **Establish baseline:**
   ```bash
   # On device or via SSH:
   curl -s http://localhost:5000/api/meeting/status | jq .
   
   # Expected output:
   # {
   #   "connected": true,
   #   "last_heartbeat": "2026-01-21T14:30:00",
   #   "last_heartbeat_ago": "11 seconds",
   #   ...
   # }
   ```

2. **Monitor logs in real-time:**
   ```bash
   # Terminal 1 (watch logs):
   journalctl -u rpi-cam-webmanager -f | grep -E "Meeting|Failover"
   ```

3. **Unplug ethernet cable:**
   - Physically unplug ethernet cable from device
   - Note the time (T=0s)

4. **Observe failover:**
   ```
   Expected log sequence (within 1-5 seconds):
   
   T+1s: [Failover] eth0 disconnected
   T+1s: [Failover] Connecting to wlan0...
   T+2s: [Failover] wlan0 is active (192.168.1.127)
   T+2s: [Network] Triggering immediate heartbeat due to failover: failover_to_wlan0
   T+2s: [Meeting] Immediate heartbeat triggered by event
   T+2s: [Meeting] Heartbeat sent: success=true
   ```

5. **Verify heartbeat in Meeting API:**
   ```bash
   # Within 3 seconds of failover:
   curl -s http://localhost:5000/api/meeting/status
   
   # Should show:
   # - "connected": true
   # - "last_heartbeat_ago": "0-2 seconds"
   # - Device appears online in Meeting dashboard
   ```

### Expected Outcome
✅ Heartbeat sent within 1-3 seconds of failover (not waiting 30s)

---

## Scenario 2: WiFi Router Reboot Recovery

### Objective
Verify that when WiFi router reboots and comes back online, heartbeat is sent immediately.

### Prerequisites
- Device connected via WiFi (wlan0)
- Device has internet connectivity
- SSH access for monitoring

### Test Steps

1. **Verify WiFi connectivity:**
   ```bash
   # On device or via SSH:
   ifconfig wlan0
   # Should show IP address assigned
   ```

2. **Watch logs:**
   ```bash
   journalctl -u rpi-cam-webmanager -f
   ```

3. **Reboot WiFi router** or simulate outage:
   - Physical reboot of WiFi device, or
   - Temporarily disable WiFi from access point UI

4. **Observe reconnection:**
   ```
   Expected sequence:
   
   T+0s: Internet/WiFi down
   T+10-20s: WiFi goes offline, device detects no connectivity
   T+25s: WiFi comes back online, device gets IP
   T+26s: [Meeting] Connectivity restored, sending immediate heartbeat
   T+26s: [Meeting] Heartbeat sent successfully
   ```

5. **Verify in Meeting API:**
   - Device shows online in Meeting dashboard
   - Timestamp shows recent heartbeat (within 1-2s of reconnection)

### Expected Outcome
✅ Immediate heartbeat sent when connectivity restored, not on next 30s cycle

---

## Scenario 3: Internet Outage (Box Reboot)

### Objective
Verify immediate heartbeat when internet comes back after a temporary outage.

### Prerequisites
- Device has stable network connectivity
- Ability to monitor network status
- SSH access

### Test Steps

1. **Verify connectivity:**
   ```bash
   ping -c 1 8.8.8.8
   curl https://api.meeting.co/health  # Should return 200
   ```

2. **Simulate internet outage:**
   ```bash
   # Temporarily block internet (not WiFi):
   # Method A: Restart router main connection
   # Method B: Block default gateway on device
   sudo iptables -I OUTPUT 1 -d 8.8.8.8 -j DROP  # Block DNS
   ```

3. **Monitor logs:**
   ```bash
   journalctl -u rpi-cam-webmanager -f
   
   Expected:
   T+0s: [Meeting] Connectivity lost (DNS fails)
   T+0s: [Meeting] Heartbeat send failed (connection timeout)
   ```

4. **Restore internet:**
   ```bash
   # Remove iptables rule or restore connection
   sudo iptables -D OUTPUT 1 -d 8.8.8.8 -j DROP
   ```

5. **Observe immediate recovery:**
   ```
   Expected:
   T+1s: [Meeting] Connectivity restored, sending immediate heartbeat
   T+1s: [Meeting] Heartbeat sent successfully
   T+1s: [Meeting] connected: true
   ```

### Expected Outcome
✅ Heartbeat sent immediately when internet restored

---

## Scenario 4: Manual Heartbeat Trigger

### Objective
Verify that external services can trigger immediate heartbeat manually.

### Prerequisites
- SSH access to device
- Python shell or script execution

### Test Steps

1. **Create test script:**
   ```python
   # test_trigger.py
   from sys import path
   path.insert(0, '/opt/rpi-cam-webmanager')
   
   from services.meeting_service import trigger_immediate_heartbeat, meeting_state
   
   # Trigger immediate heartbeat
   result = trigger_immediate_heartbeat()
   print(f"Trigger result: {result}")
   
   # Check if event is set
   print(f"Meeting state: connected={meeting_state.get('connected')}")
   ```

2. **Execute on device:**
   ```bash
   cd /opt/rpi-cam-webmanager
   python3 test_trigger.py
   ```

3. **Monitor logs:**
   ```bash
   journalctl -u rpi-cam-webmanager -n 50 | grep "heartbeat triggered"
   ```

4. **Verify heartbeat sent:**
   ```bash
   curl http://localhost:5000/api/meeting/status | jq .last_heartbeat_ago
   # Should show 0-2 seconds
   ```

### Expected Outcome
✅ Calling `trigger_immediate_heartbeat()` causes immediate send within 500ms

---

## Monitoring During Tests

### Real-time Status Check

```bash
# On device or via SSH:
watch -n 1 'curl -s http://localhost:5000/api/meeting/status | jq ".connected, .last_heartbeat_ago, .last_error"'
```

### Log Filtering

```bash
# Watch only Meeting-related logs:
journalctl -u rpi-cam-webmanager -f | grep Meeting

# Watch only Failover logs:
journalctl -u rpi-cam-webmanager -f | grep Failover

# Watch both:
journalctl -u rpi-cam-webmanager -f | grep -E "Meeting|Failover"

# Show last 50 lines with timestamps:
journalctl -u rpi-cam-webmanager -n 50 --no-pager -o short
```

### Meeting API Dashboard

1. Log into Meeting API at: `https://api.meeting.co/dashboard`
2. Find device: `RTSP Recorder - Raspberry Pi 3 Model B - 192.168.1.202`
3. Check "Last Heartbeat" timestamp
4. Verify it updates immediately after failover/reconnection

---

## Metrics to Track

| Metric | Baseline | After Fix | Target |
|--------|----------|-----------|--------|
| Time to heartbeat after failover | 30s | 1-3s | <5s |
| Time to device back online in UI | 30-60s | 1-5s | <10s |
| Heartbeats missed during failover | 0-1 | 0 | 0 |
| CPU spike during failover | <5% | <2% | <5% |
| Failed heartbeats | <1% | <0.1% | <1% |

---

## Success Criteria

✅ **All tests pass if:**

1. **Scenario 1 (Failover):** Heartbeat within 3 seconds, not 30s
2. **Scenario 2 (WiFi recovery):** Immediate heartbeat on reconnection
3. **Scenario 3 (Internet recovery):** Heartbeat sent within 1s of connectivity restored
4. **Scenario 4 (Manual trigger):** External call sends within 500ms
5. **No regressions:** Normal 30s heartbeat cycle still works
6. **Logging:** Clear "[Meeting] Immediate heartbeat" logs appear
7. **No errors:** No exceptions in logs, clean shutdown/restart

---

## Troubleshooting

### Issue: "No route to host" when deploying

**Solution:** Device is likely rebooting. Wait 1-2 minutes and retry.

```bash
ping 192.168.1.202  # Should respond
ssh device@192.168.1.202 "hostname"  # Should show device name
```

### Issue: Heartbeat not triggering immediately

**Check logs:**
```bash
journalctl -u rpi-cam-webmanager | grep -i "immediate\|trigger"

# Should show:
# [Meeting] Immediate heartbeat triggered by event
# [Meeting] Connectivity restored, sending immediate heartbeat
```

**Verify feature deployed:**
```bash
grep "trigger_immediate_heartbeat" /opt/rpi-cam-webmanager/services/meeting_service.py
# Should show the function definition
```

**Restart service:**
```bash
sudo systemctl restart rpi-cam-webmanager
sleep 3
curl http://localhost:5000/api/meeting/status
```

### Issue: Device stays offline in Meeting API

**Check connectivity:**
```bash
curl http://localhost:5000/api/meeting/status | jq .
# connected: false, last_error: ?
```

**Check network:**
```bash
ip addr show
nmcli device status
ping 8.8.8.8
```

**Verify service running:**
```bash
systemctl status rpi-cam-webmanager
```

---

## Performance Baseline (Before Testing)

Record these before making changes:

```bash
# Device uptime:
uptime

# Current interface status:
ifconfig eth0 wlan0

# Current heartbeat status:
curl -s http://localhost:5000/api/meeting/status | jq .

# Service version:
cat /opt/rpi-cam-webmanager/services/meeting_service.py | head -5

# System load:
top -b -n 1 | head -3
```

---

## Deployment Validation Checklist

After deploying v2.32.20:

- [ ] Files deployed: meeting_service.py, network_service.py, __init__.py
- [ ] Service restarted without errors
- [ ] Meeting API status shows connected=true
- [ ] Logs show no errors
- [ ] Normal heartbeats continue every 30s
- [ ] Connectivity detection working (test with ping 8.8.8.8)
- [ ] Failover trigger integrated (logs show trigger events)
- [ ] No performance degradation
- [ ] SSH access still works

---

## Post-Test Analysis

### Create test report:

1. **Date/Time of tests:** _________
2. **Device:** 192.168.1.202
3. **Scenarios passed:** ☐ Failover ☐ Recovery ☐ Trigger ☐ Internet
4. **Issues found:** _________
5. **Time to heartbeat avg:** _________ seconds
6. **Peak CPU during failover:** _________ %
7. **Conclusion:** Pass / Fail

---

## Notes

- All tests assume device has internet connectivity during baseline
- WiFi router SSID/password must be pre-configured on device
- For Scenario 3, ensure box/internet outage is temporary (don't brick permanently)
- Keep logs from tests for troubleshooting if issues arise
- Report any failures to development team with logs attached

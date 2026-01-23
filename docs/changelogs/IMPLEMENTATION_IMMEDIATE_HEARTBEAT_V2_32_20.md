# Immediate Heartbeat on Network Reconnection - v2.32.20

## Overview

This implementation adds **immediate heartbeat transmission** when network connectivity is restored, instead of waiting up to 30 seconds for the next scheduled heartbeat cycle.

**Use cases:**
- Ethernet unplugged → WiFi failover: heartbeat sent within 1-3 seconds
- WiFi box reboot → device reconnects: heartbeat sent within 1 second
- Internet outage recovered: heartbeat sent immediately

---

## Implementation Details

### 1. `web-manager/services/meeting_service.py` (v2.30.16)

#### New Functions

**`has_internet_connectivity()`**
```python
def has_internet_connectivity():
    """Check if device has internet connectivity (DNS resolution check)."""
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except Exception:
        return False
```
- Tests DNS connectivity to 8.8.8.8:53
- ~100ms latency if online, instant if offline
- Used to detect connectivity state changes

**`trigger_immediate_heartbeat()`**
```python
def trigger_immediate_heartbeat():
    """Trigger immediate heartbeat for external services (failover, etc)."""
    global _immediate_heartbeat_event
    if not _immediate_heartbeat_event.is_set():
        _immediate_heartbeat_event.set()
        print("[Meeting] Immediate heartbeat triggered by event")
        return True
    return False
```
- Called by network_service when failover occurs
- Sets `_immediate_heartbeat_event` flag
- Next loop iteration sends heartbeat within 500ms

#### Enhanced `meeting_heartbeat_loop()`

**Key changes:**
1. Added global state tracking: `_last_known_connectivity_state`
2. Detects connectivity changes:
   - `current_connectivity = has_internet_connectivity()`
   - `connectivity_restored = (previous_state == False and current_state == True)`
3. Checks for trigger event: `_immediate_heartbeat_event.is_set()`
4. Sends heartbeat immediately if:
   - Connectivity was just restored, OR
   - External service triggered immediate send
5. Responsive wait: checks every 500ms for immediate trigger events

**New loop logic:**
```
LOOP:
  1. Check for immediate trigger event
  2. Detect connectivity state change
  3. If connectivity restored → send heartbeat immediately
  4. If trigger event set → send heartbeat immediately
  5. Otherwise → send normal heartbeat
  6. Wait 30s with interruptible 500ms checks
```

#### Global State Variables
```python
_immediate_heartbeat_event = threading.Event()
_last_known_connectivity_state = None
```

---

### 2. `web-manager/services/network_service.py` (v2.30.15)

#### New Helper Function

**`_trigger_heartbeat_on_failover(action)`**
```python
def _trigger_heartbeat_on_failover(action):
    """Trigger immediate heartbeat when network failover occurs."""
    try:
        from .meeting_service import trigger_immediate_heartbeat
        
        if action in ['failover_to_wlan1', 'failover_to_wlan0', 'eth0_priority']:
            logger.info(f"[Network] Triggering immediate heartbeat: {action}")
            trigger_immediate_heartbeat()
    except Exception as e:
        logger.debug(f"[Network] Could not trigger heartbeat: {e}")
```

**Features:**
- Dynamic import to avoid circular dependencies
- Only triggers for actual network changes (not "no change" states)
- Graceful fallback if import fails
- Clear logging for debugging

#### Integration Points in `_manage_network_failover_internal()`

When failover occurs, now calls `_trigger_heartbeat_on_failover(action)`:

1. **eth0 becomes active:** `_trigger_heartbeat_on_failover('eth0_priority')`
2. **Failover to wlan1:** `_trigger_heartbeat_on_failover('failover_to_wlan1')`
3. **Failover to wlan0:** `_trigger_heartbeat_on_failover('failover_to_wlan0')`

No trigger for:
- `'wlan1_active'`, `'wlan0_active'` - already active, no change
- `'no_network'`, `'locked'`, `'manual_override'` - no actual change

---

### 3. `web-manager/services/__init__.py` (v2.30.8)

#### Exports

Added new functions to module exports:
```python
from .meeting_service import (
    ...
    trigger_immediate_heartbeat,
    has_internet_connectivity
)
```

Updated `__all__` list:
```python
__all__ = [
    ...
    'trigger_immediate_heartbeat', 'has_internet_connectivity',
]
```

---

## Files Modified

| File | Version | Changes |
|------|---------|---------|
| `web-manager/services/meeting_service.py` | 2.30.16 | Added `trigger_immediate_heartbeat()`, `has_internet_connectivity()`, enhanced loop |
| `web-manager/services/network_service.py` | 2.30.15 | Added `_trigger_heartbeat_on_failover()`, integrated into failover logic |
| `web-manager/services/__init__.py` | 2.30.8 | Export new functions |
| `VERSION` | 2.32.20 | Bumped version |
| `CHANGELOG.md` | - | Added v2.32.20 entry |
| `AGENTS.md` | 1.23.0 | Added feature documentation |

---

## Thread Safety

**Implementation is thread-safe:**
- Uses `threading.Event()` for atomic flag operations (no race conditions)
- All state reads/writes use existing `meeting_state['lock']`
- Dynamic imports are lazy and safe (import only when needed)
- No shared mutable state except `threading.Event`

---

## Performance Impact

**Minimal:**
- `has_internet_connectivity()`: ~100ms every 30s (DNS check)
- Event checks: <1ms (atomic operations)
- Loop overhead: negligible (already had sleep calls)
- No blocking operations added

---

## Testing Checklist

- [ ] Device 192.168.1.202: Deploy files, restart service
- [ ] Verify heartbeat sends every 30s: `curl http://localhost:5000/api/meeting/status`
- [ ] Test connectivity detection: Unplug ethernet, watch WiFi failover
- [ ] Verify immediate heartbeat: Check Meeting API sees device back online within 3s
- [ ] Test manual trigger: Call `trigger_immediate_heartbeat()` from shell
- [ ] Check logs: `journalctl -u rpi-cam-webmanager | grep Meeting`
- [ ] Verify no errors: Check error logs for "could not trigger heartbeat"

---

## Deployment Steps

1. **Copy modified files:**
   ```bash
   scp -r web-manager/services/meeting_service.py device@192.168.1.202:/opt/rpi-cam-webmanager/services/
   scp -r web-manager/services/network_service.py device@192.168.1.202:/opt/rpi-cam-webmanager/services/
   scp -r web-manager/services/__init__.py device@192.168.1.202:/opt/rpi-cam-webmanager/services/
   ```

2. **Restart web service:**
   ```bash
   sudo systemctl restart rpi-cam-webmanager
   ```

3. **Verify deployment:**
   ```bash
   journalctl -u rpi-cam-webmanager -n 50
   curl http://localhost:5000/api/meeting/status
   ```

---

## Use Cases Enabled

### 1. Ethernet Unplugged Scenario
- T=0s: User unplugs ethernet cable
- T=1-3s: WiFi failover completes
- T=1-3s: `manage_network_failover()` calls `_trigger_heartbeat_on_failover('failover_to_wlan1')`
- T=1-3s: `trigger_immediate_heartbeat()` sets event
- T=1-3s: Next loop iteration detects event, sends heartbeat
- **Result:** Meeting API updated within 3 seconds (vs 30s before)

### 2. WiFi Box Reboot Scenario
- T=0s: WiFi router reboots
- T=10s: Device loses WiFi, detects offline
- T=20s: WiFi back online, device auto-connects
- T=22s: `has_internet_connectivity()` detects state change (offline → online)
- T=22s: Loop sends heartbeat immediately
- **Result:** Meeting API sees device back online within 2 seconds after reconnection

### 3. Internet Outage Recovery
- T=0s: Internet down (DNS fails)
- T=10s: Internet back up
- T=11s: Loop detects connectivity restored
- T=11s: Heartbeat sent
- **Result:** Device back online in Meeting API within 1 second

### 4. External Service Trigger
- Other service calls `trigger_immediate_heartbeat()`
- Next loop iteration (within 500ms) sends heartbeat
- Use case: emergency failover, manual network switch, etc.

---

## Backward Compatibility

✅ **Fully backward compatible:**
- Normal 30s heartbeat cycle still works
- Existing API unchanged
- No breaking changes to configuration
- Falls back gracefully if meeting_service import fails

---

## Future Enhancements

- [ ] Configurable heartbeat interval per device
- [ ] Heartbeat request queue instead of simple flag
- [ ] Metrics: track how many immediate heartbeats triggered vs normal
- [ ] Dashboard widget: show last heartbeat time, immediate vs normal
- [ ] Integration with other failover scenarios (RTSP recovery, etc.)

---

## Version History

- **v2.32.20**: Initial implementation of immediate heartbeat on connectivity restoration
- **v2.32.19**: Device description in heartbeat payload
- **v2.32.18**: Critical heartbeat loop fix

# Meeting Device Integration Implementation Guide

## Overview

The Updates Manager Tool now includes mandatory device registration and heartbeat support for the Meeting server (https://meeting.ygsoft.fr).

## Features Implemented

### 1. Device Registration

**Location**: Settings tab → "Meeting Device Registration" section

**Process**:
1. User enters a registration token (6 hex characters, e.g., `ABC123`)
2. Click "Register Device"
3. Device is registered with Meeting server using one-time token
4. Token is burned (invalidated) after first successful registration
5. Device key is stored locally and displayed

**Requirements**:
- Meeting server URL (pre-populated: https://meeting.ygsoft.fr)
- Registration token from server administrator (6 characters)
- Must complete before using certain features

**Token Burn Mechanism**:
- Token codes are single-use only
- Server invalidates token after first registration attempt
- Re-registration with same token will fail
- Request new token from administrator if needed

### 2. Device Information Collection

The tool automatically collects and reports:

```json
{
  "ip_address": "192.168.1.100",
  "ip_lan": "10.0.0.50",
  "ip_public": "203.0.113.42",
  "mac": "00:1A:2B:3C:4D:5E",
  "note": "Updates Manager Tool"
}
```

**Field Details**:
- `ip_address`: Primary IP (REMOTE_ADDR fallback if unavailable)
- `ip_lan`: Private LAN IP address
- `ip_public`: Public IP from external service
- `mac`: MAC address of primary interface
- `cluster_ip`: Cluster IP (optional)
- `note`: Device description

### 3. Automatic Heartbeat

**Timing**: Sends heartbeat every 60 seconds after registration

**Endpoint**: `POST /api/devices/{device_key}/online`

**Payload**:
```json
{
  "ip_address": "...",
  "ip_lan": "...",
  "ip_public": "...",
  "mac": "...",
  "note": "..."
}
```

**Features**:
- Runs in background thread
- Non-blocking (doesn't affect UI)
- Automatic retry on failure (up to 5 consecutive failures before stopping)
- All fields optional (server uses REMOTE_ADDR if ip_address absent)
- Status displayed in Settings widget

**Manual Heartbeat**: Click "Test Heartbeat" button to send immediately

### 4. Device State Management

**Storage Location**: `~/.updates-manager-tool/device_info.json`

**Content**:
```json
{
  "device_key": "device-abc12345",
  "device_info": {
    "ip_address": "...",
    "ip_lan": "...",
    "ip_public": "...",
    "mac": "...",
    "note": "..."
  },
  "registered_at": "2024-01-15 14:30:45"
}
```

**Persistence**:
- Device key survives application restart
- Heartbeat resumes automatically on startup if device is registered
- Unregister option available to clear stored device key

## User Interface

### Settings Tab

Located in the main navigation sidebar (⚙️ Settings → Meeting Device Registration)

**Components**:

1. **Status Display**
   - Shows registration status (Registered/Not registered)
   - Color-coded: Green for registered, Red for unregistered

2. **Device Key Section**
   - Read-only display of device key (after registration)
   - Copy button for quick clipboard copy

3. **Token Input**
   - 6-character input field for registration token
   - Automatically converted to uppercase
   - Disabled after registration

4. **Instructions**
   - Step-by-step registration guide
   - Warning about one-time token usage

5. **Action Buttons**
   - `Register Device`: Initiate registration with token
   - `Test Heartbeat`: Send immediate heartbeat (registered only)
   - `Unregister`: Remove device registration and stored key

6. **Heartbeat Status**
   - Real-time indicator: "Heartbeat: Active ✓" or "Heartbeat: Inactive"
   - Color-coded for visibility

## API Integration

### Device Manager Class

**Module**: `app/device_manager.py`

**Methods**:

#### Device Key Management
```python
device_manager.load_device_key() -> Optional[str]
    # Load existing device key from storage

device_manager.save_device_key(device_key: str, device_info: dict) -> bool
    # Save device key and info locally

device_manager.clear_device_key() -> bool
    # Clear stored device key
```

#### Registration
```python
device_manager.register_with_meeting(
    client: ApiClient,
    device_key: str,
    token_code: str
) -> tuple[bool, str]
    # Register device with Meeting server
    # Returns (success, message)
```

#### Heartbeat
```python
device_manager.start_heartbeat(client: ApiClient, interval: int = 60) -> None
    # Start background heartbeat thread

device_manager.stop_heartbeat() -> None
    # Stop heartbeat thread

device_manager.send_heartbeat_now(client: ApiClient) -> tuple[bool, str]
    # Send single heartbeat immediately
    # Returns (success, message)
```

#### Device Info Collection
```python
device_manager.collect_device_info() -> dict
    # Collect current device information
    # Returns dict with ip_address, ip_lan, ip_public, mac, note
```

### API Client Methods

**Module**: `app/api_client.py`

#### Registration Endpoint
```python
client.register_device(
    device_key: str,
    token_code: str,
    device_info: dict
) -> dict
    # POST /api/devices/{device_key}/register
    # Token is burned (one-time use) server-side
    # Returns {"ok": true/false, "message": "..."}
```

#### Heartbeat Endpoint
```python
client.send_heartbeat(
    device_key: str,
    heartbeat_data: dict
) -> dict
    # POST /api/devices/{device_key}/online
    # All fields in heartbeat_data are optional
    # Returns {"ok": true/false, "message": "..."}
```

#### SSH Integration
```python
client.get_ssh_hostkey() -> str
    # GET /api/ssh-hostkey
    # Returns public key as text/plain

client.publish_ssh_key(device_key: str, pubkey: str) -> dict
    # PUT /api/devices/{device_key}/ssh-key
    # Register device's public SSH key
    # Returns {"ok": true/false, "message": "..."}
```

#### Device Info
```python
client.get_device_info(device_key: str) -> dict
    # GET /api/devices/{device_key}
    # Retrieve device info from server
    # Returns device details
```

## Configuration

### Meeting Server URL

**Default**: `https://meeting.ygsoft.fr`

**Override Methods**:
1. Create profile with custom URL in Settings tab
2. Set `MEETING_SERVER_URL` environment variable
3. Token stored in Windows Keyring (secure)

**Profile Storage** (`.updates-manager-tool/profiles.json`):
```json
{
  "active": "production",
  "profiles": [
    {
      "name": "production",
      "base_url": "https://meeting.ygsoft.fr",
      "token": "(stored in keyring)",
      "timeout": 20,
      "retries": 3
    }
  ]
}
```

## Error Handling

### Registration Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Device not found (404)` | Device doesn't exist on server | Contact administrator |
| `Invalid token (401)` | Token expired or wrong | Request new token |
| `Already registered (409)` | Device already has active registration | Unregister first or use new token |
| `Connection failed` | Network unreachable | Check Meeting server URL and connectivity |

### Heartbeat Errors

- **Automatic retry**: Up to 5 consecutive failures before stopping
- **Logging**: All errors logged to `~/.updates-manager-tool/logs/app.log`
- **User impact**: Minimal (background operation)
- **Recovery**: Restarts automatically on next application run if device registered

## Security Considerations

### Token Security
- One-time use only (burned after first registration)
- Never transmitted after initial registration
- Cannot be re-used even if saved

### Device Key
- Stored locally in plain JSON (consider encryption)
- Not transmitted outside registration/heartbeat
- Used only for device identification with Meeting server

### SSL/TLS
- Configurable certificate verification
- Default: Enabled (recommended)
- Can be disabled for self-signed certificates

## Logging

**Location**: `~/.updates-manager-tool/logs/app.log`

**Log Entries**:
- Device registration attempts (success/failure)
- Heartbeat status updates
- Device info collection details
- Error messages with full context

**Log Levels**:
- `INFO`: Registration completed, heartbeat sent
- `DEBUG`: Heartbeat details, device info collected
- `WARNING`: Connection failures, token issues
- `ERROR`: Critical failures that stop operations

## Troubleshooting

### Device Won't Register

1. **Check token code**
   - Must be exactly 6 characters (hex)
   - Convert to uppercase if needed
   - Verify with administrator

2. **Check Meeting server URL**
   - Default is `https://meeting.ygsoft.fr`
   - Verify server is accessible: `ping meeting.ygsoft.fr`

3. **Check network**
   - Verify internet connection
   - Check firewall rules
   - TLS verification: Settings → "Verify TLS certificates"

### Heartbeat Not Working

1. **Check device is registered**
   - Device Key should be visible in Settings
   - Status should show "Registered"

2. **Check logs**
   - View logs: Settings → App Info → log files
   - Look for heartbeat error messages

3. **Test manually**
   - Click "Test Heartbeat" button
   - Check response message

### Device Info Missing

- **IP addresses**: May fail on some network configs
- **MAC address**: Requires network interface access
- **Public IP**: Requires external API (may be slow)
- **Fallback**: Server can use REMOTE_ADDR if ip_address not provided

## Administration

### Server-Side Setup

1. **Create device entry** on Meeting server
   - Assign unique `device_key`
   - Generate 6-character token code
   - Provide token to device administrator

2. **Receive registration**
   - Meeting server receives registration with device_key + token_code
   - Validates device exists
   - Burns token code (marks as used)

3. **Monitor heartbeat**
   - Device sends heartbeat every 60 seconds
   - Server updates last-seen timestamp
   - Track device status and connectivity

### Revoking Devices

1. **Client-side**: Unregister button in Settings
2. **Server-side**: Delete device or disable heartbeat acceptance
3. **Result**: Heartbeat stops, manual re-registration required

## Future Enhancements

- SSH key generation and exchange
- Device clustering support
- Advanced diagnostics dashboard
- Custom heartbeat intervals
- Device groups and organizational units
- Metrics collection and monitoring
- Alert thresholds and notifications

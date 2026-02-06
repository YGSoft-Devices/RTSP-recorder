# -*- coding: utf-8 -*-
"""
Meeting Service - Meeting API integration and heartbeat
Version: 2.30.18
"""

import os
import re
import json
import time
import threading
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

from flask import has_request_context, request

from .platform_service import run_command
from .config_service import set_hostname, load_config
from .i18n_service import t as i18n_t, resolve_request_lang
from config import MEETING_CONFIG_FILE, CONFIG_FILE

# ============================================================================
# GLOBAL STATE
# ============================================================================

meeting_state = {
    'enabled': False,
    'connected': False,
    'last_heartbeat': None,
    'last_error': None,
    'device_info': None,
    'api_url': None,
    'device_key': None,
    'token_code': None,
    'heartbeat_interval': 30,
    'thread_running': False,
    'lock': threading.Lock()
}

# Heartbeat thread reference
_heartbeat_thread = None
_heartbeat_stop_event = threading.Event()

# Immediate heartbeat trigger (for failover, reconnection events)
_immediate_heartbeat_event = threading.Event()
_last_known_connectivity_state = None  # Track connectivity changes

# ---------------------------------------------------------------------------
# I18n helpers
# ---------------------------------------------------------------------------

def _resolve_lang(config=None):
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}
    req = request if has_request_context() else None
    return resolve_request_lang(req, config)


def _t(key, config=None, **params):
    return i18n_t(key, lang=_resolve_lang(config), params=params)

# ============================================================================
# CONFIGURATION
# ============================================================================

def load_meeting_config():
    """
    Load Meeting API configuration from file.
    First tries meeting.json, then falls back to config.env.
    
    IMPORTANT (v2.30.13): Auto-generates device_key if missing.
    This ensures heartbeat always runs, even on devices without provisioning.
    
    Returns:
        dict: Meeting configuration
    """
    default_config = {
        'enabled': True,  # CHANGED: Default to True (v2.30.13) - heartbeat should always try
        'api_url': 'https://api.meeting.co',  # Default Meeting API URL
        'device_key': '',  # Will be auto-generated if empty
        'token_code': '',
        'heartbeat_interval': 30,
        'auto_connect': True,
        'provisioned': False
    }
    
    # Try JSON config first
    if os.path.exists(MEETING_CONFIG_FILE):
        try:
            with open(MEETING_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                default_config.update(config)
        except Exception as e:
            print(f"Error loading meeting config from JSON: {e}")
    else:
        # Fall back to config.env if meeting.json doesn't exist
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            
                            if key == 'MEETING_ENABLED':
                                default_config['enabled'] = value.lower() in ('yes', 'true', '1')
                            elif key == 'MEETING_API_URL':
                                if value:  # Only override if not empty
                                    default_config['api_url'] = value
                            elif key == 'MEETING_DEVICE_KEY':
                                if value and value != '********':
                                    default_config['device_key'] = value
                            elif key == 'MEETING_TOKEN_CODE':
                                if value and value != '********':
                                    default_config['token_code'] = value
                            elif key == 'MEETING_HEARTBEAT_INTERVAL':
                                try:
                                    default_config['heartbeat_interval'] = int(value)
                                except:
                                    pass
                            elif key == 'MEETING_PROVISIONED':
                                default_config['provisioned'] = value.lower() in ('yes', 'true', '1')
            except Exception as e:
                print(f"Error loading meeting config from config.env: {e}")
    
    # Auto-generate device_key if missing (v2.30.13 - ensures heartbeat always works)
    if not default_config.get('device_key') or default_config['device_key'].strip() == '':
        # Generate a unique device_key from hostname + mac address
        import uuid
        import socket
        try:
            hostname = socket.gethostname()
            mac = uuid.getnode()  # Gets MAC address
            default_config['device_key'] = f"{hostname}-{mac:012x}".lower()
            print(f"[Meeting] Auto-generated device_key: {default_config['device_key']}")
        except Exception as e:
            # Fallback to UUID if hostname fails
            default_config['device_key'] = str(uuid.uuid4()).replace('-', '')[:16]
            print(f"[Meeting] Generated UUID device_key: {default_config['device_key']}")
    
    return default_config

def save_meeting_config(config):
    """
    Save Meeting API configuration to file.
    
    Args:
        config: Configuration dict
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        os.makedirs(os.path.dirname(MEETING_CONFIG_FILE), exist_ok=True)
        
        # Save all necessary config including provisioned status
        save_config = {
            'enabled': config.get('enabled', False),
            'api_url': config.get('api_url', ''),
            'device_key': config.get('device_key', ''),
            'heartbeat_interval': config.get('heartbeat_interval', 30),
            'auto_connect': config.get('auto_connect', True),
            'provisioned': config.get('provisioned', False)
        }
        
        # Token should be stored here (meeting.json has restricted permissions)
        if config.get('token_code'):
            save_config['token_code'] = config['token_code']
        
        with open(MEETING_CONFIG_FILE, 'w') as f:
            json.dump(save_config, f, indent=2)
        
        return {'success': True, 'message': _t('ui.meeting.config_saved')}
    
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_meeting_status():
    """
    Get current Meeting API connection status.
    For provisioned devices, queries the Meeting API directly to get accurate status
    even when multiple Gunicorn workers don't share state.
    
    Returns:
        dict: Status information including provisioning state
    """
    config = load_meeting_config()
    
    enabled = config.get('enabled', False)
    provisioned = config.get('provisioned', False)
    api_url = config.get('api_url', '')
    device_key = config.get('device_key', '')
    
    # Start with local state
    with meeting_state['lock']:
        last_hb = meeting_state['last_heartbeat']
        connected = meeting_state['connected']
        last_error = meeting_state['last_error']
        device_info = meeting_state['device_info']
        thread_running = meeting_state['thread_running']
    
    last_hb_ago = None
    
    # For provisioned devices, get real status from Meeting API
    # This ensures accurate status even with multiple Gunicorn workers
    if provisioned and enabled and api_url and device_key:
        try:
            avail_result = get_device_availability()
            if avail_result.get('success') and avail_result.get('data'):
                avail_data = avail_result['data']
                avail_status = avail_data.get('status', '')
                connected = avail_status.lower() == 'available'
                
                # Parse last_heartbeat from Meeting API (returned in UTC)
                last_hb_str = avail_data.get('last_heartbeat')
                if last_hb_str:
                    try:
                        # Meeting API returns UTC time
                        dt_utc = datetime.strptime(last_hb_str, '%Y-%m-%d %H:%M:%S')
                        last_hb = dt_utc.isoformat()
                        # Calculate ago using UTC
                        import time as time_module
                        now_utc = datetime.utcnow()
                        last_hb_ago = int((now_utc - dt_utc).total_seconds())
                    except:
                        pass
        except:
            pass  # Keep local state if API call fails
    elif last_hb:
        # Calculate from local state
        try:
            if isinstance(last_hb, str):
                dt = datetime.fromisoformat(last_hb.replace('Z', '+00:00'))
                last_hb_ago = int((datetime.now() - dt.replace(tzinfo=None)).total_seconds())
            elif isinstance(last_hb, (int, float)):
                last_hb_ago = int(time.time() - last_hb)
        except:
            pass
    
    return {
        'enabled': enabled,
        'connected': connected,
        'last_heartbeat': last_hb,
        'last_heartbeat_ago': last_hb_ago,
        'last_error': last_error,
        'device_info': device_info,
        'provisioned': provisioned,
        'configured': bool(api_url and device_key),
        'device_key': device_key[:4] + '****' if device_key else '',
        'device_key_full': device_key,
        'api_url': api_url,
        'heartbeat_interval': config.get('heartbeat_interval', 30),
        'heartbeat_thread_running': thread_running
    }

# ============================================================================
# API COMMUNICATION
# ============================================================================

def _build_api_url(base_url, endpoint):
    """
    Build the full API URL, handling the /api prefix correctly.
    
    If base_url ends with /api and endpoint starts with /api, 
    we remove the duplicate /api from the endpoint.
    
    Args:
        base_url: Base URL (e.g., 'https://meeting.ygsoft.fr/api')
        endpoint: API endpoint (e.g., '/api/devices/xxx/online' or '/devices/xxx/online')
    
    Returns:
        str: Full URL without duplicate /api
    """
    base_url = base_url.rstrip('/')
    
    # If base_url ends with /api and endpoint starts with /api, remove duplicate
    if base_url.endswith('/api') and endpoint.startswith('/api/'):
        endpoint = endpoint[4:]  # Remove leading '/api'
    
    return base_url + endpoint

def meeting_api_request(endpoint, method='GET', data=None, timeout=10):
    """
    Make a request to the Meeting API.
    
    Args:
        endpoint: API endpoint (e.g., '/api/devices/xxx/online')
        method: HTTP method
        data: Request data (dict for POST/PUT)
        timeout: Request timeout
    
    Returns:
        dict: {success: bool, data: any, error: str}
    """
    config = load_meeting_config()
    
    if not config.get('api_url'):
        return {'success': False, 'error': 'API URL not configured'}
    
    url = _build_api_url(config['api_url'], endpoint)
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    if config.get('token_code'):
        headers['X-Token-Code'] = config['token_code']
    
    try:
        req_data = json.dumps(data).encode('utf-8') if data else None
        
        request = urllib.request.Request(
            url,
            data=req_data,
            headers=headers,
            method=method
        )
        
        # Create SSL context that doesn't verify (for self-signed certs)
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            response_data = response.read().decode('utf-8')
            
            if response_data:
                return {
                    'success': True,
                    'data': json.loads(response_data),
                    'status_code': response.status
                }
            else:
                return {
                    'success': True,
                    'data': None,
                    'status_code': response.status
                }
    
    except urllib.error.HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP {e.code}: {e.reason}',
            'status_code': e.code
        }
    
    except urllib.error.URLError as e:
        return {
            'success': False,
            'error': f'Connection error: {e.reason}'
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

# ============================================================================
# HEARTBEAT
# ============================================================================

def send_heartbeat():
    """
    Send a heartbeat to the Meeting API.
    
    Payload structure (per Meeting API v3.4.33):
    {
        "ip_address": "192.168.1.202",           # Primary interface IP
        "timestamp": "2026-01-21T02:48:24",      # ISO8601 timestamp
        "note": "RTSP Recorder - Raspberry Pi 3 Model B Rev 1.2",  # Device description
        "services": { "ssh": 1, ... },           # Active services
        "uptime": "2h 3m",                       # System uptime
        "cpu_load": 0.45,                        # 1-minute load average
        "memory_percent": 35.2,                  # Memory usage percent
        "disk_percent": 42,                      # Disk usage percent
        "temperature": 47.2                      # CPU temperature (Pi only)
    }
    
    Returns:
        dict: {success: bool, message: str}
    """
    global meeting_state
    
    try:
        config = load_meeting_config()
        
        if not config.get('enabled'):
            return {'success': False, 'message': _t('ui.meeting.api_not_enabled')}
        
        if not config.get('device_key'):
            return {'success': False, 'message': _t('ui.meeting.device_key_missing')}
        
        # Get system info for heartbeat payload with error handling
        try:
            from .config_service import get_system_info, get_device_description
            from .network_service import get_preferred_ip
            
            sys_info = get_system_info()
            local_ip = get_preferred_ip()
            device_description = get_device_description()
        except Exception as e:
            # Fallback: send minimal heartbeat if system info collection fails
            import sys
            print(f"[Meeting] Warning: Failed to collect system info: {e}", file=sys.stderr)
            sys_info = {'uptime': '', 'cpu': {'load_1m': 0}, 'memory': {'percent': 0}, 'disk': {'percent': 0}, 'network': {}}
            local_ip = '127.0.0.1'
            device_description = 'RTSP Recorder'
        
        # Build heartbeat data per Meeting API v3.4.33 spec
        # See: https://meeting.ygsoft.fr/api/devices/{device_key}/online (POST)
        heartbeat_data = {
            'timestamp': datetime.now().isoformat(),
            'ip_address': local_ip,  # Primary IP for Meeting to store
            'note': device_description,  # Device description: "Project - Platform - IP"
            'uptime': sys_info.get('uptime', ''),
            'cpu_load': sys_info.get('cpu', {}).get('load_1m', 0),
            'memory_percent': sys_info.get('memory', {}).get('percent', 0),
            'disk_percent': sys_info.get('disk', {}).get('percent', 0),
            'temperature': sys_info.get('temperature'),
            'ip_addresses': sys_info.get('network', {})
        }
        
        # Send heartbeat
        endpoint = f"/api/devices/{config['device_key']}/online"
        result = meeting_api_request(endpoint, method='POST', data=heartbeat_data)
        
        with meeting_state['lock']:
            if result['success']:
                meeting_state['connected'] = True
                meeting_state['last_heartbeat'] = datetime.now().isoformat()
                meeting_state['last_error'] = None
                
                if result.get('data'):
                    meeting_state['device_info'] = result['data']
            else:
                meeting_state['connected'] = False
                meeting_state['last_error'] = result.get('error', 'Unknown error')
        
        return result
    
    except Exception as e:
        # Critical error handling - ensure thread survives
        import sys
        error_msg = f"Heartbeat failed: {str(e)}"
        print(f"[Meeting] ERROR: {error_msg}", file=sys.stderr)
        
        with meeting_state['lock']:
            meeting_state['connected'] = False
            meeting_state['last_error'] = error_msg
        
        return {'success': False, 'error': error_msg}

def meeting_heartbeat_loop(stop_event=None):
    """
    Background heartbeat loop with immediate reconnection support.
    
    Features:
    - Sends heartbeat every 30 seconds (configurable)
    - Detects connectivity changes and sends immediately when connection returns
    - Responds to trigger_immediate_heartbeat() events (failover, etc)
    
    Args:
        stop_event: Threading event to signal stop
    """
    global meeting_state, _immediate_heartbeat_event, _last_known_connectivity_state
    
    print("[Meeting] Heartbeat thread started")
    
    config = load_meeting_config()
    interval = config.get('heartbeat_interval', 30)
    
    while True:
        if stop_event and stop_event.is_set():
            break
        
        try:
            # Reload config to check if still enabled
            config = load_meeting_config()
            interval = config.get('heartbeat_interval', 30)
            
            # Check for immediate heartbeat trigger (failover, etc)
            immediate_triggered = _immediate_heartbeat_event.is_set()
            if immediate_triggered:
                _immediate_heartbeat_event.clear()
            
            # Detect connectivity changes
            current_connectivity = has_internet_connectivity()
            connectivity_restored = (
                _last_known_connectivity_state == False and 
                current_connectivity == True
            )
            
            if connectivity_restored:
                print("[Meeting] Connectivity restored, sending immediate heartbeat")
            
            # Update last known state
            _last_known_connectivity_state = current_connectivity
            
            if config.get('enabled'):
                with meeting_state['lock']:
                    meeting_state['enabled'] = True
                
                # Send heartbeat if:
                # 1. Connectivity was just restored
                # 2. Immediate trigger was activated (failover, etc)
                # 3. Regular interval timeout (see wait below)
                should_send = connectivity_restored or immediate_triggered
                
                if should_send:
                    # Send heartbeat with error handling
                    try:
                        send_heartbeat()
                    except Exception as e:
                        import sys
                        print(f"[Meeting] ERROR in send_heartbeat: {e}", file=sys.stderr)
                        with meeting_state['lock']:
                            meeting_state['last_error'] = str(e)
                else:
                    # No immediate send needed, send on regular interval
                    try:
                        send_heartbeat()
                    except Exception as e:
                        import sys
                        print(f"[Meeting] ERROR in send_heartbeat: {e}", file=sys.stderr)
                        with meeting_state['lock']:
                            meeting_state['last_error'] = str(e)
            else:
                with meeting_state['lock']:
                    meeting_state['enabled'] = False
                    meeting_state['connected'] = False
        
        except Exception as e:
            # Catch any unexpected errors to prevent thread crash
            import sys
            print(f"[Meeting] CRITICAL ERROR in heartbeat loop: {e}", file=sys.stderr)
        
        # Wait for next interval or immediate trigger event
        # The wait is interruptible by:
        # 1. stop_event being set (normal shutdown)
        # 2. _immediate_heartbeat_event being set (failover/reconnection)
        if stop_event:
            # Wait for either stop_event or immediate_heartbeat_event
            # Using a shorter timeout to check immediate_heartbeat_event more frequently
            start_time = time.time()
            while time.time() - start_time < interval:
                if stop_event.is_set():
                    break
                if _immediate_heartbeat_event.is_set():
                    break
                time.sleep(0.5)  # Check every 500ms for immediate trigger
            
            if stop_event.is_set():
                break
        else:
            time.sleep(interval)
    
    print("[Meeting] Heartbeat thread stopped")
    with meeting_state['lock']:
        meeting_state['thread_running'] = False

def start_heartbeat_thread():
    """
    Start the heartbeat background thread if not already running.
    
    Returns:
        bool: True if thread was started, False if already running or disabled
    """
    global _heartbeat_thread, _heartbeat_stop_event, meeting_state
    
    with meeting_state['lock']:
        if meeting_state['thread_running']:
            return False  # Already running
    
    config = load_meeting_config()
    if not config.get('enabled', False):
        return False  # Not enabled
    
    # Reset stop event
    _heartbeat_stop_event.clear()
    
    with meeting_state['lock']:
        meeting_state['thread_running'] = True
    
    _heartbeat_thread = threading.Thread(
        target=meeting_heartbeat_loop,
        args=(_heartbeat_stop_event,),
        daemon=True
    )
    _heartbeat_thread.start()
    
    return True

def stop_heartbeat_thread():
    """
    Signal the heartbeat thread to stop.
    """
    global _heartbeat_stop_event, meeting_state
    
    _heartbeat_stop_event.set()
    
    with meeting_state['lock']:
        meeting_state['thread_running'] = False
        meeting_state['connected'] = False

# ============================================================================
# IMMEDIATE HEARTBEAT TRIGGER
# ============================================================================

def has_internet_connectivity():
    """
    Check if device has internet connectivity (for detecting reconnection).
    Tests DNS resolution to a public DNS server.
    
    Returns:
        bool: True if internet is available, False otherwise
    """
    try:
        import socket
        # Try DNS lookup (non-blocking, ~100ms timeout)
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except Exception:
        return False

def trigger_immediate_heartbeat():
    """
    Trigger an immediate heartbeat to be sent as soon as possible.
    
    This is called when:
    - Network failover occurs (ethernet/wifi switch)
    - Internet connection is restored
    - WiFi reconnection after dropout
    - Other urgent connectivity changes
    
    Returns:
        bool: True if event was set, False if already pending
    """
    global _immediate_heartbeat_event
    
    if not _immediate_heartbeat_event.is_set():
        _immediate_heartbeat_event.set()
        print("[Meeting] Immediate heartbeat triggered by event")
        return True
    
    return False

# ============================================================================
# DEVICE OPERATIONS
# ============================================================================

def get_meeting_device_info():
    """
    Get device information from the Meeting API.
    
    Returns:
        dict: Device information
    """
    config = load_meeting_config()
    
    if not config.get('device_key'):
        return {'success': False, 'error': 'Device key not configured'}
    
    endpoint = f"/api/devices/{config['device_key']}"
    return meeting_api_request(endpoint, method='GET')

def request_tunnel(tunnel_type='ssh', port=22):
    """
    Request a tunnel from the Meeting API.
    
    Args:
        tunnel_type: Type of tunnel ('ssh', 'http', etc.)
        port: Local port to tunnel
    
    Returns:
        dict: Tunnel information
    """
    config = load_meeting_config()
    
    if not config.get('device_key'):
        return {'success': False, 'error': 'Device key not configured'}
    
    endpoint = f"/api/devices/{config['device_key']}/service"
    data = {
        'type': tunnel_type,
        'port': port
    }
    
    return meeting_api_request(endpoint, method='POST', data=data)

def update_provision(provision_data):
    """
    Update device provisioning data.
    
    Args:
        provision_data: Provisioning data dict
    
    Returns:
        dict: Result
    """
    config = load_meeting_config()
    
    if not config.get('device_key'):
        return {'success': False, 'error': 'Device key not configured'}
    
    endpoint = f"/api/devices/{config['device_key']}/provision"
    return meeting_api_request(endpoint, method='PUT', data=provision_data)

def get_device_availability():
    """
    Get device availability status from Meeting API.
    
    Returns:
        dict: Availability information
    """
    config = load_meeting_config()
    
    if not config.get('device_key'):
        return {'success': False, 'error': 'Device key not configured'}
    
    endpoint = f"/api/devices/{config['device_key']}/availability"
    return meeting_api_request(endpoint, method='GET')

# ============================================================================
# VALIDATION AND PROVISIONING
# ============================================================================

def validate_credentials(api_url, device_key, token_code):
    """
    Validate Meeting API credentials without saving them.
    
    Args:
        api_url: Meeting API URL
        device_key: Device key
        token_code: Token code
    
    Returns:
        dict: {success: bool, valid: bool, device: dict, message: str}
    """
    if not api_url or not device_key or not token_code:
        return {
            'success': False,
            'valid': False,
            'message': _t('ui.errors.all_fields_required')
        }
    
    url = _build_api_url(api_url, f"/api/devices/{device_key}")
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Token-Code': token_code
    }
    
    try:
        request = urllib.request.Request(url, headers=headers, method='GET')
        
        with urllib.request.urlopen(request, timeout=15) as response:
            response_data = response.read().decode('utf-8')
            data = json.loads(response_data) if response_data else {}
            
            # Check if we got valid device info
            if data.get('device_key') == device_key or data.get('key') == device_key:
                return {
                    'success': True,
                    'valid': True,
                    'device': {
                        'name': data.get('name', data.get('hostname', 'Unknown')),
                        'authorized': data.get('authorized', True),
                        'token_count': data.get('token_count', data.get('tokens_remaining', 0)),
                        'online': data.get('online', False),
                        'provisioned': data.get('provisioned', False)
                    },
                    'message': _t('ui.meeting.credentials_valid')
                }
            else:
                return {
                    'success': True,
                    'valid': True,
                    'device': data,
                    'message': _t('ui.meeting.credentials_valid')
                }
    
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {
                'success': True,
                'valid': False,
                'message': _t('ui.meeting.token_invalid')
            }
        elif e.code == 404:
            return {
                'success': True,
                'valid': False,
                'message': _t('ui.meeting.device_key_not_found')
            }
        else:
            return {
                'success': False,
                'valid': False,
                'message': _t('ui.meeting.http_error', code=e.code, reason=e.reason)
            }
    
    except urllib.error.URLError as e:
        return {
            'success': False,
            'valid': False,
            'message': _t('ui.meeting.connection_error', reason=e.reason)
        }
    
    except Exception as e:
        return {
            'success': False,
            'valid': False,
            'message': str(e)
        }

def provision_device(api_url, device_key, token_code):
    """
    Provision the device with Meeting API.
    This consumes a token via flash-request and sets up the device hostname.
    
    Args:
        api_url: Meeting API URL
        device_key: Device key
        token_code: Token code
    
    Returns:
        dict: {success: bool, hostname: str, tokens_left: int, message: str}
    """
    if not api_url or not device_key or not token_code:
        return {
            'success': False,
            'message': _t('ui.errors.all_fields_required')
        }
    
    # First validate credentials
    validation = validate_credentials(api_url, device_key, token_code)
    if not validation.get('valid'):
        return {
            'success': False,
            'message': validation.get('message', _t('ui.meeting.invalid_credentials'))
        }
    
    device = validation.get('device', {})
    
    # Check if device is authorized
    if not device.get('authorized', True):
        return {
            'success': False,
            'message': _t('ui.meeting.device_not_authorized')
        }
    
    # Check token count
    token_count = device.get('token_count', 0)
    if token_count <= 0:
        return {
            'success': False,
            'message': _t('ui.meeting.token_unavailable')
        }
    
    # Call flash-request endpoint to consume a token
    url = _build_api_url(api_url, f"/devices/{device_key}/flash-request")
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Token-Code': token_code,
        'User-Agent': 'RTSP-Recorder/1.0'
    }
    
    try:
        # Create SSL context that doesn't verify (for self-signed certs)
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        request = urllib.request.Request(url, headers=headers, method='POST')
        
        with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
            response_data = response.read().decode('utf-8')
            data = json.loads(response_data) if response_data else {}
            
            tokens_left = data.get('tokens_left', token_count - 1)
            
            # Save configuration
            config = load_meeting_config()
            config['enabled'] = True
            config['api_url'] = api_url
            config['device_key'] = device_key
            config['token_code'] = token_code
            config['provisioned'] = True
            save_meeting_config(config)
            
            # Also save to config.env
            _save_to_config_env(api_url, device_key, token_code)
            
            # Start heartbeat thread
            start_heartbeat_thread()
            
            # Change hostname to device_key (using robust set_hostname function)
            hostname_changed = False
            current_hostname = os.uname().nodename
            if device_key and device_key != current_hostname:
                result = set_hostname(device_key)
                hostname_changed = result.get('success', False)
            
            return {
                'success': True,
                'device_key': device_key,
                'hostname': device_key,
                'hostname_changed': hostname_changed,
                'tokens_left': tokens_left,
                'message': _t('ui.meeting.provision_success', tokens_left=tokens_left)
            }
    
    except urllib.error.HTTPError as e:
        error_body = ''
        try:
            error_body = e.read().decode('utf-8')
        except:
            pass
        return {
            'success': False,
            'message': _t('ui.meeting.provision_token_error', code=e.code),
            'details': error_body
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': _t('ui.meeting.provision_failed', error=str(e))
        }

def _save_to_config_env(api_url, device_key, token_code):
    """Save meeting config to config.env file."""
    try:
        if not os.path.exists(CONFIG_FILE):
            return
        
        lines = []
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
        
        # Update or add meeting settings
        settings = {
            'MEETING_ENABLED': 'yes',
            'MEETING_API_URL': api_url,
            'MEETING_DEVICE_KEY': device_key,
            'MEETING_TOKEN_CODE': '********',  # Don't store actual token in plain text
            'MEETING_PROVISIONED': 'yes'
        }
        
        updated_keys = set()
        new_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in settings:
                    new_lines.append(f'{key}="{settings[key]}"\n')
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Add missing settings
        for key, value in settings.items():
            if key not in updated_keys:
                new_lines.append(f'{key}="{value}"\n')
        
        with open(CONFIG_FILE, 'w') as f:
            f.writelines(new_lines)
    
    except Exception as e:
        print(f"Error saving to config.env: {e}")

# ============================================================================
# INITIALIZATION
# ============================================================================

def init_meeting_service():
    """
    Initialize the Meeting service with configuration.
    
    Returns:
        dict: {success: bool, message: str}
    """
    global meeting_state
    
    config = load_meeting_config()
    
    with meeting_state['lock']:
        meeting_state['api_url'] = config.get('api_url', '')
        meeting_state['device_key'] = config.get('device_key', '')
        meeting_state['token_code'] = config.get('token_code', '')
        meeting_state['heartbeat_interval'] = config.get('heartbeat_interval', 30)
        meeting_state['enabled'] = config.get('enabled', False)
    
    if config.get('enabled') and config.get('auto_connect', True):
        # Start heartbeat thread and send initial heartbeat
        start_heartbeat_thread()
        result = send_heartbeat()
        return result
    
    return {'success': True, 'message': _t('ui.meeting.service_initialized')}

def enable_meeting_service(api_url, device_key, token_code, heartbeat_interval=30):
    """
    Enable and configure the Meeting service.
    
    Args:
        api_url: Meeting API URL
        device_key: Device key for authentication
        token_code: Token code for authentication
        heartbeat_interval: Heartbeat interval in seconds
    
    Returns:
        dict: {success: bool, message: str}
    """
    config = {
        'enabled': True,
        'api_url': api_url,
        'device_key': device_key,
        'token_code': token_code,
        'heartbeat_interval': heartbeat_interval,
        'auto_connect': True
    }
    
    result = save_meeting_config(config)
    
    if result['success']:
        init_meeting_service()
    
    return result

def disable_meeting_service():
    """
    Disable the Meeting service.
    
    Returns:
        dict: {success: bool, message: str}
    """
    global meeting_state
    
    config = load_meeting_config()
    config['enabled'] = False
    
    result = save_meeting_config(config)
    
    with meeting_state['lock']:
        meeting_state['enabled'] = False
        meeting_state['connected'] = False
    
    return result

# ============================================================================
# MASTER RESET
# ============================================================================

MASTER_CODE = 'meeting'  # In production, store this securely

def master_reset(master_code):
    """
    Reset Meeting configuration completely.
    Clears device_key, token_code, and provisioned flag.
    
    Args:
        master_code: Master code for authorization
    
    Returns:
        dict: {success: bool, message: str}
    """
    global meeting_state
    
    # Check master code
    if master_code != MASTER_CODE:
        return {
            'success': False,
            'message': _t('ui.meeting.master_code_invalid')
        }
    
    try:
        # Delete meeting.json if it exists
        if os.path.exists(MEETING_CONFIG_FILE):
            os.remove(MEETING_CONFIG_FILE)
        
        # Reset config.env
        if os.path.exists(CONFIG_FILE):
            lines = []
            with open(CONFIG_FILE, 'r') as f:
                lines = f.readlines()
            
            reset_values = {
                'MEETING_ENABLED': 'no',
                'MEETING_API_URL': 'https://meeting.example.com/api',
                'MEETING_DEVICE_KEY': '',
                'MEETING_TOKEN_CODE': '',
                'MEETING_PROVISIONED': 'no'
            }
            
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    key = stripped.split('=', 1)[0].strip()
                    if key in reset_values:
                        new_lines.append(f'{key}="{reset_values[key]}"\n')
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            with open(CONFIG_FILE, 'w') as f:
                f.writelines(new_lines)
        
        # Reset in-memory state
        with meeting_state['lock']:
            meeting_state['enabled'] = False
            meeting_state['connected'] = False
            meeting_state['api_url'] = None
            meeting_state['device_key'] = None
            meeting_state['token_code'] = None
            meeting_state['last_heartbeat'] = None
            meeting_state['last_error'] = None
            meeting_state['device_info'] = None
        
        return {
            'success': True,
            'message': _t('ui.meeting.reset_done_hostname_preserved')
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': _t('ui.meeting.reset_failed', error=str(e))
        }

# ============================================================================
# SERVICE CHECK
# ============================================================================

# Cache for full device info (services, etc.)
_full_device_info_cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 300  # 5 minutes cache
}

def _get_full_device_info():
    """
    Get full device info from Meeting API with caching.
    The heartbeat only returns basic info, but /api/devices/{key} returns services.
    
    Returns:
        dict: Full device info or None
    """
    import time
    
    now = time.time()
    
    # Return cached data if still valid
    if (_full_device_info_cache['data'] and 
        now - _full_device_info_cache['timestamp'] < _full_device_info_cache['ttl']):
        return _full_device_info_cache['data']
    
    # Fetch from API
    result = get_meeting_device_info()
    if result.get('success') and result.get('data'):
        _full_device_info_cache['data'] = result['data']
        _full_device_info_cache['timestamp'] = now
        return result['data']
    
    return _full_device_info_cache['data']  # Return stale cache if API fails

def is_service_declared(service_name):
    """
    Check if a service is declared for this device in Meeting.
    
    Args:
        service_name: Name of the service to check (e.g., 'vnc', 'ssh', 'debug')
    
    Returns:
        bool: True if service is declared, False otherwise
    """
    # First check heartbeat cache
    with meeting_state['lock']:
        device_info = meeting_state.get('device_info')
    
    # Check in heartbeat device_info if available
    if device_info:
        # Check declared_services (list of strings or dicts)
        declared_services = device_info.get('declared_services', [])
        if isinstance(declared_services, list):
            for svc in declared_services:
                if isinstance(svc, str) and svc.lower() == service_name.lower():
                    return True
                elif isinstance(svc, dict):
                    svc_name = svc.get('name', '') or svc.get('type', '')
                    if svc_name.lower() == service_name.lower():
                        return True
        
        # Check services (could be list or dict)
        services = device_info.get('services', [])
        if isinstance(services, list):
            if service_name.lower() in [s.lower() for s in services if isinstance(s, str)]:
                return True
        elif isinstance(services, dict):
            if service_name.lower() in [k.lower() for k in services.keys()]:
                return True
    
    # If not found in heartbeat cache, fetch full device info from Meeting API
    full_info = _get_full_device_info()
    if full_info:
        # Check services list from full API response
        services = full_info.get('services', [])
        if isinstance(services, list):
            if service_name.lower() in [s.lower() for s in services if isinstance(s, str)]:
                return True
        elif isinstance(services, dict):
            if service_name.lower() in [k.lower() for k in services.keys()]:
                return True
    
    return False

def is_debug_enabled():
    """
    Check if debug mode is enabled (via 'vnc' service temporarily, later 'debug' service).
    
    Returns:
        bool: True if debug is enabled
    """
    # Check for 'vnc' service (temporary) or 'debug' service (future)
    return is_service_declared('vnc') or is_service_declared('debug')


# -*- coding: utf-8 -*-
"""
Meeting Service - Meeting API integration and heartbeat
Version: 2.30.23

Conforms to Meeting API integration guide (docs/MEETING - integration.md):
- Heartbeat: POST /api/devices/{device_key}/online (v1.8.0+ network fields)
- SSH hostkey sync: GET /api/ssh-hostkey
- SSH key publication: PUT /api/devices/{device_key}/ssh-key
- Meeting SSH pubkey: GET /api/ssh/pubkey

Note: Services are managed by Meeting admin only (not sent in heartbeat).
"""

import os
import re
import ssl
import json
import time
import pwd
import logging
import threading
import subprocess
import urllib.request
import urllib.error
from datetime import datetime

from .platform_service import run_command
from .config_service import set_hostname
from config import MEETING_CONFIG_FILE, CONFIG_FILE

# Logger for debug
logger = logging.getLogger('services.meeting_service')

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

# ============================================================================
# CONFIGURATION
# ============================================================================

def load_meeting_config():
    """
    Load Meeting API configuration from file.
    First tries meeting.json, then falls back to config.env.
    
    IMPORTANT (v2.30.13): Auto-generates device_key if missing.
    This ensures heartbeat always runs, even on devices without provisioning.
    
    Per Meeting API integration guide: default heartbeat interval is 60s.
    
    Returns:
        dict: Meeting configuration
    """
    default_config = {
        'enabled': True,  # CHANGED: Default to True (v2.30.13) - heartbeat should always try
        'api_url': 'https://api.meeting.co',  # Default Meeting API URL
        'device_key': '',  # Will be auto-generated if empty
        'token_code': '',
        'heartbeat_interval': 60,  # Per Meeting API spec: 60s recommended interval
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
        
        return {'success': True, 'message': 'Meeting configuration saved'}
    
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
# SSH KEY STATUS AND AUTO-SETUP
# ============================================================================

def get_ssh_keys_status():
    """
    Check the status of SSH keys for Meeting integration.
    
    Returns:
        dict: {
            device_key_present: bool,   # Device has an SSH key pair
            device_key_published: bool, # Key published to Meeting API (if we can verify)
            meeting_key_installed: bool,# Meeting pubkey in authorized_keys (for 'device' user)
            device_pubkey: str,         # Device's public key (truncated)
            details: dict               # Detailed info per user
        }
    """
    result = {
        'device_key_present': False,
        'device_key_published': False,
        'meeting_key_installed': False,
        'device_pubkey': None,
        'meeting_pubkey_preview': None,
        'details': {}
    }
    
    # Check device SSH key (in /root/.ssh since service runs as root)
    for key_type in ['id_ed25519', 'id_rsa']:
        key_path = f'/root/.ssh/{key_type}.pub'
        if os.path.exists(key_path):
            try:
                with open(key_path, 'r') as f:
                    pubkey = f.read().strip()
                    result['device_key_present'] = True
                    result['device_pubkey'] = pubkey[:60] + '...' if len(pubkey) > 60 else pubkey
                    result['details']['device_key_type'] = key_type
                    break
            except:
                pass
    
    # Check if Meeting pubkey is in authorized_keys for 'device' user
    # (This is the user Meeting SSH will connect to)
    try:
        # First, get Meeting pubkey for comparison
        meeting_result = get_meeting_ssh_pubkey()
        if meeting_result.get('success'):
            meeting_pubkey = meeting_result['pubkey'].strip()
            meeting_parts = meeting_pubkey.split()[:2]  # type + key
            result['meeting_pubkey_preview'] = meeting_pubkey[:60] + '...' if len(meeting_pubkey) > 60 else meeting_pubkey
            
            # Check authorized_keys for 'device' user
            try:
                pw = pwd.getpwnam('device')
                auth_keys_path = os.path.join(pw.pw_dir, '.ssh', 'authorized_keys')
                if os.path.exists(auth_keys_path):
                    with open(auth_keys_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                key_parts = line.split()[:2]
                                if key_parts == meeting_parts:
                                    result['meeting_key_installed'] = True
                                    break
            except KeyError:
                result['details']['device_user_error'] = 'User "device" not found'
            except Exception as e:
                result['details']['auth_keys_error'] = str(e)
    except Exception as e:
        result['details']['meeting_key_error'] = str(e)
    
    return result


def ensure_ssh_keys_configured():
    """
    Ensure SSH keys are properly configured for Meeting integration.
    Called automatically when tunnel agent starts or during provisioning.
    
    This function:
    1. Generates device SSH key if missing
    2. Installs Meeting pubkey in authorized_keys for 'device' user
    3. Publishes device key to Meeting API
    
    Returns:
        dict: {success: bool, message: str, actions: list}
    """
    config = load_meeting_config()
    if not config.get('device_key') or not config.get('provisioned'):
        return {
            'success': False,
            'message': 'Device not provisioned - SSH keys setup skipped',
            'actions': []
        }
    
    actions = []
    errors = []
    
    # Step 1: Generate device SSH key if missing
    key_exists = any(
        os.path.exists(f'/root/.ssh/{kt}')
        for kt in ['id_ed25519', 'id_rsa']
    )
    
    if not key_exists:
        gen_result = generate_device_ssh_key()
        if gen_result.get('success'):
            actions.append('Generated device SSH key (ed25519)')
        else:
            errors.append(f"Key generation failed: {gen_result.get('message')}")
    
    # Step 2: Install Meeting pubkey for 'device' user
    install_result = install_meeting_ssh_pubkey()
    if install_result.get('success'):
        actions.append(f"Meeting key: {install_result.get('message')}")
    else:
        errors.append(f"Meeting key install: {install_result.get('message')}")
    
    # Step 3: Publish device key to Meeting API
    pub_result = publish_device_ssh_key()
    if pub_result.get('success'):
        actions.append('Published device SSH key to Meeting API')
    else:
        errors.append(f"Key publication: {pub_result.get('message')}")
    
    success = len(errors) == 0
    return {
        'success': success,
        'message': 'SSH keys configured' if success else 'Some SSH operations failed',
        'actions': actions,
        'errors': errors if errors else None
    }


# ============================================================================
# HEARTBEAT
# ============================================================================

def get_meeting_ssh_pubkey():
    """
    Fetch Meeting server's SSH public key from API.
    
    Returns:
        dict: {success: bool, pubkey: str, fingerprint: str, message: str}
    """
    try:
        config = load_meeting_config()
        api_url = config.get('api_url', 'https://meeting.ygsoft.fr/api').rstrip('/')
        
        # Build URL for SSH pubkey endpoint
        url = f"{api_url}/ssh/pubkey"
        
        # Create SSL context that doesn't verify certificates (self-signed)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        request = urllib.request.Request(url)
        request.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(request, timeout=10, context=ssl_context) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if 'pubkey' in data:
                return {
                    'success': True,
                    'pubkey': data['pubkey'],
                    'fingerprint': data.get('fingerprint', ''),
                    'host': data.get('host', ''),
                    'message': 'SSH pubkey retrieved successfully'
                }
            else:
                return {'success': False, 'message': 'No pubkey in response'}
                
    except Exception as e:
        return {'success': False, 'message': str(e)}


def install_meeting_ssh_pubkey():
    """
    Fetch and install Meeting server's SSH public key to authorized_keys.
    Installs for BOTH root and 'device' user (Meeting SSH connects to 'device').
    
    Returns:
        dict: {success: bool, message: str, installed_for: list}
    """
    try:
        # Get the pubkey from Meeting API
        result = get_meeting_ssh_pubkey()
        if not result['success']:
            return result
        
        pubkey = result['pubkey'].strip()
        if not pubkey:
            return {'success': False, 'message': 'Empty pubkey received'}
        
        installed_for = []
        errors = []
        
        # Install for both root and device user
        users_to_install = ['root', 'device']
        
        for username in users_to_install:
            try:
                # Get home directory for user
                if username == 'root':
                    home_dir = '/root'
                else:
                    try:
                        pw = pwd.getpwnam(username)
                        home_dir = pw.pw_dir
                    except KeyError:
                        errors.append(f"User '{username}' not found")
                        continue
                
                ssh_dir = os.path.join(home_dir, '.ssh')
                auth_keys = os.path.join(ssh_dir, 'authorized_keys')
                
                # Create .ssh directory if needed
                os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
                
                # Fix ownership for non-root users
                if username != 'root':
                    try:
                        pw = pwd.getpwnam(username)
                        os.chown(ssh_dir, pw.pw_uid, pw.pw_gid)
                    except:
                        pass
                
                # Read existing authorized_keys
                existing_keys = []
                if os.path.exists(auth_keys):
                    with open(auth_keys, 'r') as f:
                        existing_keys = [line.strip() for line in f if line.strip()]
                
                # Check if key already installed (by key content, ignoring comment)
                pubkey_parts = pubkey.split()[:2]  # type + key without comment
                key_found = False
                for key in existing_keys:
                    key_parts = key.split()[:2]
                    if key_parts == pubkey_parts:
                        key_found = True
                        break
                
                if key_found:
                    installed_for.append(f"{username} (already present)")
                else:
                    # Add the key
                    with open(auth_keys, 'a') as f:
                        f.write(f"\n{pubkey}\n")
                    installed_for.append(username)
                
                # Fix permissions
                os.chmod(auth_keys, 0o600)
                
                # Fix ownership for non-root users
                if username != 'root':
                    try:
                        pw = pwd.getpwnam(username)
                        os.chown(auth_keys, pw.pw_uid, pw.pw_gid)
                    except:
                        pass
                        
            except Exception as e:
                errors.append(f"{username}: {str(e)}")
        
        if installed_for:
            return {
                'success': True,
                'message': f'Meeting SSH key installed for: {", ".join(installed_for)}',
                'installed_for': installed_for,
                'errors': errors if errors else None,
                'fingerprint': result.get('fingerprint', ''),
                'host': result.get('host', '')
            }
        else:
            return {
                'success': False,
                'message': f'Failed to install key: {"; ".join(errors)}',
                'errors': errors
            }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


def get_ssh_hostkey():
    """
    Fetch Meeting server's SSH hostkey for known_hosts.
    Per MEETING - integration.md: GET /api/ssh-hostkey
    
    Returns:
        dict: {success: bool, hostkeys: str, message: str}
    """
    try:
        config = load_meeting_config()
        api_url = config.get('api_url', 'https://meeting.ygsoft.fr/api').rstrip('/')
        
        # Build URL - handle /api prefix
        base_url = api_url.rstrip('/api') if api_url.endswith('/api') else api_url
        url = f"{base_url}/api/ssh-hostkey"
        
        # Create SSL context that doesn't verify certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        request = urllib.request.Request(url)
        request.add_header('Accept', 'text/plain')
        
        with urllib.request.urlopen(request, timeout=10, context=ssl_context) as response:
            hostkeys = response.read().decode('utf-8').strip()
            
            if hostkeys:
                return {
                    'success': True,
                    'hostkeys': hostkeys,
                    'message': 'SSH hostkeys retrieved successfully'
                }
            else:
                return {'success': False, 'message': 'Empty hostkey response'}
                
    except Exception as e:
        return {'success': False, 'message': str(e)}


def sync_ssh_hostkey():
    """
    Sync Meeting server's SSH hostkey to known_hosts.
    Per MEETING - integration.md: Atomic update with lockfile.
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        # Get hostkeys from server
        result = get_ssh_hostkey()
        if not result['success']:
            return result
        
        hostkeys = result['hostkeys']
        
        # Determine known_hosts location
        home_dir = os.path.expanduser('~')
        ssh_dir = os.path.join(home_dir, '.ssh')
        known_hosts = os.path.join(ssh_dir, 'known_hosts')
        lock_file = os.path.join(ssh_dir, '.known_hosts.lock')
        
        # Create .ssh directory if needed
        os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
        
        # Extract hostname from hostkeys (format: "hostname algo key comment")
        meeting_hosts = set()
        for line in hostkeys.split('\n'):
            if line.strip():
                parts = line.split()
                if parts:
                    meeting_hosts.add(parts[0])
        
        # Atomic update with lockfile
        import fcntl
        with open(lock_file, 'w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                # Read existing known_hosts
                existing_lines = []
                if os.path.exists(known_hosts):
                    with open(known_hosts, 'r') as f:
                        for line in f:
                            line_host = line.split()[0] if line.strip() else ''
                            # Keep lines that aren't for Meeting hosts
                            if line_host not in meeting_hosts:
                                existing_lines.append(line.rstrip('\n'))
                
                # Write to temp file, then rename (atomic)
                temp_file = known_hosts + '.tmp'
                with open(temp_file, 'w') as f:
                    for line in existing_lines:
                        f.write(line + '\n')
                    # Add Meeting hostkeys
                    f.write(hostkeys + '\n')
                
                os.rename(temp_file, known_hosts)
                os.chmod(known_hosts, 0o644)
                
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        
        return {
            'success': True,
            'message': f'SSH hostkeys synced for {len(meeting_hosts)} host(s)',
            'hosts': list(meeting_hosts)
        }
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


def publish_device_ssh_key():
    """
    Publish device's SSH public key to Meeting server.
    Per MEETING - integration.md: PUT /api/devices/{device_key}/ssh-key
    
    Generates ed25519 key if not present.
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        config = load_meeting_config()
        device_key = config.get('device_key')
        
        if not device_key:
            return {'success': False, 'message': 'Device key not configured'}
        
        # Find or generate SSH key
        home_dir = os.path.expanduser('~')
        ssh_dir = os.path.join(home_dir, '.ssh')
        os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
        
        # Prefer ed25519, fallback to rsa
        key_paths = [
            (os.path.join(ssh_dir, 'id_ed25519.pub'), os.path.join(ssh_dir, 'id_ed25519')),
            (os.path.join(ssh_dir, 'id_rsa.pub'), os.path.join(ssh_dir, 'id_rsa')),
        ]
        
        pubkey = None
        for pub_path, priv_path in key_paths:
            if os.path.exists(pub_path):
                with open(pub_path, 'r') as f:
                    pubkey = f.read().strip()
                break
        
        # Generate ed25519 key if none found
        if not pubkey:
            priv_path = os.path.join(ssh_dir, 'id_ed25519')
            pub_path = priv_path + '.pub'
            
            result = run_command(
                f'ssh-keygen -t ed25519 -f {priv_path} -N "" -C "device@{device_key[:8]}"',
                shell=True
            )
            
            if not result.get('success'):
                return {'success': False, 'message': f'Failed to generate SSH key: {result.get("stderr", "")}'}
            
            with open(pub_path, 'r') as f:
                pubkey = f.read().strip()
        
        # Publish to Meeting API
        endpoint = f"/api/devices/{device_key}/ssh-key"
        result = meeting_api_request(endpoint, method='PUT', data={'pubkey': pubkey})
        
        if result['success']:
            return {
                'success': True,
                'message': 'Device SSH key published successfully',
                'pubkey': pubkey[:50] + '...'  # Truncate for display
            }
        else:
            return {'success': False, 'message': result.get('error', 'Failed to publish key')}
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


def get_declared_services():
    """
    Get the list of services to declare in heartbeat.
    Per Meeting API: keys are 'ssh', 'http', 'vnc', 'scp', 'debug'.
    
    Returns:
        dict: Services status {service_name: bool}
    """
    services = {
        'ssh': False,
        'http': False,
        'vnc': False,
        'scp': False,
        'debug': False
    }
    
    try:
        # Check SSH (port 22)
        result = run_command("systemctl is-active ssh sshd 2>/dev/null || true", shell=True)
        services['ssh'] = 'active' in (result.get('stdout', '') or '')
        
        # Check HTTP (web manager on port 5000)
        result = run_command("systemctl is-active rpi-cam-webmanager 2>/dev/null || true", shell=True)
        services['http'] = 'active' in (result.get('stdout', '') or '')
        
        # SCP is available if SSH is available
        services['scp'] = services['ssh']
        
        # VNC - check if any VNC server is running
        result = run_command("pgrep -x 'vncserver|Xvnc|x11vnc' 2>/dev/null || true", shell=True)
        services['vnc'] = bool(result.get('stdout', '').strip())
        
        # Debug mode - check if debug is enabled in config
        try:
            from .config_service import load_config
            config = load_config()
            services['debug'] = config.get('DEBUG_MODE', 'no').lower() in ('yes', 'true', '1')
        except:
            pass
        
    except Exception as e:
        import sys
        print(f"[Meeting] Warning: Failed to detect services: {e}", file=sys.stderr)
    
    return services


def get_meeting_authorized_services():
    """
    Get the list of services AUTHORIZED by Meeting API for this device.
    This fetches from Meeting API what services the admin has enabled.
    
    Returns:
        dict: {success: bool, services: dict{service_name: bool}, error: str}
    """
    all_services = ['ssh', 'http', 'vnc', 'scp', 'debug']
    services = {s: False for s in all_services}
    
    try:
        # Fetch from Meeting API
        full_info = _get_full_device_info()
        
        if not full_info:
            return {
                'success': False,
                'services': services,
                'error': 'Unable to fetch device info from Meeting API'
            }
        
        # Parse services from API response
        # Services can be a list of strings or a dict
        api_services = full_info.get('services', [])
        
        if isinstance(api_services, list):
            for svc in api_services:
                if isinstance(svc, str) and svc.lower() in all_services:
                    services[svc.lower()] = True
                elif isinstance(svc, dict):
                    # Handle dict format {name: ..., enabled: ...}
                    svc_name = (svc.get('name') or svc.get('type') or '').lower()
                    if svc_name in all_services:
                        services[svc_name] = svc.get('enabled', True)
        elif isinstance(api_services, dict):
            for key, value in api_services.items():
                if key.lower() in all_services:
                    services[key.lower()] = bool(value)
        
        return {
            'success': True,
            'services': services
        }
        
    except Exception as e:
        return {
            'success': False,
            'services': services,
            'error': str(e)
        }

def get_heartbeat_payload():
    """
    Build and return the heartbeat payload without sending it.
    Useful for debugging what would be sent to Meeting API.
    
    Returns:
        dict: {success: bool, payload: dict, config: dict}
    """
    try:
        config = load_meeting_config()
        
        if not config.get('device_key'):
            return {'success': False, 'error': 'No device_key configured'}
        
        # Collect system info
        try:
            from .config_service import get_system_info, get_device_description
            from .network_service import get_preferred_ip
            sys_info = get_system_info()
            local_ip = get_preferred_ip()
            device_description = get_device_description()
        except Exception as e:
            sys_info = {'uptime': '', 'cpu': {'load_1m': 0}, 'memory': {'percent': 0}, 'disk': {'percent': 0}, 'network': {}}
            local_ip = '127.0.0.1'
            device_description = 'RTSP Recorder'
        
        # Get network info for v1.8.0+ fields
        ip_lan = local_ip
        ip_public = None
        primary_mac = None
        
        try:
            from .network_service import get_network_interfaces, get_public_ip
            interfaces = get_network_interfaces()
            
            # Find primary interface (has gateway) for MAC
            for iface in interfaces:
                if iface.get('gateway') or iface.get('is_default'):
                    primary_mac = iface.get('mac', '').upper().replace('-', ':')
                    if iface.get('ip'):
                        ip_lan = iface['ip']
                    break
            
            # Get public IP
            ip_public = get_public_ip()
            
        except Exception as e:
            import sys
            print(f"[Meeting] Warning: Failed to get network info: {e}", file=sys.stderr)
        
        # Build heartbeat payload per Meeting API spec (v1.8.0+)
        heartbeat_data = {
            'ip_address': local_ip,
            'ip_lan': ip_lan,
            'ip_public': ip_public,
            'mac': primary_mac,
            'cluster_ip': None,  # Not implemented yet
            'note': device_description,
            # Extended info (server ignores unknown fields)
            'timestamp': datetime.now().isoformat(),
            'uptime': sys_info.get('uptime', ''),
            'cpu_load': sys_info.get('cpu', {}).get('load_1m', 0),
            'memory_percent': sys_info.get('memory', {}).get('percent', 0),
            'disk_percent': sys_info.get('disk', {}).get('percent', 0),
            'temperature': sys_info.get('temperature'),
        }
        
        # Remove None values (API may not like them)
        heartbeat_data = {k: v for k, v in heartbeat_data.items() if v is not None}
        
        return {
            'success': True,
            'payload': heartbeat_data,
            'endpoint': f"/api/devices/{config['device_key']}/online",
            'api_url': config.get('api_url', 'https://meeting.ygsoft.fr/api'),
            'device_key': config.get('device_key'),
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def send_heartbeat():
    """
    Send a heartbeat to the Meeting API.
    
    Payload structure per Meeting API integration guide (v1.8.0+):
    {
        "ip_address": "203.0.113.10",      # Primary IP (optional, uses REMOTE_ADDR if absent)
        "ip_lan": "192.168.1.100",          # LAN IP
        "ip_public": "203.0.113.10",        # Public IP detected by device
        "mac": "AA:BB:CC:DD:EE:FF",         # MAC address (format with :)
        "cluster_ip": "",                   # Cluster IP(s) if applicable
        "note": "optional short status"     # Device description
    }
    
    Note: 
    - Services are managed by Meeting admin, NOT sent by device.
    - The server ignores unknown fields (cpu_load, memory, etc.) but they don't hurt.
    
    Returns:
        dict: {success: bool, message: str}
    """
    global meeting_state
    
    try:
        config = load_meeting_config()
        
        if not config.get('enabled'):
            return {'success': False, 'message': 'Meeting API not enabled'}
        
        if not config.get('device_key'):
            return {'success': False, 'message': 'Device key not configured'}
        
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
        
        # Get network info for v1.8.0+ fields
        try:
            from .network_service import get_network_interfaces, get_public_ip
            interfaces = get_network_interfaces()
            
            # Find primary interface (has gateway) for MAC
            primary_mac = None
            ip_lan = local_ip
            for iface in interfaces:
                if iface.get('gateway') or iface.get('is_default'):
                    primary_mac = iface.get('mac', '').upper().replace('-', ':')
                    if iface.get('ip'):
                        ip_lan = iface['ip']
                    break
            
            # Get public IP (may be same as local if not behind NAT)
            ip_public = get_public_ip() or local_ip
            
        except Exception as e:
            import sys
            print(f"[Meeting] Warning: Failed to get network info: {e}", file=sys.stderr)
            primary_mac = None
            ip_lan = local_ip
            ip_public = local_ip
        
        # Build heartbeat data per Meeting API integration guide (v1.8.0+)
        # Note: services are managed by Meeting admin, NOT sent by device
        heartbeat_data = {
            'ip_address': local_ip,  # Primary IP for Meeting to store
            'ip_lan': ip_lan,        # LAN IP (v1.8.0+)
            'ip_public': ip_public,  # Public IP (v1.8.0+)
            'note': device_description,  # Device description
            # Extended info (server ignores unknown fields per spec)
            'timestamp': datetime.now().isoformat(),
            'uptime': sys_info.get('uptime', ''),
            'cpu_load': sys_info.get('cpu', {}).get('load_1m', 0),
            'memory_percent': sys_info.get('memory', {}).get('percent', 0),
            'disk_percent': sys_info.get('disk', {}).get('percent', 0),
            'temperature': sys_info.get('temperature'),
            'ip_addresses': sys_info.get('network', {})
        }
        
        # Add MAC if available (format: AA:BB:CC:DD:EE:FF per spec)
        if primary_mac:
            heartbeat_data['mac'] = primary_mac
        
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
# SSH KEY MANAGEMENT (per Meeting API integration guide)
# ============================================================================

SSH_KEY_PATH = '/root/.ssh/id_ed25519'
SSH_KEY_PATH_PUB = '/root/.ssh/id_ed25519.pub'
SSH_KNOWN_HOSTS_PATH = '/root/.ssh/known_hosts'
SSH_KNOWN_HOSTS_LOCK = '/tmp/meeting_known_hosts.lock'

def sync_ssh_hostkey():
    """
    Synchronize SSH hostkey from Meeting server.
    Per Meeting API: GET /api/ssh-hostkey returns public keys in ssh-keyscan format.
    
    Updates /root/.ssh/known_hosts atomically to prevent race conditions.
    
    Returns:
        dict: {success: bool, message: str, keys_count: int}
    """
    import tempfile
    import fcntl
    
    config = load_meeting_config()
    
    if not config.get('api_url'):
        return {'success': False, 'message': 'API URL not configured'}
    
    try:
        # Build URL for ssh-hostkey endpoint
        base_url = config['api_url'].rstrip('/')
        if base_url.endswith('/api'):
            url = base_url.replace('/api', '') + '/api/ssh-hostkey'
        else:
            url = base_url + '/api/ssh-hostkey'
        
        # Create SSL context (self-signed certs allowed)
        import ssl
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        request = urllib.request.Request(url, method='GET')
        
        with urllib.request.urlopen(request, timeout=15, context=ssl_context) as response:
            hostkeys = response.read().decode('utf-8').strip()
        
        if not hostkeys:
            return {'success': False, 'message': 'Empty hostkey response from server'}
        
        keys_count = len([line for line in hostkeys.split('\n') if line.strip()])
        
        # Ensure .ssh directory exists
        ssh_dir = os.path.dirname(SSH_KNOWN_HOSTS_PATH)
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)
        
        # Atomic write with lockfile to prevent concurrent updates
        try:
            # Create lock file
            lock_fd = open(SSH_KNOWN_HOSTS_LOCK, 'w')
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write to temp file first
            with tempfile.NamedTemporaryFile(mode='w', dir=ssh_dir, delete=False, prefix='.known_hosts_') as tmp:
                # Extract hostname from API URL for the known_hosts entry
                from urllib.parse import urlparse
                parsed = urlparse(config['api_url'])
                meeting_host = parsed.hostname
                
                # Read existing known_hosts (preserve non-meeting entries)
                existing_lines = []
                if os.path.exists(SSH_KNOWN_HOSTS_PATH):
                    with open(SSH_KNOWN_HOSTS_PATH, 'r') as f:
                        for line in f:
                            # Keep lines that don't match the meeting server
                            if meeting_host and meeting_host not in line:
                                existing_lines.append(line)
                
                # Write preserved entries
                for line in existing_lines:
                    tmp.write(line)
                
                # Add meeting server hostkeys
                for line in hostkeys.split('\n'):
                    if line.strip():
                        tmp.write(line + '\n')
                
                tmp_path = tmp.name
            
            # Atomic rename
            os.chmod(tmp_path, 0o644)
            os.rename(tmp_path, SSH_KNOWN_HOSTS_PATH)
            
            # Release lock
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
            
            return {
                'success': True,
                'message': f'SSH hostkeys synchronized ({keys_count} keys)',
                'keys_count': keys_count
            }
            
        except BlockingIOError:
            return {'success': False, 'message': 'Another sync operation in progress'}
        finally:
            try:
                if 'lock_fd' in locals():
                    lock_fd.close()
                if os.path.exists(SSH_KNOWN_HOSTS_LOCK):
                    os.remove(SSH_KNOWN_HOSTS_LOCK)
            except:
                pass
    
    except urllib.error.HTTPError as e:
        return {'success': False, 'message': f'HTTP error {e.code}: {e.reason}'}
    
    except urllib.error.URLError as e:
        return {'success': False, 'message': f'Connection error: {e.reason}'}
    
    except Exception as e:
        return {'success': False, 'message': str(e)}


def generate_device_ssh_key():
    """
    Generate SSH key pair for the device if not exists.
    Uses ed25519 algorithm (recommended by Meeting API).
    
    Returns:
        dict: {success: bool, message: str, pubkey: str}
    """
    try:
        # Ensure .ssh directory exists
        ssh_dir = os.path.dirname(SSH_KEY_PATH)
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)
        
        # Check if key already exists
        if os.path.exists(SSH_KEY_PATH) and os.path.exists(SSH_KEY_PATH_PUB):
            # Read existing public key
            with open(SSH_KEY_PATH_PUB, 'r') as f:
                pubkey = f.read().strip()
            return {
                'success': True,
                'message': 'SSH key already exists',
                'pubkey': pubkey,
                'generated': False
            }
        
        # Generate new ed25519 key pair
        import socket
        hostname = socket.gethostname()
        comment = f"device@{hostname}"
        
        result = run_command(f'ssh-keygen -t ed25519 -N "" -C "{comment}" -f {SSH_KEY_PATH}', shell=True)
        
        if result.get('returncode', 1) != 0:
            return {
                'success': False,
                'message': f"Failed to generate SSH key: {result.get('stderr', 'Unknown error')}"
            }
        
        # Read generated public key
        with open(SSH_KEY_PATH_PUB, 'r') as f:
            pubkey = f.read().strip()
        
        # Set proper permissions
        os.chmod(SSH_KEY_PATH, 0o600)
        os.chmod(SSH_KEY_PATH_PUB, 0o644)
        
        return {
            'success': True,
            'message': 'SSH key generated successfully',
            'pubkey': pubkey,
            'generated': True
        }
    
    except Exception as e:
        return {'success': False, 'message': str(e)}


def publish_device_ssh_key():
    """
    Publish device's SSH public key to Meeting server.
    Per Meeting API: PUT /api/devices/{device_key}/ssh-key
    
    Payload: {"pubkey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... comment"}
    
    Returns:
        dict: {success: bool, message: str}
    """
    config = load_meeting_config()
    
    if not config.get('device_key'):
        return {'success': False, 'message': 'Device key not configured'}
    
    # Ensure we have a key
    key_result = generate_device_ssh_key()
    if not key_result.get('success'):
        return key_result
    
    pubkey = key_result.get('pubkey')
    if not pubkey:
        return {'success': False, 'message': 'No public key available'}
    
    # Send to Meeting API
    endpoint = f"/api/devices/{config['device_key']}/ssh-key"
    data = {'pubkey': pubkey}
    
    result = meeting_api_request(endpoint, method='PUT', data=data)
    
    if result.get('success'):
        return {
            'success': True,
            'message': 'SSH key published to Meeting server',
            'pubkey': pubkey
        }
    else:
        return {
            'success': False,
            'message': f"Failed to publish SSH key: {result.get('error', 'Unknown error')}"
        }


def get_device_ssh_pubkey():
    """
    Get the device's SSH public key.
    
    Returns:
        dict: {success: bool, pubkey: str}
    """
    if not os.path.exists(SSH_KEY_PATH_PUB):
        # Try to generate if missing
        result = generate_device_ssh_key()
        return result
    
    try:
        with open(SSH_KEY_PATH_PUB, 'r') as f:
            pubkey = f.read().strip()
        return {'success': True, 'pubkey': pubkey}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def full_ssh_setup():
    """
    Perform complete SSH setup for Meeting integration:
    1. Generate device SSH key if missing
    2. Sync server hostkeys to known_hosts
    3. Publish device key to Meeting server
    
    This should be called during provisioning or periodically.
    
    Returns:
        dict: {success: bool, message: str, details: dict}
    """
    details = {}
    
    # Step 1: Generate device SSH key
    gen_result = generate_device_ssh_key()
    details['generate_key'] = gen_result
    if not gen_result.get('success'):
        return {
            'success': False,
            'message': f"Failed to generate SSH key: {gen_result.get('message')}",
            'details': details
        }
    
    # Step 2: Sync server hostkeys
    sync_result = sync_ssh_hostkey()
    details['sync_hostkey'] = sync_result
    # Non-fatal: continue even if hostkey sync fails
    
    # Step 3: Publish device key to server
    pub_result = publish_device_ssh_key()
    details['publish_key'] = pub_result
    if not pub_result.get('success'):
        return {
            'success': False,
            'message': f"Failed to publish SSH key: {pub_result.get('message')}",
            'details': details
        }
    
    return {
        'success': True,
        'message': 'SSH setup completed successfully',
        'details': details
    }

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
            'message': 'All fields are required'
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
                    'message': 'Credentials are valid'
                }
            else:
                return {
                    'success': True,
                    'valid': True,
                    'device': data,
                    'message': 'Credentials are valid'
                }
    
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {
                'success': True,
                'valid': False,
                'message': 'Invalid token code'
            }
        elif e.code == 404:
            return {
                'success': True,
                'valid': False,
                'message': 'Device key not found'
            }
        else:
            return {
                'success': False,
                'valid': False,
                'message': f'HTTP error {e.code}: {e.reason}'
            }
    
    except urllib.error.URLError as e:
        return {
            'success': False,
            'valid': False,
            'message': f'Connection error: {e.reason}'
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
            'message': 'All fields are required'
        }
    
    # First validate credentials
    validation = validate_credentials(api_url, device_key, token_code)
    if not validation.get('valid'):
        return {
            'success': False,
            'message': validation.get('message', 'Invalid credentials')
        }
    
    device = validation.get('device', {})
    
    # Check if device is authorized
    if not device.get('authorized', True):
        return {
            'success': False,
            'message': 'Device non autorisé. Contactez l\'administrateur Meeting.'
        }
    
    # Check token count
    token_count = device.get('token_count', 0)
    if token_count <= 0:
        return {
            'success': False,
            'message': 'Aucun token disponible. Contactez l\'administrateur Meeting.'
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
            
            # Perform SSH setup (per Meeting API integration guide)
            # This includes: generate device SSH key, sync hostkeys, publish key to server
            ssh_setup_result = full_ssh_setup()
            ssh_setup_success = ssh_setup_result.get('success', False)
            
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
                'ssh_setup': ssh_setup_success,
                'message': f'Device provisionné avec succès ! Token consommé, {tokens_left} restant(s).'
            }
    
    except urllib.error.HTTPError as e:
        error_body = ''
        try:
            error_body = e.read().decode('utf-8')
        except:
            pass
        return {
            'success': False,
            'message': f'Erreur lors de la consommation du token: HTTP {e.code}',
            'details': error_body
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Erreur de provisioning: {str(e)}'
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
    
    return {'success': True, 'message': 'Meeting service initialized'}

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
            'message': 'Code Master incorrect'
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
            'message': 'Configuration Meeting réinitialisée. Le hostname reste inchangé.'
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Erreur lors de la réinitialisation: {str(e)}'
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
    Check if debug mode is enabled via 'debug' service declaration in Meeting.
    
    Per Meeting API integration guide: services are ssh, http, vnc, scp, debug.
    The 'debug' service specifically enables advanced debugging features in the UI.
    
    Returns:
        bool: True if 'debug' service is declared in Meeting
    """
    # Only check for 'debug' service (vnc is a separate tunnel service)
    return is_service_declared('debug')


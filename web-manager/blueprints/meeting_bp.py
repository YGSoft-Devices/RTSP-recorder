# -*- coding: utf-8 -*-
"""
Meeting Blueprint - Meeting API integration routes
Version: 2.30.12

Conforms to Meeting API integration guide (docs/MEETING - integration.md):
- Heartbeat: POST /api/devices/{device_key}/online
- SSH hostkey sync: GET /api/ssh-hostkey  
- SSH key publication: PUT /api/devices/{device_key}/ssh-key
- Meeting SSH pubkey: GET /api/ssh/pubkey (install on device)
"""

from flask import Blueprint, request, jsonify

from services.meeting_service import (
    load_meeting_config, save_meeting_config, get_meeting_status,
    send_heartbeat, get_heartbeat_payload, get_meeting_device_info, request_tunnel,
    update_provision, get_device_availability,
    enable_meeting_service, disable_meeting_service,
    validate_credentials, provision_device, master_reset,
    init_meeting_service,
    # SSH key management
    sync_ssh_hostkey, generate_device_ssh_key, publish_device_ssh_key,
    get_device_ssh_pubkey, full_ssh_setup,
    get_meeting_ssh_pubkey, install_meeting_ssh_pubkey,
    get_ssh_keys_status, ensure_ssh_keys_configured,
    # Services
    get_declared_services,
    get_meeting_authorized_services
)

meeting_bp = Blueprint('meeting', __name__, url_prefix='/api/meeting')

# ============================================================================
# CONFIGURATION ROUTES
# ============================================================================

@meeting_bp.route('/config', methods=['GET'])
def get_config():
    """Get Meeting API configuration (without sensitive data)."""
    config = load_meeting_config()
    
    # Remove sensitive data
    safe_config = {
        'enabled': config.get('enabled', False),
        'api_url': config.get('api_url', ''),
        'device_key': config.get('device_key', ''),
        'heartbeat_interval': config.get('heartbeat_interval', 30),
        'auto_connect': config.get('auto_connect', True),
        'has_token': bool(config.get('token_code')),
        'provisioned': config.get('provisioned', False)
    }
    
    return jsonify({
        'success': True,
        'config': safe_config
    })

@meeting_bp.route('/config', methods=['POST', 'PUT'])
def set_config():
    """Update Meeting API configuration."""
    data = request.get_json(silent=True) or {}
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Configuration data required'
        }), 400
    
    # Load existing and merge
    config = load_meeting_config()
    
    for key in ['enabled', 'api_url', 'device_key', 'token_code', 'heartbeat_interval', 'auto_connect']:
        if key in data:
            config[key] = data[key]
    
    result = save_meeting_config(config)
    if result.get('success'):
        init_meeting_service()
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

# ============================================================================
# STATUS ROUTES
# ============================================================================

@meeting_bp.route('/status', methods=['GET'])
def get_status():
    """Get Meeting API connection status."""
    status = get_meeting_status()
    
    return jsonify({
        'success': True,
        'status': status,  # Wrapped for frontend compatibility
        **status  # Also spread for backward compatibility
    })

@meeting_bp.route('/device', methods=['GET'])
def get_device_info():
    """Get device information from Meeting API."""
    result = get_meeting_device_info()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/availability', methods=['GET'])
def get_availability():
    """Get device availability from Meeting API."""
    result = get_device_availability()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

# ============================================================================
# CONTROL ROUTES
# ============================================================================

@meeting_bp.route('/enable', methods=['POST'])
def enable():
    """Enable Meeting API integration."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Configuration required'
        }), 400
    
    required = ['api_url', 'device_key', 'token_code']
    for field in required:
        if field not in data:
            return jsonify({
                'success': False,
                'error': f'{field} required'
            }), 400
    
    result = enable_meeting_service(
        data['api_url'],
        data['device_key'],
        data['token_code'],
        data.get('heartbeat_interval', 30)
    )
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@meeting_bp.route('/disable', methods=['POST'])
def disable():
    """Disable Meeting API integration."""
    result = disable_meeting_service()
    
    return jsonify(result)

@meeting_bp.route('/heartbeat', methods=['POST'])
def manual_heartbeat():
    """Send a manual heartbeat."""
    result = send_heartbeat()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/heartbeat/preview', methods=['GET'])
def preview_heartbeat():
    """Preview heartbeat payload without sending it.
    
    Returns the exact payload that would be sent to Meeting API.
    Useful for debugging network field detection (ip_lan, ip_public, mac).
    """
    result = get_heartbeat_payload()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/heartbeat/debug', methods=['POST'])
def debug_heartbeat():
    """Send a heartbeat and return both the payload sent and the response.
    
    Returns:
        - payload: What was sent to Meeting API
        - response: What Meeting API returned
    """
    # First get the payload
    payload_result = get_heartbeat_payload()
    
    # Then send the heartbeat
    send_result = send_heartbeat()
    
    return jsonify({
        'success': send_result.get('success', False),
        'payload_sent': payload_result.get('payload', {}),
        'endpoint': payload_result.get('endpoint', ''),
        'api_url': payload_result.get('api_url', ''),
        'response': send_result
    })

# ============================================================================
# TUNNEL ROUTES
# ============================================================================

@meeting_bp.route('/tunnel', methods=['POST'])
def create_tunnel():
    """Request a tunnel from Meeting API."""
    data = request.get_json(silent=True) or {}
    
    tunnel_type = data.get('type', 'ssh')
    port = data.get('port', 22)
    
    result = request_tunnel(tunnel_type, port)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

# ============================================================================
# PROVISION ROUTES
# ============================================================================

@meeting_bp.route('/provision', methods=['GET'])
def get_provision():
    """Get current provision data."""
    # Get device info which includes provision data
    result = get_meeting_device_info()
    
    if result['success'] and result.get('data'):
        return jsonify({
            'success': True,
            'provision': result['data'].get('provision', {})
        })
    
    return jsonify({
        'success': False,
        'error': result.get('error', 'Could not get provision data')
    }), 400

@meeting_bp.route('/provision', methods=['POST', 'PUT'])
def do_provision():
    """Provision the device with Meeting API."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'message': 'Provision data required'
        }), 400
    
    api_url = data.get('api_url')
    device_key = data.get('device_key')
    token_code = data.get('token_code')
    
    if not api_url or not device_key or not token_code:
        return jsonify({
            'success': False,
            'message': 'api_url, device_key and token_code are required'
        }), 400
    
    result = provision_device(api_url, device_key, token_code)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/validate', methods=['POST'])
def validate():
    """Validate Meeting API credentials without saving."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'valid': False,
            'message': 'Credentials required'
        }), 400
    
    api_url = data.get('api_url')
    device_key = data.get('device_key')
    token_code = data.get('token_code')
    
    if not api_url or not device_key or not token_code:
        return jsonify({
            'success': False,
            'valid': False,
            'message': 'api_url, device_key and token_code are required'
        }), 400
    
    result = validate_credentials(api_url, device_key, token_code)
    
    return jsonify(result)

# ============================================================================
# MASTER RESET ROUTE
# ============================================================================

@meeting_bp.route('/master-reset', methods=['POST'])
def do_master_reset():
    """
    Reset Meeting configuration (requires master code).
    Clears device_key, token_code, and provisioned flag.
    """
    data = request.get_json(silent=True) or {}
    master_code = data.get('master_code', '')
    
    result = master_reset(master_code)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code
# ============================================================================
# SSH KEY MANAGEMENT ROUTES (per Meeting API integration guide)
# ============================================================================

@meeting_bp.route('/ssh/hostkey/sync', methods=['POST'])
def sync_hostkey():
    """
    Synchronize SSH hostkeys from Meeting server.
    GET /api/ssh-hostkey returns server public keys in ssh-keyscan format.
    Updates /root/.ssh/known_hosts atomically.
    """
    result = sync_ssh_hostkey()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/ssh/key', methods=['GET'])
def get_ssh_key():
    """Get device's SSH public key."""
    result = get_device_ssh_pubkey()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/ssh/key/generate', methods=['POST'])
def generate_ssh_key():
    """Generate device SSH key pair (ed25519) if not exists."""
    result = generate_device_ssh_key()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/ssh/key/publish', methods=['POST'])
def publish_ssh_key():
    """
    Publish device's SSH public key to Meeting server.
    PUT /api/devices/{device_key}/ssh-key
    """
    result = publish_device_ssh_key()
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@meeting_bp.route('/ssh/setup', methods=['POST'])
def ssh_setup():
    """
    Perform complete SSH setup for Meeting integration:
    1. Generate device SSH key if missing
    2. Sync server hostkeys to known_hosts
    3. Publish device key to Meeting server
    4. Install Meeting server pubkey to authorized_keys
    """
    result = full_ssh_setup()
    
    # Also install Meeting SSH pubkey
    if result.get('success'):
        install_result = install_meeting_ssh_pubkey()
        result['meeting_pubkey_installed'] = install_result.get('success', False)
        if not install_result.get('success'):
            result['meeting_pubkey_error'] = install_result.get('message', 'Unknown error')
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


@meeting_bp.route('/ssh/meeting-pubkey', methods=['GET'])
def get_meeting_pubkey():
    """
    Get Meeting server's SSH public key.
    """
    result = get_meeting_ssh_pubkey()
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


@meeting_bp.route('/ssh/meeting-pubkey/install', methods=['POST'])
def install_meeting_pubkey():
    """
    Install Meeting server's SSH public key to authorized_keys.
    This allows Meeting to SSH into this device via tunnel.
    Installs for both 'root' and 'device' users.
    """
    result = install_meeting_ssh_pubkey()
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


@meeting_bp.route('/ssh/keys/status', methods=['GET'])
def ssh_keys_status():
    """
    Get SSH keys status for Meeting integration.
    Returns whether device key exists, Meeting key is installed, etc.
    """
    result = get_ssh_keys_status()
    return jsonify({
        'success': True,
        **result
    })


@meeting_bp.route('/ssh/keys/ensure', methods=['POST'])
def ensure_ssh_keys():
    """
    Ensure SSH keys are properly configured for Meeting integration.
    This will:
    1. Generate device SSH key if missing
    2. Install Meeting pubkey in authorized_keys for 'device' user
    3. Publish device key to Meeting API
    
    Called automatically when tunnel agent starts, but can also be triggered manually.
    """
    result = ensure_ssh_keys_configured()
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


# ============================================================================
# SERVICES DECLARATION ROUTES
# ============================================================================

@meeting_bp.route('/services', methods=['GET'])
def get_services():
    """
    Get services status.
    
    Query params:
        source: 'local' (default) - services running locally on device
                'meeting' - services authorized by Meeting API admin
    
    Per Meeting API: services are ssh, http, vnc, scp, debug.
    """
    source = request.args.get('source', 'local')
    
    if source == 'meeting':
        # Get services authorized by Meeting API
        result = get_meeting_authorized_services()
        return jsonify(result)
    else:
        # Get local services status (running on device)
        services = get_declared_services()
        return jsonify({
            'success': True,
            'services': services
        })

# ============================================================================
# TUNNEL AGENT ROUTES
# ============================================================================

@meeting_bp.route('/tunnel/agent/status', methods=['GET'])
def tunnel_agent_status():
    """Get tunnel agent service status."""
    import subprocess
    
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'meeting-tunnel-agent'],
            capture_output=True, text=True, timeout=5
        )
        active = result.stdout.strip() == 'active'
        
        # Get enabled status
        result_enabled = subprocess.run(
            ['systemctl', 'is-enabled', 'meeting-tunnel-agent'],
            capture_output=True, text=True, timeout=5
        )
        enabled = result_enabled.stdout.strip() == 'enabled'
        
        return jsonify({
            'success': True,
            'status': {
                'active': active,
                'enabled': enabled,
                'state': result.stdout.strip()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@meeting_bp.route('/tunnel/agent/start', methods=['POST'])
def tunnel_agent_start():
    """Start the tunnel agent service (install if missing)."""
    import subprocess
    import os
    
    try:
        # Check if service file exists, if not install it
        service_file = '/etc/systemd/system/meeting-tunnel-agent.service'
        source_file = '/opt/rpi-cam-webmanager/setup/meeting-tunnel-agent.service'
        
        if not os.path.exists(service_file):
            # Copy service file and reload systemd
            if os.path.exists(source_file):
                subprocess.run(['sudo', 'cp', source_file, service_file], check=True, timeout=5)
                subprocess.run(['sudo', 'systemctl', 'daemon-reload'], check=True, timeout=5)
            else:
                return jsonify({
                    'success': False,
                    'error': f'Service file not found: {source_file}'
                }), 500
        
        subprocess.run(
            ['sudo', 'systemctl', 'start', 'meeting-tunnel-agent'],
            check=True, timeout=10
        )
        return jsonify({
            'success': True,
            'message': 'Tunnel agent démarré'
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'error': f'Échec du démarrage: {e}'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@meeting_bp.route('/tunnel/agent/stop', methods=['POST'])
def tunnel_agent_stop():
    """Stop the tunnel agent service."""
    import subprocess
    
    try:
        subprocess.run(
            ['sudo', 'systemctl', 'stop', 'meeting-tunnel-agent'],
            check=True, timeout=10
        )
        return jsonify({
            'success': True,
            'message': 'Tunnel agent arrêté'
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'error': f'Échec de l\'arrêt: {e}'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@meeting_bp.route('/tunnel/agent/enable', methods=['POST'])
def tunnel_agent_enable():
    """Enable the tunnel agent service at boot."""
    import subprocess
    
    try:
        subprocess.run(
            ['sudo', 'systemctl', 'enable', 'meeting-tunnel-agent'],
            check=True, timeout=10
        )
        return jsonify({
            'success': True,
            'message': 'Tunnel agent activé au démarrage'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@meeting_bp.route('/tunnel/agent/disable', methods=['POST'])
def tunnel_agent_disable():
    """Disable the tunnel agent service at boot."""
    import subprocess
    
    try:
        subprocess.run(
            ['sudo', 'systemctl', 'disable', 'meeting-tunnel-agent'],
            check=True, timeout=10
        )
        return jsonify({
            'success': True,
            'message': 'Tunnel agent désactivé au démarrage'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
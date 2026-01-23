# -*- coding: utf-8 -*-
"""
Meeting Blueprint - Meeting API integration routes
Version: 2.30.5
"""

from flask import Blueprint, request, jsonify

from services.meeting_service import (
    load_meeting_config, save_meeting_config, get_meeting_status,
    send_heartbeat, get_meeting_device_info, request_tunnel,
    update_provision, get_device_availability,
    enable_meeting_service, disable_meeting_service,
    validate_credentials, provision_device, master_reset,
    init_meeting_service
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

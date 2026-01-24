# -*- coding: utf-8 -*-
"""
ONVIF Blueprint - ONVIF server management routes
Version: 2.30.2
"""

import os
import json
import subprocess
from flask import Blueprint, request, jsonify

from services.platform_service import run_command
from services.config_service import control_service, get_service_status, load_config
from config import ONVIF_CONFIG_FILE, ONVIF_SERVICE_NAME
from services.i18n_service import t as i18n_t, resolve_request_lang

onvif_bp = Blueprint('onvif', __name__, url_prefix='/api/onvif')


def _t(key, **params):
    return i18n_t(key, lang=resolve_request_lang(request), params=params)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_onvif_service_running():
    """Check if ONVIF service is running."""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', ONVIF_SERVICE_NAME],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except:
        return False


def get_onvif_device_name_from_meeting():
    """Get ONVIF device name from Meeting API.
    
    Returns the product_serial from Meeting if provisioned,
    otherwise returns 'UNPROVISIONNED'.
    """
    try:
        from services.meeting_service import get_meeting_device_info
        
        result = get_meeting_device_info()
        if result.get('success') and result.get('data'):
            data = result['data']
            # Try product_serial first, then name, then device_name
            device_name = data.get('product_serial', '') or data.get('name', '') or data.get('device_name', '')
            if device_name:
                return device_name, True
        return 'UNPROVISIONNED', False
    except Exception as e:
        print(f"[ONVIF Status] Error getting device name from Meeting: {e}")
        return 'UNPROVISIONNED', False


# ============================================================================
# ONVIF SERVICE ROUTES
# ============================================================================

@onvif_bp.route('/status', methods=['GET'])
def get_onvif_status():
    """Get ONVIF service status and configuration."""
    from services.network_service import get_preferred_ip
    
    try:
        config = load_onvif_config()
        running = is_onvif_service_running()
        main_config = load_config()
        
        # Get real device name from Meeting API (same logic as onvif_server.py v1.5.0)
        device_name, name_from_meeting = get_onvif_device_name_from_meeting()
        
        # Don't expose password, just indicate if one is set
        safe_config = {
            'port': config.get('port', 8080),
            'name': device_name,
            'name_from_meeting': name_from_meeting,
            'username': config.get('username', ''),
            'has_password': bool(config.get('password', '')),
            'rtsp_port': config.get('rtsp_port', 8554),
            'rtsp_path': config.get('rtsp_path', '/stream')
        }
        
        # Video settings that ONVIF reports
        bitrate_str = main_config.get('H264_BITRATE_KBPS', '') or '0'
        video_settings = {
            'width': int(main_config.get('VIDEO_WIDTH', 640) or 640),
            'height': int(main_config.get('VIDEO_HEIGHT', 480) or 480),
            'fps': int(main_config.get('VIDEO_FPS', 15) or 15),
            'bitrate': int(bitrate_str) if bitrate_str else None
        }
        
        # Get preferred IP (respects interface priority: eth0 > wlan1 > wlan0)
        preferred_ip = get_preferred_ip()
        
        return jsonify({
            'success': True,
            'enabled': config.get('enabled', False),
            'running': running,
            'config': safe_config,
            'video_settings': video_settings,
            'preferred_ip': preferred_ip
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@onvif_bp.route('/start', methods=['POST'])
def start_onvif():
    """Start ONVIF server."""
    result = control_service('rpi-cam-onvif', 'start')
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@onvif_bp.route('/stop', methods=['POST'])
def stop_onvif():
    """Stop ONVIF server."""
    result = control_service('rpi-cam-onvif', 'stop')
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@onvif_bp.route('/restart', methods=['POST'])
def restart_onvif():
    """Restart ONVIF service."""
    try:
        config = load_onvif_config()
        
        if not config.get('enabled', False):
            return jsonify({'success': False, 'message': _t('ui.onvif.service_disabled')}), 400
        
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', ONVIF_SERVICE_NAME],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': _t('ui.onvif.restart_failed', error=result.stderr)
            }), 500
        
        return jsonify({'success': True, 'message': _t('ui.onvif.service_restarted')})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================================================
# ONVIF CONFIGURATION ROUTES
# ============================================================================

@onvif_bp.route('/config', methods=['GET'])
def get_config():
    """Get ONVIF configuration."""
    # Redirect to /status for consistent API
    return get_onvif_status()

@onvif_bp.route('/config', methods=['POST', 'PUT'])
def set_config():
    """Update ONVIF configuration."""
    try:
        data = request.get_json(silent=True) or {}
        current_config = load_onvif_config()
        main_config = load_config()
        
        rtsp_user = (main_config.get('RTSP_USER', '') or '').strip()
        rtsp_password = (main_config.get('RTSP_PASSWORD', '') or '').strip()

        username = current_config.get('username', '')
        password = current_config.get('password', '')
        rtsp_port = current_config.get('rtsp_port', 8554)
        rtsp_path = current_config.get('rtsp_path', '/stream')

        if 'username' in data:
            username = data.get('username', '')
        if 'password' in data and data.get('password'):
            password = data.get('password')
        if 'rtsp_port' in data:
            try:
                rtsp_port = int(data.get('rtsp_port', 8554))
            except (TypeError, ValueError):
                rtsp_port = current_config.get('rtsp_port', 8554)
        if 'rtsp_path' in data:
            raw_path = str(data.get('rtsp_path') or '').strip()
            if raw_path:
                rtsp_path = '/' + raw_path.lstrip('/')
            else:
                rtsp_path = current_config.get('rtsp_path', '/stream')

        # If RTSP credentials are set, keep ONVIF credentials shared with RTSP
        if rtsp_user and rtsp_password:
            username = rtsp_user
            password = rtsp_password
        
        # Update configuration
        # Note: 'name' is ignored - it comes from Meeting API (onvif_server.py v1.5.0)
        new_config = {
            'enabled': data.get('enabled', False),
            'port': int(data.get('port', 8080)),
            'username': username,
            'password': password,
            'rtsp_port': rtsp_port,
            'rtsp_path': rtsp_path
        }
        
        if not save_onvif_config(new_config):
            return jsonify({'success': False, 'message': _t('ui.config.save_failed')}), 500
        
        # Enable/disable service based on config
        if new_config['enabled']:
            # Start or restart service
            subprocess.run(['sudo', 'systemctl', 'enable', ONVIF_SERVICE_NAME], capture_output=True)
            subprocess.run(['sudo', 'systemctl', 'restart', ONVIF_SERVICE_NAME], capture_output=True)
        else:
            # Stop and disable service
            subprocess.run(['sudo', 'systemctl', 'stop', ONVIF_SERVICE_NAME], capture_output=True)
            subprocess.run(['sudo', 'systemctl', 'disable', ONVIF_SERVICE_NAME], capture_output=True)
        
        return jsonify({'success': True, 'message': _t('ui.onvif.saved')})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================================================
# ONVIF DISCOVERY ROUTES
# ============================================================================

@onvif_bp.route('/discovery', methods=['GET'])
def get_discovery_status():
    """Get ONVIF discovery status."""
    config = load_onvif_config()
    
    return jsonify({
        'success': True,
        'discovery_enabled': config.get('discovery_enabled', True),
        'discovery_scope': config.get('discovery_scope', 'onvif://www.onvif.org/type/video_encoder')
    })

@onvif_bp.route('/discovery', methods=['POST'])
def set_discovery():
    """Enable or disable ONVIF discovery."""
    data = request.get_json()
    
    if not data or 'enabled' not in data:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.enabled_required')
        }), 400
    
    config = load_onvif_config()
    config['discovery_enabled'] = data['enabled']
    
    if save_onvif_config(config):
        # Restart ONVIF service to apply changes if enabled
        if config.get('enabled', False):
            subprocess.run(['sudo', 'systemctl', 'restart', ONVIF_SERVICE_NAME], capture_output=True)
        return jsonify({'success': True, 'message': _t('ui.onvif.discovery_saved')})
    
    return jsonify({'success': False, 'message': _t('ui.config.save_failed')}), 500

# ============================================================================
# ONVIF AUTHENTICATION ROUTES
# ============================================================================

@onvif_bp.route('/auth', methods=['GET'])
def get_auth_status():
    """Get ONVIF authentication status."""
    config = load_onvif_config()
    
    return jsonify({
        'success': True,
        'auth_enabled': config.get('auth_enabled', False),
        'username': config.get('username', 'admin')
    })

@onvif_bp.route('/auth', methods=['POST', 'PUT'])
def set_auth():
    """Configure ONVIF authentication."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.auth_config_required')
        }), 400
    
    config = load_onvif_config()
    
    if 'enabled' in data:
        config['auth_enabled'] = data['enabled']
    
    if 'username' in data:
        config['username'] = data['username']
    
    if 'password' in data:
        config['password'] = data['password']
    
    if save_onvif_config(config):
        # Restart ONVIF service to apply changes if enabled
        if config.get('enabled', False):
            subprocess.run(['sudo', 'systemctl', 'restart', ONVIF_SERVICE_NAME], capture_output=True)
        return jsonify({'success': True, 'message': _t('ui.onvif.auth_saved')})
    
    return jsonify({'success': False, 'message': _t('ui.config.save_failed')}), 500

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_onvif_config():
    """Load ONVIF configuration from file."""
    default_config = {
        'enabled': False,
        'port': 8080,
        'rtsp_port': 8554,
        'rtsp_path': '/stream',
        'discovery_enabled': True,
        'discovery_scope': 'onvif://www.onvif.org/type/video_encoder',
        'auth_enabled': False,
        'username': 'admin',
        'password': '',
        'manufacturer': 'RPi-Cam',
        'model': 'WebManager',
        'firmware_version': '2.30.0'
    }
    
    if os.path.exists(ONVIF_CONFIG_FILE):
        try:
            with open(ONVIF_CONFIG_FILE, 'r') as f:
                file_config = json.load(f)
                default_config.update(file_config)
        except Exception as e:
            print(f"Error loading ONVIF config: {e}")
    
    return default_config

def save_onvif_config(config):
    """Save ONVIF configuration to file."""
    try:
        # Ensure directory exists
        config_dir = os.path.dirname(ONVIF_CONFIG_FILE)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, mode=0o755)
        
        # Merge with existing config
        existing = load_onvif_config()
        existing.update(config)
        
        with open(ONVIF_CONFIG_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
        
        # Secure the file (contains password)
        os.chmod(ONVIF_CONFIG_FILE, 0o600)
        
        return True
    
    except Exception as e:
        print(f"[ONVIF] Error saving config: {e}")
        return False

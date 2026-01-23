# -*- coding: utf-8 -*-
"""
Config Blueprint - Configuration and service management routes
Version: 2.30.1
"""

from flask import Blueprint, request, jsonify

from services.i18n_service import t as i18n_t, resolve_request_lang
from services.config_service import (
    load_config, save_config, get_config_metadata, validate_config,
    get_service_status, control_service, get_all_services_status,
    get_system_info, get_hostname, set_hostname, sync_recorder_service
)
from config import APP_VERSION, DEFAULT_CONFIG, CONFIG_METADATA

config_bp = Blueprint('config', __name__, url_prefix='/api')


def _t(key, **params):
    return i18n_t(key, lang=resolve_request_lang(request), params=params)

# ============================================================================
# CONFIGURATION ROUTES
# ============================================================================

@config_bp.route('/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    config = load_config()
    return jsonify({
        'success': True,
        'config': config,
        'version': APP_VERSION
    })

@config_bp.route('/config', methods=['POST', 'PUT'])
def update_config():
    """Update configuration."""
    try:
        data = request.get_json(silent=True) or {}
        
        if not data:
            return jsonify({'success': False, 'error': _t('ui.errors.no_data_provided')}), 400
        
        # Load current config and merge
        current = load_config()
        
        # Track if RECORD_ENABLE changed
        old_record_enable = current.get('RECORD_ENABLE', 'no')
        
        for key, value in data.items():
            if key in DEFAULT_CONFIG or key in current:
                meta = CONFIG_METADATA.get(key, {})
                if meta.get('type') == 'number' and (value is None or value == ''):
                    continue
                current[key] = value

        # CSI/libcamera: ignore USB-only VIDEO_FORMAT values
        camera_type = (current.get('CAMERA_TYPE') or 'auto').lower()
        video_format = current.get('VIDEO_FORMAT', 'auto')
        if camera_type in ['csi', 'libcamera'] and video_format not in ['auto', 'MJPG', 'YUYV', 'H264']:
            current['VIDEO_FORMAT'] = 'auto'
        
        # Validate
        validation = validate_config(current)
        if not validation['valid']:
            return jsonify({
                'success': False,
                'error': _t('ui.config.validation_failed'),
                'errors': validation['errors']
            }), 400
        
        # Save
        result = save_config(current)
        
        if result['success']:
            response_data = {
                'success': True,
                'message': _t('ui.config.saved'),
                'config': current
            }
            
            # Sync recorder service if RECORD_ENABLE changed or was set
            new_record_enable = current.get('RECORD_ENABLE', 'no')
            if 'RECORD_ENABLE' in data or old_record_enable != new_record_enable:
                sync_result = sync_recorder_service(current)
                response_data['recorder_sync'] = sync_result
                if sync_result.get('action') in ['started', 'stopped']:
                    response_data['message'] += _t('ui.config.recorder_action', action=sync_result['action'])
            
            return jsonify(response_data)
        else:
            return jsonify({
                'success': False,
                'error': result['message']
            }), 500
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@config_bp.route('/config/metadata', methods=['GET'])
def get_config_meta():
    """Get configuration metadata (field definitions, types, etc.)."""
    return jsonify({
        'success': True,
        'metadata': get_config_metadata(),
        'defaults': DEFAULT_CONFIG
    })

@config_bp.route('/config/reset', methods=['POST'])
def reset_config():
    """Reset configuration to defaults."""
    result = save_config(DEFAULT_CONFIG.copy())
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': _t('ui.config.reset_defaults'),
            'config': DEFAULT_CONFIG
        })
    else:
        return jsonify({
            'success': False,
            'error': result['message']
        }), 500

# ============================================================================
# SERVICE MANAGEMENT ROUTES
# ============================================================================

@config_bp.route('/service/status', methods=['GET'])
def get_main_service_status():
    """Get main RTSP service status."""
    status = get_service_status()
    return jsonify({
        'success': True,
        **status
    })

@config_bp.route('/service/status/<service_name>', methods=['GET'])
def get_specific_service_status(service_name):
    """Get status of a specific service."""
    status = get_service_status(service_name)
    return jsonify({
        'success': True,
        'service': service_name,
        **status
    })

@config_bp.route('/services', methods=['GET'])
def get_all_services():
    """Get status of all related services."""
    services = get_all_services_status()
    return jsonify({
        'success': True,
        'services': services
    })

@config_bp.route('/service/<service_name>/<action>', methods=['POST'])
def control_service_route(service_name, action):
    """Control a service (start, stop, restart, etc.)."""
    result = control_service(service_name, action)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@config_bp.route('/service/<action>', methods=['POST'])
def control_main_service(action):
    """Control the main RTSP service (legacy route for backward compatibility)."""
    from config import SERVICE_NAME
    result = control_service(SERVICE_NAME, action)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@config_bp.route('/service/restart', methods=['POST'])
def restart_main_service():
    """Restart the main RTSP service."""
    result = control_service(None, 'restart')  # None uses default service
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': _t('ui.services.restart_initiated')
        })
    else:
        return jsonify(result), 500

# ============================================================================
# SYSTEM INFORMATION ROUTES
# ============================================================================

@config_bp.route('/system/info', methods=['GET'])
def system_info():
    """Get system information."""
    info = get_system_info()
    return jsonify({
        'success': True,
        **info
    })

@config_bp.route('/system/hostname', methods=['GET'])
def get_system_hostname():
    """Get current hostname."""
    return jsonify({
        'success': True,
        'hostname': get_hostname()
    })

@config_bp.route('/system/hostname', methods=['POST', 'PUT'])
def set_system_hostname():
    """Set system hostname."""
    data = request.get_json(silent=True) or {}
    
    if not data or 'hostname' not in data:
        return jsonify({
            'success': False,
            'error': _t('ui.system.hostname_required')
        }), 400
    
    result = set_hostname(data['hostname'])
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@config_bp.route('/version', methods=['GET'])
def get_version():
    """Get application version."""
    return jsonify({
        'success': True,
        'version': APP_VERSION
    })

@config_bp.route('/status', methods=['GET'])
def get_overall_status():
    """Get overall system status summary."""
    system = get_system_info()
    service = get_service_status()
    
    # Extract status string for frontend compatibility
    status = service.get('status', 'unknown') if isinstance(service, dict) else 'unknown'
    
    return jsonify({
        'success': True,
        'version': APP_VERSION,
        'hostname': system.get('hostname', 'unknown'),
        'platform': system.get('platform', {}),
        'service': service,
        'status': status,  # Frontend compatibility
        'uptime': system.get('uptime', ''),
        'temperature': system.get('temperature'),
        'memory': system.get('memory', {}),
        'disk': system.get('disk', {})
    })

# -*- coding: utf-8 -*-
"""
Watchdog Blueprint - RTSP and WiFi failover watchdog routes
Version: 2.30.0
"""

import os
import time
import threading
from flask import Blueprint, request, jsonify

from services.watchdog_service import (
    check_rtsp_service_health,
    get_rtsp_watchdog_status,
    restart_rtsp_service,
    check_camera_available,
    enable_rtsp_watchdog,
    disable_rtsp_watchdog,
    check_network_connectivity
)
from services.camera_service import find_camera_device
from services.i18n_service import t as i18n_t, resolve_request_lang

watchdog_bp = Blueprint('watchdog', __name__, url_prefix='/api')


def _t(key, **params):
    return i18n_t(key, lang=resolve_request_lang(request), params=params)

# ============================================================================
# RTSP WATCHDOG ROUTES
# ============================================================================

@watchdog_bp.route('/rtsp/watchdog/status', methods=['GET'])
def rtsp_watchdog_status():
    """Get RTSP watchdog status including camera health."""
    status = get_rtsp_watchdog_status()
    health = check_rtsp_service_health()
    camera = find_camera_device()
    
    return jsonify({
        'success': True,
        'watchdog': {
            'running': status.get('running', False),
            'enabled': status.get('enabled', False),
            'last_check': status.get('last_check'),
            'last_healthy': status.get('last_healthy'),
            'restart_count': status.get('restart_count', 0),
            'last_restart': status.get('last_restart')
        },
        'health': {
            'healthy': health.get('overall') == 'healthy',
            'reason': health.get('message', ''),
            'camera_device': camera
        }
    })

@watchdog_bp.route('/rtsp/watchdog', methods=['POST'])
def rtsp_watchdog_control():
    """Control RTSP watchdog."""
    try:
        data = request.get_json(silent=True) or {}
        action = data.get('action', '')
        
        if action == 'start':
            result = enable_rtsp_watchdog()
            return jsonify({
                'success': True,
                'message': _t('ui.watchdog.rtsp.started')
            })
        elif action == 'stop':
            result = disable_rtsp_watchdog()
            return jsonify({
                'success': True,
                'message': _t('ui.watchdog.rtsp.stopped')
            })
        elif action == 'restart_service':
            result = restart_rtsp_service("Manual restart requested")
            return jsonify({
                'success': result.get('success', False),
                'message': result.get('message', _t('ui.watchdog.rtsp.service_restarted'))
            })
        else:
            return jsonify({
                'success': False,
                'message': _t('ui.watchdog.rtsp.invalid_action')
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# WIFI FAILOVER WATCHDOG ROUTES  
# ============================================================================

@watchdog_bp.route('/wifi/failover/watchdog', methods=['GET'])
def wifi_failover_watchdog_status():
    """Get WiFi failover watchdog status."""
    # Import dynamically to avoid circular imports
    from services.watchdog_service import watchdog_state
    
    with watchdog_state['lock']:
        running = watchdog_state['wifi_failover'].get('running', False)
        last_check = watchdog_state['wifi_failover'].get('last_check')
        current_state = watchdog_state['wifi_failover'].get('current_state', 'unknown')
    
    return jsonify({
        'success': True,
        'running': running,
        'last_check': last_check,
        'current_state': current_state
    })

@watchdog_bp.route('/wifi/failover/watchdog', methods=['POST'])
def wifi_failover_watchdog_control():
    """Start or stop the WiFi failover watchdog."""
    try:
        data = request.get_json(silent=True) or {}
        action = data.get('action', '')
        
        from services.watchdog_service import watchdog_state
        
        if action == 'start':
            with watchdog_state['lock']:
                watchdog_state['wifi_failover']['enabled'] = True
                watchdog_state['wifi_failover']['running'] = True
            return jsonify({
                'success': True,
                'message': _t('ui.watchdog.wifi.started')
            })
        elif action == 'stop':
            with watchdog_state['lock']:
                watchdog_state['wifi_failover']['enabled'] = False
                watchdog_state['wifi_failover']['running'] = False
            return jsonify({
                'success': True,
                'message': _t('ui.watchdog.wifi.stopped')
            })
        else:
            return jsonify({
                'success': False,
                'message': _t('ui.watchdog.wifi.invalid_action')
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

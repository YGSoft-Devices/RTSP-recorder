# -*- coding: utf-8 -*-
"""
Power Blueprint - LED, GPU, HDMI, and power management routes
Version: 2.30.4
"""

from flask import Blueprint, request, jsonify

from services.power_service import (
    get_led_status, set_led_state, configure_leds_boot,
    get_led_boot_config, save_led_boot_config,
    get_gpu_mem, set_gpu_mem,
    get_hdmi_status, configure_hdmi,
    get_power_status, configure_power_boot,
    reboot_system, shutdown_system,
    get_full_power_status, get_boot_power_config, get_all_services_status,
    set_service_state, configure_boot_power_settings
)

power_bp = Blueprint('power', __name__, url_prefix='/api')

# ============================================================================
# LED ROUTES
# ============================================================================

@power_bp.route('/leds', methods=['GET'])
def get_leds():
    """Get status of all LEDs."""
    leds = get_led_status()
    return jsonify({
        'success': True,
        'leds': leds
    })

@power_bp.route('/leds/set', methods=['POST'])
def set_led():
    """API endpoint to set LED state."""
    try:
        data = request.get_json()
        led = data.get('led', '')  # 'pwr' or 'act'
        enabled = data.get('enabled', True)
        trigger = data.get('trigger', None)
        persist = data.get('persist', True)  # Default to True for persistence
        
        if led not in ['pwr', 'act']:
            return jsonify({'success': False, 'message': 'Invalid LED'}), 400
        
        # Set immediate state
        success, message = set_led_state(led, enabled, trigger)
        
        if persist and success:
            # Get current boot config to preserve the other LED's setting
            boot_config = get_led_boot_config()
            pwr_enabled = enabled if led == 'pwr' else boot_config.get('pwr_enabled', True)
            act_enabled = enabled if led == 'act' else boot_config.get('act_enabled', True)
            
            boot_success, boot_msg = configure_leds_boot(pwr_enabled, act_enabled)
            if boot_success:
                message += " - Configuration persistante au redémarrage activée"
            else:
                message += f" - Attention: persistance échouée ({boot_msg})"
        
        return jsonify({
            'success': success, 
            'message': message,
            'persisted': persist,
            'reboot_required': persist
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@power_bp.route('/leds/boot-config', methods=['GET'])
def leds_boot_config():
    """API endpoint to get LED boot configuration."""
    from config import BOOT_CONFIG_FILE
    boot_config = get_led_boot_config()
    return jsonify({
        'success': True, 
        'boot_config': boot_config,
        'config_file': BOOT_CONFIG_FILE
    })

# ============================================================================
# GPU ROUTES
# ============================================================================

@power_bp.route('/gpu', methods=['GET'])
def get_gpu():
    """Get GPU memory allocation."""
    gpu_info = get_gpu_mem()
    
    return jsonify({
        'success': True,
        **gpu_info
    })

@power_bp.route('/gpu', methods=['POST', 'PUT'])
def set_gpu():
    """Set GPU memory allocation."""
    data = request.get_json()
    
    if not data or 'memory' not in data:
        return jsonify({
            'success': False,
            'error': 'memory value required (16, 32, 64, 128, 256, or 512)'
        }), 400
    
    result = set_gpu_mem(data['memory'])
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

# ============================================================================
# HDMI ROUTES
# ============================================================================

@power_bp.route('/hdmi', methods=['GET'])
def get_hdmi():
    """Get HDMI status."""
    status = get_hdmi_status()
    
    return jsonify({
        'success': True,
        **status
    })

@power_bp.route('/hdmi', methods=['POST', 'PUT'])
def set_hdmi():
    """Enable or disable HDMI output."""
    data = request.get_json()
    
    if not data or 'enabled' not in data:
        return jsonify({
            'success': False,
            'error': 'enabled (true/false) required'
        }), 400
    
    result = configure_hdmi(data['enabled'])
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

# ============================================================================
# POWER STATUS ROUTES
# ============================================================================

@power_bp.route('/status', methods=['GET'])
def power_status():
    """Get power-related status information."""
    status = get_power_status()
    
    return jsonify({
        'success': True,
        **status
    })

@power_bp.route('/config', methods=['POST', 'PUT'])
def power_config():
    """Configure power-related boot settings."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Power configuration required'
        }), 400
    
    result = configure_power_boot(data)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

# ============================================================================
# SYSTEM CONTROL ROUTES
# ============================================================================

@power_bp.route('/reboot', methods=['POST'])
def reboot():
    """Reboot the system."""
    data = request.get_json(silent=True) or {}
    delay = data.get('delay', 0)
    
    result = reboot_system(delay)
    
    return jsonify(result)

@power_bp.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the system."""
    data = request.get_json(silent=True) or {}
    delay = data.get('delay', 0)
    
    result = shutdown_system(delay)
    
    return jsonify(result)

# ============================================================================
# COMBINED STATUS ROUTE
# ============================================================================

@power_bp.route('', methods=['GET'])
def all_power_info():
    """Get all power-related information."""
    return jsonify({
        'success': True,
        'leds': get_led_status(),
        'gpu': get_gpu_mem(),
        'hdmi': get_hdmi_status(),
        'power': get_power_status()
    })

# ============================================================================
# POWER STATUS AND BOOT CONFIG ROUTES
# ============================================================================

@power_bp.route('/power/status', methods=['GET'])
def api_full_power_status():
    """Get comprehensive power status including bluetooth, HDMI, audio, savings estimate.
    
    Returns structure expected by frontend:
    {
        success: true,
        current: { estimated_savings_ma: int, ... },
        boot_config: { bluetooth_enabled, hdmi_enabled, audio_enabled, wifi_enabled, ... }
    }
    """
    status = get_full_power_status()
    boot_config = get_boot_power_config()
    
    # Build current status from the status dict
    current = {
        'estimated_savings_ma': status.get('estimated_savings_ma', 0),
        'cpu_freq_mhz': status.get('cpu_freq', {}).get('current'),
        'bluetooth_enabled': status.get('bluetooth', {}).get('enabled'),
        'hdmi_enabled': status.get('hdmi', {}).get('enabled'),
        'audio_enabled': status.get('audio', {}).get('enabled')
    }
    
    return jsonify({
        'success': True,
        'current': current,
        'boot_config': boot_config
    })

@power_bp.route('/power/boot-config', methods=['GET'])
def api_power_boot_config():
    """Get boot power configuration and services status."""
    boot_config = get_boot_power_config()
    services_status = get_all_services_status()
    
    return jsonify({
        'success': True,
        'boot_config': boot_config,
        'services': services_status
    })

@power_bp.route('/power/apply-all', methods=['POST'])
def api_power_apply_all():
    """API endpoint to apply all power settings at once."""
    try:
        data = request.get_json()
        
        # Get all settings from request
        led_pwr = data.get('led_pwr', True)
        led_act = data.get('led_act', True)
        led_camera_csi = data.get('led_camera_csi', True)
        bluetooth = data.get('bluetooth', True)
        wifi = data.get('wifi', True)
        hdmi = data.get('hdmi', True)
        audio = data.get('audio', True)
        
        # Service settings
        service_modemmanager = data.get('service_modemmanager', True)
        service_avahi = data.get('service_avahi', True)
        service_cloudinit = data.get('service_cloudinit', True)
        service_serial = data.get('service_serial', True)
        service_tty1 = data.get('service_tty1', True)
        service_udisks2 = data.get('service_udisks2', True)
        
        errors = []
        
        # Apply all settings to boot config
        success, message = configure_boot_power_settings(
            bluetooth_enabled=bluetooth,
            hdmi_enabled=hdmi,
            audio_enabled=audio,
            wifi_enabled=wifi,
            pwr_led_enabled=led_pwr,
            act_led_enabled=led_act,
            camera_led_csi_enabled=led_camera_csi
        )
        
        if not success:
            errors.append(f"Boot config: {message}")
        
        # Apply service settings
        service_settings = [
            ('modemmanager', service_modemmanager),
            ('avahi', service_avahi),
            ('cloudinit', service_cloudinit),
            ('serial', service_serial),
            ('tty1', service_tty1),
            ('udisks2', service_udisks2)
        ]
        
        for service_key, enabled in service_settings:
            svc_success, svc_message = set_service_state(service_key, enabled)
            if not svc_success:
                errors.append(f"{service_key}: {svc_message}")
        
        # Calculate estimated savings
        savings = 0
        if not bluetooth:
            savings += 20
        if not wifi:
            savings += 40
        if not hdmi:
            savings += 40
        if not audio:
            savings += 10
        if not led_pwr:
            savings += 5
        if not led_act:
            savings += 3
        if not led_camera_csi:
            savings += 2
        # Service savings
        if not service_modemmanager:
            savings += 15
        if not service_avahi:
            savings += 5
        if not service_serial:
            savings += 2
        if not service_tty1:
            savings += 2
        if not service_udisks2:
            savings += 5
        
        if errors:
            return jsonify({
                'success': False,
                'message': 'Certains paramètres ont échoué: ' + '; '.join(errors),
                'partial_errors': errors,
                'estimated_savings_ma': savings
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'Tous les paramètres ont été enregistrés. Redémarrage requis pour les changements hardware.',
            'estimated_savings_ma': savings,
            'reboot_required': True
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

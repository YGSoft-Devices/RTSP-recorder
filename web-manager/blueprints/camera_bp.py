# -*- coding: utf-8 -*-
"""
Camera Blueprint - Camera controls and profiles routes
Version: 2.30.12
"""

import os
from flask import Blueprint, request, jsonify

from services.camera_service import (
    find_camera_device, get_camera_info,
    get_camera_controls, get_all_camera_controls,
    set_camera_control, reset_camera_control,
    auto_camera_controls, focus_oneshot,
    get_camera_autofocus_status, set_camera_autofocus, set_camera_focus,
    get_camera_profiles, create_camera_profile,
    delete_camera_profile, apply_camera_profile,
    capture_camera_profile,
    get_scheduler_state, set_scheduler_enabled,
    add_schedule, remove_schedule,
    get_camera_formats, detect_camera_type,
    get_hw_encoder_capabilities,
    get_active_profile_by_schedule, set_current_profile
)
from services.csi_camera_service import (
    is_picamera2_available,
    get_csi_camera_controls,
    set_csi_camera_control,
    get_csi_camera_info,
    save_csi_tuning_to_config,
    load_csi_tuning_from_config
)
from services.config_service import load_config
from services.i18n_service import t as i18n_t, resolve_request_lang

camera_bp = Blueprint('camera', __name__, url_prefix='/api/camera')


def _t(key, **params):
    return i18n_t(key, lang=resolve_request_lang(request), params=params)

# ============================================================================
# CAMERA DEVICE ROUTES
# ============================================================================

@camera_bp.route('/status', methods=['GET'])
def get_camera_status():
    """Get camera device status."""
    device = find_camera_device()
    
    if device:
        info = get_camera_info(device)
        return jsonify({
            'success': True,
            'available': True,
            'device': device,
            **info
        })
    else:
        return jsonify({
            'success': True,
            'available': False,
            'message': _t('ui.camera.no_camera_found')
        })

@camera_bp.route('/info', methods=['GET'])
def camera_info():
    """Get detailed camera information."""
    device = request.args.get('device')
    info = get_camera_info(device)
    
    if 'error' in info:
        return jsonify({
            'success': False,
            'error': info['error']
        }), 404
    
    return jsonify({
        'success': True,
        **info
    })

# ============================================================================
# CAMERA CONTROLS ROUTES
# ============================================================================

@camera_bp.route('/controls', methods=['GET'])
def list_controls():
    """Get all camera controls with current values."""
    device = request.args.get('device')
    controls = get_camera_controls(device)
    
    return jsonify({
        'success': True,
        'controls': controls,
        'count': len(controls)
    })

@camera_bp.route('/all-controls', methods=['GET'])
def all_controls():
    """Get all camera controls grouped by category."""
    device = request.args.get('device')
    result = get_all_camera_controls(device)
    
    # result is {controls: {...}, grouped: {...}, categories: [...]}
    # Return flat structure for frontend compatibility
    return jsonify({
        'success': True,
        'controls': result.get('controls', {}),
        'grouped': result.get('grouped', {}),
        'categories': result.get('categories', []),
        'count': len(result.get('controls', {}))
    })

@camera_bp.route('/control/<control_name>', methods=['GET'])
def get_control(control_name):
    """Get a specific control value."""
    device = request.args.get('device')
    controls = get_camera_controls(device)
    
    control = next((c for c in controls if c['name'] == control_name), None)
    
    if control:
        return jsonify({
            'success': True,
            **control
        })
    else:
        return jsonify({
            'success': False,
            'error': _t('ui.camera.control_not_found', name=control_name)
        }), 404

@camera_bp.route('/control', methods=['POST'])
def set_control_generic():
    """Set any camera control (control name in body)."""
    try:
        data = request.get_json(silent=True) or {}
        device = data.get('device', '/dev/video0')
        control = data.get('control', '')
        value = data.get('value', 0)
        
        if not control:
            return jsonify({'success': False, 'message': _t('ui.camera.control_name_required')}), 400
        
        result = set_camera_control(control, value, device)
        return jsonify({
            'success': result['success'],
            'message': result['message'],
            'control': control,
            'value': value
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@camera_bp.route('/control/<control_name>', methods=['POST', 'PUT'])
def set_control(control_name):
    """Set a camera control value."""
    data = request.get_json()
    
    if not data or 'value' not in data:
        return jsonify({
            'success': False,
            'error': _t('ui.camera.value_required')
        }), 400
    
    device = data.get('device')
    value = data['value']
    
    result = set_camera_control(control_name, value, device)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@camera_bp.route('/control/<control_name>/reset', methods=['POST'])
def reset_control(control_name):
    """Reset a control to its default value."""
    device = request.args.get('device')
    result = reset_camera_control(control_name, device)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@camera_bp.route('/controls/set-multiple', methods=['POST'])
def set_multiple_controls():
    """Set multiple camera controls at once."""
    try:
        data = request.get_json(silent=True) or {}
        device = data.get('device', '/dev/video0')
        controls = data.get('controls', {})
        
        results = []
        for name, value in controls.items():
            result = set_camera_control(name, value, device)
            results.append({
                'control': name,
                'value': value,
                'success': result['success'],
                'message': result['message']
            })
        
        failed = [r for r in results if not r['success']]
        return jsonify({
            'success': len(failed) == 0,
            'results': results,
            'errors': len(failed)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@camera_bp.route('/controls/auto', methods=['POST'])
def enable_auto_controls():
    """Enable auto controls (focus, exposure, white balance)."""
    device = request.args.get('device')
    result = auto_camera_controls(device)
    
    return jsonify(result)

@camera_bp.route('/oneshot-focus', methods=['POST'])
def oneshot_focus():
    """Trigger one-shot autofocus."""
    device = request.args.get('device')
    result = focus_oneshot(device)
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

# ============================================================================
# AUTOFOCUS AND FOCUS ROUTES
# ============================================================================

@camera_bp.route('/autofocus', methods=['GET'])
def get_autofocus():
    """Get autofocus status."""
    device = request.args.get('device', '/dev/video0')
    status = get_camera_autofocus_status(device)
    return jsonify({'success': True, 'autofocus': status})


@camera_bp.route('/autofocus', methods=['POST'])
def set_autofocus():
    """Set autofocus state (with persistence)."""
    try:
        data = request.get_json(silent=True) or {}
        device = data.get('device', '/dev/video0')
        enabled = data.get('enabled', True)
        persist = data.get('persist', True)  # Save to config by default
        
        success, message = set_camera_autofocus(device, enabled, persist=persist)
        return jsonify({
            'success': success,
            'message': message,
            'enabled': enabled,
            'persisted': persist and success
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@camera_bp.route('/focus', methods=['POST'])
def set_focus():
    """Set manual focus value."""
    try:
        data = request.get_json(silent=True) or {}
        device = data.get('device', '/dev/video0')
        value = data.get('value', 30)
        
        # First disable autofocus
        set_camera_autofocus(device, False)
        
        # Then set manual focus
        success, message = set_camera_focus(device, value)
        return jsonify({
            'success': success,
            'message': message,
            'value': value
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================================================
# CAMERA PROFILES ROUTES
# ============================================================================

@camera_bp.route('/profiles', methods=['GET'])
def list_profiles():
    """Get all camera profiles with scheduler status."""
    profiles_data = get_camera_profiles()
    
    # Get scheduler state
    scheduler_state = get_scheduler_state()
    
    # Check if scheduler enabled from config
    config = load_config()
    scheduler_enabled = config.get('CAMERA_PROFILES_ENABLED', 'no') == 'yes'
    active_profile = get_active_profile_by_schedule(profiles_data.get('profiles', {}))
    
    # The scheduler is "running" if it's enabled and has a current schedule active
    scheduler_running = scheduler_enabled and active_profile is not None
    
    return jsonify({
        'success': True,
        'profiles': profiles_data['profiles'],
        'current_profile': profiles_data['current_profile'],
        'active_profile': scheduler_state.get('current_schedule'),
        'scheduler_active_profile': active_profile,
        'scheduler_enabled': scheduler_enabled,
        'scheduler_running': scheduler_running,
        'last_profile_change': scheduler_state.get('last_check')
    })

@camera_bp.route('/profiles/<name>', methods=['GET'])
def get_profile(name):
    """Get a specific profile."""
    profiles_data = get_camera_profiles()
    
    if name in profiles_data['profiles']:
        return jsonify({
            'success': True,
            'name': name,
            'profile': profiles_data['profiles'][name]
        })
    else:
        return jsonify({
            'success': False,
            'error': _t('ui.camera.profile.not_found_named', profile=name)
        }), 404

@camera_bp.route('/profiles/<name>', methods=['PUT', 'POST'])
def create_or_update_profile(name):
    """Create or update a camera profile."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': _t('ui.camera.profile.data_required')
        }), 400
    
    # Extract all profile fields
    profile_data = {
        'controls': data.get('controls', {}),
        'description': data.get('description', ''),
        'display_name': data.get('name', name),  # Display name from form
        'enabled': data.get('enabled', False),
        'schedule': data.get('schedule', {'start': '', 'end': ''})
    }
    
    result = create_camera_profile(name, profile_data)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@camera_bp.route('/profiles/<name>', methods=['DELETE'])
def delete_profile(name):
    """Delete a camera profile."""
    result = delete_camera_profile(name)
    
    status_code = 200 if result['success'] else 404
    return jsonify(result), status_code

@camera_bp.route('/profiles/<name>/apply', methods=['POST'])
def apply_profile(name):
    """Apply a camera profile."""
    data = request.get_json(silent=True) or {}
    device = data.get('device') or request.args.get('device')
    
    # Detect camera type to route to correct handler
    cam_type = detect_camera_type()
    
    if cam_type['type'] == 'libcamera':
        # Apply profile to CSI camera via IPC
        profiles_data = get_camera_profiles()
        profile = profiles_data.get('profiles', {}).get(name)
        if not profile:
            return jsonify({'success': False, 'message': _t('ui.camera.profile.not_found_named', profile=name)}), 400
        
        controls = profile.get('controls', {})
        if not controls:
            return jsonify({'success': False, 'message': _t('ui.camera.profile.controls_missing')}), 400
        
        # Apply each control via the IPC API
        applied = 0
        failed = 0
        skipped = 0
        errors = []

        # If AE/AWB are enabled, avoid forcing manual values
        ae_enabled = controls.get('AeEnable') is True
        awb_enabled = controls.get('AwbEnable') is True
        filtered_controls = {}
        for ctrl_name, ctrl_value in controls.items():
            if ae_enabled and ctrl_name in ['ExposureTime', 'AnalogueGain', 'ExposureTimeMode', 'AnalogueGainMode', 'FrameDurationLimits']:
                continue
            if awb_enabled and ctrl_name in ['ColourGains', 'ColourTemperature']:
                continue
            filtered_controls[ctrl_name] = ctrl_value

        for ctrl_name, ctrl_value in filtered_controls.items():
            if ctrl_value is None:
                skipped += 1
                continue
            result = set_csi_camera_control(ctrl_name, ctrl_value)
            if result.get('success'):
                applied += 1
            else:
                failed += 1
                errors.append(f"{ctrl_name}: {result.get('message', _t('ui.errors.unknown_error'))}")
        
        if failed > 0:
            message = f"Applied {applied} controls, {failed} failed, {skipped} skipped"
        else:
            message = _t('ui.camera.profile.applied_status', profile=name, applied=applied, skipped=skipped)

        if failed == 0:
            set_current_profile(name)
        return jsonify({
            'success': failed == 0,
            'message': message,
            'applied': applied,
            'failed': failed,
            'skipped': skipped,
            'errors': errors if failed > 0 else []
        }), (200 if failed == 0 else 400)
    else:
        # Use USB camera controls
        result = apply_camera_profile(name, device)
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

@camera_bp.route('/profiles/<name>/capture', methods=['POST'])
def capture_profile(name):
    """Capture current camera settings as a new profile."""
    data = request.get_json(silent=True) or {}
    description = data.get('description')
    
    # Detect camera type to route to correct handler
    cam_type = detect_camera_type()
    
    if cam_type['type'] == 'libcamera':
        # Use CSI camera controls
        csi_response = get_csi_camera_controls()
        if not csi_response or not csi_response.get('success'):
            return jsonify({'success': False, 'message': _t('ui.camera.csi_controls_read_error', error=csi_response.get('error', _t('ui.status.unknown')))}), 400
        
        controls_dict = csi_response.get('controls', {})
        if not controls_dict:
            return jsonify({'success': False, 'message': _t('ui.camera.csi_controls_none')}), 400
        
        profile_controls = {}
        for ctrl_name, ctrl_data in controls_dict.items():
            if not isinstance(ctrl_data, dict):
                continue
            if ctrl_data.get('read_only'):
                continue
            profile_controls[ctrl_name] = ctrl_data.get('value')
        
        profile_data = {
            'controls': profile_controls
        }
        if description is not None:
            profile_data['description'] = description
        result = create_camera_profile(name, profile_data)
        if result['success']:
            return jsonify({
                'success': True,
                'message': _t('ui.camera.profile.captured_status', profile=name, count=len(profile_controls)),
                'profile': {
                    'name': name,
                    'controls': profile_controls,
                    'description': description
                }
            }), 200
        return jsonify(result), 400
    else:
        # Use USB camera controls
        device = data.get('device')
        result = capture_camera_profile(name, description, device)
        status_code = 200 if result['success'] else 400
        return jsonify(result), status_code

@camera_bp.route('/profiles/<name>/ghost-fix', methods=['POST'])
def ghost_fix_profile(name):
    """Apply ghost-fix controls to a profile and save them."""
    profiles_data = get_camera_profiles()
    profile = profiles_data.get('profiles', {}).get(name)
    if not profile:
        return jsonify({'success': False, 'message': _t('ui.camera.profile.not_found_named', profile=name)}), 404

    cam_type = detect_camera_type()
    if cam_type['type'] != 'libcamera':
        return jsonify({'success': False, 'message': _t('ui.camera.ghost_fix.csi_only')}), 400

    csi_response = get_csi_camera_controls()
    if not csi_response or not csi_response.get('success'):
        return jsonify({'success': False, 'message': _t('ui.camera.csi_controls_read_error_generic')}), 400

    controls_meta = csi_response.get('controls', {})
    current_controls = profile.get('controls', {}) or {}
    updated_controls = current_controls.copy()
    ghost_fix_controls = {}

    if 'AeEnable' in controls_meta or 'AeEnable' in current_controls:
        ghost_fix_controls['AeEnable'] = False
    if 'AwbEnable' in controls_meta or 'AwbEnable' in current_controls:
        ghost_fix_controls['AwbEnable'] = False

    if 'Brightness' in controls_meta or 'Brightness' in current_controls:
        brightness_ctrl = controls_meta.get('Brightness', {})
        min_val = brightness_ctrl.get('min')
        max_val = brightness_ctrl.get('max')
        if isinstance(min_val, (int, float)) and isinstance(max_val, (int, float)):
            brightness_value = (min_val + max_val) / 2
        else:
            existing_value = current_controls.get('Brightness')
            brightness_value = 0.0 if isinstance(existing_value, (int, float)) and abs(existing_value) <= 2 else 128
        ghost_fix_controls['Brightness'] = brightness_value

    updated_controls.update(ghost_fix_controls)
    result = create_camera_profile(name, {'controls': updated_controls})
    if not result.get('success'):
        return jsonify({'success': False, 'message': result.get('message', _t('ui.camera.profile.save_error'))}), 500

    applied = 0
    failed = 0
    errors = []
    for ctrl_name, ctrl_value in ghost_fix_controls.items():
        if ctrl_value is None:
            continue
        res = set_csi_camera_control(ctrl_name, ctrl_value)
        if res.get('success'):
            applied += 1
        else:
            failed += 1
            errors.append(f"{ctrl_name}: {res.get('message', _t('ui.errors.unknown_error'))}")

    return jsonify({
        'success': failed == 0,
        'message': _t('ui.camera.ghost_fix.applied_status', applied=applied, failed=failed),
        'applied': applied,
        'failed': failed,
        'controls': ghost_fix_controls,
        'errors': errors if failed > 0 else []
    }), (200 if failed == 0 else 400)

# ============================================================================
# PROFILE SCHEDULER ROUTES
# ============================================================================

@camera_bp.route('/scheduler', methods=['GET'])
def get_scheduler():
    """Get profile scheduler status and schedules."""
    state = get_scheduler_state()
    return jsonify({
        'success': True,
        **state
    })

@camera_bp.route('/scheduler/enable', methods=['POST'])
def enable_scheduler():
    """Enable the profile scheduler."""
    result = set_scheduler_enabled(True)
    return jsonify(result)

@camera_bp.route('/scheduler/disable', methods=['POST'])
def disable_scheduler():
    """Disable the profile scheduler."""
    result = set_scheduler_enabled(False)
    return jsonify(result)

# Routes alternatives pour compatibilité avec le frontend
@camera_bp.route('/profiles/scheduler/start', methods=['POST'])
def start_profiles_scheduler():
    """Start the profile scheduler (alias for enable)."""
    result = set_scheduler_enabled(True)
    return jsonify(result)

@camera_bp.route('/profiles/scheduler/stop', methods=['POST'])
def stop_profiles_scheduler():
    """Stop the profile scheduler (alias for disable)."""
    result = set_scheduler_enabled(False)
    return jsonify(result)

@camera_bp.route('/profiles/scheduler/status', methods=['GET'])
def get_profiles_scheduler_status():
    """Get scheduler status."""
    state = get_scheduler_state()
    config = load_config()
    scheduler_enabled = config.get('CAMERA_PROFILES_ENABLED', 'no') == 'yes'
    
    return jsonify({
        'success': True,
        'enabled': scheduler_enabled,
        'running': state.get('running', False),
        'current_schedule': state.get('current_schedule'),
        'last_check': state.get('last_check')
    })

@camera_bp.route('/scheduler/schedule', methods=['POST'])
def add_scheduler_schedule():
    """Add a scheduled profile activation."""
    data = request.get_json()
    
    if not data or 'profile' not in data or 'time_start' not in data:
        return jsonify({
            'success': False,
            'error': _t('ui.camera.profile.schedule_required')
        }), 400
    
    result = add_schedule(
        data['profile'],
        data['time_start'],
        data.get('time_end'),
        data.get('days')
    )
    
    return jsonify(result)

@camera_bp.route('/scheduler/schedule/<int:schedule_id>', methods=['DELETE'])
def delete_scheduler_schedule(schedule_id):
    """Remove a schedule."""
    result = remove_schedule(schedule_id)
    return jsonify(result)

# ============================================================================
# CAMERA FORMATS ROUTES
# ============================================================================

@camera_bp.route('/formats', methods=['GET'])
def api_camera_formats():
    """Get available camera formats and resolutions."""
    device = request.args.get('device', '/dev/video0')
    formats = get_camera_formats(device)
    camera_type = detect_camera_type()
    encoder_caps = get_hw_encoder_capabilities()
    config = load_config()
    current = {
        'width': int(config.get('VIDEO_WIDTH', 640)),
        'height': int(config.get('VIDEO_HEIGHT', 480)),
        'fps': int(config.get('VIDEO_FPS', 15))
    }
    return jsonify({
        'success': True,
        'device': device,
        'formats': formats,
        'camera_type': camera_type,
        'encoder': encoder_caps,
        'current': current
    })
# ============================================================================
# CSI CAMERA ROUTES (Picamera2)
# ============================================================================

@camera_bp.route('/csi/available', methods=['GET'])
def csi_available():
    """
    Check if Picamera2/CSI camera system is available.
    
    Returns available=True if either:
    - CSI RTSP server is running (IPC available)
    - Picamera2 package is installed (offline mode)
    """
    import subprocess
    
    # Check if CSI server is running (IPC available = controls available)
    csi_server_running = False
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'rpi_csi_rtsp_server'],
            capture_output=True, timeout=2
        )
        csi_server_running = result.returncode == 0
    except:
        pass
    
    if csi_server_running:
        return jsonify({
            'success': True,
            'available': True,
            'mode': 'ipc',
            'message': _t('ui.camera.csi.server_running')
        })
    
    # Check Picamera2 availability for offline mode
    picam_available = is_picamera2_available()
    return jsonify({
        'success': True,
        'available': picam_available,
        'mode': 'offline' if picam_available else None,
        'message': _t('ui.camera.csi.picamera2_available') if picam_available else _t('ui.camera.csi.picamera2_missing')
    })

@camera_bp.route('/csi/info', methods=['GET'])
def csi_info():
    """Get CSI camera detailed information."""
    result = get_csi_camera_info()
    return jsonify(result)

@camera_bp.route('/csi/controls', methods=['GET'])
def csi_controls():
    """Get all CSI camera controls via Picamera2."""
    result = get_csi_camera_controls()
    
    # Merge with saved tuning values
    if result.get('success'):
        saved = load_csi_tuning_from_config()
        for name, value in saved.items():
            if name in result.get('controls', {}):
                result['controls'][name]['value'] = value
                result['controls'][name]['saved'] = True
    
    return jsonify(result)

@camera_bp.route('/csi/control', methods=['POST'])
def csi_set_control():
    """Set a CSI camera control value."""
    try:
        data = request.get_json(silent=True) or {}
        control = data.get('control', '')
        value = data.get('value')
        save = data.get('save', True)  # Save to config by default
        
        if not control:
            return jsonify({'success': False, 'message': _t('ui.camera.control_name_required')}), 400
        
        if value is None:
            return jsonify({'success': False, 'message': _t('ui.camera.value_required')}), 400
        
        # Apply the control (temporary, for preview)
        result = set_csi_camera_control(control, value)
        
        # Save to config file if requested
        if result['success'] and save:
            save_result = save_csi_tuning_to_config({control: value})
            result['saved'] = save_result['success']
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@camera_bp.route('/csi/controls/set-multiple', methods=['POST'])
def csi_set_multiple_controls():
    """Set multiple CSI camera controls at once."""
    try:
        data = request.get_json(silent=True) or {}
        controls = data.get('controls', {})
        save = data.get('save', True)
        
        if not controls:
            return jsonify({'success': False, 'message': _t('ui.camera.controls_required')}), 400
        
        results = []
        for name, value in controls.items():
            result = set_csi_camera_control(name, value)
            results.append({
                'control': name,
                'value': value,
                'success': result['success'],
                'message': result.get('message', '')
            })
        
        # Save all to config if requested
        if save:
            save_csi_tuning_to_config(controls)
        
        failed = [r for r in results if not r['success']]
        return jsonify({
            'success': len(failed) == 0,
            'results': results,
            'errors': len(failed)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@camera_bp.route('/csi/tuning', methods=['GET'])
def csi_get_tuning():
    """Get saved CSI tuning configuration."""
    tuning = load_csi_tuning_from_config()
    return jsonify({
        'success': True,
        'tuning': tuning
    })

@camera_bp.route('/csi/tuning', methods=['POST'])
def csi_save_tuning():
    """Save CSI tuning configuration."""
    try:
        data = request.get_json(silent=True) or {}
        controls = data.get('controls', data)  # Accept {controls: {...}} or direct dict
        
        result = save_csi_tuning_to_config(controls)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@camera_bp.route('/csi/tuning/reset', methods=['POST'])
def csi_reset_tuning():
    """Reset CSI tuning to defaults."""
    try:
        import os
        config_path = '/etc/rpi-cam/csi_tuning.json'
        if os.path.exists(config_path):
            os.remove(config_path)
        return jsonify({
            'success': True,
            'message': _t('ui.camera.csi_config_reset')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

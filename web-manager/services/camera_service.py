# -*- coding: utf-8 -*-
"""
Camera Service - Camera controls, profiles, and detection
Version: 2.30.10

Changes in 2.30.4:
- Added libcamera/CSI camera support (PiCam)
- Fixed resolution detection for unicam/CSI devices (Stepwise issue)
- New function detect_camera_type() to identify USB vs CSI cameras
- New function get_libcamera_formats() for CSI camera resolution detection
Changes in 2.30.10:
- Added get_hw_encoder_capabilities() for v4l2h264enc limits
"""

import os
import re
import json
import time
import threading
import subprocess
from datetime import datetime

from .platform_service import run_command, is_raspberry_pi
from config import (
    CAMERA_PROFILES_FILE, SCHEDULER_STATE_FILE,
    DEFAULT_CAMERA_PROFILES
)

# ============================================================================
# GLOBAL STATE
# ============================================================================

# Camera profiles state with thread safety
camera_profiles_state = {
    'profiles': {},
    'current_profile': None,
    'lock': threading.Lock()
}

# Scheduler state for auto-profiles
scheduler_state = {
    'enabled': False,
    'schedules': [],
    'current_schedule': None,
    'last_check': None
}

_scheduler_lock = threading.Lock()

# ============================================================================
# CAMERA DEVICE DETECTION
# ============================================================================

def detect_camera_type():
    """
    Detect what type of camera is connected.
    
    Returns:
        dict: {
            'type': 'libcamera' | 'usb' | 'none',
            'device': device path or camera id,
            'name': camera name,
            'driver': driver name
        }
    """
    # First, check for libcamera/CSI cameras (PiCam, etc.)
    result = run_command("rpicam-hello --list-cameras 2>&1", timeout=5)
    if result['success'] and 'Available cameras' in result['stdout']:
        # Parse libcamera output
        lines = result['stdout'].split('\n')
        for i, line in enumerate(lines):
            # Format: "0 : ov5647 [2592x1944 10-bit GBRG] (/base/soc/...)"
            match = re.match(r'(\d+)\s*:\s*(\w+)\s*\[', line)
            if match:
                cam_id = match.group(1)
                cam_name = match.group(2)
                return {
                    'type': 'libcamera',
                    'device': cam_id,
                    'name': cam_name,
                    'driver': 'libcamera'
                }
    
    # Fallback: check for USB cameras via v4l2
    for i in range(10):
        device = f"/dev/video{i}"
        if os.path.exists(device):
            result = run_command(f"v4l2-ctl -d {device} --info 2>/dev/null", timeout=5)
            if result['success'] and result['stdout']:
                info = {'type': 'usb', 'device': device, 'name': 'Unknown', 'driver': ''}
                for line in result['stdout'].split('\n'):
                    if 'Card type' in line:
                        info['name'] = line.split(':', 1)[1].strip()
                    elif 'Driver name' in line:
                        info['driver'] = line.split(':', 1)[1].strip()
                
                # Skip ISP/codec devices (bcm2835-isp, bcm2835-codec, unicam without libcamera)
                if info['driver'] in ['bcm2835-isp', 'bcm2835-codec']:
                    continue
                # Skip unicam if no libcamera (CSI without proper driver)
                if info['driver'] == 'unicam':
                    continue
                # Verify it's a capture device
                result2 = run_command(f"v4l2-ctl -d {device} --info 2>/dev/null | grep -i 'Video Capture'", timeout=5)
                if result2['success'] and result2['stdout']:
                    return info
    
    return {'type': 'none', 'device': None, 'name': None, 'driver': None}


def get_libcamera_formats():
    """
    Get available formats and resolutions for libcamera/CSI cameras.
    
    Returns:
        list: List of format dicts with resolutions and framerates
    """
    formats = []
    
    result = run_command("rpicam-hello --list-cameras 2>&1", timeout=10)
    if not result['success']:
        return formats
    
    # Parse rpicam-hello output
    # Example:
    # 0 : ov5647 [2592x1944 10-bit GBRG] (/base/soc/...)
    #     Modes: 'SGBRG10_CSI2P' : 640x480 [58.92 fps - (16, 0)/2560x1920 crop]
    #                              1296x972 [46.34 fps - (0, 0)/2592x1944 crop]
    
    lines = result['stdout'].split('\n')
    current_format = None
    
    for line in lines:
        # Detect format line: Modes: 'SGBRG10_CSI2P' : 640x480 [58.92 fps ...]
        mode_match = re.search(r"Modes:\s*'(\w+)'", line)
        if mode_match:
            current_format = {
                'format': mode_match.group(1),
                'resolutions': []
            }
            formats.append(current_format)
        
        # Parse resolution line: 640x480 [58.92 fps - ...]
        # Can be on the same line as Modes: or on subsequent lines
        res_matches = re.finditer(r'(\d+)x(\d+)\s*\[(\d+(?:\.\d+)?)\s*fps', line)
        for res_match in res_matches:
            width = int(res_match.group(1))
            height = int(res_match.group(2))
            fps = float(res_match.group(3))
            
            if current_format:
                # Check if this resolution already exists
                existing = next((r for r in current_format['resolutions'] 
                               if r['width'] == width and r['height'] == height), None)
                if existing:
                    if fps not in existing['framerates']:
                        existing['framerates'].append(fps)
                else:
                    current_format['resolutions'].append({
                        'width': width,
                        'height': height,
                        'framerates': [fps]
                    })
    
    # If no formats found but we have a libcamera camera, add common resolutions
    if not formats:
        # Check if camera exists
        detect = detect_camera_type()
        if detect['type'] == 'libcamera':
            # Add default PiCam resolutions
            formats = [{
                'format': 'YUV420',
                'resolutions': [
                    {'width': 2592, 'height': 1944, 'framerates': [15.0]},
                    {'width': 1920, 'height': 1080, 'framerates': [30.0]},
                    {'width': 1296, 'height': 972, 'framerates': [42.0]},
                    {'width': 640, 'height': 480, 'framerates': [60.0, 30.0]}
                ]
            }]
    
    # Sort resolutions
    for fmt in formats:
        fmt['resolutions'].sort(key=lambda r: r['width'] * r['height'], reverse=True)
        for res in fmt['resolutions']:
            res['framerates'].sort(reverse=True)
    
    return formats


def find_camera_device():
    """
    Find the video capture device (camera).
    
    Returns:
        str: Device path (e.g., '/dev/video0') or camera id for libcamera, or None
    """
    # Check camera type first
    cam_info = detect_camera_type()
    
    if cam_info['type'] == 'libcamera':
        # Return camera ID for libcamera
        return cam_info['device']
    elif cam_info['type'] == 'usb':
        return cam_info['device']
    
    # Legacy fallback: Check common video devices
    for i in range(10):
        device = f"/dev/video{i}"
        if os.path.exists(device):
            # Verify it's a capture device
            result = run_command(f"v4l2-ctl -d {device} --info 2>/dev/null | grep -i capture", timeout=5)
            if result['success'] and result['stdout']:
                return device
    
    return None

def get_camera_info(device=None):
    """
    Get detailed camera information.
    
    Args:
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: Camera information including formats, resolutions, etc.
    """
    # First detect camera type
    cam_info = detect_camera_type()
    
    if cam_info['type'] == 'libcamera':
        # CSI/libcamera camera
        formats_data = get_libcamera_formats()
        resolutions = []
        formats = []
        for fmt in formats_data:
            if fmt['format'] not in formats:
                formats.append(fmt['format'])
            for res in fmt['resolutions']:
                res_str = f"{res['width']}x{res['height']}"
                if res_str not in resolutions:
                    resolutions.append(res_str)
        
        return {
            'device': f"libcamera:{cam_info['device']}",
            'name': cam_info['name'],
            'driver': 'libcamera',
            'type': 'csi',
            'formats': formats,
            'resolutions': resolutions,
            'controls': []  # libcamera controls require different handling
        }
    
    # USB camera via v4l2
    if device is None:
        device = find_camera_device()
    
    if not device or (not device.startswith('libcamera:') and not os.path.exists(device)):
        return {'error': 'No camera found'}
    
    info = {
        'device': device,
        'name': 'Unknown',
        'driver': '',
        'type': 'usb',
        'formats': [],
        'resolutions': [],
        'controls': []
    }
    
    # Get camera info
    result = run_command(f"v4l2-ctl -d {device} --info", timeout=5)
    if result['success']:
        for line in result['stdout'].split('\n'):
            if 'Card type' in line:
                info['name'] = line.split(':', 1)[1].strip()
            elif 'Driver name' in line:
                info['driver'] = line.split(':', 1)[1].strip()
    
    # Get supported formats using v4l2
    formats_data = get_v4l2_formats(device)
    for fmt in formats_data:
        if fmt['format'] not in info['formats']:
            info['formats'].append(fmt['format'])
        for res in fmt['resolutions']:
            res_str = f"{res['width']}x{res['height']}"
            if res_str not in info['resolutions']:
                info['resolutions'].append(res_str)
    
    return info

# ============================================================================
# CAMERA CONTROLS (V4L2)
# ============================================================================

def get_camera_controls(device=None):
    """
    Get all available camera controls with current values.
    
    Args:
        device: Camera device path (auto-detect if None)
    
    Returns:
        list: List of control dicts with name, value, min, max, default, etc.
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return []
    
    controls = []
    
    # Get all controls
    result = run_command(f"v4l2-ctl -d {device} --list-ctrls-menus", timeout=10)
    if not result['success']:
        return []
    
    current_control = None
    
    for line in result['stdout'].split('\n'):
        line = line.strip()
        
        # Control line format: "control_name 0x00000000 (type): min=0 max=100 step=1 default=50 value=50"
        ctrl_match = re.match(
            r'^(\w+)\s+0x[0-9a-fA-F]+\s+\((\w+)\)\s*:\s*(.*)',
            line
        )
        
        if ctrl_match:
            name = ctrl_match.group(1)
            ctrl_type = ctrl_match.group(2)
            params_str = ctrl_match.group(3)
            
            control = {
                'name': name,
                'type': ctrl_type,
                'value': None,
                'min': None,
                'max': None,
                'step': 1,
                'default': None,
                'menu_items': []
            }
            
            # Parse parameters
            for param in ['min', 'max', 'step', 'default', 'value']:
                match = re.search(rf'{param}=(-?\d+)', params_str)
                if match:
                    control[param] = int(match.group(1))
            
            # Check for flags
            control['read_only'] = 'flags=read-only' in params_str or 'flags=inactive' in params_str
            
            controls.append(control)
            current_control = control
        
        # Menu item line (for menu type controls)
        elif current_control and current_control['type'] == 'menu':
            menu_match = re.match(r'^\s*(\d+):\s*(.+)', line)
            if menu_match:
                current_control['menu_items'].append({
                    'value': int(menu_match.group(1)),
                    'label': menu_match.group(2).strip()
                })
    
    return controls

def get_all_camera_controls(device=None):
    """
    Get ALL available camera controls with extended info for dynamic UI.
    Returns controls grouped by category for better UI organization.
    
    Args:
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: {controls: dict, grouped: dict, categories: list}
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return {'controls': {}, 'grouped': {}, 'categories': [], 'error': 'No camera found'}
    
    # Category definitions
    categories = {
        'focus': ['focus', 'zoom'],
        'exposure': ['exposure', 'gain', 'brightness', 'contrast', 'gamma', 'backlight'],
        'white_balance': ['white_balance', 'temperature'],
        'color': ['saturation', 'hue', 'sharpness'],
        'power_line': ['power_line', 'frequency'],
        'other': []  # Catch-all
    }
    
    controls_dict = {}
    
    # Get controls from v4l2
    result = run_command(f"v4l2-ctl -d {device} --list-ctrls-menus", timeout=10)
    if not result['success']:
        return {'controls': {}, 'grouped': {}, 'categories': list(categories.keys()), 'error': result['stderr']}
    
    current_control = None
    
    for line in result['stdout'].split('\n'):
        line_stripped = line.strip()
        
        # Control line format: "control_name 0x00000000 (type): min=0 max=100 step=1 default=50 value=50"
        ctrl_match = re.match(
            r'^(\w+)\s+0x[0-9a-fA-F]+\s+\((\w+)\)\s*:\s*(.*)',
            line_stripped
        )
        
        if ctrl_match:
            name = ctrl_match.group(1)
            ctrl_type = ctrl_match.group(2)
            params_str = ctrl_match.group(3)
            
            control = {
                'name': name,
                'type': ctrl_type,
                'display_name': name.replace('_', ' ').title(),
                'value': None,
                'min': None,
                'max': None,
                'step': 1,
                'default': None,
                'menu_items': {}
            }
            
            # Parse parameters
            for param in ['min', 'max', 'step', 'default', 'value']:
                match = re.search(rf'{param}=(-?\d+)', params_str)
                if match:
                    control[param] = int(match.group(1))
            
            # Check for flags
            control['read_only'] = 'flags=read-only' in params_str or 'flags=inactive' in params_str
            
            # Determine category
            category = 'other'
            name_lower = name.lower()
            for cat, keywords in categories.items():
                if cat != 'other' and any(kw in name_lower for kw in keywords):
                    category = cat
                    break
            control['category'] = category
            
            controls_dict[name] = control
            
            # Track current control for menu items
            if ctrl_type == 'menu':
                current_control = name
            else:
                current_control = None
        
        # Menu item line (for menu type controls)
        elif current_control and current_control in controls_dict:
            menu_match = re.match(r'^\s*(\d+):\s*(.+)', line)
            if menu_match:
                idx = int(menu_match.group(1))
                label = menu_match.group(2).strip()
                controls_dict[current_control]['menu_items'][idx] = label
    
    # Group controls by category
    grouped = {cat: [] for cat in categories.keys()}
    for name, ctrl in controls_dict.items():
        cat = ctrl.get('category', 'other')
        if cat in grouped:
            grouped[cat].append(ctrl)
        else:
            grouped['other'].append(ctrl)
    
    return {
        'controls': controls_dict,
        'grouped': grouped,
        'categories': list(categories.keys())
    }

def set_camera_control(control_name, value, device=None):
    """
    Set a camera control value.
    
    Args:
        control_name: Name of the control (e.g., 'brightness')
        value: Value to set
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: {success: bool, message: str}
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return {'success': False, 'message': 'No camera found'}
    
    # Set the control
    result = run_command(
        f"v4l2-ctl -d {device} --set-ctrl={control_name}={value}",
        timeout=5
    )
    
    if result['success']:
        return {'success': True, 'message': f'{control_name} set to {value}'}
    else:
        return {'success': False, 'message': result['stderr'] or 'Failed to set control'}

def reset_camera_control(control_name, device=None):
    """
    Reset a camera control to its default value.
    
    Args:
        control_name: Name of the control to reset
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: {success: bool, message: str, value: int}
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return {'success': False, 'message': 'No camera found'}
    
    # Get the control's default value
    controls = get_camera_controls(device)
    control = next((c for c in controls if c['name'] == control_name), None)
    
    if not control:
        return {'success': False, 'message': f'Control {control_name} not found'}
    
    if control['default'] is None:
        return {'success': False, 'message': 'No default value available'}
    
    # Set to default
    result = set_camera_control(control_name, control['default'], device)
    result['value'] = control['default']
    
    return result

def auto_camera_controls(device=None):
    """
    Enable auto settings for applicable controls (auto focus, auto exposure, auto white balance).
    
    Args:
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: {success: bool, message: str, controls_set: list}
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return {'success': False, 'message': 'No camera found', 'controls_set': []}
    
    auto_controls = {
        'focus_auto': 1,
        'focus_automatic_continuous': 1,
        'auto_exposure': 3,  # Aperture priority mode
        'exposure_auto': 3,
        'white_balance_auto_preset': 1,
        'white_balance_automatic': 1,
        'auto_white_balance': 1
    }
    
    controls_set = []
    
    for control_name, value in auto_controls.items():
        result = set_camera_control(control_name, value, device)
        if result['success']:
            controls_set.append(control_name)
    
    if controls_set:
        return {
            'success': True,
            'message': f'Auto controls enabled: {", ".join(controls_set)}',
            'controls_set': controls_set
        }
    else:
        return {
            'success': False,
            'message': 'No auto controls could be set',
            'controls_set': []
        }

def focus_oneshot(device=None):
    """
    Trigger a one-shot autofocus operation.
    Focus once then stay in manual mode.
    
    Args:
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: {success: bool, message: str}
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return {'success': False, 'message': 'No camera found'}
    
    try:
        # Enable autofocus
        success, msg = set_camera_autofocus(device, True, persist=False)
        if not success:
            return {'success': False, 'message': f'Failed to enable autofocus: {msg}'}
        
        # Wait for focus to settle (typical cameras take 500-2000ms)
        time.sleep(1.5)
        
        # Disable autofocus (lock the focus)
        success, msg = set_camera_autofocus(device, False, persist=False)
        if not success:
            return {'success': False, 'message': f'Failed to lock focus: {msg}'}
        
        return {'success': True, 'message': 'Focus triggered and locked'}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def get_camera_autofocus_status(device=None):
    """
    Get autofocus status for a camera.
    
    Args:
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: Autofocus status with fields:
            - autofocus_available: bool
            - autofocus_enabled: bool
            - focus_absolute_available: bool
            - focus_absolute: int
            - focus_min: int
            - focus_max: int
    """
    if device is None:
        device = find_camera_device()
    
    status = {
        'autofocus_available': False,
        'autofocus_enabled': False,
        'focus_absolute_available': False,
        'focus_absolute': 0,
        'focus_min': 0,
        'focus_max': 255
    }
    
    if not device:
        return status
    
    controls = get_camera_controls(device)
    
    # Convert to dict for easier lookup
    controls_dict = {c['name']: c for c in controls}
    
    # Check for autofocus control
    if 'focus_automatic_continuous' in controls_dict:
        status['autofocus_available'] = True
        status['autofocus_enabled'] = controls_dict['focus_automatic_continuous'].get('value', 0) == 1
    elif 'focus_auto' in controls_dict:
        status['autofocus_available'] = True
        status['autofocus_enabled'] = controls_dict['focus_auto'].get('value', 0) == 1
    
    # Check for manual focus control
    if 'focus_absolute' in controls_dict:
        ctrl = controls_dict['focus_absolute']
        status['focus_absolute_available'] = True
        status['focus_absolute'] = ctrl.get('value', 0)
        status['focus_min'] = ctrl.get('min', 0)
        status['focus_max'] = ctrl.get('max', 255)
    
    return status


def set_camera_autofocus(device, enabled, persist=False):
    """
    Enable or disable autofocus.
    
    Args:
        device: Camera device path (or None to auto-detect)
        enabled: True to enable autofocus
        persist: If True, save the setting to config.env
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return False, 'No camera found'
    
    controls = get_camera_controls(device)
    controls_dict = {c['name']: c for c in controls}
    
    success = False
    message = 'Autofocus control not available'
    
    # Try different autofocus control names
    if 'focus_automatic_continuous' in controls_dict:
        result = set_camera_control('focus_automatic_continuous', 1 if enabled else 0, device)
        success = result['success']
        message = result['message']
    elif 'focus_auto' in controls_dict:
        result = set_camera_control('focus_auto', 1 if enabled else 0, device)
        success = result['success']
        message = result['message']
    
    # Save to config if requested and successful
    if success and persist:
        try:
            from .config_service import load_config, save_config
            config = load_config()
            config['CAMERA_AUTOFOCUS'] = 'yes' if enabled else 'no'
            save_config(config)
        except Exception as e:
            print(f"Error saving autofocus config: {e}")
    
    return success, message


def set_camera_focus(device, value):
    """
    Set manual focus value.
    
    Args:
        device: Camera device path (or None to auto-detect)
        value: Focus value to set
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return False, 'No camera found'
    
    result = set_camera_control('focus_absolute', int(value), device)
    return result['success'], result['message']


# ============================================================================
# CAMERA PROFILES MANAGEMENT
# ============================================================================

def load_camera_profiles():
    """
    Load camera profiles from file.
    Supports both old format (profiles at root) and new format ({profiles: {...}})
    
    Returns:
        dict: {profiles: dict, current_profile: str}
    """
    global camera_profiles_state
    
    with camera_profiles_state['lock']:
        if os.path.exists(CAMERA_PROFILES_FILE):
            try:
                with open(CAMERA_PROFILES_FILE, 'r') as f:
                    data = json.load(f)
                    
                    # Support both formats:
                    # New format: {profiles: {...}, current_profile: ...}
                    # Old format: profiles directly at root level
                    if 'profiles' in data:
                        # New format
                        camera_profiles_state['profiles'] = data.get('profiles', {})
                        camera_profiles_state['current_profile'] = data.get('current_profile')
                    else:
                        # Old format - profiles are at root level
                        # Check if it looks like profiles (has 'controls' or 'schedule' keys)
                        is_old_format = any(
                            isinstance(v, dict) and ('controls' in v or 'schedule' in v)
                            for v in data.values()
                        )
                        if is_old_format:
                            camera_profiles_state['profiles'] = data
                            camera_profiles_state['current_profile'] = None
                        else:
                            camera_profiles_state['profiles'] = DEFAULT_CAMERA_PROFILES.copy()
            except Exception as e:
                print(f"Error loading camera profiles: {e}")
                camera_profiles_state['profiles'] = DEFAULT_CAMERA_PROFILES.copy()
        else:
            camera_profiles_state['profiles'] = DEFAULT_CAMERA_PROFILES.copy()
        
        return {
            'profiles': camera_profiles_state['profiles'].copy(),
            'current_profile': camera_profiles_state['current_profile']
        }

def save_camera_profiles():
    """
    Save camera profiles to file.
    
    Returns:
        dict: {success: bool, message: str}
    """
    global camera_profiles_state
    
    try:
        with camera_profiles_state['lock']:
            # Ensure directory exists
            profiles_dir = os.path.dirname(CAMERA_PROFILES_FILE)
            if profiles_dir and not os.path.exists(profiles_dir):
                os.makedirs(profiles_dir, mode=0o755)
            
            data = {
                'profiles': camera_profiles_state['profiles'],
                'current_profile': camera_profiles_state['current_profile']
            }
            
            with open(CAMERA_PROFILES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        
        return {'success': True, 'message': 'Profiles saved'}
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_camera_profiles():
    """
    Get all camera profiles.
    
    Returns:
        dict: {profiles: dict, current_profile: str}
    """
    return load_camera_profiles()

def create_camera_profile(name, profile_data):
    """
    Create or update a camera profile.
    
    Args:
        name: Profile ID (key)
        profile_data: dict with keys:
            - controls: dict of control_name: value
            - description: Optional description
            - display_name: Display name for UI
            - enabled: Whether profile is enabled for scheduler
            - schedule: {start: 'HH:MM', end: 'HH:MM'}
    
    Returns:
        dict: {success: bool, message: str}
    """
    global camera_profiles_state

    # Ensure profiles are loaded before updating (preserves schedule/enabled)
    load_camera_profiles()
    
    # Handle legacy call format (name, controls, description)
    if isinstance(profile_data, dict) and 'controls' not in profile_data:
        # Old format: profile_data is actually controls dict
        profile_data = {
            'controls': profile_data,
            'description': '',
            'display_name': name,
            'enabled': False,
            'schedule': {'start': '', 'end': ''}
        }
    
    # Get existing profile to preserve fields not being updated
    with camera_profiles_state['lock']:
        existing = camera_profiles_state['profiles'].get(name, {})
        
        camera_profiles_state['profiles'][name] = {
            'controls': profile_data.get('controls', existing.get('controls', {})),
            'description': profile_data.get('description', existing.get('description', '')),
            'display_name': profile_data.get('display_name', existing.get('display_name', name)),
            'enabled': profile_data.get('enabled', existing.get('enabled', False)),
            'schedule': profile_data.get('schedule', existing.get('schedule', {'start': '', 'end': ''})),
            'created': existing.get('created', datetime.now().isoformat()),
            'updated': datetime.now().isoformat()
        }
    
    return save_camera_profiles()

def delete_camera_profile(name):
    """
    Delete a camera profile.
    
    Args:
        name: Profile name to delete
    
    Returns:
        dict: {success: bool, message: str}
    """
    global camera_profiles_state
    
    with camera_profiles_state['lock']:
        if name not in camera_profiles_state['profiles']:
            return {'success': False, 'message': f'Profile "{name}" not found'}
        
        del camera_profiles_state['profiles'][name]
        
        if camera_profiles_state['current_profile'] == name:
            camera_profiles_state['current_profile'] = None
    
    return save_camera_profiles()

def apply_camera_profile(name, device=None):
    """
    Apply a camera profile to the camera.
    
    Args:
        name: Profile name to apply
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: {success: bool, message: str, controls_applied: list}
    """
    global camera_profiles_state
    
    if device is None:
        device = find_camera_device()
    
    if not device:
        return {'success': False, 'message': 'No camera found', 'controls_applied': []}
    
    with camera_profiles_state['lock']:
        if name not in camera_profiles_state['profiles']:
            return {'success': False, 'message': f'Profile "{name}" not found', 'controls_applied': []}
        
        profile = camera_profiles_state['profiles'][name]
    
    controls_applied = []
    errors = []
    
    for control_name, value in profile.get('controls', {}).items():
        if value is None:
            continue
        result = set_camera_control(control_name, value, device)
        if result['success']:
            controls_applied.append(control_name)
        else:
            errors.append(f"{control_name}: {result['message']}")
    
    # Update current profile
    with camera_profiles_state['lock']:
        camera_profiles_state['current_profile'] = name
    save_camera_profiles()
    
    if errors:
        return {
            'success': len(controls_applied) > 0,
            'message': f'Applied {len(controls_applied)} controls, {len(errors)} failed',
            'controls_applied': controls_applied,
            'errors': errors
        }
    
    return {
        'success': True,
        'message': f'Profile "{name}" applied ({len(controls_applied)} controls)',
        'controls_applied': controls_applied
    }

def apply_csi_camera_profile(name):
    """
    Apply a camera profile to a CSI/libcamera device via IPC + config persistence.
    """
    global camera_profiles_state

    with camera_profiles_state['lock']:
        if name not in camera_profiles_state['profiles']:
            return {'success': False, 'message': f'Profile "{name}" not found', 'controls_applied': []}
        profile = camera_profiles_state['profiles'][name]

    controls = profile.get('controls', {})
    if not controls:
        return {'success': False, 'message': 'Profile has no controls', 'controls_applied': []}

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

    applied = 0
    failed = 0
    skipped = 0
    errors = []

    from .csi_camera_service import set_csi_camera_control

    for ctrl_name, ctrl_value in filtered_controls.items():
        if ctrl_value is None:
            skipped += 1
            continue
        result = set_csi_camera_control(ctrl_name, ctrl_value)
        if result.get('success'):
            applied += 1
        else:
            failed += 1
            errors.append(f"{ctrl_name}: {result.get('message', 'Unknown error')}")

    # Update current profile
    with camera_profiles_state['lock']:
        camera_profiles_state['current_profile'] = name
    save_camera_profiles()

    if failed > 0:
        return {
            'success': False,
            'message': f'Applied {applied} controls, {failed} failed, {skipped} skipped',
            'controls_applied': list(filtered_controls.keys()),
            'errors': errors
        }

    return {
        'success': True,
        'message': f'Profile "{name}" applied ({applied} controls, {skipped} skipped)',
        'controls_applied': list(filtered_controls.keys())
    }

def apply_camera_profile_auto(name, device=None):
    """
    Apply a camera profile, selecting CSI or USB backend automatically.
    """
    cam_info = detect_camera_type()
    use_csi = cam_info.get('type') == 'libcamera'

    if not use_csi:
        try:
            from .config_service import load_config
            cfg = load_config()
            if str(cfg.get('CAMERA_TYPE', '')).lower() == 'csi' or str(cfg.get('CSI_ENABLE', '')).lower() == 'yes':
                use_csi = True
        except Exception:
            pass

    if use_csi:
        return apply_csi_camera_profile(name)
    return apply_camera_profile(name, device)

def set_current_profile(name):
    """Update the current profile marker without applying controls."""
    global camera_profiles_state
    with camera_profiles_state['lock']:
        camera_profiles_state['current_profile'] = name
    save_camera_profiles()
    return {'success': True, 'current_profile': name}

def capture_camera_profile(name, description='', device=None):
    """
    Capture current camera settings as a new profile.
    
    Args:
        name: Name for the new profile
        description: Optional description
        device: Camera device path (auto-detect if None)
    
    Returns:
        dict: {success: bool, message: str, profile: dict}
    """
    if device is None:
        device = find_camera_device()
    
    if not device:
        return {'success': False, 'message': 'No camera found'}
    
    # Get current control values
    controls = get_camera_controls(device)
    
    if not controls:
        return {'success': False, 'message': 'Could not read camera controls'}
    
    # Build profile from current values
    profile_controls = {}
    for ctrl in controls:
        if ctrl.get('read_only'):
            continue
        profile_controls[ctrl['name']] = ctrl.get('value')
    
    # Create the profile
    profile_data = {
        'controls': profile_controls
    }
    if description != '':
        profile_data['description'] = description
    result = create_camera_profile(name, profile_data)
    
    if result['success']:
        return {
            'success': True,
            'message': f'Profile "{name}" captured ({len(profile_controls)} controls)',
            'profile': {
                'name': name,
                'controls': profile_controls,
                'description': description
            }
        }
    
    return result

# ============================================================================
# PROFILE SCHEDULER HELPERS
# ============================================================================

def _parse_time_to_minutes(time_str):
    if not time_str:
        return None
    try:
        hours, minutes = time_str.split(':', 1)
        return int(hours) * 60 + int(minutes)
    except Exception:
        return None

def _is_time_in_range(start_str, end_str, now_minutes):
    start = _parse_time_to_minutes(start_str)
    end = _parse_time_to_minutes(end_str)

    if start is None and end is None:
        return False
    if start is None:
        start = 0
    if end is None:
        return True

    if start == end:
        return True
    if start < end:
        return start <= now_minutes < end
    return now_minutes >= start or now_minutes < end

def get_active_profile_by_schedule(profiles, now=None):
    if not profiles:
        return None

    now_dt = now or datetime.now()
    now_minutes = now_dt.hour * 60 + now_dt.minute

    for name, profile in profiles.items():
        if not profile.get('enabled', False):
            continue
        schedule = profile.get('schedule', {}) or {}
        if _is_time_in_range(schedule.get('start'), schedule.get('end'), now_minutes):
            return name
    return None

def _filter_csi_controls(controls):
    if not controls:
        return {}
    ae_enabled = controls.get('AeEnable') is True
    awb_enabled = controls.get('AwbEnable') is True
    filtered = {}
    for ctrl_name, ctrl_value in controls.items():
        if ae_enabled and ctrl_name in ['ExposureTime', 'AnalogueGain', 'ExposureTimeMode', 'AnalogueGainMode', 'FrameDurationLimits']:
            continue
        if awb_enabled and ctrl_name in ['ColourGains', 'ColourTemperature']:
            continue
        filtered[ctrl_name] = ctrl_value
    return filtered

def _apply_csi_profile(profile_name, profile):
    from .csi_camera_service import set_csi_camera_control

    controls = profile.get('controls', {}) if profile else {}
    controls = _filter_csi_controls(controls)
    applied = 0
    failed = 0
    for ctrl_name, ctrl_value in controls.items():
        if ctrl_value is None:
            continue
        result = set_csi_camera_control(ctrl_name, ctrl_value)
        if result.get('success'):
            applied += 1
        else:
            failed += 1
    return {'success': failed == 0, 'applied': applied, 'failed': failed}

def _restart_rtsp_for_csi_overlay_if_needed():
    try:
        from .config_service import load_config
        config = load_config()
        camera_type = str(config.get('CAMERA_TYPE', '')).lower()
        overlay_mode = str(config.get('CSI_OVERLAY_MODE', '')).lower()
        if camera_type == 'csi' and overlay_mode == 'libcamera':
            # Libcamera overlay mode cannot apply controls live; restart to re-read config.
            run_command("systemctl restart rpi-av-rtsp-recorder", timeout=10)
    except Exception:
        pass

def profiles_scheduler_loop(stop_event=None, interval_sec=30):
    from .config_service import load_config

    while True:
        if stop_event and stop_event.is_set():
            break

        config = load_config()
        scheduler_enabled = config.get('CAMERA_PROFILES_ENABLED', 'no') == 'yes'
        scheduler_state['enabled'] = scheduler_enabled

        profiles_data = load_camera_profiles()
        profiles = profiles_data.get('profiles', {})
        active_profile = get_active_profile_by_schedule(profiles)

        with _scheduler_lock:
            scheduler_state['last_check'] = datetime.now().isoformat()

            if not scheduler_enabled:
                scheduler_state['current_schedule'] = None
                save_scheduler_state()
            else:
                if active_profile and active_profile != scheduler_state.get('current_schedule'):
                    cam_type = detect_camera_type()
                    if cam_type['type'] == 'libcamera':
                        profile = profiles.get(active_profile, {})
                        result = _apply_csi_profile(active_profile, profile)
                    else:
                        result = apply_camera_profile_auto(active_profile)

                    if result.get('success'):
                        _restart_rtsp_for_csi_overlay_if_needed()
                        scheduler_state['current_schedule'] = active_profile
                        set_current_profile(active_profile)
                        save_scheduler_state()
                elif not active_profile:
                    scheduler_state['current_schedule'] = None
                    save_scheduler_state()

        time.sleep(interval_sec)

def apply_active_scheduled_profile(force: bool = False) -> dict:
    """
    Apply the currently active scheduled profile immediately.

    Needed because after a manual RTSP service restart, the scheduler state may
    still think the profile is applied (same schedule), while the RTSP pipeline
    and CSI control API have restarted and require re-applying the controls.
    """
    from .config_service import load_config

    config = load_config()
    scheduler_enabled = config.get('CAMERA_PROFILES_ENABLED', 'no') == 'yes'
    if not scheduler_enabled:
        return {'success': True, 'applied': False, 'reason': 'scheduler_disabled'}

    profiles_data = load_camera_profiles()
    profiles = profiles_data.get('profiles', {}) or {}
    active_profile = get_active_profile_by_schedule(profiles)

    if not active_profile:
        with _scheduler_lock:
            scheduler_state['current_schedule'] = None
            save_scheduler_state()
        return {'success': True, 'applied': False, 'reason': 'no_active_schedule'}

    with _scheduler_lock:
        if not force and active_profile == scheduler_state.get('current_schedule'):
            return {'success': True, 'applied': False, 'reason': 'already_applied', 'profile': active_profile}

    cam_type = detect_camera_type()
    if cam_type['type'] == 'libcamera':
        profile = profiles.get(active_profile, {}) or {}
        result = _apply_csi_profile(active_profile, profile)
    else:
        result = apply_camera_profile_auto(active_profile)

    if result.get('success'):
        _restart_rtsp_for_csi_overlay_if_needed()
        with _scheduler_lock:
            scheduler_state['current_schedule'] = active_profile
            scheduler_state['last_check'] = datetime.now().isoformat()
            set_current_profile(active_profile)
            save_scheduler_state()
        return {'success': True, 'applied': True, 'profile': active_profile}

    return {'success': False, 'applied': False, 'profile': active_profile, 'error': 'apply_failed', 'details': result}

def reapply_scheduler_after_rtsp_restart(delay_sec: float = 1.5, retries: int = 8, retry_delay_sec: float = 0.5) -> None:
    """
    Best-effort re-apply the active scheduled profile after an RTSP service restart.

    Intended to be run in a background thread.
    """
    try:
        time.sleep(max(0.0, float(delay_sec)))
    except Exception:
        pass

    for _ in range(max(1, int(retries))):
        result = apply_active_scheduled_profile(force=True)
        if result.get('success'):
            return
        time.sleep(max(0.1, float(retry_delay_sec)))

# ============================================================================
# PROFILE SCHEDULER
# ============================================================================

def load_scheduler_state():
    """Load scheduler state from file."""
    global scheduler_state
    
    if os.path.exists(SCHEDULER_STATE_FILE):
        try:
            with open(SCHEDULER_STATE_FILE, 'r') as f:
                data = json.load(f)
                scheduler_state.update(data)
        except Exception as e:
            print(f"Error loading scheduler state: {e}")

def save_scheduler_state():
    """Save scheduler state to file."""
    global scheduler_state
    
    try:
        state_to_save = {
            'enabled': scheduler_state['enabled'],
            'schedules': scheduler_state['schedules'],
            'current_schedule': scheduler_state['current_schedule']
        }
        with open(SCHEDULER_STATE_FILE, 'w') as f:
            json.dump(state_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving scheduler state: {e}")

def get_scheduler_state():
    """Get current scheduler state."""
    load_scheduler_state()
    return {
        'enabled': scheduler_state['enabled'],
        'schedules': scheduler_state['schedules'],
        'current_schedule': scheduler_state['current_schedule'],
        'last_check': scheduler_state['last_check']
    }

def set_scheduler_enabled(enabled):
    """Enable or disable the profile scheduler."""
    global scheduler_state
    scheduler_state['enabled'] = enabled
    save_scheduler_state()
    return {'success': True, 'enabled': enabled}

def add_schedule(profile_name, time_start, time_end=None, days=None):
    """
    Add a scheduled profile activation.
    
    Args:
        profile_name: Name of the profile to activate
        time_start: Start time (HH:MM format)
        time_end: Optional end time
        days: Optional list of days (0=Monday, 6=Sunday)
    """
    global scheduler_state
    
    schedule = {
        'id': len(scheduler_state['schedules']) + 1,
        'profile': profile_name,
        'time_start': time_start,
        'time_end': time_end,
        'days': days or list(range(7)),  # All days by default
        'enabled': True
    }
    
    scheduler_state['schedules'].append(schedule)
    save_scheduler_state()
    
    return {'success': True, 'schedule': schedule}

def remove_schedule(schedule_id):
    """Remove a schedule by ID."""
    global scheduler_state
    
    scheduler_state['schedules'] = [
        s for s in scheduler_state['schedules'] if s.get('id') != schedule_id
    ]
    save_scheduler_state()
    
    return {'success': True}

# ============================================================================
# CAMERA FORMATS
# ============================================================================

def get_camera_formats(device='/dev/video0'):
    """Get available video formats and resolutions for a camera.
    
    Supports both USB cameras (v4l2) and CSI cameras (libcamera/PiCam).
    
    Returns a list of format objects with:
    - format: pixel format (e.g., 'MJPG', 'YUYV', 'YUV420')
    - resolutions: list of {width, height, framerates}
    """
    # First, detect camera type
    cam_info = detect_camera_type()
    
    # If it's a libcamera/CSI camera, use libcamera detection
    if cam_info['type'] == 'libcamera':
        return get_libcamera_formats()
    
    # Otherwise, use v4l2 detection for USB cameras
    return get_v4l2_formats(device)


def get_hw_encoder_capabilities():
    """Get v4l2h264enc capabilities (max resolution) when available."""
    info = {
        'available': False,
        'type': None,
        'device': None,
        'max_width': 0,
        'max_height': 0
    }

    encoder_device = '/dev/video11'
    if not os.path.exists(encoder_device):
        return info

    result = run_command("gst-inspect-1.0 v4l2h264enc >/dev/null 2>&1", timeout=5)
    if not result['success']:
        return info

    info['available'] = True
    info['type'] = 'v4l2h264enc'
    info['device'] = encoder_device

    result = run_command(f"v4l2-ctl -d {encoder_device} --list-formats-ext 2>/dev/null", timeout=5)
    if not result['success'] or not result['stdout']:
        return info

    max_area = 0
    max_width = 0
    max_height = 0
    for line in result['stdout'].splitlines():
        step_match = re.search(r'Size:\s*Stepwise\s*(\d+)x(\d+)\s*-\s*(\d+)x(\d+)', line)
        if step_match:
            width = int(step_match.group(3))
            height = int(step_match.group(4))
        else:
            discrete_match = re.search(r'Size:\s*Discrete\s*(\d+)x(\d+)', line)
            if not discrete_match:
                continue
            width = int(discrete_match.group(1))
            height = int(discrete_match.group(2))

        area = width * height
        if area > max_area:
            max_area = area
            max_width = width
            max_height = height

    info['max_width'] = max_width
    info['max_height'] = max_height
    return info

def get_v4l2_formats(device='/dev/video0'):
    """Get available video formats for USB cameras via v4l2.
    
    Returns a list of format objects with:
    - format: pixel format (e.g., 'MJPG', 'YUYV')
    - resolutions: list of {width, height, framerates}
    """
    formats = []
    
    try:
        # Get list of formats
        result = subprocess.run(
            ['v4l2-ctl', '-d', device, '--list-formats-ext'],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            return formats
        
        current_format = None
        current_resolution = None
        is_stepwise = False
        
        for line in result.stdout.split('\n'):
            # Parse format line: [0]: 'MJPG' (Motion-JPEG, compressed)
            format_match = re.match(r"\s*\[\d+\]:\s*'(\w+)'", line)
            if format_match:
                current_format = {
                    'format': format_match.group(1),
                    'resolutions': []
                }
                formats.append(current_format)
                current_resolution = None
                is_stepwise = False
                continue
            
            # Check for Stepwise (CSI cameras via v4l2 - should use libcamera instead)
            if 'Stepwise' in line:
                is_stepwise = True
                continue
            
            # Skip stepwise formats - they're not real discrete resolutions
            if is_stepwise:
                continue
            
            # Parse size line: Size: Discrete 1280x960
            size_match = re.match(r'\s*Size:\s*\w+\s*(\d+)x(\d+)', line)
            if size_match and current_format:
                width = int(size_match.group(1))
                height = int(size_match.group(2))
                # Skip tiny resolutions (ISP artifacts)
                if width < 32 or height < 32:
                    continue
                current_resolution = {
                    'width': width,
                    'height': height,
                    'framerates': []
                }
                current_format['resolutions'].append(current_resolution)
                continue
            
            # Parse framerate line: Interval: Discrete 0.033s (30.000 fps)
            fps_match = re.match(r'\s*Interval:.*\((\d+(?:\.\d+)?)\s*fps\)', line)
            if fps_match and current_resolution:
                fps = float(fps_match.group(1))
                if fps not in current_resolution['framerates']:
                    current_resolution['framerates'].append(fps)
        
        # Remove formats with no valid resolutions (all stepwise)
        formats = [f for f in formats if f['resolutions']]
        
        # Sort resolutions by megapixels (descending) and framerates
        for fmt in formats:
            fmt['resolutions'].sort(key=lambda r: r['width'] * r['height'], reverse=True)
            for res in fmt['resolutions']:
                res['framerates'].sort(reverse=True)
        
    except Exception as e:
        print(f"Error getting camera formats: {e}")
    
    return formats

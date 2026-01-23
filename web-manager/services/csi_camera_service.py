"""
CSI Camera Service - Picamera2 controls for CSI/PiCam cameras
Version: 1.2.1

This module provides control over CSI cameras (PiCam v1/v2/v3) via Picamera2.
Unlike USB cameras that use v4l2-ctl, CSI cameras require libcamera/Picamera2.

Changelog:
  - 1.2.1: Fixed Picamera2 detection - don't cache False results, check package instead
  - 1.2.0: Fix IPC response handling - data from rpi_csi_rtsp_server is already formatted
  - 1.1.1: Added timeout/logging to IPC, better error handling
  - 1.1.0: Replace requests with urllib.request (no external dependency)
"""

import subprocess
import json
import logging
import os

logger = logging.getLogger(__name__)

# Cache for Picamera2 availability - only cache positive results
_picamera2_available = None

# Use system Python for Picamera2 (not venv Python)
# because picamera2 has system dependencies that are hard to install in venv
SYSTEM_PYTHON = '/usr/bin/python3'

def is_picamera2_available():
    """Check if Picamera2 module is available in system Python."""
    global _picamera2_available
    
    # Only use cache if it's True (don't cache False - allow retry)
    if _picamera2_available is True:
        return True
    
    # Method 1: Check if package is installed (fast, doesn't need camera)
    try:
        result = subprocess.run(
            ['dpkg', '-s', 'python3-picamera2'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and 'Status: install ok installed' in result.stdout:
            logger.info("Picamera2 detected via dpkg")
            _picamera2_available = True
            return True
    except Exception as e:
        logger.debug(f"dpkg check failed: {e}")
    
    # Method 2: Try import (slower, may fail if camera is busy)
    try:
        result = subprocess.run(
            [SYSTEM_PYTHON, '-c', 'import picamera2; print("OK")'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and 'OK' in result.stdout:
            logger.info("Picamera2 detected via import")
            _picamera2_available = True
            return True
    except Exception as e:
        logger.warning(f"Picamera2 import check failed: {e}")
    
    # Don't cache False - allow retry on next call
    logger.warning("Picamera2 not detected")
    return False


# ==============================================================================
# Helper Functions
# ==============================================================================

def _format_csi_response(picam2_data):
    """
    Format raw Picamera2 data (from IPC or script) into UI structure.
    Args:
        picam2_data: dict with keys 'controls', 'properties', 'sensor_modes'
                     where 'controls' is {name: (min, max, default)}
    """
    if not picam2_data:
        return {'success': False, 'error': 'No data'}
        
    raw_controls = picam2_data.get('controls', {})
    props = picam2_data.get('properties', {})
    modes = picam2_data.get('sensor_modes', [])
    
    formatted_controls = {}
    
    for name, limits in raw_controls.items():
        min_val, max_val, default_val = limits
        
        # Determine type
        if isinstance(default_val, bool):
            ctrl_type = 'bool'
        elif isinstance(default_val, float):
            ctrl_type = 'float'
        elif isinstance(default_val, int):
            ctrl_type = 'int'
        else:
            ctrl_type = 'other'
        
        # Categorize
        name_lower = name.lower()
        if any(k in name_lower for k in ['exposure', 'gain', 'analogue']):
            category = 'exposure'
        elif any(k in name_lower for k in ['white', 'colour', 'saturation', 'contrast', 'brightness', 'sharpness']):
            category = 'color'
        elif any(k in name_lower for k in ['focus', 'lens', 'af']):
            category = 'focus'
        elif any(k in name_lower for k in ['noise', 'denoise']):
            category = 'noise'
        elif any(k in name_lower for k in ['awb', 'ae', 'auto']):
            category = 'auto'
        else:
            category = 'other'
            
        display_name = name.replace('_', ' ').title()
        
        formatted_controls[name] = {
            'name': name,
            'display_name': display_name,
            'min': min_val,
            'max': max_val,
            'default': default_val,
            'value': default_val, # Note: We don't have CURRENT value, assuming default for now
            'type': ctrl_type,
            'category': category,
            'read_only': False
        }

    grouped = {}
    for name, ctrl in formatted_controls.items():
        cat = ctrl['category']
        if cat not in grouped:
            grouped[cat] = {}
        grouped[cat][name] = ctrl
        
    camera_info = {
        'model': props.get('Model', 'Unknown'),
        'pixel_array_size': props.get('PixelArraySize', [0, 0]),
        'unit_cell_size': props.get('UnitCellSize', [0, 0]),
        'sensor_modes_count': len(modes)
    }
    
    return {
        'success': True,
        'controls': formatted_controls,
        'grouped': grouped,
        'camera_info': camera_info,
        'categories': list(grouped.keys())
    }

def get_csi_camera_controls():
    """
    Get all available controls for CSI camera via Picamera2.
    
    Strategy:
    1. Try IPC to running CSI server (port 8085) - fast, works if server is running
    2. If IPC fails AND server is running, return "server busy" error (don't block)
    3. If no server running, try offline Picamera2 script (slow, needs camera free)
    """
    import urllib.request
    import urllib.error
    
    ipc_error = None
    
    # 1. Try IPC (Live Server) using urllib (always available)
    try:
        logger.info("Attempting IPC connection to CSI server on port 8085...")
        req = urllib.request.Request('http://127.0.0.1:8085/controls', method='GET')
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                raw_data = resp.read().decode('utf-8')
                logger.info(f"IPC response received ({len(raw_data)} bytes)")
                data = json.loads(raw_data)
                
                # If data already has 'controls' key with formatted structure, return directly
                if 'controls' in data and isinstance(data['controls'], dict):
                    # Check if it's already formatted (has nested dicts with 'name' key)
                    first_ctrl = next(iter(data['controls'].values()), None)
                    if first_ctrl and isinstance(first_ctrl, dict) and 'name' in first_ctrl:
                        logger.info(f"IPC response already formatted: {len(data['controls'])} controls found")
                        data['success'] = True
                        return data
                
                # Otherwise, format raw Picamera2 data
                result = _format_csi_response(data)
                logger.info(f"IPC controls formatted: {len(result.get('controls', {}))} controls found")
                return result
    except urllib.error.URLError as e:
        ipc_error = str(e.reason) if hasattr(e, 'reason') else str(e)
        logger.warning(f"IPC connection failed (URLError): {ipc_error}")
    except Exception as e:
        ipc_error = f"{type(e).__name__}: {e}"
        logger.warning(f"IPC connection failed: {ipc_error}")

    # Check if CSI RTSP server is running (camera will be busy)
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
        # Server is running but IPC failed - camera is busy, don't try offline script
        logger.warning("CSI server is running but IPC failed - server may be starting up")
        return {
            'success': False,
            'error': 'Serveur CSI en cours de démarrage. Réessayez dans quelques secondes.',
            'controls': {},
            'grouped': {},
            'retry': True
        }

    logger.info("IPC not available and server not running, falling back to offline Picamera2 script...")

    # 2. Fallback to offline script (only if server not running)
    if not is_picamera2_available():
        return {
            'success': False,
            'error': 'Picamera2 non installé. Lancez: sudo apt install python3-picamera2',
            'controls': {},
            'grouped': {}
        }
    
    # Python script to execute with Picamera2
    script = '''
import json
import sys
try:
    from picamera2 import Picamera2
    
    # Initialize camera
    picam2 = Picamera2()
    
    # Get camera properties
    camera_props = picam2.camera_properties
    sensor_modes = picam2.sensor_modes
    
    # Get available controls with their ranges
    controls = {}
    for name, (min_val, max_val, default_val) in picam2.camera_controls.items():
        # Determine type
        if isinstance(default_val, bool):
            ctrl_type = 'bool'
        elif isinstance(default_val, float):
            ctrl_type = 'float'
        elif isinstance(default_val, int):
            ctrl_type = 'int'
        else:
            ctrl_type = 'other'
        
        # Categorize controls
        name_lower = name.lower()
        if any(k in name_lower for k in ['exposure', 'gain', 'analogue']):
            category = 'exposure'
        elif any(k in name_lower for k in ['white', 'colour', 'saturation', 'contrast', 'brightness', 'sharpness']):
            category = 'color'
        elif any(k in name_lower for k in ['focus', 'lens', 'af']):
            category = 'focus'
        elif any(k in name_lower for k in ['noise', 'denoise']):
            category = 'noise'
        elif any(k in name_lower for k in ['awb', 'ae', 'auto']):
            category = 'auto'
        else:
            category = 'other'
        
        # Make display name more readable
        display_name = name.replace('_', ' ').title()
        
        controls[name] = {
            'name': name,
            'display_name': display_name,
            'min': min_val if not isinstance(min_val, (list, tuple)) else min_val[0] if min_val else 0,
            'max': max_val if not isinstance(max_val, (list, tuple)) else max_val[0] if max_val else 100,
            'default': default_val if not isinstance(default_val, (list, tuple)) else default_val[0] if default_val else 0,
            'value': default_val if not isinstance(default_val, (list, tuple)) else default_val[0] if default_val else 0,
            'type': ctrl_type,
            'category': category,
            'read_only': False
        }
    
    # Camera info
    camera_info = {
        'model': camera_props.get('Model', 'Unknown'),
        'pixel_array_size': camera_props.get('PixelArraySize', [0, 0]),
        'unit_cell_size': camera_props.get('UnitCellSize', [0, 0]),
        'sensor_modes_count': len(sensor_modes)
    }
    
    picam2.close()
    
    # Group controls by category
    grouped = {}
    for name, ctrl in controls.items():
        cat = ctrl['category']
        if cat not in grouped:
            grouped[cat] = {}
        grouped[cat][name] = ctrl
    
    print(json.dumps({
        'success': True,
        'controls': controls,
        'grouped': grouped,
        'camera_info': camera_info,
        'categories': list(grouped.keys())
    }))
    
except Exception as e:
    print(json.dumps({
        'success': False,
        'error': str(e),
        'controls': {},
        'grouped': {}
    }))
    sys.exit(1)
'''
    
    try:
        result = subprocess.run(
            [SYSTEM_PYTHON, '-c', script],
            capture_output=True, text=True, timeout=15
        )
        
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            return data
        else:
            error_msg = result.stderr.strip() if result.stderr else 'Unknown error'
            # Check for common errors
            if 'No cameras available' in error_msg:
                error_msg = "Aucune caméra CSI détectée. Vérifiez la connexion du ruban."
            elif 'Camera is already' in error_msg or 'in use' in error_msg.lower() or 'Device or resource busy' in error_msg:
                error_msg = "Caméra occupée par le flux RTSP. Arrêtez le flux pour modifier les paramètres, puis redémarrez-le."
            elif 'Camera' in error_msg and 'failed' in error_msg.lower():
                error_msg = "Caméra occupée par le flux RTSP. Arrêtez le flux pour modifier les paramètres."
            return {
                'success': False,
                'error': error_msg,
                'camera_busy': 'occupée' in error_msg or 'busy' in error_msg.lower(),
                'controls': {},
                'grouped': {}
            }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Timeout lors de la lecture des contrôles CSI',
            'controls': {},
            'grouped': {}
        }
    except json.JSONDecodeError as e:
        return {
            'success': False,
            'error': f'Erreur de parsing JSON: {e}',
            'controls': {},
            'grouped': {}
        }
    except Exception as e:
        logger.error(f"Error getting CSI controls: {e}")
        return {
            'success': False,
            'error': str(e),
            'controls': {},
            'grouped': {}
        }


def set_csi_camera_control(control_name, value):
    """
    Set a CSI camera control value via Picamera2.
    
    IMPORTANT: When Picamera2 is in streaming mode (started with start_encoder),
    some controls may not apply live and will only take effect after restart.
    """
    import urllib.request
    import urllib.error
    ipc_success = False
    try:
        payload = json.dumps({control_name: value}).encode('utf-8')
        req = urllib.request.Request(
            'http://127.0.0.1:8085/set_controls',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=1) as resp:
            if resp.status == 200:
                ipc_success = True
                logger.info(f"CSI Control {control_name}={value} set via IPC")
    except (urllib.error.URLError, Exception) as e:
        logger.warning(f"Failed to set CSI control {control_name} via IPC: {e}")


    # Always save to config for persistent application
    save_res = save_csi_tuning_to_config({control_name: value})
    
    if ipc_success:
        return {'success': True, 'message': f'Contrôle {control_name} appliqué (aussi sauvegardé pour redémarrage).'}
    elif save_res['success']:
        logger.warning(f"CSI control {control_name} saved to config but IPC application failed - will apply on next server restart")
        return {'success': True, 'message': f'Contrôle {control_name} sauvegardé. NOTE: Le serveur CSI est en streaming, le changement prendra effet au prochain redémarrage du serveur.'}
    else:
        return {'success': False, 'message': save_res['message']}


def get_csi_camera_info():
    """
    Get detailed CSI camera information.
    
    Returns:
        dict with camera model, resolution, sensor info
    """
    if not is_picamera2_available():
        return {'success': False, 'error': 'Picamera2 non disponible'}
    
    script = '''
import json
try:
    from picamera2 import Picamera2
    
    picam2 = Picamera2()
    props = picam2.camera_properties
    modes = picam2.sensor_modes
    
    # Format sensor modes for display
    formatted_modes = []
    for i, mode in enumerate(modes):
        size = mode.get('size', (0, 0))
        fps = mode.get('fps', 0)
        fmt = mode.get('format', 'unknown')
        formatted_modes.append({
            'index': i,
            'width': size[0],
            'height': size[1],
            'fps': fps,
            'format': str(fmt)
        })
    
    info = {
        'success': True,
        'model': props.get('Model', 'Unknown'),
        'pixel_array_size': list(props.get('PixelArraySize', [0, 0])),
        'unit_cell_size': list(props.get('UnitCellSize', [0, 0])),
        'color_filter_arrangement': props.get('ColorFilterArrangement', 'Unknown'),
        'sensor_modes': formatted_modes,
        'location': props.get('Location', 0),
        'rotation': props.get('Rotation', 0)
    }
    
    picam2.close()
    print(json.dumps(info))
except Exception as e:
    print(json.dumps({'success': False, 'error': str(e)}))
'''
    
    try:
        result = subprocess.run(
            [SYSTEM_PYTHON, '-c', script],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
        return {'success': False, 'error': result.stderr.strip() or 'Erreur'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def save_csi_tuning_to_config(controls_dict):
    """
    Save CSI camera tuning parameters to config file for RTSP pipeline.
    
    The RTSP script (rpi_av_rtsp_recorder.sh) will read these and apply
    them to libcamerasrc via the 'tuning-file' or environment variables.
    
    Args:
        controls_dict: dict of {control_name: value}
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    import os
    
    config_path = '/etc/rpi-cam/csi_tuning.json'
    
    try:
        # Read existing config
        existing = {}
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                existing = json.load(f)
        
        # Merge with new values
        existing.update(controls_dict)
        
        # Write back
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(existing, f, indent=2)
        
        return {'success': True, 'message': f'Configuration sauvegardée dans {config_path}'}
    except Exception as e:
        return {'success': False, 'message': str(e)}


def load_csi_tuning_from_config():
    """
    Load saved CSI camera tuning parameters.
    
    Returns:
        dict: The saved tuning parameters or empty dict
    """
    config_path = '/etc/rpi-cam/csi_tuning.json'
    
    try:
        import os
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.warning(f"Could not load CSI tuning: {e}")
        return {}

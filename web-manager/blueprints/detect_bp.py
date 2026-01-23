# -*- coding: utf-8 -*-
"""
Detect Blueprint - Camera and audio device detection routes
Version: 2.30.1
"""

import os
import subprocess
from flask import Blueprint, request, jsonify

from services.camera_service import find_camera_device, get_camera_info
from services.platform_service import run_command, PLATFORM
from config import APP_VERSION

detect_bp = Blueprint('detect', __name__, url_prefix='/api')

# ============================================================================
# CAMERA DETECTION
# ============================================================================

@detect_bp.route('/detect/cameras', methods=['GET'])
def detect_cameras():
    """Detect all available cameras (USB and CSI)."""
    cameras = []
    
    # First, check for CSI camera (Raspberry Pi only)
    csi_detected = False
    if PLATFORM.get('has_libcamera'):
        try:
            # Try rpicam-hello first (Trixie), then libcamera-hello (legacy)
            cmds = [
                ['rpicam-hello', '--list-cameras'],
                ['libcamera-hello', '--list-cameras']
            ]
            for cmd in cmds:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0 and 'Available cameras' in result.stdout:
                        # Parse camera name from output
                        cam_name = 'Raspberry Pi Camera'
                        for line in result.stdout.split('\n'):
                            if ':' in line and ('imx' in line.lower() or 'ov' in line.lower()):
                                # Extract sensor name (e.g., imx219, ov5647)
                                parts = line.split()
                                for part in parts:
                                    if any(s in part.lower() for s in ['imx', 'ov', 'sony', 'omnivision']):
                                        cam_name = part.strip('()[]')
                                        break
                                break
                        cameras.append({
                            'device': 'CSI',
                            'type': 'CSI',
                            'name': cam_name
                        })
                        csi_detected = True
                        break
                except FileNotFoundError:
                    continue
        except Exception as e:
            pass
    
    # Check USB cameras (skip CSI unicam devices if CSI camera was already detected)
    for i in range(10):
        dev = f'/dev/video{i}'
        if os.path.exists(dev):
            info = {'device': dev, 'type': 'USB'}
            try:
                result = subprocess.run(
                    ['v4l2-ctl', '-d', dev, '--info'],
                    capture_output=True, text=True, timeout=5
                )
                if 'Card type' in result.stdout:
                    for line in result.stdout.split('\n'):
                        if 'Card type' in line:
                            card_name = line.split(':')[1].strip()
                            info['name'] = card_name
                            # If this is unicam (CSI interface) and we already detected CSI, skip
                            if 'unicam' in card_name.lower() and csi_detected:
                                info = None
                            break
            except:
                info['name'] = f'Video Device {i}'
            
            if info:
                cameras.append(info)
    
    return jsonify({
        'success': True,
        'cameras': cameras
    })

@detect_bp.route('/detect/audio', methods=['GET'])
def detect_audio():
    """Detect available audio capture devices."""
    devices = []
    
    try:
        result = subprocess.run(
            ['arecord', '-l'],
            capture_output=True, text=True, timeout=5
        )
        
        for line in result.stdout.split('\n'):
            if line.startswith('card '):
                parts = line.split(':')
                if len(parts) >= 2:
                    card_num = parts[0].replace('card ', '').strip()
                    device_info = parts[1].strip()
                    devices.append({
                        'device': f'plughw:{card_num},0',
                        'name': device_info
                    })
    except:
        pass
    
    return jsonify({
        'success': True,
        'devices': devices
    })

# ============================================================================
# PLATFORM INFORMATION
# ============================================================================

@detect_bp.route('/platform', methods=['GET'])
def get_platform():
    """Get platform information."""
    return jsonify({
        'success': True,
        'platform': PLATFORM
    })

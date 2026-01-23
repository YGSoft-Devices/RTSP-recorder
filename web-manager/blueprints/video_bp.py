# -*- coding: utf-8 -*-
"""
Video Blueprint - Video preview and streaming routes
Version: 2.30.3
"""

import os
import time
import subprocess
import threading
from flask import Blueprint, request, jsonify, Response

from services.camera_service import find_camera_device
from services.config_service import load_config, get_service_status
from services.platform_service import run_command

video_bp = Blueprint('video', __name__, url_prefix='/api/video')

# ============================================================================
# GLOBAL STATE
# ============================================================================

preview_state = {
    'active': False,
    'process': None,
    'port': 8555,
    'lock': threading.Lock()
}

# ============================================================================
# PREVIEW ROUTES
# ============================================================================

@video_bp.route('/preview/status', methods=['GET'])
def preview_status():
    """Get video preview status."""
    with preview_state['lock']:
        return jsonify({
            'success': True,
            'active': preview_state['active'],
            'port': preview_state['port'] if preview_state['active'] else None
        })

@video_bp.route('/preview/start', methods=['POST'])
def start_preview():
    """Start video preview stream."""
    global preview_state
    
    with preview_state['lock']:
        if preview_state['active']:
            return jsonify({
                'success': True,
                'message': 'Preview already active',
                'port': preview_state['port']
            })
    
    data = request.get_json(silent=True) or {}
    port = data.get('port', 8555)
    resolution = data.get('resolution', '640x480')
    framerate = data.get('framerate', 15)
    
    # Find camera
    device = find_camera_device()
    if not device:
        return jsonify({
            'success': False,
            'error': 'No camera found'
        }), 404
    
    # Parse resolution
    width, height = resolution.split('x')
    
    # Build GStreamer pipeline for MJPEG over HTTP
    pipeline = (
        f"v4l2src device={device} ! "
        f"image/jpeg,width={width},height={height},framerate={framerate}/1 ! "
        f"jpegdec ! videoconvert ! "
        f"jpegenc quality=80 ! "
        f"multipartmux boundary=frame ! "
        f"tcpserversink host=0.0.0.0 port={port}"
    )
    
    try:
        process = subprocess.Popen(
            ['gst-launch-1.0', '-q'] + pipeline.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a moment to see if it starts
        time.sleep(1)
        
        if process.poll() is not None:
            stderr = process.stderr.read().decode()
            return jsonify({
                'success': False,
                'error': f'Failed to start preview: {stderr}'
            }), 500
        
        with preview_state['lock']:
            preview_state['active'] = True
            preview_state['process'] = process
            preview_state['port'] = port
        
        return jsonify({
            'success': True,
            'message': 'Preview started',
            'port': port,
            'url': f'http://localhost:{port}'
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@video_bp.route('/preview/stop', methods=['POST'])
def stop_preview():
    """Stop video preview stream."""
    global preview_state
    
    with preview_state['lock']:
        if not preview_state['active']:
            return jsonify({
                'success': True,
                'message': 'Preview not active'
            })
        
        if preview_state['process']:
            preview_state['process'].terminate()
            try:
                preview_state['process'].wait(timeout=5)
            except subprocess.TimeoutExpired:
                preview_state['process'].kill()
        
        preview_state['active'] = False
        preview_state['process'] = None
    
    return jsonify({
        'success': True,
        'message': 'Preview stopped'
    })

@video_bp.route('/preview/stream')
def preview_stream():
    """
    Stream live MJPEG preview of the camera.
    Query params:
    - source: 'camera' (direct) or 'rtsp' (via RTSP server) - auto-detected if service running
    - width: preview width (default 640)
    - height: preview height (default 480)
    - fps: frames per second (default 10)
    """
    source = request.args.get('source', 'auto')
    width = int(request.args.get('width', 640))
    height = int(request.args.get('height', 480))
    fps = int(request.args.get('fps', 10))
    
    config = load_config()
    device = config.get('VIDEO_DEVICE', '/dev/video0')
    
    # Auto-detect: use RTSP if service is running (camera is busy)
    rtsp_service_status = get_service_status()
    rtsp_running = rtsp_service_status.get('status') == 'active' if isinstance(rtsp_service_status, dict) else False
    
    if source == 'auto':
        source = 'rtsp' if rtsp_running else 'camera'
    
    rtsp_url = None
    if source == 'rtsp':
        # Build RTSP URL from config with optional auth
        rtsp_port = config.get('RTSP_PORT', '8554')
        rtsp_path = config.get('RTSP_PATH', 'stream')
        rtsp_user = config.get('RTSP_USER', '')
        rtsp_pass = config.get('RTSP_PASSWORD', '')
        
        if rtsp_user and rtsp_pass:
            rtsp_url = f"rtsp://{rtsp_user}:{rtsp_pass}@127.0.0.1:{rtsp_port}/{rtsp_path}"
        else:
            rtsp_url = f"rtsp://127.0.0.1:{rtsp_port}/{rtsp_path}"
    
    return Response(
        generate_mjpeg_stream(source, rtsp_url, device, width, height, fps),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


def generate_mjpeg_stream(source_type='camera', rtsp_url=None, device='/dev/video0', width=640, height=480, fps=10):
    """
    Generate MJPEG stream from camera or RTSP source using ffmpeg.
    Yields MJPEG frames in multipart format for browser display.
    """
    
    if source_type == 'rtsp' and rtsp_url:
        # Stream from RTSP source (relay the existing RTSP stream)
        cmd = [
            'ffmpeg',
            '-rtsp_transport', 'tcp',
            '-i', rtsp_url,
            '-f', 'mjpeg',
            '-q:v', '5',  # Quality (2-31, lower is better)
            '-r', str(fps),
            '-s', f'{width}x{height}',
            '-an',  # No audio
            '-'
        ]
    else:
        # Stream directly from camera device
        cmd = [
            'ffmpeg',
            '-f', 'v4l2',
            '-input_format', 'mjpeg',
            '-video_size', f'{width}x{height}',
            '-framerate', str(fps),
            '-i', device,
            '-f', 'mjpeg',
            '-q:v', '5',
            '-r', str(fps),
            '-'
        ]
    
    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # Suppress ffmpeg logs
            bufsize=10**6
        )
        
        # Read JPEG frames from ffmpeg output
        # MJPEG frames start with FFD8 and end with FFD9
        buffer = b''
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk
            
            # Find complete JPEG frames
            while True:
                start = buffer.find(b'\xff\xd8')
                if start == -1:
                    buffer = b''
                    break
                    
                end = buffer.find(b'\xff\xd9', start + 2)
                if end == -1:
                    buffer = buffer[start:]
                    break
                
                frame = buffer[start:end + 2]
                buffer = buffer[end + 2:]
                
                # Yield as multipart MJPEG
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                       
    except Exception as e:
        print(f"[Preview] Error in MJPEG stream: {e}")
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=2)
            except:
                process.kill()

# ============================================================================
# SNAPSHOT ROUTES
# ============================================================================

@video_bp.route('/snapshot', methods=['GET'])
def take_snapshot():
    """Take a snapshot from the camera."""
    device = find_camera_device()
    
    if not device:
        return jsonify({
            'success': False,
            'error': 'No camera found'
        }), 404
    
    # Create temporary file
    import tempfile
    fd, temp_path = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)
    
    try:
        # Use fswebcam or v4l2-ctl for snapshot
        result = run_command(
            f"fswebcam -d {device} --no-banner -r 1280x720 {temp_path}",
            timeout=10
        )
        
        if not result['success']:
            # Try with v4l2-ctl + ffmpeg
            result = run_command(
                f"ffmpeg -y -f v4l2 -i {device} -vframes 1 {temp_path}",
                timeout=10
            )
        
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            with open(temp_path, 'rb') as f:
                image_data = f.read()
            
            os.unlink(temp_path)
            
            return Response(
                image_data,
                mimetype='image/jpeg',
                headers={
                    'Content-Disposition': f'inline; filename=snapshot-{int(time.time())}.jpg'
                }
            )
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to capture snapshot'
            }), 500
    
    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@video_bp.route('/snapshot/save', methods=['POST'])
def save_snapshot():
    """Take a snapshot and save it to disk."""
    data = request.get_json(silent=True) or {}
    filename = data.get('filename', f'snapshot-{int(time.time())}.jpg')
    
    device = find_camera_device()
    
    if not device:
        return jsonify({
            'success': False,
            'error': 'No camera found'
        }), 404
    
    # Get snapshots directory from config
    config = load_config()
    snapshots_dir = config.get('SNAPSHOTS_DIR', '/var/snapshots')
    
    if not os.path.exists(snapshots_dir):
        os.makedirs(snapshots_dir, mode=0o755)
    
    filepath = os.path.join(snapshots_dir, filename)
    
    result = run_command(
        f"fswebcam -d {device} --no-banner -r 1920x1080 {filepath}",
        timeout=10
    )
    
    if not result['success'] or not os.path.exists(filepath):
        # Fallback to ffmpeg
        result = run_command(
            f"ffmpeg -y -f v4l2 -i {device} -vframes 1 {filepath}",
            timeout=10
        )
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return jsonify({
            'success': True,
            'message': 'Snapshot saved',
            'path': filepath,
            'filename': filename
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to save snapshot'
        }), 500

# ============================================================================
# STREAM INFO ROUTES
# ============================================================================

@video_bp.route('/stream/info', methods=['GET'])
def stream_info():
    """Get RTSP stream information."""
    config = load_config()
    
    port = config.get('RTSP_PORT', 8554)
    path = config.get('RTSP_PATH', '/stream')
    
    # Try to get local IP
    result = run_command("hostname -I | awk '{print $1}'", timeout=5)
    local_ip = result['stdout'].strip() if result['success'] else '127.0.0.1'
    
    return jsonify({
        'success': True,
        'rtsp_url': f'rtsp://{local_ip}:{port}{path}',
        'port': port,
        'path': path,
        'local_ip': local_ip
    })

@video_bp.route('/stream/test', methods=['GET'])
def test_stream():
    """Test if RTSP stream is accessible."""
    config = load_config()
    
    port = config.get('RTSP_PORT', 8554)
    path = config.get('RTSP_PATH', '/stream')
    
    # Use ffprobe to test stream
    rtsp_url = f'rtsp://127.0.0.1:{port}{path}'
    
    result = run_command(
        f'ffprobe -v quiet -show_streams -select_streams v:0 "{rtsp_url}"',
        timeout=10
    )
    
    if result['success'] and result['stdout']:
        return jsonify({
            'success': True,
            'accessible': True,
            'url': rtsp_url
        })
    else:
        return jsonify({
            'success': True,
            'accessible': False,
            'url': rtsp_url,
            'error': result['stderr'] or 'Stream not accessible'
        })

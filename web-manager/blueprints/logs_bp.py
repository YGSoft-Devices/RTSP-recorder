# -*- coding: utf-8 -*-
"""
Logs Blueprint - Log viewing and streaming routes
Version: 2.30.6

Note: This is a specialized blueprint for log streaming.
Basic log functionality is also in system_bp.
"""

from flask import Blueprint, request, jsonify, Response
import json
import time
import subprocess
import threading
import queue
import select

from services.system_service import get_recent_logs, get_service_logs
from config import SERVICE_NAME

logs_bp = Blueprint('logs', __name__, url_prefix='/api/logs')

# ============================================================================
# LOG RETRIEVAL ROUTES
# ============================================================================

@logs_bp.route('', methods=['GET'])
def get_logs():
    """Get recent log entries."""
    lines = request.args.get('lines', 100, type=int)
    source = request.args.get('source', 'all')
    
    logs_data = get_recent_logs(lines, source)
    
    return jsonify({
        'success': True,
        **logs_data
    })

@logs_bp.route('/service/<service_name>', methods=['GET'])
def service_logs(service_name):
    """Get logs for a specific service."""
    lines = request.args.get('lines', 50, type=int)
    since = request.args.get('since')
    
    result = get_service_logs(service_name, lines, since)
    
    return jsonify({
        'success': True,
        **result
    })

@logs_bp.route('/rtsp', methods=['GET'])
def rtsp_logs():
    """Get RTSP service logs."""
    lines = request.args.get('lines', 100, type=int)
    
    result = get_service_logs(SERVICE_NAME, lines)
    
    return jsonify({
        'success': True,
        **result
    })

@logs_bp.route('/webmanager', methods=['GET'])
def webmanager_logs():
    """Get web manager logs."""
    lines = request.args.get('lines', 100, type=int)
    
    result = get_service_logs('rpi-cam-webmanager', lines)
    
    return jsonify({
        'success': True,
        **result
    })

# ============================================================================
# LOG STREAMING ROUTES
# ============================================================================

@logs_bp.route('/stream', methods=['GET'])
def stream_logs():
    """Stream logs in real-time via Server-Sent Events."""
    
    def generate():
        # Send initial connection event with 20 recent logs
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')})}\n\n"
        
        # Start with 20 recent logs, then follow
        cmd = ['journalctl', '-f', '-n', '20', '--no-pager', '-o', 'short-iso', 
               '-u', SERVICE_NAME, '-u', 'rpi-cam-webmanager', '-u', 'rtsp-watchdog']
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Use select for non-blocking reads
            import select
            while True:
                ready = select.select([process.stdout], [], [], 1.0)
                if ready[0]:
                    line = process.stdout.readline()
                    if line:
                        yield f"data: {json.dumps({'log': line.rstrip(), 'source': 'journald'})}\n\n"
                    else:
                        break
                else:
                    # Send heartbeat every second to keep connection alive
                    yield f": heartbeat\n\n"
        
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        finally:
            if 'process' in locals():
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    process.kill()
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

@logs_bp.route('/stream/<service_name>', methods=['GET'])
def stream_service_logs(service_name):
    """Stream logs for a specific service."""
    def generate():
        yield f"data: {json.dumps({'type': 'connected', 'service': service_name})}\n\n"
        
        cmd = ['journalctl', '-u', service_name, '--follow', '--no-pager', '-o', 'cat']
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                log_entry = {
                    'source': service_name,
                    'message': line.strip(),
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
                }
                yield f"data: {json.dumps(log_entry)}\n\n"
        
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        finally:
            if 'process' in dir() and process:
                process.terminate()
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

# ============================================================================
# LOG MANAGEMENT ROUTES
# ============================================================================

@logs_bp.route('/clean', methods=['POST'])
def clean_logs():
    """Clean old logs."""
    from services.system_service import clean_old_logs
    
    data = request.get_json(silent=True) or {}
    max_size_mb = data.get('max_size_mb', 100)
    
    result = clean_old_logs(max_size_mb)
    
    return jsonify(result)

@logs_bp.route('/export', methods=['GET'])
def export_logs():
    """Export logs as downloadable file."""
    service = request.args.get('service')
    lines = request.args.get('lines', 1000, type=int)
    format_type = request.args.get('format', 'text')
    
    logs_data = get_recent_logs(lines, service or 'all')
    
    if format_type == 'json':
        return jsonify(logs_data)
    else:
        # Plain text format
        text_content = '\n'.join(
            f"[{log.get('source', 'unknown')}] {log.get('message', '')}"
            for log in logs_data.get('logs', [])
        )
        
        return Response(
            text_content,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename=logs-{time.strftime("%Y%m%d-%H%M%S")}.txt'
            }
        )

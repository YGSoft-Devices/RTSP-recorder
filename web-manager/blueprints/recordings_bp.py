# -*- coding: utf-8 -*-
"""
Recordings Blueprint - Recording management routes
Version: 2.30.6
"""

import os
import subprocess
from flask import Blueprint, request, jsonify, send_file, Response

from services.recording_service import (
    get_recordings_list, get_recording_info, delete_recording,
    delete_old_recordings, cleanup_recordings, get_disk_usage,
    get_recording_dir
)
from services.config_service import load_config
from services import media_cache_service
from config import THUMBNAIL_CACHE_DIR

recordings_bp = Blueprint('recordings', __name__, url_prefix='/api/recordings')

# ============================================================================
# RECORDING LIST ROUTES
# ============================================================================

@recordings_bp.route('', methods=['GET'])
def list_recordings():
    """Get list of all recordings."""
    # Parse query parameters - support .ts (MPEG-TS) and .mp4 by default
    pattern = request.args.get('pattern', '*.ts')
    sort_by = request.args.get('sort', 'date')
    reverse = request.args.get('reverse', 'true').lower() == 'true'
    limit = request.args.get('limit', type=int)
    
    config = load_config()
    recordings = get_recordings_list(config, pattern, sort_by, reverse)
    
    if limit:
        recordings = recordings[:limit]
    
    return jsonify({
        'success': True,
        'recordings': recordings,
        'count': len(recordings)
    })

@recordings_bp.route('/list', methods=['GET'])
def list_recordings_paginated():
    """Get list of recordings with pagination, filtering and sorting."""
    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    filter_type = request.args.get('filter', 'all')
    sort_by = request.args.get('sort', 'date-desc')
    search = request.args.get('search', '')
    
    config = load_config()
    
    # Determine sort parameters
    if sort_by == 'date-desc':
        sort_field, reverse = 'date', True
    elif sort_by == 'date-asc':
        sort_field, reverse = 'date', False
    elif sort_by == 'name-asc':
        sort_field, reverse = 'name', False
    elif sort_by == 'name-desc':
        sort_field, reverse = 'name', True
    elif sort_by == 'size-desc':
        sort_field, reverse = 'size', True
    elif sort_by == 'size-asc':
        sort_field, reverse = 'size', False
    else:
        sort_field, reverse = 'date', True
    
    # Get all recordings
    pattern = '*.mp4' if filter_type == 'mp4' else '*.ts' if filter_type == 'ts' else '*.*'
    all_recordings = get_recordings_list(config, pattern, sort_field, reverse)
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        all_recordings = [r for r in all_recordings if search_lower in r['name'].lower()]
    
    # Calculate pagination
    total = len(all_recordings)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total)
    
    # Get page slice
    page_recordings = all_recordings[start_idx:end_idx]
    
    # Transform recordings to add frontend-expected fields
    for rec in page_recordings:
        rec['size_display'] = rec.get('size_human', 'N/A')
        rec['duration_display'] = rec.get('duration_human', 'N/A')
        rec['modified_display'] = rec.get('modified', '')[:10] if rec.get('modified') else ''
        rec['modified_iso'] = rec.get('modified', '')
        rec['locked'] = False  # TODO: implement file locking
    
    # Calculate total size
    total_size = sum(r.get('size', 0) for r in all_recordings)
    
    # Get disk info
    disk = get_disk_usage(config)

    def parse_int(value, default=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
    
    # Format sizes for display
    def format_size(size_bytes):
        for unit in ['o', 'Ko', 'Mo', 'Go', 'To']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} Po"
    
    min_free_mb = max(0, parse_int(config.get('MIN_FREE_DISK_MB', 0)))
    max_disk_mb = max(0, parse_int(config.get('MAX_DISK_MB', 0)))
    min_free_bytes = min_free_mb * 1024 * 1024
    max_disk_bytes = max_disk_mb * 1024 * 1024
    available_bytes = disk.get('available', 0)
    usable_bytes = max(0, available_bytes - min_free_bytes) if min_free_bytes > 0 else available_bytes
    disk_full = min_free_bytes > 0 and available_bytes < min_free_bytes

    return jsonify({
        'success': True,
        'recordings': page_recordings,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_filtered': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'start_index': start_idx + 1,
            'end_index': end_idx
        },
        'total_size_display': format_size(total_size),
        'disk_info': {
            'total': disk.get('total', 0),
            'used': disk.get('used', 0),
            'available': disk.get('available', 0),
            'total_display': format_size(disk.get('total', 0)),
            'used_display': format_size(disk.get('used', 0)),
            'available_display': format_size(disk.get('available', 0)),
            'percent': disk.get('percent', 0)
        },
        'storage_info': {
            'usable_bytes': usable_bytes,
            'usable_display': format_size(usable_bytes),
            'min_free_bytes': min_free_bytes,
            'min_free_display': format_size(min_free_bytes),
            'max_disk_bytes': max_disk_bytes,
            'max_disk_display': format_size(max_disk_bytes) if max_disk_bytes > 0 else 'Illimité',
            'max_disk_enabled': max_disk_bytes > 0,
            'recordings_size_bytes': total_size,
            'recordings_size_display': format_size(total_size),
            'disk_full': disk_full
        }
    })

@recordings_bp.route('/recent', methods=['GET'])
def recent_recordings():
    """Get most recent recordings."""
    limit = request.args.get('limit', 10, type=int)
    config = load_config()
    
    recordings = get_recordings_list(config, sort_by='date', reverse=True)
    
    return jsonify({
        'success': True,
        'recordings': recordings[:limit],
        'count': len(recordings)
    })

# ============================================================================
# SINGLE RECORDING ROUTES
# ============================================================================

@recordings_bp.route('/info/<path:filename>', methods=['GET'])
def get_recording_info_route(filename):
    """Get information about a specific recording (frontend-compatible route)."""
    config = load_config()
    record_dir = get_recording_dir(config)
    filepath = os.path.join(record_dir, filename)
    
    info = get_recording_info(filepath)
    
    if 'error' in info:
        return jsonify({
            'success': False,
            'error': info['error']
        }), 404
    
    return jsonify({
        'success': True,
        **info
    })

@recordings_bp.route('/<path:filename>', methods=['GET'])
def get_recording(filename):
    """Get information about a specific recording."""
    config = load_config()
    record_dir = get_recording_dir(config)
    filepath = os.path.join(record_dir, filename)
    
    info = get_recording_info(filepath)
    
    if 'error' in info:
        return jsonify({
            'success': False,
            'error': info['error']
        }), 404
    
    return jsonify({
        'success': True,
        **info
    })

@recordings_bp.route('/<path:filename>', methods=['DELETE'])
def remove_recording(filename):
    """Delete a specific recording."""
    config = load_config()
    record_dir = get_recording_dir(config)
    filepath = os.path.join(record_dir, filename)
    
    result = delete_recording(filepath, config)
    
    status_code = 200 if result['success'] else 404
    return jsonify(result), status_code

@recordings_bp.route('/download/<path:filename>', methods=['GET'])
def download_recording_route(filename):
    """Download a recording file (frontend-compatible route)."""
    return _serve_recording_file(filename, as_attachment=True)

@recordings_bp.route('/<path:filename>/download', methods=['GET'])
def download_recording(filename):
    """Download a recording file."""
    return _serve_recording_file(filename, as_attachment=True)

@recordings_bp.route('/stream/<path:filename>', methods=['GET'])
def stream_recording_route(filename):
    """Stream a recording for playback (frontend-compatible route)."""
    return _serve_recording_file(filename, as_attachment=False)

@recordings_bp.route('/<path:filename>/stream', methods=['GET'])
def stream_recording(filename):
    """Stream a recording for playback."""
    return _serve_recording_file(filename, as_attachment=False)

def _serve_recording_file(filename, as_attachment=False):
    """Internal helper to serve recording files."""
    config = load_config()
    record_dir = get_recording_dir(config)
    filepath = os.path.join(record_dir, filename)
    
    # Security check
    real_path = os.path.realpath(filepath)
    real_record_dir = os.path.realpath(record_dir)
    
    if not real_path.startswith(real_record_dir):
        return jsonify({
            'success': False,
            'error': 'Access denied'
        }), 403
    
    if not os.path.exists(filepath):
        return jsonify({
            'success': False,
            'error': 'File not found'
        }), 404
    
    # Determine mime type
    ext = os.path.splitext(filename)[1].lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo',
        '.webm': 'video/webm',
        '.ts': 'video/mp2t'
    }
    mime_type = mime_types.get(ext, 'application/octet-stream')
    
    if as_attachment:
        return send_file(
            filepath,
            as_attachment=True,
            download_name=os.path.basename(filename)
        )
    else:
        return send_file(filepath, mimetype=mime_type)

# ============================================================================
# BULK OPERATIONS ROUTES
# ============================================================================

@recordings_bp.route('/delete', methods=['POST'])
@recordings_bp.route('/delete-multiple', methods=['POST'])
def delete_multiple_recordings():
    """Delete multiple recordings."""
    data = request.get_json(silent=True) or {}
    
    if not data or 'files' not in data:
        return jsonify({
            'success': False,
            'error': 'files array required'
        }), 400
    
    config = load_config()
    record_dir = get_recording_dir(config)
    
    results = {
        'deleted': [],
        'failed': []
    }
    
    for filename in data['files']:
        filepath = os.path.join(record_dir, filename)
        result = delete_recording(filepath, config)
        
        if result['success']:
            results['deleted'].append(filename)
        else:
            results['failed'].append({
                'file': filename,
                'error': result['message']
            })
    
    return jsonify({
        'success': len(results['failed']) == 0,
        **results
    })

@recordings_bp.route('/cleanup/old', methods=['POST'])
def cleanup_old_recordings():
    """Delete recordings older than specified days."""
    data = request.get_json(silent=True) or {}
    max_age_days = data.get('max_age_days', 30)
    
    config = load_config()
    result = delete_old_recordings(max_age_days, config)
    
    return jsonify(result)

@recordings_bp.route('/cleanup/size', methods=['POST'])
def cleanup_by_size():
    """Cleanup recordings to stay under size limit."""
    data = request.get_json(silent=True) or {}
    max_size_gb = data.get('max_size_gb')
    max_count = data.get('max_count')
    
    if not max_size_gb and not max_count:
        return jsonify({
            'success': False,
            'error': 'max_size_gb or max_count required'
        }), 400
    
    config = load_config()
    result = cleanup_recordings(max_size_gb, max_count, config)
    
    return jsonify(result)

# ============================================================================
# DISK USAGE ROUTES
# ============================================================================

@recordings_bp.route('/disk', methods=['GET'])
def disk_usage():
    """Get disk usage information for recordings."""
    config = load_config()
    usage = get_disk_usage(config)
    
    return jsonify({
        'success': True,
        **usage
    })

@recordings_bp.route('/stats', methods=['GET'])
def recording_stats():
    """Get recording statistics."""
    config = load_config()
    recordings = get_recordings_list(config, pattern='*.ts')
    usage = get_disk_usage(config)
    
    # Calculate stats
    total_size = sum(r['size'] for r in recordings)
    total_duration = sum(r.get('duration') or 0 for r in recordings)
    
    return jsonify({
        'success': True,
        'count': len(recordings),
        'total_size': total_size,
        'total_size_human': usage['recordings_size_human'],
        'total_duration': total_duration,
        'disk': {
            'total': usage['total'],
            'available': usage['available'],
            'percent_used': usage['percent']
        }
    })

# ============================================================================
# THUMBNAIL ROUTES (Using Media Cache)
# ============================================================================

def is_valid_recording_filename(filename):
    """Check if filename is a valid recording filename (security)."""
    if not filename:
        return False
    # Must end with valid video extension
    valid_extensions = ('.ts', '.mp4', '.mkv', '.avi', '.mov')
    if not filename.lower().endswith(valid_extensions):
        return False
    # No path traversal
    if '..' in filename or filename.startswith('/'):
        return False
    return True

@recordings_bp.route('/thumbnail/<path:filename>', methods=['GET'])
def get_thumbnail(filename):
    """
    Get thumbnail for a recording (cached).
    
    Thumbnails are cached in SQLite database and generated in background.
    This endpoint returns immediately if cached, or queues generation.
    """
    try:
        # Security: validate filename
        if not is_valid_recording_filename(filename):
            return jsonify({'success': False, 'message': 'Invalid filename'}), 400
        
        config = load_config()
        record_dir = get_recording_dir(config)
        video_path = os.path.join(record_dir, filename)
        
        if not os.path.exists(video_path):
            return jsonify({'success': False, 'message': 'File not found'}), 404
        
        try:
            thumb_path = media_cache_service.get_thumbnail_path(filename)
            video_mtime = os.path.getmtime(video_path)

            # If we already have a thumbnail, return it immediately (even if stale),
            # and refresh in background when needed.
            if os.path.exists(thumb_path):
                thumb_mtime = os.path.getmtime(thumb_path)
                if thumb_mtime < video_mtime:
                    worker = media_cache_service.get_thumbnail_worker()
                    worker.enqueue(video_path)

                return send_file(
                    thumb_path,
                    mimetype='image/jpeg',
                    as_attachment=False
                )

            # Thumbnail missing: queue generation in background (deduplicated)
            worker = media_cache_service.get_thumbnail_worker()
            worker.enqueue(video_path)

            # Do not generate synchronously: it can spawn N ffmpeg processes when the UI loads,
            # which can destabilize RTSP on Pi 3B+.
            return Response('', status=202, mimetype='text/plain', headers={'Retry-After': '2'})
        
        except Exception as e:
            print(f"[Recordings] Error in get_thumbnail: {str(e)}")
            return jsonify({'success': False, 'message': f'Thumbnail error: {str(e)}'}), 400
        
    except Exception as e:
        print(f"[Recordings] Error in get_thumbnail outer: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@recordings_bp.route('/thumbnails/generate', methods=['POST'])
def generate_thumbnails():
    """
    Batch generate thumbnails for all recordings.
    
    This queues all missing thumbnails for background generation.
    """
    try:
        config = load_config()
        record_dir = get_recording_dir(config)
        
        # Scan directory and queue thumbnail generation
        results = media_cache_service.scan_and_cache_directory(record_dir, pattern='*.ts')
        
        return jsonify({
            'success': True,
            'scanned': results['scanned'],
            'cached': results['cached'],
            'thumbnails_queued': results['thumbnails_queued'],
            'errors': results['errors']
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ============================================================================
# CACHE MANAGEMENT ROUTES
# ============================================================================

@recordings_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """Get media cache statistics."""
    try:
        stats = media_cache_service.get_cache_stats()
        return jsonify({
            'success': True,
            **stats
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@recordings_bp.route('/cache/refresh', methods=['POST'])
def refresh_cache():
    """
    Refresh the media cache.
    
    Scans the recordings directory and updates metadata cache.
    Queues missing thumbnails for background generation.
    """
    try:
        config = load_config()
        record_dir = get_recording_dir(config)
        
        # Clean up stale entries first
        cleanup_results = media_cache_service.cleanup_stale_cache(record_dir)
        
        # Scan and cache new files
        scan_results = media_cache_service.scan_and_cache_directory(record_dir, pattern='*.*')
        
        return jsonify({
            'success': True,
            'cleanup': cleanup_results,
            'scan': scan_results
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@recordings_bp.route('/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """Remove cache entries for deleted files."""
    try:
        config = load_config()
        record_dir = get_recording_dir(config)
        
        results = media_cache_service.cleanup_stale_cache(record_dir)
        
        return jsonify({
            'success': True,
            **results
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

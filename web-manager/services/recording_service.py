# -*- coding: utf-8 -*-
"""
Recording Service - Recording management and disk usage
Version: 2.30.2
"""

import os
import re
import json
import glob
from datetime import datetime

from .platform_service import run_command
from config import DEFAULT_CONFIG

# Lazy import to avoid circular dependency
_media_cache = None

def _get_media_cache():
    """Lazy load media cache service."""
    global _media_cache
    if _media_cache is None:
        try:
            from . import media_cache_service
            _media_cache = media_cache_service
        except ImportError:
            _media_cache = False  # Mark as unavailable
    return _media_cache if _media_cache else None

# ============================================================================
# RECORDING DIRECTORY MANAGEMENT
# ============================================================================

def get_recording_dir(config=None):
    """
    Get the recording directory path.
    
    Args:
        config: Configuration dict (will load if None)
    
    Returns:
        str: Path to recording directory
    """
    if config is None:
        from .config_service import load_config
        config = load_config()
    
    return config.get('RECORD_DIR', DEFAULT_CONFIG.get('RECORD_DIR', '/var/recordings'))

def ensure_recording_dir(config=None):
    """
    Ensure the recording directory exists with proper permissions.
    
    Args:
        config: Configuration dict
    
    Returns:
        dict: {success: bool, path: str, message: str}
    """
    record_dir = get_recording_dir(config)
    
    try:
        if not os.path.exists(record_dir):
            os.makedirs(record_dir, mode=0o755)
        
        return {
            'success': True,
            'path': record_dir,
            'message': f'Recording directory ready: {record_dir}'
        }
    except Exception as e:
        return {
            'success': False,
            'path': record_dir,
            'message': str(e)
        }

# ============================================================================
# RECORDING LISTING
# ============================================================================

def get_recordings_list(config=None, pattern='*.ts', sort_by='date', reverse=True, skip_metadata=False):
    """
    Get list of all recordings.
    
    Uses SQLite cache for metadata to reduce ffprobe calls and SD card wear.
    
    Args:
        config: Configuration dict
        pattern: Glob pattern for files (default: *.ts for MPEG-TS)
        sort_by: Sort field ('date', 'name', 'size')
        reverse: Reverse sort order (newest first by default)
        skip_metadata: If True, only return basic file info (faster)
    
    Returns:
        list: List of recording dicts with name, path, size, date, duration
    """
    record_dir = get_recording_dir(config)
    recordings = []
    
    if not os.path.exists(record_dir):
        return recordings
    
    # Find all matching files
    search_pattern = os.path.join(record_dir, '**', pattern)
    files = glob.glob(search_pattern, recursive=True)
    
    # Get media cache service (if available)
    media_cache = _get_media_cache()
    
    for filepath in files:
        try:
            stat = os.stat(filepath)
            
            recording = {
                'name': os.path.basename(filepath),
                'path': filepath,
                'relative_path': os.path.relpath(filepath, record_dir),
                'size': stat.st_size,
                'size_human': format_size(stat.st_size),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'duration': None,
                'resolution': None
            }
            
            # Try to get video metadata (from cache only for speed, or full extraction if not skipping)
            metadata = None
            if not skip_metadata:
                if media_cache:
                    # Try cache first (fast), only extract if not in cache
                    cached = media_cache.get_cached_metadata(filepath)
                    if cached:
                        metadata = cached
                    else:
                        # Queue for background extraction, don't block
                        worker = media_cache.get_thumbnail_worker()
                        worker.enqueue(filepath)
                else:
                    metadata = get_video_metadata(filepath)
            
            if metadata:
                recording['duration'] = metadata.get('duration')
                recording['duration_human'] = format_duration(metadata.get('duration'))
                recording['resolution'] = metadata.get('resolution')
                recording['codec'] = metadata.get('codec')
            
            recordings.append(recording)
        
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            continue
    
    # Sort recordings
    if sort_by == 'date':
        recordings.sort(key=lambda x: x['modified'], reverse=reverse)
    elif sort_by == 'name':
        recordings.sort(key=lambda x: x['name'], reverse=reverse)
    elif sort_by == 'size':
        recordings.sort(key=lambda x: x['size'], reverse=reverse)
    
    return recordings

def get_recording_info(filepath):
    """
    Get detailed information about a specific recording.
    
    Args:
        filepath: Path to the recording file
    
    Returns:
        dict: Recording information or error
    """
    if not os.path.exists(filepath):
        return {'error': 'File not found'}
    
    try:
        stat = os.stat(filepath)
        
        info = {
            'name': os.path.basename(filepath),
            'path': filepath,
            'size': stat.st_size,
            'size_human': format_size(stat.st_size),
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }
        
        # Get video metadata
        metadata = get_video_metadata(filepath)
        if metadata:
            info.update(metadata)
        
        return info
    
    except Exception as e:
        return {'error': str(e)}

def get_video_metadata(filepath):
    """
    Extract video metadata using ffprobe.
    
    Args:
        filepath: Path to video file
    
    Returns:
        dict: Video metadata or None
    """
    result = run_command(
        f'ffprobe -v quiet -print_format json -show_format -show_streams "{filepath}"',
        timeout=30
    )
    
    if not result['success']:
        return None
    
    try:
        data = json.loads(result['stdout'])
        
        metadata = {
            'duration': None,
            'resolution': None,
            'codec': None,
            'bitrate': None,
            'fps': None
        }
        
        # Get format info
        if 'format' in data:
            fmt = data['format']
            if 'duration' in fmt:
                metadata['duration'] = float(fmt['duration'])
            if 'bit_rate' in fmt:
                metadata['bitrate'] = int(fmt['bit_rate'])
        
        # Get video stream info
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                metadata['codec'] = stream.get('codec_name')
                
                width = stream.get('width')
                height = stream.get('height')
                if width and height:
                    metadata['resolution'] = f"{width}x{height}"
                
                # Parse frame rate
                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    if int(den) > 0:
                        metadata['fps'] = round(int(num) / int(den), 2)
                
                break
        
        return metadata
    
    except Exception as e:
        print(f"Error parsing video metadata: {e}")
        return None

# ============================================================================
# RECORDING MANAGEMENT
# ============================================================================

def delete_recording(filepath, config=None):
    """
    Delete a recording file.
    
    Also removes associated cache entries and thumbnail.
    
    Args:
        filepath: Path to the recording
        config: Configuration dict (for validation)
    
    Returns:
        dict: {success: bool, message: str}
    """
    # Security check - ensure path is within recording directory
    record_dir = get_recording_dir(config)
    
    try:
        real_path = os.path.realpath(filepath)
        real_record_dir = os.path.realpath(record_dir)
        
        if not real_path.startswith(real_record_dir):
            return {
                'success': False,
                'message': 'Access denied: path outside recording directory'
            }
        
        if not os.path.exists(filepath):
            return {
                'success': False,
                'message': 'File not found'
            }
        
        os.remove(filepath)
        
        # Invalidate cache entry and thumbnail
        media_cache = _get_media_cache()
        if media_cache:
            media_cache.invalidate_cache(filepath)
        
        return {
            'success': True,
            'message': f'Recording deleted: {os.path.basename(filepath)}'
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

def delete_old_recordings(max_age_days=30, config=None):
    """
    Delete recordings older than a specified age.
    
    Args:
        max_age_days: Maximum age in days
        config: Configuration dict
    
    Returns:
        dict: {success: bool, deleted_count: int, freed_space: int}
    """
    from datetime import timedelta
    
    record_dir = get_recording_dir(config)
    cutoff = datetime.now() - timedelta(days=max_age_days)
    
    deleted_count = 0
    freed_space = 0
    
    recordings = get_recordings_list(config)
    
    for rec in recordings:
        try:
            modified = datetime.fromisoformat(rec['modified'])
            if modified < cutoff:
                size = rec['size']
                result = delete_recording(rec['path'], config)
                if result['success']:
                    deleted_count += 1
                    freed_space += size
        except Exception as e:
            print(f"Error processing {rec['name']}: {e}")
            continue
    
    return {
        'success': True,
        'deleted_count': deleted_count,
        'freed_space': freed_space,
        'freed_space_human': format_size(freed_space)
    }

def cleanup_recordings(max_size_gb=None, max_count=None, config=None):
    """
    Cleanup recordings based on total size or count limits.
    
    Args:
        max_size_gb: Maximum total size in GB
        max_count: Maximum number of recordings
        config: Configuration dict
    
    Returns:
        dict: Cleanup results
    """
    recordings = get_recordings_list(config, sort_by='date', reverse=False)  # Oldest first
    
    if not recordings:
        return {'success': True, 'deleted_count': 0, 'message': 'No recordings found'}
    
    deleted_count = 0
    freed_space = 0
    
    # Calculate current totals
    total_size = sum(r['size'] for r in recordings)
    total_count = len(recordings)
    
    # Delete oldest recordings if over limit
    max_size_bytes = (max_size_gb * 1024 * 1024 * 1024) if max_size_gb else None
    
    for rec in recordings:
        should_delete = False
        
        if max_size_bytes and total_size > max_size_bytes:
            should_delete = True
        
        if max_count and total_count > max_count:
            should_delete = True
        
        if not should_delete:
            break
        
        result = delete_recording(rec['path'], config)
        if result['success']:
            deleted_count += 1
            freed_space += rec['size']
            total_size -= rec['size']
            total_count -= 1
    
    return {
        'success': True,
        'deleted_count': deleted_count,
        'freed_space': freed_space,
        'freed_space_human': format_size(freed_space),
        'remaining_count': total_count,
        'remaining_size': total_size,
        'remaining_size_human': format_size(total_size)
    }

# ============================================================================
# DISK USAGE
# ============================================================================

def get_disk_usage(config=None):
    """
    Get disk usage information for the recording directory.
    
    Args:
        config: Configuration dict
    
    Returns:
        dict: Disk usage information
    """
    record_dir = get_recording_dir(config)
    
    # Get overall disk usage
    result = run_command(f"df -B1 '{record_dir}'", timeout=5)
    
    disk_info = {
        'path': record_dir,
        'total': 0,
        'used': 0,
        'available': 0,
        'percent': 0,
        'recordings_size': 0,
        'recordings_count': 0
    }
    
    if result['success']:
        lines = result['stdout'].split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 4:
                disk_info['total'] = int(parts[1])
                disk_info['used'] = int(parts[2])
                disk_info['available'] = int(parts[3])
                disk_info['percent'] = int(parts[4].rstrip('%')) if '%' in parts[4] else 0
    
    # Calculate recordings size
    recordings = get_recordings_list(config)
    disk_info['recordings_count'] = len(recordings)
    disk_info['recordings_size'] = sum(r['size'] for r in recordings)
    
    # Add human-readable sizes
    disk_info['total_human'] = format_size(disk_info['total'])
    disk_info['used_human'] = format_size(disk_info['used'])
    disk_info['available_human'] = format_size(disk_info['available'])
    disk_info['recordings_size_human'] = format_size(disk_info['recordings_size'])
    
    return disk_info

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_size(bytes_size):
    """
    Format bytes into human-readable string.
    
    Args:
        bytes_size: Size in bytes
    
    Returns:
        str: Formatted size string (e.g., "1.5 GB")
    """
    if bytes_size is None:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_size) < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    
    return f"{bytes_size:.1f} PB"

def format_duration(seconds):
    """
    Format seconds into human-readable duration.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        str: Formatted duration (e.g., "1h 30m 45s")
    """
    if seconds is None:
        return "0s"
    
    seconds = int(seconds)
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)

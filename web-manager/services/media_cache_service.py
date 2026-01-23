# -*- coding: utf-8 -*-
"""
Media Cache Service - SQLite-based caching for recordings metadata and thumbnails
Version: 1.0.1

This service optimizes the recordings gallery by:
1. Caching video metadata (duration, resolution, codec) in SQLite
2. Managing thumbnail generation with background workers
3. Invalidating cache entries when files change
4. Reducing SD card wear by minimizing ffprobe calls
"""

import os
import sys
import json
import sqlite3
import hashlib
import threading
import subprocess
import shutil
from datetime import datetime
from queue import Queue, Empty
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

from config import THUMBNAIL_CACHE_DIR

# ============================================================================
# CONFIGURATION
# ============================================================================

# Database path
MEDIA_CACHE_DB = '/var/cache/rpi-cam/media_cache.db'

# Thumbnail settings
THUMBNAIL_WIDTH = 320
THUMBNAIL_QUALITY = 3  # ffmpeg quality (1-31, lower is better)
THUMBNAIL_SEEK_TIME = 2  # seconds into video

# Background worker settings
MAX_QUEUE_SIZE = 100
WORKER_TIMEOUT = 30  # seconds per thumbnail generation

# ============================================================================
# PROCESS PRIORITIES (CPU/IO FRIENDLY)
# ============================================================================

def _wrap_low_priority(cmd: List[str]) -> List[str]:
    """
    Wrap a command with best-effort low CPU/IO priority on Linux.

    This helps reduce the impact of background thumbnail/metadata work on RTSP streaming.
    """
    if not cmd:
        return cmd

    ionice = shutil.which('ionice')
    nice = shutil.which('nice')

    wrapped = cmd
    if nice:
        wrapped = [nice, '-n', '10', *wrapped]
    if ionice:
        wrapped = [ionice, '-c', '3', *wrapped]

    return wrapped

# ============================================================================
# DATABASE SCHEMA
# ============================================================================

SCHEMA_VERSION = 1
SCHEMA_SQL = """
-- Media metadata cache
CREATE TABLE IF NOT EXISTS media_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_mtime REAL NOT NULL,
    duration REAL,
    duration_human TEXT,
    resolution TEXT,
    width INTEGER,
    height INTEGER,
    codec TEXT,
    bitrate INTEGER,
    fps REAL,
    has_audio INTEGER DEFAULT 0,
    thumbnail_path TEXT,
    thumbnail_generated INTEGER DEFAULT 0,
    metadata_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_media_filepath ON media_cache(filepath);
CREATE INDEX IF NOT EXISTS idx_media_filename ON media_cache(filename);
CREATE INDEX IF NOT EXISTS idx_media_mtime ON media_cache(file_mtime DESC);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""

# ============================================================================
# DATABASE CONNECTION MANAGEMENT
# ============================================================================

_db_lock = threading.Lock()

@contextmanager
def get_db_connection():
    """Thread-safe database connection context manager."""
    conn = None
    try:
        # Ensure directory exists
        db_dir = os.path.dirname(MEDIA_CACHE_DB)
        os.makedirs(db_dir, exist_ok=True)
        
        conn = sqlite3.connect(MEDIA_CACHE_DB, timeout=10)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        yield conn
    finally:
        if conn:
            conn.close()

def init_database():
    """Initialize the database schema."""
    with get_db_connection() as conn:
        with _db_lock:
            # Check schema version
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            if not cursor.fetchone():
                # Fresh install - create schema
                conn.executescript(SCHEMA_SQL)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
                conn.commit()
                print(f"[MediaCache] Database initialized (version {SCHEMA_VERSION})")
            else:
                # Check for migrations
                cursor = conn.execute("SELECT version FROM schema_version")
                row = cursor.fetchone()
                current_version = row['version'] if row else 0
                
                if current_version < SCHEMA_VERSION:
                    # Run migrations here if needed
                    conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
                    conn.commit()
                    print(f"[MediaCache] Database migrated to version {SCHEMA_VERSION}")

# ============================================================================
# METADATA EXTRACTION
# ============================================================================

def extract_video_metadata(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Extract video metadata using ffprobe.
    
    Args:
        filepath: Path to video file
        
    Returns:
        Dict with metadata or None on error
    """
    if not os.path.exists(filepath):
        return None
    
    try:
        # Use shorter timeout (10s) and only read first few seconds of file
        result = subprocess.run(
            _wrap_low_priority([
                'ffprobe', '-v', 'quiet',
                '-read_intervals', '%+5',  # Only analyze first 5 seconds
                '-print_format', 'json',
                '-show_format', '-show_streams',
                filepath
            ]),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return None
        
        data = json.loads(result.stdout)
        
        metadata = {
            'duration': None,
            'resolution': None,
            'width': None,
            'height': None,
            'codec': None,
            'bitrate': None,
            'fps': None,
            'has_audio': False
        }
        
        # Get format info
        if 'format' in data:
            fmt = data['format']
            if 'duration' in fmt:
                metadata['duration'] = float(fmt['duration'])
            if 'bit_rate' in fmt:
                metadata['bitrate'] = int(fmt['bit_rate'])
        
        # Get stream info
        for stream in data.get('streams', []):
            codec_type = stream.get('codec_type')
            
            if codec_type == 'video' and metadata['codec'] is None:
                metadata['codec'] = stream.get('codec_name')
                metadata['width'] = stream.get('width')
                metadata['height'] = stream.get('height')
                
                if metadata['width'] and metadata['height']:
                    metadata['resolution'] = f"{metadata['width']}x{metadata['height']}"
                
                # Parse frame rate
                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    if int(den) > 0:
                        metadata['fps'] = round(int(num) / int(den), 2)
            
            elif codec_type == 'audio':
                metadata['has_audio'] = True
        
        # Human-readable duration
        if metadata['duration']:
            metadata['duration_human'] = format_duration(metadata['duration'])
        
        return metadata
        
    except Exception as e:
        print(f"[MediaCache] Error extracting metadata from {filepath}: {e}")
        return None

def format_duration(seconds: Optional[float]) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if seconds is None:
        return 'N/A'
    
    try:
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    except:
        return 'N/A'

# ============================================================================
# THUMBNAIL GENERATION
# ============================================================================

def get_thumbnail_path(filename: str) -> str:
    """Get the cache path for a thumbnail."""
    # Use hash to handle special characters in filename
    safe_name = os.path.splitext(filename)[0]
    thumb_name = f"{safe_name}.jpg"
    return os.path.join(THUMBNAIL_CACHE_DIR, thumb_name)

def generate_thumbnail(video_path: str, thumb_path: str, seek_time: int = THUMBNAIL_SEEK_TIME) -> bool:
    """
    Generate a thumbnail from a video file.
    
    Args:
        video_path: Path to source video
        thumb_path: Path to save thumbnail
        seek_time: Seconds to seek before capturing frame
        
    Returns:
        True if successful
    """
    if not os.path.exists(video_path):
        return False
    
    try:
        # Create directory if needed
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        
        # Use ffmpeg to extract a frame
        result = subprocess.run(
            _wrap_low_priority([
                'ffmpeg', '-y',
                '-ss', str(seek_time),
                '-i', video_path,
                '-vframes', '1',
                '-vf', f'scale={THUMBNAIL_WIDTH}:-1',
                '-q:v', str(THUMBNAIL_QUALITY),
                thumb_path
            ]),
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT
        )
        
        if result.returncode == 0 and os.path.exists(thumb_path):
            return True
        
        # If seeking failed (short video), try at frame 0
        if seek_time > 0:
            return generate_thumbnail(video_path, thumb_path, seek_time=0)
        
        return False
        
    except subprocess.TimeoutExpired:
        print(f"[MediaCache] Thumbnail generation timed out for {video_path}")
        return False
    except Exception as e:
        print(f"[MediaCache] Error generating thumbnail: {e}")
        return False

# ============================================================================
# CACHE OPERATIONS
# ============================================================================

def get_cached_metadata(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Get cached metadata for a file, or None if not cached/stale.
    
    Args:
        filepath: Path to video file
        
    Returns:
        Dict with metadata or None
    """
    if not os.path.exists(filepath):
        return None
    
    try:
        file_mtime = os.path.getmtime(filepath)
        
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM media_cache WHERE filepath = ?",
                (filepath,)
            )
            row = cursor.fetchone()
            
            if row and row['file_mtime'] >= file_mtime:
                # Cache is valid
                return dict(row)
            
        return None
        
    except Exception as e:
        print(f"[MediaCache] Error getting cached metadata: {e}")
        return None

def cache_metadata(filepath: str, metadata: Dict[str, Any]) -> bool:
    """
    Store metadata in cache.
    
    Args:
        filepath: Path to video file
        metadata: Metadata dict to cache
        
    Returns:
        True if successful
    """
    if not os.path.exists(filepath):
        return False
    
    try:
        stat = os.stat(filepath)
        filename = os.path.basename(filepath)
        thumb_path = get_thumbnail_path(filename)
        
        with get_db_connection() as conn:
            with _db_lock:
                conn.execute("""
                    INSERT OR REPLACE INTO media_cache (
                        filepath, filename, file_size, file_mtime,
                        duration, duration_human, resolution, width, height,
                        codec, bitrate, fps, has_audio, thumbnail_path,
                        thumbnail_generated, metadata_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    filepath,
                    filename,
                    stat.st_size,
                    stat.st_mtime,
                    metadata.get('duration'),
                    metadata.get('duration_human'),
                    metadata.get('resolution'),
                    metadata.get('width'),
                    metadata.get('height'),
                    metadata.get('codec'),
                    metadata.get('bitrate'),
                    metadata.get('fps'),
                    1 if metadata.get('has_audio') else 0,
                    thumb_path,
                    1 if os.path.exists(thumb_path) else 0,
                    json.dumps(metadata),
                    datetime.now().isoformat()
                ))
                conn.commit()
        
        return True
        
    except Exception as e:
        print(f"[MediaCache] Error caching metadata: {e}")
        return False

def get_or_extract_metadata(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata from cache, or extract and cache it.
    
    Args:
        filepath: Path to video file
        
    Returns:
        Metadata dict or None
    """
    # Try cache first
    cached = get_cached_metadata(filepath)
    if cached:
        return cached
    
    # Extract fresh metadata
    metadata = extract_video_metadata(filepath)
    if metadata:
        cache_metadata(filepath, metadata)
        return metadata
    
    return None

def invalidate_cache(filepath: str) -> bool:
    """Remove a file from cache (e.g., when deleted)."""
    try:
        with get_db_connection() as conn:
            with _db_lock:
                conn.execute("DELETE FROM media_cache WHERE filepath = ?", (filepath,))
                conn.commit()
        
        # Also remove thumbnail
        filename = os.path.basename(filepath)
        thumb_path = get_thumbnail_path(filename)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        return True
        
    except Exception as e:
        print(f"[MediaCache] Error invalidating cache: {e}")
        return False

def get_all_cached() -> List[Dict[str, Any]]:
    """Get all cached entries (for bulk listing)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM media_cache ORDER BY file_mtime DESC"
            )
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[MediaCache] Error getting all cached: {e}")
        return []

# ============================================================================
# BACKGROUND MEDIA WORKER
# ============================================================================

class ThumbnailWorker:
    """Background worker for generating thumbnails and extracting metadata without blocking requests."""
    
    def __init__(self):
        self.queue = Queue(maxsize=MAX_QUEUE_SIZE)
        self.worker_thread = None
        self.running = False
        self.processed_count = 0
        self.metadata_count = 0
        self.error_count = 0
        self._lock = threading.Lock()
        self._enqueued = set()
        self._in_progress = set()
    
    def start(self):
        """Start the background worker thread."""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        print("[MediaCache] Thumbnail worker started")
    
    def stop(self):
        """Stop the background worker."""
        self.running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5)
        print("[MediaCache] Thumbnail worker stopped")
    
    def enqueue(self, video_path: str, priority: bool = False):
        """
        Add a video to the thumbnail generation queue.
        
        Args:
            video_path: Path to video file
            priority: If True, process sooner (not implemented yet)
        """
        if not self.running:
            self.start()
        
        try:
            with self._lock:
                if video_path in self._enqueued or video_path in self._in_progress:
                    return
                self._enqueued.add(video_path)
            self.queue.put_nowait(video_path)
        except:
            # Queue full - skip
            with self._lock:
                self._enqueued.discard(video_path)
    
    def _worker_loop(self):
        """Main worker loop - extracts metadata and generates thumbnails."""
        while self.running:
            try:
                video_path = self.queue.get(timeout=1)
                with self._lock:
                    self._enqueued.discard(video_path)
                    self._in_progress.add(video_path)
                
                if not os.path.exists(video_path):
                    continue
                
                filename = os.path.basename(video_path)
                thumb_path = get_thumbnail_path(filename)
                video_mtime = os.path.getmtime(video_path)
                
                # Check if metadata needs extraction
                cached = get_cached_metadata(video_path)
                if not cached:
                    metadata = extract_video_metadata(video_path)
                    if metadata:
                        cache_metadata(video_path, metadata)
                        self.metadata_count += 1
                
                # Check if thumbnail already exists and is fresh
                need_thumbnail = True
                if os.path.exists(thumb_path):
                    thumb_mtime = os.path.getmtime(thumb_path)
                    if thumb_mtime >= video_mtime:
                        need_thumbnail = False
                
                # Generate thumbnail if needed
                if need_thumbnail:
                    if generate_thumbnail(video_path, thumb_path):
                        self.processed_count += 1
                        
                        # Update cache to mark thumbnail as generated
                        with get_db_connection() as conn:
                            conn.execute(
                                "UPDATE media_cache SET thumbnail_generated = 1 WHERE filepath = ?",
                                (video_path,)
                            )
                            conn.commit()
                    else:
                        self.error_count += 1
                
            except Empty:
                continue
            except Exception as e:
                print(f"[MediaCache] Worker error: {e}")
                self.error_count += 1
            finally:
                try:
                    with self._lock:
                        self._in_progress.discard(video_path)
                except Exception:
                    pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get worker status."""
        with self._lock:
            queued_unique = len(self._enqueued)
            in_progress = len(self._in_progress)
        return {
            'running': self.running,
            'queue_size': self.queue.qsize(),
            'queue_unique': queued_unique,
            'in_progress': in_progress,
            'thumbnails_generated': self.processed_count,
            'metadata_extracted': self.metadata_count,
            'errors': self.error_count
        }

# Global worker instance
_thumbnail_worker = None

def get_thumbnail_worker() -> ThumbnailWorker:
    """Get or create the global thumbnail worker."""
    global _thumbnail_worker
    if _thumbnail_worker is None:
        _thumbnail_worker = ThumbnailWorker()
    return _thumbnail_worker

# ============================================================================
# BULK OPERATIONS
# ============================================================================

def scan_and_cache_directory(record_dir: str, pattern: str = '*.ts') -> Dict[str, Any]:
    """
    Scan a directory and cache metadata for all matching files.
    
    Args:
        record_dir: Directory to scan
        pattern: Glob pattern for files
        
    Returns:
        Dict with scan results
    """
    import glob
    
    results = {
        'scanned': 0,
        'cached': 0,
        'errors': 0,
        'thumbnails_queued': 0
    }
    
    if not os.path.exists(record_dir):
        return results
    
    search_pattern = os.path.join(record_dir, '**', pattern)
    files = glob.glob(search_pattern, recursive=True)
    
    worker = get_thumbnail_worker()
    if not worker.running:
        worker.start()
    
    for filepath in files:
        results['scanned'] += 1
        
        try:
            # Get or extract metadata
            metadata = get_or_extract_metadata(filepath)
            if metadata:
                results['cached'] += 1
                
                # Queue thumbnail generation
                filename = os.path.basename(filepath)
                thumb_path = get_thumbnail_path(filename)
                if not os.path.exists(thumb_path):
                    worker.enqueue(filepath)
                    results['thumbnails_queued'] += 1
            else:
                results['errors'] += 1
                
        except Exception as e:
            print(f"[MediaCache] Error processing {filepath}: {e}")
            results['errors'] += 1
    
    return results

def cleanup_stale_cache(record_dir: str) -> Dict[str, Any]:
    """
    Remove cache entries for files that no longer exist.
    
    Args:
        record_dir: Recording directory
        
    Returns:
        Dict with cleanup results
    """
    results = {
        'checked': 0,
        'removed': 0,
        'thumbnails_removed': 0
    }
    
    try:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT filepath, thumbnail_path FROM media_cache")
            rows = cursor.fetchall()
            
            for row in rows:
                results['checked'] += 1
                filepath = row['filepath']
                thumb_path = row['thumbnail_path']
                
                if not os.path.exists(filepath):
                    # File no longer exists - remove from cache
                    with _db_lock:
                        conn.execute(
                            "DELETE FROM media_cache WHERE filepath = ?",
                            (filepath,)
                        )
                    results['removed'] += 1
                    
                    # Remove orphaned thumbnail
                    if thumb_path and os.path.exists(thumb_path):
                        try:
                            os.remove(thumb_path)
                            results['thumbnails_removed'] += 1
                        except:
                            pass
            
            conn.commit()
        
    except Exception as e:
        print(f"[MediaCache] Error cleaning stale cache: {e}")
    
    return results

def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    try:
        with get_db_connection() as conn:
            # Total entries
            cursor = conn.execute("SELECT COUNT(*) as count FROM media_cache")
            total = cursor.fetchone()['count']
            
            # With thumbnails
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM media_cache WHERE thumbnail_generated = 1"
            )
            with_thumbs = cursor.fetchone()['count']
            
            # Total duration
            cursor = conn.execute(
                "SELECT SUM(duration) as total FROM media_cache WHERE duration IS NOT NULL"
            )
            total_duration = cursor.fetchone()['total'] or 0
            
            # Database size
            db_size = os.path.getsize(MEDIA_CACHE_DB) if os.path.exists(MEDIA_CACHE_DB) else 0
            
            # Thumbnail cache size
            thumb_size = 0
            if os.path.exists(THUMBNAIL_CACHE_DIR):
                for f in os.listdir(THUMBNAIL_CACHE_DIR):
                    fpath = os.path.join(THUMBNAIL_CACHE_DIR, f)
                    if os.path.isfile(fpath):
                        thumb_size += os.path.getsize(fpath)
        
        worker = get_thumbnail_worker()
        
        return {
            'total_entries': total,
            'with_thumbnails': with_thumbs,
            'missing_thumbnails': total - with_thumbs,
            'total_duration_seconds': total_duration,
            'total_duration_human': format_duration(total_duration),
            'database_size': db_size,
            'database_size_human': format_size(db_size),
            'thumbnail_cache_size': thumb_size,
            'thumbnail_cache_size_human': format_size(thumb_size),
            'worker_status': worker.get_status()
        }
        
    except Exception as e:
        print(f"[MediaCache] Error getting cache stats: {e}")
        return {'error': str(e)}

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable string."""
    for unit in ['o', 'Ko', 'Mo', 'Go']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} To"

# ============================================================================
# INITIALIZATION
# ============================================================================

def init_media_cache():
    """Initialize the media cache system."""
    try:
        init_database()
        
        # Start thumbnail worker
        worker = get_thumbnail_worker()
        worker.start()
        
        print("[MediaCache] Media cache system initialized")
        return True
        
    except Exception as e:
        print(f"[MediaCache] Error initializing: {e}")
        return False

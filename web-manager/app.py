#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTSP Recorder Web Manager - Main Application
Modular Flask application with blueprints architecture.

Version: 2.30.16
"""

import os
import sys
import signal
import threading
import logging
from datetime import datetime

from flask import Flask, render_template, jsonify, request, g

# Import configuration
from config import APP_VERSION, PLATFORM

# Import blueprints
from blueprints import (
    config_bp,
    camera_bp,
    recordings_bp,
    network_bp,
    system_bp,
    meeting_bp,
    logs_bp,
    video_bp,
    power_bp,
    onvif_bp,
    detect_bp,
    watchdog_bp,
    wifi_bp,
    debug_bp,
    legacy_bp,
    i18n_bp
)

# Import services for background tasks
from services.meeting_service import meeting_heartbeat_loop, init_meeting_service
from services.watchdog_service import (
    rtsp_watchdog_loop, wifi_failover_watchdog_loop,
    load_watchdog_state
)
from services.camera_service import load_camera_profiles, profiles_scheduler_loop
from services.network_service import manage_wifi_based_on_ethernet
from services import media_cache_service
from services.config_service import load_config
from services.i18n_service import (
    DEFAULT_LANG,
    LANG_COOKIE_NAME,
    list_languages,
    load_translations,
    normalize_lang,
    resolve_request_lang,
    t as translate
)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging():
    """Configure application logging."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce Flask/Werkzeug logging noise
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    return logging.getLogger('rpi-cam-webmanager')

logger = setup_logging()

# ============================================================================
# FLASK APPLICATION FACTORY
# ============================================================================

# Flag to track if background tasks have been initialized
_background_tasks_started = False
_startup_thread = None

def _delayed_startup():
    """Start background tasks after a short delay (allows Gunicorn to fully initialize)."""
    global _background_tasks_started
    import time
    time.sleep(2)  # Wait for Gunicorn workers to be ready
    if not _background_tasks_started:
        _background_tasks_started = True
        logger.info("Starting background tasks (delayed startup)")
        start_background_tasks()

def create_app():
    """Create and configure the Flask application."""
    global _startup_thread
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.urandom(24)
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register main routes
    register_main_routes(app)
    
    # Start background tasks on first request (fallback) AND via delayed startup
    @app.before_request
    def init_once():
        global _background_tasks_started
        if not _background_tasks_started:
            _background_tasks_started = True
            logger.info("Initializing background tasks (first request)")
            start_background_tasks()

    @app.before_request
    def resolve_language():
        try:
            config = load_config()
        except Exception:
            config = {}
        g.current_lang = resolve_request_lang(request, config)

    @app.after_request
    def persist_language_cookie(response):
        requested = request.args.get("lang")
        if requested:
            normalized = normalize_lang(requested)
            if normalized in list_languages():
                response.set_cookie(
                    LANG_COOKIE_NAME,
                    normalized,
                    max_age=31536000,
                    samesite="Lax"
                )
        return response

    @app.context_processor
    def inject_i18n():
        current_lang = getattr(g, "current_lang", DEFAULT_LANG)
        translations = load_translations(current_lang)
        fallback_translations = load_translations(DEFAULT_LANG)

        def _t(key, **params):
            return translate(key, current_lang, params)

        def _t_lang(lang, key, **params):
            return translate(key, lang, params)

        return {
            "t": _t,
            "t_lang": _t_lang,
            "current_lang": current_lang,
            "available_langs": list_languages(),
            "default_lang": DEFAULT_LANG,
            "translations": translations,
            "default_translations": fallback_translations
        }
    
    # Also start a delayed startup thread (ensures tasks start even without HTTP requests)
    # This is critical for network failover when the device boots without connectivity
    global _startup_thread
    if _startup_thread is None:
        _startup_thread = threading.Thread(target=_delayed_startup, daemon=True, name="delayed-startup")
        _startup_thread.start()
        logger.info("Delayed startup thread scheduled")
    
    return app

def register_blueprints(app):
    """Register all blueprints with the application."""
    blueprints = [
        (config_bp, None),      # /api/config, /api/service, /api/system
        (camera_bp, None),      # /api/camera
        (recordings_bp, None),  # /api/recordings
        (network_bp, None),     # /api/network
        (system_bp, None),      # /api/system (diagnostic, logs, updates)
        (meeting_bp, None),     # /api/meeting
        (logs_bp, None),        # /api/logs
        (video_bp, None),       # /api/video
        (power_bp, None),       # /api/power
        (onvif_bp, None),       # /api/onvif
        (detect_bp, None),      # /api/detect, /api/platform
        (watchdog_bp, None),    # /api/rtsp/watchdog, /api/wifi/failover/watchdog
        (wifi_bp, None),        # /api/wifi (legacy compatibility)
        (debug_bp, None),       # /api/debug, /api/system/ntp
        (legacy_bp, None),      # /api/leds/*, /api/gpu/* (backward compatibility)
        (i18n_bp, None),        # /i18n/*.json
    ]
    
    for blueprint, url_prefix in blueprints:
        if url_prefix:
            app.register_blueprint(blueprint, url_prefix=url_prefix)
        else:
            app.register_blueprint(blueprint)
    
    logger.info(f"Registered {len(blueprints)} blueprints")

def format_bytes(size):
    """Format bytes to human readable string."""
    for unit in ['B', 'Ko', 'Mo', 'Go', 'To']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} Po"

def enrich_system_info(info):
    """Add template-compatible keys to system_info."""
    enriched = info.copy()
    
    # Disk info in human readable format
    disk = info.get('disk', {})
    enriched['disk_used'] = format_bytes(disk.get('used', 0))
    enriched['disk_total'] = format_bytes(disk.get('total', 0))
    enriched['disk_avail'] = format_bytes(disk.get('available', 0))
    enriched['disk_percent_num'] = disk.get('percent', 0)
    
    # Memory percent
    memory = info.get('memory', {})
    enriched['ram_percent'] = memory.get('percent', 0)
    
    # CPU percent (use load average as proxy)
    cpu = info.get('cpu', {})
    cores = cpu.get('cores', 1)
    load = cpu.get('load_1m', 0)
    enriched['cpu_percent'] = min(100, int(load / cores * 100))
    
    # Temperature
    enriched['cpu_temp'] = info.get('temperature')
    
    # IP addresses
    network = info.get('network', {})
    ip_list = [ip for ip in network.values() if ip and ip != '127.0.0.1']
    enriched['ip_addresses'] = ip_list if ip_list else ['N/A']
    enriched['ip'] = ip_list[0] if ip_list else 'N/A'
    
    # Model
    platform = info.get('platform', {})
    enriched['model'] = platform.get('model', 'Raspberry Pi').title()
    
    # Recording info - calculate from actual files
    try:
        from services.recording_service import get_recordings_list, get_recording_dir
        from services.config_service import load_config as load_conf
        cfg = load_conf()
        recordings = get_recordings_list(cfg, pattern='*.ts')
        enriched['recording_count'] = len(recordings)
        total_bytes = sum(r.get('size', 0) for r in recordings)
        enriched['recording_size_mb'] = round(total_bytes / (1024 * 1024), 1)
        enriched['recording_size_human'] = format_bytes(total_bytes)
    except Exception as e:
        print(f"[enrich_system_info] Error getting recording stats: {e}")
        enriched['recording_count'] = 0
        enriched['recording_size_mb'] = 0
        enriched['recording_size_human'] = '0 Mo'
    
    return enriched

def register_error_handlers(app):
    """Register error handlers."""
    
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'success': False,
                'error': 'Endpoint not found',
                'path': request.path
            }), 404
        # For non-API 404s, render template with all needed context
        from services.config_service import load_config, get_system_info
        from services.network_service import get_current_wifi, get_preferred_ip, load_ap_config
        from services.power_service import get_led_status, get_gpu_mem
        from services.meeting_service import is_debug_enabled
        from config import CONFIG_METADATA
        
        config = load_config()
        raw_system_info = get_system_info()
        system_info = enrich_system_info(raw_system_info)
        wifi_info = get_current_wifi()
        led_status = get_led_status()
        gpu_mem = get_gpu_mem()
        ap_mode = load_ap_config()
        debug_enabled = is_debug_enabled()
        
        rtsp_port = config.get('RTSP_PORT', '8554')
        rtsp_path = config.get('RTSP_PATH', 'stream')
        ip = get_preferred_ip()
        rtsp_url = f"rtsp://{ip}:{rtsp_port}/{rtsp_path}"
        hostname = system_info.get('hostname', '')
        rtsp_url_hostname = f"rtsp://{hostname}:{rtsp_port}/{rtsp_path}" if hostname else None
        is_provisioned = config.get('MEETING_PROVISIONED', 'no') == 'yes'
        
        return render_template('index.html', 
                             config=config,
                             metadata=CONFIG_METADATA,
                             status='unknown',
                             system_info=system_info,
                             rtsp_url=rtsp_url,
                             rtsp_url_hostname=rtsp_url_hostname,
                             is_provisioned=is_provisioned,
                             debug_enabled=debug_enabled,
                             wifi_info=wifi_info,
                             led_status=led_status,
                             gpu_mem=gpu_mem,
                             platform=PLATFORM,
                             app_version=APP_VERSION,
                             ap_mode=ap_mode), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(error)
        }), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        logger.exception(f"Unhandled exception: {error}")
        return jsonify({
            'success': False,
            'error': 'Unexpected error',
            'message': str(error)
        }), 500

def register_main_routes(app):
    """Register main application routes."""
    
    @app.route('/')
    def index():
        """Serve the main web interface."""
        from services.config_service import load_config, get_service_status, get_system_info
        from services.network_service import get_current_wifi, get_preferred_ip, load_ap_config
        from services.power_service import get_led_status, get_gpu_mem
        from services.meeting_service import is_debug_enabled
        from config import CONFIG_METADATA
        
        config = load_config()
        service_status = get_service_status()
        raw_system_info = get_system_info()
        system_info = enrich_system_info(raw_system_info)
        wifi_info = get_current_wifi()
        led_status = get_led_status()
        gpu_mem = get_gpu_mem()
        ap_mode = load_ap_config()
        
        # Check if debug tab should be shown (requires 'vnc' or 'debug' service in Meeting)
        debug_enabled = is_debug_enabled()
        
        # Extract status string from service status dict
        if isinstance(service_status, dict):
            status = service_status.get('status', 'unknown')
        else:
            status = service_status
        
        # Build RTSP URL for display
        rtsp_port = config.get('RTSP_PORT', '8554')
        rtsp_path = config.get('RTSP_PATH', 'stream')
        ip = get_preferred_ip()
        rtsp_url = f"rtsp://{ip}:{rtsp_port}/{rtsp_path}"
        
        # Get hostname for alternate URL (without .local - Synology doesn't support it)
        hostname = system_info.get('hostname', '')
        rtsp_url_hostname = f"rtsp://{hostname}:{rtsp_port}/{rtsp_path}" if hostname else None
        
        # Check if device is provisioned (Meeting)
        is_provisioned = config.get('MEETING_PROVISIONED', 'no') == 'yes'
        
        return render_template('index.html', 
                             config=config, 
                             metadata=CONFIG_METADATA,
                             status=status,
                             system_info=system_info,
                             rtsp_url=rtsp_url,
                             rtsp_url_hostname=rtsp_url_hostname,
                             is_provisioned=is_provisioned,
                             debug_enabled=debug_enabled,
                             wifi_info=wifi_info,
                             led_status=led_status,
                             gpu_mem=gpu_mem,
                             platform=PLATFORM,
                             app_version=APP_VERSION,
                             ap_mode=ap_mode)
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'version': APP_VERSION,
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api')
    def api_index():
        """API documentation endpoint."""
        return jsonify({
            'version': APP_VERSION,
            'endpoints': {
                'config': '/api/config',
                'camera': '/api/camera',
                'recordings': '/api/recordings',
                'network': '/api/network',
                'system': '/api/system',
                'meeting': '/api/meeting',
                'logs': '/api/logs',
                'video': '/api/video',
                'power': '/api/power',
                'onvif': '/api/onvif'
            }
        })

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

# Stop events for background threads
stop_events = {
    'meeting': threading.Event(),
    'rtsp_watchdog': threading.Event(),
    'wifi_failover': threading.Event(),
    'profiles_scheduler': threading.Event()
}

# Background threads
background_threads = {}

def start_background_tasks():
    """Start background worker threads."""
    global background_threads
    
    # Load saved states
    load_watchdog_state()
    load_camera_profiles()
    
    # Initialize media cache (SQLite + thumbnail worker)
    try:
        media_cache_service.init_media_cache()
        logger.info("Media cache service initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize media cache: {e}")
    
    # Synchronize recorder service with RECORD_ENABLE config
    try:
        from services.config_service import sync_recorder_service
        result = sync_recorder_service()
        if result.get('action') in ['started', 'stopped']:
            logger.info(f"Recorder service {result['action']} based on RECORD_ENABLE config")
        else:
            logger.debug(f"Recorder service sync: {result.get('action', 'no change')}")
    except Exception as e:
        logger.warning(f"Failed to sync recorder service: {e}")
    
    # Apply WiFi priority policy (disable WiFi if Ethernet connected and no override)
    try:
        manage_wifi_based_on_ethernet()
        logger.info("WiFi/Ethernet priority policy applied")
    except Exception as e:
        logger.warning(f"Failed to apply WiFi priority policy: {e}")
    
    # Initialize meeting service
    init_meeting_service()
    
    # Start meeting heartbeat thread
    meeting_thread = threading.Thread(
        target=meeting_heartbeat_loop,
        args=(stop_events['meeting'],),
        daemon=True,
        name='meeting-heartbeat'
    )
    meeting_thread.start()
    background_threads['meeting'] = meeting_thread
    logger.info("Started meeting heartbeat thread")
    
    # Start RTSP watchdog thread
    rtsp_thread = threading.Thread(
        target=rtsp_watchdog_loop,
        args=(stop_events['rtsp_watchdog'],),
        daemon=True,
        name='rtsp-watchdog'
    )
    rtsp_thread.start()
    background_threads['rtsp_watchdog'] = rtsp_thread
    logger.info("Started RTSP watchdog thread")
    
    # Start WiFi failover thread
    wifi_thread = threading.Thread(
        target=wifi_failover_watchdog_loop,
        args=(stop_events['wifi_failover'],),
        daemon=True,
        name='wifi-failover'
    )
    wifi_thread.start()
    background_threads['wifi_failover'] = wifi_thread
    logger.info("Started WiFi failover thread")

    # Start profiles scheduler thread
    profiles_thread = threading.Thread(
        target=profiles_scheduler_loop,
        args=(stop_events['profiles_scheduler'],),
        daemon=True,
        name='profiles-scheduler'
    )
    profiles_thread.start()
    background_threads['profiles_scheduler'] = profiles_thread
    logger.info("Started profiles scheduler thread")

def stop_background_tasks():
    """Stop all background worker threads."""
    logger.info("Stopping background tasks...")
    
    for name, event in stop_events.items():
        event.set()
    
    # Wait for threads to finish (with timeout)
    for name, thread in background_threads.items():
        if thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                logger.warning(f"Thread {name} did not stop gracefully")

# ============================================================================
# SIGNAL HANDLERS
# ============================================================================

def handle_shutdown(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    stop_background_tasks()
    sys.exit(0)

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

# Create the application
app = create_app()

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    # Log startup info
    logger.info(f"Starting RTSP Web Manager v{APP_VERSION}")
    logger.info(f"Platform: {PLATFORM['model']}")
    
    # Start background tasks
    start_background_tasks()
    
    # Run Flask development server
    # In production, use gunicorn or similar
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True,
        use_reloader=False  # Important: disable reloader with background threads
    )

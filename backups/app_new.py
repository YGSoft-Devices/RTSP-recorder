#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTSP Recorder Web Manager - Main Application
Modular Flask application with blueprints architecture.

Version: 2.30.0
"""

import os
import sys
import signal
import threading
import logging
from datetime import datetime

from flask import Flask, render_template, jsonify, request

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
    legacy_bp
)

# Import services for background tasks
from services.meeting_service import meeting_heartbeat_loop, init_meeting_service
from services.watchdog_service import (
    rtsp_watchdog_loop, wifi_failover_watchdog_loop,
    load_watchdog_state
)
from services.camera_service import load_camera_profiles

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

def create_app():
    """Create and configure the Flask application."""
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
    ]
    
    for blueprint, url_prefix in blueprints:
        if url_prefix:
            app.register_blueprint(blueprint, url_prefix=url_prefix)
        else:
            app.register_blueprint(blueprint)
    
    logger.info(f"Registered {len(blueprints)} blueprints")

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
        return render_template('index.html'), 404
    
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
        from services.network_service import get_current_wifi, get_preferred_ip
        from services.power_service import get_led_status, get_gpu_mem
        from config import CONFIG_METADATA
        
        config = load_config()
        status = get_service_status()
        system_info = get_system_info()
        wifi_info = get_current_wifi()
        led_status = get_led_status()
        gpu_mem = get_gpu_mem()
        
        # Build RTSP URL for display
        rtsp_port = config.get('RTSP_PORT', '8554')
        rtsp_path = config.get('RTSP_PATH', 'stream')
        ip = get_preferred_ip()
        rtsp_url = f"rtsp://{ip}:{rtsp_port}/{rtsp_path}"
        
        # Get hostname for alternate URL
        hostname = system_info.get('hostname', '')
        rtsp_url_hostname = f"rtsp://{hostname}.local:{rtsp_port}/{rtsp_path}" if hostname else None
        
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
                             wifi_info=wifi_info,
                             led_status=led_status,
                             gpu_mem=gpu_mem,
                             platform=PLATFORM)
    
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
    'wifi_failover': threading.Event()
}

# Background threads
background_threads = {}

def start_background_tasks():
    """Start background worker threads."""
    global background_threads
    
    # Load saved states
    load_watchdog_state()
    load_camera_profiles()
    
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

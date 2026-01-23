# -*- coding: utf-8 -*-
"""
Blueprints module - Flask route handlers organized by domain
Version: 2.30.0
"""

from .config_bp import config_bp
from .camera_bp import camera_bp
from .recordings_bp import recordings_bp
from .network_bp import network_bp
from .system_bp import system_bp
from .meeting_bp import meeting_bp
from .logs_bp import logs_bp
from .video_bp import video_bp
from .power_bp import power_bp
from .onvif_bp import onvif_bp
from .detect_bp import detect_bp
from .watchdog_bp import watchdog_bp
from .wifi_bp import wifi_bp
from .debug_bp import debug_bp
from .legacy_bp import legacy_bp

__all__ = [
    'config_bp',
    'camera_bp',
    'recordings_bp',
    'network_bp',
    'system_bp',
    'meeting_bp',
    'logs_bp',
    'video_bp',
    'power_bp',
    'onvif_bp',
    'detect_bp',
    'watchdog_bp',
    'wifi_bp',
    'debug_bp',
    'legacy_bp'
]

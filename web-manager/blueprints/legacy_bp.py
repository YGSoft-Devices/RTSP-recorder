# -*- coding: utf-8 -*-
"""
Legacy Routes Blueprint - Backward compatibility for old API paths
Version: 2.30.2

This module provides compatibility routes for old API endpoints
that have been reorganized in the modular architecture.
NOTE: Most LED/GPU routes are now in power_bp.py
"""

from flask import Blueprint, request, jsonify

from services.power_service import (
    get_gpu_mem, set_gpu_mem
)
from services.system_service import get_legacy_diagnostic_info
from services.network_service import get_current_wifi

legacy_bp = Blueprint('legacy', __name__, url_prefix='/api')

# ============================================================================
# LEGACY GPU ROUTES (moved to /api/power/gpu)
# ============================================================================

@legacy_bp.route('/gpu/mem', methods=['GET'])
def gpu_mem_get_legacy():
    """API endpoint to get GPU memory."""
    mem = get_gpu_mem()
    return jsonify({
        'success': True,
        'gpu_mem': mem,
        'available': True
    })

@legacy_bp.route('/gpu/mem', methods=['POST'])
def gpu_mem_set_legacy():
    """API endpoint to set GPU memory."""
    try:
        data = request.get_json(silent=True) or {}
        mem_mb = data.get('gpu_mem', 128)
        
        result = set_gpu_mem(mem_mb)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# LEGACY DIAGNOSTIC ROUTE (moved to /api/system/diagnostic)
# ============================================================================

@legacy_bp.route('/diagnostic', methods=['GET'])
def diagnostic_legacy():
    """Legacy diagnostic endpoint - returns format expected by frontend."""
    diag = get_legacy_diagnostic_info()
    return jsonify({
        'success': True,
        'diagnostic': diag
    })

# ============================================================================
# LEGACY WIFI ROUTE (moved to /api/wifi/status)
# ============================================================================

@legacy_bp.route('/wifi/current', methods=['GET'])
def wifi_current_legacy():
    """Legacy wifi current endpoint."""
    wifi = get_current_wifi()
    return jsonify({
        'success': True,
        'current': wifi,
        **wifi
    })

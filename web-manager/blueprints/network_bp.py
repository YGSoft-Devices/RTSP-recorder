# -*- coding: utf-8 -*-
"""
Network Blueprint - Network interfaces, WiFi, and AP mode routes
Version: 2.30.8
"""

import logging
from flask import Blueprint, request, jsonify

from services.network_service import (
    get_network_interfaces, get_interface_details,
    configure_static_ip, configure_dhcp, set_interface_priority,
    get_wifi_networks, get_current_wifi, connect_wifi, disconnect_wifi,
    get_ap_status, create_access_point, stop_access_point,
    get_wifi_failover_config, save_wifi_failover_config,
    get_ethernet_status, get_wifi_manual_override, set_wifi_manual_override,
    manage_wifi_based_on_ethernet, get_wlan0_status
)
from services.watchdog_service import (
    get_wifi_failover_status, check_network_connectivity
)
from services.i18n_service import t as i18n_t, resolve_request_lang

logger = logging.getLogger(__name__)

network_bp = Blueprint('network', __name__, url_prefix='/api/network')

def _t(key, **params):
    return i18n_t(key, lang=resolve_request_lang(request), params=params)

# ============================================================================
# INTERFACE ROUTES
# ============================================================================

@network_bp.route('/interfaces', methods=['GET'])
def list_interfaces():
    """Get all network interfaces."""
    from services.config_service import load_config
    
    interfaces = get_network_interfaces()
    
    # Add 'connected' key for frontend compatibility (based on state and ip)
    for iface in interfaces:
        iface['connected'] = iface.get('state') == 'up' and iface.get('ip') is not None
    
    # Get priority order from saved config (or default)
    try:
        config = load_config()
        saved_priority = config.get('NETWORK_INTERFACE_PRIORITY', 'eth0,wlan1,wlan0')
        priority = [p.strip() for p in saved_priority.split(',') if p.strip()]
    except:
        priority = ['eth0', 'wlan1', 'wlan0']
    
    # Add any interfaces not in priority list at the end
    interface_names = [iface['name'] for iface in interfaces]
    for name in interface_names:
        if name not in priority and not name.startswith('lo'):
            priority.append(name)
    
    # Filter priority to only include existing interfaces
    priority = [p for p in priority if p in interface_names]
    
    return jsonify({
        'success': True,
        'interfaces': interfaces,
        'count': len(interfaces),
        'priority': priority
    })

@network_bp.route('/interfaces/<interface_name>', methods=['GET'])
def interface_details(interface_name):
    """Get details of a specific interface."""
    details = get_interface_details(interface_name)
    
    if not details['exists']:
        return jsonify({
            'success': False,
            'error': _t('ui.network.interface_not_found', interface=interface_name)
        }), 404
    
    return jsonify({
        'success': True,
        **details
    })

@network_bp.route('/config', methods=['GET'])
def get_network_config():
    """Get overall network configuration."""
    interfaces = get_network_interfaces()
    wifi = get_current_wifi()
    failover = get_wifi_failover_config()
    
    return jsonify({
        'success': True,
        'interfaces': interfaces,
        'current_wifi': wifi,
        'failover_config': failover
    })

# ============================================================================
# IP CONFIGURATION ROUTES
# ============================================================================

@network_bp.route('/static', methods=['POST'])
def set_static_ip():
    """Configure static IP address and save to failover config."""
    data = request.get_json()
    
    required = ['interface', 'ip_address']
    for field in required:
        if field not in data:
            return jsonify({
                'success': False,
                'error': _t('ui.errors.field_required', field=field)
            }), 400
    
    result = configure_static_ip(
        data['interface'],
        data['ip_address'],
        data.get('netmask', '24'),
        data.get('gateway'),
        data.get('dns')
    )
    
    # Also save to wifi_failover.json to ensure persistence
    if result['success']:
        try:
            failover_config = get_wifi_failover_config()
            # Extract IP and netmask from ip_address (e.g., "192.168.1.4/24")
            ip_with_mask = data['ip_address']
            if '/' not in ip_with_mask:
                ip_with_mask = f"{ip_with_mask}/{data.get('netmask', '24')}"
            
            failover_config['static_ip'] = ip_with_mask
            failover_config['gateway'] = data.get('gateway', '')
            failover_config['dns'] = data.get('dns', '8.8.8.8')
            failover_config['ip_mode'] = 'static'
            
            save_wifi_failover_config(failover_config)
        except Exception as e:
            # Log but don't fail - the static IP was already applied to NetworkManager
            logger.warning(f"Failed to save static IP to wifi_failover.json: {e}")
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@network_bp.route('/dhcp', methods=['POST'])
def set_dhcp():
    """Configure interface for DHCP and save to failover config."""
    data = request.get_json()
    
    if not data or 'interface' not in data:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.field_required', field='interface')
        }), 400
    
    result = configure_dhcp(data['interface'])
    
    # Also save to wifi_failover.json to ensure persistence
    if result['success']:
        try:
            failover_config = get_wifi_failover_config()
            failover_config['ip_mode'] = 'dhcp'
            save_wifi_failover_config(failover_config)
        except Exception as e:
            # Log but don't fail - the DHCP was already applied to NetworkManager
            logger.warning(f"Failed to save DHCP mode to wifi_failover.json: {e}")
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@network_bp.route('/priority', methods=['POST'])
def set_priority():
    """Set interface priority order."""
    data = request.get_json()
    
    if not data or 'interfaces' not in data:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.array_required', field='interfaces')
        }), 400
    
    result = set_interface_priority(data['interfaces'])
    
    return jsonify(result)

# ============================================================================
# WIFI ROUTES
# ============================================================================

@network_bp.route('/wifi/networks', methods=['GET'])
def scan_wifi():
    """Scan for available WiFi networks."""
    interface = request.args.get('interface', 'wlan0')
    networks = get_wifi_networks(interface)
    
    return jsonify({
        'success': True,
        'networks': networks,
        'count': len(networks)
    })

@network_bp.route('/wifi/current', methods=['GET'])
def current_wifi():
    """Get current WiFi connection."""
    interface = request.args.get('interface', 'wlan0')
    connection = get_current_wifi(interface)
    
    if connection:
        return jsonify({
            'success': True,
            'connected': True,
            **connection
        })
    else:
        return jsonify({
            'success': True,
            'connected': False
        })

@network_bp.route('/wifi/connect', methods=['POST'])
def wifi_connect():
    """Connect to a WiFi network."""
    data = request.get_json()
    
    if not data or 'ssid' not in data:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.field_required', field='ssid')
        }), 400
    
    result = connect_wifi(
        data['ssid'],
        data.get('password'),
        data.get('interface', 'wlan0')
    )
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@network_bp.route('/wifi/disconnect', methods=['POST'])
def wifi_disconnect():
    """Disconnect from WiFi."""
    data = request.get_json(silent=True) or {}
    interface = data.get('interface', 'wlan0')
    
    result = disconnect_wifi(interface)
    
    return jsonify(result)

# ============================================================================
# ACCESS POINT ROUTES
# ============================================================================

@network_bp.route('/ap/config', methods=['POST'])
def ap_config():
    """Get AP configuration, optionally from Meeting API.
    
    Request body (optional):
    {
        'from_meeting': true/false  - If true, fetch from Meeting API
    }
    
    Returns:
    {
        success: true,
        config: {
            ap_ssid: str (from Meeting or local config),
            ap_password: str (from Meeting or local config),
            ap_ip: str (192.168.4.1)
        }
    }
    """
    from services.network_service import load_ap_config
    from services.meeting_service import get_meeting_device_info
    
    data = request.get_json(silent=True) or {}
    from_meeting = data.get('from_meeting', False)
    
    ap_config = load_ap_config()
    
    # Try to fetch from Meeting if requested
    if from_meeting:
        try:
            meeting_info = get_meeting_device_info()
            if meeting_info.get('success') and meeting_info.get('data'):
                device_data = meeting_info['data']
                # Extract AP credentials from Meeting device data
                # Meeting API returns ap_ssid and ap_password directly in device data
                if device_data.get('ap_ssid'):
                    ap_config['ssid'] = device_data['ap_ssid']
                if device_data.get('ap_password'):
                    ap_config['password'] = device_data['ap_password']
                # Channel is fixed to 11 per project requirements
                ap_config['channel'] = 11
                print(f"[network_bp] AP config from Meeting: SSID={ap_config.get('ssid', '')}, channel=11")
        except Exception as e:
            print(f"[network_bp] Error fetching AP config from Meeting: {e}")
    
    return jsonify({
        'success': True,
        'config': {
            'ap_ssid': ap_config.get('ssid', ''),
            'ap_password': ap_config.get('password', ''),
            'ap_channel': ap_config.get('channel', 11),
            'ap_ip': '192.168.4.1'
        }
    })

@network_bp.route('/ap/status', methods=['GET'])
def ap_status():
    """Get Access Point status.
    
    Returns structure expected by frontend:
    {
        success: true,
        status: { active: bool, ssid: str, ip: str, clients: int },
        config: { ap_ssid: str, ap_password: str, ap_ip: str }
    }
    """
    from services.network_service import get_ap_status, load_ap_config
    
    raw_status = get_ap_status()
    ap_config = load_ap_config()
    
    # Build structure expected by frontend
    status = {
        'active': raw_status.get('enabled', False),
        'ssid': raw_status.get('ssid', ''),
        'ip': raw_status.get('ip', ''),
        'clients': len(raw_status.get('clients', []))
    }
    
    config = {
        'ap_ssid': ap_config.get('ssid', ''),
        'ap_password': ap_config.get('password', ''),
        'ap_channel': ap_config.get('channel', 11),
        'ap_ip': ap_config.get('ap_ip', '192.168.4.1')
    }
    
    return jsonify({
        'success': True,
        'status': status,
        'config': config
    })

@network_bp.route('/ap/start', methods=['POST'])
def ap_start():
    """Start Access Point."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.ssid_password_required')
        }), 400
    
    required = ['ssid', 'password']
    for field in required:
        if field not in data:
            return jsonify({
                'success': False,
                'error': _t('ui.errors.field_required', field=field)
            }), 400
    
    result = create_access_point(
        data['ssid'],
        data['password'],
        data.get('channel', 11),
        data.get('interface', 'wlan0')
    )
    
    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code

@network_bp.route('/ap/stop', methods=['POST'])
def ap_stop():
    """Stop Access Point."""
    data = request.get_json(silent=True) or {}
    interface = data.get('interface', 'wlan0')
    
    result = stop_access_point(interface)
    
    return jsonify(result)

# ============================================================================
# FAILOVER ROUTES
# ============================================================================

@network_bp.route('/failover/config', methods=['GET'])
def get_failover_config():
    """Get WiFi failover configuration."""
    config = get_wifi_failover_config()
    
    return jsonify({
        'success': True,
        'config': config
    })

@network_bp.route('/failover/config', methods=['POST', 'PUT'])
def set_failover_config():
    """Update WiFi failover configuration."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.configuration_required')
        }), 400
    
    # Merge with existing config
    current = get_wifi_failover_config()
    current.update(data)
    
    result = save_wifi_failover_config(current)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@network_bp.route('/failover/status', methods=['GET'])
def get_failover_status():
    """Get WiFi failover status."""
    status = get_wifi_failover_status()
    config = get_wifi_failover_config()
    
    return jsonify({
        'success': True,
        'status': status,
        'config': config
    })

@network_bp.route('/failover/test', methods=['POST'])
def test_connectivity():
    """Test network connectivity."""
    data = request.get_json(silent=True) or {}
    interface = data.get('interface')
    targets = data.get('targets')
    
    result = check_network_connectivity(interface, targets)
    
    return jsonify({
        'success': True,
        **result
    })

# ============================================================================
# WIFI MANUAL OVERRIDE ROUTES
# ============================================================================

@network_bp.route('/wifi/override', methods=['GET'])
def get_wifi_override():
    """Get WiFi manual override status.
    
    Returns structure expected by frontend:
    {
        success: true,
        override: bool,
        ethernet: { connected: bool, present: bool },
        wlan0: { connected: bool, ap_mode: bool, managed: bool }
    }
    """
    override = get_wifi_manual_override()
    eth_status = get_ethernet_status()
    wlan_status = get_wlan0_status()
    
    # wlan0 is connected if it has 'connected' state (not 'up' which doesn't exist)
    wlan_connected = wlan_status.get('connected', False)
    wlan_ap_mode = wlan_status.get('ap_mode', False)
    eth_connected = eth_status.get('connected', False)
    
    # 'managed' means WiFi is auto-disabled because Ethernet is up
    # But only if wlan0 is NOT actually connected (if it's connected, it's not disabled!)
    managed = not override and eth_connected and not wlan_connected and not wlan_ap_mode
    
    return jsonify({
        'success': True,
        'override': override,
        'ethernet': {
            'connected': eth_connected,
            'present': eth_status.get('present', False)
        },
        'wlan0': {
            'connected': wlan_connected and not wlan_ap_mode,
            'ap_mode': wlan_ap_mode,
            'managed': managed
        }
    })

@network_bp.route('/wifi/override', methods=['POST'])
def set_wifi_override():
    """Set WiFi manual override (enable/disable WiFi regardless of ethernet)."""
    data = request.get_json(silent=True) or {}
    enable = data.get('enable')
    
    if enable is None:
        return jsonify({
            'success': False,
            'error': _t('ui.errors.enable_required')
        }), 400
    
    result = set_wifi_manual_override(enable)
    
    if result['success']:
        # Manage WiFi based on new setting
        manage_result = manage_wifi_based_on_ethernet()
        result['wifi_management'] = manage_result
    
    return jsonify(result)

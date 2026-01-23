# -*- coding: utf-8 -*-
"""
WiFi Blueprint - WiFi specific routes (legacy compatibility)
Version: 2.30.8

These routes provide backward compatibility with the original API.
"""

import os
import json
import subprocess
from flask import Blueprint, request, jsonify

from services.network_service import (
    get_wifi_networks,
    get_current_wifi,
    connect_wifi,
    disconnect_wifi,
    get_wifi_failover_config,
    save_wifi_failover_config,
    get_wifi_failover_status,
    get_network_interfaces,
    clone_wifi_config,
    auto_configure_wifi_interface
)

wifi_bp = Blueprint('wifi', __name__, url_prefix='/api/wifi')

# Simple WiFi config file
WIFI_SIMPLE_CONFIG_FILE = '/var/lib/rpi-cam/wifi_simple.json'

# ============================================================================
# WIFI SCANNING AND CONNECTION
# ============================================================================

@wifi_bp.route('/scan', methods=['GET'])
def wifi_scan():
    """API endpoint to scan for WiFi networks."""
    networks = get_wifi_networks()
    return jsonify({
        'success': True,
        'networks': networks
    })

@wifi_bp.route('/status', methods=['GET'])
def wifi_status():
    """API endpoint to get WiFi status."""
    info = get_current_wifi()
    config = get_wifi_failover_config()
    return jsonify({
        'success': True,
        'current': info,
        'config': config
    })

@wifi_bp.route('/connect', methods=['POST'])
def wifi_connect():
    """API endpoint to connect to WiFi."""
    try:
        data = request.get_json(silent=True) or {}
        ssid = data.get('ssid', '')
        password = data.get('password', '')
        is_fallback = data.get('fallback', False)
        
        if not ssid:
            return jsonify({
                'success': False,
                'message': 'SSID required'
            }), 400
        
        # Fallback network gets lower priority
        priority = 5 if is_fallback else 10
        success, message = connect_wifi(ssid, password, priority)
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@wifi_bp.route('/disconnect', methods=['POST'])
def wifi_disconnect():
    """API endpoint to disconnect from WiFi."""
    try:
        data = request.get_json(silent=True) or {}
        ssid = data.get('ssid', '')
        
        try:
            if ssid:
                subprocess.run(['sudo', 'nmcli', 'con', 'delete', ssid],
                              capture_output=True, timeout=30)
            else:
                subprocess.run(['sudo', 'nmcli', 'dev', 'disconnect', 'wlan0'],
                              capture_output=True, timeout=30)
        except:
            pass
        
        return jsonify({
            'success': True,
            'message': 'Disconnected'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# SIMPLE WIFI CONFIGURATION (for single adapter)
# ============================================================================

def load_wifi_simple_config():
    """Load simple WiFi config."""
    default = {
        'ssid': '',
        'password': '',
        'ip_mode': 'dhcp',
        'static_ip': '',
        'gateway': '',
        'dns': '8.8.8.8'
    }
    if os.path.exists(WIFI_SIMPLE_CONFIG_FILE):
        try:
            with open(WIFI_SIMPLE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                default.update(config)
        except:
            pass
    return default

def save_wifi_simple_config(config):
    """Save simple WiFi config."""
    os.makedirs(os.path.dirname(WIFI_SIMPLE_CONFIG_FILE), exist_ok=True)
    with open(WIFI_SIMPLE_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_saved_wifi_ssid():
    """Get SSID from NetworkManager saved connections (e.g., from RPi Imager)."""
    try:
        import subprocess
        # Get all WiFi connections from NetworkManager
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if ':802-11-wireless' in line:
                    conn_name = line.split(':')[0]
                    # Get SSID from connection details
                    detail_result = subprocess.run(
                        ['nmcli', '-t', '-f', '802-11-wireless.ssid', 'connection', 'show', conn_name],
                        capture_output=True, text=True, timeout=10
                    )
                    if detail_result.returncode == 0:
                        ssid_line = detail_result.stdout.strip()
                        if ':' in ssid_line:
                            ssid = ssid_line.split(':', 1)[1]
                            if ssid:
                                return ssid
    except Exception as e:
        print(f"[WiFi] Error getting saved SSID: {e}")
    return ''

@wifi_bp.route('/simple/status', methods=['GET'])
def wifi_simple_status():
    """Get simple WiFi status and config for single adapter setup."""
    config = load_wifi_simple_config()
    current = get_current_wifi()
    interfaces = get_network_interfaces()
    
    # Find wlan0 interface
    wlan0_connected = False
    wlan0_ip = None
    for iface in interfaces:
        if iface.get('name') == 'wlan0' and iface.get('type') == 'wifi':
            wlan0_connected = bool(iface.get('state') == 'up' and iface.get('ip'))
            wlan0_ip = iface.get('ip')
            break
    
    # Get current SSID from active connection
    current_ssid = current.get('ssid', '') if current else ''
    
    # Get saved SSID: priority is our config > NetworkManager saved connection
    saved_ssid = config.get('ssid', '')
    if not saved_ssid:
        # Try to get from NetworkManager (e.g., configured via RPi Imager)
        saved_ssid = get_saved_wifi_ssid()
    
    return jsonify({
        'success': True,
        'status': {
            'connected': wlan0_connected,
            'ssid': current_ssid or saved_ssid,  # Show current if connected, else saved
            'ip': wlan0_ip,
            'saved_ssid': saved_ssid,
            'has_saved_password': bool(config.get('password')) or bool(saved_ssid),  # NM has password too
            'ip_mode': config.get('ip_mode', 'dhcp'),
            'static_ip': config.get('static_ip', ''),
            'gateway': config.get('gateway', ''),
            'dns': config.get('dns', '8.8.8.8')
        }
    })

@wifi_bp.route('/simple/config', methods=['POST'])
def wifi_simple_config_set():
    """Save simple WiFi configuration."""
    try:
        data = request.get_json(silent=True) or {}
        config = load_wifi_simple_config()
        
        # Update fields
        if 'ssid' in data:
            config['ssid'] = data['ssid']
        if 'password' in data and data['password']:
            config['password'] = data['password']
        if 'ip_mode' in data:
            config['ip_mode'] = data['ip_mode']
        if 'static_ip' in data:
            config['static_ip'] = data['static_ip']
        if 'gateway' in data:
            config['gateway'] = data['gateway']
        if 'dns' in data:
            config['dns'] = data['dns']
        
        save_wifi_simple_config(config)
        
        return jsonify({
            'success': True,
            'message': 'Configuration WiFi enregistrée'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@wifi_bp.route('/simple/connect', methods=['POST'])
def wifi_simple_connect():
    """Connect to WiFi with simple config."""
    try:
        data = request.get_json(silent=True) or {}
        ssid = data.get('ssid', '')
        password = data.get('password', '')
        
        if not ssid:
            # Try to use saved config
            config = load_wifi_simple_config()
            ssid = config.get('ssid', '')
            if not password:
                password = config.get('password', '')
        
        if not ssid:
            return jsonify({
                'success': False,
                'message': 'SSID requis'
            }), 400
        
        # Save config if password provided
        if password:
            config = load_wifi_simple_config()
            config['ssid'] = ssid
            config['password'] = password
            save_wifi_simple_config(config)
        
        # Connect using nmcli
        result = connect_wifi(ssid, password, interface='wlan0')
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# WIFI FAILOVER ROUTES
# ============================================================================

@wifi_bp.route('/failover/status', methods=['GET'])
def failover_status():
    """Get WiFi failover status with full config for frontend."""
    from services.network_service import get_network_interfaces, get_current_wifi
    
    status = get_wifi_failover_status()
    config = get_wifi_failover_config()
    interfaces = get_network_interfaces()
    
    # Get current WiFi connection (checks all interfaces)
    current_wifi = get_current_wifi()
    
    # Find WiFi interfaces
    wifi_interfaces = []
    active_interface = None
    active_ssid = None
    active_ip = None
    
    for iface in interfaces:
        if iface.get('type') == 'wifi':
            wifi_info = {
                'name': iface['name'],
                'mac': iface.get('mac', ''),
                'ip': iface.get('ip'),
                'ssid': None,
                'is_usb': 'wlan1' in iface['name'] or iface['name'].startswith('wlx'),
                'phy_exists': iface.get('state') != 'unavailable'
            }
            # Check if this interface is connected
            if iface.get('state') == 'up' and iface.get('ip'):
                active_interface = iface['name']
                active_ip = iface['ip']
                # Get SSID for this specific interface
                iface_wifi = get_current_wifi(iface['name'])
                if iface_wifi and iface_wifi.get('ssid'):
                    active_ssid = iface_wifi['ssid']
                    wifi_info['ssid'] = iface_wifi['ssid']
            wifi_interfaces.append(wifi_info)
    
    # Fallback: if we have current_wifi but couldn't match interface
    if not active_ssid and current_wifi and current_wifi.get('ssid'):
        active_ssid = current_wifi['ssid']
        if current_wifi.get('interface'):
            active_interface = current_wifi['interface']
    
    # Check if NetworkManager has saved connections for the SSIDs
    primary_ssid = config.get('primary_ssid', '')
    secondary_ssid = config.get('secondary_ssid', '')
    
    has_primary_password = bool(config.get('primary_password'))
    has_secondary_password = bool(config.get('secondary_password'))
    
    # Also check NetworkManager saved connections
    try:
        import subprocess
        nm_result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
            capture_output=True, text=True, timeout=10
        )
        if nm_result.returncode == 0:
            saved_connections = [line.split(':')[0] for line in nm_result.stdout.strip().split('\n') 
                               if ':wifi' in line.lower() or ':802-11-wireless' in line.lower()]
            # If the SSID has a saved NM profile, consider it has password
            if primary_ssid and primary_ssid in saved_connections:
                has_primary_password = True
            if secondary_ssid and secondary_ssid in saved_connections:
                has_secondary_password = True
    except:
        pass
    
    # Build comprehensive status for frontend
    full_status = {
        # Config fields
        'hardware_failover_enabled': config.get('hardware_failover_enabled', True),
        'network_failover_enabled': config.get('network_failover_enabled', True),
        'primary_interface': config.get('primary_interface', 'wlan1'),
        'secondary_interface': config.get('secondary_interface', 'wlan0'),
        'primary_ssid': primary_ssid,
        'secondary_ssid': secondary_ssid,
        'has_primary_password': has_primary_password,
        'has_secondary_password': has_secondary_password,
        'ip_mode': config.get('ip_mode', 'dhcp'),
        'static_ip': config.get('static_ip', ''),
        'gateway': config.get('gateway', ''),
        'dns': config.get('dns', '8.8.8.8'),
        'check_interval': config.get('check_interval', 30),
        # Status fields
        'enabled': status.get('enabled', False),
        'running': status.get('running', False),
        'active_interface': active_interface,
        'active_ssid': active_ssid,
        'active_ip': active_ip,
        'wifi_interfaces': wifi_interfaces,
        'last_failover': status.get('last_failover'),
        'failover_count': status.get('failover_count', 0)
    }
    
    return jsonify({
        'success': True,
        'status': full_status
    })

@wifi_bp.route('/failover/config', methods=['GET'])
def failover_config_get():
    """Get WiFi failover configuration."""
    config = get_wifi_failover_config()
    return jsonify({
        'success': True,
        'config': config
    })

@wifi_bp.route('/failover/config', methods=['POST'])
def failover_config_set():
    """Update WiFi failover configuration."""
    try:
        data = request.get_json(silent=True) or {}
        config = get_wifi_failover_config()
        
        # Update allowed fields
        allowed_fields = [
            'hardware_failover_enabled', 'primary_interface', 'secondary_interface',
            'network_failover_enabled', 'primary_ssid', 'secondary_ssid',
            'ip_mode', 'static_ip', 'gateway', 'dns', 'check_interval'
        ]
        
        for field in allowed_fields:
            if field in data:
                config[field] = data[field]
        
        # Handle passwords separately - only update if not empty
        if data.get('primary_password'):
            config['primary_password'] = data['primary_password']
        if data.get('secondary_password'):
            config['secondary_password'] = data['secondary_password']
        
        result = save_wifi_failover_config(config)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Configuration saved'
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', 'Failed to save configuration')
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@wifi_bp.route('/failover/apply', methods=['POST'])
def failover_apply():
    """Apply WiFi failover - connect the appropriate interface."""
    try:
        from services.watchdog_service import perform_wifi_failover
        from services.network_service import get_wifi_failover_config
        
        config = get_wifi_failover_config()
        
        result = perform_wifi_failover(
            config.get('primary_ssid', ''),
            config.get('primary_password', ''),
            config.get('primary_interface', 'wlan0')
        )
        
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@wifi_bp.route('/failover/interfaces', methods=['GET'])
def failover_interfaces():
    """Get all WiFi interfaces with their status."""
    from services.network_service import get_wifi_interfaces
    interfaces = get_wifi_interfaces()
    return jsonify({
        'success': True,
        'interfaces': interfaces
    })

@wifi_bp.route('/failover/disconnect', methods=['POST'])
def failover_disconnect():
    """Disconnect a specific WiFi interface."""
    try:
        data = request.get_json(silent=True) or {}
        interface = data.get('interface', '')
        
        if not interface:
            return jsonify({
                'success': False,
                'message': 'Interface required'
            }), 400
        
        result = disconnect_wifi(interface)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# WIFI CONFIG CLONING
# ============================================================================

@wifi_bp.route('/clone', methods=['POST'])
def clone_config():
    """Clone WiFi configuration from one interface to another."""
    try:
        data = request.get_json(silent=True) or {}
        source = data.get('source', 'wlan0')
        target = data.get('target', 'wlan1')
        
        result = clone_wifi_config(source, target)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@wifi_bp.route('/auto-configure', methods=['POST'])
def auto_configure():
    """Auto-configure a WiFi interface by cloning from connected interface."""
    try:
        data = request.get_json(silent=True) or {}
        interface = data.get('interface', 'wlan1')
        
        result = auto_configure_wifi_interface(interface)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============================================================================
# FAILOVER SECTION-SPECIFIC APPLY ENDPOINTS
# ============================================================================

@wifi_bp.route('/failover/apply/hardware', methods=['POST'])
def apply_hardware_failover():
    """Apply only the hardware failover settings (interface priority)."""
    try:
        data = request.get_json(silent=True) or {}
        
        # Get current config
        config = get_wifi_failover_config()
        
        # Update only hardware failover fields
        if 'hardware_failover_enabled' in data:
            config['hardware_failover_enabled'] = data['hardware_failover_enabled']
        if 'primary_interface' in data:
            config['primary_interface'] = data['primary_interface']
        if 'secondary_interface' in data:
            config['secondary_interface'] = data['secondary_interface']
        
        # Save config
        save_wifi_failover_config(config)
        
        # If hardware failover enabled, auto-configure the secondary interface
        if config.get('hardware_failover_enabled', True):
            secondary = config.get('secondary_interface', 'wlan0')
            # Check if secondary needs config
            auto_result = auto_configure_wifi_interface(secondary)
            
            return jsonify({
                'success': True,
                'message': 'Hardware failover settings applied',
                'auto_config': auto_result
            })
        
        return jsonify({
            'success': True,
            'message': 'Hardware failover settings saved'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@wifi_bp.route('/failover/apply/network', methods=['POST'])
def apply_network_failover():
    """Apply only the network failover settings (SSID configuration)."""
    try:
        data = request.get_json(silent=True) or {}
        
        # Get current config
        config = get_wifi_failover_config()
        
        # Update only network failover fields
        if 'network_failover_enabled' in data:
            config['network_failover_enabled'] = data['network_failover_enabled']
        if 'primary_ssid' in data:
            config['primary_ssid'] = data['primary_ssid']
        if 'secondary_ssid' in data:
            config['secondary_ssid'] = data['secondary_ssid']
        if data.get('primary_password'):
            config['primary_password'] = data['primary_password']
        if data.get('secondary_password'):
            config['secondary_password'] = data['secondary_password']
        
        # Save config
        save_wifi_failover_config(config)
        
        # If a primary SSID is configured, try to connect the primary interface
        if config.get('primary_ssid'):
            primary_iface = config.get('primary_interface', 'wlan1')
            connect_result = connect_wifi(
                config['primary_ssid'],
                config.get('primary_password'),
                primary_iface
            )
            
            return jsonify({
                'success': True,
                'message': 'Network failover settings applied',
                'connection': connect_result
            })
        
        return jsonify({
            'success': True,
            'message': 'Network failover settings saved'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@wifi_bp.route('/failover/apply/ip', methods=['POST'])
def apply_ip_config():
    """Apply only the IP configuration settings.
    
    Only applies changes if static IP is requested.
    DHCP mode just saves the config without touching interfaces
    (NetworkManager handles DHCP automatically).
    """
    try:
        from services.network_service import configure_static_ip
        
        data = request.get_json(silent=True) or {}
        
        # Get current config
        config = get_wifi_failover_config()
        
        # Update only IP config fields
        if 'ip_mode' in data:
            config['ip_mode'] = data['ip_mode']
        if 'static_ip' in data:
            config['static_ip'] = data['static_ip']
        if 'gateway' in data:
            config['gateway'] = data['gateway']
        if 'dns' in data:
            config['dns'] = data['dns']
        
        # Save config
        save_wifi_failover_config(config)
        
        # Only apply if static IP is requested
        interfaces_configured = []
        
        if config.get('ip_mode') == 'static' and config.get('static_ip'):
            # Parse static IP (format: 192.168.1.100/24)
            ip_parts = config['static_ip'].split('/')
            ip = ip_parts[0]
            prefix = ip_parts[1] if len(ip_parts) > 1 else '24'
            
            for iface in ['wlan0', 'wlan1']:
                # Check if interface is connected (has active connection)
                check = subprocess.run(
                    ['nmcli', '-t', '-f', 'DEVICE,STATE', 'device', 'status'],
                    capture_output=True, text=True, timeout=5
                )
                
                is_connected = False
                for line in check.stdout.strip().split('\n'):
                    if line.startswith(f'{iface}:') and 'connected' in line:
                        is_connected = True
                        break
                
                if is_connected:
                    result = configure_static_ip(
                        iface, ip, prefix,
                        config.get('gateway', ''),
                        config.get('dns', '8.8.8.8')
                    )
                    interfaces_configured.append({'interface': iface, 'result': result})
            
            return jsonify({
                'success': True,
                'message': f'Static IP applied to {len(interfaces_configured)} interface(s)',
                'interfaces': interfaces_configured
            })
        else:
            # DHCP mode - just save config, NetworkManager handles the rest
            return jsonify({
                'success': True,
                'message': 'DHCP mode saved. NetworkManager manages IP automatically.',
                'interfaces': []
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# -*- coding: utf-8 -*-
"""
Network Service - Network interfaces, WiFi, and AP mode management
Version: 2.30.16

Changes in 2.30.16:
- Added get_public_ip() for Meeting API heartbeat v1.8.0+ ip_public field
"""

import os
import re
import json
import time
import socket
import logging
import subprocess
import fcntl
from datetime import datetime

from .platform_service import run_command, is_raspberry_pi
from .config_service import load_config
from config import (
    WIFI_FAILOVER_CONFIG_FILE, AP_CONFIG_FILE
)

logger = logging.getLogger(__name__)

# Lock file for failover operations (prevents race conditions between Gunicorn workers)
FAILOVER_LOCK_FILE = '/tmp/network_failover.lock'

# ============================================================================
# MEETING API INTEGRATION
# ============================================================================

def _trigger_heartbeat_on_failover(action):
    """
    Trigger immediate heartbeat when network failover occurs.
    Uses dynamic import to avoid circular dependencies.
    
    Args:
        action: Failover action that occurred (e.g., 'failover_to_wlan1', 'eth0_priority', etc)
    """
    try:
        from .meeting_service import trigger_immediate_heartbeat
        
        # Only trigger for actual network changes, not for "no change" statuses
        if action in ['failover_to_wlan1', 'failover_to_wlan0', 'eth0_priority']:
            logger.info(f"[Network] Triggering immediate heartbeat due to failover: {action}")
            trigger_immediate_heartbeat()
    except Exception as e:
        logger.debug(f"[Network] Could not trigger heartbeat: {e}")

# ============================================================================
# IP ADDRESS UTILITIES
# ============================================================================

def get_local_ip():
    """Get local IP address using socket connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_public_ip():
    """
    Get public IP address by querying external services.
    Used for Meeting API heartbeat (v1.8.0+ ip_public field).
    
    Returns:
        str: Public IP address or None if detection fails
    """
    import urllib.request
    import ssl
    
    # List of services that return plain text IP
    services = [
        'https://api.ipify.org',
        'https://ipinfo.io/ip',
        'https://checkip.amazonaws.com',
    ]
    
    # SSL context that doesn't verify (some services have cert issues)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    for service in services:
        try:
            request = urllib.request.Request(service, headers={'User-Agent': 'curl/7.64.0'})
            with urllib.request.urlopen(request, timeout=5, context=ssl_context) as response:
                ip = response.read().decode('utf-8').strip()
                # Validate IP format
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                    return ip
        except Exception:
            continue
    
    return None

def get_preferred_ip():
    """Get local IP address based on interface priority.
    
    Priority: eth0 (Ethernet) > wlan1 (USB WiFi) > wlan0 (built-in WiFi)
    Configurable via NETWORK_INTERFACE_PRIORITY in config.env
    """
    # Default priority order - Ethernet first, then WiFi interfaces
    priority_order = ['eth0', 'wlan1', 'wlan0', 'enp0s3', 'end0']
    
    # Try to read custom priority from config file
    try:
        config = load_config()
        custom_priority = config.get('NETWORK_INTERFACE_PRIORITY', '')
        if custom_priority:
            priority_order = [iface.strip() for iface in custom_priority.split(',')]
    except:
        pass
    
    # Get all interface IPs
    interface_ips = {}
    try:
        result = subprocess.run(['ip', '-4', 'addr'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            current_iface = None
            for line in result.stdout.split('\n'):
                # Match interface line: "2: eth0: <BROADCAST,MULTICAST,UP,..."
                if ': ' in line and not line.startswith(' '):
                    parts = line.split(': ')
                    if len(parts) >= 2:
                        current_iface = parts[1].split('@')[0]  # Handle eth0@if2 format
                # Match IP line: "    inet 192.168.1.191/24 ..."
                elif current_iface and 'inet ' in line and 'scope global' in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ip = parts[1].split('/')[0]
                        if not ip.startswith('127.'):
                            interface_ips[current_iface] = ip
    except Exception as e:
        print(f"[get_preferred_ip] Error getting interfaces: {e}")
    
    # Return IP of highest priority interface
    for iface in priority_order:
        if iface in interface_ips:
            return interface_ips[iface]
    
    # Fallback: any non-loopback IP
    for ip in interface_ips.values():
        return ip
    
    # Ultimate fallback: socket method
    return get_local_ip()

# ============================================================================
# NETWORK INTERFACE MANAGEMENT
# ============================================================================

def get_network_interfaces():
    """
    Get list of all network interfaces with their status.
    
    Returns:
        list: List of interface dicts with name, type, status, ip, mac, etc.
    """
    interfaces = []
    
    # Get interface list
    result = run_command("ip -o link show", timeout=5)
    if not result['success']:
        return interfaces
    
    for line in result['stdout'].split('\n'):
        if not line.strip():
            continue
        
        # Parse interface line
        match = re.match(r'^\d+:\s+(\S+)[@:].*state\s+(\S+)', line)
        if not match:
            continue
        
        name = match.group(1)
        state = match.group(2)
        
        # Skip loopback
        if name == 'lo':
            continue
        
        iface = {
            'name': name,
            'state': state.lower(),
            'type': 'unknown',
            'ip': None,
            'mac': None,
            'gateway': None
        }
        
        # Determine type
        if name.startswith('eth') or name.startswith('enp') or name.startswith('end'):
            iface['type'] = 'ethernet'
        elif name.startswith('wlan') or name.startswith('wlp'):
            iface['type'] = 'wifi'
        elif name.startswith('docker') or name.startswith('br-'):
            iface['type'] = 'bridge'
        elif name.startswith('veth'):
            iface['type'] = 'virtual'
        
        # Get MAC address
        mac_match = re.search(r'link/ether\s+([0-9a-fA-F:]+)', line)
        if mac_match:
            iface['mac'] = mac_match.group(1)
        
        # Get IP address
        ip_result = run_command(f"ip -4 addr show {name} | grep 'inet '", timeout=5)
        if ip_result['success'] and ip_result['stdout']:
            ip_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', ip_result['stdout'])
            if ip_match:
                iface['ip'] = ip_match.group(1)
                iface['prefix'] = ip_match.group(2)
        
        interfaces.append(iface)
    
    # Get default gateway for each interface
    gw_result = run_command("ip route show default", timeout=5)
    if gw_result['success']:
        for line in gw_result['stdout'].split('\n'):
            match = re.search(r'default via (\S+) dev (\S+)', line)
            if match:
                gw_ip = match.group(1)
                gw_dev = match.group(2)
                for iface in interfaces:
                    if iface['name'] == gw_dev:
                        iface['gateway'] = gw_ip
                        iface['is_default'] = True
                        break
    
    return interfaces

def get_interface_details(interface_name):
    """
    Get detailed information about a specific interface.
    
    Args:
        interface_name: Name of the interface (e.g., 'eth0', 'wlan0')
    
    Returns:
        dict: Detailed interface information
    """
    details = {
        'name': interface_name,
        'exists': False,
        'state': 'unknown',
        'type': 'unknown',
        'addresses': [],
        'statistics': {}
    }
    
    # Check if interface exists
    result = run_command(f"ip link show {interface_name}", timeout=5)
    if not result['success']:
        return details
    
    details['exists'] = True
    
    # Parse state
    if 'state UP' in result['stdout']:
        details['state'] = 'up'
    elif 'state DOWN' in result['stdout']:
        details['state'] = 'down'
    
    # Get addresses
    addr_result = run_command(f"ip addr show {interface_name}", timeout=5)
    if addr_result['success']:
        for line in addr_result['stdout'].split('\n'):
            # IPv4
            ipv4_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)', line)
            if ipv4_match:
                details['addresses'].append({
                    'type': 'ipv4',
                    'address': ipv4_match.group(1),
                    'prefix': int(ipv4_match.group(2))
                })
            
            # IPv6
            ipv6_match = re.search(r'inet6\s+([0-9a-fA-F:]+)/(\d+)', line)
            if ipv6_match:
                details['addresses'].append({
                    'type': 'ipv6',
                    'address': ipv6_match.group(1),
                    'prefix': int(ipv6_match.group(2))
                })
    
    # Get statistics
    stats_result = run_command(f"cat /sys/class/net/{interface_name}/statistics/{{rx_bytes,tx_bytes,rx_packets,tx_packets}}", timeout=5)
    if stats_result['success']:
        lines = stats_result['stdout'].split('\n')
        if len(lines) >= 4:
            details['statistics'] = {
                'rx_bytes': int(lines[0]) if lines[0].isdigit() else 0,
                'tx_bytes': int(lines[1]) if lines[1].isdigit() else 0,
                'rx_packets': int(lines[2]) if lines[2].isdigit() else 0,
                'tx_packets': int(lines[3]) if lines[3].isdigit() else 0
            }
    
    return details

def configure_static_ip(interface, ip_address, netmask='24', gateway=None, dns=None):
    """
    Configure a static IP address for an interface via NetworkManager.
    
    Args:
        interface: Interface name
        ip_address: IP address to set
        netmask: Network prefix length (default: 24)
        gateway: Optional gateway IP
        dns: Optional DNS server(s)
    
    Returns:
        dict: {success: bool, message: str}
    """
    # Validate IP
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip_address):
        return {'success': False, 'message': 'Invalid IP address format'}
    
    try:
        # Get active connection name for this interface
        result = run_command(f"nmcli -t -f NAME,DEVICE con show --active | grep ':{interface}$' | cut -d: -f1", timeout=5)
        conn_name = result['stdout'].strip() if result['success'] else None
        
        if not conn_name:
            return {'success': False, 'message': f'No active connection found for {interface}'}
        
        # Build nmcli command for static IP
        addr = f"{ip_address}/{netmask}"
        cmd = f"sudo nmcli con mod \"{conn_name}\" ipv4.method manual ipv4.addresses {addr}"
        
        if gateway:
            cmd += f" ipv4.gateway {gateway}"
        
        if dns:
            dns_str = dns if isinstance(dns, str) else ','.join(dns)
            cmd += f" ipv4.dns {dns_str}"
        
        # Apply changes
        result = run_command(cmd, timeout=10)
        if not result['success']:
            return {'success': False, 'message': f"Failed to configure: {result['stderr']}"}
        
        # Reapply connection
        result = run_command(f"sudo nmcli device reapply {interface}", timeout=15)
        if result['success']:
            return {'success': True, 'message': f'Static IP {addr} configured on {interface}'}
        else:
            return {'success': False, 'message': result['stderr'] or 'Failed to reapply connection'}
    
    except Exception as e:
        return {'success': False, 'message': str(e)}

def configure_dhcp(interface):
    """
    Configure an interface to use DHCP via NetworkManager.
    
    Args:
        interface: Interface name
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        # Get active connection name for this interface
        result = run_command(f"nmcli -t -f NAME,DEVICE con show --active | grep ':{interface}$' | cut -d: -f1", timeout=5)
        conn_name = result['stdout'].strip() if result['success'] else None
        
        if conn_name:
            # Modify existing connection to use DHCP
            run_command(f"sudo nmcli con mod \"{conn_name}\" ipv4.method auto ipv4.addresses '' ipv4.gateway ''", timeout=10)
            # Reapply connection to get new DHCP lease
            result = run_command(f"sudo nmcli device reapply {interface}", timeout=15)
            if result['success']:
                return {'success': True, 'message': f'DHCP configured on {interface} via NetworkManager'}
            else:
                return {'success': False, 'message': result['stderr'] or 'Failed to reapply connection'}
        else:
            # No active connection, try to reconnect
            result = run_command(f"sudo nmcli device connect {interface}", timeout=15)
            if result['success']:
                return {'success': True, 'message': f'DHCP reconnected on {interface}'}
            else:
                return {'success': False, 'message': result['stderr'] or 'Failed to connect interface'}
    
    except Exception as e:
        return {'success': False, 'message': str(e)}

def set_interface_priority(interfaces_priority):
    """
    Set the priority order for network interfaces.
    Saves to config.env and applies routing metrics.
    
    Args:
        interfaces_priority: List of interface names in priority order
    
    Returns:
        dict: {success: bool, message: str}
    """
    from .config_service import load_config, save_config
    
    # 1. Save to config.env for persistence across reboots
    try:
        config = load_config()
        priority_str = ','.join(interfaces_priority)
        config['NETWORK_INTERFACE_PRIORITY'] = priority_str
        save_config(config)
        logger.info(f"Saved interface priority to config: {priority_str}")
    except Exception as e:
        logger.error(f"Failed to save interface priority: {e}")
        return {'success': False, 'message': f'Failed to save config: {e}'}
    
    # 2. Apply routing metrics for immediate effect
    # Lower metric = higher priority
    applied_count = 0
    for idx, iface in enumerate(interfaces_priority):
        metric = (idx + 1) * 100  # 100, 200, 300, etc.
        
        # Get current gateway for this interface via NetworkManager
        gw_result = run_command(f"ip route show dev {iface} | grep default | head -1", timeout=5)
        if gw_result['success'] and gw_result['stdout']:
            match = re.search(r'default via (\S+)', gw_result['stdout'])
            if match:
                gateway = match.group(1)
                # Update route with new metric
                run_command(f"sudo ip route del default via {gateway} dev {iface} 2>/dev/null", timeout=5)
                result = run_command(f"sudo ip route add default via {gateway} dev {iface} metric {metric}", timeout=5)
                if result['success']:
                    applied_count += 1
                    logger.info(f"Set {iface} metric to {metric} via {gateway}")
    
    # 3. Also try to update NetworkManager connection priorities
    for idx, iface in enumerate(interfaces_priority):
        # Get the active connection name for this interface
        conn_result = run_command(f"nmcli -t -f NAME,DEVICE con show --active | grep ':{iface}$' | cut -d: -f1", timeout=5)
        if conn_result['success'] and conn_result['stdout'].strip():
            conn_name = conn_result['stdout'].strip()
            # Set autoconnect-priority (higher = more priority, we invert since lower metric = higher priority)
            priority = 100 - (idx * 10)  # 100, 90, 80, etc.
            run_command(f"sudo nmcli con mod \"{conn_name}\" connection.autoconnect-priority {priority}", timeout=5)
            logger.info(f"Set nmcli priority {priority} for connection '{conn_name}' ({iface})")
    
    return {
        'success': True, 
        'message': f'Interface priorities updated ({applied_count} routes applied)',
        'priority': interfaces_priority
    }

# ============================================================================
# WIFI MANAGEMENT
# ============================================================================

def get_wifi_networks(interface='wlan0'):
    """
    Scan for available WiFi networks.
    
    Args:
        interface: WiFi interface name (default: wlan0)
    
    Returns:
        list: List of network dicts with ssid, signal, security, etc.
    """
    networks = []
    
    # Trigger a scan
    run_command(f"sudo iw dev {interface} scan trigger", timeout=5)
    time.sleep(2)  # Wait for scan to complete
    
    # Get scan results
    result = run_command(f"sudo iw dev {interface} scan", timeout=30)
    
    if not result['success']:
        # Try with wpa_cli as fallback
        result = run_command(f"sudo wpa_cli -i {interface} scan_results", timeout=10)
        if result['success']:
            # Parse wpa_cli format
            for line in result['stdout'].split('\n')[1:]:  # Skip header
                parts = line.split('\t')
                if len(parts) >= 5:
                    networks.append({
                        'bssid': parts[0],
                        'frequency': int(parts[1]) if parts[1].isdigit() else 0,
                        'signal': int(parts[2]) if parts[2].lstrip('-').isdigit() else 0,
                        'security': 'WPA' if 'WPA' in parts[3] else ('WEP' if 'WEP' in parts[3] else 'Open'),
                        'ssid': parts[4] if len(parts) > 4 else ''
                    })
        return networks
    
    # Parse iw scan output
    current_network = {}
    
    for line in result['stdout'].split('\n'):
        line = line.strip()
        
        if line.startswith('BSS '):
            if current_network and current_network.get('ssid'):
                networks.append(current_network)
            bssid_match = re.search(r'BSS ([0-9a-fA-F:]+)', line)
            current_network = {
                'bssid': bssid_match.group(1) if bssid_match else '',
                'ssid': '',
                'signal': 0,
                'frequency': 0,
                'channel': 0,
                'security': 'Open'
            }
        
        elif line.startswith('SSID:'):
            current_network['ssid'] = line.split(':', 1)[1].strip()
        
        elif line.startswith('signal:'):
            match = re.search(r'(-?\d+)', line)
            if match:
                current_network['signal'] = int(match.group(1))
        
        elif line.startswith('freq:'):
            match = re.search(r'(\d+)', line)
            if match:
                current_network['frequency'] = int(match.group(1))
        
        elif 'WPA' in line or 'RSN' in line:
            current_network['security'] = 'WPA2' if 'RSN' in line else 'WPA'
        
        elif 'WEP' in line:
            current_network['security'] = 'WEP'
    
    # Don't forget the last network
    if current_network and current_network.get('ssid'):
        networks.append(current_network)
    
    # Sort by signal strength
    networks.sort(key=lambda x: x.get('signal', -100), reverse=True)
    
    return networks

def get_current_wifi(interface=None):
    """
    Get current WiFi connection information.
    
    Args:
        interface: WiFi interface name (if None, checks all wifi interfaces)
    
    Returns:
        dict: Current connection info or None if not connected
    """
    # Use nmcli for reliable detection (iw may not be installed)
    if interface:
        # Check specific interface
        result = run_command(f"nmcli -t -f DEVICE,STATE,CONNECTION dev status | grep '^{interface}:'", timeout=5)
        if not result['success']:
            return None
        line = result['stdout'].strip()
        if ':connected:' not in line:
            return None
        parts = line.split(':')
        if len(parts) >= 3:
            return {
                'interface': parts[0],
                'ssid': parts[2],
                'bssid': '',
                'frequency': 0,
                'signal': 0,
                'tx_bitrate': '',
                'rx_bitrate': ''
            }
        return None
    else:
        # Check all WiFi interfaces for any connection
        result = run_command("nmcli -t -f DEVICE,STATE,CONNECTION dev status | grep wlan", timeout=5)
        if not result['success']:
            return None
        
        for line in result['stdout'].strip().split('\n'):
            if ':connected:' in line:
                parts = line.split(':')
                if len(parts) >= 3:
                    return {
                        'interface': parts[0],
                        'ssid': parts[2],
                        'bssid': '',
                        'frequency': 0,
                        'signal': 0,
                        'tx_bitrate': '',
                        'rx_bitrate': ''
                    }
        return None

def connect_wifi(ssid, password=None, interface='wlan0'):
    """
    Connect to a WiFi network.
    
    Args:
        ssid: Network SSID
        password: Network password (None for open networks)
        interface: WiFi interface name
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        # Check if NetworkManager is available
        nm_result = run_command("which nmcli", timeout=5)
        
        if nm_result['success'] and nm_result['stdout']:
            # Use NetworkManager
            if password:
                cmd = f'nmcli device wifi connect "{ssid}" password "{password}" ifname {interface}'
            else:
                cmd = f'nmcli device wifi connect "{ssid}" ifname {interface}'
            
            result = run_command(cmd, timeout=60)
            
            if result['success']:
                return {'success': True, 'message': f'Connected to {ssid}'}
            else:
                return {'success': False, 'message': result['stderr'] or 'Connection failed'}
        
        else:
            # Use wpa_supplicant directly
            # Create a temporary config
            config_content = f'''
ctrl_interface=/var/run/wpa_supplicant
update_config=1

network={{
    ssid="{ssid}"
'''
            if password:
                config_content += f'    psk="{password}"\n'
            else:
                config_content += '    key_mgmt=NONE\n'
            config_content += '}\n'
            
            # Write config
            config_file = f'/tmp/wpa_{interface}.conf'
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            # Stop existing wpa_supplicant
            run_command(f"sudo killall wpa_supplicant", timeout=5)
            time.sleep(1)
            
            # Start wpa_supplicant
            result = run_command(
                f"sudo wpa_supplicant -B -i {interface} -c {config_file}",
                timeout=10
            )
            
            if result['success']:
                # Request DHCP
                time.sleep(2)
                run_command(f"sudo dhclient {interface}", timeout=30)
                return {'success': True, 'message': f'Connected to {ssid}'}
            else:
                return {'success': False, 'message': result['stderr'] or 'Connection failed'}
    
    except Exception as e:
        return {'success': False, 'message': str(e)}

def disconnect_wifi(interface='wlan0'):
    """
    Disconnect from current WiFi network.
    
    Args:
        interface: WiFi interface name
    
    Returns:
        dict: {success: bool, message: str}
    """
    # Try NetworkManager first
    result = run_command(f"nmcli device disconnect {interface}", timeout=10)
    
    if not result['success']:
        # Fallback to wpa_cli
        result = run_command(f"sudo wpa_cli -i {interface} disconnect", timeout=10)
    
    return {
        'success': True,
        'message': f'Disconnected from WiFi on {interface}'
    }


def clone_wifi_config(source_interface='wlan0', target_interface='wlan1'):
    """
    Clone WiFi configuration from one interface to another.
    Copies the active connection profile from source to target.
    
    Args:
        source_interface: Source WiFi interface (default: wlan0)
        target_interface: Target WiFi interface (default: wlan1)
    
    Returns:
        dict: {success: bool, message: str, cloned_ssid: str or None}
    """
    try:
        # Get the active connection on source interface
        conn_result = run_command(
            f"nmcli -t -f NAME,DEVICE con show --active | grep ':{source_interface}$' | cut -d: -f1",
            timeout=5
        )
        
        if not conn_result['success'] or not conn_result['stdout'].strip():
            return {
                'success': False,
                'message': f'No active WiFi connection on {source_interface}',
                'cloned_ssid': None
            }
        
        source_conn_name = conn_result['stdout'].strip()
        logger.info(f"Found source connection: {source_conn_name}")
        
        # Get SSID from source connection
        ssid_result = run_command(
            f'nmcli -t -f 802-11-wireless.ssid con show "{source_conn_name}"',
            timeout=5
        )
        ssid = ''
        if ssid_result['success'] and ssid_result['stdout'].strip():
            ssid = ssid_result['stdout'].strip().split(':')[-1]
        
        # Check if target interface already has a connection for this SSID
        existing_result = run_command(
            f"nmcli -t -f NAME con show | grep -E 'wlan1|{ssid}'",
            timeout=5
        )
        
        # Create new connection name for target
        target_conn_name = f"{ssid}-{target_interface}"
        
        # Check if this connection already exists
        check_result = run_command(f'nmcli con show "{target_conn_name}" 2>/dev/null', timeout=5)
        
        if check_result['success'] and check_result['stdout'].strip():
            # Connection exists, just modify the interface
            logger.info(f"Connection {target_conn_name} exists, updating interface binding")
            result = run_command(
                f'sudo nmcli con mod "{target_conn_name}" connection.interface-name {target_interface}',
                timeout=10
            )
        else:
            # Clone the connection
            logger.info(f"Cloning {source_conn_name} to {target_conn_name}")
            
            # Clone connection profile
            result = run_command(
                f'sudo nmcli con clone "{source_conn_name}" "{target_conn_name}"',
                timeout=10
            )
            
            if not result['success']:
                return {
                    'success': False,
                    'message': f'Failed to clone connection: {result["stderr"]}',
                    'cloned_ssid': None
                }
            
            # Modify the cloned connection to use target interface
            run_command(
                f'sudo nmcli con mod "{target_conn_name}" connection.interface-name {target_interface}',
                timeout=10
            )
        
        logger.info(f"Successfully cloned WiFi config to {target_interface}")
        return {
            'success': True,
            'message': f'WiFi configuration cloned from {source_interface} to {target_interface}',
            'cloned_ssid': ssid,
            'connection_name': target_conn_name
        }
        
    except Exception as e:
        logger.error(f"Error cloning WiFi config: {e}")
        return {
            'success': False,
            'message': str(e),
            'cloned_ssid': None
        }


def auto_configure_wifi_interface(interface='wlan1'):
    """
    Automatically configure a WiFi interface by cloning from another connected interface.
    Used when a new WiFi dongle is inserted.
    
    Args:
        interface: WiFi interface to configure (default: wlan1)
    
    Returns:
        dict: {success: bool, message: str, action: str}
    """
    try:
        # Check if interface already has a connection
        conn_result = run_command(
            f"nmcli -t -f NAME,DEVICE con show --active | grep ':{interface}$'",
            timeout=5
        )
        
        if conn_result['success'] and conn_result['stdout'].strip():
            return {
                'success': True,
                'message': f'{interface} already connected',
                'action': 'already_configured'
            }
        
        # Find a connected WiFi interface to clone from
        for source in ['wlan0', 'wlan1', 'wlan2']:
            if source == interface:
                continue
            
            check_result = run_command(
                f"nmcli -t -f DEVICE,STATE dev | grep '^{source}:connected$'",
                timeout=5
            )
            
            if check_result['success'] and check_result['stdout'].strip():
                # Found a connected interface, clone its config
                clone_result = clone_wifi_config(source, interface)
                
                if clone_result['success']:
                    # Try to connect with the cloned config
                    connect_result = run_command(
                        f'nmcli con up "{clone_result["connection_name"]}"',
                        timeout=30
                    )
                    
                    if connect_result['success']:
                        return {
                            'success': True,
                            'message': f'Cloned WiFi config from {source} and connected {interface}',
                            'action': 'cloned_and_connected',
                            'ssid': clone_result['cloned_ssid']
                        }
                    else:
                        return {
                            'success': True,
                            'message': f'Cloned WiFi config from {source}, connection pending',
                            'action': 'cloned',
                            'ssid': clone_result['cloned_ssid']
                        }
                
                return clone_result
        
        return {
            'success': False,
            'message': 'No connected WiFi interface found to clone from',
            'action': 'no_source'
        }
        
    except Exception as e:
        logger.error(f"Error auto-configuring WiFi interface: {e}")
        return {
            'success': False,
            'message': str(e),
            'action': 'error'
        }

# ============================================================================
# ACCESS POINT MODE
# ============================================================================

def get_ap_status():
    """
    Get the current Access Point status.
    
    Returns:
        dict: AP status including enabled state, SSID, clients
    """
    status = {
        'enabled': False,
        'ssid': '',
        'interface': 'wlan0',
        'ip': '',
        'clients': []
    }
    
    # Check if hostapd is running
    result = run_command("systemctl is-active hostapd", timeout=5)
    status['enabled'] = result['success'] and result['stdout'].strip() == 'active'
    
    if status['enabled']:
        # Get hostapd config
        if os.path.exists('/etc/hostapd/hostapd.conf'):
            try:
                with open('/etc/hostapd/hostapd.conf', 'r') as f:
                    for line in f:
                        if line.startswith('ssid='):
                            status['ssid'] = line.split('=', 1)[1].strip()
                        elif line.startswith('interface='):
                            status['interface'] = line.split('=', 1)[1].strip()
            except:
                pass
        
        # Get AP IP
        ip_result = run_command(f"ip -4 addr show {status['interface']} | grep 'inet '", timeout=5)
        if ip_result['success']:
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_result['stdout'])
            if match:
                status['ip'] = match.group(1)
        
        # Get connected clients
        clients_result = run_command("cat /var/lib/misc/dnsmasq.leases 2>/dev/null", timeout=5)
        if clients_result['success']:
            for line in clients_result['stdout'].split('\n'):
                parts = line.split()
                if len(parts) >= 4:
                    status['clients'].append({
                        'mac': parts[1],
                        'ip': parts[2],
                        'hostname': parts[3] if len(parts) > 3 else 'unknown'
                    })
    
    return status

def load_ap_config():
    """
    Load AP configuration from file.
    
    Returns:
        dict: AP configuration with enabled, ssid, password, channel, interface
    """
    default_config = {
        'ap_enabled': False,
        'enabled': False,
        'ssid': '',
        'password': '',
        'channel': 11,  # Fixed to channel 11 per project requirements
        'interface': 'wlan0',
        'ap_ip': '192.168.4.1',
        'dhcp_range_start': '192.168.4.10',
        'dhcp_range_end': '192.168.4.100',
        'dhcp_lease_time': '24h'
    }
    
    if os.path.exists(AP_CONFIG_FILE):
        try:
            with open(AP_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure ap_enabled key exists
                config['ap_enabled'] = config.get('enabled', config.get('ap_enabled', False))
                return config
        except Exception as e:
            print(f"[Network] Error loading AP config: {e}")
    
    return default_config

def create_access_point(ssid, password, channel=11, interface='wlan0'):
    """
    Create a WiFi Access Point with DHCP server.
    
    Args:
        ssid: Access point SSID
        password: WPA2 password (min 8 characters)
        channel: WiFi channel (default: 11 per project requirements)
        interface: Interface to use (default: wlan0)
    
    Returns:
        dict: {success: bool, message: str}
    """
    if len(password) < 8:
        return {'success': False, 'message': 'Password must be at least 8 characters'}
    
    try:
        # Install required packages if needed
        run_command("sudo apt-get install -y hostapd dnsmasq", timeout=120)
        
        # Stop services first
        run_command("sudo systemctl stop hostapd dnsmasq", timeout=10)
        
        # Ensure wlan0 is available (not managed by NetworkManager in disconnected state)
        # Disconnect from any WiFi network first, then set to unmanaged for AP use
        run_command(f"sudo nmcli device disconnect {interface}", timeout=10)
        run_command(f"sudo nmcli device set {interface} managed no", timeout=5)
        
        # Configure hostapd
        hostapd_conf = f"""interface={interface}
driver=nl80211
ssid={ssid}
hw_mode=g
channel={channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
        
        with open('/etc/hostapd/hostapd.conf', 'w') as f:
            f.write(hostapd_conf)
        
        # Configure dnsmasq for DHCP server
        dnsmasq_conf = f"""# dnsmasq AP configuration - Generated by RTSP Recorder
interface={interface}
bind-interfaces
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
server=8.8.4.4
log-facility=/var/log/rpi-cam/dnsmasq.log
log-dhcp
"""
        
        # Create log directory if needed
        os.makedirs('/var/log/rpi-cam', exist_ok=True)
        
        # Write to dnsmasq.d to not overwrite system config
        with open('/etc/dnsmasq.d/rpi-cam-ap.conf', 'w') as f:
            f.write(dnsmasq_conf)
        
        # Configure static IP for AP interface
        run_command(f"sudo ip addr flush dev {interface}", timeout=5)
        run_command(f"sudo ip addr add 192.168.4.1/24 dev {interface}", timeout=5)
        run_command(f"sudo ip link set {interface} up", timeout=5)
        
        # Enable IP forwarding
        run_command("sudo sysctl -w net.ipv4.ip_forward=1", timeout=5)
        
        # Start services
        run_command("sudo systemctl unmask hostapd", timeout=5)
        result = run_command("sudo systemctl start hostapd dnsmasq", timeout=10)
        
        if result['success']:
            # Save AP config
            ap_config = {
                'enabled': True,
                'ssid': ssid,
                'password': password,
                'channel': channel,
                'interface': interface
            }
            os.makedirs(os.path.dirname(AP_CONFIG_FILE), exist_ok=True)
            with open(AP_CONFIG_FILE, 'w') as f:
                json.dump(ap_config, f)
            
            return {'success': True, 'message': f'Access Point "{ssid}" started on 192.168.4.1'}
        else:
            return {'success': False, 'message': result['stderr'] or 'Failed to start AP'}
    
    except Exception as e:
        return {'success': False, 'message': str(e)}

def stop_access_point(interface='wlan0'):
    """
    Stop the Access Point.
    
    Args:
        interface: Interface used for AP
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        # Stop services
        run_command("sudo systemctl stop hostapd dnsmasq", timeout=10)
        
        # Flush IP
        run_command(f"sudo ip addr flush dev {interface}", timeout=5)
        
        # Return wlan0 to NetworkManager management
        run_command(f"sudo nmcli device set {interface} managed yes", timeout=5)
        
        # Update config
        if os.path.exists(AP_CONFIG_FILE):
            with open(AP_CONFIG_FILE, 'r') as f:
                config = json.load(f)
            config['enabled'] = False
            with open(AP_CONFIG_FILE, 'w') as f:
                json.dump(config, f)
        
        # Re-apply WiFi/Ethernet priority policy
        manage_wifi_based_on_ethernet()
        
        return {'success': True, 'message': 'Access Point stopped'}
    
    except Exception as e:
        return {'success': False, 'message': str(e)}

# ============================================================================
# WIFI FAILOVER CONFIGURATION
# ============================================================================

def get_wifi_failover_config():
    """
    Get WiFi failover configuration.
    
    Returns:
        dict: Failover configuration with hardware_failover_enabled defaulting to True
        
    Note: Supports both old (backup_*) and new (primary_*/secondary_*) field names
    for backward compatibility. The code uses secondary_* internally for WiFi backup.
    """
    default_config = {
        'enabled': False,
        'hardware_failover_enabled': True,  # Enable automatic eth0 > wlan1 > wlan0 failover by default
        'network_failover_enabled': True,   # Enable network-based failover checks
        'check_interval': 30,
        'primary_interface': 'wlan1',       # Primary WiFi (USB 5GHz dongle)
        'secondary_interface': 'wlan0',     # Secondary WiFi (built-in 2.4GHz)
        'primary_ssid': '',
        'primary_password': '',
        'secondary_ssid': '',
        'secondary_password': '',
        'ip_mode': 'dhcp',
        'static_ip': '',
        'gateway': '',
        'dns': '8.8.8.8',
        'ping_targets': ['8.8.8.8', '1.1.1.1']
    }
    
    if os.path.exists(WIFI_FAILOVER_CONFIG_FILE):
        try:
            with open(WIFI_FAILOVER_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
                # Migrate old field names to new ones (backward compatibility)
                if 'backup_ssid' in config and not config.get('secondary_ssid'):
                    config['secondary_ssid'] = config.pop('backup_ssid')
                if 'backup_password' in config and not config.get('secondary_password'):
                    config['secondary_password'] = config.pop('backup_password')
                if 'backup_interface' in config and not config.get('secondary_interface'):
                    config['secondary_interface'] = config.pop('backup_interface')
                
                default_config.update(config)
        except:
            pass
    
    return default_config

def save_wifi_failover_config(config):
    """
    Save WiFi failover configuration.
    
    Args:
        config: Failover configuration dict
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        os.makedirs(os.path.dirname(WIFI_FAILOVER_CONFIG_FILE), exist_ok=True)
        with open(WIFI_FAILOVER_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return {'success': True, 'message': 'Failover configuration saved'}
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_wifi_failover_status():
    """
    Get current WiFi failover status.
    
    Returns:
        dict: Current failover status
    """
    config = get_wifi_failover_config()
    
    status = {
        'enabled': config.get('enabled', False),
        'current_interface': None,
        'primary_interface': config.get('primary_interface', 'eth0'),
        'secondary_interface': config.get('secondary_interface', 'wlan0'),
        'primary_connected': False,
        'secondary_connected': False,
        'last_failover': None
    }
    
    # Check primary interface status
    try:
        result = run_command(f"ip addr show {status['primary_interface']} 2>/dev/null | grep 'inet '")
        status['primary_connected'] = bool(result.strip())
        if status['primary_connected']:
            status['current_interface'] = status['primary_interface']
    except:
        pass
    
    # Check secondary interface status
    try:
        result = run_command(f"ip addr show {status['secondary_interface']} 2>/dev/null | grep 'inet '")
        status['secondary_connected'] = bool(result.strip())
        if not status['primary_connected'] and status['secondary_connected']:
            status['current_interface'] = status['secondary_interface']
    except:
        pass
    
    return status

def get_wifi_interfaces():
    """
    Get list of WiFi interfaces available on the system.
    
    Returns:
        list: List of WiFi interface names
    """
    interfaces = []
    try:
        result = run_command("iw dev 2>/dev/null | grep Interface | awk '{print $2}'")
        for line in result.strip().split('\n'):
            if line.strip():
                interfaces.append(line.strip())
    except:
        # Fallback: check for common interface names
        common_names = ['wlan0', 'wlan1', 'wlp2s0', 'wlp3s0']
        for name in common_names:
            try:
                run_command(f"ip link show {name} 2>/dev/null")
                interfaces.append(name)
            except:
                pass
    
    return interfaces

# ============================================================================
# WIFI OVERRIDE MANAGEMENT
# ============================================================================

def get_ethernet_status():
    """Check if Ethernet is connected and functional."""
    import json as json_mod
    
    try:
        result = subprocess.run(['ip', '-j', 'link', 'show', 'eth0'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            data = json_mod.loads(result.stdout)
            if data and len(data) > 0:
                state = data[0].get('operstate', 'unknown')
                return {
                    'present': True,
                    'connected': state.lower() == 'up',
                    'state': state
                }
    except:
        pass
    return {'present': False, 'connected': False, 'state': 'unknown'}

def get_wifi_manual_override():
    """Check if WiFi manual override is enabled."""
    config = load_config()
    return config.get('WIFI_MANUAL_OVERRIDE', 'no') == 'yes'

def set_wifi_manual_override(enabled):
    """Set WiFi manual override."""
    from .config_service import save_config
    config = load_config()
    config['WIFI_MANUAL_OVERRIDE'] = 'yes' if enabled else 'no'
    save_config(config)
    return {'success': True}

def get_interface_connection_status(interface):
    """
    Get detailed connection status for an interface.
    
    Returns:
        dict: {present, connected, has_ip, ip, state}
    """
    status = {
        'present': False,
        'connected': False,
        'has_ip': False,
        'ip': None,
        'state': 'unknown'
    }
    
    try:
        # Check device state via nmcli
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'DEVICE,STATE', 'device', 'status'],
            capture_output=True, text=True, timeout=5
        )
        
        for line in result.stdout.strip().split('\n'):
            if line.startswith(f'{interface}:'):
                status['present'] = True
                state = line.split(':')[1] if ':' in line else ''
                status['state'] = state
                status['connected'] = state == 'connected'
                break
        
        if not status['present']:
            return status
        
        # Check if has IP
        ip_result = subprocess.run(
            ['ip', '-4', '-o', 'addr', 'show', interface],
            capture_output=True, text=True, timeout=5
        )
        
        if ip_result.returncode == 0 and 'inet ' in ip_result.stdout:
            import re
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_result.stdout)
            if match:
                status['has_ip'] = True
                status['ip'] = match.group(1)
    
    except Exception as e:
        logger.error(f"Error getting status for {interface}: {e}")
    
    return status

def disconnect_interface(interface):
    """Disconnect an interface via NetworkManager."""
    try:
        result = subprocess.run(
            ['sudo', 'nmcli', 'device', 'disconnect', interface],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            logger.info(f"[Failover] {interface} disconnected")
            return True
        elif 'not active' in result.stderr.lower() or 'already' in result.stderr.lower():
            return True  # Already disconnected
        else:
            logger.warning(f"[Failover] Failed to disconnect {interface}: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"[Failover] Error disconnecting {interface}: {e}")
        return False

def connect_interface(interface):
    """
    Connect an interface via NetworkManager.
    
    First tries to use existing saved connection.
    For WiFi interfaces, if no saved connection exists, tries to connect
    to the backup SSID configured in wifi_failover.json.
    
    After successful connection, applies static IP if configured.
    
    Args:
        interface: Network interface name (eth0, wlan0, wlan1)
    
    Returns:
        bool: True if connected successfully
    """
    try:
        # Get failover config for IP settings
        config = get_wifi_failover_config()
        
        # First try to connect using saved connection
        result = subprocess.run(
            ['sudo', 'nmcli', 'device', 'connect', interface],
            capture_output=True, text=True, timeout=15
        )
        connected = result.returncode == 0
        
        if connected:
            logger.info(f"[Failover] {interface} connected via saved profile")
        elif interface.startswith('wlan'):
            # If failed and this is a WiFi interface, try configured SSID
            logger.info(f"[Failover] No saved profile for {interface}, trying configured SSID...")
            
            # Match interface to config: wlan1=primary, wlan0=secondary
            if interface == config.get('primary_interface', 'wlan1'):
                ssid = config.get('primary_ssid', '')
                password = config.get('primary_password', '')
            else:
                # Default to secondary (wlan0 or any other)
                ssid = config.get('secondary_ssid', '')
                password = config.get('secondary_password', '')
            
            if ssid:
                logger.info(f"[Failover] Connecting {interface} to SSID: {ssid}")
                
                # Try to connect to the configured SSID
                connect_cmd = [
                    'sudo', 'nmcli', 'device', 'wifi', 'connect', ssid,
                    'ifname', interface
                ]
                if password:
                    connect_cmd.extend(['password', password])
                
                result = subprocess.run(
                    connect_cmd,
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    logger.info(f"[Failover] {interface} connected to {ssid}")
                    connected = True
                else:
                    logger.warning(f"[Failover] Failed to connect {interface} to {ssid}: {result.stderr}")
            else:
                logger.warning(f"[Failover] No SSID configured in wifi_failover.json for {interface}")
        
        # If connected successfully, apply IP settings from failover config
        if connected and interface.startswith('wlan'):
            ip_mode = config.get('ip_mode', 'dhcp')
            if ip_mode == 'static':
                static_ip = config.get('static_ip', '')
                gateway = config.get('gateway', '')
                dns = config.get('dns', '8.8.8.8')
                
                if static_ip:
                    logger.info(f"[Failover] Applying static IP {static_ip} to {interface}")
                    _apply_static_ip_to_interface(interface, static_ip, gateway, dns)
            
            return True
        
        if not connected:
            logger.warning(f"[Failover] Failed to connect {interface}: {result.stderr}")
        return connected
    except Exception as e:
        logger.error(f"[Failover] Error connecting {interface}: {e}")
        return False

def _apply_static_ip_to_interface(interface, static_ip, gateway, dns):
    """
    Apply static IP configuration to an interface via NetworkManager.
    
    Args:
        interface: Network interface name
        static_ip: IP address with prefix (e.g., '192.168.1.100/24')
        gateway: Gateway IP address
        dns: DNS server IP address
    """
    try:
        # Get the active connection name for this interface
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show', '--active'],
            capture_output=True, text=True, timeout=5
        )
        
        connection_name = None
        for line in result.stdout.strip().split('\n'):
            if f':{interface}' in line:
                connection_name = line.split(':')[0]
                break
        
        if not connection_name:
            logger.warning(f"[Failover] No active connection found for {interface}")
            return False
        
        # Add /24 if not present
        if '/' not in static_ip:
            static_ip = f"{static_ip}/24"
        
        # Modify connection to use static IP
        modify_cmds = [
            ['sudo', 'nmcli', 'connection', 'modify', connection_name, 
             'ipv4.method', 'manual', 
             'ipv4.addresses', static_ip],
        ]
        
        if gateway:
            modify_cmds[0].extend(['ipv4.gateway', gateway])
        if dns:
            modify_cmds[0].extend(['ipv4.dns', dns])
        
        for cmd in modify_cmds:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.warning(f"[Failover] Failed to modify connection: {result.stderr}")
                return False
        
        # Reapply the connection to use new settings
        result = subprocess.run(
            ['sudo', 'nmcli', 'device', 'reapply', interface],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            logger.info(f"[Failover] Static IP {static_ip} applied to {interface}")
            return True
        else:
            logger.warning(f"[Failover] Failed to reapply connection: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"[Failover] Error applying static IP: {e}")
        return False

def manage_network_failover():
    """
    Manage network failover between eth0, wlan1, and wlan0.
    
    Priority order: eth0 > wlan1 > wlan0
    Only one interface should be active at a time (except during transitions).
    
    Uses file locking to prevent race conditions between Gunicorn workers.
    
    Returns:
        dict: {active_interface, action, message}
    """
    # Use file lock to prevent concurrent execution by multiple workers
    try:
        lock_fd = open(FAILOVER_LOCK_FILE, 'w')
        try:
            # Non-blocking lock - if already locked, skip this run
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            # Another worker is already running failover
            logger.debug("[Failover] Another worker is handling failover, skipping")
            lock_fd.close()
            return {
                'active_interface': None,
                'action': 'locked',
                'message': 'Failover already in progress by another worker'
            }
    except Exception as e:
        logger.warning(f"[Failover] Could not acquire lock: {e}")
        # Continue anyway on lock error
        lock_fd = None
    
    try:
        return _manage_network_failover_internal()
    finally:
        # Release lock
        if lock_fd:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
            except:
                pass

def _manage_network_failover_internal():
    """Internal failover logic (called with lock held)."""
    # Check AP mode - don't touch wlan0 if AP is active
    ap_config = load_ap_config()
    if ap_config.get('ap_enabled', False):
        logger.info("[Failover] AP mode active, skipping failover management")
        return {
            'active_interface': 'wlan0',
            'action': 'ap_mode',
            'message': 'AP mode active'
        }
    
    # Check manual override
    manual_override = get_wifi_manual_override()
    if manual_override:
        logger.info("[Failover] Manual override enabled, skipping automatic failover")
        return {
            'active_interface': None,
            'action': 'manual_override',
            'message': 'Manual override enabled - all interfaces managed manually'
        }
    
    # Get status of all interfaces
    eth0_status = get_interface_connection_status('eth0')
    wlan1_status = get_interface_connection_status('wlan1')
    wlan0_status = get_interface_connection_status('wlan0')
    
    logger.debug(f"[Failover] eth0: {eth0_status}")
    logger.debug(f"[Failover] wlan1: {wlan1_status}")
    logger.debug(f"[Failover] wlan0: {wlan0_status}")
    
    # Determine which interface should be active
    # Priority: eth0 > wlan1 > wlan0
    
    if eth0_status['present'] and eth0_status['connected'] and eth0_status['has_ip']:
        # eth0 is working - disconnect WiFi interfaces
        target_interface = 'eth0'
        logger.info(f"[Failover] eth0 is active ({eth0_status['ip']}), disabling WiFi")
        
        # Disconnect wlan1 if connected
        if wlan1_status['present'] and wlan1_status['connected']:
            disconnect_interface('wlan1')
        
        # Disconnect wlan0 if connected
        if wlan0_status['present'] and wlan0_status['connected']:
            disconnect_interface('wlan0')
        
        action = 'eth0_priority'
        _trigger_heartbeat_on_failover(action)
        
        return {
            'active_interface': 'eth0',
            'action': action,
            'message': f'Ethernet active ({eth0_status["ip"]}), WiFi disabled'
        }
    
    elif wlan1_status['present']:
        # eth0 is down, try wlan1
        target_interface = 'wlan1'
        
        # Disconnect wlan0 first (lower priority)
        if wlan0_status['present'] and wlan0_status['connected']:
            logger.info("[Failover] Disconnecting wlan0 (lower priority than wlan1)")
            disconnect_interface('wlan0')
        
        if wlan1_status['connected'] and wlan1_status['has_ip']:
            logger.info(f"[Failover] wlan1 is active ({wlan1_status['ip']})")
            return {
                'active_interface': 'wlan1',
                'action': 'wlan1_active',
                'message': f'wlan1 active ({wlan1_status["ip"]})'
            }
        else:
            # Try to connect wlan1
            logger.info("[Failover] eth0 down, connecting wlan1...")
            if connect_interface('wlan1'):
                # Wait a bit for IP
                time.sleep(3)
                wlan1_status = get_interface_connection_status('wlan1')
                if wlan1_status['has_ip']:
                    action = 'failover_to_wlan1'
                    _trigger_heartbeat_on_failover(action)
                    return {
                        'active_interface': 'wlan1',
                        'action': action,
                        'message': f'Failover to wlan1 ({wlan1_status["ip"]})'
                    }
            
            # wlan1 failed, fall through to wlan0
            logger.warning("[Failover] wlan1 failed to connect, trying wlan0")
    
    # Last resort: wlan0
    if wlan0_status['present']:
        if wlan0_status['connected'] and wlan0_status['has_ip']:
            logger.info(f"[Failover] wlan0 is active ({wlan0_status['ip']})")
            return {
                'active_interface': 'wlan0',
                'action': 'wlan0_active',
                'message': f'wlan0 active ({wlan0_status["ip"]})'
            }
        else:
            # Try to connect wlan0
            logger.info("[Failover] Connecting wlan0 (last resort)...")
            if connect_interface('wlan0'):
                time.sleep(3)
                wlan0_status = get_interface_connection_status('wlan0')
                if wlan0_status['has_ip']:
                    action = 'failover_to_wlan0'
                    _trigger_heartbeat_on_failover(action)
                    return {
                        'active_interface': 'wlan0',
                        'action': action,
                        'message': f'Failover to wlan0 ({wlan0_status["ip"]})'
                    }
    
    # No interface available
    logger.error("[Failover] No network interface available!")
    return {
        'active_interface': None,
        'action': 'no_network',
        'message': 'No network interface available'
    }

def manage_wifi_based_on_ethernet():
    """Legacy function - now calls manage_network_failover()."""
    return manage_network_failover()

def get_wlan0_status():
    """Get wlan0 interface status."""
    status = {
        'present': False,
        'connected': False,
        'managed': False,  # True if auto-disabled because eth is up
        'ap_mode': False
    }
    
    try:
        # Check if in AP mode
        ap_config = load_ap_config()
        if ap_config.get('ap_enabled', False):
            result = subprocess.run(['systemctl', 'is-active', 'hostapd'],
                                   capture_output=True, text=True, timeout=5)
            if result.stdout.strip() == 'active':
                status['present'] = True
                status['ap_mode'] = True
                return status
        
        # Check wlan0 status via nmcli
        result = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,STATE', 'device'],
                               capture_output=True, text=True, timeout=5)
        for line in result.stdout.strip().split('\n'):
            if line.startswith('wlan0:'):
                status['present'] = True
                state = line.split(':')[1] if ':' in line else ''
                status['connected'] = state == 'connected'
                status['managed'] = state == 'disconnected'
                break
    except Exception as e:
        print(f"[Network] Error getting wlan0 status: {e}")
    
    return status

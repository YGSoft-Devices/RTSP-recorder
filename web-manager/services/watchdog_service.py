# -*- coding: utf-8 -*-
"""
Watchdog Service - RTSP service monitoring and WiFi failover
Version: 2.30.7

Changelog:
  - 2.30.6: Fix health check to detect CSI mode (python3 rpi_csi_rtsp_server.py)
"""

import os
import re
import json
import time
import threading
from datetime import datetime, timedelta

from flask import has_request_context, request

from .platform_service import run_command, is_raspberry_pi
from .camera_service import find_camera_device
from .network_service import (
    get_network_interfaces, get_current_wifi, connect_wifi,
    get_wifi_failover_config, manage_network_failover
)
from .config_service import load_config
from .i18n_service import t as i18n_t, resolve_request_lang
from config import (
    SERVICE_NAME, WATCHDOG_STATE_FILE,
    WIFI_FAILOVER_CONFIG_FILE
)

# ============================================================================
# GLOBAL STATE
# ============================================================================

watchdog_state = {
    'rtsp': {
        'enabled': False,
        'running': False,
        'last_check': None,
        'last_restart': None,
        'restart_count': 0,
        'consecutive_failures': 0
    },
    'wifi_failover': {
        'enabled': False,
        'running': False,
        'current_state': 'primary',  # 'primary', 'backup', 'disconnected'
        'active_interface': None,    # 'eth0', 'wlan1', 'wlan0', or None
        'last_check': None,
        'last_failover': None,
        'failover_count': 0
    },
    'lock': threading.Lock()
}

# ---------------------------------------------------------------------------
# I18n helpers
# ---------------------------------------------------------------------------

def _resolve_lang(config=None):
    if config is None:
        try:
            config = load_config()
        except Exception:
            config = {}
    req = request if has_request_context() else None
    return resolve_request_lang(req, config)


def _t(key, config=None, **params):
    return i18n_t(key, lang=_resolve_lang(config), params=params)

# ============================================================================
# RTSP SERVICE HEALTH CHECK
# ============================================================================

def check_camera_available():
    """
    Check if a camera device is available.
    
    Returns:
        dict: {available: bool, device: str, message: str}
    """
    device = find_camera_device()
    
    if device:
        return {
            'available': True,
            'device': device,
            'message': f'Camera found at {device}'
        }
    else:
        return {
            'available': False,
            'device': None,
            'message': _t('ui.watchdog.camera_not_found')
        }

def check_rtsp_service_status():
    """
    Check the status of the RTSP streaming service.
    
    Returns:
        dict: Service status information
    """
    from .config_service import get_service_status
    return get_service_status(SERVICE_NAME)

def check_rtsp_stream_health(rtsp_url=None, timeout=5):
    """
    Check if the RTSP stream is actually working.
    
    Uses port check instead of ffprobe because ffprobe doesn't support
    Digest authentication well, which is used by our RTSP server.
    
    Args:
        rtsp_url: RTSP URL to check (default: local stream with auth from config)
        timeout: Connection timeout in seconds
    
    Returns:
        dict: {healthy: bool, message: str, latency: float}
    """
    start_time = time.time()
    
    # Get RTSP port from config
    config = load_config()
    rtsp_port = config.get('RTSP_PORT', '8554')
    
    # Method 1: Check if port is listening (most reliable)
    port_check = run_command(
        f'ss -tuln | grep -q ":{rtsp_port}" && echo "OK"',
        timeout=3
    )
    
    latency = time.time() - start_time
    
    if port_check['success'] and 'OK' in port_check.get('stdout', ''):
        # Port is open, also verify RTSP process is running
        # Check for test-launch (USB mode) or rpi_csi_rtsp_server.py (CSI mode)
        process_check = run_command(
            'pgrep -f "test-launch|rpi_csi_rtsp_server" >/dev/null && echo "OK"',
            timeout=2
        )
        
        if process_check['success'] and 'OK' in process_check.get('stdout', ''):
            return {
                'healthy': True,
                'message': f'RTSP server listening on port {rtsp_port}',
                'latency': round(latency, 3)
            }
    
    return {
        'healthy': False,
        'message': f'RTSP port {rtsp_port} not responding',
        'latency': round(latency, 3)
    }

def check_rtsp_service_health():
    """
    Comprehensive health check for RTSP service.
    
    Returns:
        dict: Complete health status
    """
    health = {
        'timestamp': datetime.now().isoformat(),
        'overall': 'unknown',
        'camera': check_camera_available(),
        'service': check_rtsp_service_status(),
        'stream': {'healthy': False, 'message': _t('ui.watchdog.stream_not_checked')}
    }
    
    # Check stream only if service is running
    if health['service']['active']:
        health['stream'] = check_rtsp_stream_health()
    
    # Determine overall health
    if not health['camera']['available']:
        health['overall'] = 'error'
        health['message'] = 'Camera not available'
    elif not health['service']['active']:
        health['overall'] = 'warning'
        health['message'] = 'Service not running'
    elif not health['stream']['healthy']:
        health['overall'] = 'warning'
        health['message'] = 'Stream not accessible'
    else:
        health['overall'] = 'healthy'
        health['message'] = 'All systems operational'
    
    return health

# ============================================================================
# RTSP SERVICE RECOVERY
# ============================================================================

def restart_rtsp_service(reason='manual'):
    """
    Restart the RTSP streaming service.
    
    Args:
        reason: Reason for restart (for logging)
    
    Returns:
        dict: {success: bool, message: str}
    """
    global watchdog_state
    
    from .config_service import control_service
    
    # Stop service
    stop_result = control_service(SERVICE_NAME, 'stop')
    
    # Wait a moment
    time.sleep(2)
    
    # Start service
    start_result = control_service(SERVICE_NAME, 'start')
    if start_result.get('success'):
        try:
            from .camera_service import reapply_scheduler_after_rtsp_restart

            threading.Thread(
                target=reapply_scheduler_after_rtsp_restart,
                kwargs={'delay_sec': 1.5, 'retries': 10, 'retry_delay_sec': 0.5},
                daemon=True,
                name='reapply-profiles-after-watchdog-restart'
            ).start()
        except Exception:
            pass
    
    # Update state
    with watchdog_state['lock']:
        if start_result['success']:
            watchdog_state['rtsp']['last_restart'] = datetime.now().isoformat()
            watchdog_state['rtsp']['restart_count'] += 1
    
    if start_result['success']:
        return {
            'success': True,
            'message': f'RTSP service restarted ({reason})'
        }
    else:
        return {
            'success': False,
            'message': f"Failed to restart: {start_result['message']}"
        }

def recover_camera():
    """
    Attempt to recover camera device.
    
    Returns:
        dict: Recovery result
    """
    # Try to reset USB device
    result = run_command("sudo usb_rescan.sh 2>/dev/null || true", timeout=10)
    
    # Wait for device to re-enumerate
    time.sleep(3)
    
    # Check if camera is now available
    camera = check_camera_available()
    
    if camera['available']:
        return {
            'success': True,
            'message': f"Camera recovered at {camera['device']}"
        }
    else:
        return {
            'success': False,
            'message': _t('ui.watchdog.camera_recovery_failed')
        }

# ============================================================================
# RTSP WATCHDOG LOOP
# ============================================================================

def rtsp_watchdog_loop(stop_event=None, check_interval=30, max_consecutive_failures=3):
    """
    Background watchdog loop for RTSP service.
    
    Args:
        stop_event: Threading event to signal stop
        check_interval: Seconds between checks
        max_consecutive_failures: Failures before restart
    """
    global watchdog_state
    
    with watchdog_state['lock']:
        watchdog_state['rtsp']['running'] = True
        watchdog_state['rtsp']['enabled'] = True
    
    consecutive_failures = 0
    
    while True:
        if stop_event and stop_event.is_set():
            break
        
        try:
            # Perform health check
            health = check_rtsp_service_health()
            
            with watchdog_state['lock']:
                watchdog_state['rtsp']['last_check'] = health['timestamp']
            
            if health['overall'] == 'healthy':
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                
                with watchdog_state['lock']:
                    watchdog_state['rtsp']['consecutive_failures'] = consecutive_failures
                
                # Attempt recovery if too many failures
                if consecutive_failures >= max_consecutive_failures:
                    print(f"[Watchdog] {consecutive_failures} consecutive failures, attempting restart")
                    
                    # If camera missing, try recovery first
                    if not health['camera']['available']:
                        recover_camera()
                        time.sleep(2)
                    
                    # Restart service
                    restart_rtsp_service(reason='watchdog')
                    consecutive_failures = 0
        
        except Exception as e:
            print(f"[Watchdog] Error in check loop: {e}")
        
        # Wait for next check
        if stop_event:
            stop_event.wait(check_interval)
        else:
            time.sleep(check_interval)
    
    with watchdog_state['lock']:
        watchdog_state['rtsp']['running'] = False

def get_rtsp_watchdog_status():
    """
    Get current RTSP watchdog status.
    
    Returns:
        dict: Watchdog status
    """
    with watchdog_state['lock']:
        return {
            'enabled': watchdog_state['rtsp']['enabled'],
            'running': watchdog_state['rtsp']['running'],
            'last_check': watchdog_state['rtsp']['last_check'],
            'last_restart': watchdog_state['rtsp']['last_restart'],
            'restart_count': watchdog_state['rtsp']['restart_count'],
            'consecutive_failures': watchdog_state['rtsp']['consecutive_failures']
        }

def enable_rtsp_watchdog():
    """Enable the RTSP watchdog."""
    global watchdog_state
    with watchdog_state['lock']:
        watchdog_state['rtsp']['enabled'] = True
    return {'success': True, 'message': _t('ui.watchdog.rtsp.enabled')}

def disable_rtsp_watchdog():
    """Disable the RTSP watchdog."""
    global watchdog_state
    with watchdog_state['lock']:
        watchdog_state['rtsp']['enabled'] = False
    return {'success': True, 'message': _t('ui.watchdog.rtsp.disabled')}

# ============================================================================
# WIFI FAILOVER
# ============================================================================

def check_network_connectivity(interface=None, ping_targets=None):
    """
    Check network connectivity by pinging targets.
    
    Args:
        interface: Specific interface to test
        ping_targets: List of IPs to ping
    
    Returns:
        dict: {connected: bool, latency: float, target: str}
    """
    if ping_targets is None:
        ping_targets = ['8.8.8.8', '1.1.1.1', '208.67.222.222']
    
    for target in ping_targets:
        cmd = f"ping -c 1 -W 3 {target}"
        if interface:
            cmd = f"ping -c 1 -W 3 -I {interface} {target}"
        
        result = run_command(cmd, timeout=5)
        
        if result['success']:
            # Parse latency
            match = re.search(r'time=(\d+\.?\d*)', result['stdout'])
            latency = float(match.group(1)) if match else 0
            
            return {
                'connected': True,
                'latency': latency,
                'target': target
            }
    
    return {
        'connected': False,
        'latency': None,
        'target': None
    }

def perform_wifi_failover(backup_ssid, backup_password, backup_interface='wlan0'):
    """
    Perform failover to backup WiFi network.
    
    Args:
        backup_ssid: SSID of backup network
        backup_password: Password for backup network
        backup_interface: WiFi interface
    
    Returns:
        dict: Failover result
    """
    global watchdog_state
    
    print(f"[WiFi Failover] Connecting to backup network: {backup_ssid}")
    
    result = connect_wifi(backup_ssid, backup_password, backup_interface)
    
    if result['success']:
        # Wait for connection to establish
        time.sleep(5)
        
        # Verify connectivity
        connectivity = check_network_connectivity(backup_interface)
        
        if connectivity['connected']:
            with watchdog_state['lock']:
                watchdog_state['wifi_failover']['current_state'] = 'backup'
                watchdog_state['wifi_failover']['last_failover'] = datetime.now().isoformat()
                watchdog_state['wifi_failover']['failover_count'] += 1
            
            return {
                'success': True,
                'message': f'Failed over to {backup_ssid}',
                'latency': connectivity['latency']
            }
    
    return {
        'success': False,
        'message': f"Failover failed: {result.get('message', 'Unknown error')}"
    }

def perform_wifi_failback(primary_interface='eth0'):
    """
    Fail back to primary network when it becomes available.
    
    Args:
        primary_interface: Primary network interface
    
    Returns:
        dict: Failback result
    """
    global watchdog_state
    
    # Check primary connectivity
    connectivity = check_network_connectivity(primary_interface)
    
    if connectivity['connected']:
        with watchdog_state['lock']:
            watchdog_state['wifi_failover']['current_state'] = 'primary'
        
        return {
            'success': True,
            'message': _t('ui.watchdog.failover.primary_restored'),
            'latency': connectivity['latency']
        }
    
    return {
        'success': False,
        'message': _t('ui.watchdog.failover.primary_unavailable')
    }

def wifi_failover_watchdog_loop(stop_event=None):
    """
    Background watchdog loop for network failover management.
    
    Uses the new manage_network_failover() function which properly handles
    priority between eth0 > wlan1 > wlan0 and ensures only one interface
    is active at a time.
    
    Args:
        stop_event: Threading event to signal stop
    """
    global watchdog_state
    
    with watchdog_state['lock']:
        watchdog_state['wifi_failover']['running'] = True
    
    # Initial delay to let the system stabilize on boot
    time.sleep(10)
    
    while True:
        if stop_event and stop_event.is_set():
            break
        
        try:
            config = get_wifi_failover_config()
            hardware_failover = config.get('hardware_failover_enabled', True)
            
            # Always run failover management for hardware failover
            # (ensuring only one interface is active at a time)
            if hardware_failover:
                with watchdog_state['lock']:
                    watchdog_state['wifi_failover']['enabled'] = True
                    previous_state = watchdog_state['wifi_failover'].get('active_interface')
                
                # Run the failover logic
                result = manage_network_failover()
                
                with watchdog_state['lock']:
                    watchdog_state['wifi_failover']['last_check'] = datetime.now().isoformat()
                    new_active = result.get('active_interface')
                    action = result.get('action', '')
                    
                    # Update state
                    watchdog_state['wifi_failover']['active_interface'] = new_active
                    
                    # Determine state name for compatibility
                    if new_active == 'eth0':
                        watchdog_state['wifi_failover']['current_state'] = 'primary'
                    elif new_active in ('wlan0', 'wlan1'):
                        watchdog_state['wifi_failover']['current_state'] = 'backup'
                    else:
                        watchdog_state['wifi_failover']['current_state'] = 'disconnected'
                    
                    # Count failover events
                    if 'failover' in action and previous_state != new_active:
                        watchdog_state['wifi_failover']['failover_count'] += 1
                        watchdog_state['wifi_failover']['last_failover'] = datetime.now().isoformat()
                        print(f"[WiFi Failover] Switched to {new_active}: {result.get('message')}")
                
            else:
                # Failover disabled
                with watchdog_state['lock']:
                    watchdog_state['wifi_failover']['enabled'] = False
            
            # Wait for next check
            interval = config.get('check_interval', 30)
            if stop_event:
                stop_event.wait(interval)
            else:
                time.sleep(interval)
        
        except Exception as e:
            print(f"[WiFi Failover] Error in loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(30)
    
    with watchdog_state['lock']:
        watchdog_state['wifi_failover']['running'] = False

def get_wifi_failover_status():
    """
    Get current WiFi failover status.
    
    Returns:
        dict: Failover status
    """
    with watchdog_state['lock']:
        return {
            'enabled': watchdog_state['wifi_failover']['enabled'],
            'running': watchdog_state['wifi_failover']['running'],
            'current_state': watchdog_state['wifi_failover']['current_state'],
            'active_interface': watchdog_state['wifi_failover'].get('active_interface'),
            'last_check': watchdog_state['wifi_failover']['last_check'],
            'last_failover': watchdog_state['wifi_failover']['last_failover'],
            'failover_count': watchdog_state['wifi_failover']['failover_count']
        }

# ============================================================================
# STATE PERSISTENCE
# ============================================================================

def save_watchdog_state():
    """Save watchdog state to file."""
    global watchdog_state
    
    try:
        with watchdog_state['lock']:
            state_to_save = {
                'rtsp': {
                    'restart_count': watchdog_state['rtsp']['restart_count'],
                    'last_restart': watchdog_state['rtsp']['last_restart']
                },
                'wifi_failover': {
                    'failover_count': watchdog_state['wifi_failover']['failover_count'],
                    'last_failover': watchdog_state['wifi_failover']['last_failover']
                }
            }
        
        os.makedirs(os.path.dirname(WATCHDOG_STATE_FILE), exist_ok=True)
        with open(WATCHDOG_STATE_FILE, 'w') as f:
            json.dump(state_to_save, f, indent=2)
    
    except Exception as e:
        print(f"Error saving watchdog state: {e}")

def load_watchdog_state():
    """Load watchdog state from file."""
    global watchdog_state
    
    if os.path.exists(WATCHDOG_STATE_FILE):
        try:
            with open(WATCHDOG_STATE_FILE, 'r') as f:
                saved_state = json.load(f)
            
            with watchdog_state['lock']:
                if 'rtsp' in saved_state:
                    watchdog_state['rtsp'].update(saved_state['rtsp'])
                if 'wifi_failover' in saved_state:
                    watchdog_state['wifi_failover'].update(saved_state['wifi_failover'])
        
        except Exception as e:
            print(f"Error loading watchdog state: {e}")

# -*- coding: utf-8 -*-
"""
Config Service - Configuration management and service control
Version: 2.36.11
"""

import os
import json
import re
import time
import logging
from datetime import datetime, timedelta

from .platform_service import run_command, is_raspberry_pi, PLATFORM
from config import (
    CONFIG_FILE, SERVICE_NAME, DEFAULT_CONFIG, SYSTEM_DEFAULTS,
    CONFIG_METADATA, OPTIONAL_SERVICES
)

logger = logging.getLogger(__name__)

# ============================================================================
# VIDEOIN_* / VIDEO_* COMPATIBILITY MAPPING
# ============================================================================

# Map new VIDEOIN_* variables to legacy VIDEO_* for backwards compatibility
VIDEOIN_LEGACY_MAP = {
    'VIDEOIN_WIDTH': 'VIDEO_WIDTH',
    'VIDEOIN_HEIGHT': 'VIDEO_HEIGHT',
    'VIDEOIN_FPS': 'VIDEO_FPS',
    'VIDEOIN_DEVICE': 'VIDEO_DEVICE',
    'VIDEOIN_FORMAT': 'VIDEO_FORMAT',
}

# Map new VIDEOOUT_* variables to legacy OUTPUT_* for backwards compatibility
VIDEOOUT_LEGACY_MAP = {
    'VIDEOOUT_WIDTH': 'OUTPUT_WIDTH',
    'VIDEOOUT_HEIGHT': 'OUTPUT_HEIGHT',
    'VIDEOOUT_FPS': 'OUTPUT_FPS',
}

# ============================================================================
# CONFIGURATION FILE MANAGEMENT
# ============================================================================

def load_config():
    """
    Load configuration from the config file.
    
    Handles VIDEOIN_*/VIDEOOUT_* with fallback to legacy VIDEO_*/OUTPUT_*.
    Also provides VIDEO_* aliases from VIDEOIN_* for template compatibility.
    
    Returns:
        dict: Configuration dictionary with all settings
    """
    config = DEFAULT_CONFIG.copy()
    
    if not os.path.exists(CONFIG_FILE):
        return config
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Convert to appropriate type
                    if key in config:
                        if isinstance(config[key], bool):
                            config[key] = value.lower() in ('true', '1', 'yes', 'on')
                        elif isinstance(config[key], int):
                            try:
                                config[key] = int(value)
                            except ValueError:
                                pass
                        else:
                            config[key] = value
                    else:
                        config[key] = value
        
        # VIDEOIN_* / VIDEO_* compatibility: prefer VIDEOIN_*, fallback to VIDEO_*
        for new_key, legacy_key in VIDEOIN_LEGACY_MAP.items():
            if new_key not in config and legacy_key in config:
                # Legacy VIDEO_* present but no VIDEOIN_* -> use legacy
                config[new_key] = config[legacy_key]
            elif new_key in config:
                # VIDEOIN_* present -> also expose as VIDEO_* for templates
                config[legacy_key] = config[new_key]
        
        # VIDEOOUT_* / OUTPUT_* compatibility
        for new_key, legacy_key in VIDEOOUT_LEGACY_MAP.items():
            if new_key not in config and legacy_key in config:
                config[new_key] = config[legacy_key]
            elif new_key in config:
                config[legacy_key] = config[new_key]
                
    except Exception as e:
        print(f"Error loading config: {e}")
    
    return config

def save_config(config):
    """
    Save configuration to the config file.
    
    IMPORTANT (v2.30.14): Preserves existing config keys not in the dict passed.
    This prevents accidental data loss when updating partial configs (e.g., profiles scheduler).
    
    Args:
        config: dict with configuration values to save/update
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        # Create directory if needed
        config_dir = os.path.dirname(CONFIG_FILE)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, mode=0o755)
        
        # CRITICAL FIX (v2.30.14): Load existing config to preserve keys not in the update dict
        # This prevents Meeting config from being wiped if a profile/scheduler update calls save_config()
        existing_config = load_config()
        
        # Merge: update existing with new values, but keep existing keys that aren't being updated
        merged_config = existing_config.copy()
        merged_config.update(config)
        
        # VIDEOIN_* / VIDEO_* sync (v2.31.0): Keep both in sync when saving
        # If VIDEOIN_* is set, also set VIDEO_* (and vice versa) for compatibility
        for new_key, legacy_key in VIDEOIN_LEGACY_MAP.items():
            if new_key in merged_config:
                merged_config[legacy_key] = merged_config[new_key]
            elif legacy_key in merged_config:
                merged_config[new_key] = merged_config[legacy_key]
        
        for new_key, legacy_key in VIDEOOUT_LEGACY_MAP.items():
            if new_key in merged_config:
                merged_config[legacy_key] = merged_config[new_key]
            elif legacy_key in merged_config:
                merged_config[new_key] = merged_config[legacy_key]
        
        # Build config content from MERGED config
        lines = ["# RTSP Camera Configuration", f"# Generated: {datetime.now().isoformat()}", ""]
        
        # Group by category if possible
        for key, value in merged_config.items():
            if isinstance(value, bool):
                lines.append(f'{key}={"true" if value else "false"}')
            elif isinstance(value, str) and (' ' in value or '"' in value):
                lines.append(f'{key}="{value}"')
            else:
                lines.append(f'{key}={value}')
        
        # Write atomically
        temp_file = f"{CONFIG_FILE}.tmp"
        with open(temp_file, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        
        os.rename(temp_file, CONFIG_FILE)
        
        return {'success': True, 'message': 'Configuration saved'}
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_config_metadata():
    """
    Get metadata about configuration options.
    
    Returns:
        dict: CONFIG_METADATA with field descriptions, types, and validation
    """
    return CONFIG_METADATA.copy()

def validate_config(config):
    """
    Validate configuration values against metadata.
    
    Args:
        config: dict with configuration values
    
    Returns:
        dict: {valid: bool, errors: list}
    """
    errors = []
    
    for key, value in config.items():
        if key not in CONFIG_METADATA:
            continue
        
        meta = CONFIG_METADATA[key]
        
        # Type validation
        expected_type = meta.get('type', 'text')
        if expected_type == 'number':
            try:
                num_val = int(value) if isinstance(value, str) else value
                if 'min' in meta and num_val < meta['min']:
                    errors.append(f"{key}: value {num_val} is below minimum {meta['min']}")
                if 'max' in meta and num_val > meta['max']:
                    errors.append(f"{key}: value {num_val} is above maximum {meta['max']}")
            except (ValueError, TypeError):
                errors.append(f"{key}: expected number, got {type(value).__name__}")
        
        elif expected_type == 'select':
            options = meta.get('options', [])
            # Case-insensitive comparison for video format fields
            # Also accept any value for dynamic formats detected from camera hardware
            if key in ('VIDEOIN_FORMAT', 'VIDEO_FORMAT'):
                # Accept any format - hardware detection is authoritative
                # Common formats: auto, MJPG, MJPEG, YUYV, YUY2, H264, NV12, I420, etc.
                continue
            # For other select fields, do case-insensitive validation
            value_upper = str(value).upper() if value else ''
            options_upper = [str(o).upper() for o in options]
            if value_upper not in options_upper and value not in options:
                errors.append(f"{key}: '{value}' not in allowed options {options}")
    
    return {'valid': len(errors) == 0, 'errors': errors}

# ============================================================================
# SERVICE MANAGEMENT
# ============================================================================

def get_service_status(service_name=None):
    """
    Get the status of a systemd service.
    
    Args:
        service_name: Name of the service (default: main RTSP service)
    
    Returns:
        dict: {active: bool, status: str, since: str, memory: str, cpu: str}
    """
    if service_name is None:
        service_name = SERVICE_NAME
    
    result = {
        'active': False,
        'status': 'unknown',
        'since': None,
        'memory': None,
        'cpu': None,
        'pid': None
    }
    
    # Check if active
    cmd_result = run_command(f"systemctl is-active {service_name}", timeout=5)
    status = cmd_result['stdout'].strip() if cmd_result['success'] else 'inactive'
    result['status'] = status
    result['active'] = status == 'active'
    
    # Get detailed status
    if result['active']:
        show_result = run_command(
            f"systemctl show {service_name} --property=ActiveEnterTimestamp,MemoryCurrent,MainPID",
            timeout=5
        )
        if show_result['success']:
            for line in show_result['stdout'].split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key == 'ActiveEnterTimestamp' and value:
                        result['since'] = value
                    elif key == 'MemoryCurrent' and value:
                        try:
                            mem_bytes = int(value)
                            result['memory'] = f"{mem_bytes / 1024 / 1024:.1f} MB"
                        except ValueError:
                            pass
                    elif key == 'MainPID' and value:
                        result['pid'] = value
    
    return result

def control_service(service_name, action):
    """
    Control a systemd service (start, stop, restart, enable, disable).
    
    Args:
        service_name: Name of the service
        action: One of 'start', 'stop', 'restart', 'enable', 'disable'
    
    Returns:
        dict: {success: bool, message: str}
    """
    valid_actions = ['start', 'stop', 'restart', 'enable', 'disable', 'reload']
    
    if action not in valid_actions:
        return {'success': False, 'message': f"Invalid action. Use: {', '.join(valid_actions)}"}
    
    # Special case: restarting ourselves - run in background with delay
    if service_name == 'rpi-cam-webmanager' and action in ['restart', 'stop']:
        # Use nohup + sleep to delay the restart and allow response to be sent
        cmd = f"nohup bash -c 'sleep 1 && sudo systemctl {action} {service_name}' >/dev/null 2>&1 &"
        run_command(cmd, timeout=5)
        return {'success': True, 'message': f"Service {service_name} {action} initiated (will occur in 1 second)", 'self_restart': True}
    
    if not service_name:
        service_name = SERVICE_NAME

    result = run_command(f"sudo systemctl {action} {service_name}", timeout=30)
     
    if result['success']:
        if action == 'restart' and service_name == SERVICE_NAME:
            try:
                import threading
                from .camera_service import reapply_scheduler_after_rtsp_restart

                threading.Thread(
                    target=reapply_scheduler_after_rtsp_restart,
                    kwargs={'delay_sec': 1.5, 'retries': 10, 'retry_delay_sec': 0.5},
                    daemon=True,
                    name='reapply-profiles-after-rtsp-restart'
                ).start()
            except Exception:
                pass
        return {'success': True, 'message': f"Service {service_name} {action}ed successfully"}
    else:
        return {'success': False, 'message': result['stderr'] or f"Failed to {action} service"}

def sync_recorder_service(config=None):
    """
    Synchronize the rtsp-recorder service state with RECORD_ENABLE configuration.
    
    If RECORD_ENABLE=yes and service is not running, start it.
    If RECORD_ENABLE=no and service is running, stop it.
    
    Args:
        config: Configuration dict (will load if None)
    
    Returns:
        dict: {success: bool, action: str, message: str}
    """
    if config is None:
        config = load_config()
    
    record_enable = config.get('RECORD_ENABLE', 'no')
    should_run = record_enable == 'yes'
    
    # Check current service status
    status = get_service_status('rtsp-recorder')
    is_running = status.get('active', False)
    
    logger.info(f"sync_recorder_service: RECORD_ENABLE={record_enable}, service running={is_running}")
    
    if should_run and not is_running:
        # Start the recorder service
        logger.info("Starting rtsp-recorder service (RECORD_ENABLE=yes)")
        result = control_service('rtsp-recorder', 'start')
        return {
            'success': result['success'],
            'action': 'started',
            'message': result['message']
        }
    elif not should_run and is_running:
        # Stop the recorder service
        logger.info("Stopping rtsp-recorder service (RECORD_ENABLE=no)")
        result = control_service('rtsp-recorder', 'stop')
        return {
            'success': result['success'],
            'action': 'stopped',
            'message': result['message']
        }
    else:
        action = 'already running' if is_running else 'already stopped'
        return {
            'success': True,
            'action': action,
            'message': f"rtsp-recorder service is {action}"
        }

def get_all_services_status():
    """
    Get status of all RTSP-related services.
    
    Returns:
        dict: {service_name: status_dict} for all services
    """
    services = {
        SERVICE_NAME: 'Main RTSP Streaming',
        'rtsp-watchdog': 'RTSP Watchdog',
        'rtsp-recorder': 'Recording Service',
        'rpi-cam-webmanager': 'Web Manager',
        'rpi-cam-onvif': 'ONVIF Server'
    }
    
    # Add optional services
    for svc_name, svc_info in OPTIONAL_SERVICES.items():
        if svc_name not in services:
            services[svc_name] = svc_info.get('description', svc_name)
    
    result = {}
    for svc_name, description in services.items():
        status = get_service_status(svc_name)
        status['description'] = description
        result[svc_name] = status
    
    return result

# ============================================================================
# SYSTEM INFORMATION
# ============================================================================

def get_system_info():
    """
    Get comprehensive system information.
    Optimized for heartbeat calls - uses fast file reads instead of shell commands where possible.
    
    Returns:
        dict: System information including CPU, memory, disk, temperature
    """
    info = {
        'platform': PLATFORM.copy(),
        'hostname': '',
        'uptime': '',
        'cpu': {},
        'memory': {},
        'disk': {},
        'temperature': None,
        'network': {}
    }
    
    # Hostname - use socket instead of shell command (faster)
    try:
        import socket
        info['hostname'] = socket.gethostname()
    except:
        info['hostname'] = 'unknown'
    
    # Uptime - use /proc/uptime instead of shell command (much faster, no timeout issues)
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_sec = int(float(f.read().split()[0]))
            hours = uptime_sec // 3600
            minutes = (uptime_sec % 3600) // 60
            info['uptime'] = f"{hours}h {minutes}m"
    except:
        info['uptime'] = 'unknown'
    
    # CPU Info
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]
            info['cpu']['load_1m'] = float(load[0])
            info['cpu']['load_5m'] = float(load[1])
            info['cpu']['load_15m'] = float(load[2])
    except:
        pass
    
    # CPU count
    try:
        with open('/proc/cpuinfo', 'r') as f:
            info['cpu']['cores'] = f.read().count('processor')
    except:
        pass
    
    # Memory Info
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                parts = line.split(':')
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]
                    meminfo[key] = int(value) * 1024  # Convert KB to bytes
            
            total = meminfo.get('MemTotal', 0)
            available = meminfo.get('MemAvailable', 0)
            used = total - available
            
            info['memory'] = {
                'total': total,
                'used': used,
                'available': available,
                'percent': round(used / total * 100, 1) if total > 0 else 0
            }
    except:
        pass
    
    # Disk Info - with shorter timeout (2s instead of 5s)
    disk_result = run_command("df -B1 / | tail -1", timeout=2)
    if disk_result['success']:
        try:
            parts = disk_result['stdout'].split()
            if len(parts) >= 4:
                info['disk'] = {
                    'total': int(parts[1]),
                    'used': int(parts[2]),
                    'available': int(parts[3]),
                    'percent': int(parts[4].rstrip('%')) if '%' in parts[4] else 0
                }
        except:
            pass
    
    # Temperature (Raspberry Pi) - with shorter timeout
    if is_raspberry_pi():
        temp_result = run_command("cat /sys/class/thermal/thermal_zone0/temp", timeout=2)
        if temp_result['success']:
            try:
                info['temperature'] = int(temp_result['stdout'].strip()) / 1000.0
            except ValueError:
                pass
    
    # Network interfaces with IPs - with shorter timeout
    ip_result = run_command("ip -4 addr show | grep -E 'inet |^[0-9]'", timeout=2)
    if ip_result['success']:
        try:
            current_iface = None
            for line in ip_result['stdout'].split('\n'):
                if ':' in line and 'inet' not in line:
                    # Interface line
                    parts = line.split(':')
                    if len(parts) >= 2:
                        current_iface = parts[1].strip().split('@')[0]
                elif 'inet ' in line and current_iface:
                    # IP line
                    match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        info['network'][current_iface] = match.group(1)
        except:
            pass
    
    return info

def get_device_description():
    """
    Get a human-readable device description for Meeting API heartbeat.
    
    Format: "Project Name - Platform Model - IP Address"
    Example: "RTSP Recorder - Raspberry Pi 3 Model B Rev 1.2 - 192.168.1.202"
    
    Used in Meeting API /api/devices/{device_key}/online payload as 'note' field.
    Per Meeting API v3.4.33: "note" field allows dynamic device info updates.
    
    Returns:
        str: Device description string
    """
    from config import APP_VERSION, PLATFORM
    from .network_service import get_preferred_ip
    
    # Project name and version
    project = "RTSP Recorder"
    
    # Platform information
    platform_model = PLATFORM.get('model', 'Unknown Platform')
    
    # Local IP address
    try:
        local_ip = get_preferred_ip()
    except:
        local_ip = 'N/A'
    
    # Build description: "Project - Platform - IP"
    description = f"{project} - {platform_model} - {local_ip}"
    
    return description

def get_hostname():
    """Get the current hostname."""
    result = run_command("hostname", timeout=5)
    return result['stdout'] if result['success'] else 'unknown'

def set_hostname(new_hostname):
    """
    Set the system hostname with full persistence (cloud-init aware).
    
    Args:
        new_hostname: New hostname to set
    
    Returns:
        dict: {success: bool, message: str}
    """
    import re
    
    # Validate hostname (RFC 1123)
    if not new_hostname or not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$', new_hostname):
        return {'success': False, 'message': 'Invalid hostname format'}
    
    errors = []
    
    # 1. Set hostname via hostnamectl
    result = run_command(f"sudo hostnamectl set-hostname {new_hostname}", timeout=10)
    if not result['success']:
        errors.append(f"hostnamectl failed: {result['stderr']}")
    
    # 2. Update /etc/hosts
    hosts_cmd = f"sudo sed -i 's/127.0.1.1.*/127.0.1.1\\t{new_hostname}/' /etc/hosts"
    result = run_command(hosts_cmd, timeout=10)
    if not result['success']:
        # Try adding the entry if it doesn't exist
        run_command(f"echo '127.0.1.1\\t{new_hostname}' | sudo tee -a /etc/hosts", timeout=10)
    
    # 3. Disable cloud-init hostname modules (critical for persistence)
    cloud_cfg = "/etc/cloud/cloud.cfg"
    cloud_init_cmds = [
        # Ensure preserve_hostname is true
        f"sudo sed -i 's/preserve_hostname:.*/preserve_hostname: true/' {cloud_cfg} 2>/dev/null || true",
        # Comment out set_hostname module
        f"sudo sed -i 's/^[[:space:]]*- set_hostname/#  - set_hostname  # Disabled for hostname persistence/' {cloud_cfg} 2>/dev/null || true",
        # Comment out update_hostname module
        f"sudo sed -i 's/^[[:space:]]*- update_hostname/#  - update_hostname  # Disabled for hostname persistence/' {cloud_cfg} 2>/dev/null || true",
        # Clear cloud-init's previous hostname cache
        "sudo rm -f /var/lib/cloud/data/previous-hostname 2>/dev/null || true"
    ]
    
    for cmd in cloud_init_cmds:
        run_command(cmd, timeout=10)
    
    if errors:
        return {'success': False, 'message': '; '.join(errors)}
    
    return {'success': True, 'message': f'Hostname set to {new_hostname} (persistent)'}

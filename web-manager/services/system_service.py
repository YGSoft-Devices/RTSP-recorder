# -*- coding: utf-8 -*-
"""
System Service - Diagnostics, logs, updates, and system management
Version: 2.30.28
"""

import os
import re
import json
import time
import tarfile
import tempfile
import shutil
import subprocess
import hashlib
import threading
from datetime import datetime

from .platform_service import run_command, is_raspberry_pi, PLATFORM
from .config_service import load_config, save_config
from config import (
    GITHUB_REPO, APP_VERSION, SERVICE_NAME, SCRIPT_PATH,
    LOG_FILES, CONFIG_FILE, BOOT_CONFIG_FILE
)

UPDATE_STATUS_FILE = '/tmp/rpi-cam-update-status.json'
UPDATE_LOG_FILE = '/var/log/rpi-cam/update_from_file.log'
SCHEDULED_REBOOT_CRON = '/etc/cron.d/rpi-cam-reboot'
SCHEDULED_REBOOT_STATE = '/etc/rpi-cam/reboot_schedule.json'
UPDATE_ALLOWED_PREFIXES = ['opt/rpi-cam-webmanager', 'usr/local/bin']
UPDATE_REPO_BRANCH_FALLBACK = 'main'
UPDATE_WEB_INSTALL_DIR = '/opt/rpi-cam-webmanager'
DEPENDENCIES_FILE_NAME = 'DEPENDENCIES.json'
DEPENDENCIES_FILE_PATH = os.path.join(UPDATE_WEB_INSTALL_DIR, DEPENDENCIES_FILE_NAME)
UPDATE_REPO_BINARIES = {
    'rpi_av_rtsp_recorder.sh': '/usr/local/bin/rpi_av_rtsp_recorder.sh',
    'rpi_csi_rtsp_server.py': '/usr/local/bin/rpi_csi_rtsp_server.py',
    'rtsp_recorder.sh': '/usr/local/bin/rtsp_recorder.sh',
    'rtsp_watchdog.sh': '/usr/local/bin/rtsp_watchdog.sh'
}
RTC_CONFIG_FILE = '/etc/rpi-cam/rtc_config.json'
RTC_I2C_PARAM = 'dtparam=i2c_arm=on'
RTC_OVERLAY_LINE = 'dtoverlay=i2c-rtc,ds3231'
RTC_I2C_DEVICE = '/dev/i2c-1'
RTC_DETECT_KEYWORDS = ['ds3231', 'ds3232']
RTC_I2C_MODULE_FILE = '/etc/modules-load.d/rpi-cam-i2c.conf'

# ============================================================================
# DIAGNOSTIC INFORMATION (Legacy format for frontend compatibility)
# ============================================================================

def get_legacy_diagnostic_info():
    """
    Get diagnostic information in the legacy format expected by the frontend.
    
    Returns:
        dict: Diagnostic data with service, gstreamer, camera, audio, network, encoder, errors
    """
    diag = {
        'service': {},
        'gstreamer': {},
        'camera': {},
        'audio': {},
        'network': {},
        'encoder': {},
        'errors': []
    }
    
    # Check service status
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', SERVICE_NAME],
            capture_output=True, text=True, timeout=5
        )
        diag['service']['status'] = result.stdout.strip()
        diag['service']['active'] = result.returncode == 0
    except Exception as e:
        diag['errors'].append(f"Service check: {e}")
    
    # Check if script exists
    diag['service']['script_exists'] = os.path.exists(SCRIPT_PATH)
    diag['service']['script_path'] = SCRIPT_PATH
    
    # Check GStreamer installation
    try:
        result = subprocess.run(
            ['gst-launch-1.0', '--version'],
            capture_output=True, text=True, timeout=5
        )
        diag['gstreamer']['installed'] = result.returncode == 0
        if result.returncode == 0:
            diag['gstreamer']['version'] = result.stdout.split('\n')[0]
    except FileNotFoundError:
        diag['gstreamer']['installed'] = False
        diag['errors'].append("GStreamer non installé (gst-launch-1.0 introuvable)")
    except Exception as e:
        diag['errors'].append(f"GStreamer check: {e}")
    
    # Check RTSP server plugin
    try:
        result = subprocess.run(
            ['gst-inspect-1.0', 'rtspclientsink'],
            capture_output=True, text=True, timeout=5
        )
        diag['gstreamer']['rtsp_plugin'] = result.returncode == 0
        if result.returncode != 0:
            diag['errors'].append("Plugin RTSP non trouvé (gst-rtsp-server)")
    except Exception as e:
        diag['gstreamer']['rtsp_plugin'] = False
    
    # Check H264 encoder (hardware vs software)
    diag['encoder'] = {
        'hw_plugin_exists': False,
        'hw_device_exists': False,
        'hw_module_loaded': False,
        'hw_available': False,
        'sw_available': False,
        'active_encoder': 'unknown',
        'encoder_type': 'unknown'
    }
    
    try:
        # Check if v4l2h264enc plugin exists
        result = subprocess.run(
            ['gst-inspect-1.0', 'v4l2h264enc'],
            capture_output=True, text=True, timeout=5
        )
        diag['encoder']['hw_plugin_exists'] = result.returncode == 0
        
        # Check if /dev/video11 exists (bcm2835-codec device)
        diag['encoder']['hw_device_exists'] = os.path.exists('/dev/video11')
        
        # Check if bcm2835_codec module is loaded
        result = subprocess.run(
            ['lsmod'],
            capture_output=True, text=True, timeout=5
        )
        diag['encoder']['hw_module_loaded'] = 'bcm2835_codec' in result.stdout
        
        # Hardware is available if all conditions are met
        diag['encoder']['hw_available'] = (
            diag['encoder']['hw_plugin_exists'] and 
            diag['encoder']['hw_device_exists'] and
            diag['encoder']['hw_module_loaded']
        )
        
        # Check if x264enc (software) is available
        result = subprocess.run(
            ['gst-inspect-1.0', 'x264enc'],
            capture_output=True, text=True, timeout=5
        )
        diag['encoder']['sw_available'] = result.returncode == 0
        
        # Determine which encoder is being used by checking running processes
        result = subprocess.run(
            ['pgrep', '-a', '-f', 'test-launch|gst-launch'],
            capture_output=True, text=True, timeout=5
        )
        process_output = result.stdout.lower()
        
        if 'v4l2h264enc' in process_output:
            diag['encoder']['active_encoder'] = 'v4l2h264enc'
            diag['encoder']['encoder_type'] = 'hardware'
        elif 'x264enc' in process_output:
            diag['encoder']['active_encoder'] = 'x264enc'
            diag['encoder']['encoder_type'] = 'software'
        elif diag['encoder']['hw_available']:
            diag['encoder']['active_encoder'] = 'v4l2h264enc (probable)'
            diag['encoder']['encoder_type'] = 'hardware'
        elif diag['encoder']['sw_available']:
            diag['encoder']['active_encoder'] = 'x264enc (probable)'
            diag['encoder']['encoder_type'] = 'software'
        else:
            diag['encoder']['active_encoder'] = 'aucun'
            diag['encoder']['encoder_type'] = 'none'
            diag['errors'].append("Aucun encodeur H264 disponible")
            
    except Exception as e:
        diag['errors'].append(f"Encoder check: {e}")
    
    # Check camera devices
    try:
        result = subprocess.run(
            ['v4l2-ctl', '--list-devices'],
            capture_output=True, text=True, timeout=10
        )
        diag['camera']['v4l2_output'] = result.stdout if result.returncode == 0 else result.stderr
        diag['camera']['devices_found'] = '/dev/video' in result.stdout
    except FileNotFoundError:
        diag['camera']['v4l2_output'] = "v4l2-ctl non installé"
        diag['errors'].append("v4l2-utils non installé")
    except Exception as e:
        diag['errors'].append(f"Camera check: {e}")
    
    # Check libcamera
    if PLATFORM.get('has_libcamera'):
        try:
            result = subprocess.run(
                ['libcamera-hello', '--list-cameras'],
                capture_output=True, text=True, timeout=10
            )
            diag['camera']['libcamera_output'] = result.stdout + result.stderr
            diag['camera']['csi_detected'] = 'Available cameras' in result.stdout
        except Exception as e:
            diag['camera']['libcamera_output'] = str(e)
    
    # Check audio devices
    try:
        result = subprocess.run(
            ['arecord', '-l'],
            capture_output=True, text=True, timeout=10
        )
        diag['audio']['arecord_output'] = result.stdout if result.returncode == 0 else result.stderr
        diag['audio']['devices_found'] = 'card' in result.stdout.lower()
    except FileNotFoundError:
        diag['audio']['arecord_output'] = "alsa-utils non installé"
    except Exception as e:
        diag['errors'].append(f"Audio check: {e}")
    
    # Check network/port availability
    from .config_service import load_config
    config = load_config()
    rtsp_port = config.get('RTSP_PORT', '8554')
    try:
        result = subprocess.run(
            ['ss', '-tuln'],
            capture_output=True, text=True, timeout=5
        )
        diag['network']['listening_ports'] = result.stdout
        diag['network']['rtsp_port_in_use'] = f":{rtsp_port}" in result.stdout
    except Exception as e:
        diag['errors'].append(f"Network check: {e}")
    
    return diag


# ============================================================================
# DIAGNOSTIC INFORMATION (Extended format)
# ============================================================================

def get_diagnostic_info():
    """
    Get comprehensive diagnostic information for troubleshooting.
    
    Returns:
        dict: Diagnostic data including services, hardware, network
    """
    diag = {
        'timestamp': datetime.now().isoformat(),
        'version': APP_VERSION,
        'platform': PLATFORM.copy(),
        'services': {},
        'hardware': {},
        'network': {},
        'storage': {},
        'processes': []
    }
    
    # Service status
    from .config_service import get_all_services_status
    diag['services'] = get_all_services_status()
    
    # Hardware info
    if is_raspberry_pi():
        # CPU temperature
        temp_result = run_command("cat /sys/class/thermal/thermal_zone0/temp", timeout=5)
        if temp_result['success']:
            try:
                diag['hardware']['cpu_temp'] = int(temp_result['stdout']) / 1000.0
            except:
                pass
        
        # CPU frequency
        freq_result = run_command("vcgencmd measure_clock arm", timeout=5)
        if freq_result['success']:
            match = re.search(r'(\d+)', freq_result['stdout'])
            if match:
                diag['hardware']['cpu_freq_mhz'] = int(match.group(1)) / 1000000
        
        # Throttle status
        throttle_result = run_command("vcgencmd get_throttled", timeout=5)
        if throttle_result['success']:
            diag['hardware']['throttle_status'] = throttle_result['stdout']
        
        # Camera detection
        camera_result = run_command("ls -la /dev/video*", timeout=5)
        if camera_result['success']:
            diag['hardware']['video_devices'] = camera_result['stdout'].split('\n')
    
    # Memory info
    mem_result = run_command("free -m", timeout=5)
    if mem_result['success']:
        diag['hardware']['memory'] = mem_result['stdout']
    
    # Network interfaces
    net_result = run_command("ip -br addr", timeout=5)
    if net_result['success']:
        diag['network']['interfaces'] = net_result['stdout']
    
    # Default route
    route_result = run_command("ip route show default", timeout=5)
    if route_result['success']:
        diag['network']['default_route'] = route_result['stdout']
    
    # DNS
    dns_result = run_command("cat /etc/resolv.conf", timeout=5)
    if dns_result['success']:
        diag['network']['dns'] = dns_result['stdout']
    
    # Disk usage
    disk_result = run_command("df -h", timeout=5)
    if disk_result['success']:
        diag['storage']['disk_usage'] = disk_result['stdout']
    
    # Related processes
    proc_result = run_command("ps aux | grep -E 'gst|rtsp|ffmpeg|test-launch' | grep -v grep", timeout=5)
    if proc_result['success']:
        diag['processes'] = proc_result['stdout'].split('\n')
    
    return diag

# ============================================================================
# LOG MANAGEMENT
# ============================================================================

def _tail_file(path, lines):
    result = run_command(f"tail -n {lines} {path} 2>/dev/null", timeout=10)
    if result['success'] and result['stdout']:
        return result['stdout']
    return ''

def _get_latest_gstreamer_log():
    result = run_command("ls -t /var/log/rpi-cam/gstreamer*.log 2>/dev/null | head -1", timeout=5)
    return result['stdout'].strip() if result['success'] else ''

def get_recent_logs(lines=100, source='all'):
    """
    Get recent log entries from various sources.

    Args:
        lines: Number of lines to retrieve
        source: Log source (all, rtsp, webmanager, recorder, watchdog, onvif,
                system, journald, file-rtsp, file-recorder, file-watchdog,
                file-dnsmasq, file-gstreamer, file-all)

    Returns:
        dict: {logs: list, logs_text: str, source: str}
    """
    logs = []
    logs_text = ''

    service_map = {
        'rtsp': SERVICE_NAME,
        'webmanager': 'rpi-cam-webmanager',
        'recorder': 'rtsp-recorder',
        'watchdog': 'rtsp-watchdog',
        'onvif': 'rpi-cam-onvif'
    }

    file_map = {
        'file-rtsp': '/var/log/rpi-cam/rpi_av_rtsp_recorder.log',
        'file-recorder': '/var/log/rpi-cam/rtsp_recorder.log',
        'file-watchdog': '/var/log/rpi-cam/rtsp_watchdog.log',
        'file-dnsmasq': '/var/log/rpi-cam/dnsmasq.log'
    }

    if source == 'file':
        source = 'file-rtsp'

    if source.startswith('file-') or source == 'file-all':
        if source == 'file-gstreamer':
            latest = _get_latest_gstreamer_log()
            logs_text = _tail_file(latest, lines) if latest else ''
        elif source == 'file-all':
            logs_text = _tail_file('/var/log/rpi-cam/*.log', lines)
        else:
            target = file_map.get(source, '')
            logs_text = _tail_file(target, lines) if target else ''
    elif source == 'journald':
        result = run_command(f"sudo journalctl -n {lines} --no-pager -o short-iso", timeout=10)
        logs_text = result['stdout'] if result['success'] else result['stderr']
    else:
        if source in ['all', 'system']:
            result = run_command(f"sudo journalctl -n {lines} --no-pager -p warning", timeout=10)
            if result['success']:
                for line in result['stdout'].split('\n'):
                    if line.strip():
                        logs.append({'source': 'system', 'message': line})

        if source in ['all'] + list(service_map.keys()):
            for key, service in service_map.items():
                if source != 'all' and source != key:
                    continue
                result = run_command(f"sudo journalctl -u {service} -n {lines} --no-pager", timeout=10)
                if result['success']:
                    for line in result['stdout'].split('\n'):
                        if line.strip():
                            logs.append({'source': key, 'message': line})

    return {
        'logs': logs[-lines:] if logs else [],
        'logs_text': logs_text,
        'source': source,
        'count': len(logs) if logs else (len(logs_text.splitlines()) if logs_text else 0)
    }

def get_service_logs(service_name, lines=50, since=None):
    """
    Get logs for a specific service.
    
    Args:
        service_name: Name of the systemd service
        lines: Number of lines
        since: Time filter (e.g., '1h ago', 'today')
    
    Returns:
        dict: {logs: str, service: str}
    """
    cmd = f"sudo journalctl -u {service_name} -n {lines} --no-pager"
    
    if since:
        cmd += f' --since "{since}"'
    
    result = run_command(cmd, timeout=15)
    
    return {
        'logs': result['stdout'] if result['success'] else result['stderr'],
        'service': service_name,
        'success': result['success']
    }

def clean_old_logs(max_size_mb=100):
    """
    Clean old log files to free disk space.
    
    Args:
        max_size_mb: Maximum log size to keep
    
    Returns:
        dict: {success: bool, freed_space: int}
    """
    freed = 0
    
    # Vacuum journalctl logs
    result = run_command(f"sudo journalctl --vacuum-size={max_size_mb}M", timeout=60)
    
    if result['success']:
        # Try to parse freed space from output
        match = re.search(r'Freed\s+(\d+(\.\d+)?)\s*(K|M|G)?', result['stdout'])
        if match:
            value = float(match.group(1))
            unit = match.group(3) or 'B'
            
            if unit == 'K':
                freed = int(value * 1024)
            elif unit == 'M':
                freed = int(value * 1024 * 1024)
            elif unit == 'G':
                freed = int(value * 1024 * 1024 * 1024)
            else:
                freed = int(value)
    
    return {
        'success': result['success'],
        'freed_space': freed,
        'message': result['stdout'] if result['success'] else result['stderr']
    }

# ============================================================================
# UPDATE FROM FILE
# ============================================================================

def _read_update_status():
    if not os.path.exists(UPDATE_STATUS_FILE):
        return {
            'state': 'idle',
            'message': 'No update running',
            'progress': 0,
            'log': []
        }
    try:
        with open(UPDATE_STATUS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            'state': 'error',
            'message': 'Failed to read update status',
            'progress': 0,
            'log': []
        }

def _write_update_status(status):
    status['updated_at'] = datetime.now().isoformat()
    with open(UPDATE_STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2)

def _append_update_log(line: str) -> None:
    if not line:
        return
    try:
        os.makedirs(os.path.dirname(UPDATE_LOG_FILE), exist_ok=True)
        with open(UPDATE_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().isoformat()}] {line}\n")
    except Exception:
        pass

def _set_update_status(state, message=None, progress=None, log_line=None, details=None):
    status = _read_update_status()
    status['state'] = state
    if message is not None:
        status['message'] = message
        _append_update_log(f"{state}: {message}")
    if progress is not None:
        status['progress'] = progress
    if log_line:
        status.setdefault('log', [])
        status['log'].append(log_line)
        status['log'] = status['log'][-200:]
        _append_update_log(log_line)
    if details is not None:
        status['details'] = details
    _write_update_status(status)

def get_update_status():
    return _read_update_status()

def _normalize_update_path(path):
    return path.lstrip('/').replace('\\', '/')

def _is_safe_update_member(member):
    if member.islnk() or member.issym():
        return False
    name = member.name
    if name.startswith('/') or name.startswith('\\'):
        return False
    if '..' in name.split('/'):
        return False
    return True

def _sha256_from_bytes(data):
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest()

def _get_missing_packages(packages: list) -> list:
    missing = []
    for pkg in packages:
        if not pkg:
            continue
        result = run_command(f"dpkg -s {pkg}", timeout=8)
        if not result['success']:
            missing.append(pkg)
    return missing

def _install_packages(packages: list) -> dict:
    if not packages:
        return {'success': True, 'message': 'No packages to install'}
    run_command("sudo apt-get update -qq", timeout=120)
    pkg_list = ' '.join(packages)
    result = run_command(f"sudo apt-get install -y --no-install-recommends {pkg_list}", timeout=600)
    return {
        'success': result['success'],
        'message': result['stdout'] if result['success'] else result['stderr']
    }

def _reset_config_directory() -> dict:
    config_dir = os.path.dirname(CONFIG_FILE)
    if not os.path.isdir(config_dir):
        os.makedirs(config_dir, exist_ok=True)
        return {'success': True, 'message': 'Config directory created'}

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f"{config_dir}.backup_update_{timestamp}"
    try:
        shutil.move(config_dir, backup_dir)
        os.makedirs(config_dir, exist_ok=True)
        return {'success': True, 'message': f"Config reset, backup: {backup_dir}", 'backup_dir': backup_dir}
    except Exception as e:
        return {'success': False, 'message': str(e)}
def _normalize_required_packages(required_packages) -> list:
    if required_packages is None:
        return []
    if isinstance(required_packages, str):
        candidates = re.split(r'[,\s]+', required_packages)
    elif isinstance(required_packages, list):
        candidates = []
        for item in required_packages:
            if isinstance(item, str):
                candidates.extend(re.split(r'[,\s]+', item))
            else:
                candidates.append(item)
    else:
        return []

    normalized = []
    for pkg in candidates:
        if pkg is None:
            continue
        pkg_str = str(pkg)
        pkg_str = ''.join(ch for ch in pkg_str if ch.isprintable())
        pkg_str = pkg_str.strip()
        if pkg_str:
            normalized.append(pkg_str)
    return normalized

def _filter_required_packages(packages: list) -> tuple[list, list]:
    if not packages:
        return [], []
    valid = []
    invalid = []
    pattern = re.compile(r'^[A-Za-z0-9][A-Za-z0-9+.-]+$')
    for pkg in packages:
        pkg_str = str(pkg).strip()
        if pattern.match(pkg_str):
            valid.append(pkg_str)
        else:
            invalid.append(pkg_str)
    return valid, invalid

def _filter_available_packages(packages: list) -> tuple[list, list]:
    available = []
    unavailable = []
    for pkg in packages:
        if not pkg:
            continue
        result = run_command(f"apt-cache show {pkg} >/dev/null 2>&1", timeout=8)
        if result['success']:
            available.append(pkg)
        else:
            unavailable.append(pkg)
    return available, unavailable

def _load_dependencies_spec_from_text(text: str) -> tuple[dict, list]:
    warnings = []
    try:
        data = json.loads(text)
    except Exception as e:
        return {}, [f"Invalid dependencies file: {e}"]

    if not isinstance(data, dict):
        return {}, ["Invalid dependencies file format"]

    if data.get('schema_version') != 1:
        warnings.append("Unsupported dependencies schema version")

    return data, warnings

def _load_dependencies_spec(path: str) -> tuple[dict, list]:
    if not path or not os.path.exists(path):
        return {}, ["Dependencies file not found"]
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return _load_dependencies_spec_from_text(handle.read())
    except Exception as e:
        return {}, [f"Failed to read dependencies file: {e}"]

def _parse_requirements_text(text: str) -> list:
    packages = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith('#'):
            continue
        if raw.startswith('-r') or raw.startswith('--'):
            continue
        if raw.startswith('git+'):
            continue
        entry = raw.split(';', 1)[0].strip()
        name = re.split(r'[<=>]', entry, 1)[0].strip()
        if name:
            packages.append(name)
    return packages

def _get_pip_command() -> str:
    venv_pip = os.path.join(UPDATE_WEB_INSTALL_DIR, 'venv', 'bin', 'pip')
    if os.path.exists(venv_pip):
        return f"sudo {venv_pip}"
    return "sudo pip3"

def _get_missing_python_packages(packages: list) -> list:
    if not packages:
        return []
    missing = []
    pip_cmd = _get_pip_command()
    for pkg in packages:
        result = run_command(f"{pip_cmd} show {pkg} >/dev/null 2>&1", timeout=10)
        if not result['success']:
            missing.append(pkg)
    return missing

def _install_python_requirements(requirements_path: str) -> dict:
    if not requirements_path or not os.path.exists(requirements_path):
        return {'success': False, 'message': 'requirements.txt not found'}
    pip_cmd = _get_pip_command()
    result = run_command(f"{pip_cmd} install -q -r {requirements_path}", timeout=600)
    return {
        'success': result['success'],
        'message': result['stdout'] if result['success'] else result['stderr']
    }

def inspect_update_package(archive_path, allow_same_version=False):
    if not os.path.exists(archive_path):
        return {'success': False, 'message': 'Update file not found'}

    if not tarfile.is_tarfile(archive_path):
        return {'success': False, 'message': 'Update file is not a valid tar archive'}

    errors = []
    warnings = []
    manifest = {}
    dependencies = {}
    requirements_text = None
    requirements_file = None

    try:
        with tarfile.open(archive_path, 'r:*') as tar:
            members = tar.getmembers()
            unsafe = [m.name for m in members if not _is_safe_update_member(m)]
            if unsafe:
                errors.append('Unsafe paths detected in archive')

            for member in members:
                if member.name in ['update_manifest.json', 'payload', 'payload/']:
                    continue
                if not member.name.startswith('payload/'):
                    errors.append('Unexpected files outside payload')
                    break

            try:
                manifest_member = tar.getmember('update_manifest.json')
            except KeyError:
                errors.append('update_manifest.json not found')
                manifest_member = None

            if manifest_member:
                manifest_data = tar.extractfile(manifest_member).read().decode('utf-8')
                manifest = json.loads(manifest_data)

            deps_member_path = f"payload/{DEPENDENCIES_FILE_PATH.lstrip('/')}"
            try:
                deps_member = tar.getmember(deps_member_path)
                deps_data = tar.extractfile(deps_member).read().decode('utf-8')
                dependencies, dep_warnings = _load_dependencies_spec_from_text(deps_data)
                warnings.extend(dep_warnings)
            except KeyError:
                warnings.append('Dependencies file missing in update archive')

            required_packages = []
            requires_reboot = False
            if manifest:
                if manifest.get('schema_version') != 1:
                    errors.append('Unsupported update schema version')

                version = manifest.get('version')
                if not version:
                    errors.append('Update version missing in manifest')
                else:
                    version_cmp = compare_versions(version, APP_VERSION)
                    manifest_allow = bool(manifest.get('allow_reapply', False))
                    if version_cmp < 0:
                        errors.append('Update version must be greater than current')
                    elif version_cmp == 0 and not (allow_same_version or manifest_allow):
                        errors.append('Update version must be greater than current')

                files = manifest.get('files', [])
                if not isinstance(files, list) or not files:
                    errors.append('Manifest file list is empty')
                else:
                    for entry in files:
                        path = _normalize_update_path(entry.get('path', ''))
                        if not path:
                            errors.append('Manifest contains empty path')
                            continue
                        if '..' in path.split('/'):
                            errors.append(f"Path traversal not allowed: {path}")
                            continue
                        if not any(path.startswith(prefix + '/') or path == prefix for prefix in UPDATE_ALLOWED_PREFIXES):
                            errors.append(f"Path not allowed: {path}")
                            continue
                        if path.startswith('etc/'):
                            errors.append('Config directory is not allowed in updates')
                            continue

                        payload_path = f"payload/{path}"
                        try:
                            member = tar.getmember(payload_path)
                        except KeyError:
                            errors.append(f"Missing file in archive: {payload_path}")
                            continue

                        if not member.isfile():
                            errors.append(f"Invalid member type: {payload_path}")
                            continue

                        data = tar.extractfile(member).read()
                        expected_hash = entry.get('sha256')
                        expected_size = entry.get('size')
                        if expected_hash and _sha256_from_bytes(data) != expected_hash:
                            errors.append(f"Checksum mismatch: {path}")
                        if expected_size is not None and len(data) != expected_size:
                            errors.append(f"Size mismatch: {path}")

                deps_packages = _normalize_required_packages(dependencies.get('apt_packages', []))
                manifest_packages = _normalize_required_packages(manifest.get('required_packages', []))
                combined_packages = deps_packages or manifest_packages
                if deps_packages and manifest_packages:
                    combined_packages = list(dict.fromkeys(deps_packages + manifest_packages))
                required_packages, invalid_packages = _filter_required_packages(combined_packages)
                if invalid_packages:
                    warnings.append(f"Invalid package names ignored: {', '.join(invalid_packages)}")
                requires_reboot = bool(manifest.get('requires_reboot', False))

            if errors:
                return {'success': False, 'message': '; '.join(errors), 'errors': errors}

            version_cmp = compare_versions(manifest.get('version', ''), APP_VERSION) if manifest.get('version') else 0
            available_packages, unavailable_packages = _filter_available_packages(required_packages)
            if unavailable_packages:
                warnings.append(f"Unavailable packages ignored: {', '.join(unavailable_packages)}")
            missing_packages = _get_missing_packages(available_packages) if available_packages else []

            requirements_file = dependencies.get('python_requirements_file', 'requirements.txt') if dependencies else 'requirements.txt'
            if requirements_file:
                req_member_path = f"payload/{UPDATE_WEB_INSTALL_DIR.lstrip('/')}/{requirements_file}"
                try:
                    req_member = tar.getmember(req_member_path)
                    requirements_text = tar.extractfile(req_member).read().decode('utf-8')
                except KeyError:
                    warnings.append('requirements.txt missing in update archive')

            pip_packages = _normalize_required_packages(dependencies.get('pip_packages', [])) if dependencies else []
            requirements_packages = _parse_requirements_text(requirements_text) if requirements_text else []
            combined_pip = list(dict.fromkeys(requirements_packages + pip_packages)) if (requirements_packages or pip_packages) else []
            missing_pip = _get_missing_python_packages(combined_pip) if combined_pip else []
            if missing_packages or missing_pip:
                requires_reboot = True

            return {
                'success': True,
                'version': manifest.get('version'),
                'created_at': manifest.get('created_at'),
                'files_count': len(manifest.get('files', [])),
                'restart_services': manifest.get('restart_services', []),
                'required_packages': available_packages,
                'missing_packages': missing_packages,
                'missing_apt_packages': missing_packages,
                'missing_pip_packages': missing_pip,
                'python_requirements_file': requirements_file,
                'requires_reboot': requires_reboot,
                'warnings': warnings,
                'same_version': version_cmp == 0,
                'reapply_allowed': allow_same_version or bool(manifest.get('allow_reapply', False))
            }
    except Exception as e:
        return {'success': False, 'message': str(e)}

def _apply_update_package(archive_path, allow_same_version=False, install_deps=False, reset_settings=False):
    inspect_result = inspect_update_package(archive_path, allow_same_version=allow_same_version)
    if not inspect_result.get('success'):
        return inspect_result

    missing_apt = inspect_result.get('missing_apt_packages') or inspect_result.get('missing_packages', [])
    missing_pip = inspect_result.get('missing_pip_packages', [])
    deps_installed = False

    if missing_apt:
        deps_result = _install_packages(missing_apt)
        if not deps_result.get('success'):
            return {'success': False, 'message': deps_result.get('message', 'Dependency install failed')}
        deps_installed = True

    services = inspect_result.get('restart_services') or ['rpi-cam-webmanager']

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with tarfile.open(archive_path, 'r:*') as tar:
                safe_members = [m for m in tar.getmembers() if _is_safe_update_member(m)]
                tar.extractall(path=temp_dir, members=safe_members)

            payload_root = os.path.join(temp_dir, 'payload')
            if not os.path.isdir(payload_root):
                return {'success': False, 'message': 'Payload directory missing'}

            updated = 0
            for root, _, filenames in os.walk(payload_root):
                rel_root = os.path.relpath(root, payload_root)
                dest_root = '/' if rel_root == '.' else os.path.join('/', rel_root)
                os.makedirs(dest_root, exist_ok=True)

                for filename in filenames:
                    src_path = os.path.join(root, filename)
                    dest_path = os.path.join(dest_root, filename)
                    shutil.copy2(src_path, dest_path)
                    src_mode = os.stat(src_path).st_mode
                    os.chmod(dest_path, src_mode & 0o777)
                    if dest_path.startswith('/usr/local/bin/') and filename.endswith(('.sh', '.py')):
                        os.chmod(dest_path, 0o755)
                    updated += 1

            if missing_pip:
                requirements_file = inspect_result.get('python_requirements_file') or 'requirements.txt'
                requirements_path = os.path.join(UPDATE_WEB_INSTALL_DIR, requirements_file)
                pip_result = _install_python_requirements(requirements_path)
                if not pip_result.get('success'):
                    return {'success': False, 'message': pip_result.get('message', 'Python dependencies install failed')}
                deps_installed = True

        reset_result = None
        if reset_settings:
            reset_result = _reset_config_directory()
            if not reset_result.get('success'):
                return {'success': False, 'message': reset_result.get('message')}

        return {
            'success': True,
            'message': 'Update applied',
            'updated_files': updated,
            'restart_services': services,
            'version': inspect_result.get('version'),
            'requires_reboot': bool(inspect_result.get('requires_reboot', False)) or deps_installed,
            'dependencies_installed': deps_installed,
            'reset_settings': bool(reset_settings),
            'reset_result': reset_result
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}

def start_update_from_file(archive_path, allow_same_version=False, install_deps=False, reset_settings=False):
    status = _read_update_status()
    if status.get('state') in ['validating', 'applying', 'restarting']:
        return {'success': False, 'message': 'Update already in progress'}

    _write_update_status({
        'state': 'starting',
        'message': 'Starting update',
        'progress': 5,
        'log': ['Starting update']
    })

    def worker():
        try:
            _set_update_status('validating', 'Validating update', 15, 'Validating archive')
            inspect_result = inspect_update_package(archive_path, allow_same_version=allow_same_version)
            if not inspect_result.get('success'):
                _set_update_status('error', inspect_result.get('message'), 0, 'Validation failed')
                return
            missing_apt = inspect_result.get('missing_apt_packages') or inspect_result.get('missing_packages', [])
            missing_pip = inspect_result.get('missing_pip_packages', [])
            if missing_apt or missing_pip:
                _set_update_status('dependencies', 'Installing dependencies', 30, 'Installing dependencies', details=inspect_result)

            _set_update_status('applying', 'Applying update', 50, 'Copying files', details=inspect_result)
            apply_result = _apply_update_package(
                archive_path,
                allow_same_version=allow_same_version,
                install_deps=True,
                reset_settings=reset_settings
            )
            if not apply_result.get('success'):
                _set_update_status('error', apply_result.get('message'), 0, 'Apply failed')
                return

            requires_reboot = bool(apply_result.get('requires_reboot')) or bool(reset_settings)
            _set_update_status(
                'success' if not requires_reboot else 'rebooting',
                'Update applied, rebooting' if requires_reboot else 'Update applied, restarting services',
                100,
                'Update completed',
                details={**inspect_result, 'requires_reboot': requires_reboot}
            )

            if requires_reboot:
                subprocess.Popen(
                    ['bash', '-c', "sleep 5 && sudo shutdown -r now 'Update from file reboot'"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                for service in apply_result.get('restart_services', []):
                    subprocess.Popen(
                        ['bash', '-c', f"sleep 2 && sudo systemctl restart {service}"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
        except Exception as e:
            _set_update_status('error', str(e), 0, 'Unexpected error')
        finally:
            try:
                os.remove(archive_path)
            except OSError:
                pass

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return {'success': True, 'message': 'Update started'}

# ============================================================================
# BACKUP MANAGEMENT
# ============================================================================

def _normalize_archive_path(path):
    return path.lstrip(os.sep).replace(os.sep, '/')

def _is_safe_member(member):
    name = member.name
    if member.islnk() or member.issym():
        return False
    if name.startswith('/') or name.startswith('\\'):
        return False
    if '..' in name.split('/'):
        return False
    return True

def _collect_backup_paths(include_logs):
    config_dir = os.path.dirname(CONFIG_FILE)
    paths = []

    if os.path.isdir(config_dir):
        paths.append((config_dir, _normalize_archive_path(config_dir)))

    if include_logs:
        log_dirs = sorted({os.path.dirname(path) for path in LOG_FILES.values()})
        for log_dir in log_dirs:
            if os.path.isdir(log_dir):
                paths.append((log_dir, _normalize_archive_path(log_dir)))

    return paths

def _build_manifest_file_list(paths):
    files = []
    for src, arc_base in paths:
        if os.path.isdir(src):
            for root, _, filenames in os.walk(src):
                for filename in filenames:
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, src)
                    files.append(_normalize_archive_path(os.path.join(arc_base, rel_path)))
        elif os.path.isfile(src):
            files.append(_normalize_archive_path(arc_base))
    return sorted(set(files))

def create_config_backup(include_logs=False):
    """
    Create a backup archive of configuration files (and logs optionally).
    """
    config_dir = os.path.dirname(CONFIG_FILE)
    if not os.path.isdir(config_dir):
        return {
            'success': False,
            'message': f"Config directory not found: {config_dir}"
        }

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_name = f"rpi-cam-backup_{timestamp}.tar.gz"
    archive_path = os.path.join(tempfile.gettempdir(), archive_name)

    paths = _collect_backup_paths(include_logs)
    manifest = {
        'schema_version': 1,
        'version': APP_VERSION,
        'created_at': datetime.now().isoformat(),
        'include_logs': include_logs,
        'files': _build_manifest_file_list(paths)
    }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = os.path.join(temp_dir, 'backup_manifest.json')
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)

            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(manifest_path, arcname='backup_manifest.json')
                for src, arc_base in paths:
                    if os.path.exists(src):
                        tar.add(src, arcname=arc_base)

        return {
            'success': True,
            'archive_path': archive_path,
            'archive_name': archive_name,
            'version': APP_VERSION
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

def inspect_config_backup(archive_path):
    """
    Inspect a backup archive and validate structure/manifest.
    """
    if not os.path.exists(archive_path):
        return {
            'success': False,
            'message': 'Backup file not found'
        }

    if not tarfile.is_tarfile(archive_path):
        return {
            'success': False,
            'message': 'Backup file is not a valid tar archive'
        }

    config_dir = os.path.dirname(CONFIG_FILE)
    required_file = _normalize_archive_path(os.path.join(config_dir, 'config.env'))
    errors = []

    try:
        with tarfile.open(archive_path, 'r:*') as tar:
            members = tar.getmembers()
            unsafe_members = [m.name for m in members if not _is_safe_member(m)]
            if unsafe_members:
                errors.append('Unsafe paths detected in archive')

            try:
                manifest_member = tar.getmember('backup_manifest.json')
            except KeyError:
                errors.append('backup_manifest.json not found')
                manifest_member = None

            manifest = {}
            if manifest_member:
                manifest_data = tar.extractfile(manifest_member).read().decode('utf-8')
                manifest = json.loads(manifest_data)

            if manifest:
                if manifest.get('schema_version') != 1:
                    errors.append('Unsupported backup schema version')
                if not manifest.get('version'):
                    errors.append('Backup version missing in manifest')

                files = manifest.get('files', [])
                if not isinstance(files, list):
                    errors.append('Invalid file list in manifest')
                    files = []

                if required_file not in files:
                    errors.append(f"Required file missing: {required_file}")

                member_files = {m.name for m in members if m.isfile()}
                missing_in_archive = [f for f in files if f not in member_files]
                if missing_in_archive:
                    errors.append('Manifest references missing files')

            if errors:
                return {
                    'success': False,
                    'message': '; '.join(errors),
                    'errors': errors
                }

            return {
                'success': True,
                'version': manifest.get('version'),
                'created_at': manifest.get('created_at'),
                'include_logs': manifest.get('include_logs', False),
                'files_count': len(manifest.get('files', []))
            }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

def restore_config_backup(archive_path):
    """
    Restore configuration files from a backup archive.
    """
    inspect_result = inspect_config_backup(archive_path)
    if not inspect_result.get('success'):
        return inspect_result

    config_dir = os.path.dirname(CONFIG_FILE)
    config_dir_archive = _normalize_archive_path(config_dir)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with tarfile.open(archive_path, 'r:*') as tar:
                safe_members = [m for m in tar.getmembers() if _is_safe_member(m)]
                tar.extractall(path=temp_dir, members=safe_members)

            source_root = os.path.join(temp_dir, config_dir_archive)
            if not os.path.isdir(source_root):
                return {
                    'success': False,
                    'message': f"Config directory not found in backup: {config_dir_archive}"
                }

            os.makedirs(config_dir, exist_ok=True)
            restored_files = 0

            for root, _, filenames in os.walk(source_root):
                rel_path = os.path.relpath(root, source_root)
                dest_root = config_dir if rel_path == '.' else os.path.join(config_dir, rel_path)
                os.makedirs(dest_root, exist_ok=True)

                for filename in filenames:
                    src_path = os.path.join(root, filename)
                    dest_path = os.path.join(dest_root, filename)
                    shutil.copy2(src_path, dest_path)
                    restored_files += 1

        return {
            'success': True,
            'message': 'Backup restored successfully',
            'version': inspect_result.get('version'),
            'restored_files': restored_files
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

# ============================================================================
# SNMP CONFIGURATION
# ============================================================================

def get_snmp_config() -> dict:
    config = load_config()
    port_raw = config.get('SNMP_SERVER_PORT', '162') or '162'
    try:
        port_int = int(port_raw)
    except Exception:
        port_int = 162

    return {
        'success': True,
        'enabled': config.get('SNMP_ENABLED', 'no') == 'yes',
        'host': config.get('SNMP_SERVER_HOST', ''),
        'port': port_int
    }

def set_snmp_config(enabled: bool, host: str, port: int) -> dict:
    host = (host or '').strip()
    try:
        port_int = int(port)
    except Exception:
        return {'success': False, 'message': 'Port SNMP invalide'}

    if port_int < 1 or port_int > 65535:
        return {'success': False, 'message': 'Port SNMP hors limites (1-65535)'}

    if enabled and not host:
        return {'success': False, 'message': 'Host SNMP requis quand SNMP est activé'}

    update = {
        'SNMP_ENABLED': 'yes' if enabled else 'no',
        'SNMP_SERVER_HOST': host,
        'SNMP_SERVER_PORT': str(port_int)
    }
    result = save_config(update)
    if not result.get('success'):
        return result

    return {'success': True, 'message': 'Configuration SNMP sauvegardée', **update}

def test_snmp_config(enabled: bool, host: str, port: int) -> dict:
    if not enabled:
        return {'success': False, 'message': 'SNMP est désactivé'}

    host = (host or '').strip()
    if not host:
        return {'success': False, 'message': 'Host SNMP manquant'}

    try:
        port_int = int(port)
    except Exception:
        return {'success': False, 'message': 'Port SNMP invalide'}

    if port_int < 1 or port_int > 65535:
        return {'success': False, 'message': 'Port SNMP hors limites (1-65535)'}

    try:
        import socket
        addrs = socket.getaddrinfo(host, port_int, proto=socket.IPPROTO_UDP)
    except Exception as e:
        return {'success': False, 'message': f"DNS/resolve impossible: {e}"}

    # Best-effort UDP "connect" + send to validate reachability (no ACK expected)
    resolved = []
    for addr in addrs:
        family, _, _, _, sockaddr = addr
        resolved.append(sockaddr[0])
        try:
            with socket.socket(family, socket.SOCK_DGRAM) as sock:
                sock.settimeout(1.5)
                sock.connect(sockaddr)
                sock.send(b'\x00')
        except Exception:
            continue

    resolved = sorted(set(resolved))
    if not resolved:
        return {'success': False, 'message': 'Résolution OK mais envoi UDP impossible'}

    return {'success': True, 'message': f"SNMP OK (résolu: {', '.join(resolved)})"}

# ============================================================================
# RTC DS3231 CONFIGURATION
# ============================================================================

def _load_rtc_state() -> dict:
    default_state = {
        'mode': 'auto',
        'updated': None
    }

    if not os.path.exists(RTC_CONFIG_FILE):
        return default_state

    try:
        with open(RTC_CONFIG_FILE, 'r') as f:
            data = json.load(f) or {}
        mode = str(data.get('mode', 'auto')).lower()
        if mode not in ['auto', 'enabled', 'disabled']:
            mode = 'auto'
        return {
            'mode': mode,
            'updated': data.get('updated')
        }
    except Exception:
        return default_state

def _save_rtc_state(state: dict) -> None:
    state = state or {}
    config_dir = os.path.dirname(RTC_CONFIG_FILE)
    os.makedirs(config_dir, exist_ok=True)
    with open(RTC_CONFIG_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def _read_boot_config_lines() -> tuple:
    if not BOOT_CONFIG_FILE or not os.path.exists(BOOT_CONFIG_FILE):
        return None, []
    with open(BOOT_CONFIG_FILE, 'r') as f:
        return BOOT_CONFIG_FILE, f.readlines()

def _write_boot_config_lines(path: str, lines: list) -> None:
    with open(path, 'w') as f:
        f.writelines(lines)

def _boot_config_has_line(lines: list, line_prefix: str) -> bool:
    for line in lines:
        if line.strip().startswith(line_prefix):
            return True
    return False

def _ensure_boot_config_line(lines: list, line_value: str) -> tuple:
    if _boot_config_has_line(lines, line_value):
        return lines, False
    new_lines = list(lines)
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines[-1] = new_lines[-1] + '\n'
    new_lines.append(f"{line_value}\n")
    return new_lines, True

def _remove_rtc_overlay_lines(lines: list) -> tuple:
    removed = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('dtoverlay=i2c-rtc') and 'ds3231' in stripped:
            removed = True
            continue
        new_lines.append(line)
    return new_lines, removed

def _detect_rtc_devices() -> dict:
    devices = []
    detected = False
    detected_via = None

    try:
        rtc_paths = [p for p in os.listdir('/sys/class/rtc') if p.startswith('rtc')]
    except Exception:
        rtc_paths = []

    for rtc in rtc_paths:
        name_path = os.path.join('/sys/class/rtc', rtc, 'name')
        try:
            with open(name_path, 'r') as f:
                name = f.read().strip()
        except Exception:
            continue

        devices.append({'device': rtc, 'name': name})
        lowered = name.lower()
        if any(keyword in lowered for keyword in RTC_DETECT_KEYWORDS):
            detected = True
            detected_via = 'rtc'

    if not detected and os.path.exists(RTC_I2C_DEVICE):
        i2cdetect_path = shutil.which('i2cdetect')
        if not i2cdetect_path and os.path.exists('/usr/sbin/i2cdetect'):
            i2cdetect_path = '/usr/sbin/i2cdetect'
        if i2cdetect_path:
            scan = run_command(f'{i2cdetect_path} -y 1', timeout=8)
            if scan['success']:
                output = scan['stdout']
                for line in output.splitlines():
                    line = line.strip()
                    if line.startswith('60:'):
                        cells = line.split()[1:]
                        if len(cells) >= 9:
                            value = cells[8].lower()
                            if value in ['68', 'uu']:
                                detected = True
                                detected_via = 'i2c'
                        break

    return {
        'detected': detected,
        'detected_via': detected_via,
        'devices': devices
    }

def _ensure_i2c_module_autoload() -> dict:
    try:
        os.makedirs(os.path.dirname(RTC_I2C_MODULE_FILE), exist_ok=True)
        content = "i2c-dev\n"
        if os.path.exists(RTC_I2C_MODULE_FILE):
            with open(RTC_I2C_MODULE_FILE, 'r') as f:
                if 'i2c-dev' in f.read():
                    return {'success': True, 'changed': False}
        with open(RTC_I2C_MODULE_FILE, 'w') as f:
            f.write(content)
        return {'success': True, 'changed': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _set_fake_hwclock(enabled: bool) -> dict:
    if not shutil.which('systemctl'):
        return {'success': False, 'message': 'systemctl introuvable'}

    if enabled:
        cmd = 'sudo systemctl enable --now fake-hwclock'
    else:
        cmd = 'sudo systemctl disable --now fake-hwclock'

    result = run_command(cmd, timeout=10)
    return {
        'success': result['success'],
        'stdout': result.get('stdout'),
        'stderr': result.get('stderr'),
        'returncode': result.get('returncode')
    }

def get_rtc_status() -> dict:
    state = _load_rtc_state()
    detection = _detect_rtc_devices()
    config_path, lines = _read_boot_config_lines()

    overlay_configured = False
    i2c_enabled = False
    if lines:
        overlay_configured = any(
            line.strip().startswith('dtoverlay=i2c-rtc') and 'ds3231' in line
            for line in lines
        )
        i2c_enabled = _boot_config_has_line(lines, 'dtparam=i2c_arm=on')

    mode = state.get('mode', 'auto')
    if mode not in ['auto', 'enabled', 'disabled']:
        mode = 'auto'

    if mode == 'disabled':
        effective_enabled = False
    else:
        effective_enabled = overlay_configured

    auto_pending = mode == 'auto' and (
        not i2c_enabled or (detection['detected'] and not overlay_configured)
    )

    return {
        'success': True,
        'mode': mode,
        'detected': detection['detected'],
        'detected_via': detection['detected_via'],
        'devices': detection['devices'],
        'effective_enabled': effective_enabled,
        'overlay_configured': overlay_configured,
        'i2c_enabled': i2c_enabled,
        'i2c_device_present': os.path.exists(RTC_I2C_DEVICE),
        'config_file': config_path,
        'config_state_file': RTC_CONFIG_FILE,
        'auto_pending': auto_pending
    }

def set_rtc_config(mode: str) -> dict:
    mode = str(mode or '').lower().strip()
    if mode not in ['auto', 'enabled', 'disabled']:
        return {'success': False, 'message': 'Mode RTC invalide'}

    config_path, lines = _read_boot_config_lines()
    if not config_path:
        return {'success': False, 'message': 'Fichier boot config introuvable'}

    detection = _detect_rtc_devices()
    overlay_configured = False
    i2c_enabled = False
    if lines:
        overlay_configured = any(
            line.strip().startswith('dtoverlay=i2c-rtc') and 'ds3231' in line
            for line in lines
        )
        i2c_enabled = _boot_config_has_line(lines, 'dtparam=i2c_arm=on')

    if mode == 'disabled':
        desired_overlay = False
    elif mode == 'enabled':
        desired_overlay = True
    else:
        desired_overlay = detection['detected'] or overlay_configured

    new_lines = list(lines)
    changed = False

    if desired_overlay:
        new_lines, i2c_changed = _ensure_boot_config_line(new_lines, RTC_I2C_PARAM)
        new_lines, overlay_changed = _ensure_boot_config_line(new_lines, RTC_OVERLAY_LINE)
        changed = changed or i2c_changed or overlay_changed
    elif mode == 'auto':
        new_lines, i2c_changed = _ensure_boot_config_line(new_lines, RTC_I2C_PARAM)
        changed = changed or i2c_changed
    else:
        new_lines, overlay_removed = _remove_rtc_overlay_lines(new_lines)
        changed = changed or overlay_removed

    if changed:
        _write_boot_config_lines(config_path, new_lines)

    state = {
        'mode': mode,
        'updated': datetime.now().isoformat()
    }
    _save_rtc_state(state)

    i2c_module_result = None
    if mode in ['auto', 'enabled']:
        i2c_module_result = _ensure_i2c_module_autoload()
        run_command('sudo modprobe i2c-dev', timeout=5)

    fake_hwclock_result = None
    if desired_overlay:
        fake_hwclock_result = _set_fake_hwclock(False)
    elif mode == 'disabled':
        fake_hwclock_result = _set_fake_hwclock(True)

    return {
        'success': True,
        'message': 'Configuration RTC mise à jour',
        'mode': mode,
        'detected': detection['detected'],
        'effective_enabled': desired_overlay,
        'reboot_required': changed,
        'fake_hwclock': fake_hwclock_result,
        'i2c_module': i2c_module_result
    }

def get_rtc_debug_info() -> dict:
    status = get_rtc_status()

    timedatectl_result = run_command('timedatectl status', timeout=8)
    hwclock_result = run_command('hwclock -r', timeout=8)

    i2c_scan = None
    i2cdetect_path = shutil.which('i2cdetect')
    if not i2cdetect_path and os.path.exists('/usr/sbin/i2cdetect'):
        i2cdetect_path = '/usr/sbin/i2cdetect'
    if os.path.exists(RTC_I2C_DEVICE) and i2cdetect_path:
        i2c_scan = run_command(f'{i2cdetect_path} -y 1', timeout=8)

    boot_snippet = []
    config_path, lines = _read_boot_config_lines()
    if lines:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('dtparam=i2c_arm') or stripped.startswith('dtoverlay=i2c-rtc'):
                boot_snippet.append(stripped)

    return {
        'success': True,
        'status': status,
        'timedatectl': timedatectl_result,
        'hwclock': hwclock_result,
        'i2c_scan': i2c_scan,
        'boot_config_snippet': boot_snippet,
        'boot_config_file': config_path
    }

# ============================================================================
# UPDATE MANAGEMENT
# ============================================================================

def check_for_updates():
    """
    Check for updates from GitHub repository.
    
    Returns:
        dict: Update availability information
    """
    result = {
        'current_version': APP_VERSION,
        'latest_version': None,
        'update_available': False,
        'release_notes': None,
        'download_url': None
    }
    
    try:
        branch = _get_repo_default_branch()
        latest_version = _get_repo_version(branch)
        result['latest_version'] = latest_version
        result['download_url'] = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{branch}.tar.gz"

        if latest_version:
            result['update_available'] = compare_versions(
                latest_version,
                result['current_version']
            ) > 0
    
    except Exception as e:
        result['error'] = str(e)
    
    return result

def perform_update(backup=True, force=False, reset_settings=False):
    """
    Perform an update from the GitHub repository.
    
    Args:
        backup: Create backup before updating
        force: Allow reapply if same version
        reset_settings: Reset configuration after update
    
    Returns:
        dict: Update result
    """
    result = {
        'success': False,
        'message': '',
        'requires_restart': False,
        'updated_files': 0
    }
    
    try:
        branch = _get_repo_default_branch()
        repo_version = _get_repo_version(branch)
        if repo_version and compare_versions(repo_version, APP_VERSION) <= 0 and not force:
            result['message'] = 'Version identique, activez "forcer la reinstallation" pour continuer'
            result['latest_version'] = repo_version
            return result

        # Create backup if requested
        if backup:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            backup_path = f"/tmp/rpi-cam-backup-{timestamp}.tar.gz"
            backup_sources = [UPDATE_WEB_INSTALL_DIR]
            for dest_path in UPDATE_REPO_BINARIES.values():
                if os.path.exists(dest_path):
                    backup_sources.append(dest_path)
            try:
                with tarfile.open(backup_path, 'w:gz') as tar:
                    for source in backup_sources:
                        if os.path.exists(source):
                            tar.add(source, arcname=source.lstrip('/'))
            except Exception as e:
                result['message'] = f"Backup failed: {e}"
                return result

        deps_installed = False
        missing_apt = []
        missing_pip = []
        dep_warnings = []

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = os.path.join(temp_dir, 'repo.tar.gz')
            extract_dir = os.path.join(temp_dir, 'extract')
            os.makedirs(extract_dir, exist_ok=True)

            _download_repo_archive(archive_path, branch)
            with tarfile.open(archive_path, 'r:*') as tar:
                tar.extractall(path=extract_dir)

            repo_root = _find_repo_root(extract_dir)
            if not repo_root:
                result['message'] = 'Update failed: repository archive is empty'
                return result

            deps_path = os.path.join(repo_root, 'web-manager', DEPENDENCIES_FILE_NAME)
            dependencies, dep_warnings = _load_dependencies_spec(deps_path)
            deps_packages = _normalize_required_packages(dependencies.get('apt_packages', []))
            if deps_packages:
                deps_packages, invalid_packages = _filter_required_packages(deps_packages)
                if invalid_packages:
                    dep_warnings.append(f"Invalid package names ignored: {', '.join(invalid_packages)}")
                available_packages, unavailable_packages = _filter_available_packages(deps_packages)
                if unavailable_packages:
                    dep_warnings.append(f"Unavailable packages ignored: {', '.join(unavailable_packages)}")
                missing_apt = _get_missing_packages(available_packages) if available_packages else []

            requirements_file = dependencies.get('python_requirements_file', 'requirements.txt') if dependencies else 'requirements.txt'
            requirements_path = os.path.join(repo_root, 'web-manager', requirements_file)
            requirements_text = None
            if os.path.exists(requirements_path):
                with open(requirements_path, 'r', encoding='utf-8') as handle:
                    requirements_text = handle.read()

            pip_packages = _normalize_required_packages(dependencies.get('pip_packages', [])) if dependencies else []
            requirements_packages = _parse_requirements_text(requirements_text) if requirements_text else []
            combined_pip = list(dict.fromkeys(requirements_packages + pip_packages)) if (requirements_packages or pip_packages) else []
            missing_pip = _get_missing_python_packages(combined_pip) if combined_pip else []

            if missing_apt:
                deps_result = _install_packages(missing_apt)
                if not deps_result.get('success'):
                    result['message'] = deps_result.get('message', 'Dependency install failed')
                    return result
                deps_installed = True
            if missing_pip and os.path.exists(requirements_path):
                pip_result = _install_python_requirements(requirements_path)
                if not pip_result.get('success'):
                    result['message'] = pip_result.get('message', 'Python dependencies install failed')
                    return result
                deps_installed = True

            result['updated_files'] = _sync_repo_update(repo_root)
            if result['updated_files'] == 0:
                result['message'] = 'Update failed: no files were applied'
                return result

        reset_result = None
        if reset_settings:
            reset_result = _reset_config_directory()
            if not reset_result.get('success'):
                result['message'] = reset_result.get('message', 'Reset settings failed')
                return result

        requires_reboot = deps_installed or bool(reset_settings)
        if requires_reboot:
            subprocess.Popen(
                ['bash', '-c', "sleep 5 && sudo shutdown -r now 'Update from repo reboot'"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            run_command("sudo systemctl restart rpi-av-rtsp-recorder", timeout=20)
            run_command("sudo systemctl restart rtsp-recorder", timeout=20)
            run_command("sudo systemctl restart rtsp-watchdog", timeout=20)
            run_command("sudo systemctl restart rpi-cam-onvif", timeout=20)

            subprocess.Popen(
                ['bash', '-c', "sleep 2 && sudo systemctl restart rpi-cam-webmanager"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        result['success'] = True
        result['message'] = f'Update completed successfully (branch: {branch})'
        result['requires_restart'] = not requires_reboot
        result['latest_version'] = repo_version
        result['reset_settings'] = bool(reset_settings)
        result['reset_result'] = reset_result
        result['dependencies_installed'] = deps_installed
        result['missing_apt_packages'] = missing_apt
        result['missing_pip_packages'] = missing_pip
        if dep_warnings:
            result['warnings'] = dep_warnings
        if requires_reboot:
            result['message'] += ' (dependencies installed, rebooting)'
    
    except Exception as e:
        result['message'] = str(e)
    
    return result

def compare_versions(version1, version2):
    """
    Compare two version strings.
    
    Returns:
        int: -1 if v1 < v2, 0 if equal, 1 if v1 > v2
    """
    def parse_version(v):
        return [int(x) for x in re.findall(r'\d+', v)]
    
    v1_parts = parse_version(version1)
    v2_parts = parse_version(version2)
    
    # Pad shorter version with zeros
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))
    
    for a, b in zip(v1_parts, v2_parts):
        if a < b:
            return -1
        elif a > b:
            return 1
    
    return 0

# ============================================================================
# UPDATE FROM REPOSITORY
# ============================================================================

def _get_repo_default_branch():
    try:
        import urllib.request
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}"
        request = urllib.request.Request(api_url)
        request.add_header('Accept', 'application/vnd.github.v3+json')
        request.add_header('User-Agent', f'rpi-cam-webmanager/{APP_VERSION}')
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            branch = data.get('default_branch')
            if branch:
                return branch
    except Exception:
        pass
    return UPDATE_REPO_BRANCH_FALLBACK

def _download_repo_archive(dest_path, branch):
    import urllib.request
    url = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/{branch}.tar.gz"
    request = urllib.request.Request(url)
    request.add_header('User-Agent', f'rpi-cam-webmanager/{APP_VERSION}')
    with urllib.request.urlopen(request, timeout=30) as response, open(dest_path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

def _get_repo_version(branch):
    import urllib.request
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{branch}/VERSION"
    request = urllib.request.Request(url)
    request.add_header('User-Agent', f'rpi-cam-webmanager/{APP_VERSION}')
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode('utf-8').strip()

def _find_repo_root(extract_dir):
    entries = [
        name for name in os.listdir(extract_dir)
        if os.path.isdir(os.path.join(extract_dir, name))
    ]
    if not entries:
        return None
    entries.sort()
    return os.path.join(extract_dir, entries[0])

def _copy_repo_file(src_path, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy2(src_path, dest_path)
    os.chmod(dest_path, 0o755)

def _copy_repo_tree(src_dir, dest_dir):
    for root, _, filenames in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        dest_root = dest_dir if rel_root == '.' else os.path.join(dest_dir, rel_root)
        os.makedirs(dest_root, exist_ok=True)
        for filename in filenames:
            src_path = os.path.join(root, filename)
            dest_path = os.path.join(dest_root, filename)
            shutil.copy2(src_path, dest_path)

def _sync_repo_update(repo_root):
    updated_files = 0

    web_src = os.path.join(repo_root, 'web-manager')
    if os.path.isdir(web_src):
        _copy_repo_tree(web_src, UPDATE_WEB_INSTALL_DIR)
        updated_files += 1

    onvif_src = os.path.join(repo_root, 'onvif-server')
    if os.path.isdir(onvif_src):
        dest = os.path.join(UPDATE_WEB_INSTALL_DIR, 'onvif-server')
        _copy_repo_tree(onvif_src, dest)
        updated_files += 1

    version_src = os.path.join(repo_root, 'VERSION')
    if os.path.isfile(version_src):
        version_dest = os.path.join(UPDATE_WEB_INSTALL_DIR, 'VERSION')
        os.makedirs(os.path.dirname(version_dest), exist_ok=True)
        shutil.copy2(version_src, version_dest)
        updated_files += 1

    for repo_file, dest_path in UPDATE_REPO_BINARIES.items():
        src_path = os.path.join(repo_root, repo_file)
        if os.path.isfile(src_path):
            _copy_repo_file(src_path, dest_path)
            updated_files += 1

    return updated_files

# ============================================================================
# APT PACKAGE MANAGEMENT
# ============================================================================

def get_apt_updates():
    """
    Check for available APT package updates.
    
    Returns:
        dict: Available updates information
    """
    result = {
        'available': [],
        'security': [],
        'count': 0,
        'last_update': None
    }
    
    # Update package list first
    run_command("sudo apt-get update -qq", timeout=120)
    
    # Check for upgradable packages
    list_result = run_command("apt list --upgradable 2>/dev/null", timeout=30)
    
    if list_result['success']:
        for line in list_result['stdout'].split('\n'):
            if '/' in line and 'upgradable' in line.lower():
                parts = line.split('/')
                if parts:
                    package_name = parts[0].strip()
                    result['available'].append(package_name)
                    
                    # Check if security update
                    if 'security' in line.lower():
                        result['security'].append(package_name)
    
    result['count'] = len(result['available'])
    
    # Get last update time
    stat_file = '/var/lib/apt/periodic/update-success-stamp'
    if os.path.exists(stat_file):
        result['last_update'] = datetime.fromtimestamp(
            os.path.getmtime(stat_file)
        ).isoformat()
    
    return result

def perform_apt_upgrade(packages=None, security_only=False):
    """
    Perform APT package upgrade.
    
    Args:
        packages: List of specific packages to upgrade (None for all)
        security_only: Only install security updates
    
    Returns:
        dict: Upgrade result
    """
    result = {
        'success': False,
        'upgraded': [],
        'message': ''
    }
    
    try:
        if packages:
            # Upgrade specific packages
            pkg_list = ' '.join(packages)
            cmd = f"sudo apt-get install --only-upgrade -y {pkg_list}"
        elif security_only:
            cmd = "sudo apt-get upgrade -y -o Dir::Etc::SourceList=/etc/apt/sources.list.d/security.list"
        else:
            cmd = "sudo apt-get upgrade -y"
        
        upgrade_result = run_command(cmd, timeout=600)  # 10 minute timeout
        
        result['success'] = upgrade_result['success']
        result['message'] = upgrade_result['stdout'] if upgrade_result['success'] else upgrade_result['stderr']
        
        # Parse upgraded packages from output
        if upgrade_result['success']:
            for line in upgrade_result['stdout'].split('\n'):
                if 'Unpacking' in line:
                    match = re.search(r'Unpacking\s+(\S+)', line)
                    if match:
                        result['upgraded'].append(match.group(1))
    
    except Exception as e:
        result['message'] = str(e)
    
    return result

# ============================================================================
# SYSTEM ACTIONS
# ============================================================================

def restart_service(service_name):
    """
    Restart a systemd service.
    
    Args:
        service_name: Name of the service
    
    Returns:
        dict: {success: bool, message: str}
    """
    result = run_command(f"sudo systemctl restart {service_name}", timeout=30)
    
    return {
        'success': result['success'],
        'message': f'Service {service_name} restarted' if result['success'] else result['stderr']
    }

def restart_all_services():
    """
    Restart all RTSP-related services.
    
    Returns:
        dict: Results for each service
    """
    services = [
        SERVICE_NAME,
        'rtsp-watchdog',
        'rtsp-recorder',
        'rpi-cam-onvif'
    ]
    
    results = {}
    
    for svc in services:
        results[svc] = restart_service(svc)
    
    # Restart web manager last
    # Note: This might interrupt the current request
    results['rpi-cam-webmanager'] = {
        'success': True,
        'message': 'Will restart after response'
    }
    
    return results
# ============================================================================
# SYSTEM REBOOT/SHUTDOWN
# ============================================================================

def reboot_system(delay=0):
    """
    Reboot the system.
    
    Args:
        delay: Delay in seconds before rebooting (default: 0)
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        if delay > 0:
            cmd = f"sudo shutdown -r +{delay} 'Redémarrage demandé par le web manager'"
        else:
            cmd = "sudo shutdown -r now 'Redémarrage demandé par le web manager'"
        
        result = run_command(cmd, timeout=5)
        
        if result['success']:
            return {
                'success': True,
                'message': f'Redémarrage en cours{" dans " + str(delay) + "s" if delay > 0 else ""}'
            }
        else:
            return {
                'success': False,
                'message': result.get('stderr', 'Erreur lors du redémarrage')
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

def shutdown_system(delay=0):
    """
    Shutdown the system.
    
    Args:
        delay: Delay in seconds before shutting down (default: 0)
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        if delay > 0:
            cmd = f"sudo shutdown -h +{delay} 'Arrêt demandé par le web manager'"
        else:
            cmd = "sudo shutdown -h now 'Arrêt demandé par le web manager'"
        
        result = run_command(cmd, timeout=5)
        
        if result['success']:
            return {
                'success': True,
                'message': f'Arrêt en cours{" dans " + str(delay) + "s" if delay > 0 else ""}'
            }
        else:
            return {
                'success': False,
                'message': result.get('stderr', 'Erreur lors de l\'arrêt')
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Erreur: {str(e)}'
        }

# ============================================================================
# SCHEDULED REBOOT
# ============================================================================

def get_reboot_schedule() -> dict:
    if os.path.exists(SCHEDULED_REBOOT_STATE):
        try:
            with open(SCHEDULED_REBOOT_STATE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {'success': True, **data}
        except Exception:
            pass
    return {
        'success': True,
        'enabled': False,
        'hour': 3,
        'minute': 0,
        'days': ['all']
    }

def _write_reboot_schedule_state(state: dict) -> None:
    os.makedirs(os.path.dirname(SCHEDULED_REBOOT_STATE), exist_ok=True)
    with open(SCHEDULED_REBOOT_STATE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

def set_reboot_schedule(enabled: bool, hour: int, minute: int, days: list) -> dict:
    try:
        hour = int(hour)
        minute = int(minute)
    except Exception:
        return {'success': False, 'message': 'Heure/minute invalides'}

    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return {'success': False, 'message': 'Heure/minute hors limites'}

    if not isinstance(days, list) or not days:
        return {'success': False, 'message': 'Jours invalides'}

    normalized_days = []
    for day in days:
        if day == 'all':
            normalized_days = ['all']
            break
        try:
            day_int = int(day)
        except Exception:
            return {'success': False, 'message': 'Jours invalides'}
        if day_int < 0 or day_int > 6:
            return {'success': False, 'message': 'Jour hors limites (0-6)'}
        normalized_days.append(str(day_int))

    state = {
        'enabled': bool(enabled),
        'hour': hour,
        'minute': minute,
        'days': normalized_days
    }

    try:
        if not state['enabled']:
            if os.path.exists(SCHEDULED_REBOOT_CRON):
                os.remove(SCHEDULED_REBOOT_CRON)
        else:
            days_field = '*' if 'all' in normalized_days else ','.join(sorted(set(normalized_days)))
            cron_line = f"{minute} {hour} * * {days_field} root /sbin/reboot\n"
            with open(SCHEDULED_REBOOT_CRON, 'w', encoding='utf-8') as f:
                f.write('# rpi-cam scheduled reboot\n')
                f.write(cron_line)
        _write_reboot_schedule_state(state)
    except Exception as e:
        return {'success': False, 'message': str(e)}

    return {'success': True, 'message': 'Schedule saved', **state}

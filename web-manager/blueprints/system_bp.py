# -*- coding: utf-8 -*-
"""
System Blueprint - Diagnostics, logs, updates, NTP and info routes
Version: 2.30.12
"""

from flask import Blueprint, request, jsonify, Response, send_file, after_this_request
import json
import time
import subprocess
import os
import tempfile

from services.system_service import (
    get_diagnostic_info, get_recent_logs, get_service_logs,
    clean_old_logs, check_for_updates, perform_update,
    get_apt_updates, perform_apt_upgrade,
    inspect_update_package, start_update_from_file, get_update_status,
    create_config_backup, inspect_config_backup, restore_config_backup,
    restart_service, restart_all_services,
    get_snmp_config, set_snmp_config, test_snmp_config,
    get_reboot_schedule, set_reboot_schedule,
    get_rtc_status, set_rtc_config
)
from services.power_service import (
    reboot_system, shutdown_system
)
from services.platform_service import detect_platform
from services.i18n_service import t as i18n_t, resolve_request_lang

system_bp = Blueprint('system', __name__, url_prefix='/api/system')


def _t(key, **params):
    return i18n_t(key, lang=resolve_request_lang(request), params=params)

# ============================================================================
# SYSTEM INFO ROUTES
# ============================================================================

@system_bp.route('/info', methods=['GET'])
def system_info():
    """Get comprehensive system information."""
    try:
        # Platform info
        platform = detect_platform()
        
        # CPU info using /proc
        load = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        cpu_info = {
            'cores': cpu_count,
            'load_1m': round(load[0], 2),
            'load_5m': round(load[1], 2),
            'load_15m': round(load[2], 2)
        }
        
        # Memory info using /proc/meminfo
        mem_info = {}
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(':')
                        value = int(parts[1]) * 1024  # Convert KB to bytes
                        mem_info[key] = value
            
            total = mem_info.get('MemTotal', 0)
            available = mem_info.get('MemAvailable', mem_info.get('MemFree', 0))
            used = total - available
            percent = round((used / total * 100) if total > 0 else 0, 1)
        except:
            total = available = used = 0
            percent = 0
        
        memory_info = {
            'total': total,
            'available': available,
            'used': used,
            'percent': percent
        }
        
        # Disk info using df
        disk_info = {'total': 0, 'used': 0, 'available': 0, 'percent': 0}
        try:
            result = subprocess.run(['df', '-B1', '/'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        disk_info = {
                            'total': int(parts[1]),
                            'used': int(parts[2]),
                            'available': int(parts[3]),
                            'percent': int(parts[4].rstrip('%'))
                        }
        except:
            pass
        
        # Temperature
        temp = None
        try:
            result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                temp_str = result.stdout.strip()
                temp = float(temp_str.replace('temp=', '').replace("'C", ''))
        except:
            pass
        
        # Uptime
        uptime = ""
        try:
            result = subprocess.run(['uptime', '-p'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                uptime = result.stdout.strip()
        except:
            pass
        
        # Network IPs
        network = {}
        try:
            result = subprocess.run(['ip', '-4', 'addr', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                current_iface = None
                for line in result.stdout.split('\n'):
                    if ': ' in line and not line.startswith(' '):
                        parts = line.split(': ')
                        if len(parts) >= 2:
                            current_iface = parts[1].split('@')[0]
                    elif 'inet ' in line and current_iface:
                        ip = line.strip().split()[1].split('/')[0]
                        network[current_iface] = ip
        except:
            pass
        
        # Hostname
        hostname = os.uname().nodename
        
        return jsonify({
            'success': True,
            'platform': platform,
            'cpu': cpu_info,
            'memory': memory_info,
            'disk': disk_info,
            'temperature': temp,
            'uptime': uptime,
            'network': network,
            'hostname': hostname
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# DIAGNOSTIC ROUTES
# ============================================================================

@system_bp.route('/diagnostic', methods=['GET'])
def diagnostic_info():
    """Get diagnostic information."""
    diag = get_diagnostic_info()
    
    return jsonify({
        'success': True,
        **diag
    })

@system_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
    })

# ============================================================================
# SNMP ROUTES
# ============================================================================

@system_bp.route('/snmp', methods=['GET'])
def snmp_get():
    return jsonify(get_snmp_config())

@system_bp.route('/snmp', methods=['POST'])
def snmp_set():
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))
    host = str(data.get('host', '') or '')
    port = data.get('port', 162)
    result = set_snmp_config(enabled, host, port)
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code

@system_bp.route('/snmp/test', methods=['POST'])
def snmp_test():
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))
    host = str(data.get('host', '') or '')
    port = data.get('port', 162)
    result = test_snmp_config(enabled, host, port)
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code

# ============================================================================
# RTC ROUTES
# ============================================================================

@system_bp.route('/rtc', methods=['GET'])
def rtc_get():
    return jsonify(get_rtc_status())

@system_bp.route('/rtc', methods=['POST'])
def rtc_set():
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'auto')
    result = set_rtc_config(mode)
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code

# ============================================================================
# LOG ROUTES
# ============================================================================

@system_bp.route('/logs', methods=['GET'])
def get_logs():
    """Get recent log entries."""
    lines = request.args.get('lines', 100, type=int)
    source = request.args.get('source', 'all')
    
    logs_data = get_recent_logs(lines, source)
    
    return jsonify({
        'success': True,
        **logs_data
    })

@system_bp.route('/logs/<service_name>', methods=['GET'])
def get_logs_for_service(service_name):
    """Get logs for a specific service."""
    lines = request.args.get('lines', 50, type=int)
    since = request.args.get('since')
    
    logs_data = get_service_logs(service_name, lines, since)
    
    return jsonify({
        'success': True,
        **logs_data
    })

@system_bp.route('/logs/stream', methods=['GET'])
def stream_logs():
    """Stream logs in real-time via Server-Sent Events."""
    service = request.args.get('service', 'all')
    
    def generate():
        # Initial connection message
        yield f"data: {json.dumps({'type': 'connected', 'service': service})}\n\n"
        
        # Note: In production, this would use journalctl --follow
        # For now, we poll every few seconds
        last_check = time.time()
        
        while True:
            try:
                logs_data = get_recent_logs(20, service)
                
                for log in logs_data.get('logs', []):
                    yield f"data: {json.dumps(log)}\n\n"
                
                time.sleep(2)
                
            except GeneratorExit:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                break
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )

@system_bp.route('/logs/clean', methods=['POST'])
def clean_logs():
    """Clean old logs to free disk space."""
    data = request.get_json(silent=True) or {}
    max_size_mb = data.get('max_size_mb', 100)
    
    result = clean_old_logs(max_size_mb)
    
    return jsonify(result)

# ============================================================================
# BACKUP ROUTES
# ============================================================================

@system_bp.route('/backup', methods=['POST'])
def create_backup():
    """Create a configuration backup archive."""
    data = request.get_json(silent=True) or {}
    include_logs = bool(data.get('include_logs', False))

    result = create_config_backup(include_logs)
    if not result.get('success'):
        return jsonify(result), 500

    archive_path = result['archive_path']
    archive_name = result['archive_name']

    @after_this_request
    def cleanup(response):
        try:
            os.remove(archive_path)
        except OSError:
            pass
        return response

    return send_file(
        archive_path,
        as_attachment=True,
        download_name=archive_name,
        mimetype='application/gzip'
    )

@system_bp.route('/backup/check', methods=['POST'])
def check_backup():
    """Validate a backup archive."""
    file = request.files.get('backup')
    if not file or not file.filename:
        return jsonify({
            'success': False,
            'message': _t('ui.system.backup_file_required')
        }), 400

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as temp_file:
            temp_path = temp_file.name
            file.save(temp_path)

        result = inspect_config_backup(temp_path)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@system_bp.route('/backup/restore', methods=['POST'])
def restore_backup():
    """Restore configuration from a backup archive."""
    file = request.files.get('backup')
    if not file or not file.filename:
        return jsonify({
            'success': False,
            'message': _t('ui.system.backup_file_required')
        }), 400

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as temp_file:
            temp_path = temp_file.name
            file.save(temp_path)

        result = restore_config_backup(temp_path)
        if not result.get('success'):
            return jsonify(result), 400

        reboot_result = reboot_system(2)
        result['reboot'] = reboot_result
        return jsonify(result)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

# ============================================================================
# UPDATE ROUTES
# ============================================================================

@system_bp.route('/updates/check', methods=['GET'])
def check_updates():
    """Check for application updates."""
    result = check_for_updates()
    
    return jsonify({
        'success': True,
        **result
    })

@system_bp.route('/updates/install', methods=['POST'])
def install_update():
    """Install application update."""
    data = request.get_json(silent=True) or {}
    backup = data.get('backup', True)
    force = bool(data.get('force', False))
    reset_settings = bool(data.get('reset_settings', False))
    
    result = perform_update(backup, force, reset_settings)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@system_bp.route('/apt/updates', methods=['GET'])
def apt_updates():
    """Check for APT package updates."""
    result = get_apt_updates()
    
    return jsonify({
        'success': True,
        **result
    })

@system_bp.route('/apt/upgrade', methods=['POST'])
def apt_upgrade():
    """Perform APT package upgrade."""
    data = request.get_json(silent=True) or {}
    packages = data.get('packages')
    security_only = data.get('security_only', False)
    
    result = perform_apt_upgrade(packages, security_only)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

# ============================================================================
# SERVICE CONTROL ROUTES
# ============================================================================

@system_bp.route('/restart/<service_name>', methods=['POST'])
def restart_single_service(service_name):
    """Restart a specific service."""
    result = restart_service(service_name)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

@system_bp.route('/restart-all', methods=['POST'])
def restart_all():
    """Restart all RTSP-related services."""
    results = restart_all_services()
    
    return jsonify({
        'success': True,
        'results': results
    })

# ============================================================================
# POWER CONTROL ROUTES
# ============================================================================

@system_bp.route('/reboot', methods=['POST'])
def reboot():
    """Reboot the system."""
    data = request.get_json(silent=True) or {}
    delay = data.get('delay', 0)
    
    result = reboot_system(delay)
    
    return jsonify(result)

@system_bp.route('/reboot/schedule', methods=['GET'])
def get_reboot_schedule_route():
    return jsonify(get_reboot_schedule())

@system_bp.route('/reboot/schedule', methods=['POST'])
def set_reboot_schedule_route():
    data = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))
    hour = data.get('hour', 3)
    minute = data.get('minute', 0)
    days = data.get('days', ['all'])
    result = set_reboot_schedule(enabled, hour, minute, days)
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code

@system_bp.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the system."""
    data = request.get_json(silent=True) or {}
    delay = data.get('delay', 0)
    
    result = shutdown_system(delay)
    
    return jsonify(result)

# ============================================================================
# NTP ROUTES
# ============================================================================

def _get_ntp_server():
    """Get current NTP server from timesyncd.conf or chrony.conf."""
    server = None
    
    # Try timesyncd.conf first (Debian default)
    timesyncd_paths = [
        '/etc/systemd/timesyncd.conf',
        '/etc/systemd/timesyncd.conf.d/local.conf'
    ]
    for conf_path in timesyncd_paths:
        if os.path.exists(conf_path):
            try:
                with open(conf_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('NTP='):
                            server = line.split('=', 1)[1].strip().split()[0]
                            if server:
                                return server
                        elif line.strip().startswith('FallbackNTP=') and not server:
                            server = line.split('=', 1)[1].strip().split()[0]
            except:
                pass
    
    # Try chrony.conf
    if os.path.exists('/etc/chrony/chrony.conf'):
        try:
            with open('/etc/chrony/chrony.conf', 'r') as f:
                for line in f:
                    if line.strip().startswith('server ') or line.strip().startswith('pool '):
                        server = line.strip().split()[1]
                        break
        except:
            pass
    
    return server or 'pool.ntp.org'  # Default

@system_bp.route('/ntp', methods=['GET'])
def get_ntp_status():
    """Get NTP synchronization status."""
    try:
        # Get timedatectl status
        result = subprocess.run(['timedatectl', 'show'], 
                              capture_output=True, text=True, timeout=10)
        
        status = {
            'ntp_enabled': False,
            'synchronized': False,  # JS uses 'synchronized', not 'ntp_synchronized'
            'ntp_synchronized': False,  # Keep for backward compatibility
            'timezone': 'Unknown',
            'server': _get_ntp_server(),  # NTP server configured
            'current_time': time.strftime('%Y-%m-%d %H:%M:%S'),  # JS uses 'current_time'
            'local_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'utc_time': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
        }
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key == 'NTP':
                        status['ntp_enabled'] = value.lower() == 'yes'
                    elif key == 'NTPSynchronized':
                        is_sync = value.lower() == 'yes'
                        status['ntp_synchronized'] = is_sync
                        status['synchronized'] = is_sync  # JS uses this field
                    elif key == 'Timezone':
                        status['timezone'] = value
        
        return jsonify({
            'success': True,
            **status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@system_bp.route('/ntp', methods=['POST'])
def set_ntp_config():
    """Configure NTP settings."""
    data = request.get_json(silent=True) or {}
    ntp_enabled = data.get('ntp_enabled', True)
    timezone = data.get('timezone')
    
    results = []
    
    try:
        # Enable/disable NTP
        action = 'true' if ntp_enabled else 'false'
        result = subprocess.run(['sudo', 'timedatectl', 'set-ntp', action],
                              capture_output=True, text=True, timeout=10)
        results.append({
            'action': f'set-ntp {action}',
            'success': result.returncode == 0,
            'error': result.stderr if result.returncode != 0 else None
        })
        
        # Set timezone if specified
        if timezone:
            result = subprocess.run(['sudo', 'timedatectl', 'set-timezone', timezone],
                                  capture_output=True, text=True, timeout=10)
            results.append({
                'action': f'set-timezone {timezone}',
                'success': result.returncode == 0,
                'error': result.stderr if result.returncode != 0 else None
            })
        
        all_success = all(r['success'] for r in results)
        
        return jsonify({
            'success': all_success,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@system_bp.route('/ntp/sync', methods=['POST'])
def force_ntp_sync():
    """Force immediate NTP synchronization."""
    try:
        # Try systemd-timesyncd first
        result = subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-timesyncd'],
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            # Try chrony if available
            result = subprocess.run(['sudo', 'chronyc', 'makestep'],
                                  capture_output=True, text=True, timeout=10)
        
        return jsonify({
            'success': result.returncode == 0,
            'message': _t('ui.system.ntp.sync_requested'),
            'output': result.stdout if result.returncode == 0 else result.stderr
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# UPDATE ROUTES (Legacy paths for frontend compatibility)
# ============================================================================

@system_bp.route('/update/check', methods=['GET'])
def check_update():
    """Check for application updates (legacy path)."""
    result = check_for_updates()
    
    return jsonify({
        'success': True,
        **result
    })

@system_bp.route('/update/perform', methods=['POST'])
def perform_update_legacy():
    """Perform application update (legacy path)."""
    data = request.get_json(silent=True) or {}
    backup = data.get('backup', True)
    force = bool(data.get('force', False))
    reset_settings = bool(data.get('reset_settings', False))
    
    result = perform_update(backup, force, reset_settings)
    
    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code

# ============================================================================
# UPDATE FROM FILE ROUTES
# ============================================================================

@system_bp.route('/update/file/check', methods=['POST'])
def check_update_file():
    """Validate an update archive uploaded by the user."""
    file = request.files.get('update')
    if not file or not file.filename:
        return jsonify({
            'success': False,
            'message': _t('ui.system.update_file_required')
        }), 400

    force_reapply = str(request.form.get('force', '')).lower() in ['1', 'true', 'yes', 'on']

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as temp_file:
            temp_path = temp_file.name
            file.save(temp_path)

        result = inspect_update_package(temp_path, allow_same_version=force_reapply)
        status = 200 if result.get('success') else 400
        return jsonify(result), status
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

@system_bp.route('/update/file/apply', methods=['POST'])
def apply_update_file():
    """Apply an update archive uploaded by the user."""
    file = request.files.get('update')
    if not file or not file.filename:
        return jsonify({
            'success': False,
            'message': _t('ui.system.update_file_required')
        }), 400

    force_reapply = str(request.form.get('force', '')).lower() in ['1', 'true', 'yes', 'on']
    install_deps = True
    reset_settings = str(request.form.get('reset_settings', '')).lower() in ['1', 'true', 'yes', 'on']

    with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as temp_file:
        temp_path = temp_file.name
        file.save(temp_path)

    result = start_update_from_file(
        temp_path,
        allow_same_version=force_reapply,
        install_deps=install_deps,
        reset_settings=reset_settings
    )
    status = 200 if result.get('success') else 400
    return jsonify(result), status

@system_bp.route('/update/file/status', methods=['GET'])
def update_file_status():
    """Return current update-from-file status."""
    return jsonify(get_update_status())

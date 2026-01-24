# -*- coding: utf-8 -*-
"""
Debug Blueprint - Firmware, APT, and system debug routes
Version: 2.30.8

NOTE: All debug API endpoints require 'vnc' or 'debug' service to be declared
in Meeting. If not declared, endpoints return 403 Forbidden.
"""

import os
import time
import json
import subprocess
from functools import wraps
from datetime import datetime
from flask import Blueprint, request, jsonify

from services.platform_service import run_command, PLATFORM
from services.meeting_service import is_debug_enabled
from services.system_service import get_rtc_debug_info
from services.i18n_service import t as i18n_t, resolve_request_lang

debug_bp = Blueprint('debug', __name__, url_prefix='/api')


def _t(key, **params):
    return i18n_t(key, lang=resolve_request_lang(request), params=params)

# ============================================================================
# ACCESS CONTROL DECORATOR
# ============================================================================

def require_debug_access(f):
    """Decorator to require debug access (vnc or debug service declared in Meeting)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_debug_enabled():
            return jsonify({
                'success': False,
                'error': _t('ui.debug.access_denied'),
                'message': _t('ui.debug.access_required')
            }), 403
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# LAST ACTION DATES & SCHEDULER PERSISTENCE
# ============================================================================

DEBUG_STATE_FILE = '/etc/rpi-cam/debug_state.json'
APT_SCHEDULER_CRON = '/etc/cron.d/rpi-cam-apt-autoupdate'

def load_debug_state():
    """Load debug state (last action dates, scheduler config)."""
    try:
        if os.path.exists(DEBUG_STATE_FILE):
            with open(DEBUG_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"[DEBUG] Error loading state: {e}")
    return {
        'last_actions': {
            'firmware_check': None,
            'firmware_update': None,
            'apt_update': None,
            'apt_upgrade': None
        },
        'apt_scheduler': {
            'enabled': False,
            'update_hour': 3,
            'update_minute': 0,
            'upgrade_enabled': False,
            'upgrade_day': 0  # 0=Sunday, 1=Monday, etc.
        }
    }

def save_debug_state(state):
    """Save debug state to persistent storage."""
    try:
        os.makedirs(os.path.dirname(DEBUG_STATE_FILE), exist_ok=True)
        with open(DEBUG_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"[DEBUG] Error saving state: {e}")
        return False

def record_action(action_name):
    """Record the timestamp of an action."""
    state = load_debug_state()
    state['last_actions'][action_name] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_debug_state(state)

def update_apt_cron(scheduler_config):
    """Update the cron job for apt auto-update."""
    try:
        if not scheduler_config.get('enabled'):
            # Remove cron file if exists
            if os.path.exists(APT_SCHEDULER_CRON):
                subprocess.run(['sudo', 'rm', '-f', APT_SCHEDULER_CRON], 
                             capture_output=True, timeout=10)
            return True
        
        hour = scheduler_config.get('update_hour', 3)
        minute = scheduler_config.get('update_minute', 0)
        upgrade_enabled = scheduler_config.get('upgrade_enabled', False)
        upgrade_day = scheduler_config.get('upgrade_day', 0)
        
        # Build cron content
        cron_lines = [
            "# RTSP-Full Automatic APT Updates",
            "# Managed by rpi-cam-webmanager - DO NOT EDIT MANUALLY",
            "SHELL=/bin/bash",
            "PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin",
            "",
            f"# Daily apt update at {hour:02d}:{minute:02d}",
            f"{minute} {hour} * * * root /usr/bin/apt-get update -qq > /var/log/rpi-cam/apt-autoupdate.log 2>&1"
        ]
        
        if upgrade_enabled:
            # Weekly upgrade on specified day
            day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
            cron_lines.extend([
                "",
                f"# Weekly apt upgrade on {day_names[upgrade_day]} at {hour:02d}:{minute+5:02d}",
                f"{(minute+5) % 60} {hour + ((minute+5)//60)} * * {upgrade_day} root DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get upgrade -y -qq >> /var/log/rpi-cam/apt-autoupdate.log 2>&1"
            ])
        
        cron_content = '\n'.join(cron_lines) + '\n'
        
        # Write via sudo tee
        result = subprocess.run(
            ['sudo', 'tee', APT_SCHEDULER_CRON],
            input=cron_content, capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            subprocess.run(['sudo', 'chmod', '644', APT_SCHEDULER_CRON], 
                         capture_output=True, timeout=5)
            return True
        return False
    except Exception as e:
        print(f"[DEBUG] Error updating cron: {e}")
        return False

# ============================================================================
# LAST ACTIONS API
# ============================================================================

@debug_bp.route('/debug/last-actions', methods=['GET'])
@require_debug_access
def get_last_actions():
    """Get last action dates for debug operations."""
    state = load_debug_state()
    return jsonify({
        'success': True,
        'last_actions': state.get('last_actions', {})
    })

# ============================================================================
# APT SCHEDULER API
# ============================================================================

@debug_bp.route('/debug/apt/scheduler', methods=['GET'])
@require_debug_access
def get_apt_scheduler():
    """Get APT auto-update scheduler configuration."""
    state = load_debug_state()
    scheduler = state.get('apt_scheduler', {})
    
    # Check if cron file exists
    cron_exists = os.path.exists(APT_SCHEDULER_CRON)
    
    return jsonify({
        'success': True,
        'scheduler': scheduler,
        'cron_active': cron_exists
    })

@debug_bp.route('/debug/apt/scheduler', methods=['POST'])
@require_debug_access
def set_apt_scheduler():
    """Set APT auto-update scheduler configuration."""
    try:
        data = request.get_json(silent=True) or {}
        
        state = load_debug_state()
        scheduler = state.get('apt_scheduler', {})
        
        # Update scheduler config
        if 'enabled' in data:
            scheduler['enabled'] = bool(data['enabled'])
        if 'update_hour' in data:
            scheduler['update_hour'] = max(0, min(23, int(data['update_hour'])))
        if 'update_minute' in data:
            scheduler['update_minute'] = max(0, min(59, int(data['update_minute'])))
        if 'upgrade_enabled' in data:
            scheduler['upgrade_enabled'] = bool(data['upgrade_enabled'])
        if 'upgrade_day' in data:
            scheduler['upgrade_day'] = max(0, min(6, int(data['upgrade_day'])))
        
        state['apt_scheduler'] = scheduler
        
        # Update cron job
        if update_apt_cron(scheduler):
            save_debug_state(state)
            return jsonify({
                'success': True,
                'message': _t('ui.debug.scheduler.updated'),
                'scheduler': scheduler
            })
        else:
            return jsonify({
                'success': False,
                'message': _t('ui.debug.scheduler.update_error')
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# FIRMWARE UPDATE
# ============================================================================

def get_pi_model():
    """Detect Raspberry Pi model for firmware update method selection."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip().rstrip('\x00')
            if 'Pi 4' in model or 'Pi 5' in model:
                return 'pi4+'  # Uses rpi-eeprom-update
            elif 'Pi 3' in model or 'Pi 2' in model or 'Pi Zero' in model:
                return 'pi3'   # Uses rpi-update
            else:
                return 'unknown'
    except:
        return 'unknown'

def has_initramfs():
    """Check if system uses initramfs (incompatible with rpi-update)."""
    config_files = ['/boot/firmware/config.txt', '/boot/config.txt']
    for cfg in config_files:
        try:
            if os.path.exists(cfg):
                with open(cfg, 'r') as f:
                    content = f.read()
                    if 'initramfs' in content.lower():
                        return True
        except:
            pass
    
    initrd_paths = [
        '/boot/firmware/initrd.img',
        '/boot/initrd.img',
        '/boot/firmware/initramfs'
    ]
    for path in initrd_paths:
        if os.path.exists(path):
            return True
    
    try:
        import glob
        if glob.glob('/boot/firmware/initrd.img-*') or glob.glob('/boot/initrd.img-*'):
            return True
    except:
        pass
    
    return False

@debug_bp.route('/debug/firmware/check', methods=['GET'])
@require_debug_access
def firmware_check():
    """Check for Raspberry Pi firmware updates."""
    pi_model = get_pi_model()
    record_action('firmware_check')
    
    try:
        if pi_model == 'pi4+':
            result = subprocess.run(
                ['sudo', 'rpi-eeprom-update'],
                capture_output=True, text=True, timeout=30
            )
            
            output = result.stdout + result.stderr
            update_available = 'UPDATE AVAILABLE' in output.upper()
            
            current_version = _t('ui.status.unknown')
            for line in output.split('\n'):
                if 'CURRENT:' in line or 'current:' in line.lower():
                    current_version = line.split(':')[-1].strip()
                    break
            
            return jsonify({
                'success': True,
                'method': 'rpi-eeprom-update',
                'model': 'Pi 4/5',
                'update_available': update_available,
                'current_version': current_version,
                'output': output,
                'message': _t('ui.debug.firmware.eeprom_available') if update_available else _t('ui.debug.firmware.eeprom_up_to_date'),
                'can_update': True
            })
        else:
            if has_initramfs():
                try:
                    uname_result = subprocess.run(['uname', '-r'], capture_output=True, text=True, timeout=5)
                    kernel_version = uname_result.stdout.strip()
                except:
                    kernel_version = _t('ui.status.unknown')
                
                return jsonify({
                    'success': True,
                    'method': 'apt',
                    'model': 'Pi 3/2/Zero (initramfs)',
                    'update_available': False,
                    'current_version': kernel_version,
                    'output': _t('ui.debug.firmware.initramfs_output'),
                    'message': _t('ui.debug.firmware.use_apt_message'),
                    'can_update': False,
                    'use_apt': True
                })
            
            env = os.environ.copy()
            env['JUST_CHECK'] = '1'
            
            result = subprocess.run(
                ['sudo', '-E', 'rpi-update'],
                capture_output=True, text=True, timeout=60,
                env=env
            )
            
            output = result.stdout + result.stderr
            update_available = 'update required' in output.lower() or 'running for the first time' in output.lower()
            
            current_version = _t('ui.status.unknown')
            for line in output.split('\n'):
                if 'FW_REV:' in line:
                    current_version = line.split(':')[-1].strip()[:12] + '...'
                    break
            
            return jsonify({
                'success': True,
                'method': 'rpi-update',
                'model': 'Pi 3/2/Zero',
                'update_available': update_available,
                'current_version': current_version,
                'output': output,
                'message': _t('ui.debug.firmware.available') if update_available else _t('ui.debug.firmware.up_to_date'),
                'can_update': True
            })
            
    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'message': _t('ui.debug.firmware.tool_not_found', error=str(e)),
            'output': _t('ui.debug.firmware.install_tools')
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': _t('ui.debug.firmware.check_timeout'),
            'output': _t('ui.debug.firmware.check_timeout_output')
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@debug_bp.route('/debug/firmware/update', methods=['POST'])
@require_debug_access
def firmware_update():
    """Apply Raspberry Pi firmware update."""
    pi_model = get_pi_model()
    record_action('firmware_update')
    
    try:
        if pi_model == 'pi4+':
            result = subprocess.run(
                ['sudo', 'rpi-eeprom-update', '-a'],
                capture_output=True, text=True, timeout=300
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            return jsonify({
                'success': success,
                'method': 'rpi-eeprom-update',
                'output': output,
                'message': _t('ui.debug.firmware.eeprom_updated') if success else _t('ui.debug.firmware.eeprom_update_failed'),
                'reboot_required': success
            })
        else:
            result = subprocess.run(
                ['sudo', 'rpi-update'],
                capture_output=True, text=True, timeout=600,
                input='y\n'
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0 or 'already up to date' in output.lower()
            
            return jsonify({
                'success': success,
                'method': 'rpi-update',
                'output': output,
                'message': _t('ui.debug.firmware.updated') if success else _t('ui.debug.firmware.update_failed'),
                'reboot_required': success,
                'warning': _t('ui.debug.firmware.experimental_warning')
            })
            
    except FileNotFoundError as e:
        return jsonify({
            'success': False,
            'message': _t('ui.debug.firmware.tool_not_found', error=str(e))
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': _t('ui.debug.firmware.update_timeout')
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================================================
# APT PACKAGE MANAGEMENT
# ============================================================================

@debug_bp.route('/debug/apt/update', methods=['POST'])
@require_debug_access
def apt_update():
    """Run apt update to refresh package lists."""
    record_action('apt_update')
    try:
        result = subprocess.run(
            ['sudo', 'apt-get', 'update'],
            capture_output=True, text=True, timeout=300
        )
        
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        hit_count = output.count('Hit:')
        get_count = output.count('Get:')
        
        return jsonify({
            'success': success,
            'output': output,
            'hit_count': hit_count,
            'get_count': get_count,
            'message': _t('ui.debug.apt_update.completed_message', hit_count=hit_count, get_count=get_count) if success else _t('ui.debug.apt_update.failed')
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': _t('ui.debug.apt_update.timeout')
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@debug_bp.route('/debug/apt/upgradable', methods=['GET'])
@require_debug_access
def apt_upgradable():
    """List packages that can be upgraded."""
    try:
        result = subprocess.run(
            ['apt', 'list', '--upgradable'],
            capture_output=True, text=True, timeout=60
        )
        
        output = result.stdout
        lines = [l for l in output.split('\n') if l and 'Listing...' not in l]
        
        packages = []
        for line in lines:
            if '/' in line:
                parts = line.split()
                if parts:
                    pkg_name = parts[0].split('/')[0]
                    pkg_version = parts[1] if len(parts) > 1 else ''
                    packages.append({
                        'name': pkg_name,
                        'version': pkg_version,
                        'line': line
                    })
        
        return jsonify({
            'success': True,
            'packages': packages,
            'count': len(packages),
            'output': output,
            'message': _t('ui.debug.apt_upgrade.available_count', count=len(packages))
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@debug_bp.route('/debug/apt/upgrade', methods=['POST'])
@require_debug_access
def apt_upgrade():
    """Run apt upgrade to update all packages."""
    record_action('apt_upgrade')
    try:
        env = os.environ.copy()
        env['DEBIAN_FRONTEND'] = 'noninteractive'
        
        result = subprocess.run(
            ['sudo', 'apt-get', 'upgrade', '-y'],
            capture_output=True, text=True, timeout=1800,
            env=env
        )
        
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        upgraded = 0
        newly_installed = 0
        for line in output.split('\n'):
            if 'upgraded,' in line and 'newly installed' in line:
                parts = line.split()
                try:
                    upgraded = int(parts[0])
                    newly_installed = int(parts[2])
                except:
                    pass
        
        return jsonify({
            'success': success,
            'output': output,
            'upgraded': upgraded,
            'newly_installed': newly_installed,
            'message': _t('ui.debug.apt_upgrade.completed_message', upgraded=upgraded, newly_installed=newly_installed) if success else _t('ui.debug.apt_upgrade.failed')
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': _t('ui.debug.apt_upgrade.timeout')
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@debug_bp.route('/debug/system/uptime', methods=['GET'])
@require_debug_access
def system_uptime():
    """Get system uptime."""
    try:
        result = subprocess.run(
            ['uptime', '-p'],
            capture_output=True, text=True, timeout=5
        )
        uptime_pretty = result.stdout.strip()
        
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
        
        return jsonify({
            'success': True,
            'uptime': uptime_pretty,
            'uptime_seconds': uptime_seconds
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@debug_bp.route('/debug/rtc', methods=['GET'])
@require_debug_access
def debug_rtc():
    """Get RTC DS3231 debug information."""
    return jsonify(get_rtc_debug_info())

# ============================================================================
# WEB TERMINAL
# ============================================================================

# Whitelist of allowed commands (security)
TERMINAL_ALLOWED_COMMANDS = [
    'ls', 'cat', 'head', 'tail', 'grep', 'find', 'df', 'du', 'free', 'top',
    'ps', 'uptime', 'date', 'hostname', 'uname', 'whoami', 'id', 'pwd',
    'journalctl', 'systemctl', 'service', 'dmesg', 'vcgencmd', 'pinctrl',
    'ip', 'ifconfig', 'iwconfig', 'nmcli', 'netstat', 'ss', 'ping', 'traceroute',
    'v4l2-ctl', 'ffprobe', 'ffmpeg', 'gst-launch-1.0', 'gst-inspect-1.0',
    'apt', 'apt-get', 'apt-cache', 'dpkg',
    'lsusb', 'lspci', 'lsblk', 'lscpu', 'lshw', 'lsmod',
    'mount', 'blkid', 'fdisk',
    'test-launch', 'rpi-eeprom-update', 'rpi-update',
    'timedatectl', 'raspi-config', 'vcdbg',
    'echo', 'which', 'whereis', 'file', 'stat', 'wc', 'sort', 'uniq',
    'awk', 'sed', 'cut', 'tr', 'tee',
    'curl', 'wget',
    'clear', 'history',
    'sudo'
]

@debug_bp.route('/debug/terminal/exec', methods=['POST'])
@require_debug_access
def terminal_exec():
    """
    Execute a shell command and return the output.
    Limited to whitelisted commands for security.
    """
    try:
        data = request.get_json(silent=True) or {}
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({
                'success': False,
                'error': _t('ui.debug.terminal.no_command')
            }), 400
        
        # Parse command to check if it's allowed
        import shlex
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': _t('ui.debug.terminal.invalid_syntax', error=str(e))
            }), 400
        
        if not parts:
            return jsonify({
                'success': False,
                'error': _t('ui.debug.terminal.empty_command')
            }), 400
        
        # Check if base command is allowed
        base_cmd = parts[0]
        if base_cmd not in TERMINAL_ALLOWED_COMMANDS:
            return jsonify({
                'success': False,
                'error': _t('ui.debug.terminal.command_not_allowed', command=base_cmd),
                'allowed': TERMINAL_ALLOWED_COMMANDS
            }), 403
        
        # If sudo, check the actual command
        if base_cmd == 'sudo' and len(parts) > 1:
            actual_cmd = parts[1]
            if actual_cmd not in TERMINAL_ALLOWED_COMMANDS:
                return jsonify({
                    'success': False,
                    'error': _t('ui.debug.terminal.command_not_allowed_sudo', command=actual_cmd)
                }), 403
        
        # Execute command with timeout
        timeout = min(int(data.get('timeout', 30)), 120)  # Max 2 minutes
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=data.get('cwd', '/home/device')
        )
        
        return jsonify({
            'success': True,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'command': command
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': _t('ui.debug.terminal.command_timeout', seconds=timeout),
            'command': command
        }), 408
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@debug_bp.route('/debug/terminal/allowed', methods=['GET'])
@require_debug_access
def terminal_allowed():
    """Get list of allowed terminal commands."""
    return jsonify({
        'success': True,
        'commands': sorted(TERMINAL_ALLOWED_COMMANDS)
    })

# ============================================================================
# NTP CONFIGURATION
# ============================================================================

@debug_bp.route('/system/ntp', methods=['GET'])
def ntp_get():
    """Get NTP configuration and status."""
    try:
        result = {
            'success': True,
            'server': '',
            'synchronized': False,
            'current_time': '',
            'timezone': ''
        }
        
        try:
            with open('/etc/systemd/timesyncd.conf', 'r') as f:
                for line in f:
                    if line.strip().startswith('NTP='):
                        result['server'] = line.split('=', 1)[1].strip()
                        break
        except:
            pass
        
        if not result['server']:
            try:
                output = subprocess.run(
                    ['timedatectl', 'show', '--property=NTP', '--value'],
                    capture_output=True, text=True, timeout=5
                )
                if output.returncode == 0 and output.stdout.strip() == 'yes':
                    result['server'] = 'pool.ntp.org'
            except:
                pass
        
        try:
            output = subprocess.run(
                ['timedatectl', 'show', '--property=NTPSynchronized', '--value'],
                capture_output=True, text=True, timeout=5
            )
            result['synchronized'] = output.stdout.strip().lower() == 'yes'
        except:
            pass
        
        try:
            output = subprocess.run(
                ['date', '+%Y-%m-%d %H:%M:%S'],
                capture_output=True, text=True, timeout=5
            )
            result['current_time'] = output.stdout.strip()
        except:
            pass
        
        try:
            output = subprocess.run(
                ['timedatectl', 'show', '--property=Timezone', '--value'],
                capture_output=True, text=True, timeout=5
            )
            result['timezone'] = output.stdout.strip()
        except:
            pass
        
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@debug_bp.route('/system/ntp', methods=['POST'])
def ntp_set():
    """Set NTP server configuration."""
    try:
        data = request.get_json(silent=True) or {}
        server = data.get('server', '').strip()
        
        if not server:
            return jsonify({
                'success': False,
                'message': _t('ui.system.ntp.server_required')
            }), 400
        
        config_content = f"""[Time]
NTP={server}
FallbackNTP=pool.ntp.org time.google.com
"""
        
        result = subprocess.run(
            ['sudo', 'tee', '/etc/systemd/timesyncd.conf'],
            input=config_content, capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': _t('ui.system.ntp.write_error', error=result.stderr)
            }), 500
        
        subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-timesyncd'],
                      capture_output=True, timeout=10)
        
        return jsonify({
            'success': True,
            'message': _t('ui.system.ntp.server_configured', server=server)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@debug_bp.route('/system/ntp/sync', methods=['POST'])
def ntp_sync():
    """Force NTP synchronization."""
    try:
        result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'systemd-timesyncd'],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({
                'success': False,
                'message': _t('ui.errors.with_message', message=result.stderr)
            }), 500
        
        time.sleep(2)
        
        output = subprocess.run(
            ['timedatectl', 'show', '--property=NTPSynchronized', '--value'],
            capture_output=True, text=True, timeout=5
        )
        synced = output.stdout.strip().lower() == 'yes'
        
        return jsonify({
            'success': True,
            'synchronized': synced,
            'message': _t('ui.system.ntp.sync_done') if synced else _t('ui.system.ntp.sync_in_progress')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

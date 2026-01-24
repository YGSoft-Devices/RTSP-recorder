# -*- coding: utf-8 -*-
"""
Power Service - LED, GPU memory, HDMI, and power management
Version: 2.30.7
"""

import os
import re
import subprocess
from datetime import datetime

from flask import has_request_context, request

from .platform_service import run_command, is_raspberry_pi, PLATFORM
from .config_service import load_config
from .i18n_service import t as i18n_t, resolve_request_lang

# Boot config file path
BOOT_CONFIG_FILE = '/boot/firmware/config.txt' if os.path.exists('/boot/firmware/config.txt') else (
    '/boot/config.txt' if os.path.exists('/boot/config.txt') else None
)

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
# LED MANAGEMENT
# ============================================================================

def get_led_boot_config():
    """
    Read current LED configuration from boot config.
    Returns dict with current settings.
    """
    config = {
        'pwr_enabled': True,
        'act_enabled': True,
        'source': 'default'
    }
    
    if not BOOT_CONFIG_FILE or not os.path.exists(BOOT_CONFIG_FILE):
        return config
    
    try:
        with open(BOOT_CONFIG_FILE, 'r') as f:
            content = f.read()
        
        # Check for PWR LED disabled
        if re.search(r'dtparam=pwr_led_trigger=none', content) or \
           re.search(r'dtparam=power_led_trigger=none', content):
            config['pwr_enabled'] = False
            config['source'] = 'boot_config'
        
        # Check for ACT LED disabled
        if re.search(r'dtparam=act_led_trigger=none', content) or \
           re.search(r'dtparam=activity_led_trigger=none', content):
            config['act_enabled'] = False
            config['source'] = 'boot_config'
    except Exception as e:
        print(f"Error reading LED boot config: {e}")
    
    return config

def save_led_boot_config(pwr_enabled=None, act_enabled=None):
    """
    Save LED configuration to boot config for persistence.
    
    Args:
        pwr_enabled: bool - Enable power LED (None to skip)
        act_enabled: bool - Enable activity LED (None to skip)
    
    Returns:
        dict: {success: bool, message: str}
    """
    if not BOOT_CONFIG_FILE:
        return {'success': False, 'message': _t('ui.power.boot_config_not_found')}
    
    try:
        content = ""
        if os.path.exists(BOOT_CONFIG_FILE):
            with open(BOOT_CONFIG_FILE, 'r') as f:
                content = f.read()
        
        lines = content.split('\n')
        new_lines = []
        
        # Filter out existing LED config lines
        for line in lines:
            if not re.match(r'^dtparam=(pwr|power|act|activity)_led', line.strip()):
                new_lines.append(line)
        
        # Add new configuration
        if pwr_enabled is not None:
            if not pwr_enabled:
                new_lines.append('dtparam=pwr_led_trigger=none')
        
        if act_enabled is not None:
            if not act_enabled:
                new_lines.append('dtparam=act_led_trigger=none')
        
        # Write back
        with open(BOOT_CONFIG_FILE, 'w') as f:
            f.write('\n'.join(new_lines))
        
        return {
            'success': True,
            'message': _t('ui.power.led_boot_saved_reboot'),
            'reboot_required': True
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}

def get_led_paths():
    """Get LED paths based on platform."""
    leds = {}
    
    # Standard Raspberry Pi LED paths
    pwr_paths = ['/sys/class/leds/PWR', '/sys/class/leds/led1']
    act_paths = ['/sys/class/leds/ACT', '/sys/class/leds/led0']
    
    for path in pwr_paths:
        if os.path.exists(path):
            leds['pwr'] = path
            break
    
    for path in act_paths:
        if os.path.exists(path):
            leds['act'] = path
            break
    
    # Ethernet LED paths (Pi 4/5 with bcmgenet only)
    # Pi 3B/3B+ (smsc95xx/lan78xx) don't have software-controllable LEDs
    eth_led_paths = [
        '/sys/class/leds/led2',           # Some Pi 4 variants
        '/sys/class/leds/eth_led0',       # Alternative naming
        '/sys/class/net/eth0/device/leds' # Generic location
    ]
    for path in eth_led_paths:
        if os.path.exists(path):
            leds['eth'] = path
            break
    
    return leds


def is_ethernet_led_controllable():
    """
    Check if Ethernet LEDs can be controlled via software.
    
    Returns tuple: (controllable: bool, reason: str)
    
    Note: Raspberry Pi 3B/3B+ use smsc95xx/lan78xx controllers
    where LEDs are controlled by the PHY chip, not software.
    Pi 4/5 with bcmgenet may have software control.
    """
    import subprocess
    
    # Check for known non-controllable drivers
    driver_path = '/sys/class/net/eth0/device/driver/module/name'
    if os.path.exists(driver_path):
        try:
            with open(driver_path, 'r') as f:
                driver = f.read().strip()
                if driver in ['smsc95xx', 'lan78xx']:
                    return False, f"Driver {driver} (LEDs controlled by PHY)"
        except:
            pass
    
    # Check for ethtool LED control (Pi 4/5)
    try:
        result = subprocess.run(
            ['ethtool', '--show-eee', 'eth0'],
            capture_output=True, text=True, timeout=5
        )
        # If ethtool exists and doesn't error, we might have control
        if result.returncode == 0:
            return True, "ethtool supported"
    except:
        pass
    
    # Check for sysfs LED control
    led_paths = [
        '/sys/class/leds/led2',
        '/sys/class/leds/eth_led0',
    ]
    for path in led_paths:
        if os.path.exists(path):
            return True, f"sysfs control at {path}"
    
    return False, "No software control available"


def get_led_status():
    """Get current LED status with format expected by template."""
    leds = {
        'pwr': {'enabled': True, 'trigger': 'default-on', 'available': False, 'boot_disabled': False},
        'act': {'enabled': True, 'trigger': 'mmc0', 'available': False, 'boot_disabled': False},
        'eth': {'enabled': True, 'trigger': None, 'available': False, 'boot_disabled': False, 'reason': ''}
    }
    
    if not PLATFORM['has_led_control']:
        # Still check Ethernet LED availability even without general LED control
        eth_controllable, eth_reason = is_ethernet_led_controllable()
        leds['eth']['available'] = eth_controllable
        leds['eth']['reason'] = eth_reason
        return leds
    
    led_paths = get_led_paths()
    
    # Get boot config status
    boot_config = get_led_boot_config()
    
    try:
        # Check PWR LED
        if 'pwr' in led_paths:
            leds['pwr']['available'] = True
            leds['pwr']['boot_disabled'] = not boot_config.get('pwr_enabled', True)
            
            pwr_path = f"{led_paths['pwr']}/brightness"
            if os.path.exists(pwr_path):
                with open(pwr_path, 'r') as f:
                    leds['pwr']['enabled'] = int(f.read().strip()) > 0
            
            pwr_trigger = f"{led_paths['pwr']}/trigger"
            if os.path.exists(pwr_trigger):
                with open(pwr_trigger, 'r') as f:
                    content = f.read()
                    match = re.search(r'\[([^\]]+)\]', content)
                    if match:
                        leds['pwr']['trigger'] = match.group(1)
        
        # Check ACT LED
        if 'act' in led_paths:
            leds['act']['available'] = True
            leds['act']['boot_disabled'] = not boot_config.get('act_enabled', True)
            
            act_path = f"{led_paths['act']}/brightness"
            if os.path.exists(act_path):
                with open(act_path, 'r') as f:
                    leds['act']['enabled'] = int(f.read().strip()) > 0
            
            act_trigger = f"{led_paths['act']}/trigger"
            if os.path.exists(act_trigger):
                with open(act_trigger, 'r') as f:
                    content = f.read()
                    match = re.search(r'\[([^\]]+)\]', content)
                    if match:
                        leds['act']['trigger'] = match.group(1)
        
        # Check Ethernet LED
        eth_controllable, eth_reason = is_ethernet_led_controllable()
        leds['eth']['available'] = eth_controllable
        leds['eth']['reason'] = eth_reason
        
        if eth_controllable and 'eth' in led_paths:
            eth_path = f"{led_paths['eth']}/brightness"
            if os.path.exists(eth_path):
                with open(eth_path, 'r') as f:
                    leds['eth']['enabled'] = int(f.read().strip()) > 0
            
            eth_trigger = f"{led_paths['eth']}/trigger"
            if os.path.exists(eth_trigger):
                with open(eth_trigger, 'r') as f:
                    content = f.read()
                    match = re.search(r'\[([^\]]+)\]', content)
                    if match:
                        leds['eth']['trigger'] = match.group(1)
                        
    except Exception as e:
        print(f"Error getting LED status: {e}")
    
    return leds

def set_led_state(led, enabled, trigger=None):
    """Set LED state (immediate effect)."""
    import subprocess
    
    led_paths = get_led_paths()
    
    if led not in led_paths:
        return False, f"LED '{led}' not found"
    
    try:
        led_base = led_paths[led]
        
        # Set trigger to 'none' to disable any automatic behavior
        trigger_path = f'{led_base}/trigger'
        if os.path.exists(trigger_path):
            new_trigger = trigger if trigger else ('default-on' if enabled else 'none')
            subprocess.run(
                ['sudo', 'bash', '-c', f'echo "{new_trigger}" > {trigger_path}'],
                capture_output=True, timeout=5
            )
        
        # Set brightness for immediate effect
        brightness_path = f'{led_base}/brightness'
        if os.path.exists(brightness_path):
            value = '1' if enabled else '0'
            subprocess.run(
                ['sudo', 'bash', '-c', f'echo "{value}" > {brightness_path}'],
                capture_output=True, timeout=5
            )
        
        return True, "LED updated"
    except Exception as e:
        return False, str(e)

def configure_leds_boot(pwr_enabled, act_enabled):
    """
    Configure LEDs in boot config for persistence across reboots.
    
    This ensures LEDs are disabled from the very first moment of boot
    if configured to be off. Uses dtparam overlay parameters.
    
    For Raspberry Pi 3B+/4/5:
    - PWR LED (red): dtparam=pwr_led_trigger, dtparam=pwr_led_activelow
    - ACT LED (green): dtparam=act_led_trigger, dtparam=act_led_activelow
    
    To completely disable a LED at boot:
    - Set trigger to 'none' (no automatic behavior)
    - Set activelow to 'off' (LED stays off when trigger is none)
    """
    if not BOOT_CONFIG_FILE:
        return False, _t('ui.power.boot_config_not_found')
    
    try:
        config_content = ""
        if os.path.exists(BOOT_CONFIG_FILE):
            with open(BOOT_CONFIG_FILE, 'r') as f:
                config_content = f.read()
        
        # Remove existing LED settings (all variations)
        patterns_to_remove = [
            r'\n?# LED Configuration[^\n]*\n?',
            r'\n?# Disable PWR LED[^\n]*\n?',
            r'\n?# Disable ACT LED[^\n]*\n?',
            r'\n?dtparam=pwr_led_trigger=[^\n]*',
            r'\n?dtparam=pwr_led_activelow=[^\n]*',
            r'\n?dtparam=act_led_trigger=[^\n]*',
            r'\n?dtparam=act_led_activelow=[^\n]*',
            r'\n?dtparam=act_led_gpio=[^\n]*',
            r'\n?dtparam=pwr_led_gpio=[^\n]*',
            # Pi 5 specific
            r'\n?dtparam=power_led_trigger=[^\n]*',
            r'\n?dtparam=power_led_activelow=[^\n]*',
            r'\n?dtparam=activity_led_trigger=[^\n]*',
            r'\n?dtparam=activity_led_activelow=[^\n]*',
        ]
        
        for pattern in patterns_to_remove:
            config_content = re.sub(pattern, '', config_content)
        
        # Clean up multiple blank lines
        config_content = re.sub(r'\n{3,}', '\n\n', config_content)
        
        # Build new LED configuration
        led_config_lines = []
        
        # Detect Pi model for correct parameters
        pi_model = PLATFORM.get('model', '')
        is_pi5 = 'Pi 5' in pi_model or 'Raspberry Pi 5' in pi_model
        
        if not pwr_enabled:
            led_config_lines.append("# Disable PWR LED (red) - completely off at boot")
            if is_pi5:
                led_config_lines.append("dtparam=power_led_trigger=none")
                led_config_lines.append("dtparam=power_led_activelow=off")
            else:
                led_config_lines.append("dtparam=pwr_led_trigger=none")
                led_config_lines.append("dtparam=pwr_led_activelow=off")
        
        if not act_enabled:
            led_config_lines.append("# Disable ACT LED (green) - completely off at boot")
            if is_pi5:
                led_config_lines.append("dtparam=activity_led_trigger=none")
                led_config_lines.append("dtparam=activity_led_activelow=off")
            else:
                led_config_lines.append("dtparam=act_led_trigger=none")
                led_config_lines.append("dtparam=act_led_activelow=off")
        
        # Only add LED section if there are changes
        if led_config_lines:
            led_config = "\n\n# === LED Configuration (managed by web interface) ===\n"
            led_config += "\n".join(led_config_lines) + "\n"
            config_content = config_content.rstrip() + led_config
        
        # Write the config file
        with open(BOOT_CONFIG_FILE, 'w') as f:
            f.write(config_content)
        
        return True, "LED boot config updated (reboot required for full effect)"
    except PermissionError:
        return False, "Permission denied. Run with sudo."
    except Exception as e:
        return False, str(e)

# ============================================================================
# GPU MEMORY MANAGEMENT
# ============================================================================

def get_gpu_mem():
    """
    Get the current GPU memory allocation.
    
    Returns:
        dict: {current: int, available_options: list}
    """
    result = {
        'current': 128,  # Default
        'available_options': [16, 32, 64, 128, 256, 512],
        'recommended': 128
    }
    
    # Read from config.txt
    config_file = '/boot/config.txt'
    if os.path.exists('/boot/firmware/config.txt'):
        config_file = '/boot/firmware/config.txt'
    
    try:
        with open(config_file, 'r') as f:
            for line in f:
                if line.strip().startswith('gpu_mem='):
                    result['current'] = int(line.split('=')[1].strip())
                    break
    except:
        pass
    
    # Also try vcgencmd
    cmd_result = run_command("vcgencmd get_mem gpu", timeout=5)
    if cmd_result['success']:
        match = re.search(r'(\d+)', cmd_result['stdout'])
        if match:
            result['current'] = int(match.group(1))
    
    # Adjust recommendations based on Pi version
    if PLATFORM['pi_version'] >= 4:
        result['recommended'] = 256
    elif PLATFORM['pi_version'] == 3:
        result['recommended'] = 128
    
    return result

def set_gpu_mem(mem_mb):
    """
    Set the GPU memory allocation (requires reboot).
    
    Args:
        mem_mb: Memory in MB (16, 32, 64, 128, 256, or 512)
    
    Returns:
        dict: {success: bool, message: str, requires_reboot: bool}
    """
    valid_values = [16, 32, 64, 128, 256, 512]
    
    if mem_mb not in valid_values:
        return {
            'success': False,
            'message': f'Invalid GPU memory value. Use: {valid_values}',
            'requires_reboot': False
        }
    
    config_file = '/boot/config.txt'
    if os.path.exists('/boot/firmware/config.txt'):
        config_file = '/boot/firmware/config.txt'
    
    try:
        # Read current config
        with open(config_file, 'r') as f:
            lines = f.readlines()
        
        # Update or add gpu_mem line
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith('gpu_mem='):
                lines[i] = f'gpu_mem={mem_mb}\n'
                found = True
                break
        
        if not found:
            lines.append(f'\ngpu_mem={mem_mb}\n')
        
        # Write back
        with open(config_file, 'w') as f:
            f.writelines(lines)
        
        return {
            'success': True,
            'message': f'GPU memory set to {mem_mb}MB. Reboot required.',
            'requires_reboot': True
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'requires_reboot': False
        }

# ============================================================================
# HDMI MANAGEMENT
# ============================================================================

def get_hdmi_status():
    """
    Get HDMI output status.
    
    Returns:
        dict: HDMI status information
    """
    status = {
        'enabled': True,
        'display_detected': False,
        'resolution': 'unknown',
        'can_disable': True
    }
    
    # Check if display is connected
    result = run_command("tvservice -s", timeout=5)
    if result['success']:
        output = result['stdout'].lower()
        status['display_detected'] = 'hdmi' in output and 'off' not in output
        
        # Parse resolution
        match = re.search(r'(\d+x\d+)', result['stdout'])
        if match:
            status['resolution'] = match.group(1)
    
    # Check if HDMI is blanked
    result = run_command("vcgencmd display_power", timeout=5)
    if result['success']:
        status['enabled'] = '1' in result['stdout']
    
    return status

def configure_hdmi(enabled):
    """
    Enable or disable HDMI output.
    
    Args:
        enabled: True to enable, False to disable
    
    Returns:
        dict: {success: bool, message: str}
    """
    if enabled:
        result = run_command("vcgencmd display_power 1", timeout=5)
    else:
        result = run_command("vcgencmd display_power 0", timeout=5)
    
    if result['success']:
        return {
            'success': True,
            'message': f"HDMI {'enabled' if enabled else 'disabled'}"
        }
    else:
        return {
            'success': False,
            'message': result['stderr'] or 'Failed to configure HDMI'
        }

# ============================================================================
# POWER MANAGEMENT
# ============================================================================

def get_power_status():
    """
    Get power-related status information.
    
    Returns:
        dict: Power status including voltage, throttling, temperature
    """
    status = {
        'voltage': None,
        'throttled': False,
        'throttle_reason': [],
        'temperature': None,
        'frequency': None,
        'power_source': 'unknown'
    }
    
    if not is_raspberry_pi():
        return status
    
    # Get throttle status
    result = run_command("vcgencmd get_throttled", timeout=5)
    if result['success']:
        match = re.search(r'0x([0-9a-fA-F]+)', result['stdout'])
        if match:
            throttle_bits = int(match.group(1), 16)
            
            # Decode throttle bits
            if throttle_bits & 0x1:
                status['throttle_reason'].append('under-voltage')
            if throttle_bits & 0x2:
                status['throttle_reason'].append('arm-frequency-capped')
            if throttle_bits & 0x4:
                status['throttle_reason'].append('currently-throttled')
            if throttle_bits & 0x8:
                status['throttle_reason'].append('soft-temperature-limit')
            if throttle_bits & 0x10000:
                status['throttle_reason'].append('under-voltage-occurred')
            if throttle_bits & 0x20000:
                status['throttle_reason'].append('arm-frequency-capped-occurred')
            if throttle_bits & 0x40000:
                status['throttle_reason'].append('throttling-occurred')
            if throttle_bits & 0x80000:
                status['throttle_reason'].append('soft-temperature-limit-occurred')
            
            status['throttled'] = throttle_bits != 0
    
    # Get core voltage
    result = run_command("vcgencmd measure_volts core", timeout=5)
    if result['success']:
        match = re.search(r'(\d+\.\d+)V', result['stdout'])
        if match:
            status['voltage'] = float(match.group(1))
    
    # Get temperature
    result = run_command("vcgencmd measure_temp", timeout=5)
    if result['success']:
        match = re.search(r'(\d+\.\d+)', result['stdout'])
        if match:
            status['temperature'] = float(match.group(1))
    
    # Get CPU frequency
    result = run_command("vcgencmd measure_clock arm", timeout=5)
    if result['success']:
        match = re.search(r'(\d+)', result['stdout'])
        if match:
            status['frequency'] = int(match.group(1)) / 1000000  # Convert to MHz
    
    return status

def configure_power_boot(settings):
    """
    Configure power-related boot settings.
    
    Args:
        settings: dict with power configuration options
    
    Returns:
        dict: {success: bool, message: str, requires_reboot: bool}
    """
    config_file = '/boot/config.txt'
    if os.path.exists('/boot/firmware/config.txt'):
        config_file = '/boot/firmware/config.txt'
    
    changes = []
    
    try:
        with open(config_file, 'r') as f:
            lines = f.readlines()
        
        # Process each setting
        for key, value in settings.items():
            config_key = key
            config_value = str(value)
            
            # Map friendly names to config.txt keys
            key_map = {
                'hdmi_blanking': 'hdmi_blanking',
                'disable_overscan': 'disable_overscan',
                'arm_freq': 'arm_freq',
                'over_voltage': 'over_voltage',
                'disable_splash': 'disable_splash'
            }
            
            if key in key_map:
                config_key = key_map[key]
            
            # Find and update or add the line
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f'{config_key}='):
                    lines[i] = f'{config_key}={config_value}\n'
                    found = True
                    changes.append(f'{config_key}={config_value}')
                    break
            
            if not found:
                lines.append(f'{config_key}={config_value}\n')
                changes.append(f'{config_key}={config_value}')
        
        # Write back
        with open(config_file, 'w') as f:
            f.writelines(lines)
        
        return {
            'success': True,
            'message': f'Power settings updated: {", ".join(changes)}',
            'requires_reboot': True
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'requires_reboot': False
        }

# ============================================================================
# BOOT POWER CONFIGURATION
# ============================================================================

def get_boot_power_config():
    """Read current power configuration from boot config."""
    config = {
        'bluetooth_enabled': True,
        'wifi_enabled': True,
        'hdmi_enabled': True,
        'audio_enabled': True,
        'pwr_led_enabled': True,
        'act_led_enabled': True,
        'camera_led_csi_enabled': True,
        'source': 'default'
    }
    
    if not BOOT_CONFIG_FILE or not os.path.exists(BOOT_CONFIG_FILE):
        return config
    
    try:
        with open(BOOT_CONFIG_FILE, 'r') as f:
            content = f.read()
        
        # Check for disabled components
        if re.search(r'dtoverlay\s*=\s*disable-bt', content):
            config['bluetooth_enabled'] = False
            config['source'] = 'boot_config'
        
        if re.search(r'dtoverlay\s*=\s*disable-wifi', content):
            config['wifi_enabled'] = False
            config['source'] = 'boot_config'
        
        if re.search(r'hdmi_blanking\s*=\s*2', content):
            config['hdmi_enabled'] = False
            config['source'] = 'boot_config'
        
        if re.search(r'dtparam\s*=\s*audio\s*=\s*off', content):
            config['audio_enabled'] = False
            config['source'] = 'boot_config'
        
        # Check for PWR LED disabled
        if re.search(r'dtparam=pwr_led_trigger=none', content) or \
           re.search(r'dtparam=power_led_trigger=none', content):
            config['pwr_led_enabled'] = False
            config['source'] = 'boot_config'
        
        # Check for ACT LED disabled
        if re.search(r'dtparam=act_led_trigger=none', content) or \
           re.search(r'dtparam=activity_led_trigger=none', content):
            config['act_led_enabled'] = False
            config['source'] = 'boot_config'
        
        # Check for Camera LED (CSI) disabled
        if re.search(r'disable_camera_led\s*=\s*1', content):
            config['camera_led_csi_enabled'] = False
            config['source'] = 'boot_config'
            
    except Exception as e:
        print(f"Error reading power boot config: {e}")
    
    return config

def get_full_power_status():
    """Get current power state of all components (for /api/power/status)."""
    import subprocess
    
    status = {
        'bluetooth': {'enabled': None, 'boot_config': None, 'available': False},
        'hdmi': {'enabled': None, 'boot_config': None, 'available': True},
        'audio': {'enabled': None, 'boot_config': None, 'available': True},
        'cpu_freq': {'current': None, 'min': 600, 'max': 1500, 'available': True},
        'estimated_savings_ma': 0
    }
    
    try:
        # Check Bluetooth
        bt_result = subprocess.run(
            ['systemctl', 'is-enabled', 'bluetooth'],
            capture_output=True, text=True, timeout=5
        )
        if bt_result.returncode == 0:
            status['bluetooth']['available'] = True
            status['bluetooth']['enabled'] = bt_result.stdout.strip() == 'enabled'
        
        # Check HDMI (from boot config)
        if BOOT_CONFIG_FILE and os.path.exists(BOOT_CONFIG_FILE):
            with open(BOOT_CONFIG_FILE, 'r') as f:
                content = f.read()
                # HDMI0 is always on by default unless explicitly disabled
                status['hdmi']['boot_config'] = not re.search(r'hdmi_blanking\s*=\s*2', content)
                # Audio disabled if dtparam=audio=off
                status['audio']['boot_config'] = not re.search(r'dtparam\s*=\s*audio\s*=\s*off', content)
                # Bluetooth disabled if dtoverlay=disable-bt
                status['bluetooth']['boot_config'] = not re.search(r'dtoverlay\s*=\s*disable-bt', content)
        
        # Get CPU frequency (for Pi 3B+ and 4)
        cpu_freq_path = '/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq'
        if os.path.exists(cpu_freq_path):
            try:
                with open(cpu_freq_path, 'r') as f:
                    freq_khz = int(f.read().strip())
                    status['cpu_freq']['current'] = freq_khz // 1000  # Convert to MHz
            except:
                pass
        
        # Calculate estimated energy savings (rough estimates in mA)
        savings = 0
        boot_config = get_boot_power_config()
        
        if boot_config.get('bluetooth_enabled') is False:
            savings += 20  # ~20 mA without BT
        if boot_config.get('hdmi_enabled') is False:
            savings += 40  # ~40 mA without HDMI
        if boot_config.get('audio_enabled') is False:
            savings += 10  # ~10 mA without audio
        if boot_config.get('wifi_enabled') is False:
            savings += 40  # ~40 mA without WiFi
        if boot_config.get('pwr_led_enabled') is False:
            savings += 5  # ~5 mA for PWR LED
        if boot_config.get('act_led_enabled') is False:
            savings += 3  # ~3 mA average for ACT LED (blinks)
        
        # CPU underclocking savings (very approximate)
        if status['cpu_freq']['current'] and status['cpu_freq']['current'] < 1200:
            underclocking_percent = (1200 - status['cpu_freq']['current']) / 1200
            savings += int(100 * underclocking_percent)  # Up to ~100 mA saved
        
        status['estimated_savings_ma'] = savings
        
    except Exception as e:
        print(f"Error getting power status: {e}")
    
    return status

# ============================================================================
# OPTIONAL SERVICES MANAGEMENT
# ============================================================================

# Services that can be safely disabled for power savings
OPTIONAL_SERVICES = {
    'modemmanager': {
        'unit': 'ModemManager.service',
        'description_key': 'ui.power.service.modemmanager_desc',
        'savings_ma': 5
    },
    'avahi': {
        'unit': 'avahi-daemon.service',
        'description_key': 'ui.power.service.avahi_desc',
        'savings_ma': 5,
        'warning_key': 'ui.power.service.avahi_warning'
    },
    'cloudinit': {
        'units': [
            'cloud-init-main.service',
            'cloud-init-network.service',
            'cloud-init.service',
            'cloud-init-local.service',
            'cloud-config.service',
            'cloud-final.service'
        ],
        'description_key': 'ui.power.service.cloudinit_desc',
        'savings_ma': 0
    },
    'serial': {
        'units': [
            'serial-getty@ttyAMA0.service',
            'serial-getty@ttyS0.service'
        ],
        'description_key': 'ui.power.service.serial_desc',
        'savings_ma': 2,
        'mask_on_disable': True
    },
    'tty1': {
        'unit': 'getty@tty1.service',
        'description_key': 'ui.power.service.tty1_desc',
        'savings_ma': 2
    },
    'udisks2': {
        'unit': 'udisks2.service',
        'description_key': 'ui.power.service.udisks2_desc',
        'savings_ma': 5
    }
}

def get_optional_service_status(service_key):
    """Get status of an optional service."""
    import subprocess
    
    if service_key not in OPTIONAL_SERVICES:
        return None
    
    service_info = OPTIONAL_SERVICES[service_key]
    
    try:
        if 'units' in service_info:
            # Check first unit for multi-unit services
            unit = service_info['units'][0]
        else:
            unit = service_info['unit']
        
        result = subprocess.run(
            ['systemctl', 'is-enabled', unit],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == 'enabled'
    except:
        return None

def get_all_services_status():
    """Get status of all optional services."""
    status = {}
    for key in OPTIONAL_SERVICES:
        enabled = get_optional_service_status(key)
        status[key] = {
            'enabled': enabled,
            'description': OPTIONAL_SERVICES[key]['description'],
            'savings_ma': OPTIONAL_SERVICES[key]['savings_ma'],
            'warning': OPTIONAL_SERVICES[key].get('warning')
        }
    return status

def set_service_state(service_key, enabled):
    """
    Enable or disable an optional service.
    
    Args:
        service_key: Key from OPTIONAL_SERVICES dict
        enabled: True to enable, False to disable
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if service_key not in OPTIONAL_SERVICES:
        return False, f"Unknown service: {service_key}"
    
    service_info = OPTIONAL_SERVICES[service_key]
    action = 'enable' if enabled else 'disable'
    
    try:
        # Handle services with multiple units
        if 'units' in service_info:
            existing_units = []
            for unit in service_info['units']:
                # Check if unit exists before trying to enable/disable
                check = subprocess.run(
                    ['systemctl', 'cat', unit],
                    capture_output=True, text=True, timeout=5
                )
                if check.returncode == 0:
                    existing_units.append(unit)
            
            if not existing_units:
                # No units exist, skip silently
                return True, f"Service {service_key} not installed, skipping"
            
            for unit in existing_units:
                if enabled:
                    if service_info.get('mask_on_disable'):
                        subprocess.run(['sudo', 'systemctl', 'unmask', unit],
                                       capture_output=True, text=True, timeout=10)
                    result = subprocess.run(
                        ['sudo', 'systemctl', 'enable', unit],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode != 0:
                        return False, f"Failed to enable {unit}: {result.stderr}"
                else:
                    if service_info.get('mask_on_disable'):
                        result = subprocess.run(
                            ['sudo', 'systemctl', 'mask', '--now', unit],
                            capture_output=True, text=True, timeout=10
                        )
                    else:
                        result = subprocess.run(
                            ['sudo', 'systemctl', 'disable', unit],
                            capture_output=True, text=True, timeout=10
                        )
                        if result.returncode == 0:
                            subprocess.run(['sudo', 'systemctl', 'stop', unit],
                                           capture_output=True, timeout=10)
                    if result.returncode != 0:
                        return False, f"Failed to disable {unit}: {result.stderr}"

            return True, f"Services {action}d"
        else:
            unit = service_info['unit']
            
            # Check if unit exists before trying to enable/disable
            check = subprocess.run(
                ['systemctl', 'cat', unit],
                capture_output=True, text=True, timeout=5
            )
            if check.returncode != 0:
                # Unit doesn't exist, skip silently
                return True, f"Service {unit} not installed, skipping"
            
            if enabled:
                if service_info.get('mask_on_disable'):
                    subprocess.run(['sudo', 'systemctl', 'unmask', unit],
                                   capture_output=True, text=True, timeout=10)
                result = subprocess.run(
                    ['sudo', 'systemctl', 'enable', unit],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    return True, f"Service {unit} enabled"
                return False, result.stderr or f"Failed to enable {unit}"

            if service_info.get('mask_on_disable'):
                result = subprocess.run(
                    ['sudo', 'systemctl', 'mask', '--now', unit],
                    capture_output=True, text=True, timeout=10
                )
            else:
                result = subprocess.run(
                    ['sudo', 'systemctl', 'disable', unit],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    subprocess.run(['sudo', 'systemctl', 'stop', unit],
                                   capture_output=True, timeout=10)

            if result.returncode == 0:
                return True, f"Service {unit} disabled"
            return False, result.stderr or f"Failed to disable {unit}"
                
    except Exception as e:
        return False, str(e)

def configure_boot_power_settings(bluetooth_enabled=True, hdmi_enabled=True, audio_enabled=True, 
                                   wifi_enabled=True, pwr_led_enabled=True, act_led_enabled=True, 
                                   camera_led_csi_enabled=True):
    """
    Configure power settings in boot config for persistence across reboots.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not BOOT_CONFIG_FILE:
        return False, _t('ui.power.boot_config_not_found')
    
    try:
        config_content = ""
        if os.path.exists(BOOT_CONFIG_FILE):
            with open(BOOT_CONFIG_FILE, 'r') as f:
                config_content = f.read()
        
        # List of settings to configure
        settings = []
        
        # Bluetooth
        if not bluetooth_enabled:
            if 'dtoverlay=disable-bt' not in config_content:
                settings.append('dtoverlay=disable-bt')
        else:
            config_content = config_content.replace('dtoverlay=disable-bt\n', '')
        
        # HDMI
        if not hdmi_enabled:
            if 'hdmi_blanking=2' not in config_content:
                settings.append('hdmi_blanking=2')
        else:
            config_content = config_content.replace('hdmi_blanking=2\n', '')
        
        # Audio
        if not audio_enabled:
            if 'dtparam=audio=off' not in config_content:
                settings.append('dtparam=audio=off')
            config_content = config_content.replace('dtparam=audio=on\n', '')
        else:
            config_content = config_content.replace('dtparam=audio=off\n', '')
        
        # WiFi
        if not wifi_enabled:
            if 'dtoverlay=disable-wifi' not in config_content:
                settings.append('dtoverlay=disable-wifi')
        else:
            config_content = config_content.replace('dtoverlay=disable-wifi\n', '')
        
        # PWR LED
        if not pwr_led_enabled:
            if 'dtparam=pwr_led_trigger=none' not in config_content:
                settings.append('dtparam=pwr_led_trigger=none')
        else:
            config_content = config_content.replace('dtparam=pwr_led_trigger=none\n', '')
        
        # ACT LED
        if not act_led_enabled:
            if 'dtparam=act_led_trigger=none' not in config_content:
                settings.append('dtparam=act_led_trigger=none')
        else:
            config_content = config_content.replace('dtparam=act_led_trigger=none\n', '')
        
        # Camera LED (CSI)
        if not camera_led_csi_enabled:
            if 'disable_camera_led=1' not in config_content:
                settings.append('disable_camera_led=1')
        else:
            config_content = config_content.replace('disable_camera_led=1\n', '')
        
        # Append new settings
        if settings:
            if not config_content.endswith('\n'):
                config_content += '\n'
            config_content += '\n'.join(settings) + '\n'
        
        # Write back
        with open(BOOT_CONFIG_FILE, 'w') as f:
            f.write(config_content)

        # Apply Bluetooth service state immediately (saves CPU if disabled)
        try:
            check = subprocess.run(
                ['systemctl', 'cat', 'bluetooth.service'],
                capture_output=True, text=True, timeout=5
            )
            if check.returncode == 0:
                if bluetooth_enabled:
                    subprocess.run(['sudo', 'systemctl', 'enable', '--now', 'bluetooth.service'],
                                   capture_output=True, timeout=10)
                else:
                    subprocess.run(['sudo', 'systemctl', 'disable', '--now', 'bluetooth.service'],
                                   capture_output=True, timeout=10)
        except Exception:
            pass
        
        return True, "Boot configuration updated"
        
    except Exception as e:
        return False, str(e)

def reboot_system(delay=0):
    """
    Schedule a system reboot.
    
    Args:
        delay: Delay in seconds before reboot
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        if delay > 0:
            # Use shutdown with delay in minutes
            subprocess.Popen(
                ['sudo', 'shutdown', '-r', f'+{max(1, delay // 60)}'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Use reboot command directly - fire and forget
            subprocess.Popen(
                ['sudo', 'reboot'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        return {
            'success': True,
            'message': f'System will reboot in {delay} seconds' if delay else 'Rebooting now...'
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

def shutdown_system(delay=0):
    """
    Schedule a system shutdown.
    
    Args:
        delay: Delay in seconds before shutdown
    
    Returns:
        dict: {success: bool, message: str}
    """
    try:
        if delay > 0:
            subprocess.Popen(
                ['sudo', 'shutdown', f'+{max(1, delay // 60)}'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Use poweroff command directly - fire and forget
            subprocess.Popen(
                ['sudo', 'poweroff'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        
        return {
            'success': True,
            'message': f'System will shutdown in {delay} seconds' if delay else 'Shutting down now...'
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

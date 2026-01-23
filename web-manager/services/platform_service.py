# -*- coding: utf-8 -*-
"""
Platform Service - OS detection and command execution utilities
Version: 2.30.1
"""

import subprocess
import platform as py_platform
import os

# ============================================================================
# PLATFORM DETECTION
# ============================================================================

def detect_platform():
    """Detect if running on Raspberry Pi and which model."""
    is_pi = False
    model = "Unknown"
    pi_version = 0
    
    # Check for Raspberry Pi
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model_info = f.read().lower()
            is_pi = 'raspberry pi' in model_info
            model = model_info.strip().rstrip('\x00')
            
            # Detect version
            if 'raspberry pi 5' in model_info:
                pi_version = 5
            elif 'raspberry pi 4' in model_info:
                pi_version = 4
            elif 'raspberry pi 3' in model_info:
                pi_version = 3
            elif 'raspberry pi 2' in model_info:
                pi_version = 2
            elif 'raspberry pi' in model_info:
                pi_version = 1
    except FileNotFoundError:
        pass
    
    # Check architecture
    arch = py_platform.machine()
    is_64bit = arch in ('aarch64', 'arm64', 'x86_64')
    
    # Check for vcgencmd (Raspberry Pi tools)
    has_vcgencmd = os.path.exists('/usr/bin/vcgencmd')
    
    # Check for LED control (available on Pi with accessible LED sysfs)
    has_led_control = (
        os.path.exists('/sys/class/leds/PWR') or 
        os.path.exists('/sys/class/leds/ACT') or
        os.path.exists('/sys/class/leds/led0') or
        os.path.exists('/sys/class/leds/led1')
    )
    
    # Check for libcamera/rpicam (Trixie uses rpicam-*, older uses libcamera-*)
    has_libcamera = (
        os.path.exists('/usr/bin/rpicam-hello') or    # Trixie/Bookworm
        os.path.exists('/usr/bin/rpicam-vid') or      # Trixie/Bookworm
        os.path.exists('/usr/bin/libcamera-hello') or # Legacy
        os.path.exists('/usr/bin/libcamera-vid')      # Legacy
    )
    
    # Find boot config file (Trixie uses /boot/firmware/)
    boot_config = None
    boot_config_paths = [
        '/boot/firmware/config.txt',  # Raspberry Pi OS Trixie/Bookworm
        '/boot/config.txt'             # Older Raspberry Pi OS
    ]
    for path in boot_config_paths:
        if os.path.exists(path):
            boot_config = path
            break
    
    return {
        'is_raspberry_pi': is_pi,
        'model': model,
        'pi_version': pi_version,
        'architecture': arch,
        'is_64bit': is_64bit,
        'system': py_platform.system(),
        'release': py_platform.release(),
        # Additional Pi features
        'has_vcgencmd': has_vcgencmd,
        'has_led_control': has_led_control,
        'has_libcamera': has_libcamera,
        'boot_config': boot_config
    }

# Detect platform at module load
PLATFORM = detect_platform()

def is_raspberry_pi():
    """Check if running on a Raspberry Pi."""
    return PLATFORM['is_raspberry_pi']

# ============================================================================
# COMMAND EXECUTION UTILITIES
# ============================================================================

def run_command(cmd, shell=True, timeout=30, capture_output=True):
    """
    Execute a shell command and return the result.
    
    Args:
        cmd: Command to execute (string or list)
        shell: Use shell execution (default: True)
        timeout: Command timeout in seconds (default: 30)
        capture_output: Capture stdout/stderr (default: True)
    
    Returns:
        dict with keys: success, stdout, stderr, returncode
    """
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=capture_output,
            text=True,
            timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip() if result.stdout else '',
            'stderr': result.stderr.strip() if result.stderr else '',
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': f'Command timed out after {timeout}s',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

def run_command_with_timeout(cmd, timeout=30, shell=True):
    """
    Execute a command with a specific timeout.
    Alias for run_command for backward compatibility.
    
    Args:
        cmd: Command to execute
        timeout: Timeout in seconds
        shell: Use shell execution
    
    Returns:
        dict with keys: success, stdout, stderr, returncode
    """
    return run_command(cmd, shell=shell, timeout=timeout)

def run_command_async(cmd, shell=True):
    """
    Start a command asynchronously without waiting for completion.
    
    Args:
        cmd: Command to execute
        shell: Use shell execution
    
    Returns:
        subprocess.Popen object or None on error
    """
    try:
        process = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return process
    except Exception as e:
        print(f"Error starting async command: {e}")
        return None

def check_command_exists(cmd_name):
    """
    Check if a command exists in PATH.
    
    Args:
        cmd_name: Name of the command to check
    
    Returns:
        bool: True if command exists
    """
    result = run_command(f"which {cmd_name}", timeout=5)
    return result['success'] and result['stdout']

def get_service_path(service_name):
    """
    Get the path to a systemd service file.
    
    Args:
        service_name: Name of the service
    
    Returns:
        str: Path to service file or None
    """
    paths = [
        f"/etc/systemd/system/{service_name}.service",
        f"/lib/systemd/system/{service_name}.service",
        f"/usr/lib/systemd/system/{service_name}.service"
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None

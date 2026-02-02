# -*- coding: utf-8 -*-
"""
Services module - Business logic separated from Flask routes
Version: 2.30.8

Changes in 2.30.8:
- Added get_ssh_keys_status, ensure_ssh_keys_configured for SSH key management

Changes in 2.30.7:
- Added csi_camera_service lazy import for Picamera2 CSI camera controls

Changes in 2.30.6:
- Added detect_camera_type, get_camera_info, get_libcamera_formats exports
"""

from .platform_service import (
    run_command,
    run_command_with_timeout,
    is_raspberry_pi,
    PLATFORM
)

from .config_service import (
    load_config,
    save_config,
    get_service_status,
    control_service,
    get_system_info
)

from .camera_service import (
    find_camera_device,
    detect_camera_type,
    get_camera_info,
    get_camera_controls,
    set_camera_control,
    get_all_camera_controls,
    reset_camera_control,
    auto_camera_controls,
    focus_oneshot,
    load_camera_profiles,
    save_camera_profiles,
    apply_camera_profile,
    capture_camera_profile,
    get_camera_formats,
    get_libcamera_formats,
    get_hw_encoder_capabilities
)

from .network_service import (
    get_network_interfaces,
    get_interface_details,
    configure_static_ip,
    configure_dhcp,
    set_interface_priority,
    get_wifi_networks,
    get_current_wifi,
    connect_wifi,
    create_access_point,
    stop_access_point,
    get_ap_status,
    get_ethernet_status,
    get_wifi_manual_override,
    set_wifi_manual_override,
    manage_wifi_based_on_ethernet,
    manage_network_failover,
    get_interface_connection_status,
    disconnect_interface,
    connect_interface,
    get_wlan0_status,
    clone_wifi_config,
    auto_configure_wifi_interface
)

from .power_service import (
    get_power_status,
    get_full_power_status,
    get_boot_power_config,
    get_all_services_status,
    configure_power_boot,
    configure_hdmi,
    get_led_status,
    set_led_state,
    configure_leds_boot,
    get_led_boot_config,
    save_led_boot_config,
    get_gpu_mem,
    set_gpu_mem
)

from .recording_service import (
    get_recordings_list,
    get_recording_info,
    delete_recording,
    get_disk_usage
)

from .meeting_service import (
    load_meeting_config,
    save_meeting_config,
    get_meeting_status,
    send_heartbeat,
    get_heartbeat_payload,
    meeting_heartbeat_loop,
    start_heartbeat_thread,
    stop_heartbeat_thread,
    get_meeting_device_info,
    request_tunnel,
    update_provision,
    get_device_availability,
    enable_meeting_service,
    disable_meeting_service,
    validate_credentials,
    provision_device,
    master_reset,
    init_meeting_service,
    is_service_declared,
    is_debug_enabled,
    trigger_immediate_heartbeat,
    has_internet_connectivity,
    # SSH key management (per Meeting API integration guide)
    get_ssh_hostkey,
    sync_ssh_hostkey,
    generate_device_ssh_key,
    publish_device_ssh_key,
    get_device_ssh_pubkey,
    full_ssh_setup,
    get_meeting_ssh_pubkey,
    install_meeting_ssh_pubkey,
    get_ssh_keys_status,
    ensure_ssh_keys_configured,
    # Services declaration
    get_declared_services,
    get_meeting_authorized_services
)

from .system_service import (
    get_diagnostic_info,
    get_legacy_diagnostic_info,
    get_recent_logs,
    check_for_updates,
    perform_update,
    get_apt_updates,
    perform_apt_upgrade
)

from .watchdog_service import (
    check_rtsp_service_health,
    restart_rtsp_service,
    rtsp_watchdog_loop,
    wifi_failover_watchdog_loop
)

# Media cache service (lazy-loaded to avoid circular imports)
from . import media_cache_service

# CSI camera service (lazy-loaded for Picamera2 controls)
from . import csi_camera_service

__all__ = [
    # Platform
    'run_command', 'run_command_with_timeout', 'is_raspberry_pi', 'PLATFORM',
    # Config
    'load_config', 'save_config', 'get_service_status', 'control_service', 'get_system_info',
    # Camera
    'find_camera_device', 'get_camera_controls', 'set_camera_control',
    'get_all_camera_controls', 'reset_camera_control', 'auto_camera_controls',
    'focus_oneshot', 'load_camera_profiles', 'save_camera_profiles',
    'apply_camera_profile', 'capture_camera_profile', 'get_camera_formats',
    'get_hw_encoder_capabilities',
    # Network
    'get_network_interfaces', 'get_interface_details', 'configure_static_ip',
    'configure_dhcp', 'set_interface_priority', 'get_wifi_networks',
    'get_current_wifi', 'connect_wifi', 'create_access_point',
    'stop_access_point', 'get_ap_status',
    'get_ethernet_status', 'get_wifi_manual_override', 'set_wifi_manual_override',
    'manage_wifi_based_on_ethernet', 'manage_network_failover',
    'get_interface_connection_status', 'disconnect_interface', 'connect_interface',
    'get_wlan0_status',
    # Power
    'get_power_status', 'get_full_power_status', 'get_boot_power_config',
    'get_all_services_status', 'configure_power_boot', 'configure_hdmi',
    'get_led_status', 'set_led_state', 'configure_leds_boot',
    'get_led_boot_config', 'save_led_boot_config',
    'get_gpu_mem', 'set_gpu_mem',
    # Recording
    'get_recordings_list', 'get_recording_info', 'delete_recording', 'get_disk_usage',
    # Media Cache
    'media_cache_service',
    # CSI Camera (Picamera2)
    'csi_camera_service',
    # Meeting
    'meeting_heartbeat_loop', 'get_meeting_device_info', 'request_tunnel', 'update_provision',
    'trigger_immediate_heartbeat', 'has_internet_connectivity',
    # System
    'get_diagnostic_info', 'get_recent_logs', 'check_for_updates',
    'perform_update', 'get_apt_updates', 'perform_apt_upgrade',
    # Watchdog
    'check_rtsp_service_health', 'restart_rtsp_service',
    'rtsp_watchdog_loop', 'wifi_failover_watchdog_loop'
]

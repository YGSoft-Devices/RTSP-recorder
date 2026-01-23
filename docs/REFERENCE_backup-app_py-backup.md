# Référence complète — `backup-app.py-backup`

Généré le: `2026-01-17T22:41:53+01:00`

Source: `web-manager/backup-app.py-backup`

- Lignes: **8349**
- Octets: **313031**
- SHA-256: `651351a0618eca3c937600ff9f3f2841c19716466ca6c1455a0f13a944e38e5a`

## Table des matières

- [1) Endpoints HTTP (`@app.route`, `@app.get`, ...)](#1-endpoints-http-approute-appget-)
- [2) Routes via `app.add_url_rule`](#2-routes-via-appadd_url_rule)
- [3) Hooks Flask (before/after/error/…)](#3-hooks-flask-beforeaftererror)
- [4) Fonctions (toutes, y compris imbriquées)](#4-fonctions-toutes-y-compris-imbriquees)
- [5) Classes et méthodes](#5-classes-et-methodes)

---

## 1) Endpoints HTTP (`@app.route`, `@app.get`, ...)

### Index (table)

| Méthodes | Path(s) | Fonction | Ligne | Résumé |
|---|---|---|---:|---|
| `GET` | `/` | `index` | 3739 | Main dashboard page. |
| `GET` | `/api/config` | `api_get_config` | 3776 | API endpoint to get current configuration. |
| `POST` | `/api/config` | `api_save_config` | 3787 | API endpoint to save configuration. |
| `GET` | `/api/status` | `api_get_status` | 3807 | API endpoint to get service status. |
| `POST` | `/api/service/<action>` | `api_service_control` | 3819 | API endpoint to control the service. |
| `GET` | `/api/logs` | `api_get_logs` | 3830 | API endpoint to get recent logs. |
| `GET` | `/api/logs/stream` | `api_stream_logs` | 3842 | API endpoint for real-time log streaming via SSE. |
| `POST` | `/api/logs/clean` | `api_clean_logs` | 3856 | API endpoint to clean/truncate log files. |
| `GET` | `/api/diagnostic` | `api_diagnostic` | 3925 | API endpoint to get diagnostic information. |
| `GET` | `/api/recordings` | `api_get_recordings` | 3935 | API endpoint to list recordings. |
| `GET` | `/api/recordings/list` | `api_list_recordings` | 4001 | API endpoint to list recordings with pagination support. |
| `POST` | `/api/recordings/delete` | `api_delete_recordings` | 4158 | API endpoint to delete recordings. |
| `POST` | `/api/recordings/lock` | `api_lock_recordings` | 4210 | API endpoint to lock/unlock recordings (prevent deletion). |
| `GET` | `/api/recordings/download/<filename>` | `api_download_recording` | 4251 | API endpoint to download a recording file. |
| `GET` | `/api/recordings/stream/<filename>` | `api_stream_recording` | 4287 | API endpoint to stream a recording for playback. |
| `GET` | `/api/recordings/info/<filename>` | `api_recording_info` | 4375 | API endpoint to get detailed info about a recording. |
| `GET` | `/api/recordings/thumbnail/<filename>` | `api_recording_thumbnail` | 4473 | API endpoint to get or generate a thumbnail for a recording. |
| `POST` | `/api/recordings/thumbnails/generate` | `api_generate_thumbnails` | 4517 | API endpoint to batch generate thumbnails for all recordings. |
| `POST` | `/api/recordings/thumbnails/clean` | `api_clean_thumbnails` | 4561 | API endpoint to clean orphaned thumbnails. |
| `GET` | `/api/detect/cameras` | `api_detect_cameras` | 4590 | API endpoint to detect available cameras. |
| `GET` | `/api/detect/audio` | `api_detect_audio` | 4629 | API endpoint to detect available audio devices. |
| `GET` | `/api/camera/controls` | `api_camera_controls` | 4656 | API endpoint to get camera controls. |
| `GET` | `/api/camera/autofocus` | `api_camera_autofocus_get` | 4670 | API endpoint to get autofocus status. |
| `POST` | `/api/camera/autofocus` | `api_camera_autofocus_set` | 4678 | API endpoint to set autofocus (with persistence). |
| `POST` | `/api/camera/focus` | `api_camera_focus_set` | 4698 | API endpoint to set manual focus. |
| `POST` | `/api/camera/control` | `api_camera_control_set` | 4720 | API endpoint to set any camera control. |
| `GET` | `/api/camera/formats` | `api_camera_formats` | 4743 | API endpoint to get available camera formats and resolutions. |
| `POST` | `/api/camera/oneshot-focus` | `api_camera_oneshot_focus` | 4765 | API endpoint to trigger one-shot autofocus. |
| `GET` | `/api/camera/all-controls` | `api_camera_all_controls` | 4781 | API endpoint to get ALL camera controls for advanced settings. |
| `POST` | `/api/camera/controls/set-multiple` | `api_camera_set_multiple_controls` | 4794 | API endpoint to set multiple camera controls at once. |
| `GET` | `/api/camera/profiles` | `api_camera_profiles_get` | 4826 | Get all camera profiles. |
| `POST` | `/api/camera/profiles` | `api_camera_profiles_save` | 4855 | Save all camera profiles. |
| `GET` | `/api/camera/profiles/<profile_name>` | `api_camera_profile_get` | 4874 | Get a specific camera profile. |
| `PUT` | `/api/camera/profiles/<profile_name>` | `api_camera_profile_update` | 4889 | Update or create a camera profile. |
| `DELETE` | `/api/camera/profiles/<profile_name>` | `api_camera_profile_delete` | 4904 | Delete a camera profile. |
| `POST` | `/api/camera/profiles/<profile_name>/apply` | `api_camera_profile_apply` | 4921 | Apply a camera profile immediately. |
| `POST` | `/api/camera/profiles/<profile_name>/capture` | `api_camera_profile_capture` | 4939 | Capture current camera settings into a profile. |
| `POST` | `/api/camera/profiles/scheduler/start` | `api_camera_profiles_scheduler_start` | 4981 | Start the camera profiles scheduler. |
| `POST` | `/api/camera/profiles/scheduler/stop` | `api_camera_profiles_scheduler_stop` | 4988 | Stop the camera profiles scheduler. |
| `GET` | `/api/camera/profiles/scheduler/status` | `api_camera_profiles_scheduler_status` | 4995 | Get camera profiles scheduler status. |
| `GET` | `/api/platform` | `api_platform` | 5027 | API endpoint to get platform information. |
| `GET` | `/api/video/preview/stream` | `api_video_preview_stream` | 5127 | Stream live MJPEG preview of the camera. |
| `GET` | `/api/video/preview/snapshot` | `api_video_preview_snapshot` | 5163 | Capture a single snapshot from the camera or RTSP stream. |
| `GET` | `/api/video/preview/status` | `api_video_preview_status` | 5221 | Check if preview is available and which source will be used. |
| `GET` | `/api/wifi/scan` | `api_wifi_scan` | 5251 | API endpoint to scan for WiFi networks. |
| `GET` | `/api/wifi/status` | `api_wifi_status` | 5258 | API endpoint to get WiFi status. |
| `POST` | `/api/wifi/connect` | `api_wifi_connect` | 5270 | API endpoint to connect to WiFi. |
| `POST` | `/api/wifi/disconnect` | `api_wifi_disconnect` | 5291 | API endpoint to disconnect from WiFi. |
| `GET` | `/api/network/interfaces` | `api_network_interfaces` | 5314 | API endpoint to get all network interfaces. |
| `GET` | `/api/network/config` | `api_network_config` | 5326 | API endpoint to get network configuration. |
| `POST` | `/api/network/priority` | `api_network_priority` | 5333 | API endpoint to set interface priority order. |
| `POST` | `/api/network/static` | `api_network_static` | 5349 | API endpoint to configure static IP. |
| `POST` | `/api/network/dhcp` | `api_network_dhcp` | 5368 | API endpoint to configure DHCP. |
| `GET` | `/api/wifi/failover/status` | `api_wifi_failover_status` | 5388 | Get WiFi failover status. |
| `GET` | `/api/wifi/failover/config` | `api_wifi_failover_config_get` | 5395 | Get WiFi failover configuration. |
| `POST` | `/api/wifi/failover/config` | `api_wifi_failover_config_set` | 5402 | Update WiFi failover configuration. |
| `POST` | `/api/wifi/failover/apply` | `api_wifi_failover_apply` | 5437 | Apply WiFi failover - connect the appropriate interface. |
| `GET` | `/api/wifi/failover/interfaces` | `api_wifi_failover_interfaces` | 5450 | Get all WiFi interfaces with their status. |
| `POST` | `/api/wifi/failover/disconnect` | `api_wifi_failover_disconnect` | 5457 | Disconnect a specific WiFi interface. |
| `GET` | `/api/network/ap/status` | `api_ap_status` | 5717 | Get Access Point status. |
| `POST` | `/api/network/ap/config` | `api_ap_config` | 5729 | Configure Access Point settings. |
| `POST` | `/api/network/ap/start` | `api_ap_start` | 5785 | Start Access Point. |
| `POST` | `/api/network/ap/stop` | `api_ap_stop` | 5795 | Stop Access Point. |
| `GET` | `/api/network/wifi/override` | `api_wifi_override_get` | 5902 | Get WiFi manual override status. |
| `POST` | `/api/network/wifi/override` | `api_wifi_override_set` | 5916 | Set WiFi manual override. |
| `GET` | `/api/wifi/failover/watchdog` | `api_wifi_failover_watchdog_status` | 5936 | Get WiFi failover watchdog status. |
| `POST` | `/api/wifi/failover/watchdog` | `api_wifi_failover_watchdog_control` | 5949 | Start or stop the WiFi failover watchdog. |
| `GET` | `/api/rtsp/watchdog/status` | `api_rtsp_watchdog_status` | 5972 | Get RTSP watchdog status including camera health. |
| `POST` | `/api/rtsp/watchdog` | `api_rtsp_watchdog_control` | 5999 | Control RTSP watchdog. |
| `GET` | `/api/leds/status` | `api_leds_status` | 6022 | API endpoint to get LED status. |
| `POST` | `/api/leds/set` | `api_leds_set` | 6029 | API endpoint to set LED state. |
| `GET` | `/api/leds/boot-config` | `api_leds_boot_config` | 6070 | API endpoint to get LED boot configuration. |
| `GET` | `/api/gpu/mem` | `api_gpu_mem_get` | 6081 | API endpoint to get GPU memory. |
| `POST` | `/api/gpu/mem` | `api_gpu_mem_set` | 6088 | API endpoint to set GPU memory. |
| `GET` | `/api/power/status` | `api_power_status` | 6105 | API endpoint to get power/energy status of all components. |
| `POST` | `/api/power/bluetooth` | `api_power_bluetooth` | 6119 | API endpoint to control Bluetooth. |
| `POST` | `/api/power/hdmi` | `api_power_hdmi` | 6152 | API endpoint to control HDMI. |
| `POST` | `/api/power/audio` | `api_power_audio` | 6185 | API endpoint to control Audio. |
| `POST` | `/api/power/cpu-freq` | `api_power_cpu_freq` | 6218 | API endpoint to control CPU frequency. |
| `GET` | `/api/power/boot-config` | `api_power_boot_config` | 6236 | API endpoint to get power boot configuration. |
| `POST` | `/api/power/apply-all` | `api_power_apply_all` | 6249 | API endpoint to apply all power settings at once. |
| `POST` | `/api/system/reboot` | `api_system_reboot` | 6350 | API endpoint to reboot the system. |
| `GET` | `/api/system/ntp` | `api_ntp_get` | 6366 | Get NTP configuration and status. |
| `POST` | `/api/system/ntp` | `api_ntp_set` | 6435 | Set NTP server configuration. |
| `POST` | `/api/system/ntp/sync` | `api_ntp_sync` | 6469 | Force NTP synchronization. |
| `GET` | `/api/system/update/check` | `api_update_check` | 6508 | Check for available updates from GitHub. |
| `POST` | `/api/system/update/perform` | `api_update_perform` | 6566 | Perform system update from GitHub. |
| `GET` | `/api/debug/firmware/check` | `api_debug_firmware_check` | 6722 | Check for Raspberry Pi firmware updates. |
| `POST` | `/api/debug/firmware/update` | `api_debug_firmware_update` | 6836 | Apply Raspberry Pi firmware update. |
| `POST` | `/api/debug/apt/update` | `api_debug_apt_update` | 6905 | Run apt update to refresh package lists. |
| `GET` | `/api/debug/apt/upgradable` | `api_debug_apt_upgradable` | 6940 | List packages that can be upgraded. |
| `POST` | `/api/debug/apt/upgrade` | `api_debug_apt_upgrade` | 6979 | Run apt upgrade to update all packages. |
| `GET` | `/api/debug/system/uptime` | `api_debug_system_uptime` | 7027 | Get system uptime. |
| `POST` | `/api/meeting/test` | `api_meeting_test` | 7423 | Test Meeting API connection and start heartbeat if successful. |
| `POST` | `/api/meeting/heartbeat` | `api_meeting_heartbeat` | 7468 | Send heartbeat to Meeting API (manual trigger). |
| `GET` | `/api/meeting/availability` | `api_meeting_availability` | 7493 | Check device availability on Meeting API. |
| `GET` | `/api/meeting/device` | `api_meeting_device_info` | 7511 | Get device info from Meeting API. |
| `POST` | `/api/meeting/tunnel` | `api_meeting_request_tunnel` | 7556 | Request a tunnel from Meeting API. |
| `GET` | `/api/meeting/status` | `api_meeting_status` | 7579 | Get Meeting integration status including heartbeat state. |
| `POST` | `/api/meeting/validate` | `api_meeting_validate` | 7635 | Validate Meeting credentials without provisioning - just checks if valid. |
| `POST` | `/api/meeting/provision` | `api_meeting_provision` | 7689 | Provision the device with Meeting API - validates credentials and burns a token. |
| `POST` | `/api/meeting/master-reset` | `api_meeting_master_reset` | 7808 | Reset Meeting configuration (requires master code). |
| `GET` | `/api/onvif/status` | `api_onvif_status` | 8119 | Get ONVIF service status and configuration. |
| `GET, POST` | `/api/onvif/config` | `api_onvif_config` | 8163 | Get or set ONVIF configuration. |
| `POST` | `/api/onvif/restart` | `api_onvif_restart` | 8217 | Restart ONVIF service. |

### Détails par handler

#### `index` (ligne 3739)

- Signature: `index()`
- Doc: Main dashboard page.
- Méthodes: `GET`
- Path(s): `/`
- Décorateur: `app.route('/')`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_get_config` (ligne 3776)

- Signature: `api_get_config()`
- Doc: API endpoint to get current configuration.
- Méthodes: `GET`
- Path(s): `/api/config`
- Décorateur: `app.route('/api/config', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_save_config` (ligne 3787)

- Signature: `api_save_config()`
- Doc: API endpoint to save configuration.
- Méthodes: `POST`
- Path(s): `/api/config`
- Décorateur: `app.route('/api/config', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_get_status` (ligne 3807)

- Signature: `api_get_status()`
- Doc: API endpoint to get service status.
- Méthodes: `GET`
- Path(s): `/api/status`
- Décorateur: `app.route('/api/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_service_control` (ligne 3819)

- Signature: `api_service_control(action)`
- Doc: API endpoint to control the service.
- Méthodes: `POST`
- Path(s): `/api/service/<action>`
- Décorateur: `app.route('/api/service/<action>', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_get_logs` (ligne 3830)

- Signature: `api_get_logs()`
- Doc: API endpoint to get recent logs.
- Méthodes: `GET`
- Path(s): `/api/logs`
- Décorateur: `app.route('/api/logs', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): `lines`, `source`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_stream_logs` (ligne 3842)

- Signature: `api_stream_logs()`
- Doc: API endpoint for real-time log streaming via SSE.
- Méthodes: `GET`
- Path(s): `/api/logs/stream`
- Décorateur: `app.route('/api/logs/stream')`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_clean_logs` (ligne 3856)

- Signature: `api_clean_logs()`
- Doc: API endpoint to clean/truncate log files.
- Méthodes: `POST`
- Path(s): `/api/logs/clean`
- Décorateur: `app.route('/api/logs/clean', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_diagnostic` (ligne 3925)

- Signature: `api_diagnostic()`
- Doc: API endpoint to get diagnostic information.
- Méthodes: `GET`
- Path(s): `/api/diagnostic`
- Décorateur: `app.route('/api/diagnostic', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_get_recordings` (ligne 3935)

- Signature: `api_get_recordings()`
- Doc: API endpoint to list recordings.
- Méthodes: `GET`
- Path(s): `/api/recordings`
- Décorateur: `app.route('/api/recordings', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_list_recordings` (ligne 4001)

- Signature: `api_list_recordings()`
- Doc: API endpoint to list recordings with pagination support.
- Méthodes: `GET`
- Path(s): `/api/recordings/list`
- Décorateur: `app.route('/api/recordings/list', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): `filter`, `page`, `per_page`, `search`, `sort`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_delete_recordings` (ligne 4158)

- Signature: `api_delete_recordings()`
- Doc: API endpoint to delete recordings.
- Méthodes: `POST`
- Path(s): `/api/recordings/delete`
- Décorateur: `app.route('/api/recordings/delete', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_lock_recordings` (ligne 4210)

- Signature: `api_lock_recordings()`
- Doc: API endpoint to lock/unlock recordings (prevent deletion).
- Méthodes: `POST`
- Path(s): `/api/recordings/lock`
- Décorateur: `app.route('/api/recordings/lock', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_download_recording` (ligne 4251)

- Signature: `api_download_recording(filename)`
- Doc: API endpoint to download a recording file.
- Méthodes: `GET`
- Path(s): `/api/recordings/download/<filename>`
- Décorateur: `app.route('/api/recordings/download/<filename>', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_stream_recording` (ligne 4287)

- Signature: `api_stream_recording(filename)`
- Doc: API endpoint to stream a recording for playback.
- Méthodes: `GET`
- Path(s): `/api/recordings/stream/<filename>`
- Décorateur: `app.route('/api/recordings/stream/<filename>', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): `Range`
  - Files (`request.files`): _aucun détecté_

#### `api_recording_info` (ligne 4375)

- Signature: `api_recording_info(filename)`
- Doc: API endpoint to get detailed info about a recording.
- Méthodes: `GET`
- Path(s): `/api/recordings/info/<filename>`
- Décorateur: `app.route('/api/recordings/info/<filename>', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_recording_thumbnail` (ligne 4473)

- Signature: `api_recording_thumbnail(filename)`
- Doc: API endpoint to get or generate a thumbnail for a recording.
- Méthodes: `GET`
- Path(s): `/api/recordings/thumbnail/<filename>`
- Décorateur: `app.route('/api/recordings/thumbnail/<filename>', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_generate_thumbnails` (ligne 4517)

- Signature: `api_generate_thumbnails()`
- Doc: API endpoint to batch generate thumbnails for all recordings.
- Méthodes: `POST`
- Path(s): `/api/recordings/thumbnails/generate`
- Décorateur: `app.route('/api/recordings/thumbnails/generate', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_clean_thumbnails` (ligne 4561)

- Signature: `api_clean_thumbnails()`
- Doc: API endpoint to clean orphaned thumbnails.
- Méthodes: `POST`
- Path(s): `/api/recordings/thumbnails/clean`
- Décorateur: `app.route('/api/recordings/thumbnails/clean', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_detect_cameras` (ligne 4590)

- Signature: `api_detect_cameras()`
- Doc: API endpoint to detect available cameras.
- Méthodes: `GET`
- Path(s): `/api/detect/cameras`
- Décorateur: `app.route('/api/detect/cameras', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_detect_audio` (ligne 4629)

- Signature: `api_detect_audio()`
- Doc: API endpoint to detect available audio devices.
- Méthodes: `GET`
- Path(s): `/api/detect/audio`
- Décorateur: `app.route('/api/detect/audio', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_controls` (ligne 4656)

- Signature: `api_camera_controls()`
- Doc: API endpoint to get camera controls.
- Méthodes: `GET`
- Path(s): `/api/camera/controls`
- Décorateur: `app.route('/api/camera/controls', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): `device`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_autofocus_get` (ligne 4670)

- Signature: `api_camera_autofocus_get()`
- Doc: API endpoint to get autofocus status.
- Méthodes: `GET`
- Path(s): `/api/camera/autofocus`
- Décorateur: `app.route('/api/camera/autofocus', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): `device`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_autofocus_set` (ligne 4678)

- Signature: `api_camera_autofocus_set()`
- Doc: API endpoint to set autofocus (with persistence).
- Méthodes: `POST`
- Path(s): `/api/camera/autofocus`
- Décorateur: `app.route('/api/camera/autofocus', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_focus_set` (ligne 4698)

- Signature: `api_camera_focus_set()`
- Doc: API endpoint to set manual focus.
- Méthodes: `POST`
- Path(s): `/api/camera/focus`
- Décorateur: `app.route('/api/camera/focus', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_control_set` (ligne 4720)

- Signature: `api_camera_control_set()`
- Doc: API endpoint to set any camera control.
- Méthodes: `POST`
- Path(s): `/api/camera/control`
- Décorateur: `app.route('/api/camera/control', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_formats` (ligne 4743)

- Signature: `api_camera_formats()`
- Doc: API endpoint to get available camera formats and resolutions.
- Méthodes: `GET`
- Path(s): `/api/camera/formats`
- Décorateur: `app.route('/api/camera/formats', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): `device`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_oneshot_focus` (ligne 4765)

- Signature: `api_camera_oneshot_focus()`
- Doc: API endpoint to trigger one-shot autofocus.
- Méthodes: `POST`
- Path(s): `/api/camera/oneshot-focus`
- Décorateur: `app.route('/api/camera/oneshot-focus', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_all_controls` (ligne 4781)

- Signature: `api_camera_all_controls()`
- Doc: API endpoint to get ALL camera controls for advanced settings.
- Méthodes: `GET`
- Path(s): `/api/camera/all-controls`
- Décorateur: `app.route('/api/camera/all-controls', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): `device`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_set_multiple_controls` (ligne 4794)

- Signature: `api_camera_set_multiple_controls()`
- Doc: API endpoint to set multiple camera controls at once.
- Méthodes: `POST`
- Path(s): `/api/camera/controls/set-multiple`
- Décorateur: `app.route('/api/camera/controls/set-multiple', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profiles_get` (ligne 4826)

- Signature: `api_camera_profiles_get()`
- Doc: Get all camera profiles.
- Méthodes: `GET`
- Path(s): `/api/camera/profiles`
- Décorateur: `app.route('/api/camera/profiles', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profiles_save` (ligne 4855)

- Signature: `api_camera_profiles_save()`
- Doc: Save all camera profiles.
- Méthodes: `POST`
- Path(s): `/api/camera/profiles`
- Décorateur: `app.route('/api/camera/profiles', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profile_get` (ligne 4874)

- Signature: `api_camera_profile_get(profile_name)`
- Doc: Get a specific camera profile.
- Méthodes: `GET`
- Path(s): `/api/camera/profiles/<profile_name>`
- Décorateur: `app.route('/api/camera/profiles/<profile_name>', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profile_update` (ligne 4889)

- Signature: `api_camera_profile_update(profile_name)`
- Doc: Update or create a camera profile.
- Méthodes: `PUT`
- Path(s): `/api/camera/profiles/<profile_name>`
- Décorateur: `app.route('/api/camera/profiles/<profile_name>', methods=['PUT'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profile_delete` (ligne 4904)

- Signature: `api_camera_profile_delete(profile_name)`
- Doc: Delete a camera profile.
- Méthodes: `DELETE`
- Path(s): `/api/camera/profiles/<profile_name>`
- Décorateur: `app.route('/api/camera/profiles/<profile_name>', methods=['DELETE'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profile_apply` (ligne 4921)

- Signature: `api_camera_profile_apply(profile_name)`
- Doc: Apply a camera profile immediately.
- Méthodes: `POST`
- Path(s): `/api/camera/profiles/<profile_name>/apply`
- Décorateur: `app.route('/api/camera/profiles/<profile_name>/apply', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profile_capture` (ligne 4939)

- Signature: `api_camera_profile_capture(profile_name)`
- Doc: Capture current camera settings into a profile.
- Méthodes: `POST`
- Path(s): `/api/camera/profiles/<profile_name>/capture`
- Décorateur: `app.route('/api/camera/profiles/<profile_name>/capture', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profiles_scheduler_start` (ligne 4981)

- Signature: `api_camera_profiles_scheduler_start()`
- Doc: Start the camera profiles scheduler.
- Méthodes: `POST`
- Path(s): `/api/camera/profiles/scheduler/start`
- Décorateur: `app.route('/api/camera/profiles/scheduler/start', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profiles_scheduler_stop` (ligne 4988)

- Signature: `api_camera_profiles_scheduler_stop()`
- Doc: Stop the camera profiles scheduler.
- Méthodes: `POST`
- Path(s): `/api/camera/profiles/scheduler/stop`
- Décorateur: `app.route('/api/camera/profiles/scheduler/stop', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_camera_profiles_scheduler_status` (ligne 4995)

- Signature: `api_camera_profiles_scheduler_status()`
- Doc: Get camera profiles scheduler status.
- Méthodes: `GET`
- Path(s): `/api/camera/profiles/scheduler/status`
- Décorateur: `app.route('/api/camera/profiles/scheduler/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_platform` (ligne 5027)

- Signature: `api_platform()`
- Doc: API endpoint to get platform information.
- Méthodes: `GET`
- Path(s): `/api/platform`
- Décorateur: `app.route('/api/platform', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_video_preview_stream` (ligne 5127)

- Signature: `api_video_preview_stream()`
- Doc: Stream live MJPEG preview of the camera.
- Méthodes: `GET`
- Path(s): `/api/video/preview/stream`
- Décorateur: `app.route('/api/video/preview/stream')`
- Entrées détectées (heuristique):
  - Query (`request.args`): `fps`, `height`, `source`, `width`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_video_preview_snapshot` (ligne 5163)

- Signature: `api_video_preview_snapshot()`
- Doc: Capture a single snapshot from the camera or RTSP stream.
- Méthodes: `GET`
- Path(s): `/api/video/preview/snapshot`
- Décorateur: `app.route('/api/video/preview/snapshot')`
- Entrées détectées (heuristique):
  - Query (`request.args`): `height`, `width`
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_video_preview_status` (ligne 5221)

- Signature: `api_video_preview_status()`
- Doc: Check if preview is available and which source will be used.
- Méthodes: `GET`
- Path(s): `/api/video/preview/status`
- Décorateur: `app.route('/api/video/preview/status')`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_scan` (ligne 5251)

- Signature: `api_wifi_scan()`
- Doc: API endpoint to scan for WiFi networks.
- Méthodes: `GET`
- Path(s): `/api/wifi/scan`
- Décorateur: `app.route('/api/wifi/scan', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_status` (ligne 5258)

- Signature: `api_wifi_status()`
- Doc: API endpoint to get WiFi status.
- Méthodes: `GET`
- Path(s): `/api/wifi/status`
- Décorateur: `app.route('/api/wifi/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_connect` (ligne 5270)

- Signature: `api_wifi_connect()`
- Doc: API endpoint to connect to WiFi.
- Méthodes: `POST`
- Path(s): `/api/wifi/connect`
- Décorateur: `app.route('/api/wifi/connect', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_disconnect` (ligne 5291)

- Signature: `api_wifi_disconnect()`
- Doc: API endpoint to disconnect from WiFi.
- Méthodes: `POST`
- Path(s): `/api/wifi/disconnect`
- Décorateur: `app.route('/api/wifi/disconnect', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_network_interfaces` (ligne 5314)

- Signature: `api_network_interfaces()`
- Doc: API endpoint to get all network interfaces.
- Méthodes: `GET`
- Path(s): `/api/network/interfaces`
- Décorateur: `app.route('/api/network/interfaces', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_network_config` (ligne 5326)

- Signature: `api_network_config()`
- Doc: API endpoint to get network configuration.
- Méthodes: `GET`
- Path(s): `/api/network/config`
- Décorateur: `app.route('/api/network/config', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_network_priority` (ligne 5333)

- Signature: `api_network_priority()`
- Doc: API endpoint to set interface priority order.
- Méthodes: `POST`
- Path(s): `/api/network/priority`
- Décorateur: `app.route('/api/network/priority', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_network_static` (ligne 5349)

- Signature: `api_network_static()`
- Doc: API endpoint to configure static IP.
- Méthodes: `POST`
- Path(s): `/api/network/static`
- Décorateur: `app.route('/api/network/static', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_network_dhcp` (ligne 5368)

- Signature: `api_network_dhcp()`
- Doc: API endpoint to configure DHCP.
- Méthodes: `POST`
- Path(s): `/api/network/dhcp`
- Décorateur: `app.route('/api/network/dhcp', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_status` (ligne 5388)

- Signature: `api_wifi_failover_status()`
- Doc: Get WiFi failover status.
- Méthodes: `GET`
- Path(s): `/api/wifi/failover/status`
- Décorateur: `app.route('/api/wifi/failover/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_config_get` (ligne 5395)

- Signature: `api_wifi_failover_config_get()`
- Doc: Get WiFi failover configuration.
- Méthodes: `GET`
- Path(s): `/api/wifi/failover/config`
- Décorateur: `app.route('/api/wifi/failover/config', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_config_set` (ligne 5402)

- Signature: `api_wifi_failover_config_set()`
- Doc: Update WiFi failover configuration.
- Méthodes: `POST`
- Path(s): `/api/wifi/failover/config`
- Décorateur: `app.route('/api/wifi/failover/config', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_apply` (ligne 5437)

- Signature: `api_wifi_failover_apply()`
- Doc: Apply WiFi failover - connect the appropriate interface.
- Méthodes: `POST`
- Path(s): `/api/wifi/failover/apply`
- Décorateur: `app.route('/api/wifi/failover/apply', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_interfaces` (ligne 5450)

- Signature: `api_wifi_failover_interfaces()`
- Doc: Get all WiFi interfaces with their status.
- Méthodes: `GET`
- Path(s): `/api/wifi/failover/interfaces`
- Décorateur: `app.route('/api/wifi/failover/interfaces', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_disconnect` (ligne 5457)

- Signature: `api_wifi_failover_disconnect()`
- Doc: Disconnect a specific WiFi interface.
- Méthodes: `POST`
- Path(s): `/api/wifi/failover/disconnect`
- Décorateur: `app.route('/api/wifi/failover/disconnect', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_ap_status` (ligne 5717)

- Signature: `api_ap_status()`
- Doc: Get Access Point status.
- Méthodes: `GET`
- Path(s): `/api/network/ap/status`
- Décorateur: `app.route('/api/network/ap/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_ap_config` (ligne 5729)

- Signature: `api_ap_config()`
- Doc: Configure Access Point settings.
- Méthodes: `POST`
- Path(s): `/api/network/ap/config`
- Décorateur: `app.route('/api/network/ap/config', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_ap_start` (ligne 5785)

- Signature: `api_ap_start()`
- Doc: Start Access Point.
- Méthodes: `POST`
- Path(s): `/api/network/ap/start`
- Décorateur: `app.route('/api/network/ap/start', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_ap_stop` (ligne 5795)

- Signature: `api_ap_stop()`
- Doc: Stop Access Point.
- Méthodes: `POST`
- Path(s): `/api/network/ap/stop`
- Décorateur: `app.route('/api/network/ap/stop', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_override_get` (ligne 5902)

- Signature: `api_wifi_override_get()`
- Doc: Get WiFi manual override status.
- Méthodes: `GET`
- Path(s): `/api/network/wifi/override`
- Décorateur: `app.route('/api/network/wifi/override', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_override_set` (ligne 5916)

- Signature: `api_wifi_override_set()`
- Doc: Set WiFi manual override.
- Méthodes: `POST`
- Path(s): `/api/network/wifi/override`
- Décorateur: `app.route('/api/network/wifi/override', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_watchdog_status` (ligne 5936)

- Signature: `api_wifi_failover_watchdog_status()`
- Doc: Get WiFi failover watchdog status.
- Méthodes: `GET`
- Path(s): `/api/wifi/failover/watchdog`
- Décorateur: `app.route('/api/wifi/failover/watchdog', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_wifi_failover_watchdog_control` (ligne 5949)

- Signature: `api_wifi_failover_watchdog_control()`
- Doc: Start or stop the WiFi failover watchdog.
- Méthodes: `POST`
- Path(s): `/api/wifi/failover/watchdog`
- Décorateur: `app.route('/api/wifi/failover/watchdog', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_rtsp_watchdog_status` (ligne 5972)

- Signature: `api_rtsp_watchdog_status()`
- Doc: Get RTSP watchdog status including camera health.
- Méthodes: `GET`
- Path(s): `/api/rtsp/watchdog/status`
- Décorateur: `app.route('/api/rtsp/watchdog/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_rtsp_watchdog_control` (ligne 5999)

- Signature: `api_rtsp_watchdog_control()`
- Doc: Control RTSP watchdog.
- Méthodes: `POST`
- Path(s): `/api/rtsp/watchdog`
- Décorateur: `app.route('/api/rtsp/watchdog', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_leds_status` (ligne 6022)

- Signature: `api_leds_status()`
- Doc: API endpoint to get LED status.
- Méthodes: `GET`
- Path(s): `/api/leds/status`
- Décorateur: `app.route('/api/leds/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_leds_set` (ligne 6029)

- Signature: `api_leds_set()`
- Doc: API endpoint to set LED state.
- Méthodes: `POST`
- Path(s): `/api/leds/set`
- Décorateur: `app.route('/api/leds/set', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_leds_boot_config` (ligne 6070)

- Signature: `api_leds_boot_config()`
- Doc: API endpoint to get LED boot configuration.
- Méthodes: `GET`
- Path(s): `/api/leds/boot-config`
- Décorateur: `app.route('/api/leds/boot-config', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_gpu_mem_get` (ligne 6081)

- Signature: `api_gpu_mem_get()`
- Doc: API endpoint to get GPU memory.
- Méthodes: `GET`
- Path(s): `/api/gpu/mem`
- Décorateur: `app.route('/api/gpu/mem', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_gpu_mem_set` (ligne 6088)

- Signature: `api_gpu_mem_set()`
- Doc: API endpoint to set GPU memory.
- Méthodes: `POST`
- Path(s): `/api/gpu/mem`
- Décorateur: `app.route('/api/gpu/mem', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_power_status` (ligne 6105)

- Signature: `api_power_status()`
- Doc: API endpoint to get power/energy status of all components.
- Méthodes: `GET`
- Path(s): `/api/power/status`
- Décorateur: `app.route('/api/power/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_power_bluetooth` (ligne 6119)

- Signature: `api_power_bluetooth()`
- Doc: API endpoint to control Bluetooth.
- Méthodes: `POST`
- Path(s): `/api/power/bluetooth`
- Décorateur: `app.route('/api/power/bluetooth', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_power_hdmi` (ligne 6152)

- Signature: `api_power_hdmi()`
- Doc: API endpoint to control HDMI.
- Méthodes: `POST`
- Path(s): `/api/power/hdmi`
- Décorateur: `app.route('/api/power/hdmi', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_power_audio` (ligne 6185)

- Signature: `api_power_audio()`
- Doc: API endpoint to control Audio.
- Méthodes: `POST`
- Path(s): `/api/power/audio`
- Décorateur: `app.route('/api/power/audio', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_power_cpu_freq` (ligne 6218)

- Signature: `api_power_cpu_freq()`
- Doc: API endpoint to control CPU frequency.
- Méthodes: `POST`
- Path(s): `/api/power/cpu-freq`
- Décorateur: `app.route('/api/power/cpu-freq', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_power_boot_config` (ligne 6236)

- Signature: `api_power_boot_config()`
- Doc: API endpoint to get power boot configuration.
- Méthodes: `GET`
- Path(s): `/api/power/boot-config`
- Décorateur: `app.route('/api/power/boot-config', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_power_apply_all` (ligne 6249)

- Signature: `api_power_apply_all()`
- Doc: API endpoint to apply all power settings at once.
- Méthodes: `POST`
- Path(s): `/api/power/apply-all`
- Décorateur: `app.route('/api/power/apply-all', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_system_reboot` (ligne 6350)

- Signature: `api_system_reboot()`
- Doc: API endpoint to reboot the system.
- Méthodes: `POST`
- Path(s): `/api/system/reboot`
- Décorateur: `app.route('/api/system/reboot', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_ntp_get` (ligne 6366)

- Signature: `api_ntp_get()`
- Doc: Get NTP configuration and status.
- Méthodes: `GET`
- Path(s): `/api/system/ntp`
- Décorateur: `app.route('/api/system/ntp', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_ntp_set` (ligne 6435)

- Signature: `api_ntp_set()`
- Doc: Set NTP server configuration.
- Méthodes: `POST`
- Path(s): `/api/system/ntp`
- Décorateur: `app.route('/api/system/ntp', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_ntp_sync` (ligne 6469)

- Signature: `api_ntp_sync()`
- Doc: Force NTP synchronization.
- Méthodes: `POST`
- Path(s): `/api/system/ntp/sync`
- Décorateur: `app.route('/api/system/ntp/sync', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_update_check` (ligne 6508)

- Signature: `api_update_check()`
- Doc: Check for available updates from GitHub.
- Méthodes: `GET`
- Path(s): `/api/system/update/check`
- Décorateur: `app.route('/api/system/update/check', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_update_perform` (ligne 6566)

- Signature: `api_update_perform()`
- Doc: Perform system update from GitHub.
- Méthodes: `POST`
- Path(s): `/api/system/update/perform`
- Décorateur: `app.route('/api/system/update/perform', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_debug_firmware_check` (ligne 6722)

- Signature: `api_debug_firmware_check()`
- Doc: Check for Raspberry Pi firmware updates.
- Méthodes: `GET`
- Path(s): `/api/debug/firmware/check`
- Décorateur: `app.route('/api/debug/firmware/check', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_debug_firmware_update` (ligne 6836)

- Signature: `api_debug_firmware_update()`
- Doc: Apply Raspberry Pi firmware update.
- Méthodes: `POST`
- Path(s): `/api/debug/firmware/update`
- Décorateur: `app.route('/api/debug/firmware/update', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_debug_apt_update` (ligne 6905)

- Signature: `api_debug_apt_update()`
- Doc: Run apt update to refresh package lists.
- Méthodes: `POST`
- Path(s): `/api/debug/apt/update`
- Décorateur: `app.route('/api/debug/apt/update', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_debug_apt_upgradable` (ligne 6940)

- Signature: `api_debug_apt_upgradable()`
- Doc: List packages that can be upgraded.
- Méthodes: `GET`
- Path(s): `/api/debug/apt/upgradable`
- Décorateur: `app.route('/api/debug/apt/upgradable', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_debug_apt_upgrade` (ligne 6979)

- Signature: `api_debug_apt_upgrade()`
- Doc: Run apt upgrade to update all packages.
- Méthodes: `POST`
- Path(s): `/api/debug/apt/upgrade`
- Décorateur: `app.route('/api/debug/apt/upgrade', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_debug_system_uptime` (ligne 7027)

- Signature: `api_debug_system_uptime()`
- Doc: Get system uptime.
- Méthodes: `GET`
- Path(s): `/api/debug/system/uptime`
- Décorateur: `app.route('/api/debug/system/uptime', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_test` (ligne 7423)

- Signature: `api_meeting_test()`
- Doc: Test Meeting API connection and start heartbeat if successful.
- Méthodes: `POST`
- Path(s): `/api/meeting/test`
- Décorateur: `app.route('/api/meeting/test', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_heartbeat` (ligne 7468)

- Signature: `api_meeting_heartbeat()`
- Doc: Send heartbeat to Meeting API (manual trigger).
- Méthodes: `POST`
- Path(s): `/api/meeting/heartbeat`
- Décorateur: `app.route('/api/meeting/heartbeat', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_availability` (ligne 7493)

- Signature: `api_meeting_availability()`
- Doc: Check device availability on Meeting API.
- Méthodes: `GET`
- Path(s): `/api/meeting/availability`
- Décorateur: `app.route('/api/meeting/availability', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_device_info` (ligne 7511)

- Signature: `api_meeting_device_info()`
- Doc: Get device info from Meeting API.
- Méthodes: `GET`
- Path(s): `/api/meeting/device`
- Décorateur: `app.route('/api/meeting/device', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_request_tunnel` (ligne 7556)

- Signature: `api_meeting_request_tunnel()`
- Doc: Request a tunnel from Meeting API.
- Méthodes: `POST`
- Path(s): `/api/meeting/tunnel`
- Décorateur: `app.route('/api/meeting/tunnel', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_status` (ligne 7579)

- Signature: `api_meeting_status()`
- Doc: Get Meeting integration status including heartbeat state.
- Méthodes: `GET`
- Path(s): `/api/meeting/status`
- Décorateur: `app.route('/api/meeting/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_validate` (ligne 7635)

- Signature: `api_meeting_validate()`
- Doc: Validate Meeting credentials without provisioning - just checks if valid.
- Méthodes: `POST`
- Path(s): `/api/meeting/validate`
- Décorateur: `app.route('/api/meeting/validate', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_provision` (ligne 7689)

- Signature: `api_meeting_provision()`
- Doc: Provision the device with Meeting API - validates credentials and burns a token.
- Méthodes: `POST`
- Path(s): `/api/meeting/provision`
- Décorateur: `app.route('/api/meeting/provision', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_meeting_master_reset` (ligne 7808)

- Signature: `api_meeting_master_reset()`
- Doc: Reset Meeting configuration (requires master code).
- Méthodes: `POST`
- Path(s): `/api/meeting/master-reset`
- Décorateur: `app.route('/api/meeting/master-reset', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_onvif_status` (ligne 8119)

- Signature: `api_onvif_status()`
- Doc: Get ONVIF service status and configuration.
- Méthodes: `GET`
- Path(s): `/api/onvif/status`
- Décorateur: `app.route('/api/onvif/status', methods=['GET'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_onvif_config` (ligne 8163)

- Signature: `api_onvif_config()`
- Doc: Get or set ONVIF configuration.
- Méthodes: `GET, POST`
- Path(s): `/api/onvif/config`
- Décorateur: `app.route('/api/onvif/config', methods=['GET', 'POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

#### `api_onvif_restart` (ligne 8217)

- Signature: `api_onvif_restart()`
- Doc: Restart ONVIF service.
- Méthodes: `POST`
- Path(s): `/api/onvif/restart`
- Décorateur: `app.route('/api/onvif/restart', methods=['POST'])`
- Entrées détectées (heuristique):
  - Query (`request.args`): _aucun détecté_
  - Form (`request.form`): _aucun détecté_
  - JSON (`request.json` / `request.get_json()`): _aucun détecté_
  - Headers (`request.headers`): _aucun détecté_
  - Files (`request.files`): _aucun détecté_

## 2) Routes via `app.add_url_rule`

Aucune route détectée via `app.add_url_rule()`.

## 3) Hooks Flask (before/after/error/…)

Aucun hook Flask détecté via décorateurs.

## 4) Fonctions (toutes, y compris imbriquées)

### Résumé

- Total fonctions (y compris méthodes/nested): **224**
- Total endpoints (décorateurs): **105**
- Total hooks: **0**

### Index (table)

| Nom qualifié | Signature | Ligne | Fin | Est endpoint | Résumé |
|---|---|---:|---:|---:|---|
| `load_scheduler_state` | `load_scheduler_state()` | 51 | 59 | non | Load scheduler state from shared file. |
| `save_scheduler_state` | `save_scheduler_state(running, active_profile=…, last_change=…)` | 62 | 74 | non | Save scheduler state to shared file. |
| `detect_platform` | `detect_platform()` | 81 | 128 | non | Detect Raspberry Pi model and available features. |
| `get_wifi_networks` | `get_wifi_networks()` | 493 | 532 | non | Get list of available WiFi networks. |
| `get_current_wifi` | `get_current_wifi()` | 535 | 565 | non | Get current WiFi connection info. |
| `connect_wifi` | `connect_wifi(ssid, password, priority=…)` | 568 | 660 | non | Connect to a WiFi network using the first available WiFi interface by priority. |
| `configure_wpa_supplicant` | `configure_wpa_supplicant(ssid, password, priority=…)` | 663 | 703 | non | Configure WiFi via wpa_supplicant.conf. |
| `get_wifi_config` | `get_wifi_config()` | 706 | 731 | non | Get saved WiFi configuration. |
| `find_camera_device` | `find_camera_device()` | 750 | 811 | non | Find the best available camera device. |
| `check_rtsp_service_health` | `check_rtsp_service_health()` | 814 | 851 | non | Check if RTSP service is healthy (running and streaming). |
| `restart_rtsp_service` | `restart_rtsp_service(reason=…)` | 854 | 889 | non | Restart the RTSP service with proper camera device. |
| `rtsp_watchdog_loop` | `rtsp_watchdog_loop()` | 892 | 931 | non | Background thread that monitors RTSP service health. |
| `start_rtsp_watchdog` | `start_rtsp_watchdog()` | 934 | 949 | non | Start the RTSP watchdog thread. |
| `stop_rtsp_watchdog` | `stop_rtsp_watchdog()` | 952 | 965 | non | Stop the RTSP watchdog thread. |
| `wifi_failover_watchdog_loop` | `wifi_failover_watchdog_loop()` | 988 | 1104 | non | Background thread that monitors WiFi interfaces and triggers failover if needed. |
| `start_wifi_failover_watchdog` | `start_wifi_failover_watchdog()` | 1107 | 1124 | non | Start the WiFi failover watchdog thread. |
| `stop_wifi_failover_watchdog` | `stop_wifi_failover_watchdog()` | 1127 | 1137 | non | Stop the WiFi failover watchdog thread. |
| `load_wifi_failover_config` | `load_wifi_failover_config()` | 1140 | 1180 | non | Load WiFi failover configuration. |
| `save_wifi_failover_config` | `save_wifi_failover_config(config)` | 1183 | 1192 | non | Save WiFi failover configuration. |
| `get_wifi_interfaces` | `get_wifi_interfaces()` | 1195 | 1266 | non | Get all WiFi interfaces and their status. |
| `get_active_wifi_interface` | `get_active_wifi_interface()` | 1269 | 1291 | non | Get the currently active (connected) WiFi interface according to failover priority. |
| `disconnect_wifi_interface` | `disconnect_wifi_interface(interface_name)` | 1294 | 1319 | non | Disconnect a WiFi interface. |
| `connect_wifi_on_interface` | `connect_wifi_on_interface(interface_name, ssid, password, ip_config=…)` | 1322 | 1486 | non | Connect a specific WiFi interface to an SSID with optional IP config. |
| `perform_wifi_failover` | `perform_wifi_failover()` | 1489 | 1621 | non | Apply WiFi failover configuration. |
| `get_wifi_failover_status` | `get_wifi_failover_status()` | 1624 | 1665 | non | Get current WiFi failover status. |
| `get_network_interfaces` | `get_network_interfaces()` | 1672 | 1754 | non | Get list of all network interfaces with their status. |
| `get_interface_priority` | `get_interface_priority()` | 1757 | 1775 | non | Get the current interface priority order from NetworkManager metrics. |
| `set_interface_priority` | `set_interface_priority(interfaces_order)` | 1778 | 1810 | non | Set network interface priority using NetworkManager metrics. |
| `get_network_config` | `get_network_config()` | 1813 | 1835 | non | Get current network configuration. |
| `configure_static_ip` | `configure_static_ip(interface, ip_address, gateway, dns)` | 1838 | 1881 | non | Configure static IP on an interface. |
| `configure_dhcp` | `configure_dhcp(interface)` | 1884 | 1930 | non | Configure DHCP on an interface. |
| `get_led_paths` | `get_led_paths()` | 1937 | 1967 | non | Get LED paths based on platform. |
| `is_ethernet_led_controllable` | `is_ethernet_led_controllable()` | 1970 | 2012 | non | Check if Ethernet LEDs can be controlled via software. |
| `get_led_status` | `get_led_status()` | 2015 | 2094 | non | Get current LED status. |
| `set_led_state` | `set_led_state(led, enabled, trigger=…)` | 2097 | 2127 | non | Set LED state (immediate effect). |
| `configure_leds_boot` | `configure_leds_boot(pwr_enabled, act_enabled)` | 2130 | 2217 | non | Configure LEDs in boot config for persistence across reboots. |
| `get_led_boot_config` | `get_led_boot_config()` | 2220 | 2252 | non | Read current LED configuration from boot config. |
| `get_gpu_mem` | `get_gpu_mem()` | 2259 | 2283 | non | Get current GPU memory allocation. |
| `set_gpu_mem` | `set_gpu_mem(mem_mb)` | 2286 | 2312 | non | Set GPU memory allocation in boot config. |
| `get_power_status` | `get_power_status()` | 2319 | 2390 | non | Get current power state of all components. |
| `get_optional_service_status` | `get_optional_service_status(service_key)` | 2446 | 2473 | non | Get the enabled status of an optional service. |
| `get_all_services_status` | `get_all_services_status()` | 2476 | 2487 | non | Get status of all optional services. |
| `set_service_state` | `set_service_state(service_key, enabled)` | 2490 | 2531 | non | Enable or disable a service. |
| `set_bluetooth_state` | `set_bluetooth_state(enabled)` | 2534 | 2548 | non | Enable or disable Bluetooth. |
| `configure_power_boot` | `configure_power_boot(bluetooth_enabled, hdmi_enabled, audio_enabled, wifi_enabled=…, pwr_led_enabled=…, act_led_enabled=…, camera_led_csi_enabled=…)` | 2551 | 2659 | non | Configure power settings in boot config for persistence across reboots. |
| `set_cpu_frequency` | `set_cpu_frequency(freq_mhz)` | 2662 | 2680 | non | Set CPU frequency (requires cpufreq-set or raspi-config). |
| `get_boot_power_config` | `get_boot_power_config()` | 2683 | 2740 | non | Read current power configuration from boot config. |
| `load_config` | `load_config()` | 2747 | 2765 | non | Load configuration from file or return defaults. |
| `save_config` | `save_config(config)` | 2768 | 2800 | non | Save configuration to file. |
| `get_service_status` | `get_service_status()` | 2803 | 2813 | non | Get the status of the RTSP recorder service. |
| `control_service` | `control_service(action)` | 2816 | 2827 | non | Control the RTSP recorder service. |
| `get_system_info` | `get_system_info()` | 2830 | 2977 | non | Get system information for display. |
| `get_recent_logs` | `get_recent_logs(lines=…, source=…)` | 2980 | 3026 | non | Get recent log entries from multiple sources. |
| `stream_logs` | `stream_logs()` | 3029 | 3059 | non | Generator for streaming logs in real-time via SSE. |
| `get_diagnostic_info` | `get_diagnostic_info()` | 3062 | 3167 | non | Get diagnostic information for troubleshooting. |
| `get_camera_controls` | `get_camera_controls(device=…)` | 3174 | 3203 | non | Get available camera controls and their current values. |
| `set_camera_control` | `set_camera_control(device, control, value)` | 3206 | 3215 | non | Set a camera control value. |
| `get_camera_autofocus_status` | `get_camera_autofocus_status(device=…)` | 3218 | 3246 | non | Get autofocus status for a camera. |
| `set_camera_autofocus` | `set_camera_autofocus(device, enabled, persist=…)` | 3249 | 3276 | non | Enable or disable autofocus. |
| `set_camera_focus` | `set_camera_focus(device, value)` | 3279 | 3281 | non | Set manual focus value. |
| `get_camera_formats` | `get_camera_formats(device=…)` | 3284 | 3345 | non | Get available video formats and resolutions for a camera. |
| `apply_camera_autofocus_from_config` | `apply_camera_autofocus_from_config(device=…)` | 3348 | 3361 | non | Apply autofocus setting from config at startup. |
| `trigger_one_shot_focus` | `trigger_one_shot_focus(device=…)` | 3364 | 3385 | non | Trigger one-shot autofocus (focus once then stay in manual mode). |
| `get_all_camera_controls` | `get_all_camera_controls(device=…)` | 3388 | 3490 | non | Get ALL available camera controls with extended info for dynamic UI. |
| `get_profiles_path` | `get_profiles_path()` | 3519 | 3522 | non | Get the camera profiles JSON file path. |
| `load_camera_profiles` | `load_camera_profiles()` | 3525 | 3538 | non | Load camera profiles from JSON file. |
| `save_camera_profiles` | `save_camera_profiles(profiles)` | 3541 | 3553 | non | Save camera profiles to JSON file. |
| `apply_camera_profile` | `apply_camera_profile(profile_name, device=…)` | 3556 | 3589 | non | Apply a camera profile (set all its controls). |
| `get_current_profile_for_time` | `get_current_profile_for_time(profiles, current_time=…)` | 3592 | 3638 | non | Determine which profile should be active based on current time. |
| `get_current_profile_for_time.time_to_minutes` | `time_to_minutes(t)` | 3605 | 3610 | non | Convert time string (HH:MM) to minutes since midnight. |
| `camera_profiles_scheduler_loop` | `camera_profiles_scheduler_loop()` | 3641 | 3686 | non | Background scheduler loop for camera profiles. |
| `start_camera_profiles_scheduler` | `start_camera_profiles_scheduler()` | 3689 | 3718 | non | Start the camera profiles scheduler thread. |
| `stop_camera_profiles_scheduler` | `stop_camera_profiles_scheduler()` | 3721 | 3731 | non | Stop the camera profiles scheduler thread. |
| `index` | `index()` | 3739 | 3772 | oui | Main dashboard page. |
| `api_get_config` | `api_get_config()` | 3776 | 3783 | oui | API endpoint to get current configuration. |
| `api_save_config` | `api_save_config()` | 3787 | 3803 | oui | API endpoint to save configuration. |
| `api_get_status` | `api_get_status()` | 3807 | 3815 | oui | API endpoint to get service status. |
| `api_service_control` | `api_service_control(action)` | 3819 | 3826 | oui | API endpoint to control the service. |
| `api_get_logs` | `api_get_logs()` | 3830 | 3838 | oui | API endpoint to get recent logs. |
| `api_stream_logs` | `api_stream_logs()` | 3842 | 3852 | oui | API endpoint for real-time log streaming via SSE. |
| `api_clean_logs` | `api_clean_logs()` | 3856 | 3921 | oui | API endpoint to clean/truncate log files. |
| `api_diagnostic` | `api_diagnostic()` | 3925 | 3931 | oui | API endpoint to get diagnostic information. |
| `api_get_recordings` | `api_get_recordings()` | 3935 | 3958 | oui | API endpoint to list recordings. |
| `load_locked_files` | `load_locked_files()` | 3968 | 3976 | non | Load list of locked recording files. |
| `save_locked_files` | `save_locked_files(locked_files)` | 3979 | 3988 | non | Save list of locked recording files. |
| `is_valid_recording_filename` | `is_valid_recording_filename(filename)` | 3991 | 3997 | non | Check if filename is a valid recording file (security). |
| `api_list_recordings` | `api_list_recordings()` | 4001 | 4145 | oui | API endpoint to list recordings with pagination support. |
| `format_file_size` | `format_file_size(size_bytes)` | 4148 | 4154 | non | Format file size in human readable format. |
| `api_delete_recordings` | `api_delete_recordings()` | 4158 | 4206 | oui | API endpoint to delete recordings. |
| `api_lock_recordings` | `api_lock_recordings()` | 4210 | 4247 | oui | API endpoint to lock/unlock recordings (prevent deletion). |
| `api_download_recording` | `api_download_recording(filename)` | 4251 | 4283 | oui | API endpoint to download a recording file. |
| `api_stream_recording` | `api_stream_recording(filename)` | 4287 | 4371 | oui | API endpoint to stream a recording for playback. |
| `api_stream_recording.generate_range` | `generate_range()` | 4328 | 4339 | non |  |
| `api_stream_recording.generate_file` | `generate_file()` | 4353 | 4359 | non |  |
| `api_recording_info` | `api_recording_info(filename)` | 4375 | 4425 | oui | API endpoint to get detailed info about a recording. |
| `get_thumbnail_path` | `get_thumbnail_path(filename)` | 4432 | 4436 | non | Get the path to the thumbnail for a recording. |
| `generate_thumbnail` | `generate_thumbnail(video_path, thumb_path, timestamp=…)` | 4439 | 4469 | non | Generate a thumbnail from a video file using ffmpeg. |
| `api_recording_thumbnail` | `api_recording_thumbnail(filename)` | 4473 | 4513 | oui | API endpoint to get or generate a thumbnail for a recording. |
| `api_generate_thumbnails` | `api_generate_thumbnails()` | 4517 | 4557 | oui | API endpoint to batch generate thumbnails for all recordings. |
| `api_clean_thumbnails` | `api_clean_thumbnails()` | 4561 | 4586 | oui | API endpoint to clean orphaned thumbnails. |
| `api_detect_cameras` | `api_detect_cameras()` | 4590 | 4625 | oui | API endpoint to detect available cameras. |
| `api_detect_audio` | `api_detect_audio()` | 4629 | 4652 | oui | API endpoint to detect available audio devices. |
| `api_camera_controls` | `api_camera_controls()` | 4656 | 4666 | oui | API endpoint to get camera controls. |
| `api_camera_autofocus_get` | `api_camera_autofocus_get()` | 4670 | 4674 | oui | API endpoint to get autofocus status. |
| `api_camera_autofocus_set` | `api_camera_autofocus_set()` | 4678 | 4694 | oui | API endpoint to set autofocus (with persistence). |
| `api_camera_focus_set` | `api_camera_focus_set()` | 4698 | 4716 | oui | API endpoint to set manual focus. |
| `api_camera_control_set` | `api_camera_control_set()` | 4720 | 4739 | oui | API endpoint to set any camera control. |
| `api_camera_formats` | `api_camera_formats()` | 4743 | 4761 | oui | API endpoint to get available camera formats and resolutions. |
| `api_camera_oneshot_focus` | `api_camera_oneshot_focus()` | 4765 | 4777 | oui | API endpoint to trigger one-shot autofocus. |
| `api_camera_all_controls` | `api_camera_all_controls()` | 4781 | 4790 | oui | API endpoint to get ALL camera controls for advanced settings. |
| `api_camera_set_multiple_controls` | `api_camera_set_multiple_controls()` | 4794 | 4818 | oui | API endpoint to set multiple camera controls at once. |
| `api_camera_profiles_get` | `api_camera_profiles_get()` | 4826 | 4851 | oui | Get all camera profiles. |
| `api_camera_profiles_save` | `api_camera_profiles_save()` | 4855 | 4870 | oui | Save all camera profiles. |
| `api_camera_profile_get` | `api_camera_profile_get(profile_name)` | 4874 | 4885 | oui | Get a specific camera profile. |
| `api_camera_profile_update` | `api_camera_profile_update(profile_name)` | 4889 | 4900 | oui | Update or create a camera profile. |
| `api_camera_profile_delete` | `api_camera_profile_delete(profile_name)` | 4904 | 4917 | oui | Delete a camera profile. |
| `api_camera_profile_apply` | `api_camera_profile_apply(profile_name)` | 4921 | 4935 | oui | Apply a camera profile immediately. |
| `api_camera_profile_capture` | `api_camera_profile_capture(profile_name)` | 4939 | 4977 | oui | Capture current camera settings into a profile. |
| `api_camera_profiles_scheduler_start` | `api_camera_profiles_scheduler_start()` | 4981 | 4984 | oui | Start the camera profiles scheduler. |
| `api_camera_profiles_scheduler_stop` | `api_camera_profiles_scheduler_stop()` | 4988 | 4991 | oui | Stop the camera profiles scheduler. |
| `api_camera_profiles_scheduler_status` | `api_camera_profiles_scheduler_status()` | 4995 | 5023 | oui | Get camera profiles scheduler status. |
| `api_platform` | `api_platform()` | 5027 | 5032 | oui | API endpoint to get platform information. |
| `generate_mjpeg_stream` | `generate_mjpeg_stream(source_type=…, rtsp_url=…, device=…, width=…, height=…, fps=…)` | 5044 | 5123 | non | Generate MJPEG stream from camera or RTSP source using ffmpeg. |
| `api_video_preview_stream` | `api_video_preview_stream()` | 5127 | 5159 | oui | Stream live MJPEG preview of the camera. |
| `api_video_preview_snapshot` | `api_video_preview_snapshot()` | 5163 | 5217 | oui | Capture a single snapshot from the camera or RTSP stream. |
| `api_video_preview_status` | `api_video_preview_status()` | 5221 | 5243 | oui | Check if preview is available and which source will be used. |
| `api_wifi_scan` | `api_wifi_scan()` | 5251 | 5254 | oui | API endpoint to scan for WiFi networks. |
| `api_wifi_status` | `api_wifi_status()` | 5258 | 5266 | oui | API endpoint to get WiFi status. |
| `api_wifi_connect` | `api_wifi_connect()` | 5270 | 5287 | oui | API endpoint to connect to WiFi. |
| `api_wifi_disconnect` | `api_wifi_disconnect()` | 5291 | 5306 | oui | API endpoint to disconnect from WiFi. |
| `api_network_interfaces` | `api_network_interfaces()` | 5314 | 5322 | oui | API endpoint to get all network interfaces. |
| `api_network_config` | `api_network_config()` | 5326 | 5329 | oui | API endpoint to get network configuration. |
| `api_network_priority` | `api_network_priority()` | 5333 | 5345 | oui | API endpoint to set interface priority order. |
| `api_network_static` | `api_network_static()` | 5349 | 5364 | oui | API endpoint to configure static IP. |
| `api_network_dhcp` | `api_network_dhcp()` | 5368 | 5380 | oui | API endpoint to configure DHCP. |
| `api_wifi_failover_status` | `api_wifi_failover_status()` | 5388 | 5391 | oui | Get WiFi failover status. |
| `api_wifi_failover_config_get` | `api_wifi_failover_config_get()` | 5395 | 5398 | oui | Get WiFi failover configuration. |
| `api_wifi_failover_config_set` | `api_wifi_failover_config_set()` | 5402 | 5433 | oui | Update WiFi failover configuration. |
| `api_wifi_failover_apply` | `api_wifi_failover_apply()` | 5437 | 5446 | oui | Apply WiFi failover - connect the appropriate interface. |
| `api_wifi_failover_interfaces` | `api_wifi_failover_interfaces()` | 5450 | 5453 | oui | Get all WiFi interfaces with their status. |
| `api_wifi_failover_disconnect` | `api_wifi_failover_disconnect()` | 5457 | 5469 | oui | Disconnect a specific WiFi interface. |
| `load_ap_config` | `load_ap_config()` | 5478 | 5499 | non | Load Access Point configuration. |
| `save_ap_config` | `save_ap_config(config)` | 5502 | 5511 | non | Save Access Point configuration. |
| `get_ap_status` | `get_ap_status()` | 5514 | 5554 | non | Get current Access Point status. |
| `configure_hostapd` | `configure_hostapd(config)` | 5557 | 5587 | non | Configure hostapd for Access Point mode. |
| `configure_dnsmasq` | `configure_dnsmasq(config)` | 5590 | 5616 | non | Configure dnsmasq for DHCP server in AP mode. |
| `start_access_point` | `start_access_point()` | 5619 | 5683 | non | Start Access Point mode. |
| `stop_access_point` | `stop_access_point()` | 5686 | 5713 | non | Stop Access Point mode. |
| `api_ap_status` | `api_ap_status()` | 5717 | 5725 | oui | Get Access Point status. |
| `api_ap_config` | `api_ap_config()` | 5729 | 5781 | oui | Configure Access Point settings. |
| `api_ap_start` | `api_ap_start()` | 5785 | 5791 | oui | Start Access Point. |
| `api_ap_stop` | `api_ap_stop()` | 5795 | 5801 | oui | Stop Access Point. |
| `get_ethernet_status` | `get_ethernet_status()` | 5808 | 5824 | non | Check if Ethernet is connected and functional. |
| `get_wifi_manual_override` | `get_wifi_manual_override()` | 5827 | 5830 | non | Check if WiFi manual override is enabled. |
| `set_wifi_manual_override` | `set_wifi_manual_override(enabled)` | 5833 | 5837 | non | Set WiFi manual override. |
| `manage_wifi_based_on_ethernet` | `manage_wifi_based_on_ethernet()` | 5840 | 5862 | non | Enable/disable WiFi based on Ethernet status and manual override. |
| `get_wlan0_status` | `get_wlan0_status()` | 5865 | 5898 | non | Get wlan0 interface status. |
| `api_wifi_override_get` | `api_wifi_override_get()` | 5902 | 5912 | oui | Get WiFi manual override status. |
| `api_wifi_override_set` | `api_wifi_override_set()` | 5916 | 5932 | oui | Set WiFi manual override. |
| `api_wifi_failover_watchdog_status` | `api_wifi_failover_watchdog_status()` | 5936 | 5945 | oui | Get WiFi failover watchdog status. |
| `api_wifi_failover_watchdog_control` | `api_wifi_failover_watchdog_control()` | 5949 | 5964 | oui | Start or stop the WiFi failover watchdog. |
| `api_rtsp_watchdog_status` | `api_rtsp_watchdog_status()` | 5972 | 5995 | oui | Get RTSP watchdog status including camera health. |
| `api_rtsp_watchdog_control` | `api_rtsp_watchdog_control()` | 5999 | 6018 | oui | Control RTSP watchdog. |
| `api_leds_status` | `api_leds_status()` | 6022 | 6025 | oui | API endpoint to get LED status. |
| `api_leds_set` | `api_leds_set()` | 6029 | 6066 | oui | API endpoint to set LED state. |
| `api_leds_boot_config` | `api_leds_boot_config()` | 6070 | 6077 | oui | API endpoint to get LED boot configuration. |
| `api_gpu_mem_get` | `api_gpu_mem_get()` | 6081 | 6084 | oui | API endpoint to get GPU memory. |
| `api_gpu_mem_set` | `api_gpu_mem_set()` | 6088 | 6097 | oui | API endpoint to set GPU memory. |
| `api_power_status` | `api_power_status()` | 6105 | 6115 | oui | API endpoint to get power/energy status of all components. |
| `api_power_bluetooth` | `api_power_bluetooth()` | 6119 | 6148 | oui | API endpoint to control Bluetooth. |
| `api_power_hdmi` | `api_power_hdmi()` | 6152 | 6181 | oui | API endpoint to control HDMI. |
| `api_power_audio` | `api_power_audio()` | 6185 | 6214 | oui | API endpoint to control Audio. |
| `api_power_cpu_freq` | `api_power_cpu_freq()` | 6218 | 6232 | oui | API endpoint to control CPU frequency. |
| `api_power_boot_config` | `api_power_boot_config()` | 6236 | 6245 | oui | API endpoint to get power boot configuration. |
| `api_power_apply_all` | `api_power_apply_all()` | 6249 | 6346 | oui | API endpoint to apply all power settings at once. |
| `api_system_reboot` | `api_system_reboot()` | 6350 | 6358 | oui | API endpoint to reboot the system. |
| `api_ntp_get` | `api_ntp_get()` | 6366 | 6431 | oui | Get NTP configuration and status. |
| `api_ntp_set` | `api_ntp_set()` | 6435 | 6465 | oui | Set NTP server configuration. |
| `api_ntp_sync` | `api_ntp_sync()` | 6469 | 6497 | oui | Force NTP synchronization. |
| `api_update_check` | `api_update_check()` | 6508 | 6562 | oui | Check for available updates from GitHub. |
| `api_update_check.version_tuple` | `version_tuple(v)` | 6541 | 6542 | non |  |
| `api_update_perform` | `api_update_perform()` | 6566 | 6664 | oui | Perform system update from GitHub. |
| `api_update_perform.log` | `log(msg)` | 6574 | 6576 | non |  |
| `get_pi_model` | `get_pi_model()` | 6671 | 6683 | non | Detect Raspberry Pi model for firmware update method selection. |
| `has_initramfs` | `has_initramfs()` | 6686 | 6718 | non | Check if system uses initramfs (incompatible with rpi-update). |
| `api_debug_firmware_check` | `api_debug_firmware_check()` | 6722 | 6832 | oui | Check for Raspberry Pi firmware updates. |
| `api_debug_firmware_update` | `api_debug_firmware_update()` | 6836 | 6901 | oui | Apply Raspberry Pi firmware update. |
| `api_debug_apt_update` | `api_debug_apt_update()` | 6905 | 6936 | oui | Run apt update to refresh package lists. |
| `api_debug_apt_upgradable` | `api_debug_apt_upgradable()` | 6940 | 6975 | oui | List packages that can be upgraded. |
| `api_debug_apt_upgrade` | `api_debug_apt_upgrade()` | 6979 | 7023 | oui | Run apt upgrade to update all packages. |
| `api_debug_system_uptime` | `api_debug_system_uptime()` | 7027 | 7049 | oui | Get system uptime. |
| `get_preferred_ip` | `get_preferred_ip()` | 7061 | 7113 | non | Get local IP address based on interface priority. |
| `get_local_ip` | `get_local_ip()` | 7115 | 7125 | non | Get local IP address of the device (fallback method). |
| `meeting_api_request` | `meeting_api_request(method, endpoint, data=…, config=…)` | 7127 | 7183 | non | Make a request to the Meeting API. |
| `get_mac_address` | `get_mac_address()` | 7190 | 7220 | non | Get MAC address of the primary network interface. |
| `get_public_ip` | `get_public_ip()` | 7223 | 7249 | non | Get public IP address of the device. |
| `get_cluster_from_api_url` | `get_cluster_from_api_url(api_url)` | 7252 | 7269 | non | Extract cluster name from Meeting API URL. |
| `build_heartbeat_payload` | `build_heartbeat_payload(config)` | 7272 | 7323 | non | Build the payload for heartbeat request. |
| `send_heartbeat_internal` | `send_heartbeat_internal(config=…)` | 7326 | 7345 | non | Internal function to send heartbeat. Returns (success, error_message). |
| `heartbeat_loop` | `heartbeat_loop()` | 7348 | 7391 | non | Background thread that sends heartbeats at regular intervals. |
| `start_heartbeat_thread` | `start_heartbeat_thread()` | 7394 | 7410 | non | Start the heartbeat background thread if not already running. |
| `stop_heartbeat_thread` | `stop_heartbeat_thread()` | 7413 | 7419 | non | Signal the heartbeat thread to stop (it will stop on next iteration). |
| `api_meeting_test` | `api_meeting_test()` | 7423 | 7464 | oui | Test Meeting API connection and start heartbeat if successful. |
| `api_meeting_heartbeat` | `api_meeting_heartbeat()` | 7468 | 7489 | oui | Send heartbeat to Meeting API (manual trigger). |
| `api_meeting_availability` | `api_meeting_availability()` | 7493 | 7507 | oui | Check device availability on Meeting API. |
| `api_meeting_device_info` | `api_meeting_device_info()` | 7511 | 7552 | oui | Get device info from Meeting API. |
| `api_meeting_request_tunnel` | `api_meeting_request_tunnel()` | 7556 | 7575 | oui | Request a tunnel from Meeting API. |
| `api_meeting_status` | `api_meeting_status()` | 7579 | 7631 | oui | Get Meeting integration status including heartbeat state. |
| `api_meeting_validate` | `api_meeting_validate()` | 7635 | 7685 | oui | Validate Meeting credentials without provisioning - just checks if valid. |
| `api_meeting_provision` | `api_meeting_provision()` | 7689 | 7804 | oui | Provision the device with Meeting API - validates credentials and burns a token. |
| `api_meeting_provision.delayed_reboot` | `delayed_reboot()` | 7784 | 7790 | non |  |
| `api_meeting_master_reset` | `api_meeting_master_reset()` | 7808 | 7844 | oui | Reset Meeting configuration (requires master code). |
| `change_hostname` | `change_hostname(new_hostname)` | 7847 | 7984 | non | Change the system hostname persistently (survives reboot, handles cloud-init). |
| `get_current_hostname` | `get_current_hostname()` | 7987 | 7993 | non | Get the current system hostname. |
| `load_onvif_config` | `load_onvif_config()` | 8003 | 8024 | non | Load ONVIF configuration from file. |
| `save_onvif_config` | `save_onvif_config(config)` | 8027 | 8042 | non | Save ONVIF configuration to file. |
| `sync_onvif_credentials_from_rtsp` | `sync_onvif_credentials_from_rtsp(main_config)` | 8045 | 8076 | non | Keep ONVIF WS-Security credentials aligned with RTSP credentials. |
| `is_onvif_service_running` | `is_onvif_service_running()` | 8079 | 8088 | non | Check if ONVIF service is running. |
| `get_onvif_device_name_from_meeting` | `get_onvif_device_name_from_meeting()` | 8091 | 8115 | non | Get ONVIF device name from Meeting API. |
| `api_onvif_status` | `api_onvif_status()` | 8119 | 8159 | oui | Get ONVIF service status and configuration. |
| `api_onvif_config` | `api_onvif_config()` | 8163 | 8213 | oui | Get or set ONVIF configuration. |
| `api_onvif_restart` | `api_onvif_restart()` | 8217 | 8238 | oui | Restart ONVIF service. |
| `on_startup` | `on_startup()` | 8245 | 8279 | non | Initialize application on startup. |
| `check_auto_ap_on_startup` | `check_auto_ap_on_startup()` | 8282 | 8335 | non | Check if Access Point should be auto-enabled on startup. |

---

## 5) Classes et méthodes

Aucune classe détectée.

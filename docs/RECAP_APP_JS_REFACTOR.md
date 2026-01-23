# Recap - Refactor app.js (Frontend)

This file summarizes the refactor of the monolithic `web-manager/static/js/app.js`
into maintainable modules without functional changes.

## Final JS Structure

- `web-manager/static/js/app.js` (bootstrap + init + timers)
- `web-manager/static/js/modules/ui_utils.js`
- `web-manager/static/js/modules/utils.js`
- `web-manager/static/js/modules/navigation.js`
- `web-manager/static/js/modules/home_status.js`
- `web-manager/static/js/modules/logs.js`
- `web-manager/static/js/modules/recordings.js`
- `web-manager/static/js/modules/network.js`
- `web-manager/static/js/modules/power.js`
- `web-manager/static/js/modules/meeting.js`
- `web-manager/static/js/modules/camera.js`
- `web-manager/static/js/modules/config_video.js`
- `web-manager/static/js/modules/diagnostics.js`

## Move Map (High Level)

- UI toast/clipboard -> `web-manager/static/js/modules/ui_utils.js`
- escapeHtml -> `web-manager/static/js/modules/utils.js`
- Tabs/URL/hash/RTSP auth status -> `web-manager/static/js/modules/navigation.js`
- Home status + service control + badge -> `web-manager/static/js/modules/home_status.js`
- Logs + SSE + clean/export -> `web-manager/static/js/modules/logs.js`
- Recordings + files UI -> `web-manager/static/js/modules/recordings.js`
- Network/WiFi/failover/AP -> `web-manager/static/js/modules/network.js`
- Power/energy + reboot overlay -> `web-manager/static/js/modules/power.js`
- Meeting + NTP/RTC + debug/terminal + ONVIF UI -> `web-manager/static/js/modules/meeting.js`
- Preview + camera controls + advanced + profiles -> `web-manager/static/js/modules/camera.js`
- Config + audio + resolutions + video -> `web-manager/static/js/modules/config_video.js`
- Diagnostics -> `web-manager/static/js/modules/diagnostics.js`

## Entry Point

`web-manager/static/js/app.js` remains the entry point and keeps the init
sequence, timers, and global state wiring.

## Smoke Test

Run on device:
```
.\debug_tools\smoke_web_manager.ps1
```

## Notes

- No behavior changes were introduced on purpose.
- Public API and routes remain unchanged.
- Each extraction kept the project executable.

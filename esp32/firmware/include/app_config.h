#pragma once

#ifndef RTSPFULL_ESP32_VERSION
#define RTSPFULL_ESP32_VERSION "0.1.0"
#endif

// WiFi AP fallback (premier boot / dépannage)
#ifndef WIFI_AP_SSID
#define WIFI_AP_SSID "RTSP-Full-ESP32"
#endif

#ifndef WIFI_AP_PASSWORD
#define WIFI_AP_PASSWORD "rtsp-full"
#endif

// HTTP
#ifndef HTTP_PORT
#define HTTP_PORT 80
#endif

// Stream MJPEG
#ifndef STREAM_BOUNDARY
#define STREAM_BOUNDARY "frame"
#endif

// FPS limit (0 = aucun)
#ifndef STREAM_FPS_LIMIT
#define STREAM_FPS_LIMIT 20
#endif


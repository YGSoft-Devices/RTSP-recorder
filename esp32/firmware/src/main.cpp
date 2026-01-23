#include <Arduino.h>

#include "app_config.h"
#include "camera_manager.h"
#include "config_store.h"
#include "meeting_manager.h"
#include "web_server.h"
#include "wifi_manager.h"

static CameraManager g_camera;
static ConfigStore g_store;
static WifiManager g_wifi;
static MeetingManager g_meeting;
static WebServerManager g_web;
static DeviceConfig g_config;

void setup() {
    Serial.begin(115200);
    delay(200);

    if (!g_store.begin()) {
        Serial.println("[store] failed to init Preferences");
    }
    g_config = g_store.load();

    (void)g_wifi.begin(g_config);

    if (!g_camera.begin(g_config.camera)) {
        Serial.println("[camera] init failed");
    } else {
        Serial.printf("[camera] sensor=%s psram=%s\n", g_camera.sensorName(), psramFound() ? "yes" : "no");
    }

    g_meeting.begin(&g_config);

    if (!g_web.begin(&g_camera, &g_store, &g_config, &g_meeting)) {
        Serial.println("[web] start failed");
    }

    Serial.printf("[boot] version=%s ip=%s\n", RTSPFULL_ESP32_VERSION, g_wifi.ipString().c_str());
}

void loop() {
    g_web.loop();
    g_meeting.loop();
    delay(2);
}

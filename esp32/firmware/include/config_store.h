#pragma once

#include <Arduino.h>
#include <Preferences.h>
#include "camera_manager.h"

struct DeviceConfig {
    String wifi_ssid;
    String wifi_password;
    CameraSettings camera;

    // Meeting (optionnel)
    bool meeting_enabled = false;
    bool meeting_provisioned = false;
    String meeting_api_url;
    String meeting_device_key;
    uint32_t meeting_heartbeat_interval = 30;
};

class ConfigStore {
public:
    bool begin();
    DeviceConfig load();
    bool save(const DeviceConfig& cfg);
    bool clearWiFi();

private:
    Preferences prefs_;
};

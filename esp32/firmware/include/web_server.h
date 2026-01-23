#pragma once

#include <Arduino.h>

class CameraManager;
class ConfigStore;
class MeetingManager;
struct DeviceConfig;

class WebServerManager {
public:
    bool begin(CameraManager* camera, ConfigStore* store, DeviceConfig* config, MeetingManager* meeting);
    void loop();

private:
    CameraManager* camera_ = nullptr;
    ConfigStore* store_ = nullptr;
    DeviceConfig* config_ = nullptr;
    MeetingManager* meeting_ = nullptr;
};

#pragma once

#include <Arduino.h>

struct DeviceConfig;

class WifiManager {
public:
    bool begin(const DeviceConfig& cfg);
    bool isApMode() const;
    String modeString() const;
    String ipString() const;
    int rssi() const;

private:
    bool ap_mode_ = false;
};


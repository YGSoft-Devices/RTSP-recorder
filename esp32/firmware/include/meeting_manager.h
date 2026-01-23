#pragma once

#include <Arduino.h>

struct DeviceConfig;

struct MeetingState {
    bool configured = false;
    bool enabled = false;
    bool connected = false;
    uint32_t last_http_code = 0;
    unsigned long last_heartbeat_ms = 0;
    String last_error;
};

class MeetingManager {
public:
    void begin(DeviceConfig* config);
    void loop();

    bool sendHeartbeat();
    MeetingState state() const;

private:
    String buildApiUrl(const String& baseUrl, const String& endpoint) const;
    bool shouldHeartbeatNow() const;

    DeviceConfig* config_ = nullptr;
    MeetingState state_{};
};


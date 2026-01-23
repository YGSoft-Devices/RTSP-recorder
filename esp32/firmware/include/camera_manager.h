#pragma once

#include <Arduino.h>
#include <esp_camera.h>

struct CameraSettings {
    framesize_t frame_size = FRAMESIZE_VGA;
    int jpeg_quality = 12; // 10-63 (plus bas = meilleure qualité)
    int brightness = 0;    // -2..2 (selon capteur)
    int contrast = 0;      // -2..2
    int saturation = 0;    // -2..2
    bool vflip = false;
    bool hmirror = false;
};

class CameraManager {
public:
    bool begin(const CameraSettings& settings);
    bool apply(const CameraSettings& settings);
    CameraSettings current() const;
    const char* sensorName() const;
    bool isReady() const;

private:
    bool ready_ = false;
    CameraSettings current_{};
    String sensor_name_ = "unknown";
};


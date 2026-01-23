#include "camera_manager.h"

#include "camera_board.h"

static String sensor_name_from_pid(int pid) {
    switch (pid) {
        case OV2640_PID: return "OV2640";
        case OV5640_PID: return "OV5640";
        case OV3660_PID: return "OV3660";
        default: return String("PID_") + String(pid, HEX);
    }
}

bool CameraManager::begin(const CameraSettings& settings) {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;

    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sccb_sda = SIOD_GPIO_NUM;
    config.pin_sccb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;

    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;

    // Frame parameters (PSRAM attendu)
    config.frame_size = settings.frame_size;
    config.jpeg_quality = settings.jpeg_quality;
    config.fb_count = psramFound() ? 2 : 1;
    config.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
#ifdef CAMERA_GRAB_LATEST
    config.grab_mode = CAMERA_GRAB_LATEST;
#endif

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ready_ = false;
        return false;
    }

    sensor_t* s = esp_camera_sensor_get();
    if (s && s->id.PID) {
        sensor_name_ = sensor_name_from_pid(s->id.PID);
    }

    ready_ = true;
    return apply(settings);
}

bool CameraManager::apply(const CameraSettings& settings) {
    if (!ready_) return false;

    sensor_t* s = esp_camera_sensor_get();
    if (!s) return false;

    s->set_framesize(s, settings.frame_size);
    s->set_quality(s, settings.jpeg_quality);
    s->set_brightness(s, settings.brightness);
    s->set_contrast(s, settings.contrast);
    s->set_saturation(s, settings.saturation);
    s->set_vflip(s, settings.vflip ? 1 : 0);
    s->set_hmirror(s, settings.hmirror ? 1 : 0);

    current_ = settings;
    return true;
}

CameraSettings CameraManager::current() const {
    return current_;
}

const char* CameraManager::sensorName() const {
    return sensor_name_.c_str();
}

bool CameraManager::isReady() const {
    return ready_;
}

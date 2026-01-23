#include "config_store.h"

static const char* kNamespace = "rtspfull";

bool ConfigStore::begin() {
    return prefs_.begin(kNamespace, false);
}

DeviceConfig ConfigStore::load() {
    DeviceConfig cfg;
    cfg.wifi_ssid = prefs_.getString("wifi_ssid", "");
    cfg.wifi_password = prefs_.getString("wifi_pass", "");

    cfg.camera.frame_size = static_cast<framesize_t>(prefs_.getUChar("fs", FRAMESIZE_VGA));
    cfg.camera.jpeg_quality = prefs_.getUChar("jq", 12);
    cfg.camera.brightness = prefs_.getChar("br", 0);
    cfg.camera.contrast = prefs_.getChar("ct", 0);
    cfg.camera.saturation = prefs_.getChar("st", 0);
    cfg.camera.vflip = prefs_.getBool("vf", false);
    cfg.camera.hmirror = prefs_.getBool("hm", false);

    cfg.meeting_enabled = prefs_.getBool("mt_en", false);
    cfg.meeting_provisioned = prefs_.getBool("mt_pr", false);
    cfg.meeting_api_url = prefs_.getString("mt_url", "");
    cfg.meeting_device_key = prefs_.getString("mt_key", "");
    cfg.meeting_heartbeat_interval = prefs_.getUInt("mt_int", 30);

    return cfg;
}

bool ConfigStore::save(const DeviceConfig& cfg) {
    bool ok = true;

    // Strings: Preferences retourne la longueur écrite (0 si vide)
    prefs_.putString("wifi_ssid", cfg.wifi_ssid);
    prefs_.putString("wifi_pass", cfg.wifi_password);

    ok = ok && prefs_.putUChar("fs", static_cast<uint8_t>(cfg.camera.frame_size)) > 0;
    ok = ok && prefs_.putUChar("jq", static_cast<uint8_t>(cfg.camera.jpeg_quality)) > 0;
    ok = ok && prefs_.putChar("br", static_cast<int8_t>(cfg.camera.brightness)) > 0;
    ok = ok && prefs_.putChar("ct", static_cast<int8_t>(cfg.camera.contrast)) > 0;
    ok = ok && prefs_.putChar("st", static_cast<int8_t>(cfg.camera.saturation)) > 0;
    ok = ok && prefs_.putBool("vf", cfg.camera.vflip) > 0;
    ok = ok && prefs_.putBool("hm", cfg.camera.hmirror) > 0;

    ok = ok && prefs_.putBool("mt_en", cfg.meeting_enabled) > 0;
    ok = ok && prefs_.putBool("mt_pr", cfg.meeting_provisioned) > 0;
    prefs_.putString("mt_url", cfg.meeting_api_url);
    prefs_.putString("mt_key", cfg.meeting_device_key);
    ok = ok && prefs_.putUInt("mt_int", cfg.meeting_heartbeat_interval) > 0;
    return ok;
}

bool ConfigStore::clearWiFi() {
    bool ok = true;
    ok = ok && prefs_.remove("wifi_ssid");
    ok = ok && prefs_.remove("wifi_pass");
    return ok;
}

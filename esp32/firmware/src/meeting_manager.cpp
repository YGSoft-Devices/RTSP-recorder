#include "meeting_manager.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include <ArduinoJson.h>

#include "config_store.h"

void MeetingManager::begin(DeviceConfig* config) {
    config_ = config;
}

static String trim_slashes(String s) {
    while (s.endsWith("/")) s.remove(s.length() - 1);
    return s;
}

String MeetingManager::buildApiUrl(const String& baseUrl, const String& endpoint) const {
    String base = trim_slashes(baseUrl);
    String ep = endpoint;
    if (!ep.startsWith("/")) ep = "/" + ep;

    if (base.endsWith("/api") && ep.startsWith("/api/")) {
        ep = ep.substring(4); // remove "/api"
    }
    return base + ep;
}

bool MeetingManager::shouldHeartbeatNow() const {
    if (!config_) return false;
    if (!config_->meeting_enabled) return false;
    if (config_->meeting_api_url.length() == 0) return false;
    if (config_->meeting_device_key.length() == 0) return false;
    if (WiFi.status() != WL_CONNECTED) return false;

    const unsigned long now = millis();
    const unsigned long last = state_.last_heartbeat_ms;
    const uint32_t interval = config_->meeting_heartbeat_interval > 0 ? config_->meeting_heartbeat_interval : 30;
    const unsigned long interval_ms = (unsigned long)interval * 1000UL;
    return (last == 0) || (now - last >= interval_ms);
}

void MeetingManager::loop() {
    state_.enabled = config_ && config_->meeting_enabled;
    state_.configured = config_ && config_->meeting_api_url.length() > 0 && config_->meeting_device_key.length() > 0;

    if (!shouldHeartbeatNow()) return;
    (void)sendHeartbeat();
}

bool MeetingManager::sendHeartbeat() {
    state_.enabled = config_ && config_->meeting_enabled;
    state_.configured = config_ && config_->meeting_api_url.length() > 0 && config_->meeting_device_key.length() > 0;

    if (!state_.enabled) {
        state_.connected = false;
        state_.last_error = "meeting_disabled";
        return false;
    }
    if (!state_.configured) {
        state_.connected = false;
        state_.last_error = "meeting_not_configured";
        return false;
    }
    if (WiFi.status() != WL_CONNECTED) {
        state_.connected = false;
        state_.last_error = "wifi_not_connected";
        return false;
    }

    const String endpoint = "/api/devices/" + config_->meeting_device_key + "/online";
    const String url = buildApiUrl(config_->meeting_api_url, endpoint);

    JsonDocument doc;
    doc["ip_address"] = WiFi.localIP().toString();
    doc["mac"] = WiFi.macAddress();
    doc["device_type"] = "esp32";
    doc["services"]["http"] = 1;
    doc["services"]["mjpeg"] = 1;
    doc["uptime_sec"] = (uint32_t)(millis() / 1000UL);

    String body;
    serializeJson(doc, body);

    HTTPClient http;
    http.setTimeout(8000);
    if (!http.begin(url)) {
        state_.connected = false;
        state_.last_error = "http_begin_failed";
        return false;
    }
    http.addHeader("Content-Type", "application/json");

    const int code = http.POST((uint8_t*)body.c_str(), body.length());
    state_.last_http_code = code > 0 ? (uint32_t)code : 0;

    if (code >= 200 && code < 300) {
        state_.connected = true;
        state_.last_error = "";
        state_.last_heartbeat_ms = millis();
        http.end();
        return true;
    }

    state_.connected = false;
    String resp = http.getString();
    http.end();

    state_.last_error = (code <= 0) ? "http_post_failed" : (String("http_") + String(code) + ":" + resp.substring(0, 120));
    return false;
}

MeetingState MeetingManager::state() const {
    return state_;
}

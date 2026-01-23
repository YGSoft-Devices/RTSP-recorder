#include "web_server.h"

#include <ArduinoJson.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <esp_http_server.h>

#include "app_config.h"
#include "camera_manager.h"
#include "config_store.h"
#include "meeting_manager.h"

static httpd_handle_t g_httpd = nullptr;
static CameraManager* g_camera = nullptr;
static ConfigStore* g_store = nullptr;
static DeviceConfig* g_cfg = nullptr;
static MeetingManager* g_meeting = nullptr;

static esp_err_t send_json(httpd_req_t* req, JsonDocument& doc, int status = 200) {
    String body;
    serializeJson(doc, body);

    httpd_resp_set_status(req, status == 200 ? "200 OK" : (status == 400 ? "400 Bad Request" : "500 Internal Server Error"));
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, body.c_str(), body.length());
}

static String read_req_body(httpd_req_t* req) {
    const size_t len = req->content_len;
    String body;
    body.reserve(len);

    char buf[256];
    size_t remaining = len;
    while (remaining > 0) {
        const int to_read = (remaining > sizeof(buf)) ? sizeof(buf) : (int)remaining;
        const int r = httpd_req_recv(req, buf, to_read);
        if (r <= 0) break;
        body.concat(String(buf).substring(0, r));
        remaining -= r;
    }
    return body;
}

static esp_err_t status_handler(httpd_req_t* req) {
    JsonDocument doc;
    doc["version"] = RTSPFULL_ESP32_VERSION;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["psram"] = psramFound();
    doc["ip"] = WiFi.localIP().toString();
    doc["mac"] = WiFi.macAddress();
    doc["rssi"] = WiFi.isConnected() ? WiFi.RSSI() : 0;
    doc["wifi_mode"] = (WiFi.getMode() == WIFI_AP) ? "ap" : (WiFi.getMode() == WIFI_STA ? "sta" : "other");
    doc["camera_ready"] = g_camera && g_camera->isReady();
    doc["sensor"] = g_camera ? g_camera->sensorName() : "unknown";

    if (g_meeting) {
        MeetingState st = g_meeting->state();
        doc["meeting"]["configured"] = st.configured;
        doc["meeting"]["enabled"] = st.enabled;
        doc["meeting"]["connected"] = st.connected;
        doc["meeting"]["last_http_code"] = st.last_http_code;
        doc["meeting"]["last_error"] = st.last_error;
        doc["meeting"]["last_heartbeat_ms"] = st.last_heartbeat_ms;
        doc["meeting"]["last_heartbeat_ago_ms"] = st.last_heartbeat_ms ? (uint32_t)(millis() - st.last_heartbeat_ms) : 0;
    }

    if (g_camera) {
        CameraSettings s = g_camera->current();
        doc["camera"]["frame_size"] = (int)s.frame_size;
        doc["camera"]["jpeg_quality"] = s.jpeg_quality;
        doc["camera"]["brightness"] = s.brightness;
        doc["camera"]["contrast"] = s.contrast;
        doc["camera"]["saturation"] = s.saturation;
        doc["camera"]["vflip"] = s.vflip;
        doc["camera"]["hmirror"] = s.hmirror;
    }

    return send_json(req, doc);
}

static esp_err_t config_get_handler(httpd_req_t* req) {
    JsonDocument doc;
    doc["version"] = RTSPFULL_ESP32_VERSION;
    doc["wifi"]["ssid"] = g_cfg ? g_cfg->wifi_ssid : "";
    doc["wifi"]["has_password"] = g_cfg ? (g_cfg->wifi_password.length() > 0) : false;

    if (g_cfg) {
        doc["camera"]["frame_size"] = (int)g_cfg->camera.frame_size;
        doc["camera"]["jpeg_quality"] = g_cfg->camera.jpeg_quality;
        doc["camera"]["brightness"] = g_cfg->camera.brightness;
        doc["camera"]["contrast"] = g_cfg->camera.contrast;
        doc["camera"]["saturation"] = g_cfg->camera.saturation;
        doc["camera"]["vflip"] = g_cfg->camera.vflip;
        doc["camera"]["hmirror"] = g_cfg->camera.hmirror;

        doc["meeting"]["enabled"] = g_cfg->meeting_enabled;
        doc["meeting"]["provisioned"] = g_cfg->meeting_provisioned;
        doc["meeting"]["api_url"] = g_cfg->meeting_api_url;
        doc["meeting"]["device_key"] = g_cfg->meeting_device_key;
        doc["meeting"]["heartbeat_interval"] = g_cfg->meeting_heartbeat_interval;
    }

    return send_json(req, doc);
}

static bool apply_config_from_json(const JsonDocument& doc, String& err) {
    if (!g_cfg) {
        err = "config_not_ready";
        return false;
    }

    if (doc["wifi"].is<JsonObject>()) {
        if (doc["wifi"]["ssid"].is<const char*>()) g_cfg->wifi_ssid = doc["wifi"]["ssid"].as<const char*>();
        if (doc["wifi"]["password"].is<const char*>()) g_cfg->wifi_password = doc["wifi"]["password"].as<const char*>();
    }

    if (doc["camera"].is<JsonObject>()) {
        if (doc["camera"]["frame_size"].is<int>()) g_cfg->camera.frame_size = (framesize_t)doc["camera"]["frame_size"].as<int>();
        if (doc["camera"]["jpeg_quality"].is<int>()) g_cfg->camera.jpeg_quality = doc["camera"]["jpeg_quality"].as<int>();
        if (doc["camera"]["brightness"].is<int>()) g_cfg->camera.brightness = doc["camera"]["brightness"].as<int>();
        if (doc["camera"]["contrast"].is<int>()) g_cfg->camera.contrast = doc["camera"]["contrast"].as<int>();
        if (doc["camera"]["saturation"].is<int>()) g_cfg->camera.saturation = doc["camera"]["saturation"].as<int>();
        if (doc["camera"]["vflip"].is<bool>()) g_cfg->camera.vflip = doc["camera"]["vflip"].as<bool>();
        if (doc["camera"]["hmirror"].is<bool>()) g_cfg->camera.hmirror = doc["camera"]["hmirror"].as<bool>();
    }

    if (doc["meeting"].is<JsonObject>()) {
        if (!g_cfg->meeting_provisioned) {
            if (doc["meeting"]["enabled"].is<bool>()) g_cfg->meeting_enabled = doc["meeting"]["enabled"].as<bool>();
            if (doc["meeting"]["api_url"].is<const char*>()) g_cfg->meeting_api_url = doc["meeting"]["api_url"].as<const char*>();
            if (doc["meeting"]["device_key"].is<const char*>()) g_cfg->meeting_device_key = doc["meeting"]["device_key"].as<const char*>();
            if (doc["meeting"]["heartbeat_interval"].is<int>()) g_cfg->meeting_heartbeat_interval = (uint32_t)doc["meeting"]["heartbeat_interval"].as<int>();
            if (doc["meeting"]["provisioned"].is<bool>()) g_cfg->meeting_provisioned = doc["meeting"]["provisioned"].as<bool>();
        }
    }

    if (g_camera && g_camera->isReady()) {
        (void)g_camera->apply(g_cfg->camera);
    }
    if (g_store) {
        (void)g_store->save(*g_cfg);
    }

    return true;
}

static esp_err_t config_post_handler(httpd_req_t* req) {
    const String body = read_req_body(req);

    JsonDocument doc;
    DeserializationError jerr = deserializeJson(doc, body);
    if (jerr) {
        JsonDocument out;
        out["ok"] = false;
        out["error"] = "invalid_json";
        return send_json(req, out, 400);
    }

    String err;
    if (!apply_config_from_json(doc, err)) {
        JsonDocument out;
        out["ok"] = false;
        out["error"] = err;
        return send_json(req, out, 400);
    }

    JsonDocument out;
    out["ok"] = true;
    out["note"] = "wifi_changes_require_reboot";
    return send_json(req, out);
}

static esp_err_t reboot_post_handler(httpd_req_t* req) {
    JsonDocument out;
    out["ok"] = true;
    send_json(req, out);
    delay(200);
    ESP.restart();
    return ESP_OK;
}

static esp_err_t meeting_heartbeat_post_handler(httpd_req_t* req) {
    JsonDocument out;
    if (!g_meeting) {
        out["ok"] = false;
        out["error"] = "meeting_not_ready";
        return send_json(req, out, 500);
    }

    const bool ok = g_meeting->sendHeartbeat();
    MeetingState st = g_meeting->state();
    out["ok"] = ok;
    out["meeting"]["configured"] = st.configured;
    out["meeting"]["enabled"] = st.enabled;
    out["meeting"]["connected"] = st.connected;
    out["meeting"]["last_http_code"] = st.last_http_code;
    out["meeting"]["last_error"] = st.last_error;
    return send_json(req, out, ok ? 200 : 400);
}

static esp_err_t meeting_status_get_handler(httpd_req_t* req) {
    JsonDocument out;
    out["ok"] = true;

    if (!g_cfg) {
        out["ok"] = false;
        out["error"] = "config_not_ready";
        return send_json(req, out, 500);
    }

    out["config"]["enabled"] = g_cfg->meeting_enabled;
    out["config"]["provisioned"] = g_cfg->meeting_provisioned;
    out["config"]["api_url"] = g_cfg->meeting_api_url;
    out["config"]["device_key"] = g_cfg->meeting_device_key;
    out["config"]["heartbeat_interval"] = g_cfg->meeting_heartbeat_interval;

    if (g_meeting) {
        MeetingState st = g_meeting->state();
        out["state"]["configured"] = st.configured;
        out["state"]["enabled"] = st.enabled;
        out["state"]["connected"] = st.connected;
        out["state"]["last_http_code"] = st.last_http_code;
        out["state"]["last_error"] = st.last_error;
        out["state"]["last_heartbeat_ms"] = st.last_heartbeat_ms;
        out["state"]["last_heartbeat_ago_ms"] = st.last_heartbeat_ms ? (uint32_t)(millis() - st.last_heartbeat_ms) : 0;
    } else {
        out["state"]["error"] = "meeting_not_ready";
    }

    return send_json(req, out);
}

static esp_err_t factory_reset_post_handler(httpd_req_t* req) {
    if (g_store) (void)g_store->clearWiFi();
    JsonDocument out;
    out["ok"] = true;
    out["note"] = "rebooting";
    send_json(req, out);
    delay(200);
    ESP.restart();
    return ESP_OK;
}

static esp_err_t file_handler(httpd_req_t* req) {
    String path = req->uri;
    int q = path.indexOf('?');
    if (q >= 0) path = path.substring(0, q);
    if (path == "/") path = "/index.html";

    if (!LittleFS.exists(path)) {
        httpd_resp_set_status(req, "404 Not Found");
        return httpd_resp_send(req, "Not Found", HTTPD_RESP_USE_STRLEN);
    }

    File f = LittleFS.open(path, "r");
    if (!f) {
        httpd_resp_set_status(req, "500 Internal Server Error");
        return httpd_resp_send(req, "Failed to open file", HTTPD_RESP_USE_STRLEN);
    }

    if (path.endsWith(".html")) httpd_resp_set_type(req, "text/html");
    else if (path.endsWith(".css")) httpd_resp_set_type(req, "text/css");
    else if (path.endsWith(".js")) httpd_resp_set_type(req, "application/javascript");
    else if (path.endsWith(".ico")) httpd_resp_set_type(req, "image/x-icon");
    else httpd_resp_set_type(req, "application/octet-stream");

    char buf[1024];
    while (true) {
        int r = f.readBytes(buf, sizeof(buf));
        if (r <= 0) break;
        esp_err_t err = httpd_resp_send_chunk(req, buf, r);
        if (err != ESP_OK) break;
    }
    f.close();
    httpd_resp_send_chunk(req, nullptr, 0);
    return ESP_OK;
}

static esp_err_t stream_handler(httpd_req_t* req) {
    if (!g_camera || !g_camera->isReady()) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_send(req, "Camera not ready", HTTPD_RESP_USE_STRLEN);
    }

    httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=" STREAM_BOUNDARY);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    const uint32_t fps_limit = STREAM_FPS_LIMIT;
    uint32_t last_ms = 0;

    while (true) {
        if (fps_limit > 0) {
            const uint32_t now = millis();
            const uint32_t frame_ms = 1000 / fps_limit;
            if (now - last_ms < frame_ms) {
                delay(1);
                continue;
            }
            last_ms = now;
        }

        camera_fb_t* fb = esp_camera_fb_get();
        if (!fb) continue;

        char part_buf[128];
        const int hlen = snprintf(
            part_buf, sizeof(part_buf),
            "\r\n--" STREAM_BOUNDARY "\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n",
            (unsigned)fb->len
        );

        if (httpd_resp_send_chunk(req, part_buf, hlen) != ESP_OK) {
            esp_camera_fb_return(fb);
            break;
        }
        if (httpd_resp_send_chunk(req, (const char*)fb->buf, fb->len) != ESP_OK) {
            esp_camera_fb_return(fb);
            break;
        }

        esp_camera_fb_return(fb);
    }

    return ESP_OK;
}

static void register_uri(const char* uri, httpd_method_t method, esp_err_t (*handler)(httpd_req_t*)) {
    httpd_uri_t h;
    memset(&h, 0, sizeof(h));
    h.uri = uri;
    h.method = method;
    h.handler = handler;
    httpd_register_uri_handler(g_httpd, &h);
}

bool WebServerManager::begin(CameraManager* camera, ConfigStore* store, DeviceConfig* config, MeetingManager* meeting) {
    g_camera = camera;
    g_store = store;
    g_cfg = config;
    g_meeting = meeting;

    if (!LittleFS.begin(true)) {
        Serial.println("[fs] LittleFS mount failed");
        return false;
    }

    httpd_config_t http_config = HTTPD_DEFAULT_CONFIG();
    http_config.server_port = HTTP_PORT;
    http_config.uri_match_fn = httpd_uri_match_wildcard;

    if (httpd_start(&g_httpd, &http_config) != ESP_OK) {
        Serial.println("[web] httpd_start failed");
        return false;
    }

    register_uri("/api/status", HTTP_GET, status_handler);
    register_uri("/api/config", HTTP_GET, config_get_handler);
    register_uri("/api/config", HTTP_POST, config_post_handler);
    register_uri("/api/meeting/status", HTTP_GET, meeting_status_get_handler);
    register_uri("/api/meeting/heartbeat", HTTP_POST, meeting_heartbeat_post_handler);
    register_uri("/api/reboot", HTTP_POST, reboot_post_handler);
    register_uri("/api/factory_reset", HTTP_POST, factory_reset_post_handler);
    register_uri("/stream", HTTP_GET, stream_handler);
    register_uri("/*", HTTP_GET, file_handler);

    return true;
}

void WebServerManager::loop() {
    (void)0;
}

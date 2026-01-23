#include "wifi_manager.h"

#include <WiFi.h>
#include "app_config.h"
#include "config_store.h"

bool WifiManager::begin(const DeviceConfig& cfg) {
    WiFi.mode(WIFI_STA);

    if (cfg.wifi_ssid.length() > 0) {
        WiFi.begin(cfg.wifi_ssid.c_str(), cfg.wifi_password.c_str());
        unsigned long start = millis();
        while (WiFi.status() != WL_CONNECTED && millis() - start < 12000) {
            delay(200);
        }
        if (WiFi.status() == WL_CONNECTED) {
            ap_mode_ = false;
            return true;
        }
    }

    // Fallback AP
    WiFi.mode(WIFI_AP);
    ap_mode_ = true;
    return WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASSWORD);
}

bool WifiManager::isApMode() const {
    return ap_mode_;
}

String WifiManager::modeString() const {
    if (WiFi.getMode() == WIFI_AP) return "ap";
    if (WiFi.getMode() == WIFI_STA) return "sta";
    return "other";
}

String WifiManager::ipString() const {
    if (WiFi.getMode() == WIFI_AP) return WiFi.softAPIP().toString();
    return WiFi.localIP().toString();
}

int WifiManager::rssi() const {
    return WiFi.isConnected() ? WiFi.RSSI() : 0;
}


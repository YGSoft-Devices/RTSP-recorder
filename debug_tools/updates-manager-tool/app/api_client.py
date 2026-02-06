from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logger import redact_headers


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None, details: Any | None = None):
        super().__init__(message)
        self.status = status
        self.details = details


@dataclass
class ApiConfig:
    base_url: str
    token: Optional[str]
    timeout: int = 20
    retries: int = 3


class ApiClient:
    def __init__(self, cfg: ApiConfig, logger=None, api_logger=None):
        self.cfg = cfg
        self.logger = logger
        self.api_logger = api_logger
        self.session = requests.Session()
        retry = Retry(
            total=cfg.retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.cfg.token:
            headers["Authorization"] = f"Bearer {self.cfg.token}"
        return headers

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = self.cfg.base_url.rstrip("/") + path
        headers = self._headers()
        extra_headers = kwargs.pop("headers", {})
        headers.update(extra_headers)

        if self.api_logger:
            safe_headers = redact_headers(headers)
            self.api_logger.info("%s %s headers=%s", method, url, safe_headers)

        resp = self.session.request(method, url, headers=headers, timeout=self.cfg.timeout, **kwargs)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(float(retry_after))
                except Exception:
                    time.sleep(1.0)

        text = resp.text or ""
        data: Dict[str, Any] = {}
        if text:
            try:
                data = resp.json()
            except Exception:
                data = {"raw": text}

        if self.api_logger:
            self.api_logger.info("%s %s status=%s", method, url, resp.status_code)

        if resp.status_code >= 400:
            raise ApiError(data.get("error") or data.get("message") or "API error", resp.status_code, data)

        if isinstance(data, dict) and data.get("ok") is False:
            err = data.get("error") or {}
            raise ApiError(err.get("message") or "API error", resp.status_code, data)

        return data

    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("DELETE", path, **kwargs)

    # --- Update channels ---
    def list_channels(self) -> Dict[str, Any]:
        return self.get("/api/admin/update-channels")

    def create_channel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.post("/api/admin/update-channels", json=payload)

    def update_channel(self, channel_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.put(f"/api/admin/update-channels/{channel_id}", json=payload)

    def delete_channel(self, channel_id: int) -> Dict[str, Any]:
        return self.delete(f"/api/admin/update-channels/{channel_id}")

    # --- Publishing ---
    def publish_update(self, files: Dict[str, Any], data: Dict[str, Any] = None, endpoint: str = "/api/admin/updates/publish") -> Dict[str, Any]:
        return self.post(endpoint, files=files, data=data)

    def verify_artifacts(self, device_type: str, distribution: str, version: str) -> Dict[str, Any]:
        return self.get(
            "/api/admin/updates/verify",
            params={"device_type": device_type, "distribution": distribution, "version": version},
        )

    def list_device_types(self) -> Dict[str, Any]:
        """Get all device types and their distributions."""
        return self.get("/api/admin/updates/device-types")

    def list_versions(self, device_type: str, distribution: str) -> Dict[str, Any]:
        """Get available versions for a device type/distribution."""
        return self.get("/api/admin/updates/versions", params={"device_type": device_type, "distribution": distribution})

    # --- Fleet / History ---
    def list_device_updates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.get("/api/admin/device-updates", params=params)

    def list_update_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.get("/api/admin/device-update-history", params=params)

    def export_device_updates(self, fmt: str = "csv") -> Dict[str, Any]:
        return self.get("/api/admin/device-updates/export", params={"format": fmt})

    # --- Device Registration (Meeting) ---
    def register_device(self, device_key: str, token_code: str, device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Register device with Meeting server.
        
        Args:
            device_key: Unique device identifier
            token_code: One-time registration token (will be burned)
            device_info: Device information (hostname, mac, ip, etc)
        
        Returns:
            Response with ok=true on success, token is burned after registration
        """
        # Remove Authorization header for registration (uses token_code instead)
        headers = {"Accept": "application/json"}
        payload = {
            "token_code": token_code,
            **device_info
        }
        url = self.cfg.base_url.rstrip("/") + f"/api/devices/{device_key}/register"
        resp = self.session.post(url, json=payload, headers=headers, timeout=self.cfg.timeout)
        
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text or ""}
        
        if resp.status_code >= 400:
            raise ApiError(data.get("error") or data.get("message") or "Registration failed", resp.status_code, data)
        
        return data

    def send_heartbeat(self, device_key: str, heartbeat_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send heartbeat to Meeting server with device status.
        
        Supported fields (all optional):
        - ip_address: IPv4/IPv6
        - ip_lan: LAN IPv4/IPv6
        - ip_public: Public IPv4/IPv6
        - mac: MAC address (AA:BB:CC:DD:EE:FF)
        - cluster_ip: Cluster IP(s)
        - note: Optional status note
        """
        return self.post(f"/api/devices/{device_key}/online", json=heartbeat_data)

    def get_ssh_hostkey(self) -> str:
        """Fetch Meeting server's SSH public host key(s)."""
        headers = {"Accept": "text/plain"}
        url = self.cfg.base_url.rstrip("/") + "/api/ssh-hostkey"
        resp = self.session.get(url, headers=headers, timeout=self.cfg.timeout)
        
        if resp.status_code >= 400:
            raise ApiError("Failed to fetch SSH hostkey", resp.status_code)
        
        return resp.text

    def publish_ssh_key(self, device_key: str, pubkey: str) -> Dict[str, Any]:
        """Publish device SSH public key to Meeting server."""
        return self.put(f"/api/devices/{device_key}/ssh-key", json={"pubkey": pubkey})

    def get_device_info(self, device_key: str) -> Dict[str, Any]:
        """Get device information from Meeting server."""
        return self.get(f"/api/devices/{device_key}")

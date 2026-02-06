"""Device registration and heartbeat management for Meeting integration."""
from __future__ import annotations

import json
import re
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .api_client import ApiClient, ApiError
from .storage import get_app_dir
import logging

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages device registration, identification, and heartbeat with Meeting server."""

    def __init__(self):
        """Initialize device manager."""
        self.app_dir = get_app_dir()
        self.device_file = self.app_dir / "device_info.json"
        self.device_key: Optional[str] = None
        self.token_code: Optional[str] = None
        self.server_url: str = "https://meeting.ygsoft.fr"
        self.device_info: Dict[str, Any] = {}
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_stop = threading.Event()

    def is_registered(self) -> bool:
        """Check if device is registered."""
        return self.device_key is not None

    # --- Device Key Management ---

    def load_device_key(self) -> Optional[str]:
        """Load device_key from local storage."""
        if self.device_file.exists():
            try:
                with open(self.device_file) as f:
                    data = json.load(f)
                    self.device_key = data.get("device_key")
                    self.token_code = data.get("token_code")
                    self.server_url = data.get("server_url", "https://meeting.ygsoft.fr")
                    self.device_info = data.get("device_info", {})
                    return self.device_key
            except Exception as e:
                logger.error(f"Failed to load device key: {e}")
        return None

    def save_device_key(self, device_key: str, token_code: str, server_url: str, device_info: Dict[str, Any] = None) -> bool:
        """Save device_key and info to local storage."""
        try:
            self.device_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.device_file, "w") as f:
                json.dump(
                    {
                        "device_key": device_key,
                        "token_code": token_code,
                        "server_url": server_url,
                        "device_info": device_info or {},
                        "registered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    },
                    f,
                    indent=2,
                )
            self.device_key = device_key
            self.token_code = token_code
            self.server_url = server_url
            self.device_info = device_info or {}
            logger.info(f"Saved device key: {device_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save device key: {e}")
            return False

    def clear_device_key(self) -> bool:
        """Clear stored device key."""
        try:
            if self.device_file.exists():
                self.device_file.unlink()
            self.device_key = None
            self.device_info = {}
            return True
        except Exception as e:
            logger.error(f"Failed to clear device key: {e}")
            return False

    # --- Device Info Collection ---

    def collect_device_info(self) -> Dict[str, Any]:
        """Collect device information to send to Meeting server."""
        info = {}

        # Hostname
        try:
            info["hostname"] = socket.gethostname()
        except Exception:
            pass

        # IP addresses
        info["ip_address"] = self._get_ip_address()
        info["ip_lan"] = self._get_lan_ip()
        info["ip_public"] = self._get_public_ip()

        # MAC address
        info["mac"] = self._get_mac_address()

        # Additional info
        info["note"] = "Updates Manager Tool"

        return {k: v for k, v in info.items() if v is not None}

    def _get_ip_address(self) -> Optional[str]:
        """Get primary IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    def _get_lan_ip(self) -> Optional[str]:
        """Get LAN IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("192.168.1.1", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip if not ip.startswith("127.") else None
        except Exception:
            return None

    def _get_public_ip(self) -> Optional[str]:
        """Get public IP address (if available)."""
        try:
            result = subprocess.run(
                ["curl", "-s", "https://api.ipify.org?format=json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("ip")
        except Exception:
            pass
        return None

    def _get_mac_address(self) -> Optional[str]:
        """Get MAC address."""
        try:
            if hasattr(socket, "AF_LINK"):
                # macOS/Linux
                result = subprocess.run(
                    ["ifconfig"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.split("\n"):
                    if "HWaddr" in line or "lladdr" in line:
                        match = re.search(r"([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})", line)
                        if match:
                            return match.group(0).replace("-", ":")
            else:
                # Windows
                result = subprocess.run(
                    ["getmac"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in result.stdout.split("\n"):
                    match = re.search(r"([0-9A-Fa-f]{2}-){5}([0-9A-Fa-f]{2})", line)
                    if match:
                        return match.group(0).replace("-", ":")
        except Exception:
            pass
        return None

    # --- Registration ---

    def register_with_meeting(
        self, client: ApiClient, device_key: str, token_code: str
    ) -> tuple[bool, str]:
        """Register device with Meeting server.

        Args:
            client: ApiClient instance connected to Meeting server
            device_key: Unique device identifier
            token_code: One-time registration token (6 hex chars)

        Returns:
            (success, message)
        """
        try:
            # Collect device info
            device_info = self.collect_device_info()

            # Register with Meeting
            response = client.register_device(device_key, token_code, device_info)

            if response.get("ok"):
                # Save locally
                if self.save_device_key(device_key, device_info):
                    return True, f"Device registered: {device_key}"
                else:
                    return False, "Registration confirmed but failed to save locally"
            else:
                return False, response.get("message", "Registration failed")

        except ApiError as e:
            logger.error(f"Registration error: {e}")
            if e.status == 404:
                return False, "Device not found - may not exist on server"
            elif e.status == 401:
                return False, "Invalid token code - may be expired or incorrect"
            elif e.status == 409:
                return False, "Device already registered"
            else:
                return False, str(e)
        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}")
            return False, f"Unexpected error: {e}"

    # --- Heartbeat ---

    def start_heartbeat(self, interval: int = 60):
        """Start periodic heartbeat to Meeting server.

        Args:
            interval: Heartbeat interval in seconds (default: 60)
        """
        if not self.device_key:
            logger.warning("Cannot start heartbeat: device not registered")
            return

        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(interval,),
            daemon=True,
        )
        self._heartbeat_thread.start()
        logger.info(f"Heartbeat started (interval: {interval}s)")

    def stop_heartbeat(self):
        """Stop heartbeat thread."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_stop.set()
            self._heartbeat_thread.join(timeout=5)
            logger.info("Heartbeat stopped")

    def _heartbeat_loop(self, interval: int):
        """Heartbeat loop (runs in background thread)."""
        import requests
        
        consecutive_failures = 0
        max_failures = 5

        while not self._heartbeat_stop.is_set():
            try:
                # Collect current device info
                heartbeat_data = self.collect_device_info()

                # Send heartbeat directly via requests
                url = f"{self.server_url}/api/devices/{self.device_key}/online"
                response = requests.post(
                    url,
                    json=heartbeat_data,
                    timeout=10,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        logger.debug(f"Heartbeat sent: {self.device_key}")
                        consecutive_failures = 0
                    else:
                        logger.warning(f"Heartbeat failed: {data.get('message')}")
                        consecutive_failures += 1
                else:
                    logger.warning(f"Heartbeat HTTP error: {response.status_code}")
                    consecutive_failures += 1

                if consecutive_failures >= max_failures:
                    logger.error(f"Too many heartbeat failures ({consecutive_failures}), stopping")
                    break

            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    logger.error(f"Too many heartbeat failures ({consecutive_failures}), stopping")
                    break

            # Wait for next heartbeat or until stop is signaled
            self._heartbeat_stop.wait(interval)

    def send_heartbeat_now(self) -> tuple[bool, str]:
        """Send a single heartbeat immediately (for testing)."""
        import requests
        
        if not self.device_key:
            return False, "Device not registered"

        try:
            heartbeat_data = self.collect_device_info()
            url = f"{self.server_url}/api/devices/{self.device_key}/online"
            response = requests.post(
                url,
                json=heartbeat_data,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return True, f"Heartbeat sent successfully (last_seen: {data.get('last_seen')})"
                else:
                    return False, data.get("message", "Heartbeat failed")
            else:
                return False, f"HTTP error: {response.status_code}"

        except Exception as e:
            return False, f"Error: {e}"

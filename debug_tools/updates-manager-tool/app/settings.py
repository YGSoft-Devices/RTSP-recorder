from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

try:
    import keyring  # type: ignore
except Exception:  # pragma: no cover
    keyring = None


SERVICE_NAME = "UpdatesManagerTool"


def get_token(profile_name: str) -> Optional[str]:
    if keyring:
        try:
            return keyring.get_password(SERVICE_NAME, profile_name)
        except Exception:
            return None
    return os.environ.get("MEETING_TOKEN")


def set_token(profile_name: str, token: str) -> bool:
    if not token:
        return False
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, profile_name, token)
            return True
        except Exception:
            return False
    return False


def clear_token(profile_name: str) -> bool:
    if keyring:
        try:
            keyring.delete_password(SERVICE_NAME, profile_name)
            return True
        except Exception:
            return False
    return False


class SettingsManager:
    """Centralized settings management for the application."""

    def __init__(self, app_dir: Optional[Path] = None):
        """Initialize settings manager.

        Args:
            app_dir: Application directory (defaults to ~/.updates-manager-tool)
        """
        if app_dir is None:
            from .storage import get_app_dir
            app_dir = get_app_dir()

        self.app_dir = Path(app_dir)
        self.settings_file = self.app_dir / "app_settings.json"
        self._settings = self._load_settings()

    def _load_settings(self) -> dict[str, Any]:
        """Load settings from file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default_settings()

    def _default_settings(self) -> dict[str, Any]:
        """Get default settings."""
        return {
            "meeting_server_url": "https://meeting.ygsoft.fr",
            "heartbeat_interval": 60,
            "verify_tls": True,
            "mask_device_keys": False,
            "auto_start_heartbeat": True,
        }

    def _save_settings(self):
        """Save settings to file."""
        self.app_dir.mkdir(parents=True, exist_ok=True)
        with open(self.settings_file, "w") as f:
            json.dump(self._settings, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set setting value and save.

        Args:
            key: Setting key
            value: Setting value
        """
        self._settings[key] = value
        self._save_settings()

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = self._default_settings()
        self._save_settings()


"""Self-update functionality for Updates Manager Tool.

This module allows the tool to check for and apply its own updates
from the Meeting update server.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Callable

import requests

from .version import __version__
from .device_manager import DeviceManager

logger = logging.getLogger(__name__)

# Device type for self-updates
DEVICE_TYPE = "updates-manager-tool"
DEFAULT_DISTRIBUTION = "stable"
DEFAULT_CHANNEL = "default"


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        version: str,
        download_url: str,
        sha256: Optional[str] = None,
        release_notes: Optional[str] = None,
        file_size: int = 0,
    ):
        self.version = version
        self.download_url = download_url
        self.sha256 = sha256
        self.release_notes = release_notes
        self.file_size = file_size

    def __repr__(self):
        return f"UpdateInfo(version={self.version}, url={self.download_url})"


class Updater:
    """Self-updater for Updates Manager Tool."""

    def __init__(self, server_url: Optional[str] = None, token: Optional[str] = None):
        """Initialize updater.
        
        Args:
            server_url: Meeting server URL (default: from device manager or https://meeting.ygsoft.fr)
            token: API token for authenticated endpoints
        """
        self.device_manager = DeviceManager()
        self.device_manager.load_device_key()
        
        self.server_url = server_url or self.device_manager.server_url or "https://meeting.ygsoft.fr"
        self.token = token
        self.current_version = __version__
        self.device_type = DEVICE_TYPE
        self.distribution = DEFAULT_DISTRIBUTION
        self.channel = DEFAULT_CHANNEL
        
        # Try to get token from active profile if not provided
        if not self.token:
            try:
                from .storage import load_profiles
                from .settings import get_token
                import os
                
                profiles = load_profiles()
                active = profiles.get("active")
                if active:
                    self.token = get_token(active) or os.environ.get("MEETING_TOKEN")
                else:
                    self.token = os.environ.get("MEETING_TOKEN")
            except Exception:
                pass

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def check_for_update(
        self,
        distribution: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> Optional[UpdateInfo]:
        """Check if an update is available.
        
        Args:
            distribution: Distribution to check (default: stable)
            channel: Channel to check (default: default)
            
        Returns:
            UpdateInfo if update available, None otherwise
        """
        dist = distribution or self.distribution
        chan = channel or self.channel

        try:
            # First, try to get the latest version from update-channels endpoint
            latest_version = self._get_latest_version(dist, chan)
            
            if not latest_version:
                logger.info("Could not determine latest version from channels")
                return None
            
            # Compare versions
            if not self._is_newer_version(latest_version, self.current_version):
                logger.info(f"No update available (current: {self.current_version}, latest: {latest_version})")
                return None
            
            # Get full update info from verify endpoint (includes download URL)
            update_info = self._get_update_info(dist, latest_version)
            
            if update_info:
                return update_info
            
            # Fallback: return basic info
            logger.warning("Could not get detailed update info, returning basic info")
            return UpdateInfo(
                version=latest_version,
                download_url=f"{self.server_url}/api/admin/updates/download?device_type={self.device_type}&distribution={dist}&version={latest_version}",
            )

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None

    def _get_update_info(self, distribution: str, version: str) -> Optional[UpdateInfo]:
        """Get detailed update info from verify endpoint."""
        try:
            url = f"{self.server_url}/api/admin/updates/verify"
            params = {
                "device_type": self.device_type,
                "distribution": distribution,
                "version": version,
            }
            
            response = requests.get(url, params=params, headers=self._get_headers(), timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("manifest_exists") and data.get("archive_exists"):
                    manifest = data.get("manifest", {})
                    
                    # Use API download endpoint (requires auth but works reliably)
                    download_url = f"{self.server_url}/api/admin/updates/download?device_type={self.device_type}&distribution={distribution}&version={version}"
                    
                    return UpdateInfo(
                        version=version,
                        download_url=download_url,
                        sha256=manifest.get("sha256"),
                        release_notes=manifest.get("notes"),
                        file_size=manifest.get("size", 0),
                    )
            
            return None
        except Exception as e:
            logger.debug(f"Could not get update info: {e}")
            return None

    def _get_latest_version(self, distribution: str, channel: str) -> Optional[str]:
        """Get latest version from update-channels endpoint."""
        try:
            url = f"{self.server_url}/api/admin/update-channels"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for ch in data.get("items", []):
                    if (ch.get("device_type") == self.device_type and 
                        ch.get("distribution") == distribution and
                        ch.get("channel") == channel and
                        ch.get("active")):
                        return ch.get("target_version")
            
            return None
        except Exception as e:
            logger.debug(f"Could not get latest version from channels: {e}")
            return None

    def _get_latest_from_manifest(self, distribution: str) -> Optional[str]:
        """Try to get latest version by checking known version numbers."""
        # This is a fallback - try incrementing version numbers
        # In practice, you'd want a proper "latest" endpoint
        return None

    def _get_manifest(self, distribution: str, version: str) -> Optional[dict]:
        """Get manifest for a specific version."""
        try:
            base_url = self.server_url.replace("https://", "http://")
            url = f"{base_url}/published/{self.device_type}/{distribution}/{version}/manifest.json"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.debug(f"Could not get manifest: {e}")
            return None

    def _is_newer_version(self, new_version: str, current_version: str) -> bool:
        """Compare version strings."""
        try:
            def parse_version(v: str) -> tuple:
                # Remove any prefix like 'v'
                v = v.lstrip('vV')
                # Split by dots and convert to integers
                parts = []
                for part in v.split('.'):
                    # Handle versions like "1.0.0-beta"
                    num = ''.join(c for c in part if c.isdigit())
                    parts.append(int(num) if num else 0)
                return tuple(parts)
            
            return parse_version(new_version) > parse_version(current_version)
        except Exception:
            # Fallback to string comparison
            return new_version > current_version

    def download_update(
        self,
        update_info: UpdateInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Optional[Path]:
        """Download an update package.
        
        Args:
            update_info: Update information from check_for_update()
            progress_callback: Optional callback(downloaded_bytes, total_bytes)
            
        Returns:
            Path to downloaded file, or None on error
        """
        try:
            # Create temp directory for download
            temp_dir = Path(tempfile.mkdtemp(prefix="umt_update_"))
            download_path = temp_dir / f"update_{update_info.version}.zip"
            
            logger.info(f"Downloading update from {update_info.download_url}")
            
            # Download with progress tracking (include auth headers for API endpoint)
            response = requests.get(
                update_info.download_url,
                stream=True,
                timeout=300,  # 5 minutes for large files
                headers=self._get_headers(),
            )
            response.raise_for_status()
            
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            
            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)
            
            logger.info(f"Downloaded {downloaded} bytes to {download_path}")
            
            # Verify SHA256 if provided
            if update_info.sha256:
                if not self._verify_checksum(download_path, update_info.sha256):
                    logger.error("SHA256 checksum verification failed")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None
                logger.info("SHA256 checksum verified")
            
            return download_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error downloading update: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading update: {e}")
            return None

    def _verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify file SHA256 checksum."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        
        calculated = sha256_hash.hexdigest().lower()
        expected = expected_sha256.lower()
        
        return calculated == expected

    def apply_update(
        self,
        update_file: Path,
        restart: bool = True,
    ) -> tuple[bool, str]:
        """Apply a downloaded update.
        
        This will:
        1. Extract the update to a temporary location
        2. Create a batch/shell script to replace files after app exits
        3. Optionally restart the application
        
        Args:
            update_file: Path to downloaded update file
            restart: Whether to restart after update
            
        Returns:
            (success, message)
        """
        try:
            # Determine installation directory
            if getattr(sys, 'frozen', False):
                # Running as compiled executable
                install_dir = Path(sys.executable).parent
            else:
                # Running from source
                install_dir = Path(__file__).parent.parent
            
            # Create extraction directory
            extract_dir = Path(tempfile.mkdtemp(prefix="umt_extract_"))
            
            logger.info(f"Extracting update to {extract_dir}")
            
            # Extract update
            with zipfile.ZipFile(update_file, 'r') as zf:
                zf.extractall(extract_dir)
            
            # Create update script
            if sys.platform == "win32":
                script_path = self._create_windows_update_script(
                    extract_dir, install_dir, restart
                )
            else:
                script_path = self._create_unix_update_script(
                    extract_dir, install_dir, restart
                )
            
            logger.info(f"Update script created: {script_path}")
            
            # Run update script and exit
            if sys.platform == "win32":
                # Use cmd.exe to run the batch script
                subprocess.Popen(
                    ["cmd.exe", "/c", str(script_path)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=str(extract_dir),
                )
            else:
                subprocess.Popen(
                    ["bash", str(script_path)],
                    start_new_session=True,
                    cwd=str(extract_dir),
                )
            
            return True, "Update prepared. The application will now close."
            
        except zipfile.BadZipFile:
            logger.error("Invalid update file (not a valid ZIP)")
            return False, "Invalid update file format"
        except Exception as e:
            logger.error(f"Error applying update: {e}")
            return False, f"Error applying update: {str(e)}"

    def _create_windows_update_script(
        self,
        extract_dir: Path,
        install_dir: Path,
        restart: bool,
    ) -> Path:
        """Create Windows batch script for update."""
        script_path = extract_dir / "update.bat"
        
        # Find the app directory in extract (might be nested)
        app_source = extract_dir
        for item in extract_dir.iterdir():
            if item.is_dir() and (item / "app").exists():
                app_source = item
                break
        
        exe_name = "updates-manager-tool.exe" if (install_dir / "updates-manager-tool.exe").exists() else "run.py"
        
        script = f'''@echo off
echo Updates Manager Tool - Update in progress...
echo.
echo Waiting for application to close...
timeout /t 3 /nobreak >nul

echo Copying new files...
xcopy /E /Y /I "{app_source}\\*" "{install_dir}\\"

echo Update complete!
'''
        if restart:
            script += f'''
echo Restarting application...
timeout /t 2 /nobreak >nul
start "" "{install_dir}\\{exe_name}"
'''
        else:
            script += '''
echo Please restart the application manually.
pause
'''
        
        script += f'''
echo Cleaning up...
rmdir /S /Q "{extract_dir}"
del "%~f0"
'''
        
        with open(script_path, 'w') as f:
            f.write(script)
        
        return script_path

    def _create_unix_update_script(
        self,
        extract_dir: Path,
        install_dir: Path,
        restart: bool,
    ) -> Path:
        """Create Unix shell script for update."""
        script_path = extract_dir / "update.sh"
        
        # Find the app directory in extract
        app_source = extract_dir
        for item in extract_dir.iterdir():
            if item.is_dir() and (item / "app").exists():
                app_source = item
                break
        
        script = f'''#!/bin/bash
echo "Updates Manager Tool - Update in progress..."
echo

echo "Waiting for application to close..."
sleep 3

echo "Copying new files..."
cp -R "{app_source}/"* "{install_dir}/"

echo "Update complete!"
'''
        if restart:
            script += f'''
echo "Restarting application..."
sleep 2
cd "{install_dir}"
python3 run.py &
'''
        else:
            script += '''
echo "Please restart the application manually."
'''
        
        script += f'''
echo "Cleaning up..."
rm -rf "{extract_dir}"
'''
        
        with open(script_path, 'w') as f:
            f.write(script)
        
        os.chmod(script_path, 0o755)
        
        return script_path

    def get_release_notes(self, version: Optional[str] = None) -> Optional[str]:
        """Get release notes for a specific version or latest.
        
        Args:
            version: Specific version, or None for latest
            
        Returns:
            Release notes text, or None if not available
        """
        try:
            url = f"{self.server_url}/api/admin/updates/release-notes"
            params = {"device_type": self.device_type}
            if version:
                params["version"] = version
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("release_notes")
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching release notes: {e}")
            return None


def check_for_update_simple() -> Optional[dict]:
    """Simple function to check for updates.
    
    Returns:
        dict with update info if available, None otherwise
    """
    updater = Updater()
    update = updater.check_for_update()
    
    if update:
        return {
            "available": True,
            "current_version": updater.current_version,
            "new_version": update.version,
            "download_url": update.download_url,
            "release_notes": update.release_notes,
        }
    
    return None

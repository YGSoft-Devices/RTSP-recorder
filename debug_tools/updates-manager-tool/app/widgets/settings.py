"""Settings widget - profile management and preferences."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from ..settings import clear_token, get_token, set_token
from ..storage import get_app_dir, load_profiles, load_ui_state, save_profiles, save_ui_state
from ..device_manager import DeviceManager

if TYPE_CHECKING:
    from ..main import MainWindow


class SettingsWidget(QWidget):
    """Settings page with profile management and preferences."""

    profile_changed = Signal()  # Emitted when active profile changes

    def __init__(self, main_window: MainWindow | None = None):
        super().__init__()
        self.main_window = main_window
        self.profiles_data = load_profiles()
        self.ui_state = load_ui_state()
        self._build_ui()
        self._load_active_profile()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Create scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(16)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        scroll_layout.addWidget(title)

        # Meeting Device Registration section
        self._build_device_registration_section(scroll_layout)

        # Profile section
        profile_group = QGroupBox("Meeting Server Profiles")
        profile_layout = QVBoxLayout()

        # Profile selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Profile:"))
        self.profile_selector = QComboBox()
        self.profile_selector.setMinimumWidth(200)
        self._refresh_profile_selector()
        self.profile_selector.currentIndexChanged.connect(self._on_profile_selected)
        selector_layout.addWidget(self.profile_selector)
        selector_layout.addStretch()
        profile_layout.addLayout(selector_layout)

        # Profile form
        form = QFormLayout()

        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("e.g., Production, Staging")
        form.addRow("Profile Name:", self.profile_name)

        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("https://meeting.ygsoft.fr")
        form.addRow("Base URL:", self.base_url)

        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("Bearer token (stored securely)")
        form.addRow("Token:", self.token)

        self.timeout = QSpinBox()
        self.timeout.setRange(5, 120)
        self.timeout.setValue(20)
        self.timeout.setSuffix(" seconds")
        form.addRow("Timeout:", self.timeout)

        self.retries = QSpinBox()
        self.retries.setRange(0, 10)
        self.retries.setValue(3)
        form.addRow("Retries:", self.retries)

        profile_layout.addLayout(form)

        # Profile buttons
        btn_layout = QHBoxLayout()

        btn_save = QPushButton("💾 Save Profile")
        btn_save.clicked.connect(self._save_profile)

        btn_activate = QPushButton("✅ Set as Active")
        btn_activate.clicked.connect(self._set_active_profile)

        btn_delete = QPushButton("🗑️ Delete Profile")
        btn_delete.clicked.connect(self._delete_profile)

        btn_clear_token = QPushButton("🔑 Clear Token")
        btn_clear_token.clicked.connect(self._clear_token)

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_activate)
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_clear_token)
        btn_layout.addStretch()

        profile_layout.addLayout(btn_layout)
        profile_group.setLayout(profile_layout)
        scroll_layout.addWidget(profile_group)

        # Defaults section
        defaults_group = QGroupBox("Default Values")
        defaults_layout = QFormLayout()

        self.default_device_type = QLineEdit()
        self.default_device_type.setPlaceholderText("e.g., rpi4")
        self.default_device_type.setText(self.ui_state.get("default_device_type", ""))
        defaults_layout.addRow("Device Type:", self.default_device_type)

        self.default_distribution = QLineEdit()
        self.default_distribution.setPlaceholderText("e.g., stable")
        self.default_distribution.setText(self.ui_state.get("default_distribution", ""))
        defaults_layout.addRow("Distribution:", self.default_distribution)

        self.default_channel = QLineEdit()
        self.default_channel.setPlaceholderText("e.g., default")
        self.default_channel.setText(self.ui_state.get("default_channel", ""))
        defaults_layout.addRow("Channel:", self.default_channel)

        self.default_archive_format = QComboBox()
        self.default_archive_format.addItems(["tar.gz", "zip"])
        if self.ui_state.get("default_archive_format") == "zip":
            self.default_archive_format.setCurrentIndex(1)
        defaults_layout.addRow("Archive Format:", self.default_archive_format)

        defaults_group.setLayout(defaults_layout)
        scroll_layout.addWidget(defaults_group)

        # Security section
        security_group = QGroupBox("Security & Display")
        security_layout = QVBoxLayout()

        self.mask_device_keys = QCheckBox("Mask device keys in UI (show only last 6 characters)")
        self.mask_device_keys.setChecked(self.ui_state.get("mask_device_keys", False))
        security_layout.addWidget(self.mask_device_keys)

        self.verify_tls = QCheckBox("Verify TLS certificates (recommended)")
        self.verify_tls.setChecked(self.ui_state.get("verify_tls", True))
        security_layout.addWidget(self.verify_tls)

        security_group.setLayout(security_layout)
        scroll_layout.addWidget(security_group)

        # Save defaults button
        btn_save_defaults = QPushButton("💾 Save Preferences")
        btn_save_defaults.clicked.connect(self._save_preferences)
        scroll_layout.addWidget(btn_save_defaults)

        # App info
        from ..version import __version__, __build_date__
        info_group = QGroupBox("Application Info")
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"Version: {__version__} (build {__build_date__})"))
        info_layout.addWidget(QLabel(f"App Data: {get_app_dir()}"))
        
        # Update check section
        update_layout = QHBoxLayout()
        self.check_update_btn = QPushButton("🔄 Check for Updates")
        self.check_update_btn.clicked.connect(self._check_for_updates)
        update_layout.addWidget(self.check_update_btn)
        
        self.update_status_label = QLabel("")
        update_layout.addWidget(self.update_status_label)
        update_layout.addStretch()
        info_layout.addLayout(update_layout)
        
        info_group.setLayout(info_layout)
        scroll_layout.addWidget(info_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)

        layout.addWidget(scroll)

    def _build_device_registration_section(self, parent_layout: QVBoxLayout):
        """Build the Meeting Device Registration section."""
        reg_group = QGroupBox("Meeting Device Registration")
        reg_layout = QVBoxLayout()

        # Load current device info
        device_mgr = DeviceManager()
        device_mgr.load_device_key()

        if device_mgr.is_registered():
            # Show registered status with green indicator
            status_layout = QHBoxLayout()
            status_icon = QLabel("✅")
            status_icon.setStyleSheet("font-size: 20px;")
            status_layout.addWidget(status_icon)
            status_label = QLabel("Device is registered")
            status_label.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 14px;")
            status_layout.addWidget(status_label)
            status_layout.addStretch()
            reg_layout.addLayout(status_layout)

            # Device info form (read-only)
            form = QFormLayout()
            form.setSpacing(10)

            # Device Key (masked for security)
            device_key_display = device_mgr.device_key
            if len(device_key_display) > 12:
                device_key_display = device_key_display[:6] + "..." + device_key_display[-6:]
            self.reg_device_key = QLineEdit(device_key_display)
            self.reg_device_key.setReadOnly(True)
            self.reg_device_key.setStyleSheet("background-color: #3d3d3d; color: #aaaaaa;")
            form.addRow("Device Key:", self.reg_device_key)

            # Token Code (masked)
            token_display = "••••••" if device_mgr.token_code else "N/A"
            self.reg_token_code = QLineEdit(token_display)
            self.reg_token_code.setReadOnly(True)
            self.reg_token_code.setStyleSheet("background-color: #3d3d3d; color: #aaaaaa;")
            form.addRow("Token Code:", self.reg_token_code)

            # Server URL
            self.reg_server_url = QLineEdit(device_mgr.server_url)
            self.reg_server_url.setReadOnly(True)
            self.reg_server_url.setStyleSheet("background-color: #3d3d3d; color: #aaaaaa;")
            form.addRow("Server URL:", self.reg_server_url)

            reg_layout.addLayout(form)

            # Reset button
            btn_layout = QHBoxLayout()
            reset_btn = QPushButton("🔄 Reset Registration")
            reset_btn.setStyleSheet("background-color: #F44336; color: white; padding: 8px;")
            reset_btn.clicked.connect(self._reset_registration)
            btn_layout.addWidget(reset_btn)
            btn_layout.addStretch()
            reg_layout.addLayout(btn_layout)

            # Info text
            info_label = QLabel(
                "⚠️ Resetting registration will require you to re-register the device on next startup."
            )
            info_label.setStyleSheet("color: #FF9800; font-size: 11px;")
            info_label.setWordWrap(True)
            reg_layout.addWidget(info_label)

        else:
            # Show not registered status with red indicator
            status_layout = QHBoxLayout()
            status_icon = QLabel("❌")
            status_icon.setStyleSheet("font-size: 20px;")
            status_layout.addWidget(status_icon)
            status_label = QLabel("Device is NOT registered")
            status_label.setStyleSheet("color: #F44336; font-weight: bold; font-size: 14px;")
            status_layout.addWidget(status_label)
            status_layout.addStretch()
            reg_layout.addLayout(status_layout)

            info_label = QLabel(
                "The device registration dialog should appear on application startup.\n"
                "If it doesn't, restart the application."
            )
            info_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
            info_label.setWordWrap(True)
            reg_layout.addWidget(info_label)

        reg_group.setLayout(reg_layout)
        parent_layout.addWidget(reg_group)

    def _reset_registration(self):
        """Reset device registration."""
        reply = QMessageBox.warning(
            self,
            "Reset Registration",
            "Are you sure you want to reset the device registration?\n\n"
            "This will:\n"
            "• Delete the local device credentials\n"
            "• Stop the heartbeat\n"
            "• Require re-registration on next startup\n\n"
            "The application will close after reset.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Load device manager and delete registration file
                device_mgr = DeviceManager()
                device_file = device_mgr.device_file
                
                if device_file.exists():
                    device_file.unlink()
                
                QMessageBox.information(
                    self,
                    "Registration Reset",
                    "Device registration has been reset.\n\n"
                    "The application will now close.\n"
                    "Please restart to register again."
                )
                
                # Close application
                from PySide6.QtWidgets import QApplication
                QApplication.instance().quit()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to reset registration:\n{str(e)}"
                )

    def _refresh_profile_selector(self):
        """Refresh profile dropdown."""
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        self.profile_selector.addItem("(New Profile)")

        for profile in self.profiles_data.get("profiles", []):
            name = profile.get("name", "Unnamed")
            if name == self.profiles_data.get("active"):
                name += " ★"
            self.profile_selector.addItem(name.rstrip(" ★"), profile.get("name"))

        self.profile_selector.blockSignals(False)

    def _on_profile_selected(self):
        """Handle profile selection change."""
        idx = self.profile_selector.currentIndex()
        if idx == 0:
            # New profile
            self.profile_name.clear()
            self.base_url.clear()
            self.token.clear()
            self.timeout.setValue(20)
            self.retries.setValue(3)
            return

        profile_name = self.profile_selector.currentData()
        for profile in self.profiles_data.get("profiles", []):
            if profile.get("name") == profile_name:
                self._load_profile(profile)
                return

    def _load_active_profile(self):
        """Load the active profile on startup."""
        active = self.profiles_data.get("active")
        if not active:
            return

        for i, profile in enumerate(self.profiles_data.get("profiles", [])):
            if profile.get("name") == active:
                self.profile_selector.setCurrentIndex(i + 1)  # +1 for "(New Profile)"
                self._load_profile(profile)
                return

    def _load_profile(self, profile: dict):
        """Populate form with profile data."""
        self.profile_name.setText(profile.get("name", ""))
        self.base_url.setText(profile.get("base_url", ""))
        self.timeout.setValue(int(profile.get("timeout", 20)))
        self.retries.setValue(int(profile.get("retries", 3)))

        # Get token from keyring
        token = get_token(profile.get("name", "")) or os.environ.get("MEETING_TOKEN", "")
        self.token.setText(token)

    def _save_profile(self):
        """Save current profile."""
        name = self.profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Profile name is required")
            return

        if not self.base_url.text().strip():
            QMessageBox.warning(self, "Validation", "Base URL is required")
            return

        profile = {
            "name": name,
            "base_url": self.base_url.text().strip(),
            "timeout": self.timeout.value(),
            "retries": self.retries.value(),
        }

        # Update or add profile
        profiles = [p for p in self.profiles_data.get("profiles", []) if p.get("name") != name]
        profiles.append(profile)
        self.profiles_data["profiles"] = profiles
        save_profiles(self.profiles_data)

        # Save token to keyring
        token_value = self.token.text().strip()
        if token_value:
            set_token(name, token_value)

        self._refresh_profile_selector()
        QMessageBox.information(self, "Saved", f"Profile '{name}' saved")
        self.profile_changed.emit()

    def _set_active_profile(self):
        """Set current profile as active."""
        name = self.profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Profile name is required")
            return

        # Check profile exists
        exists = any(p.get("name") == name for p in self.profiles_data.get("profiles", []))
        if not exists:
            QMessageBox.warning(self, "Error", "Save the profile first")
            return

        self.profiles_data["active"] = name
        save_profiles(self.profiles_data)
        self._refresh_profile_selector()
        QMessageBox.information(self, "Active", f"Active profile set to '{name}'")
        self.profile_changed.emit()

    def _delete_profile(self):
        """Delete current profile."""
        name = self.profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Select a profile first")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete profile '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Remove profile
        profiles = [p for p in self.profiles_data.get("profiles", []) if p.get("name") != name]
        self.profiles_data["profiles"] = profiles

        # Clear active if it was this profile
        if self.profiles_data.get("active") == name:
            self.profiles_data["active"] = None

        save_profiles(self.profiles_data)

        # Clear token
        clear_token(name)

        # Clear form
        self.profile_name.clear()
        self.base_url.clear()
        self.token.clear()
        self.timeout.setValue(20)
        self.retries.setValue(3)

        self._refresh_profile_selector()
        QMessageBox.information(self, "Deleted", f"Profile '{name}' deleted")
        self.profile_changed.emit()

    def _clear_token(self):
        """Clear token from keyring."""
        name = self.profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Select a profile first")
            return

        ok = clear_token(name)
        if ok:
            self.token.clear()
            QMessageBox.information(self, "Cleared", "Token cleared from secure storage")
        else:
            QMessageBox.warning(self, "Failed", "Failed to clear token")

    def _save_preferences(self):
        """Save preferences to UI state."""
        self.ui_state["default_device_type"] = self.default_device_type.text().strip()
        self.ui_state["default_distribution"] = self.default_distribution.text().strip()
        self.ui_state["default_channel"] = self.default_channel.text().strip()
        self.ui_state["default_archive_format"] = self.default_archive_format.currentText()
        self.ui_state["mask_device_keys"] = self.mask_device_keys.isChecked()
        self.ui_state["verify_tls"] = self.verify_tls.isChecked()

        save_ui_state(self.ui_state)
        QMessageBox.information(self, "Saved", "Preferences saved")

    def get_active_profile(self) -> dict:
        """Get currently active profile data."""
        active = self.profiles_data.get("active")
        if not active:
            return {}

        for profile in self.profiles_data.get("profiles", []):
            if profile.get("name") == active:
                return profile
        return {}

    def get_token_for_active(self) -> str:
        """Get token for active profile."""
        active = self.profiles_data.get("active")
        if not active:
            return os.environ.get("MEETING_TOKEN", "")
        return get_token(active) or os.environ.get("MEETING_TOKEN", "")

    def _check_for_updates(self):
        """Check for application updates."""
        from ..updater import Updater
        from ..version import __version__
        
        self.check_update_btn.setEnabled(False)
        self.update_status_label.setText("⏳ Checking...")
        self.update_status_label.setStyleSheet("color: #2196F3;")
        
        # Process events to show status
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        try:
            updater = Updater()
            update_info = updater.check_for_update()
            
            if update_info:
                self.update_status_label.setText(f"✅ Update available: v{update_info.version}")
                self.update_status_label.setStyleSheet("color: #4CAF50;")
                
                # Ask user if they want to download
                reply = QMessageBox.question(
                    self,
                    "Update Available",
                    f"A new version is available!\n\n"
                    f"Current version: {__version__}\n"
                    f"New version: {update_info.version}\n\n"
                    f"Would you like to download and install this update?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                
                if reply == QMessageBox.Yes:
                    self._download_and_install_update(updater, update_info)
            else:
                self.update_status_label.setText("✅ You're up to date!")
                self.update_status_label.setStyleSheet("color: #4CAF50;")
                
        except Exception as e:
            self.update_status_label.setText(f"❌ Error: {str(e)[:30]}")
            self.update_status_label.setStyleSheet("color: #F44336;")
        finally:
            self.check_update_btn.setEnabled(True)

    def _download_and_install_update(self, updater, update_info):
        """Download and install an update."""
        from PySide6.QtWidgets import QProgressDialog
        
        progress = QProgressDialog(
            f"Downloading update v{update_info.version}...",
            "Cancel",
            0,
            100,
            self
        )
        progress.setWindowTitle("Downloading Update")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        def progress_callback(downloaded: int, total: int):
            if total > 0:
                percent = int((downloaded / total) * 100)
                progress.setValue(percent)
                progress.setLabelText(
                    f"Downloading: {downloaded // 1024} KB / {total // 1024} KB"
                )
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
        
        try:
            # Download
            download_path = updater.download_update(update_info, progress_callback)
            
            if progress.wasCanceled():
                self.update_status_label.setText("Download cancelled")
                return
            
            if not download_path:
                QMessageBox.warning(self, "Error", "Failed to download update")
                return
            
            progress.close()
            
            # Confirm installation
            reply = QMessageBox.question(
                self,
                "Install Update",
                "Download complete!\n\n"
                "The application will close to install the update.\n"
                "Do you want to proceed?",
                QMessageBox.Yes | QMessageBox.No,
            )
            
            if reply == QMessageBox.Yes:
                success, message = updater.apply_update(download_path, restart=True)
                
                if success:
                    QMessageBox.information(self, "Update", message)
                    # Exit application
                    from PySide6.QtWidgets import QApplication
                    QApplication.instance().quit()
                else:
                    QMessageBox.warning(self, "Error", message)
                    
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Update failed: {str(e)}")

"""Device registration UI widget for Settings tab."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)

if TYPE_CHECKING:
    from ..main import MainWindow


class DeviceRegistrationWidget(QGroupBox):
    """Widget for device registration and heartbeat status."""

    registration_complete = Signal()
    heartbeat_updated = Signal(bool)  # True if heartbeat is active

    def __init__(self, main_window: MainWindow):
        """Initialize device registration widget.

        Args:
            main_window: Reference to main window for API access
        """
        super().__init__("Meeting Device Registration")
        self.main_window = main_window
        self.device_manager = main_window.device_manager
        self.api_client = main_window.api_client
        self.settings_mgr = main_window.settings_manager

        self._init_ui()
        self._load_status()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()

        # Status section
        self.status_label = QLabel("Status: Not registered")
        self.status_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
        layout.addWidget(self.status_label)

        # Device info section
        info_layout = QVBoxLayout()

        # Device Key
        key_layout = QHBoxLayout()
        key_layout.addWidget(QLabel("Device Key:"))
        self.device_key_input = QLineEdit()
        self.device_key_input.setReadOnly(True)
        self.device_key_input.setPlaceholderText("Generated after registration")
        key_layout.addWidget(self.device_key_input)
        key_copy_btn = QPushButton("Copy")
        key_copy_btn.setMaximumWidth(100)
        key_copy_btn.clicked.connect(self._copy_device_key)
        key_layout.addWidget(key_copy_btn)
        info_layout.addLayout(key_layout)

        # Token Code
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel("Registration Token:"))
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Enter 6-character token code")
        self.token_input.setMaxLength(6)
        token_layout.addWidget(self.token_input)
        info_layout.addLayout(token_layout)

        layout.addLayout(info_layout)

        # Instructions
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(120)
        instructions.setPlainText(
            """Device Registration Instructions:

1. Device key will be provided by your Meeting server administrator
2. Enter the registration token (6 hex characters) provided for this device
3. Click "Register" to complete registration
4. After successful registration, heartbeat will start automatically

Note: The token code can only be used once. If registration fails, 
request a new token from your administrator."""
        )
        layout.addWidget(instructions)

        # Buttons
        button_layout = QHBoxLayout()

        self.register_btn = QPushButton("Register Device")
        self.register_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        self.register_btn.clicked.connect(self._register_device)
        button_layout.addWidget(self.register_btn)

        self.heartbeat_btn = QPushButton("Test Heartbeat")
        self.heartbeat_btn.setEnabled(False)
        self.heartbeat_btn.clicked.connect(self._test_heartbeat)
        button_layout.addWidget(self.heartbeat_btn)

        self.unregister_btn = QPushButton("Unregister")
        self.unregister_btn.setEnabled(False)
        self.unregister_btn.setStyleSheet("background-color: #F44336; color: white; padding: 8px;")
        self.unregister_btn.clicked.connect(self._unregister_device)
        button_layout.addWidget(self.unregister_btn)

        layout.addLayout(button_layout)

        # Heartbeat status
        self.heartbeat_status_label = QLabel("Heartbeat: Inactive")
        self.heartbeat_status_label.setStyleSheet("color: #FF9800; font-style: italic;")
        layout.addWidget(self.heartbeat_status_label)

        layout.addStretch()
        self.setLayout(layout)

    def _load_status(self):
        """Load and display current registration status."""
        device_key = self.device_manager.load_device_key()

        if device_key:
            self.device_key_input.setText(device_key)
            self.register_btn.setEnabled(False)
            self.token_input.setEnabled(False)
            self.heartbeat_btn.setEnabled(True)
            self.unregister_btn.setEnabled(True)
            self.status_label.setText(f"Status: Registered ({device_key})")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.token_input.setText("(Already registered)")
            self.token_input.setStyleSheet("background-color: #F5F5F5;")
        else:
            self.device_key_input.setText("")
            self.register_btn.setEnabled(True)
            self.token_input.setEnabled(True)
            self.heartbeat_btn.setEnabled(False)
            self.unregister_btn.setEnabled(False)
            self.status_label.setText("Status: Not registered")
            self.status_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
            self.token_input.setText("")
            self.token_input.setStyleSheet("")

    def _copy_device_key(self):
        """Copy device key to clipboard."""
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.device_key_input.text())
        QMessageBox.information(self, "Success", "Device key copied to clipboard")

    def _register_device(self):
        """Register device with Meeting server."""
        token_code = self.token_input.text().strip().upper()

        if not token_code or len(token_code) != 6:
            QMessageBox.warning(
                self,
                "Invalid Token",
                "Token code must be 6 characters.\n\nExample: ABC123",
            )
            return

        # Get Meeting server URL from settings
        meeting_url = self.settings_mgr.get("meeting_server_url", "https://meeting.ygsoft.fr")

        # Temporarily set API client to Meeting server
        original_url = self.api_client.base_url
        self.api_client.base_url = meeting_url

        try:
            # For now, use a placeholder device_key
            # In a real scenario, this would be provided by the admin
            device_key = f"device-{hash(token_code) & 0xFFFFFFFF:08x}"

            success, message = self.device_manager.register_with_meeting(
                self.api_client,
                device_key,
                token_code,
            )

            if success:
                QMessageBox.information(
                    self,
                    "Registration Successful",
                    f"Device registered successfully!\n\n{message}",
                )
                self._load_status()
                self.registration_complete.emit()

                # Auto-start heartbeat
                self.device_manager.start_heartbeat(self.api_client, interval=60)
                self._update_heartbeat_status()
            else:
                QMessageBox.critical(
                    self,
                    "Registration Failed",
                    f"Registration failed:\n\n{message}",
                )

        finally:
            # Restore original API client URL
            self.api_client.base_url = original_url

    def _test_heartbeat(self):
        """Send test heartbeat to Meeting server."""
        meeting_url = self.settings_mgr.get("meeting_server_url", "https://meeting.ygsoft.fr")
        original_url = self.api_client.base_url
        self.api_client.base_url = meeting_url

        try:
            success, message = self.device_manager.send_heartbeat_now(self.api_client)

            if success:
                QMessageBox.information(self, "Heartbeat Test", message)
            else:
                QMessageBox.warning(self, "Heartbeat Test Failed", message)

        finally:
            self.api_client.base_url = original_url

    def _unregister_device(self):
        """Unregister device from Meeting server."""
        reply = QMessageBox.question(
            self,
            "Unregister Device",
            "Are you sure you want to unregister this device?\n\n"
            "This will stop heartbeat and remove the device key.",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.device_manager.stop_heartbeat()
            if self.device_manager.clear_device_key():
                QMessageBox.information(
                    self,
                    "Unregistered",
                    "Device unregistered successfully",
                )
                self._load_status()
                self._update_heartbeat_status()
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to unregister device",
                )

    def _update_heartbeat_status(self):
        """Update heartbeat status display."""
        if hasattr(self.device_manager, "_heartbeat_thread"):
            is_active = (
                self.device_manager._heartbeat_thread is not None
                and self.device_manager._heartbeat_thread.is_alive()
            )

            if is_active:
                self.heartbeat_status_label.setText("Heartbeat: Active ✓")
                self.heartbeat_status_label.setStyleSheet("color: #4CAF50; font-style: italic;")
            else:
                self.heartbeat_status_label.setText("Heartbeat: Inactive")
                self.heartbeat_status_label.setStyleSheet("color: #FF9800; font-style: italic;")

            self.heartbeat_updated.emit(is_active)

    def closeEvent(self, event):
        """Cleanup on widget close."""
        # Don't stop heartbeat on close - let it run in background
        super().closeEvent(event)

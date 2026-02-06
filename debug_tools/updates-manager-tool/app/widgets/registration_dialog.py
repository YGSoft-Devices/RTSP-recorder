"""Mandatory device registration dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QFormLayout,
)


class DeviceRegistrationDialog(QDialog):
    """Modal dialog for mandatory device registration.
    
    This dialog blocks access to the main application until the device
    is properly registered with the Meeting server.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Device Registration Required")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        # Remove close button - force registration
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint
        )
        
        self.device_key = None
        self.token_code = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("🔐 Device Registration Required")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #4CAF50;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Warning message
        warning = QLabel(
            "This tool must be registered with the Meeting server before use.\n"
            "Please enter your device credentials provided by the administrator."
        )
        warning.setStyleSheet("color: #FF9800; font-size: 12px;")
        warning.setAlignment(Qt.AlignCenter)
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Registration form
        form_group = QGroupBox("Device Credentials")
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        # Device Key
        self.device_key_input = QLineEdit()
        self.device_key_input.setPlaceholderText("e.g., 0123456789abcdef0123456789abcdef")
        self.device_key_input.setMinimumHeight(35)
        form_layout.addRow("Device Key:", self.device_key_input)

        # Token Code
        self.token_code_input = QLineEdit()
        self.token_code_input.setPlaceholderText("6-character hex code (e.g., ABC123)")
        self.token_code_input.setMaxLength(6)
        self.token_code_input.setMinimumHeight(35)
        form_layout.addRow("Token Code:", self.token_code_input)

        # Server URL (read-only, pre-filled)
        self.server_url = QLineEdit("https://meeting.ygsoft.fr")
        self.server_url.setMinimumHeight(35)
        self.server_url.setStyleSheet("background-color: #3d3d3d; color: #aaaaaa;")
        form_layout.addRow("Server:", self.server_url)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Instructions
        instructions = QLabel(
            "📋 <b>Instructions:</b><br>"
            "1. Contact your Meeting administrator to get your device credentials<br>"
            "2. The <b>device_key</b> is a unique identifier for this machine<br>"
            "3. The <b>token_code</b> is a 6-character code (used once for registration)<br>"
            "4. Click 'Register' to complete the registration"
        )
        instructions.setStyleSheet("font-size: 11px; color: #aaaaaa; padding: 10px;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Buttons
        button_layout = QHBoxLayout()
        
        self.register_btn = QPushButton("✅ Register Device")
        self.register_btn.setMinimumHeight(40)
        self.register_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;"
        )
        self.register_btn.clicked.connect(self._on_register)
        button_layout.addWidget(self.register_btn)

        self.quit_btn = QPushButton("❌ Quit")
        self.quit_btn.setMinimumHeight(40)
        self.quit_btn.setStyleSheet(
            "background-color: #F44336; color: white; font-weight: bold; font-size: 14px;"
        )
        self.quit_btn.clicked.connect(self._on_quit)
        button_layout.addWidget(self.quit_btn)

        layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def _on_register(self):
        """Handle register button click."""
        device_key = self.device_key_input.text().strip()
        token_code = self.token_code_input.text().strip().upper()
        server_url = self.server_url.text().strip()

        # Validation
        if not device_key:
            self._show_error("Device Key is required")
            return

        if len(device_key) < 8:
            self._show_error("Device Key seems too short (minimum 8 characters)")
            return

        if not token_code:
            self._show_error("Token Code is required")
            return

        if len(token_code) != 6:
            self._show_error("Token Code must be exactly 6 characters")
            return

        if not server_url:
            self._show_error("Server URL is required")
            return

        # Try to register
        self.status_label.setText("⏳ Registering...")
        self.status_label.setStyleSheet("color: #2196F3;")
        self.register_btn.setEnabled(False)
        
        # Process events to show status
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            success, message = self._try_register(device_key, token_code, server_url)
            
            if success:
                self.device_key = device_key
                self.token_code = token_code
                self.server_url_value = server_url
                self.status_label.setText("✅ Registration successful!")
                self.status_label.setStyleSheet("color: #4CAF50;")
                QMessageBox.information(
                    self,
                    "Registration Successful",
                    f"Device registered successfully!\n\nDevice Key: {device_key[:8]}...\n\n"
                    "The application will now start."
                )
                self.accept()
            else:
                self._show_error(message)
                self.register_btn.setEnabled(True)

        except Exception as e:
            self._show_error(f"Error: {str(e)}")
            self.register_btn.setEnabled(True)

    def _try_register(self, device_key: str, token_code: str, server_url: str) -> tuple[bool, str]:
        """Try to register with Meeting server.
        
        Returns:
            (success, message)
        """
        import requests
        
        # First, try a heartbeat to verify the device exists
        try:
            # Send heartbeat to verify device_key is valid
            response = requests.post(
                f"{server_url}/api/devices/{device_key}/online",
                json={
                    "note": "Updates Manager Tool - Initial registration",
                    "token_code": token_code,
                },
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return True, "Registration successful"
                else:
                    return False, data.get("message", "Unknown error")
            elif response.status_code == 404:
                return False, "Device not found on server. Contact your administrator."
            elif response.status_code == 401:
                return False, "Invalid token code. Please check and try again."
            elif response.status_code == 403:
                return False, "Access denied. Device may not be authorized."
            else:
                return False, f"Server error: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return False, f"Cannot connect to {server_url}. Check your network."
        except requests.exceptions.Timeout:
            return False, "Connection timeout. Server may be unreachable."
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

    def _show_error(self, message: str):
        """Show error message."""
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color: #F44336;")

    def _on_quit(self):
        """Handle quit button - exit application."""
        reply = QMessageBox.question(
            self,
            "Quit Application",
            "The application cannot run without device registration.\n\n"
            "Are you sure you want to quit?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.reject()

    def get_credentials(self) -> tuple[str, str, str]:
        """Get the entered credentials after successful registration.
        
        Returns:
            (device_key, token_code, server_url)
        """
        return (
            self.device_key,
            self.token_code,
            getattr(self, 'server_url_value', 'https://meeting.ygsoft.fr')
        )

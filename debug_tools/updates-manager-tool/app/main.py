"""Updates Manager Tool - Main Window."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from .api_client import ApiClient, ApiConfig
from .device_manager import DeviceManager
from .logger import setup_logger
from .settings import get_token, SettingsManager
from .storage import get_app_dir, load_profiles, load_ui_state
from .version import __version__
from .widgets import (
    ChannelsWidget,
    DashboardWidget,
    DiagnosticsWidget,
    FleetWidget,
    HistoryWidget,
    PublishWidget,
    SettingsWidget,
)


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Updates Manager Tool v{__version__}")
        self.resize(1280, 800)

        # Setup logging
        app_dir = get_app_dir()
        self.app_logger = setup_logger("app", str(app_dir / "logs" / "app.log"))
        self.api_logger = setup_logger("api", str(app_dir / "logs" / "api.log"))

        # Initialize settings manager
        self.settings_manager = SettingsManager(app_dir)

        # Initialize device manager
        self.device_manager = DeviceManager()
        self.device_manager.load_device_key()

        # Load profiles
        self.profiles = load_profiles()
        self.ui_state = load_ui_state()

        # Build UI
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                color: white;
                border: none;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px 16px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)

        self.stack = QStackedWidget()
        self.pages = {}

        self._build_pages()
        self._build_layout()
        
        # Start heartbeat if device is registered
        if self.device_manager.device_key:
            self.device_manager.start_heartbeat(interval=60)

    def _build_layout(self):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

    def _add_page(self, name: str, widget: QWidget):
        item = QListWidgetItem(name)
        self.sidebar.addItem(item)
        self.stack.addWidget(widget)
        self.pages[name] = widget

    def _build_pages(self):
        # Dashboard
        dashboard = DashboardWidget(self._api_client)
        dashboard.request_navigate.connect(self._navigate_to)
        self._add_page("📊 Dashboard", dashboard)

        # Publish Release
        publish = PublishWidget(self._api_client)
        self._add_page("📦 Publish", publish)

        # Channels
        channels = ChannelsWidget(self._api_client)
        self._add_page("📡 Channels", channels)

        # Fleet Status
        fleet = FleetWidget(self._api_client)
        self._add_page("🖥️ Fleet", fleet)

        # Update History
        history = HistoryWidget(self._api_client)
        self._add_page("📜 History", history)

        # Diagnostics
        diagnostics = DiagnosticsWidget(self._api_client)
        self._add_page("🔧 Diagnostics", diagnostics)

        # Settings
        settings = SettingsWidget(main_window=self)
        settings.profile_changed.connect(self._on_profile_changed)
        self._add_page("⚙️ Settings", settings)

    def _navigate_to(self, page_name: str):
        """Navigate to a specific page by name."""
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            if page_name.lower() in item.text().lower():
                self.sidebar.setCurrentRow(i)
                return

    def _api_client(self) -> ApiClient:
        """Create an API client using the active profile."""
        profiles = load_profiles()
        active = profiles.get("active")
        profile = {}

        if active:
            for p in profiles.get("profiles", []):
                if p.get("name") == active:
                    profile = p
                    break

        base_url = profile.get("base_url", "https://meeting.ygsoft.fr")
        token = get_token(active) if active else None
        token = token or os.environ.get("MEETING_TOKEN", "")

        cfg = ApiConfig(
            base_url=base_url,
            token=token,
            timeout=int(profile.get("timeout", 20)),
            retries=int(profile.get("retries", 3)),
        )
        return ApiClient(cfg, logger=self.app_logger, api_logger=self.api_logger)

    def _on_profile_changed(self):
        """Handle profile change - reload profiles."""
        self.profiles = load_profiles()
        self.app_logger.info("Profile changed, reloaded profiles")

    def closeEvent(self, event):
        """Cleanup on window close."""
        self.device_manager.stop_heartbeat()
        super().closeEvent(event)


def check_registration(app: QApplication) -> DeviceManager:
    """Check if device is registered, show registration dialog if not.
    
    Returns:
        DeviceManager instance (registered) or None if user cancelled
    """
    from .widgets.registration_dialog import DeviceRegistrationDialog
    
    device_manager = DeviceManager()
    device_manager.load_device_key()
    
    if not device_manager.is_registered():
        # Show mandatory registration dialog
        dialog = DeviceRegistrationDialog()
        result = dialog.exec()
        
        if result == DeviceRegistrationDialog.Accepted:
            # Save credentials
            device_key, token_code, server_url = dialog.get_credentials()
            device_manager.save_device_key(device_key, token_code, server_url)
            return device_manager
        else:
            # User cancelled - exit
            return None
    
    return device_manager


def main():
    app = QApplication(sys.argv)

    # Apply global stylesheet
    app.setStyleSheet("""
        QMainWindow, QDialog {
            background-color: #1e1e1e;
        }
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            padding: 6px 16px;
            border-radius: 4px;
            background-color: #3d3d3d;
            color: white;
            border: none;
        }
        QPushButton:hover {
            background-color: #4d4d4d;
        }
        QPushButton:pressed {
            background-color: #2d2d2d;
        }
        QLineEdit, QTextEdit, QSpinBox, QComboBox {
            padding: 6px;
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            background-color: #2d2d2d;
            color: white;
        }
        QLineEdit:focus, QTextEdit:focus {
            border-color: #4CAF50;
        }
        QTableWidget {
            gridline-color: #3d3d3d;
            background-color: #2d2d2d;
            alternate-background-color: #353535;
            color: white;
        }
        QHeaderView::section {
            background-color: #3d3d3d;
            color: white;
            padding: 8px;
            border: none;
        }
        QTableWidget::item:selected {
            background-color: #4CAF50;
        }
        QProgressBar {
            border: 1px solid #3d3d3d;
            border-radius: 4px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
        }
        QLabel {
            color: white;
        }
    """)

    # Check registration FIRST - mandatory
    device_manager = check_registration(app)
    if device_manager is None:
        # User cancelled registration
        sys.exit(0)
    
    # Now create and show main window
    window = MainWindow()
    window.device_manager = device_manager  # Use the already-registered device manager
    
    # Start heartbeat
    if device_manager.is_registered():
        device_manager.start_heartbeat(interval=60)
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

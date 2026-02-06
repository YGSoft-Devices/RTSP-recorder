"""Channels widget - CRUD operations for update channels."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)

if TYPE_CHECKING:
    from ..api_client import ApiClient


class ChannelDialog(QDialog):
    """Dialog for creating/editing a channel."""

    def __init__(self, parent=None, channel_data: Optional[dict] = None):
        super().__init__(parent)
        self.channel_data = channel_data or {}
        self.setWindowTitle("Edit Channel" if channel_data else "Create Channel")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.device_type = QLineEdit(self.channel_data.get("device_type", ""))
        self.device_type.setPlaceholderText("e.g., rpi4")
        form.addRow("Device Type:", self.device_type)

        self.distribution = QLineEdit(self.channel_data.get("distribution", ""))
        self.distribution.setPlaceholderText("e.g., stable")
        form.addRow("Distribution:", self.distribution)

        self.channel = QLineEdit(self.channel_data.get("channel", "default"))
        self.channel.setPlaceholderText("e.g., default")
        form.addRow("Channel:", self.channel)

        self.target_version = QLineEdit(self.channel_data.get("target_version", ""))
        self.target_version.setPlaceholderText("e.g., 1.2.3")
        form.addRow("Target Version:", self.target_version)

        self.active = QCheckBox()
        self.active.setChecked(self.channel_data.get("active", True))
        form.addRow("Active:", self.active)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "device_type": self.device_type.text().strip(),
            "distribution": self.distribution.text().strip(),
            "channel": self.channel.text().strip() or "default",
            "target_version": self.target_version.text().strip(),
            "active": 1 if self.active.isChecked() else 0,
        }


class ChannelsWidget(QWidget):
    """Channels page with full CRUD."""

    COLUMNS = ["ID", "Device Type", "Distribution", "Channel", "Target Version", "Active", "Artifacts", "Updated At"]

    def __init__(self, get_api_client):
        super().__init__()
        self.get_api_client = get_api_client
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Title
        title = QLabel("Update Channels")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Toolbar
        toolbar = QHBoxLayout()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh_data)

        btn_create = QPushButton("➕ Create Channel")
        btn_create.clicked.connect(self._create_channel)

        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self._edit_channel)

        btn_toggle = QPushButton("🔘 Toggle Active")
        btn_toggle.clicked.connect(self._toggle_active)

        btn_delete = QPushButton("🗑️ Delete Selected")
        btn_delete.clicked.connect(self._delete_channel)

        btn_verify = QPushButton("✅ Verify Artifacts")
        btn_verify.clicked.connect(self._verify_artifacts)

        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_create)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_toggle)
        toolbar.addWidget(btn_delete)
        toolbar.addWidget(btn_verify)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        # Status
        self.status_label = QLabel("Click 'Refresh' to load channels")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

    def refresh_data(self):
        """Fetch channels from API and populate table."""
        self.status_label.setText("Loading...")
        try:
            api = self.get_api_client()
            data = api.list_channels()
            items = data.get("items", [])

            self.table.setRowCount(len(items))
            for row, ch in enumerate(items):
                self.table.setItem(row, 0, QTableWidgetItem(str(ch.get("id", ""))))
                self.table.setItem(row, 1, QTableWidgetItem(ch.get("device_type", "")))
                self.table.setItem(row, 2, QTableWidgetItem(ch.get("distribution", "")))
                self.table.setItem(row, 3, QTableWidgetItem(ch.get("channel", "")))
                self.table.setItem(row, 4, QTableWidgetItem(ch.get("target_version", "")))

                # Active badge
                active_item = QTableWidgetItem("✅ Yes" if ch.get("active") else "❌ No")
                self.table.setItem(row, 5, active_item)

                # Artifacts status
                artifacts = ch.get("artifacts_status", "?")
                if artifacts == "OK":
                    artifacts_text = "✅ OK"
                elif artifacts == "MISSING":
                    artifacts_text = "❌ Missing"
                else:
                    artifacts_text = "⚠️ Unknown"
                self.table.setItem(row, 6, QTableWidgetItem(artifacts_text))

                self.table.setItem(row, 7, QTableWidgetItem(ch.get("updated_at", "")[:19] if ch.get("updated_at") else ""))

            self.status_label.setText(f"Loaded {len(items)} channels")

        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            QMessageBox.warning(self, "Error", str(e))

    def _get_selected_channel(self) -> Optional[dict]:
        """Get selected channel data from table."""
        row = self.table.currentRow()
        if row < 0:
            return None

        return {
            "id": int(self.table.item(row, 0).text()),
            "device_type": self.table.item(row, 1).text(),
            "distribution": self.table.item(row, 2).text(),
            "channel": self.table.item(row, 3).text(),
            "target_version": self.table.item(row, 4).text(),
            "active": "Yes" in self.table.item(row, 5).text(),
        }

    def _create_channel(self):
        """Show dialog to create a new channel."""
        dialog = ChannelDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                api = self.get_api_client()
                api.create_channel(data)
                self.refresh_data()
                QMessageBox.information(self, "Success", "Channel created")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _edit_channel(self):
        """Show dialog to edit selected channel."""
        channel = self._get_selected_channel()
        if not channel:
            QMessageBox.warning(self, "Error", "Select a channel first")
            return

        dialog = ChannelDialog(self, channel)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                api = self.get_api_client()
                api.update_channel(channel["id"], data)
                self.refresh_data()
                QMessageBox.information(self, "Success", "Channel updated")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _toggle_active(self):
        """Toggle active status of selected channel."""
        channel = self._get_selected_channel()
        if not channel:
            QMessageBox.warning(self, "Error", "Select a channel first")
            return

        try:
            api = self.get_api_client()
            new_active = 0 if channel["active"] else 1
            api.update_channel(channel["id"], {"active": new_active})
            self.refresh_data()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _delete_channel(self):
        """Delete selected channel after confirmation."""
        channel = self._get_selected_channel()
        if not channel:
            QMessageBox.warning(self, "Error", "Select a channel first")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete channel '{channel['device_type']}/{channel['distribution']}/{channel['channel']}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                api = self.get_api_client()
                api.delete_channel(channel["id"])
                self.refresh_data()
                QMessageBox.information(self, "Deleted", "Channel deleted")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _verify_artifacts(self):
        """Verify artifacts for selected channel."""
        channel = self._get_selected_channel()
        if not channel:
            QMessageBox.warning(self, "Error", "Select a channel first")
            return

        if not channel.get("target_version"):
            QMessageBox.warning(self, "Error", "Channel has no target_version set")
            return

        try:
            api = self.get_api_client()
            result = api.verify_artifacts(
                channel["device_type"],
                channel["distribution"],
                channel["target_version"],
            )

            msg = f"Verification for {channel['device_type']}/{channel['distribution']} v{channel['target_version']}:\n\n"
            msg += f"Manifest exists: {result.get('manifest_exists', '?')}\n"
            msg += f"Archive exists: {result.get('archive_exists', '?')}\n"
            msg += f"SHA256 match: {result.get('sha256_match', '?')}\n"
            if result.get("missing_files"):
                msg += f"\nMissing files: {result['missing_files']}"

            QMessageBox.information(self, "Verification Result", msg)
            self.refresh_data()

        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

"""Fleet Status widget - device supervision and monitoring."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..api_client import ApiClient


class FleetWidget(QWidget):
    """Fleet Status page with filters and device list."""

    COLUMNS = [
        "Device Key",
        "Type",
        "Distribution",
        "Channel",
        "Installed",
        "Target",
        "State",
        "Last Seen",
        "Last Attempt",
        "Last Error",
    ]

    STATE_COLORS = {
        "UP_TO_DATE": "#4CAF50",
        "OUTDATED": "#FF9800",
        "FAILING": "#F44336",
        "IN_PROGRESS": "#2196F3",
        "UNKNOWN": "#9E9E9E",
    }

    def __init__(self, get_api_client):
        super().__init__()
        self.get_api_client = get_api_client
        self.current_page = 1
        self.page_size = 50
        self.total_items = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("Fleet Status")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Filters
        filters_group = QGroupBox("Filters")
        filters_layout = QHBoxLayout()

        filters_layout.addWidget(QLabel("State:"))
        self.filter_state = QComboBox()
        self.filter_state.addItems(["All", "UP_TO_DATE", "OUTDATED", "FAILING", "IN_PROGRESS", "UNKNOWN"])
        filters_layout.addWidget(self.filter_state)

        filters_layout.addWidget(QLabel("Device Type:"))
        self.filter_device_type = QLineEdit()
        self.filter_device_type.setPlaceholderText("e.g., rpi4")
        self.filter_device_type.setMaximumWidth(120)
        filters_layout.addWidget(self.filter_device_type)

        filters_layout.addWidget(QLabel("Distribution:"))
        self.filter_distribution = QLineEdit()
        self.filter_distribution.setPlaceholderText("e.g., stable")
        self.filter_distribution.setMaximumWidth(120)
        filters_layout.addWidget(self.filter_distribution)

        filters_layout.addWidget(QLabel("Search:"))
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText("Device key...")
        self.filter_search.setMaximumWidth(200)
        filters_layout.addWidget(self.filter_search)

        btn_apply = QPushButton("🔍 Apply")
        btn_apply.clicked.connect(self._apply_filters)
        filters_layout.addWidget(btn_apply)

        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._clear_filters)
        filters_layout.addWidget(btn_clear)

        filters_layout.addStretch()
        filters_group.setLayout(filters_layout)
        layout.addWidget(filters_group)

        # Toolbar
        toolbar = QHBoxLayout()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh_data)

        btn_export_csv = QPushButton("📥 Export CSV")
        btn_export_csv.clicked.connect(lambda: self._export("csv"))

        btn_export_json = QPushButton("📥 Export JSON")
        btn_export_json.clicked.connect(lambda: self._export("json"))

        btn_copy = QPushButton("📋 Copy Device Key")
        btn_copy.clicked.connect(self._copy_device_key)

        btn_history = QPushButton("📜 Open History")
        btn_history.clicked.connect(self._open_device_history)

        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_export_csv)
        toolbar.addWidget(btn_export_json)
        toolbar.addWidget(btn_copy)
        toolbar.addWidget(btn_history)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Pagination
        pagination_layout = QHBoxLayout()

        btn_prev = QPushButton("◀ Previous")
        btn_prev.clicked.connect(self._prev_page)
        pagination_layout.addWidget(btn_prev)

        self.page_label = QLabel("Page 1")
        pagination_layout.addWidget(self.page_label)

        btn_next = QPushButton("Next ▶")
        btn_next.clicked.connect(self._next_page)
        pagination_layout.addWidget(btn_next)

        pagination_layout.addWidget(QLabel("Page size:"))
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(10, 200)
        self.page_size_spin.setValue(50)
        self.page_size_spin.valueChanged.connect(self._on_page_size_changed)
        pagination_layout.addWidget(self.page_size_spin)

        pagination_layout.addStretch()

        self.status_label = QLabel("Click 'Refresh' to load fleet data")
        self.status_label.setStyleSheet("color: gray;")
        pagination_layout.addWidget(self.status_label)

        layout.addLayout(pagination_layout)

    def _build_params(self) -> dict:
        """Build query params from filters."""
        params = {
            "page": self.current_page,
            "page_size": self.page_size,
        }

        state = self.filter_state.currentText()
        if state != "All":
            params["state"] = state

        if self.filter_device_type.text().strip():
            params["device_type"] = self.filter_device_type.text().strip()

        if self.filter_distribution.text().strip():
            params["distribution"] = self.filter_distribution.text().strip()

        if self.filter_search.text().strip():
            params["search"] = self.filter_search.text().strip()

        return params

    def refresh_data(self):
        """Fetch fleet data from API."""
        self.status_label.setText("Loading...")
        try:
            api = self.get_api_client()
            params = self._build_params()
            data = api.list_device_updates(params)

            items = data.get("items", [])
            self.total_items = data.get("total", len(items))
            total_pages = max(1, (self.total_items + self.page_size - 1) // self.page_size)

            self.table.setRowCount(len(items))
            for row, dev in enumerate(items):
                # Device key (masked or full based on settings)
                device_key = dev.get("device_key", "")
                self.table.setItem(row, 0, QTableWidgetItem(device_key))

                self.table.setItem(row, 1, QTableWidgetItem(dev.get("device_type", "")))
                self.table.setItem(row, 2, QTableWidgetItem(dev.get("distribution", "")))
                self.table.setItem(row, 3, QTableWidgetItem(dev.get("channel", "")))
                self.table.setItem(row, 4, QTableWidgetItem(dev.get("installed_version", "")))
                self.table.setItem(row, 5, QTableWidgetItem(dev.get("target_version", "")))

                # State with color
                state = dev.get("computed_state", "UNKNOWN")
                state_item = QTableWidgetItem(state)
                color = self.STATE_COLORS.get(state, "#9E9E9E")
                state_item.setBackground(Qt.GlobalColor.transparent)
                state_item.setForeground(Qt.GlobalColor.white if state != "UNKNOWN" else Qt.GlobalColor.darkGray)
                # Use stylesheet-like approach
                self.table.setItem(row, 6, state_item)

                last_seen = dev.get("last_seen", "")[:19] if dev.get("last_seen") else ""
                self.table.setItem(row, 7, QTableWidgetItem(last_seen))

                last_attempt = dev.get("last_attempt_at", "")[:19] if dev.get("last_attempt_at") else ""
                self.table.setItem(row, 8, QTableWidgetItem(last_attempt))

                last_error = dev.get("last_error", "") or ""
                # Truncate long errors
                if len(last_error) > 50:
                    last_error = last_error[:47] + "..."
                self.table.setItem(row, 9, QTableWidgetItem(last_error))

            self.page_label.setText(f"Page {self.current_page} / {total_pages}")
            self.status_label.setText(f"Showing {len(items)} of {self.total_items} devices")

        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            QMessageBox.warning(self, "Error", str(e))

    def _apply_filters(self):
        self.current_page = 1
        self.refresh_data()

    def _clear_filters(self):
        self.filter_state.setCurrentIndex(0)
        self.filter_device_type.clear()
        self.filter_distribution.clear()
        self.filter_search.clear()
        self.current_page = 1
        self.refresh_data()

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_data()

    def _next_page(self):
        total_pages = max(1, (self.total_items + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_data()

    def _on_page_size_changed(self, value: int):
        self.page_size = value
        self.current_page = 1
        self.refresh_data()

    def _copy_device_key(self):
        """Copy selected device key to clipboard."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Select a device first")
            return

        device_key = self.table.item(row, 0).text()
        QApplication.clipboard().setText(device_key)
        self.status_label.setText(f"Copied: {device_key}")

    def _open_device_history(self):
        """Signal to open history for selected device."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Select a device first")
            return

        device_key = self.table.item(row, 0).text()
        # This would typically emit a signal to parent to switch to history tab with filter
        QMessageBox.information(self, "Device History", f"Open history for: {device_key}\n\n(Navigate to History tab and filter by this device)")

    def _export(self, fmt: str):
        """Export fleet data to file."""
        try:
            api = self.get_api_client()
            data = api.export_device_updates(fmt)

            # Choose save location
            ext = "csv" if fmt == "csv" else "json"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Export as {fmt.upper()}",
                f"fleet_export.{ext}",
                f"{fmt.upper()} Files (*.{ext})",
            )
            if not file_path:
                return

            # Write to file
            if fmt == "csv":
                content = data.get("csv", "") if isinstance(data, dict) else str(data)
            else:
                import json
                content = json.dumps(data, indent=2)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.status_label.setText(f"Exported to {file_path}")
            QMessageBox.information(self, "Export", f"Exported to {file_path}")

        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

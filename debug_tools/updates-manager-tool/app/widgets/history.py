"""Update History widget - audit log of device updates."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..api_client import ApiClient


class HistoryDetailDialog(QDialog):
    """Dialog showing full details of a history record."""

    def __init__(self, parent, record: dict):
        super().__init__(parent)
        self.setWindowTitle("Update History Detail")
        self.setMinimumSize(500, 400)
        self._build_ui(record)

    def _build_ui(self, record: dict):
        layout = QVBoxLayout(self)

        # Info labels
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel(f"<b>Device Key:</b> {record.get('device_key', '?')}"))
        info_layout.addWidget(QLabel(f"<b>Target Version:</b> {record.get('target_version', '?')}"))
        info_layout.addWidget(QLabel(f"<b>Installed Version:</b> {record.get('installed_version', '?')}"))
        info_layout.addWidget(QLabel(f"<b>Status:</b> {record.get('status', '?')}"))
        info_layout.addWidget(QLabel(f"<b>Created At:</b> {record.get('created_at', '?')}"))
        info_layout.addWidget(QLabel(f"<b>Completed At:</b> {record.get('completed_at', '?')}"))

        duration = record.get("duration")
        if duration:
            info_layout.addWidget(QLabel(f"<b>Duration:</b> {duration}s"))

        layout.addLayout(info_layout)

        # Message
        layout.addWidget(QLabel("<b>Message:</b>"))
        message_text = QTextEdit()
        message_text.setReadOnly(True)
        message_text.setPlainText(record.get("message", "") or "No message")
        layout.addWidget(message_text)

        # Raw payload (if available)
        payload = record.get("payload")
        if payload:
            layout.addWidget(QLabel("<b>Raw Payload:</b>"))
            payload_text = QTextEdit()
            payload_text.setReadOnly(True)
            import json
            payload_text.setPlainText(json.dumps(payload, indent=2) if isinstance(payload, dict) else str(payload))
            layout.addWidget(payload_text)

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class HistoryWidget(QWidget):
    """Update History page with filters and audit log."""

    COLUMNS = [
        "Created At",
        "Device Key",
        "Target Version",
        "Installed Version",
        "Status",
        "Duration (s)",
        "Message",
    ]

    STATUS_ICONS = {
        "success": "✅",
        "failed": "❌",
        "pending": "⏳",
        "in_progress": "🔄",
    }

    def __init__(self, get_api_client):
        super().__init__()
        self.get_api_client = get_api_client
        self.current_page = 1
        self.page_size = 50
        self.total_items = 0
        self._history_data = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("Update History")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Filters
        filters_group = QGroupBox("Filters")
        filters_layout = QHBoxLayout()

        filters_layout.addWidget(QLabel("Device Key:"))
        self.filter_device_key = QLineEdit()
        self.filter_device_key.setPlaceholderText("Filter by device...")
        self.filter_device_key.setMaximumWidth(200)
        filters_layout.addWidget(self.filter_device_key)

        filters_layout.addWidget(QLabel("Status:"))
        self.filter_status = QComboBox()
        self.filter_status.addItems(["All", "success", "failed", "pending", "in_progress"])
        filters_layout.addWidget(self.filter_status)

        filters_layout.addWidget(QLabel("Version:"))
        self.filter_version = QLineEdit()
        self.filter_version.setPlaceholderText("e.g., 1.2.3")
        self.filter_version.setMaximumWidth(100)
        filters_layout.addWidget(self.filter_version)

        filters_layout.addWidget(QLabel("From:"))
        self.filter_date_from = QDateEdit()
        self.filter_date_from.setCalendarPopup(True)
        self.filter_date_from.setDate((datetime.now() - timedelta(days=30)).date())
        filters_layout.addWidget(self.filter_date_from)

        filters_layout.addWidget(QLabel("To:"))
        self.filter_date_to = QDateEdit()
        self.filter_date_to.setCalendarPopup(True)
        self.filter_date_to.setDate(datetime.now().date())
        filters_layout.addWidget(self.filter_date_to)

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

        btn_detail = QPushButton("📋 View Details")
        btn_detail.clicked.connect(self._show_details)

        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_detail)
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
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._show_details)
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

        self.status_label = QLabel("Click 'Refresh' to load history")
        self.status_label.setStyleSheet("color: gray;")
        pagination_layout.addWidget(self.status_label)

        layout.addLayout(pagination_layout)

    def _build_params(self) -> dict:
        """Build query params from filters."""
        params = {
            "page": self.current_page,
            "page_size": self.page_size,
        }

        if self.filter_device_key.text().strip():
            params["device_key"] = self.filter_device_key.text().strip()

        status = self.filter_status.currentText()
        if status != "All":
            params["status"] = status

        if self.filter_version.text().strip():
            params["version"] = self.filter_version.text().strip()

        params["date_from"] = self.filter_date_from.date().toString("yyyy-MM-dd")
        params["date_to"] = self.filter_date_to.date().toString("yyyy-MM-dd")

        return params

    def refresh_data(self):
        """Fetch history from API."""
        self.status_label.setText("Loading...")
        try:
            api = self.get_api_client()
            params = self._build_params()
            data = api.list_update_history(params)

            items = data.get("items", [])
            self._history_data = items
            self.total_items = data.get("total", len(items))
            total_pages = max(1, (self.total_items + self.page_size - 1) // self.page_size)

            self.table.setRowCount(len(items))
            for row, rec in enumerate(items):
                created_at = rec.get("created_at", "")[:19] if rec.get("created_at") else ""
                self.table.setItem(row, 0, QTableWidgetItem(created_at))

                self.table.setItem(row, 1, QTableWidgetItem(rec.get("device_key", "")))
                self.table.setItem(row, 2, QTableWidgetItem(rec.get("target_version", "")))
                self.table.setItem(row, 3, QTableWidgetItem(rec.get("installed_version", "")))

                status = rec.get("status", "")
                icon = self.STATUS_ICONS.get(status, "❓")
                self.table.setItem(row, 4, QTableWidgetItem(f"{icon} {status}"))

                duration = rec.get("duration")
                self.table.setItem(row, 5, QTableWidgetItem(str(duration) if duration else ""))

                message = rec.get("message", "") or ""
                if len(message) > 60:
                    message = message[:57] + "..."
                self.table.setItem(row, 6, QTableWidgetItem(message))

            self.page_label.setText(f"Page {self.current_page} / {total_pages}")
            self.status_label.setText(f"Showing {len(items)} of {self.total_items} records")

        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            QMessageBox.warning(self, "Error", str(e))

    def _apply_filters(self):
        self.current_page = 1
        self.refresh_data()

    def _clear_filters(self):
        self.filter_device_key.clear()
        self.filter_status.setCurrentIndex(0)
        self.filter_version.clear()
        self.filter_date_from.setDate((datetime.now() - timedelta(days=30)).date())
        self.filter_date_to.setDate(datetime.now().date())
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

    def _show_details(self):
        """Show detail dialog for selected record."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self._history_data):
            QMessageBox.warning(self, "Error", "Select a record first")
            return

        record = self._history_data[row]
        dialog = HistoryDetailDialog(self, record)
        dialog.exec()

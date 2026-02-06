"""Dashboard widget - quick glance at fleet status and recent activity."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ..api_client import ApiClient


class StatCard(QFrame):
    """A card displaying a single statistic with label and value."""

    def __init__(self, title: str, value: str = "—", color: str = "#2196F3"):
        super().__init__()
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet(f"""
            StatCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {color}, stop:1 {color}dd);
                border-radius: 8px;
                padding: 16px;
            }}
            QLabel {{
                color: white;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.value_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, value: str):
        self.value_label.setText(value)


class DashboardWidget(QWidget):
    """Dashboard page with fleet overview and quick actions."""

    request_navigate = Signal(str)  # Signal to navigate to another page

    def __init__(self, get_api_client):
        super().__init__()
        self.get_api_client = get_api_client
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Title
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # Stats cards row
        cards_layout = QGridLayout()
        cards_layout.setSpacing(16)

        self.card_total = StatCard("Total Devices", "—", "#607D8B")
        self.card_uptodate = StatCard("Up to Date", "—", "#4CAF50")
        self.card_outdated = StatCard("Outdated", "—", "#FF9800")
        self.card_failing = StatCard("Failing", "—", "#F44336")
        self.card_unknown = StatCard("Unknown", "—", "#9E9E9E")

        cards_layout.addWidget(self.card_total, 0, 0)
        cards_layout.addWidget(self.card_uptodate, 0, 1)
        cards_layout.addWidget(self.card_outdated, 0, 2)
        cards_layout.addWidget(self.card_failing, 0, 3)
        cards_layout.addWidget(self.card_unknown, 0, 4)

        layout.addLayout(cards_layout)

        # Middle section: recent activity + quick actions
        middle_layout = QHBoxLayout()

        # Recent publish activity
        activity_frame = QFrame()
        activity_frame.setFrameStyle(QFrame.StyledPanel)
        activity_layout = QVBoxLayout(activity_frame)
        activity_label = QLabel("Recent Publish Activity")
        activity_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        activity_layout.addWidget(activity_label)

        self.activity_list = QListWidget()
        self.activity_list.setMaximumHeight(200)
        activity_layout.addWidget(self.activity_list)

        middle_layout.addWidget(activity_frame, 2)

        # Quick actions
        actions_frame = QFrame()
        actions_frame.setFrameStyle(QFrame.StyledPanel)
        actions_layout = QVBoxLayout(actions_frame)
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        actions_layout.addWidget(actions_label)

        btn_publish = QPushButton("📦 Publish Release")
        btn_publish.setMinimumHeight(40)
        btn_publish.clicked.connect(lambda: self.request_navigate.emit("Publish Release"))

        btn_target = QPushButton("🎯 Set Target Version")
        btn_target.setMinimumHeight(40)
        btn_target.clicked.connect(lambda: self.request_navigate.emit("Channels"))

        btn_verify = QPushButton("✅ Verify Artifacts")
        btn_verify.setMinimumHeight(40)
        btn_verify.clicked.connect(lambda: self.request_navigate.emit("Diagnostics"))

        btn_refresh = QPushButton("🔄 Refresh Dashboard")
        btn_refresh.setMinimumHeight(40)
        btn_refresh.clicked.connect(self.refresh_data)

        actions_layout.addWidget(btn_publish)
        actions_layout.addWidget(btn_target)
        actions_layout.addWidget(btn_verify)
        actions_layout.addWidget(btn_refresh)
        actions_layout.addStretch()

        middle_layout.addWidget(actions_frame, 1)
        layout.addLayout(middle_layout)

        # Status bar
        self.status_label = QLabel("Click 'Refresh Dashboard' to load data")
        self.status_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def refresh_data(self):
        """Fetch fleet data and update the dashboard."""
        self.status_label.setText("Loading...")
        try:
            api = self.get_api_client()
            data = api.list_device_updates({"page": 1, "page_size": 1000})

            items = data.get("items", [])
            total = len(items)

            # Count by computed state
            counts = {"UP_TO_DATE": 0, "OUTDATED": 0, "FAILING": 0, "UNKNOWN": 0}
            for item in items:
                state = item.get("computed_state", "UNKNOWN")
                if state in counts:
                    counts[state] += 1
                else:
                    counts["UNKNOWN"] += 1

            self.card_total.set_value(str(total))
            self.card_uptodate.set_value(str(counts["UP_TO_DATE"]))
            self.card_outdated.set_value(str(counts["OUTDATED"]))
            self.card_failing.set_value(str(counts["FAILING"]))
            self.card_unknown.set_value(str(counts["UNKNOWN"]))

            self.status_label.setText(f"Last updated: {total} devices loaded")

        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            self.card_total.set_value("?")
            self.card_uptodate.set_value("?")
            self.card_outdated.set_value("?")
            self.card_failing.set_value("?")
            self.card_unknown.set_value("?")

        # Load local publish history
        self._load_publish_history()

    def _load_publish_history(self):
        """Load recent publish activity from local storage."""
        from ..storage import load_publish_history

        self.activity_list.clear()
        history = load_publish_history()
        events = history.get("events", [])[-10:]  # Last 10 events
        events.reverse()

        if not events:
            self.activity_list.addItem("No recent publish activity")
            return

        for event in events:
            ts = event.get("timestamp", "?")[:19]
            device_type = event.get("device_type", "?")
            version = event.get("version", "?")
            status = event.get("status", "?")
            icon = "✅" if status == "success" else "❌"
            item = QListWidgetItem(f"{icon} {ts} — {device_type} v{version}")
            self.activity_list.addItem(item)

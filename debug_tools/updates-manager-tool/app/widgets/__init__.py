# Updates Manager Tool - Widget modules
from .dashboard import DashboardWidget
from .publish import PublishWidget
from .channels import ChannelsWidget
from .fleet import FleetWidget
from .history import HistoryWidget
from .diagnostics import DiagnosticsWidget
from .settings import SettingsWidget

__all__ = [
    "DashboardWidget",
    "PublishWidget",
    "ChannelsWidget",
    "FleetWidget",
    "HistoryWidget",
    "DiagnosticsWidget",
    "SettingsWidget",
]

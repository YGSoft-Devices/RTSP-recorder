from __future__ import annotations

from typing import Any, Dict

from .api_client import ApiClient


class FleetService:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_device_updates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.list_device_updates(params)

    def export(self, fmt: str = "csv") -> Dict[str, Any]:
        return self.api.export_device_updates(fmt)

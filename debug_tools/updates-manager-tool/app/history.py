from __future__ import annotations

from typing import Any, Dict

from .api_client import ApiClient


class HistoryService:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.list_update_history(params)

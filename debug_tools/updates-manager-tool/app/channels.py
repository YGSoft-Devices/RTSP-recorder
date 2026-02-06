from __future__ import annotations

from typing import Any, Dict

from .api_client import ApiClient


class ChannelsService:
    def __init__(self, api: ApiClient):
        self.api = api

    def list_channels(self) -> Dict[str, Any]:
        return self.api.list_channels()

    def create_channel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.create_channel(payload)

    def update_channel(self, channel_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.api.update_channel(channel_id, payload)

    def delete_channel(self, channel_id: int) -> Dict[str, Any]:
        return self.api.delete_channel(channel_id)

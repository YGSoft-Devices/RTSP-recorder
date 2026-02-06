from __future__ import annotations

from typing import Any, Dict, List

from .api_client import ApiClient, ApiError


class DiagnosticsService:
    def __init__(self, api: ApiClient):
        self.api = api

    def test_connection(self) -> Dict[str, Any]:
        # Prefer a lightweight endpoint if available; fallback to channels list.
        try:
            return {"ok": True, "result": self.api.list_channels()}
        except ApiError as exc:
            return {"ok": False, "error": str(exc)}

    def test_endpoints(self) -> List[Dict[str, Any]]:
        tests = [
            ("channels", lambda: self.api.list_channels()),
            ("verify", lambda: self.api.verify_artifacts("__test__", "__test__", "__test__")),
            ("fleet", lambda: self.api.list_device_updates({"page": 1, "page_size": 1})),
            ("history", lambda: self.api.list_update_history({"page": 1, "page_size": 1})),
        ]
        results = []
        for name, fn in tests:
            try:
                fn()
                results.append({"name": name, "ok": True})
            except Exception as exc:
                results.append({"name": name, "ok": False, "error": str(exc)})
        return results

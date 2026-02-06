from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


APP_DIR_NAME = "UpdatesManagerTool"


def get_app_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    app_dir = Path(base) / APP_DIR_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "logs").mkdir(parents=True, exist_ok=True)
    return app_dir


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def profiles_path() -> Path:
    return get_app_dir() / "profiles.json"


def ui_state_path() -> Path:
    return get_app_dir() / "ui_state.json"


def publish_history_path() -> Path:
    return get_app_dir() / "publish_history.json"


def load_profiles() -> Dict[str, Any]:
    return load_json(profiles_path(), {"profiles": [], "active": None})


def save_profiles(data: Dict[str, Any]) -> None:
    save_json(profiles_path(), data)


def load_ui_state() -> Dict[str, Any]:
    return load_json(ui_state_path(), {})


def save_ui_state(data: Dict[str, Any]) -> None:
    save_json(ui_state_path(), data)


def load_publish_history() -> Dict[str, Any]:
    return load_json(publish_history_path(), {"events": []})


def save_publish_history(data: Dict[str, Any]) -> None:
    save_json(publish_history_path(), data)

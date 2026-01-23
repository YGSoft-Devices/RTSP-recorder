# -*- coding: utf-8 -*-
"""
I18n Service - lightweight translation loader and helpers.
Version: 1.0.0
"""

import json
import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_LANG = "fr"
ENV_LANG_VAR = "RTSP_UI_LANG"
LANG_COOKIE_NAME = "lang"

I18N_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "i18n"))

_translations_cache: Dict[str, Dict[str, Any]] = {}


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def normalize_lang(lang: Optional[str]) -> Optional[str]:
    if not lang:
        return None
    normalized = lang.replace("_", "-").strip().lower()
    return normalized.split("-")[0] if normalized else None


def _safe_read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        logger.warning(f"Invalid i18n JSON at {path}: {exc}")
        return {}
    except Exception as exc:  # Defensive: never crash UI on i18n issues
        logger.warning(f"Failed to load i18n JSON at {path}: {exc}")
        return {}


def list_languages() -> list:
    if not os.path.isdir(I18N_DIR):
        return [DEFAULT_LANG]
    langs = []
    for filename in os.listdir(I18N_DIR):
        if filename.endswith(".json"):
            langs.append(os.path.splitext(filename)[0].lower())
    return sorted(set(langs)) or [DEFAULT_LANG]


def load_translations(lang: Optional[str]) -> Dict[str, Any]:
    normalized = normalize_lang(lang) or DEFAULT_LANG
    if normalized in _translations_cache:
        return _translations_cache[normalized]
    path = os.path.join(I18N_DIR, f"{normalized}.json")
    data = _safe_read_json(path)
    _translations_cache[normalized] = data
    return data


def load_translations_from_path(path: str) -> Dict[str, Any]:
    return _safe_read_json(path)


def resolve_request_lang(request, config: Optional[Dict[str, Any]] = None) -> str:
    candidates = []
    if request is not None:
        arg_lang = request.args.get("lang") if request.args else None
        if arg_lang:
            candidates.append(arg_lang)
        cookie_lang = request.cookies.get(LANG_COOKIE_NAME) if request.cookies else None
        if cookie_lang:
            candidates.append(cookie_lang)

    env_lang = os.getenv(ENV_LANG_VAR)
    if env_lang:
        candidates.append(env_lang)

    if config:
        cfg_lang = config.get("UI_LANG")
        if cfg_lang:
            candidates.append(cfg_lang)

    candidates.append(DEFAULT_LANG)

    available = set(list_languages())
    for candidate in candidates:
        normalized = normalize_lang(candidate)
        if normalized in available:
            return normalized
    return DEFAULT_LANG


def t(key: str, lang: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
    if not key:
        return ""
    requested = normalize_lang(lang) or DEFAULT_LANG
    primary = load_translations(requested)
    value = primary.get(key)
    if value is None and requested != DEFAULT_LANG:
        value = load_translations(DEFAULT_LANG).get(key)
    if value is None:
        value = key
    if not isinstance(value, str):
        value = str(value)
    if params:
        try:
            value = value.format_map(_SafeDict(params))
        except Exception:
            return value
    return value


def reset_cache() -> None:
    _translations_cache.clear()

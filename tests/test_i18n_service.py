# -*- coding: utf-8 -*-

import json
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
WEB_MANAGER_DIR = ROOT_DIR / "web-manager"

I18N_PATH = WEB_MANAGER_DIR / "services" / "i18n_service.py"
spec = importlib.util.spec_from_file_location("i18n_service", I18N_PATH)
i18n_service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i18n_service)


class DummyAccept:
    def __init__(self, value):
        self.value = value

    def best_match(self, choices, default=None):
        return self.value if self.value in choices else default


class DummyRequest:
    def __init__(self, args=None, cookies=None, accept_lang=None):
        self.args = args or {}
        self.cookies = cookies or {}
        self.accept_languages = DummyAccept(accept_lang)


@pytest.fixture()
def temp_locales(tmp_path, monkeypatch):
    locales_dir = tmp_path / "locales"
    custom_dir = tmp_path / "custom"
    locales_dir.mkdir(parents=True, exist_ok=True)
    custom_dir.mkdir(parents=True, exist_ok=True)

    fr = {
        "_meta": {"language": "Français", "code": "fr", "version": "test"},
        "common": {
            "hello": "Bonjour {name}",
            "fallback": "Secours"
        }
    }
    en = {
        "_meta": {"language": "English", "code": "en", "version": "test"},
        "common": {
            "hello": "Hello {name}"
        }
    }

    (locales_dir / "fr.json").write_text(json.dumps(fr, ensure_ascii=False), encoding="utf-8")
    (locales_dir / "en.json").write_text(json.dumps(en, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(i18n_service, "LOCALES_DIR", locales_dir)
    monkeypatch.setattr(i18n_service, "CUSTOM_LOCALES_DIR", custom_dir)
    monkeypatch.setattr(i18n_service, "BUILT_IN_LANGUAGES", ["fr", "en"])
    monkeypatch.setattr(i18n_service, "DEFAULT_LANGUAGE", "fr")

    i18n_service._translations_cache.clear()

    return locales_dir, custom_dir


def test_t_interpolation_and_fallback(temp_locales):
    text = i18n_service.t("en", "common.hello", {"name": "Cam"})
    assert text == "Hello Cam"

    # Missing in en, fallback to default (fr)
    fallback = i18n_service.t("en", "common.fallback")
    assert fallback == "Secours"

    # Missing in both -> key itself
    missing = i18n_service.t("en", "common.missing")
    assert missing == "common.missing"


def test_invalid_custom_json_is_ignored(temp_locales):
    _, custom_dir = temp_locales
    invalid_file = Path(custom_dir) / "en.json"
    invalid_file.write_text("{invalid json", encoding="utf-8")

    data = i18n_service.load_translation("en", force_reload=True)
    assert isinstance(data, dict)
    assert data.get("common", {}).get("hello") == "Hello {name}"


def test_get_user_language_priority(monkeypatch, temp_locales):
    # Query param has priority
    req = DummyRequest(args={"lang": "en"}, cookies={"language": "fr"}, accept_lang="fr")
    assert i18n_service.get_user_language(req) == "en"

    # Cookie overrides header
    req = DummyRequest(args={}, cookies={"language": "en"}, accept_lang="fr")
    assert i18n_service.get_user_language(req) == "en"

    # Header used when no query/cookie
    req = DummyRequest(args={}, cookies={}, accept_lang="en")
    assert i18n_service.get_user_language(req) == "en"

    # Env var used when no request
    monkeypatch.setenv("WEB_LANGUAGE", "en")
    assert i18n_service.get_user_language(None) == "en"

    monkeypatch.delenv("WEB_LANGUAGE", raising=False)

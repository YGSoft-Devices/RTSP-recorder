import json
import os
import sys
import types
from pathlib import Path

import pytest


if os.name == "nt" and "fcntl" not in sys.modules:
    sys.modules["fcntl"] = types.ModuleType("fcntl")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web-manager')))
from services import i18n_service


@pytest.fixture(autouse=True)
def reset_i18n_cache():
    i18n_service.reset_cache()
    yield
    i18n_service.reset_cache()


def _write_translation(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_fallback_chain(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n_service, "I18N_DIR", str(tmp_path))

    _write_translation(tmp_path / "fr.json", {"greeting": "Bonjour"})
    _write_translation(tmp_path / "en.json", {"hello": "Hello"})

    assert i18n_service.t("greeting", lang="en") == "Bonjour"


def test_interpolation(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n_service, "I18N_DIR", str(tmp_path))

    _write_translation(tmp_path / "fr.json", {"welcome": "Bonjour {name}"})

    assert i18n_service.t("welcome", lang="fr", params={"name": "Cam"}) == "Bonjour Cam"


def test_missing_key_returns_key(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n_service, "I18N_DIR", str(tmp_path))

    _write_translation(tmp_path / "fr.json", {"hello": "Bonjour"})

    assert i18n_service.t("missing.key", lang="fr") == "missing.key"


def test_invalid_json_handling(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n_service, "I18N_DIR", str(tmp_path))

    (tmp_path / "fr.json").write_text("{", encoding="utf-8")

    assert i18n_service.load_translations("fr") == {}
    assert i18n_service.t("anything", lang="fr") == "anything"

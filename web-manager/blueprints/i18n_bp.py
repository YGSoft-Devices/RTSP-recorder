# -*- coding: utf-8 -*-
"""
I18n Blueprint - translation endpoints.
Version: 1.0.0
"""

from flask import Blueprint, jsonify

from services.i18n_service import (
    DEFAULT_LANG,
    list_languages,
    load_translations,
    normalize_lang
)

i18n_bp = Blueprint("i18n", __name__)


@i18n_bp.route("/i18n/<lang>.json", methods=["GET"])
def i18n_json(lang: str):
    normalized = normalize_lang(lang) or DEFAULT_LANG
    translations = load_translations(normalized)
    return jsonify({
        "lang": normalized,
        "default_lang": DEFAULT_LANG,
        "available_langs": list_languages(),
        "translations": translations
    })

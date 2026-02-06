# -*- coding: utf-8 -*-
"""
I18n Blueprint - translation endpoints.
Version: 1.1.0
"""

from flask import Blueprint, jsonify, request, make_response

from services.config_service import load_config
from services.i18n_service import (
    DEFAULT_LANG,
    LANG_COOKIE_NAME,
    list_languages,
    load_translations,
    normalize_lang,
    resolve_request_lang,
    t as translate
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


@i18n_bp.route("/api/i18n/languages", methods=["GET"])
def get_languages():
    languages = []
    for code in list_languages():
        translations = load_translations(code)
        name = translations.get("i18n.language_name") or code.upper()
        languages.append({
            "code": code,
            "name": name,
            "native_name": name
        })

    try:
        config = load_config()
    except Exception:
        config = {}

    current_lang = resolve_request_lang(request, config)
    return jsonify({
        "success": True,
        "languages": languages,
        "current": current_lang,
        "default": DEFAULT_LANG
    })


@i18n_bp.route("/api/i18n/language", methods=["GET"])
def get_current_language():
    try:
        config = load_config()
    except Exception:
        config = {}

    current_lang = resolve_request_lang(request, config)
    return jsonify({
        "success": True,
        "language": current_lang
    })


@i18n_bp.route("/api/i18n/language", methods=["POST"])
def set_current_language():
    data = request.get_json(silent=True) or {}
    requested = data.get("language") or data.get("lang") or DEFAULT_LANG
    normalized = normalize_lang(requested) or DEFAULT_LANG

    if normalized not in list_languages():
        return jsonify({
            "success": False,
            "error": translate("ui.errors.invalid_language", DEFAULT_LANG, {"lang": requested})
        }), 400

    response = make_response(jsonify({
        "success": True,
        "language": normalized
    }))
    response.set_cookie(
        LANG_COOKIE_NAME,
        normalized,
        max_age=31536000,
        samesite="Lax"
    )
    return response


@i18n_bp.route("/api/i18n/translations/<lang>", methods=["GET"])
def get_translations(lang: str):
    normalized = normalize_lang(lang) or DEFAULT_LANG
    translations = load_translations(normalized)
    return jsonify({
        "success": True,
        "language": normalized,
        "translations": translations
    })

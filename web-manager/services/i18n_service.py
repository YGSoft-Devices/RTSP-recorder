#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n Service - Internationalization Service for RTSP Recorder Web Manager
Handles language detection, translation loading, and custom translation upload.

Version: 1.0.0
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Locales directory (built-in translations)
LOCALES_DIR = Path(__file__).parent.parent / 'static' / 'locales'

# Custom translations directory (user-uploaded)
CUSTOM_LOCALES_DIR = Path('/etc/rpi-cam/locales')

# Supported languages (built-in)
BUILT_IN_LANGUAGES = ['fr', 'en']

# Default language
DEFAULT_LANGUAGE = 'fr'

# Cache for loaded translations
_translations_cache: Dict[str, Dict] = {}

# ============================================================================
# TRANSLATION LOADING
# ============================================================================

def get_available_languages() -> List[Dict[str, str]]:
    """
    Get list of all available languages (built-in + custom).
    
    Returns:
        List of dicts with 'code', 'name', 'version', 'builtin' keys
    """
    languages = []
    
    # Load built-in languages
    if LOCALES_DIR.exists():
        for file in LOCALES_DIR.glob('*.json'):
            lang_code = file.stem
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    meta = data.get('_meta', {})
                    languages.append({
                        'code': lang_code,
                        'name': meta.get('language', lang_code.upper()),
                        'version': meta.get('version', '1.0.0'),
                        'builtin': True,
                        'author': meta.get('author', 'RTSP-Recorder Team')
                    })
            except Exception as e:
                logger.error(f"Error loading built-in language {lang_code}: {e}")
    
    # Load custom languages
    if CUSTOM_LOCALES_DIR.exists():
        for file in CUSTOM_LOCALES_DIR.glob('*.json'):
            lang_code = file.stem
            # Skip if already in built-in (custom overrides display but not code)
            existing = next((l for l in languages if l['code'] == lang_code), None)
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    meta = data.get('_meta', {})
                    lang_info = {
                        'code': lang_code,
                        'name': meta.get('language', lang_code.upper()),
                        'version': meta.get('version', '1.0.0'),
                        'builtin': False,
                        'author': meta.get('author', 'Custom'),
                        'custom': True
                    }
                    if existing:
                        # Mark as having custom override
                        existing['hasCustomOverride'] = True
                        existing['customVersion'] = meta.get('version', '1.0.0')
                    else:
                        languages.append(lang_info)
            except Exception as e:
                logger.error(f"Error loading custom language {lang_code}: {e}")
    
    return sorted(languages, key=lambda x: (not x['builtin'], x['code']))


def load_translation(lang_code: str, force_reload: bool = False) -> Dict:
    """
    Load translation for a given language code.
    Custom translations override built-in ones.
    
    Args:
        lang_code: Language code (e.g., 'fr', 'en')
        force_reload: Force reload from disk even if cached
        
    Returns:
        Translation dictionary
    """
    global _translations_cache
    
    cache_key = lang_code
    
    # Check cache
    if not force_reload and cache_key in _translations_cache:
        return _translations_cache[cache_key]
    
    translation = {}
    
    # First, load built-in translation
    builtin_file = LOCALES_DIR / f'{lang_code}.json'
    if builtin_file.exists():
        try:
            with open(builtin_file, 'r', encoding='utf-8') as f:
                translation = json.load(f)
                logger.debug(f"Loaded built-in translation for {lang_code}")
        except Exception as e:
            logger.error(f"Error loading built-in translation {lang_code}: {e}")
    
    # Then, merge custom translation (overrides built-in)
    custom_file = CUSTOM_LOCALES_DIR / f'{lang_code}.json'
    if custom_file.exists():
        try:
            with open(custom_file, 'r', encoding='utf-8') as f:
                custom_data = json.load(f)
                translation = deep_merge(translation, custom_data)
                logger.info(f"Merged custom translation for {lang_code}")
        except Exception as e:
            logger.error(f"Error loading custom translation {lang_code}: {e}")
    
    # Fallback to default language if not found
    if not translation and lang_code != DEFAULT_LANGUAGE:
        logger.warning(f"Translation {lang_code} not found, falling back to {DEFAULT_LANGUAGE}")
        return load_translation(DEFAULT_LANGUAGE, force_reload)
    
    # Cache it
    _translations_cache[cache_key] = translation
    
    return translation


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    Deep merge two dictionaries. Override values take precedence.
    
    Args:
        base: Base dictionary
        override: Override dictionary
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def get_translation(lang_code: str, key: str, default: str = None) -> str:
    """
    Get a specific translation by dot-notation key.
    
    Args:
        lang_code: Language code
        key: Dot-notation key (e.g., 'common.save', 'nav.home')
        default: Default value if key not found
        
    Returns:
        Translated string or default
    """
    translation = load_translation(lang_code)
    
    # Navigate the nested structure
    keys = key.split('.')
    value = translation
    
    try:
        for k in keys:
            value = value[k]
        return value if isinstance(value, str) else default or key
    except (KeyError, TypeError):
        return default or key


# ============================================================================
# CUSTOM TRANSLATION MANAGEMENT
# ============================================================================

def save_custom_translation(lang_code: str, data: Dict) -> Dict[str, Any]:
    """
    Save a custom translation file.
    
    Args:
        lang_code: Language code
        data: Translation data dictionary
        
    Returns:
        Dict with 'success', 'message', and optionally 'error'
    """
    global _translations_cache
    
    try:
        # Validate translation data
        validation = validate_translation(data)
        if not validation['valid']:
            return {
                'success': False,
                'message': 'Invalid translation format',
                'errors': validation['errors']
            }
        
        # Ensure directory exists
        CUSTOM_LOCALES_DIR.mkdir(parents=True, exist_ok=True)
        
        # Save the file
        file_path = CUSTOM_LOCALES_DIR / f'{lang_code}.json'
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Clear cache for this language
        if lang_code in _translations_cache:
            del _translations_cache[lang_code]
        
        logger.info(f"Saved custom translation for {lang_code}")
        
        return {
            'success': True,
            'message': f'Translation for {lang_code} saved successfully',
            'path': str(file_path)
        }
        
    except Exception as e:
        logger.error(f"Error saving custom translation {lang_code}: {e}")
        return {
            'success': False,
            'message': f'Error saving translation: {str(e)}'
        }


def delete_custom_translation(lang_code: str) -> Dict[str, Any]:
    """
    Delete a custom translation file.
    
    Args:
        lang_code: Language code
        
    Returns:
        Dict with 'success' and 'message'
    """
    global _translations_cache
    
    try:
        file_path = CUSTOM_LOCALES_DIR / f'{lang_code}.json'
        
        if not file_path.exists():
            return {
                'success': False,
                'message': f'Custom translation {lang_code} not found'
            }
        
        # Don't allow deleting built-in language overrides if they exist
        # (user should upload empty to reset, not delete)
        
        os.remove(file_path)
        
        # Clear cache
        if lang_code in _translations_cache:
            del _translations_cache[lang_code]
        
        logger.info(f"Deleted custom translation for {lang_code}")
        
        return {
            'success': True,
            'message': f'Custom translation {lang_code} deleted'
        }
        
    except Exception as e:
        logger.error(f"Error deleting custom translation {lang_code}: {e}")
        return {
            'success': False,
            'message': f'Error deleting translation: {str(e)}'
        }


def validate_translation(data: Dict) -> Dict[str, Any]:
    """
    Validate translation data structure.
    
    Args:
        data: Translation data dictionary
        
    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    errors = []
    
    # Must have _meta section
    if '_meta' not in data:
        errors.append('Missing _meta section')
    else:
        meta = data['_meta']
        if 'language' not in meta:
            errors.append('Missing _meta.language')
        if 'code' not in meta:
            errors.append('Missing _meta.code')
    
    # Check for some essential keys
    essential_sections = ['common', 'nav', 'header']
    for section in essential_sections:
        if section not in data:
            errors.append(f'Missing essential section: {section}')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def get_translation_template() -> Dict:
    """
    Get a template for creating new translations.
    Returns the default language translation as a template.
    
    Returns:
        Translation template dictionary
    """
    return load_translation(DEFAULT_LANGUAGE)


# ============================================================================
# USER PREFERENCE
# ============================================================================

def get_user_language(request=None) -> str:
    """
    Determine user's preferred language.
    Priority: cookie > Accept-Language header > default
    
    Args:
        request: Flask request object (optional)
        
    Returns:
        Language code
    """
    if request:
        # Check cookie first
        cookie_lang = request.cookies.get('language')
        if cookie_lang and is_language_available(cookie_lang):
            return cookie_lang
        
        # Check Accept-Language header
        accept_lang = request.accept_languages.best_match(
            [l['code'] for l in get_available_languages()],
            default=DEFAULT_LANGUAGE
        )
        if accept_lang:
            return accept_lang
    
    return DEFAULT_LANGUAGE


def is_language_available(lang_code: str) -> bool:
    """
    Check if a language is available.
    
    Args:
        lang_code: Language code
        
    Returns:
        True if available
    """
    available = get_available_languages()
    return any(l['code'] == lang_code for l in available)


# ============================================================================
# INITIALIZATION
# ============================================================================

def init_i18n_service():
    """Initialize the i18n service."""
    logger.info("Initializing i18n service")
    
    # Ensure custom locales directory exists
    CUSTOM_LOCALES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Pre-load built-in translations
    for lang in BUILT_IN_LANGUAGES:
        try:
            load_translation(lang)
            logger.info(f"Pre-loaded translation: {lang}")
        except Exception as e:
            logger.error(f"Failed to pre-load translation {lang}: {e}")
    
    languages = get_available_languages()
    logger.info(f"i18n service initialized with {len(languages)} language(s): {[l['code'] for l in languages]}")


# Initialize on module load
init_i18n_service()

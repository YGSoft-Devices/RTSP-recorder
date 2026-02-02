#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n Blueprint - API endpoints for internationalization
Handles language selection, translation loading, and custom translation upload.

Version: 1.0.0
"""

import logging
from flask import Blueprint, jsonify, request, make_response

from services.i18n_service import (
    get_available_languages,
    load_translation,
    save_custom_translation,
    delete_custom_translation,
    get_user_language,
    get_translation_template,
    validate_translation,
    DEFAULT_LANGUAGE
)

logger = logging.getLogger(__name__)

i18n_bp = Blueprint('i18n', __name__)


# ============================================================================
# LANGUAGE ENDPOINTS
# ============================================================================

@i18n_bp.route('/api/i18n/languages', methods=['GET'])
def get_languages():
    """
    Get list of available languages.
    
    Returns:
        JSON: List of available languages with metadata
    """
    try:
        languages = get_available_languages()
        current_lang = get_user_language(request)
        
        return jsonify({
            'success': True,
            'languages': languages,
            'current': current_lang,
            'default': DEFAULT_LANGUAGE
        })
        
    except Exception as e:
        logger.error(f"Error getting languages: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@i18n_bp.route('/api/i18n/language', methods=['GET'])
def get_current_language():
    """
    Get current user language preference.
    
    Returns:
        JSON: Current language code and info
    """
    try:
        lang_code = get_user_language(request)
        languages = get_available_languages()
        lang_info = next((l for l in languages if l['code'] == lang_code), None)
        
        return jsonify({
            'success': True,
            'language': lang_code,
            'info': lang_info
        })
        
    except Exception as e:
        logger.error(f"Error getting current language: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@i18n_bp.route('/api/i18n/language', methods=['POST'])
def set_language():
    """
    Set user language preference (stored in cookie).
    
    Body:
        language: Language code (e.g., 'fr', 'en')
        
    Returns:
        JSON: Success status with Set-Cookie header
    """
    try:
        data = request.get_json(silent=True) or {}
        lang_code = data.get('language', DEFAULT_LANGUAGE)
        
        # Validate language exists
        languages = get_available_languages()
        if not any(l['code'] == lang_code for l in languages):
            return jsonify({
                'success': False,
                'error': f'Language {lang_code} not available'
            }), 400
        
        # Create response with cookie
        response = make_response(jsonify({
            'success': True,
            'language': lang_code,
            'message': f'Language set to {lang_code}'
        }))
        
        # Set cookie (1 year expiry)
        response.set_cookie(
            'language',
            lang_code,
            max_age=365 * 24 * 60 * 60,  # 1 year
            httponly=False,  # Allow JS access
            samesite='Lax'
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error setting language: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# TRANSLATION ENDPOINTS
# ============================================================================

@i18n_bp.route('/api/i18n/translations/<lang_code>', methods=['GET'])
def get_translation(lang_code: str):
    """
    Get translation data for a specific language.
    
    Args:
        lang_code: Language code (e.g., 'fr', 'en')
        
    Returns:
        JSON: Full translation dictionary
    """
    try:
        translation = load_translation(lang_code, force_reload=False)
        
        if not translation:
            return jsonify({
                'success': False,
                'error': f'Translation {lang_code} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'language': lang_code,
            'translation': translation
        })
        
    except Exception as e:
        logger.error(f"Error getting translation {lang_code}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@i18n_bp.route('/api/i18n/translations/<lang_code>', methods=['PUT', 'POST'])
def upload_translation(lang_code: str):
    """
    Upload a custom translation file.
    
    Args:
        lang_code: Language code
        
    Body:
        Full translation JSON data or file upload
        
    Returns:
        JSON: Success status
    """
    try:
        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'No file selected'
                }), 400
            
            if not file.filename.endswith('.json'):
                return jsonify({
                    'success': False,
                    'error': 'File must be JSON format'
                }), 400
            
            try:
                import json
                data = json.load(file)
            except json.JSONDecodeError as e:
                return jsonify({
                    'success': False,
                    'error': f'Invalid JSON: {str(e)}'
                }), 400
        
        # Handle JSON body
        else:
            data = request.get_json(silent=True)
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No translation data provided'
                }), 400
        
        # Validate the translation
        validation = validate_translation(data)
        if not validation['valid']:
            return jsonify({
                'success': False,
                'error': 'Invalid translation format',
                'details': validation['errors']
            }), 400
        
        # Update language code in meta if different
        if '_meta' in data:
            data['_meta']['code'] = lang_code
        
        # Save the translation
        result = save_custom_translation(lang_code, data)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error uploading translation {lang_code}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@i18n_bp.route('/api/i18n/translations/<lang_code>', methods=['DELETE'])
def remove_translation(lang_code: str):
    """
    Delete a custom translation file.
    Cannot delete built-in translations.
    
    Args:
        lang_code: Language code
        
    Returns:
        JSON: Success status
    """
    try:
        # Check if it's a built-in language
        languages = get_available_languages()
        lang_info = next((l for l in languages if l['code'] == lang_code), None)
        
        if lang_info and lang_info.get('builtin') and not lang_info.get('hasCustomOverride'):
            return jsonify({
                'success': False,
                'error': f'Cannot delete built-in translation {lang_code}'
            }), 400
        
        result = delete_custom_translation(lang_code)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
        
    except Exception as e:
        logger.error(f"Error deleting translation {lang_code}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@i18n_bp.route('/api/i18n/template', methods=['GET'])
def get_template():
    """
    Get translation template for creating new translations.
    Returns the default language as a starting point.
    
    Returns:
        JSON: Translation template
    """
    try:
        template = get_translation_template()
        
        # Clear meta for new translation
        if '_meta' in template:
            template['_meta'] = {
                'language': 'New Language',
                'code': 'xx',
                'version': '1.0.0',
                'author': 'Your Name'
            }
        
        return jsonify({
            'success': True,
            'template': template
        })
        
    except Exception as e:
        logger.error(f"Error getting template: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@i18n_bp.route('/api/i18n/validate', methods=['POST'])
def validate_upload():
    """
    Validate a translation file without saving.
    
    Body:
        Translation JSON data
        
    Returns:
        JSON: Validation result with errors if any
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False,
                'error': 'No translation data provided'
            }), 400
        
        validation = validate_translation(data)
        
        return jsonify({
            'success': True,
            'valid': validation['valid'],
            'errors': validation['errors']
        })
        
    except Exception as e:
        logger.error(f"Error validating translation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

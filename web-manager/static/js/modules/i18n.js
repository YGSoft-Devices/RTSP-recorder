/**
 * Internationalization (i18n) Module
 * Handles multilingual support for the RTSP Recorder Web Interface
 * 
 * @version 2.36.08
 */

const I18n = (function() {
    'use strict';

    // ============================================================================
    // CONFIGURATION
    // ============================================================================

    const CONFIG = {
        defaultLanguage: 'fr',
        fallbackLanguage: 'en',
        storageKey: 'rpi-cam-language',
        translationsEndpoint: '/api/i18n/translations',
        languagesEndpoint: '/api/i18n/languages',
        languageEndpoint: '/api/i18n/language',
        dataAttribute: 'data-i18n',
        dataAttrPlaceholder: 'data-i18n-placeholder',
        dataAttrTitle: 'data-i18n-title',
        dataAttrAlt: 'data-i18n-alt',
        interpolationPattern: /\{\{(\w+)\}\}/g
    };

    // ============================================================================
    // STATE
    // ============================================================================

    let currentLanguage = null;
    let translations = {};
    let defaultTranslations = {};
    let availableLanguages = [];
    let isInitialized = false;
    let onLanguageChangeCallbacks = [];

    // ============================================================================
    // UTILITY FUNCTIONS
    // ============================================================================

    /**
     * Deep get a value from an object using dot notation
     * @param {Object} obj - The object to query
     * @param {string} path - The path in dot notation (e.g., "common.yes")
     * @param {*} defaultValue - Default value if path not found
     * @returns {*} The value at the path or defaultValue
     */
    function deepGet(obj, path, defaultValue = null) {
        if (!obj || !path) return defaultValue;
        
        const keys = path.split('.');
        let current = obj;
        
        for (const key of keys) {
            if (current === null || current === undefined || typeof current !== 'object') {
                return defaultValue;
            }
            current = current[key];
        }
        
        return current !== undefined ? current : defaultValue;
    }

    /**
     * Interpolate variables into a string
     * @param {string} text - The text with placeholders
     * @param {Object} variables - The variables to interpolate
     * @returns {string} The interpolated text
     */
    function interpolate(text, variables = {}) {
        if (!text || typeof text !== 'string') return text;
        
        return text.replace(CONFIG.interpolationPattern, (match, key) => {
            return variables.hasOwnProperty(key) ? variables[key] : match;
        });
    }

    /**
     * Get the user's preferred language from storage, cookies, or browser
     * @returns {string} The language code
     */
    function getPreferredLanguage() {
        // Check query param (?lang=fr)
        try {
            const urlLang = new URLSearchParams(window.location.search).get('lang');
            if (urlLang && availableLanguages.some(l => l.code === urlLang)) {
                return urlLang;
            }
        } catch (e) {
            // Ignore URL parsing errors
        }

        // Check localStorage first
        const stored = localStorage.getItem(CONFIG.storageKey);
        if (stored && availableLanguages.some(l => l.code === stored)) {
            return stored;
        }
        
        // Check cookie
        const cookieMatch = document.cookie.match(/language=([^;]+)/);
        if (cookieMatch && availableLanguages.some(l => l.code === cookieMatch[1])) {
            return cookieMatch[1];
        }

        // Check HTML lang attribute
        const docLang = document.documentElement.lang;
        if (docLang && availableLanguages.some(l => l.code === docLang)) {
            return docLang;
        }
        
        // Check browser language
        const browserLang = navigator.language.split('-')[0];
        if (availableLanguages.some(l => l.code === browserLang)) {
            return browserLang;
        }
        
        // Return default
        return CONFIG.defaultLanguage;
    }

    /**
     * Save the language preference
     * @param {string} langCode - The language code to save
     */
    function saveLanguagePreference(langCode) {
        localStorage.setItem(CONFIG.storageKey, langCode);
        
        // Also set as cookie for server-side detection
        const expires = new Date();
        expires.setFullYear(expires.getFullYear() + 1);
        document.cookie = `language=${langCode};expires=${expires.toUTCString()};path=/`;
    }

    // ============================================================================
    // API FUNCTIONS
    // ============================================================================

    /**
     * Fetch available languages from the server
     * @returns {Promise<Array>} Array of language objects
     */
    async function fetchAvailableLanguages() {
        try {
            const response = await fetch(CONFIG.languagesEndpoint);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            return data.languages || [];
        } catch (error) {
            console.error('[i18n] Failed to fetch languages:', error);
            // Return default languages as fallback
            return [
                { code: 'fr', name: 'Français', native_name: 'Français' },
                { code: 'en', name: 'English', native_name: 'English' }
            ];
        }
    }

    /**
     * Fetch translations for a specific language
     * @param {string} langCode - The language code
     * @returns {Promise<Object>} The translations object
     */
    async function fetchTranslations(langCode) {
        try {
            const response = await fetch(`${CONFIG.translationsEndpoint}/${langCode}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            // API returns 'translation' (singular), not 'translations'
            return data.translation || data.translations || {};
        } catch (error) {
            console.error(`[i18n] Failed to fetch translations for ${langCode}:`, error);
            return {};
        }
    }

    /**
     * Set language preference on the server
     * @param {string} langCode - The language code
     * @returns {Promise<boolean>} Success status
     */
    async function setServerLanguage(langCode) {
        try {
            const response = await fetch(CONFIG.languageEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ language: langCode })
            });
            return response.ok;
        } catch (error) {
            console.error('[i18n] Failed to set server language:', error);
            return false;
        }
    }

    // ============================================================================
    // TRANSLATION FUNCTIONS
    // ============================================================================

    /**
     * Get a translated string
     * @param {string} key - The translation key (dot notation)
     * @param {Object} variables - Variables for interpolation
     * @param {string} defaultText - Default text if key not found
     * @returns {string} The translated string
     */
    function t(key, variables = {}, defaultText = null) {
        let text = deepGet(translations, key);

        // Fallback to default language if not found
        if (text === null) {
            text = deepGet(defaultTranslations, key);
        }

        if (text === null) {
            text = defaultText || key;
        }

        return interpolate(text, variables);
    }

    /**
     * Translate all elements in the DOM with data-i18n attributes
     * @param {Element} root - The root element to start from (default: document)
     */
    function translateDOM(root = document) {
        // Translate text content
        const elements = root.querySelectorAll(`[${CONFIG.dataAttribute}]`);
        elements.forEach(el => {
            const key = el.getAttribute(CONFIG.dataAttribute);
            if (key) {
                const translated = t(key);
                if (translated !== key) {
                    el.textContent = translated;
                }
            }
        });

        // Translate placeholders
        const placeholderElements = root.querySelectorAll(`[${CONFIG.dataAttrPlaceholder}]`);
        placeholderElements.forEach(el => {
            const key = el.getAttribute(CONFIG.dataAttrPlaceholder);
            if (key) {
                const translated = t(key);
                if (translated !== key) {
                    el.placeholder = translated;
                }
            }
        });

        // Translate titles (tooltips)
        const titleElements = root.querySelectorAll(`[${CONFIG.dataAttrTitle}]`);
        titleElements.forEach(el => {
            const key = el.getAttribute(CONFIG.dataAttrTitle);
            if (key) {
                const translated = t(key);
                if (translated !== key) {
                    el.title = translated;
                }
            }
        });

        // Translate alt text
        const altElements = root.querySelectorAll(`[${CONFIG.dataAttrAlt}]`);
        altElements.forEach(el => {
            const key = el.getAttribute(CONFIG.dataAttrAlt);
            if (key) {
                const translated = t(key);
                if (translated !== key) {
                    el.alt = translated;
                }
            }
        });
    }

    // ============================================================================
    // LANGUAGE SELECTOR
    // ============================================================================

    /**
     * Create and insert the language selector into the page
     * @param {string} containerId - The ID of the container element
     */
    function createLanguageSelector(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn(`[i18n] Container #${containerId} not found`);
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'language-selector';
        wrapper.innerHTML = `
            <select id="language-select" class="language-select" title="${t('i18n.select_language', {}, 'Select language')}">
                ${availableLanguages.map(lang => `
                    <option value="${lang.code}" ${lang.code === currentLanguage ? 'selected' : ''}>
                        ${lang.flag || ''} ${lang.native_name || lang.name}
                    </option>
                `).join('')}
            </select>
            <button type="button" id="language-btn-ok" class="language-btn-ok" title="${t('i18n.apply_language', {}, 'Apply language')}">${t('common.ok', {}, 'OK')}</button>
        `;

        container.appendChild(wrapper);

        // Add event listener for OK button (not auto-apply on change)
        const okButton = wrapper.querySelector('#language-btn-ok');
        okButton.addEventListener('click', async () => {
            const select = document.getElementById('language-select');
            if (select && select.value !== currentLanguage) {
                okButton.disabled = true;
                okButton.textContent = t('common.loading_short', {}, '...');
                try {
                    await setLanguage(select.value);
                } finally {
                    okButton.disabled = false;
                    okButton.textContent = t('common.ok', {}, 'OK');
                }
            }
        });
    }

    /**
     * Update the language selector to reflect current language
     */
    function updateLanguageSelector() {
        const select = document.getElementById('language-select');
        if (select) {
            select.value = currentLanguage;
        }
    }

    // ============================================================================
    // PUBLIC API
    // ============================================================================

    /**
     * Initialize the i18n module
     * @param {Object} options - Configuration options
     * @returns {Promise<void>}
     */
    async function init(options = {}) {
        if (isInitialized) {
            console.warn('[i18n] Already initialized');
            return;
        }

        console.log('[i18n] Initializing...');

        // Merge options
        Object.assign(CONFIG, options);

        // Fetch available languages
        availableLanguages = await fetchAvailableLanguages();
        console.log('[i18n] Available languages:', availableLanguages.map(l => l.code).join(', '));

        // Get preferred language
        let preferredLang = getPreferredLanguage();
        if (!availableLanguages.some(l => l.code === preferredLang)) {
            preferredLang = CONFIG.defaultLanguage;
        }

        // Load default translations (for fallback)
        defaultTranslations = await fetchTranslations(CONFIG.defaultLanguage);

        // Load translations for preferred language
        translations = preferredLang === CONFIG.defaultLanguage
            ? defaultTranslations
            : await fetchTranslations(preferredLang);

        currentLanguage = preferredLang;

        // If preferred language failed to load, fallback to default
        if (!translations || Object.keys(translations).length === 0) {
            translations = defaultTranslations;
            currentLanguage = CONFIG.defaultLanguage;
        }
        
        // Save preference
        saveLanguagePreference(currentLanguage);

        // Translate the DOM
        translateDOM();

        isInitialized = true;
        console.log(`[i18n] Initialized with language: ${currentLanguage}`);

        // Notify callbacks
        onLanguageChangeCallbacks.forEach(cb => cb(currentLanguage));
    }

    /**
     * Set the current language
     * @param {string} langCode - The language code
     * @returns {Promise<boolean>} Success status
     */
    async function setLanguage(langCode) {
        if (langCode === currentLanguage) return true;

        if (!availableLanguages.some(l => l.code === langCode)) {
            console.error(`[i18n] Language '${langCode}' not available`);
            return false;
        }

        console.log(`[i18n] Switching language to: ${langCode}`);

        // Fetch new translations
        const newTranslations = await fetchTranslations(langCode);
        if (Object.keys(newTranslations).length === 0) {
            console.error(`[i18n] Failed to load translations for ${langCode}`);
            return false;
        }

        // Update state
        translations = newTranslations;
        currentLanguage = langCode;

        // Save preference
        saveLanguagePreference(langCode);

        // Update server
        await setServerLanguage(langCode);

        // Translate the DOM
        translateDOM();

        // Update selector
        updateLanguageSelector();

        // Notify callbacks
        onLanguageChangeCallbacks.forEach(cb => cb(currentLanguage));

        console.log(`[i18n] Language changed to: ${currentLanguage}`);
        return true;
    }

    /**
     * Get the current language code
     * @returns {string} The current language code
     */
    function getLanguage() {
        return currentLanguage;
    }

    /**
     * Get available languages
     * @returns {Array} Array of language objects
     */
    function getLanguages() {
        return [...availableLanguages];
    }

    /**
     * Register a callback for language changes
     * @param {Function} callback - The callback function
     */
    function onLanguageChange(callback) {
        if (typeof callback === 'function') {
            onLanguageChangeCallbacks.push(callback);
        }
    }

    /**
     * Get all translations for the current language
     * @returns {Object} The translations object
     */
    function getTranslations() {
        return { ...translations };
    }

    /**
     * Manually translate a specific element
     * @param {Element} element - The element to translate
     */
    function translateElement(element) {
        if (!element) return;
        translateDOM(element.parentElement || element);
    }

    /**
     * Format a number according to current locale
     * @param {number} value - The number to format
     * @param {Object} options - Intl.NumberFormat options
     * @returns {string} The formatted number
     */
    function formatNumber(value, options = {}) {
        try {
            return new Intl.NumberFormat(currentLanguage, options).format(value);
        } catch (e) {
            return String(value);
        }
    }

    /**
     * Format a date according to current locale
     * @param {Date|string|number} date - The date to format
     * @param {Object} options - Intl.DateTimeFormat options
     * @returns {string} The formatted date
     */
    function formatDate(date, options = { dateStyle: 'medium', timeStyle: 'short' }) {
        try {
            const d = date instanceof Date ? date : new Date(date);
            return new Intl.DateTimeFormat(currentLanguage, options).format(d);
        } catch (e) {
            return String(date);
        }
    }

    /**
     * Format a file size with appropriate units
     * @param {number} bytes - The size in bytes
     * @returns {string} The formatted size
     */
    function formatSize(bytes) {
        const units = currentLanguage === 'fr' 
            ? ['o', 'Ko', 'Mo', 'Go', 'To']
            : ['B', 'KB', 'MB', 'GB', 'TB'];
        
        let unitIndex = 0;
        let size = bytes;
        
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        
        return `${formatNumber(size, { maximumFractionDigits: 1 })} ${units[unitIndex]}`;
    }

    /**
     * Format a duration in seconds to human readable string
     * @param {number} seconds - The duration in seconds
     * @returns {string} The formatted duration
     */
    function formatDuration(seconds) {
        if (seconds < 60) {
            return t('common.seconds', { value: seconds }, `${seconds}s`);
        }
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        const parts = [];
        if (hours > 0) parts.push(`${hours}h`);
        if (minutes > 0) parts.push(`${minutes}m`);
        if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
        
        return parts.join(' ');
    }

    // ============================================================================
    // EXPOSE PUBLIC API
    // ============================================================================

    return {
        // Initialization
        init,
        
        // Translation
        t,
        translateDOM,
        translateElement,
        
        // Language management
        setLanguage,
        getLanguage,
        getLanguages,
        onLanguageChange,
        getTranslations,
        
        // UI components
        createLanguageSelector,
        
        // Formatting utilities
        formatNumber,
        formatDate,
        formatSize,
        formatDuration,
        
        // Configuration access
        get isInitialized() { return isInitialized; },
        get currentLanguage() { return currentLanguage; }
    };
})();

// Export for ES modules if supported
if (typeof module !== 'undefined' && module.exports) {
    module.exports = I18n;
}

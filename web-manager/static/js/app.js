/**
 * RTSP Recorder Web Manager - Frontend JavaScript
 * Version: 2.36.00
 */

let backupFileAction = null;
let backupSelectedFile = null;


// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize i18n first (translations must be loaded before other UI)
    try {
        await I18n.init();
        I18n.createLanguageSelector('language-selector-container');
        console.log('[app] i18n initialized with language:', I18n.getLanguage());
    } catch (e) {
        console.error('[app] i18n init failed:', e);
    }
    
    initTabs();
    initForm();
    updateStatus();
    loadNetworkInterfaces();
    loadWifiConfig();  // Load WiFi config (simple or failover based on adapter count)
    loadEthernetWifiStatus();
    loadApStatus();
    checkPreviewStatus();
    loadOnvifStatus();
    loadPowerStatus();  // Load energy management status
    loadHomeStatus();   // Load home page status
    loadMeetingStatus(); // Load Meeting status
    loadResolutions();  // Auto-load camera resolutions
    initRtspAuthStatus(); // Initialize RTSP auth status display
    loadCameraProfiles(); // Load camera profiles for scheduler
    
    // Check URL for initial tab navigation
    const urlTab = getTabFromUrl();
    if (urlTab) {
        // Small delay to ensure DOM is ready
        setTimeout(() => switchToTab(urlTab), 100);
    }
    
    // Listen for hash changes (back/forward browser navigation)
    window.addEventListener('hashchange', () => {
        const hashTab = getTabFromUrl();
        if (hashTab) {
            switchToTab(hashTab, false); // Don't update URL again
        }
    });
    
    // Auto-refresh status every 10 seconds
    setInterval(updateStatus, 10000);
    // Auto-refresh home status every 30 seconds
    setInterval(loadHomeStatus, 30000);
});



/**
 * Initialize form submission
 */

// ============================================================================
// I18N MANAGEMENT FUNCTIONS
// ============================================================================

/**
 * Change language from the advanced settings page
 */
function changeLanguageFromAdvanced(langCode) {
    I18n.setLanguage(langCode);
    updateAdvancedLanguageDisplay();
}

/**
 * Update the language display in advanced settings
 */
function updateAdvancedLanguageDisplay() {
    const langSelect = document.getElementById('advanced-language-select');
    const langDisplay = document.getElementById('current-lang-display');
    
    if (langSelect && I18n.isInitialized) {
        const languages = I18n.getLanguages();
        langSelect.innerHTML = languages.map(lang => 
            `<option value="${lang.code}" ${lang.code === I18n.getLanguage() ? 'selected' : ''}>
                ${lang.native_name || lang.name}
            </option>`
        ).join('');
    }
    
    if (langDisplay && I18n.isInitialized) {
        const currentLang = I18n.getLanguages().find(l => l.code === I18n.getLanguage());
        if (currentLang) {
            langDisplay.textContent = currentLang.native_name || currentLang.name;
        }
    }
}

/**
 * Handle translation file upload
 */
async function handleTranslationUpload(input) {
    const file = input.files[0];
    if (!file) return;
    
    if (!file.name.endsWith('.json')) {
        showToast(I18n.t('i18n.invalid_file', {}, 'Fichier invalide. Utilisez un fichier JSON.'), 'error');
        return;
    }
    
    try {
        const text = await file.text();
        const json = JSON.parse(text);
        
        // Validate the translation file
        const validateResponse = await fetch('/api/i18n/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ translations: json })
        });
        
        const validateResult = await validateResponse.json();
        
        if (!validateResult.valid) {
            showToast(I18n.t('i18n.validation_failed', { errors: validateResult.errors.length }, 
                `Validation échouée: ${validateResult.errors.length} erreurs`), 'error');
            console.error('Translation validation errors:', validateResult.errors);
            return;
        }
        
        // Extract language code from _meta or filename
        const langCode = json._meta?.code || file.name.replace('.json', '').split('_').pop();
        
        if (!langCode || langCode.length < 2) {
            showToast(I18n.t('i18n.no_lang_code', {}, 'Code langue introuvable dans le fichier'), 'error');
            return;
        }
        
        // Upload the translation
        const uploadResponse = await fetch(`/api/i18n/translations/${langCode}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ translations: json })
        });
        
        if (uploadResponse.ok) {
            showToast(I18n.t('i18n.upload_success', { lang: langCode }, 
                `Traduction ${langCode} chargée avec succès`), 'success');
            loadCustomTranslationsList();
            
            // Offer to switch to the new language
            if (confirm(I18n.t('i18n.switch_to_new', { lang: langCode }, 
                `Voulez-vous utiliser la langue "${langCode}" maintenant?`))) {
                I18n.setLanguage(langCode);
            }
        } else {
            const error = await uploadResponse.json();
            showToast(I18n.t('i18n.upload_failed', {}, `Erreur: ${error.error}`), 'error');
        }
    } catch (e) {
        console.error('Translation upload error:', e);
        showToast(I18n.t('i18n.parse_error', {}, 'Erreur de lecture du fichier JSON'), 'error');
    }
    
    // Reset the input
    input.value = '';
}

/**
 * Download the translation template
 */
async function downloadTranslationTemplate() {
    try {
        const response = await fetch('/api/i18n/template');
        if (!response.ok) throw new Error('Failed to fetch template');
        
        const template = await response.json();
        const blob = new Blob([JSON.stringify(template.template, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = 'translation_template.json';
        a.click();
        
        URL.revokeObjectURL(url);
        showToast(I18n.t('i18n.template_downloaded', {}, 'Modèle téléchargé'), 'success');
    } catch (e) {
        console.error('Template download error:', e);
        showToast(I18n.t('i18n.template_error', {}, 'Erreur lors du téléchargement'), 'error');
    }
}

/**
 * Download current translation
 */
async function downloadCurrentTranslation() {
    try {
        const langCode = I18n.getLanguage();
        const response = await fetch(`/api/i18n/translations/${langCode}`);
        if (!response.ok) throw new Error('Failed to fetch translation');
        
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data.translations, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `translation_${langCode}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
        showToast(I18n.t('i18n.export_success', {}, 'Traduction exportée'), 'success');
    } catch (e) {
        console.error('Export error:', e);
        showToast(I18n.t('i18n.export_error', {}, 'Erreur lors de l\'export'), 'error');
    }
}

/**
 * Load the list of custom translations
 */
async function loadCustomTranslationsList() {
    try {
        const response = await fetch('/api/i18n/languages');
        if (!response.ok) return;
        
        const data = await response.json();
        const customLangs = data.languages.filter(l => l.is_custom);
        
        const container = document.getElementById('custom-translations-container');
        const wrapper = document.getElementById('custom-translations-list');
        
        if (!container || !wrapper) return;
        
        if (customLangs.length === 0) {
            wrapper.style.display = 'none';
            return;
        }
        
        wrapper.style.display = 'block';
        container.innerHTML = customLangs.map(lang => `
            <div class="custom-translation-item">
                <span class="lang-name">${lang.native_name || lang.name} (${lang.code})</span>
                <div class="lang-actions">
                    <button type="button" class="btn btn-sm btn-secondary" onclick="I18n.setLanguage('${lang.code}')">
                        <i class="fas fa-check"></i>
                    </button>
                    <button type="button" class="btn btn-sm btn-danger" onclick="deleteCustomTranslation('${lang.code}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Load custom translations error:', e);
    }
}

/**
 * Delete a custom translation
 */
async function deleteCustomTranslation(langCode) {
    if (!confirm(I18n.t('i18n.confirm_delete', { lang: langCode }, 
        `Supprimer la traduction "${langCode}"?`))) {
        return;
    }
    
    try {
        const response = await fetch(`/api/i18n/translations/${langCode}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showToast(I18n.t('i18n.delete_success', {}, 'Traduction supprimée'), 'success');
            loadCustomTranslationsList();
            
            // If we deleted the current language, switch back to default
            if (I18n.getLanguage() === langCode) {
                I18n.setLanguage('fr');
            }
        } else {
            const error = await response.json();
            showToast(error.error || 'Erreur', 'error');
        }
    } catch (e) {
        console.error('Delete translation error:', e);
        showToast(I18n.t('i18n.delete_error', {}, 'Erreur lors de la suppression'), 'error');
    }
}

// Initialize i18n-related UI when the tab is shown
document.addEventListener('DOMContentLoaded', () => {
    // Update advanced language settings when switching to advanced tab
    const advancedTab = document.querySelector('[data-tab="advanced"]');
    if (advancedTab) {
        advancedTab.addEventListener('click', () => {
            updateAdvancedLanguageDisplay();
            loadCustomTranslationsList();
        });
    }
    
    // Register for language changes to update UI
    if (typeof I18n !== 'undefined') {
        I18n.onLanguageChange((langCode) => {
            updateAdvancedLanguageDisplay();
            // Update document lang attribute
            document.documentElement.lang = langCode;
        });
    }
});

// ============================================================================
// UI UTILITY FUNCTIONS
// ============================================================================

/**
 * Toggle a collapsible section (generic function)
 * @param {string} sectionId - The ID of the section element with class 'collapsible'
 */
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) {
        console.warn('[app] toggleSection: section not found:', sectionId);
        return;
    }
    section.classList.toggle('collapsed');
    
    // Update the icon rotation
    const icon = section.querySelector('.collapse-icon');
    if (icon) {
        // Icon rotation is handled by CSS via .collapsed class
    }
}

/**
 * Apply resolution settings (save to config)
 * Uses VIDEOIN_* for camera input parameters
 */
async function applyResolution() {
    const resolutionSelect = document.getElementById('resolution-select');
    const fpsInput = document.getElementById('VIDEOIN_FPS') || document.getElementById('VIDEO_FPS');
    const manualWidth = document.getElementById('manual-video-width');
    const manualHeight = document.getElementById('manual-video-height');
    const manualFormat = document.getElementById('manual-video-format');
    const manualEnabled = document.getElementById('manual-resolution-toggle');
    
    let width, height, fps, format;
    
    if (manualEnabled && manualEnabled.checked) {
        // Manual mode
        width = manualWidth ? manualWidth.value : '';
        height = manualHeight ? manualHeight.value : '';
        format = manualFormat ? manualFormat.value : 'MJPEG';
    } else {
        // Auto mode - parse from select
        if (resolutionSelect && resolutionSelect.value) {
            const parts = resolutionSelect.value.split('-');
            if (parts.length >= 2) {
                const dims = parts[0].split('x');
                width = dims[0];
                height = dims[1];
                format = parts[1] || 'MJPG';
            }
        }
    }
    
    // Get FPS from input field (set by onResolutionSelectChange or user)
    fps = fpsInput ? fpsInput.value : '30';
    
    if (!width || !height) {
        showToast(I18n ? I18n.t('video.resolution_invalid', {}, 'Résolution invalide') : 'Résolution invalide', 'error');
        return;
    }
    
    // Build config object - use VIDEOIN_* for camera input parameters
    const configData = {
        VIDEOIN_WIDTH: width,
        VIDEOIN_HEIGHT: height,
        VIDEOIN_FPS: fps,
        VIDEOIN_FORMAT: format
    };
    
    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configData)
        });
        
        if (response.ok) {
            showToast(I18n ? I18n.t('video.resolution_applied', {}, 'Résolution appliquée') : 'Résolution appliquée', 'success');
        } else {
            const error = await response.json();
            showToast(error.error || 'Erreur', 'error');
        }
    } catch (e) {
        console.error('[app] applyResolution error:', e);
        showToast(I18n ? I18n.t('common.error', {}, 'Erreur') : 'Erreur', 'error');
    }
}

// ============================================================================











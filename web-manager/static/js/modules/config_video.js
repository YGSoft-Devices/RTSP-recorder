/**
 * RTSP Recorder Web Manager - Config/Audio/Video helpers
 * Version: 2.36.11
 */

(function () {
const ALLOWED_VIDEO_FORMATS = ['AUTO', 'MJPG', 'YUYV', 'H264'];
let currentCameraType = 'usb';
function initForm() {
    const form = document.getElementById('config-form');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveConfig();
    });

    const overlayMode = document.getElementById('CSI_OVERLAY_MODE');
    const overlayDatetime = document.getElementById('VIDEO_OVERLAY_SHOW_DATETIME');
    if (overlayMode) {
        overlayMode.addEventListener('change', updateCsiOverlayWarning);
    }
    if (overlayDatetime) {
        overlayDatetime.addEventListener('change', updateCsiOverlayWarning);
    }
    updateCsiOverlayWarning();
}

function updateCsiOverlayWarning() {
    const warning = document.getElementById('csi-overlay-warning');
    const overlayMode = document.getElementById('CSI_OVERLAY_MODE');
    const overlayDatetime = document.getElementById('VIDEO_OVERLAY_SHOW_DATETIME');
    if (!warning || !overlayMode || !overlayDatetime) {
        return;
    }
    const showWarning = overlayMode.value === 'libcamera' && overlayDatetime.value === 'yes';
    warning.style.display = showWarning ? 'block' : 'none';
}


/**
 * Save configuration
 */
async function saveConfig() {
    try {
        const form = document.getElementById('config-form');
        const formData = new FormData(form);
        const config = {};
        
        formData.forEach((value, key) => {
            config[key] = value;
        });

        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration sauvegardée !', 'success');
            
            // Update RTSP URL display
            const rtspUrl = document.getElementById('rtsp-url');
            if (rtspUrl) {
                const port = config.RTSP_PORT || '8554';
                const path = config.RTSP_PATH || 'stream';
                const currentUrl = rtspUrl.textContent;
                const match = currentUrl.match(/rtsp:\/\/([^:]+):/);
                if (match) {
                    rtspUrl.textContent = `rtsp://${match[1]}:${port}/${path}`;
                }
            }
        } else {
            const errors = Array.isArray(data.errors) ? data.errors.join(', ') : '';
            const message = data.message || data.error || errors || 'Échec de la sauvegarde';
            showToast(`Erreur: ${message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply audio configuration and restart RTSP service
 */
async function applyAudioConfig() {
    try {
        const audioEnable = document.querySelector('input[name="AUDIO_ENABLE"]:checked');
        const config = {
            AUDIO_ENABLE: audioEnable ? audioEnable.value : 'auto',
            AUDIO_DEVICE: document.getElementById('AUDIO_DEVICE')?.value || 'auto',
            AUDIO_RATE: document.getElementById('AUDIO_RATE')?.value || '48000',
            AUDIO_CHANNELS: document.getElementById('AUDIO_CHANNELS')?.value || '1',
            AUDIO_BITRATE_KBPS: document.getElementById('AUDIO_BITRATE_KBPS')?.value || '64',
            AUDIO_GAIN: document.getElementById('AUDIO_GAIN')?.value || '1.0'
        };

        showToast('Application des parametres audio...', 'info');

        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (!data.success) {
            const errors = Array.isArray(data.errors) ? data.errors.join(', ') : '';
            const message = data.message || data.error || errors || 'Échec de la sauvegarde';
            showToast(`Erreur: ${message}`, 'error');
            return;
        }

        showToast('Parametres audio sauvegardes, redemarrage RTSP...', 'success');
        await controlServiceAction('restart', 'rpi-av-rtsp-recorder');
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Reset form to last saved values
 */
async function resetForm() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        if (data.success) {
            Object.entries(data.config).forEach(([key, value]) => {
                const input = document.getElementById(key);
                if (input) {
                    input.value = value;
                }
            });
            showToast('Formulaire réinitialisé', 'info');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Detect available cameras
 */
async function detectCameras() {
    try {
        showToast('Détection des caméras...', 'info');
        
        const response = await fetch('/api/detect/cameras');
        const data = await response.json();
        
        const listContainer = document.getElementById('camera-list');
        
        if (data.success && data.cameras.length > 0) {
            listContainer.innerHTML = data.cameras.map(cam => `
                <div class="detection-item" onclick="selectCamera('${cam.device}', '${cam.type || 'usb'}')">
                    <span class="device-name">${cam.name || cam.type}</span>
                    <span class="device-path">${cam.device}</span>
                </div>
            `).join('');
            showToast(`${data.cameras.length} caméra(s) détectée(s)`, 'success');
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucune caméra détectée</span></div>';
            showToast('Aucune caméra détectée', 'warning');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Select camera device
 */
function selectCamera(device, type) {
    if (device !== 'CSI') {
        document.getElementById('VIDEOIN_DEVICE').value = device;
    }
    // Auto-set camera type if provided
    if (type) {
        const cameraTypeSelect = document.getElementById('CAMERA_TYPE');
        if (cameraTypeSelect) {
            cameraTypeSelect.value = type;
            onCameraTypeChange();
        }
    }
    document.getElementById('camera-list').innerHTML = '';
    showToast(`Caméra sélectionnée: ${device}`, 'success');
}

/**
 * Handle camera type change (USB/CSI selector)
 */
function onCameraTypeChange() {
    // Get value from checked radio button
    const cameraType = document.querySelector('input[name="CAMERA_TYPE"]:checked')?.value || 'usb';
    const csiNotice = document.getElementById('csi-controls-notice');
    const advancedSection = document.getElementById('advanced-camera-section');
    
    // Show/hide CSI notice
    if (csiNotice) {
        csiNotice.style.display = (cameraType === 'csi') ? 'flex' : 'none';
    }
    
    // Show toast for required restart
    showToast(`Mode ${cameraType.toUpperCase()} activé. Redémarrage requis.`, 'info');
    
    // Auto-save the config change
    updateConfigField('CAMERA_TYPE', cameraType);

    // Refresh resolutions when camera type changes
    loadResolutions();
    
    // Reload advanced controls (they will show error for CSI)
    if (advancedSection && advancedSection.style.display !== 'none') {
        loadAdvancedCameraControls();
    }
}

// Helper for single field update
function updateConfigField(key, value) {
    const data = {};
    data[key] = value;
    fetch('/api/config', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    }).catch(console.error);
}

/**
 * Detect available audio devices
 */
async function detectAudio() {
    try {
        showToast('Détection des périphériques audio...', 'info');
        
        const response = await fetch('/api/detect/audio');
        const data = await response.json();
        
        const listContainer = document.getElementById('audio-list');
        
        if (data.success && data.devices.length > 0) {
            listContainer.innerHTML = data.devices.map(dev => `
                <div class="detection-item" onclick="selectAudio('${dev.device}')">
                    <span class="device-name">${dev.name}</span>
                    <span class="device-path">${dev.device}</span>
                </div>
            `).join('');
            showToast(`${data.devices.length} périphérique(s) audio détecté(s)`, 'success');
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucun périphérique audio détecté</span></div>';
            showToast('Aucun périphérique audio détecté', 'warning');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Select audio device
 */
function selectAudio(device) {
    document.getElementById('AUDIO_DEVICE').value = device;
    document.getElementById('audio-list').innerHTML = '';
    showToast(`Périphérique audio sélectionné: ${device}`, 'success');
}

/**
 * Update audio gain display value
 */
function updateAudioGainDisplay(value) {
    const display = document.getElementById('AUDIO_GAIN_VALUE');
    if (display) {
        display.textContent = parseFloat(value).toFixed(1) + 'x';
        // Color feedback: green = normal, yellow = amplified, red = high
        if (value <= 1.0) {
            display.style.color = 'var(--primary-light)';
        } else if (value <= 2.0) {
            display.style.color = 'var(--warning-color)';
        } else {
            display.style.color = 'var(--danger-color)';
        }
    }
}

// Global storage for detected resolutions
let detectedResolutions = [];

function getEncoderLabel(format, width, height, cameraType, encoderCaps) {
    const formatUpper = (format || '').toUpperCase();
    if (cameraType === 'libcamera') {
        return 'hardware (Picamera2)';
    }
    if (formatUpper === 'H264') {
        return 'direct (H264)';
    }
    if (encoderCaps && encoderCaps.available) {
        const maxWidth = parseInt(encoderCaps.max_width) || 0;
        const maxHeight = parseInt(encoderCaps.max_height) || 0;
        if (maxWidth > 0 && maxHeight > 0) {
            return (width <= maxWidth && height <= maxHeight) ? 'hardware' : 'software';
        }
        return 'hardware';
    }
    return 'software';
}

/**
 * Load resolutions automatically into dropdown
 */
async function loadResolutions() {
    const select = document.getElementById('resolution-select');
    const loadingIndicator = document.getElementById('resolution-loading');
    
    if (!select) return;
    
    try {
        // Show loading state
        if (loadingIndicator) loadingIndicator.style.display = 'inline';
        select.innerHTML = '<option value="">⏳ Détection en cours...</option>';
        select.disabled = true;
        
        const device = document.getElementById('VIDEOIN_DEVICE')?.value || '/dev/video0';
        const response = await fetch(`/api/camera/formats?device=${encodeURIComponent(device)}`);
        const data = await response.json();
        
        if (data.success && data.formats.length > 0) {
            detectedResolutions = [];
            let options = '<option value="">-- Sélectionnez une résolution --</option>';
            const cameraType = data.camera_type?.type || 'usb';
            currentCameraType = cameraType;
            const encoderCaps = data.encoder || {};
            
            // Get current values to pre-select
            const currentWidth = parseInt(document.getElementById('VIDEOIN_WIDTH')?.value) || 0;
            const currentHeight = parseInt(document.getElementById('VIDEOIN_HEIGHT')?.value) || 0;
            const currentFormat = (document.getElementById('VIDEOIN_FORMAT')?.value || '').toUpperCase();
            let selectedKey = '';
            let fallbackKey = '';
            
            for (const fmt of data.formats) {
                // Add optgroup for each format
                options += `<optgroup label="${fmt.format}">`;
                
                for (const res of fmt.resolutions) {
                    const fps = res.framerates.length > 0 ? Math.floor(res.framerates[0]) : 30;
                    const allFps = res.framerates.map(f => Math.floor(f)).join(', ');
                    const megapixels = ((res.width * res.height) / 1000000).toFixed(1);
                    
                    // Use composite key: WIDTHxHEIGHT-FORMAT (unique identifier)
                    const resKey = `${res.width}x${res.height}-${fmt.format}`;
                    const encoderLabel = getEncoderLabel(fmt.format, res.width, res.height, cameraType, encoderCaps);
                    detectedResolutions.push({
                        key: resKey,
                        format: fmt.format,
                        width: res.width,
                        height: res.height,
                        fps: fps,
                        framerates: res.framerates.map(f => Math.floor(f)),
                        megapixels: megapixels,
                        encoder: encoderLabel
                    });
                    
                    const matchesSize = (res.width === currentWidth && res.height === currentHeight);
                    const formatUpper = (fmt.format || '').toUpperCase();
                    if (matchesSize) {
                        if (currentFormat && formatUpper === currentFormat) {
                            selectedKey = resKey;  // Exact match: size + format
                        } else if (!fallbackKey) {
                            fallbackKey = resKey;  // Fallback: only size matches
                        }
                    }
                    
                    options += `<option value="${resKey}">`;
                    options += `${res.width}×${res.height} @ ${fps}fps (${megapixels}MP) - ${encoderLabel}`;
                    options += `</option>`;
                }
                
                options += '</optgroup>';
            }
            
            select.innerHTML = options;
            select.disabled = false;
            if (selectedKey !== '') {
                select.value = selectedKey;
            } else if (fallbackKey !== '') {
                select.value = fallbackKey;
            }
            
            // Trigger change to show details if something is selected
            if (select.value) {
                onResolutionSelectChange();
            }
            
            // Populate manual format dropdown with detected formats (v2.36.10)
            populateManualFormatDropdown(data.formats, cameraType);
            
            console.log(`Loaded ${detectedResolutions.length} resolutions`);
        } else {
            select.innerHTML = '<option value="">❌ Aucune résolution détectée</option>';
            select.disabled = true;
            // Still try to populate formats with empty list
            populateManualFormatDropdown([], 'unknown');
        }
    } catch (error) {
        console.error('Error loading resolutions:', error);
        select.innerHTML = '<option value="">❌ Erreur de détection</option>';
        select.disabled = true;
        populateManualFormatDropdown([], 'unknown');
    } finally {
        if (loadingIndicator) loadingIndicator.style.display = 'none';
    }
}

/**
 * Handle resolution dropdown change
 */
function onResolutionSelectChange(userTriggered = false) {
    const select = document.getElementById('resolution-select');
    const detailsDiv = document.getElementById('resolution-details');
    const manualMode = document.getElementById('manual-resolution-mode')?.checked;
    
    if (!select || !select.value || manualMode) {
        if (detailsDiv) detailsDiv.style.display = 'none';
        return;
    }
    
    // Find resolution by key (WIDTHxHEIGHT-FORMAT)
    const resKey = select.value;
    const res = detectedResolutions.find(r => r.key === resKey);
    
    if (!res) {
        console.warn('[config_video] Resolution not found for key:', resKey);
        return;
    }
    
    // Update hidden/manual fields with selected values
    const widthInput = document.getElementById('VIDEOIN_WIDTH');
    const heightInput = document.getElementById('VIDEOIN_HEIGHT');
    const formatInput = document.getElementById('VIDEOIN_FORMAT');
    const fpsInput = document.getElementById('VIDEOIN_FPS');
    
    if (widthInput) widthInput.value = res.width;
    if (heightInput) heightInput.value = res.height;
    
    let formatValue = res.format || 'auto';
    if (currentCameraType === 'libcamera' || currentCameraType === 'csi') {
        formatValue = 'auto';
    }
    if (!ALLOWED_VIDEO_FORMATS.includes(String(formatValue).toUpperCase())) {
        formatValue = 'auto';
    }
    if (formatInput) formatInput.value = formatValue;
    
    // Only set FPS if user manually changed resolution (not on page load)
    // This preserves user's custom FPS value when page loads
    const currentFps = fpsInput ? (parseInt(fpsInput.value) || 0) : 0;
    if (fpsInput) {
        if (userTriggered || currentFps <= 0) {
            // User changed resolution or FPS is invalid -> set to max FPS
            fpsInput.value = res.fps;
        } else if (currentFps > res.fps) {
            // Current FPS exceeds resolution's max -> cap it
            fpsInput.value = res.fps;
            console.log(`VIDEO_FPS capped from ${currentFps} to ${res.fps} (resolution max)`);
        }
    }
    // Otherwise keep user's configured FPS value
    
    // Show details panel
    if (detailsDiv) {
        document.getElementById('detail-format').textContent = res.format;
        document.getElementById('detail-resolution').textContent = `${res.width} × ${res.height}`;
        document.getElementById('detail-megapixels').textContent = `${res.megapixels} MP`;
        document.getElementById('detail-fps').textContent = res.framerates.join(', ') + ' fps';
        detailsDiv.style.display = 'block';
    }
}

/**
 * Toggle manual resolution mode
 */
function toggleManualResolution() {
    const manualMode = document.getElementById('manual-resolution-mode')?.checked;
    const manualFields = document.getElementById('manual-resolution-fields');
    const selectContainer = document.querySelector('.resolution-selector .form-group');
    const detailsDiv = document.getElementById('resolution-details');
    
    if (manualMode) {
        // Show manual fields, hide dropdown details
        if (manualFields) manualFields.style.display = 'block';
        if (detailsDiv) detailsDiv.style.display = 'none';
        if (selectContainer) selectContainer.style.opacity = '0.5';
        document.getElementById('resolution-select').disabled = true;
        const formatInput = document.getElementById('VIDEOIN_FORMAT');
        if (formatInput) formatInput.value = 'auto';
    } else {
        // Hide manual fields, enable dropdown
        if (manualFields) manualFields.style.display = 'none';
        if (selectContainer) selectContainer.style.opacity = '1';
        document.getElementById('resolution-select').disabled = false;
        // Re-apply selected resolution
        onResolutionSelectChange();
    }
}

/**
 * Helper: Save config then restart RTSP service
 */
async function saveConfigAndRestartRtsp(config, description) {
    try {
        showToast(`Application: ${description}...`, 'info');
        
        // Save config
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Paramètres sauvegardés! Redémarrage du service...', 'success');
            
            // Restart RTSP service to apply changes
            try {
                const restartResponse = await fetch('/api/service/rpi-av-rtsp-recorder/restart', {
                    method: 'POST'
                });
                const restartData = await restartResponse.json();
                if (restartData.success) {
                    showToast('Service RTSP redémarré avec succès', 'success');
                    return true;
                } else {
                    showToast('Config sauvée mais redémarrage échoué: ' + restartData.error, 'warning');
                    return false;
                }
            } catch (e) {
                showToast('Config sauvée, redémarrage manuel requis', 'warning');
                return false;
            }
        } else {
            const errors = Array.isArray(data.errors) ? data.errors.join(', ') : '';
            const message = data.error || data.message || errors || 'Échec de la sauvegarde';
            showToast('Erreur: ' + message, 'error');
            return false;
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
        return false;
    }
}

/**
 * Apply RTSP server configuration (port, path, protocols)
 */
async function applyRtspServerConfig() {
    const config = {
        RTSP_PORT: document.getElementById('RTSP_PORT')?.value || '8554',
        RTSP_PATH: document.getElementById('RTSP_PATH')?.value || 'stream',
        RTSP_PROTOCOLS: document.getElementById('RTSP_PROTOCOLS')?.value || 'udp,tcp'
    };
    await saveConfigAndRestartRtsp(config, 'Configuration serveur RTSP');
}

/**
 * Apply RTSP authentication configuration (user, password)
 */
async function applyRtspAuthConfig() {
    const config = {
        RTSP_USER: document.getElementById('RTSP_USER')?.value || '',
        RTSP_PASSWORD: document.getElementById('RTSP_PASSWORD')?.value || ''
    };
    await saveConfigAndRestartRtsp(config, 'Authentification RTSP');
}

/**
 * Quality level presets (like Synology Surveillance Station)
 * Maps quality 1-5 to bitrate/resolution combinations
 */
const QUALITY_PRESETS = {
    '1': { bitrate: 400,  description: 'Très basse qualité - Économie de bande passante maximale (~400 kbps)' },
    '2': { bitrate: 700,  description: 'Basse qualité - Pour connexions limitées (~700 kbps)' },
    '3': { bitrate: 1200, description: 'Qualité moyenne - Équilibre qualité/bande passante (~1200 kbps)' },
    '4': { bitrate: 2000, description: 'Haute qualité - Bonne qualité d\'image (~2000 kbps)' },
    '5': { bitrate: 3500, description: 'Très haute qualité - Qualité maximale (~3500 kbps, peut chauffer le Pi)' },
    'custom': { bitrate: null, description: 'Personnalisé - Configurez manuellement les paramètres ci-dessous' }
};

/**
 * Handle quality level change
 */
function onQualityLevelChange() {
    const qualitySelect = document.getElementById('STREAM_QUALITY');
    const level = qualitySelect?.value || '3';
    const preset = QUALITY_PRESETS[level];
    
    const infoDiv = document.getElementById('quality-level-info');
    const descSpan = document.getElementById('quality-level-description');
    
    // Show quality description
    if (preset && descSpan) {
        descSpan.textContent = preset.description;
        if (infoDiv) infoDiv.style.display = 'block';
    }
    
    // If not custom, auto-fill bitrate (resolution stays as configured by user)
    if (level !== 'custom' && preset.bitrate !== null) {
        const bitrateInput = document.getElementById('H264_BITRATE_KBPS');
        if (bitrateInput) {
            bitrateInput.value = preset.bitrate;
        }
        // Disable manual bitrate editing when using presets
        if (bitrateInput) bitrateInput.disabled = true;
    } else {
        // Custom mode - enable manual editing
        const bitrateInput = document.getElementById('H264_BITRATE_KBPS');
        if (bitrateInput) bitrateInput.disabled = false;
    }
}

/**
 * Apply video output configuration (resolution, fps, bitrate, quality)
 */
async function applyVideoOutputConfig() {
    const config = {
        STREAM_QUALITY: document.getElementById('STREAM_QUALITY')?.value || '3',
        VIDEOOUT_WIDTH: document.getElementById('VIDEOOUT_WIDTH')?.value || '',
        VIDEOOUT_HEIGHT: document.getElementById('VIDEOOUT_HEIGHT')?.value || '',
        VIDEOOUT_FPS: document.getElementById('VIDEOOUT_FPS')?.value || '',
        H264_BITRATE_MODE: document.getElementById('H264_BITRATE_MODE')?.value || 'cbr',
        H264_BITRATE_KBPS: document.getElementById('H264_BITRATE_KBPS')?.value || '1200'
    };
    await saveConfigAndRestartRtsp(config, 'Paramètres vidéo de sortie');
}

/**
 * Toggle bitrate mode (CBR/VBR) UI
 */
function toggleBitrateMode() {
    const mode = document.getElementById('H264_BITRATE_MODE')?.value || 'cbr';
    const infoDiv = document.getElementById('bitrate-vbr-info');
    const bitrateGroup = document.getElementById('bitrate-manual-group');
    const bitrateLabel = bitrateGroup?.querySelector('label');
    const bitrateHelp = bitrateGroup?.querySelector('small');
    
    if (mode === 'vbr') {
        if (infoDiv) infoDiv.style.display = 'block';
        if (bitrateLabel) bitrateLabel.innerHTML = '<i class="fas fa-signal"></i> Débit max (kbps)';
        if (bitrateHelp) bitrateHelp.textContent = 'Débit maximum en mode VBR';
    } else {
        if (infoDiv) infoDiv.style.display = 'none';
        if (bitrateLabel) bitrateLabel.innerHTML = '<i class="fas fa-signal"></i> Débit H264 (kbps)';
        if (bitrateHelp) bitrateHelp.textContent = 'Débit cible (défaut: 1200 pour Pi 3B+)';
    }
}

/**
 * Apply advanced video configuration (source mode, proxy, encoding)
 */
async function applyVideoAdvancedConfig() {
    const config = {
        STREAM_SOURCE_MODE: document.getElementById('STREAM_SOURCE_MODE')?.value || 'camera',
        STREAM_SOURCE_URL: document.getElementById('STREAM_SOURCE_URL')?.value || '',
        RTSP_PROXY_TRANSPORT: document.getElementById('RTSP_PROXY_TRANSPORT')?.value || 'auto',
        RTSP_PROXY_AUDIO: document.getElementById('RTSP_PROXY_AUDIO')?.value || 'auto',
        RTSP_PROXY_LATENCY_MS: document.getElementById('RTSP_PROXY_LATENCY_MS')?.value || '100',
        SCREEN_DISPLAY: document.getElementById('SCREEN_DISPLAY')?.value || ':0.0',
        H264_KEYINT: document.getElementById('H264_KEYINT')?.value || '30',
        H264_PROFILE: document.getElementById('H264_PROFILE')?.value || '',
        H264_QP: document.getElementById('H264_QP')?.value || ''
    };
    await saveConfigAndRestartRtsp(config, 'Paramètres vidéo avancés');
}

/**
 * Apply overlay configuration
 */
async function applyOverlayConfig() {
    const config = {
        VIDEO_OVERLAY_ENABLE: document.getElementById('VIDEO_OVERLAY_ENABLE')?.value || 'no',
        VIDEO_OVERLAY_TEXT: document.getElementById('VIDEO_OVERLAY_TEXT')?.value || '',
        VIDEO_OVERLAY_POSITION: document.getElementById('VIDEO_OVERLAY_POSITION')?.value || 'top-left',
        VIDEO_OVERLAY_SHOW_DATETIME: document.getElementById('VIDEO_OVERLAY_SHOW_DATETIME')?.value || 'no',
        VIDEO_OVERLAY_DATETIME_FORMAT: document.getElementById('VIDEO_OVERLAY_DATETIME_FORMAT')?.value || '%Y-%m-%d %H:%M:%S',
        VIDEO_OVERLAY_CLOCK_POSITION: document.getElementById('VIDEO_OVERLAY_CLOCK_POSITION')?.value || 'bottom-right',
        VIDEO_OVERLAY_FONT_SIZE: document.getElementById('VIDEO_OVERLAY_FONT_SIZE')?.value || '24',
        CSI_OVERLAY_MODE: document.getElementById('CSI_OVERLAY_MODE')?.value || 'software'
    };
    await saveConfigAndRestartRtsp(config, 'Paramètres overlay');
}

/**
 * Apply all video settings (legacy - saves everything and restarts)
 */
async function applyVideoSettings() {
    try {
        showToast('Application des paramètres vidéo...', 'info');
        
        let formatValue = document.getElementById('VIDEOIN_FORMAT')?.value || 'auto';
        if (!ALLOWED_VIDEO_FORMATS.includes(String(formatValue).toUpperCase())) {
            formatValue = 'auto';
        }
        const config = {
            VIDEOIN_WIDTH: document.getElementById('VIDEOIN_WIDTH')?.value || '',
            VIDEOIN_HEIGHT: document.getElementById('VIDEOIN_HEIGHT')?.value || '',
            VIDEOIN_FPS: document.getElementById('VIDEOIN_FPS')?.value || '',
            VIDEOIN_FORMAT: formatValue,
            VIDEO_OVERLAY_ENABLE: document.getElementById('VIDEO_OVERLAY_ENABLE')?.value || 'no',
            VIDEO_OVERLAY_TEXT: document.getElementById('VIDEO_OVERLAY_TEXT')?.value || '',
            VIDEO_OVERLAY_POSITION: document.getElementById('VIDEO_OVERLAY_POSITION')?.value || 'top-left',
            VIDEO_OVERLAY_SHOW_DATETIME: document.getElementById('VIDEO_OVERLAY_SHOW_DATETIME')?.value || 'no',
            VIDEO_OVERLAY_DATETIME_FORMAT: document.getElementById('VIDEO_OVERLAY_DATETIME_FORMAT')?.value || '%Y-%m-%d %H:%M:%S',
            VIDEO_OVERLAY_CLOCK_POSITION: document.getElementById('VIDEO_OVERLAY_CLOCK_POSITION')?.value || 'bottom-right',
            VIDEO_OVERLAY_FONT_SIZE: document.getElementById('VIDEO_OVERLAY_FONT_SIZE')?.value || '24',
            CSI_OVERLAY_MODE: document.getElementById('CSI_OVERLAY_MODE')?.value || 'software',
            H264_BITRATE_KBPS: document.getElementById('H264_BITRATE_KBPS')?.value || '1200',
            H264_KEYINT: document.getElementById('H264_KEYINT')?.value || '30',
            H264_PROFILE: document.getElementById('H264_PROFILE')?.value || '',
            H264_QP: document.getElementById('H264_QP')?.value || '',
            STREAM_SOURCE_MODE: document.getElementById('STREAM_SOURCE_MODE')?.value || 'camera',
            STREAM_SOURCE_URL: document.getElementById('STREAM_SOURCE_URL')?.value || '',
            RTSP_PROXY_TRANSPORT: document.getElementById('RTSP_PROXY_TRANSPORT')?.value || 'auto',
            RTSP_PROXY_AUDIO: document.getElementById('RTSP_PROXY_AUDIO')?.value || 'auto',
            RTSP_PROXY_LATENCY_MS: document.getElementById('RTSP_PROXY_LATENCY_MS')?.value || '100',
            SCREEN_DISPLAY: document.getElementById('SCREEN_DISPLAY')?.value || ':0.0',
            RTSP_PROTOCOLS: document.getElementById('RTSP_PROTOCOLS')?.value || 'udp,tcp'
        };
        
        await saveConfigAndRestartRtsp(config, 'tous les paramètres vidéo');
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// Dynamic Video Format Dropdown (v2.36.10)
// ============================================================================

// Store detected formats globally
let detectedFormats = [];

/**
 * Populate the manual format dropdown with formats detected from camera hardware
 */
function populateManualFormatDropdown(formats, cameraType) {
    const select = document.getElementById('manual-format-select');
    const formatInput = document.getElementById('VIDEOIN_FORMAT');
    const helpText = document.getElementById('format-help-text');
    
    if (!select) return;
    
    // Get current configured format
    const currentFormat = formatInput?.value || 'auto';
    
    // Clear and rebuild options
    select.innerHTML = '<option value="auto">Auto (détection automatique)</option>';
    
    // Extract unique formats from camera data
    const uniqueFormats = new Set();
    if (formats && Array.isArray(formats)) {
        formats.forEach(f => {
            if (f.format) {
                uniqueFormats.add(f.format.toUpperCase());
            }
        });
    }
    
    // Store for later use
    detectedFormats = Array.from(uniqueFormats);
    
    // Format descriptions
    const formatDescriptions = {
        'MJPG': 'MJPEG - Compressé, faible CPU',
        'MJPEG': 'MJPEG - Compressé, faible CPU',
        'YUYV': 'YUYV (raw) - Non compressé, CPU élevé',
        'YUY2': 'YUY2 (raw) - Non compressé, CPU élevé',
        'H264': 'H.264 - Encodé hardware (si supporté)',
        'NV12': 'NV12 - Format brut YUV 4:2:0',
        'I420': 'I420 - Format brut YUV 4:2:0',
        'RGB3': 'RGB24 - Format couleur non compressé',
        'BGR3': 'BGR24 - Format couleur non compressé',
        'GREY': 'Grayscale - Niveaux de gris'
    };
    
    // Add detected formats
    detectedFormats.forEach(format => {
        const desc = formatDescriptions[format] || format;
        const option = document.createElement('option');
        option.value = format;
        option.textContent = desc;
        if (currentFormat.toUpperCase() === format.toUpperCase()) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    
    // Update help text based on camera type
    if (helpText) {
        if (cameraType === 'libcamera' || cameraType === 'csi') {
            helpText.textContent = 'Caméra CSI : le format est géré automatiquement par Picamera2.';
            select.disabled = true;
            select.value = 'auto';
        } else if (detectedFormats.length === 0) {
            helpText.textContent = 'Aucun format détecté. Utilisez Auto ou saisissez manuellement.';
        } else {
            helpText.textContent = `${detectedFormats.length} format(s) détecté(s) : ${detectedFormats.join(', ')}`;
            select.disabled = false;
        }
    }
    
    console.log(`[config_video] Populated ${detectedFormats.length} formats from camera: ${detectedFormats.join(', ')}`);
}

/**
 * Handle manual format dropdown change
 */
function onManualFormatChange(value) {
    const formatInput = document.getElementById('VIDEOIN_FORMAT');
    if (formatInput) {
        formatInput.value = value;
        console.log(`[config_video] Manual format changed to: ${value}`);
    }
}

// ============================================================================
// Expose functions to global scope
// ============================================================================

window.detectedResolutions = detectedResolutions;
window.initForm = initForm;
window.saveConfig = saveConfig;
window.applyAudioConfig = applyAudioConfig;
window.resetForm = resetForm;
window.detectCameras = detectCameras;
window.selectCamera = selectCamera;
window.onCameraTypeChange = onCameraTypeChange;
window.updateConfigField = updateConfigField;
window.detectAudio = detectAudio;
window.selectAudio = selectAudio;
window.updateAudioGainDisplay = updateAudioGainDisplay;
window.loadResolutions = loadResolutions;
window.onResolutionSelectChange = onResolutionSelectChange;
window.toggleManualResolution = toggleManualResolution;
window.applyVideoSettings = applyVideoSettings;
// New RTSP section-specific apply functions (v2.36.01)
window.applyRtspServerConfig = applyRtspServerConfig;
window.applyRtspAuthConfig = applyRtspAuthConfig;
window.applyVideoOutputConfig = applyVideoOutputConfig;
window.applyVideoAdvancedConfig = applyVideoAdvancedConfig;
window.applyOverlayConfig = applyOverlayConfig;
// Bitrate mode toggle (v2.36.02)
window.toggleBitrateMode = toggleBitrateMode;
// Quality level selector (v2.36.03)
window.onQualityLevelChange = onQualityLevelChange;
// Dynamic format dropdown (v2.36.10)
window.populateManualFormatDropdown = populateManualFormatDropdown;
window.onManualFormatChange = onManualFormatChange;
window.detectedFormats = detectedFormats;

})();





/**
 * RTSP Recorder Web Manager - Config/Audio/Video helpers
 * Version: 2.33.06
 */

(function () {
const t = window.t || function (key) { return key; };
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
            showToast(t('ui.config.saved'), 'success');
            
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
            const message = data.message || data.error || errors || t('ui.config.save_failed');
            showToast(t('ui.errors.with_message', { message: message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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

        showToast(t('ui.audio.applying'), 'info');

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
            const message = data.message || data.error || errors || t('ui.config.save_failed');
            showToast(t('ui.errors.with_message', { message: message }), 'error');
            return;
        }

        showToast(t('ui.audio.saved_restart'), 'success');
        await controlServiceAction('restart', 'rpi-av-rtsp-recorder');
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
            showToast(t('ui.form.reset'), 'info');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Detect available cameras
 */
    async function detectCameras() {
    try {
        showToast(t('ui.camera.detecting'), 'info');
        
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
            showToast(t('ui.camera.detected_count', { count: data.cameras.length }), 'success');
        } else {
            listContainer.innerHTML = `<div class="detection-item"><span class="text-muted">${t('ui.camera.none_detected')}</span></div>`;
            showToast(t('ui.camera.none_detected'), 'warning');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Select camera device
 */
function selectCamera(device, type) {
    if (device !== 'CSI') {
        document.getElementById('VIDEO_DEVICE').value = device;
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
    showToast(t('ui.camera.selected', { device: device }), 'success');
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
    showToast(t('ui.camera.mode_changed', { mode: cameraType.toUpperCase() }), 'info');
    
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
        showToast(t('ui.audio.detecting'), 'info');
        
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
            showToast(t('ui.audio.detected_count', { count: data.devices.length }), 'success');
        } else {
            listContainer.innerHTML = `<div class="detection-item"><span class="text-muted">${t('ui.audio.none_detected')}</span></div>`;
            showToast(t('ui.audio.none_detected'), 'warning');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Select audio device
 */
function selectAudio(device) {
    document.getElementById('AUDIO_DEVICE').value = device;
    document.getElementById('audio-list').innerHTML = '';
    showToast(t('ui.audio.selected', { device: device }), 'success');
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
        return t('ui.video.encoder_picamera2');
    }
    if (formatUpper === 'H264') {
        return t('ui.video.encoder_direct');
    }
    if (encoderCaps && encoderCaps.available) {
        const maxWidth = parseInt(encoderCaps.max_width) || 0;
        const maxHeight = parseInt(encoderCaps.max_height) || 0;
        if (maxWidth > 0 && maxHeight > 0) {
            return (width <= maxWidth && height <= maxHeight) ? t('ui.video.encoder_hardware') : t('ui.video.encoder_software');
        }
        return t('ui.video.encoder_hardware');
    }
    return t('ui.video.encoder_software');
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
        select.innerHTML = `<option value="">${t('ui.video.resolution_detecting')}</option>`;
        select.disabled = true;
        
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        const response = await fetch(`/api/camera/formats?device=${encodeURIComponent(device)}`);
        const data = await response.json();
        
        if (data.success && data.formats.length > 0) {
            detectedResolutions = [];
            let options = `<option value="">${t('ui.video.resolution_select')}</option>`;
            const cameraType = data.camera_type?.type || 'usb';
            currentCameraType = cameraType;
            const encoderCaps = data.encoder || {};
            
            // Get current values to pre-select
            const currentWidth = parseInt(document.getElementById('VIDEO_WIDTH')?.value) || 0;
            const currentHeight = parseInt(document.getElementById('VIDEO_HEIGHT')?.value) || 0;
            const currentFormat = (document.getElementById('VIDEO_FORMAT')?.value || '').toUpperCase();
            let selectedIndex = '';
            let fallbackIndex = '';
            
            for (const fmt of data.formats) {
                // Add optgroup for each format
                options += `<optgroup label="${fmt.format}">`;
                
                for (const res of fmt.resolutions) {
                    const fps = res.framerates.length > 0 ? Math.floor(res.framerates[0]) : 30;
                    const allFps = res.framerates.map(f => Math.floor(f)).join(', ');
                    const megapixels = ((res.width * res.height) / 1000000).toFixed(1);
                    
                    // Store resolution data for later use
                    const resIndex = detectedResolutions.length;
                    const encoderLabel = getEncoderLabel(fmt.format, res.width, res.height, cameraType, encoderCaps);
                    detectedResolutions.push({
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
                            selectedIndex = resIndex;
                        } else if (!fallbackIndex) {
                            fallbackIndex = resIndex;
                        }
                    }
                    
                    options += `<option value="${resIndex}">`;
                    options += `${res.width}×${res.height} @ ${fps}${t('ui.units.fps_suffix')} (${megapixels}${t('ui.units.mp_suffix')}) - ${encoderLabel}`;
                    options += `</option>`;
                }
                
                options += '</optgroup>';
            }
            
            select.innerHTML = options;
            select.disabled = false;
            if (selectedIndex !== '') {
                select.value = String(selectedIndex);
            } else if (fallbackIndex !== '') {
                select.value = String(fallbackIndex);
            }
            
            // Trigger change to show details if something is selected
            if (select.value) {
                onResolutionSelectChange();
            }
            
            console.log(`Loaded ${detectedResolutions.length} resolutions`);
        } else {
            select.innerHTML = `<option value="">${t('ui.video.resolution_none')}</option>`;
            select.disabled = true;
        }
    } catch (error) {
        console.error('Error loading resolutions:', error);
        select.innerHTML = `<option value="">${t('ui.video.resolution_error')}</option>`;
        select.disabled = true;
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
    
    const resIndex = parseInt(select.value);
    const res = detectedResolutions[resIndex];
    
    if (!res) return;
    
    // Update hidden/manual fields with selected values
    document.getElementById('VIDEO_WIDTH').value = res.width;
    document.getElementById('VIDEO_HEIGHT').value = res.height;
    let formatValue = res.format || 'auto';
    if (currentCameraType === 'libcamera' || currentCameraType === 'csi') {
        formatValue = 'auto';
    }
    if (!ALLOWED_VIDEO_FORMATS.includes(String(formatValue).toUpperCase())) {
        formatValue = 'auto';
    }
    document.getElementById('VIDEO_FORMAT').value = formatValue;
    
    // Only set FPS if user manually changed resolution (not on page load)
    // This preserves user's custom FPS value when page loads
    const fpsInput = document.getElementById('VIDEO_FPS');
    const currentFps = parseInt(fpsInput.value) || 0;
    if (userTriggered || currentFps <= 0) {
        // User changed resolution or FPS is invalid -> set to max FPS
        fpsInput.value = res.fps;
    } else if (currentFps > res.fps) {
        // Current FPS exceeds resolution's max -> cap it
        fpsInput.value = res.fps;
        console.log(`VIDEO_FPS capped from ${currentFps} to ${res.fps} (resolution max)`);
    }
    // Otherwise keep user's configured FPS value
    
    // Show details panel
    if (detailsDiv) {
        document.getElementById('detail-format').textContent = res.format;
        document.getElementById('detail-resolution').textContent = `${res.width} × ${res.height}`;
        document.getElementById('detail-megapixels').textContent = `${res.megapixels} ${t('ui.units.mp_suffix')}`;
        document.getElementById('detail-fps').textContent = `${res.framerates.join(', ')} ${t('ui.units.fps_suffix')}`;
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
        const formatInput = document.getElementById('VIDEO_FORMAT');
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
 * Apply video settings (save and restart)
 */
async function applyVideoSettings() {
    try {
        showToast(t('ui.video.applying'), 'info');
        
        let formatValue = document.getElementById('VIDEO_FORMAT')?.value || 'auto';
        if (!ALLOWED_VIDEO_FORMATS.includes(String(formatValue).toUpperCase())) {
            formatValue = 'auto';
        }
        const config = {
            VIDEO_WIDTH: document.getElementById('VIDEO_WIDTH').value,
            VIDEO_HEIGHT: document.getElementById('VIDEO_HEIGHT').value,
            VIDEO_FPS: document.getElementById('VIDEO_FPS').value,
            VIDEO_FORMAT: formatValue,
            VIDEO_OVERLAY_ENABLE: document.getElementById('VIDEO_OVERLAY_ENABLE')?.value || 'no',
            VIDEO_OVERLAY_TEXT: document.getElementById('VIDEO_OVERLAY_TEXT')?.value || '',
            VIDEO_OVERLAY_POSITION: document.getElementById('VIDEO_OVERLAY_POSITION')?.value || 'top-left',
            VIDEO_OVERLAY_SHOW_DATETIME: document.getElementById('VIDEO_OVERLAY_SHOW_DATETIME')?.value || 'no',
            VIDEO_OVERLAY_DATETIME_FORMAT: document.getElementById('VIDEO_OVERLAY_DATETIME_FORMAT')?.value || '%Y-%m-%d %H:%M:%S',
            VIDEO_OVERLAY_CLOCK_POSITION: document.getElementById('VIDEO_OVERLAY_CLOCK_POSITION')?.value || 'bottom-right',
            VIDEO_OVERLAY_FONT_SIZE: document.getElementById('VIDEO_OVERLAY_FONT_SIZE')?.value || '24',
            CSI_OVERLAY_MODE: document.getElementById('CSI_OVERLAY_MODE')?.value || 'software',
            H264_BITRATE_KBPS: document.getElementById('H264_BITRATE_KBPS').value,
            H264_KEYINT: document.getElementById('H264_KEYINT').value,
            H264_PROFILE: document.getElementById('H264_PROFILE').value,
            H264_QP: document.getElementById('H264_QP').value
        };
        
        // Save config
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.video.saved_restart'), 'success');
            
            // Restart RTSP service to apply changes
            try {
                const restartResponse = await fetch('/api/service/rpi-av-rtsp-recorder/restart', {
                    method: 'POST'
                });
                const restartData = await restartResponse.json();
                if (restartData.success) {
                    showToast(t('ui.video.service_restart_success'), 'success');
                } else {
                    showToast(t('ui.video.service_restart_failed', { message: restartData.error }), 'warning');
                }
            } catch (e) {
                showToast(t('ui.video.service_restart_manual'), 'warning');
            }
        } else {
            const errors = Array.isArray(data.errors) ? data.errors.join(', ') : '';
            const message = data.error || data.message || errors || t('ui.config.save_failed');
            showToast(t('ui.errors.with_message', { message: message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

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
})();











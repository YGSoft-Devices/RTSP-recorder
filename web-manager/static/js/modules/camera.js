/**
 * RTSP Recorder Web Manager - Preview and camera controls
 * Version: 2.33.06
 */

(function () {
const t = window.t || function (key) { return key; };
// Video Preview Functions
// ============================================================================

let previewActive = false;

/**
 * Start the video preview stream
 */
async function startPreview() {
    const source = document.getElementById('preview-source').value;
    const quality = document.getElementById('preview-quality').value;
    const [width, height] = quality.split('x');
    
    const streamImg = document.getElementById('preview-stream');
    const placeholder = document.getElementById('preview-placeholder');
    const btnStart = document.getElementById('btn-preview-start');
    const btnStop = document.getElementById('btn-preview-stop');
    const statusText = document.getElementById('preview-status-text');
    
    // Build stream URL with cache-busting parameter
    const timestamp = Date.now();
    const streamUrl = `/api/video/preview/stream?source=${source}&width=${width}&height=${height}&fps=10&t=${timestamp}`;
    
    // Update UI state - show connecting
    placeholder.innerHTML = `
        <i class="fas fa-spinner fa-spin"></i>
        <p>${t('ui.preview.connecting')}</p>
        <small>${t('ui.preview.initializing')}</small>
    `;
    statusText.innerHTML = `<i class="fas fa-circle preview-status-dot" style="color: var(--warning-color);"></i> ${t('ui.preview.connecting')}`;
    
    // Set stream source
    streamImg.src = streamUrl;
    
    // Handle stream load success
    streamImg.onload = function() {
        placeholder.style.display = 'none';
        streamImg.style.display = 'block';
        btnStart.style.display = 'none';
        btnStop.style.display = 'inline-flex';
        statusText.innerHTML = `<i class="fas fa-circle preview-status-dot active"></i> ${t('ui.preview.streaming')}`;
        previewActive = true;
        showToast(t('ui.preview.started'), 'success');
    };
    
    // Handle stream errors
    streamImg.onerror = function() {
        if (!previewActive) {
            placeholder.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <p>${t('ui.preview.connection_error_title')}</p>
                <small>${t('ui.preview.connection_error_hint')}</small>
            `;
            statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${t('ui.errors.generic')}`;
            showToast(t('ui.preview.connection_error_toast'), 'error');
        } else {
            stopPreview();
            showToast(t('ui.preview.stream_interrupted'), 'warning');
        }
    };
}

/**
 * Stop the video preview stream
 */
function stopPreview() {
    const streamImg = document.getElementById('preview-stream');
    const placeholder = document.getElementById('preview-placeholder');
    const btnStart = document.getElementById('btn-preview-start');
    const btnStop = document.getElementById('btn-preview-stop');
    const statusText = document.getElementById('preview-status-text');
    
    // Stop stream by removing src
    streamImg.src = '';
    previewActive = false;
    
    // Update UI state
    streamImg.style.display = 'none';
    placeholder.style.display = 'flex';
    btnStart.style.display = 'inline-flex';
    btnStop.style.display = 'none';
    statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${t('ui.status.inactive')}`;
    
    showToast(t('ui.preview.stopped'), 'info');
}

/**
 * Take a snapshot from the camera
 */
async function takeSnapshot() {
    const quality = document.getElementById('preview-quality').value;
    const [width, height] = quality.split('x');
    
    try {
        showToast(t('ui.preview.snapshot_in_progress'), 'info');
        
        const response = await fetch(`/api/video/preview/snapshot?width=${width}&height=${height}`);
        
        if (!response.ok) {
            throw new Error('Failed to capture snapshot');
        }
        
        const blob = await response.blob();
        
        // Create download link
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `snapshot_${new Date().toISOString().replace(/[:.]/g, '-')}.jpg`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast(t('ui.preview.snapshot_downloaded'), 'success');
    } catch (error) {
        console.error('Snapshot error:', error);
        showToast(t('ui.preview.snapshot_error'), 'error');
    }
}

/**
 * Check preview availability on page load
 */
async function checkPreviewStatus() {
    try {
        const response = await fetch('/api/video/preview/status');
        const data = await response.json();
        
        const placeholder = document.getElementById('preview-placeholder');
        const statusText = document.getElementById('preview-status-text');
        
        if (!data.preview_available) {
            placeholder.innerHTML = `
                <i class="fas fa-video-slash"></i>
                <p>${t('ui.preview.camera_unavailable')}</p>
                <small>${t('ui.preview.camera_unavailable_hint')}</small>
            `;
            statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${t('ui.preview.unavailable')}`;
        } else {
            const sourceLabel = data.preview_source === 'rtsp' ? t('ui.preview.source_rtsp') : t('ui.preview.source_direct');
            statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${t('ui.preview.ready', { source: sourceLabel })}`;
        }
    } catch (error) {
        console.error('Preview status check failed:', error);
    }
}


// ============================================================================
// Camera Control Functions
// ============================================================================

/**
 * Load camera controls and autofocus status
 */
async function loadCameraControls() {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        const response = await fetch(`/api/camera/autofocus?device=${encodeURIComponent(device)}`);
        const data = await response.json();
        
        if (data.success) {
            const af = data.autofocus;
            const autofocusCheckbox = document.getElementById('camera_autofocus');
            const autofocusStatus = document.getElementById('autofocus-status');
            const manualFocusGroup = document.getElementById('manual-focus-group');
            const focusSlider = document.getElementById('camera_focus');
            const focusValue = document.getElementById('focus-value');
            
            if (af.autofocus_available) {
                autofocusCheckbox.disabled = false;
                autofocusCheckbox.checked = af.autofocus_enabled;
                autofocusStatus.textContent = af.autofocus_enabled ? t('ui.value.enabled') : t('ui.value.disabled');
                autofocusStatus.className = 'control-status ' + (af.autofocus_enabled ? 'status-on' : 'status-off');
                
                // Show/hide manual focus based on autofocus state
                if (af.focus_absolute_available) {
                    manualFocusGroup.style.display = af.autofocus_enabled ? 'none' : 'block';
                    focusSlider.min = af.focus_min;
                    focusSlider.max = af.focus_max;
                    focusSlider.value = af.focus_absolute;
                    focusValue.textContent = af.focus_absolute;
                }
            } else {
                autofocusCheckbox.disabled = true;
                autofocusStatus.textContent = t('ui.status.unavailable');
                autofocusStatus.className = 'control-status status-unavailable';
                manualFocusGroup.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading camera controls:', error);
        document.getElementById('autofocus-status').textContent = t('ui.errors.generic');
    }
}

/**
 * Set camera autofocus state
 */
async function setCameraAutofocus(enabled) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(enabled ? t('ui.camera.autofocus_enabling') : t('ui.camera.autofocus_disabling'), 'info');
        
        const response = await fetch('/api/camera/autofocus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const autofocusStatus = document.getElementById('autofocus-status');
            const manualFocusGroup = document.getElementById('manual-focus-group');
            
            autofocusStatus.textContent = enabled ? t('ui.value.enabled') : t('ui.value.disabled');
            autofocusStatus.className = 'control-status ' + (enabled ? 'status-on' : 'status-off');
            
            // Show manual focus slider when autofocus is disabled
            if (manualFocusGroup) {
                manualFocusGroup.style.display = enabled ? 'none' : 'block';
            }
            
            showToast(enabled ? t('ui.camera.autofocus_enabled') : t('ui.camera.autofocus_disabled_manual'), 'success');
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
            // Revert checkbox
            document.getElementById('camera_autofocus').checked = !enabled;
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Set camera manual focus value
 */
async function setCameraFocus(value) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        const focusValue = document.getElementById('focus-value');
        
        // Update display immediately
        if (focusValue) {
            focusValue.textContent = value;
        }
        
        const response = await fetch('/api/camera/focus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, value: parseInt(value) })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showToast(t('ui.camera.focus_error', { message: data.message }), 'error');
        }
    } catch (error) {
        console.error('Error setting focus:', error);
    }
}

/**
 * Trigger one-shot autofocus (focus once then lock)
 */
async function triggerOneShotFocus() {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(t('ui.camera.focus_in_progress'), 'info');
        
        const response = await fetch('/api/camera/oneshot-focus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.focus_locked'), 'success');
            // Update autofocus checkbox to show it's now off (locked)
            const checkbox = document.getElementById('camera_autofocus');
            if (checkbox) {
                checkbox.checked = false;
            }
            const status = document.getElementById('autofocus-status');
            if (status) {
                status.textContent = t('ui.camera.focus_locked_status');
                status.className = 'control-status status-off';
            }
            // Show manual focus slider
            const manualGroup = document.getElementById('manual-focus-group');
            if (manualGroup) {
                manualGroup.style.display = 'block';
            }
        } else {
        showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}


// ============================================================================
// Advanced Camera Controls
// ============================================================================

let advancedControlsData = null;

/**
 * Show advanced camera controls section
 */
function showAdvancedCameraControls() {
    const section = document.getElementById('advanced-camera-section');
    if (section) {
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
        if (section.style.display === 'block') {
            loadAdvancedCameraControls();
        }
    }
}

/**
 * Load all available camera controls for advanced settings
 */
async function loadAdvancedCameraControls() {
    try {
        const cameraType = document.querySelector('input[name="CAMERA_TYPE"]:checked')?.value || 'auto';
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        const container = document.getElementById('advanced-camera-controls');
        const csiNotice = document.getElementById('csi-controls-notice');
        
        // Show CSI notice if camera type is CSI
        if (csiNotice) {
            csiNotice.style.display = (cameraType === 'csi') ? 'flex' : 'none';
        }
        
        // For CSI cameras, load Picamera2 controls instead of v4l2
        if (cameraType === 'csi') {
            await loadCSICameraControls();
            return;
        }
        
        container.innerHTML = `<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> ${t('ui.camera.controls_loading')}</p>`;
        
        const response = await fetch(`/api/camera/all-controls?device=${encodeURIComponent(device)}`);
        const data = await response.json();
        
        if (!data.success) {
            container.innerHTML = `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${data.error || t('ui.camera.controls_load_error')}</p>`;
            return;
        }
        
        advancedControlsData = data;
        renderAdvancedControls(data);
        
    } catch (error) {
        console.error('Error loading advanced controls:', error);
        document.getElementById('advanced-camera-controls').innerHTML = 
            `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${error.message}</p>`;
    }
}

/**
 * Load CSI camera controls via Picamera2
 */
async function loadCSICameraControls() {
    const container = document.getElementById('advanced-camera-controls');
    container.innerHTML = `<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> ${t('ui.camera.csi_controls_loading')}</p>`;
    
    try {
        // Check if CSI/Picamera2 is available
        const availResponse = await fetch('/api/camera/csi/available');
        const availData = await availResponse.json();
        
        if (!availData.available) {
            container.innerHTML = `
                <div class="info-box warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    <div>
                        <strong>Picamera2 non installé</strong>
                        <p>Pour contrôler les paramètres de la caméra CSI, installez Picamera2 :</p>
                        <code>sudo apt install python3-picamera2</code>
                    </div>
                </div>
            `;
            return;
        }
        
        // Load controls
        const response = await fetch('/api/camera/csi/controls');
        const data = await response.json();
        
        if (!data.success) {
            // Check if server is starting up (retry suggested)
            if (data.retry) {
                container.innerHTML = `
                    <div class="info-box info">
                        <i class="fas fa-hourglass-half"></i>
                        <div>
                            <strong>Serveur CSI en démarrage...</strong>
                            <p>Le serveur RTSP CSI est en cours de démarrage. Rechargement automatique dans 3 secondes.</p>
                        </div>
                    </div>
                `;
                // Auto-retry after 3 seconds
                setTimeout(() => loadCSICameraControls(), 3000);
                return;
            }
            
            // Check if camera is busy (RTSP stream active)
            if (data.camera_busy || data.error?.includes('occupée') || data.error?.includes('busy')) {
                container.innerHTML = `
                    <div class="info-box warning">
                        <i class="fas fa-broadcast-tower"></i>
                        <div>
                            <strong>Caméra en cours d'utilisation</strong>
                            <p>${t('ui.camera.csi_in_use_hint')}</p>
                            <p>${t('ui.camera.csi_in_use_steps_title')}</p>
                            <ol style="margin: 10px 0; padding-left: 20px;">
                                <li>${t('ui.camera.csi_stop_stream_step')}</li>
                                <li>${t('ui.camera.csi_modify_settings_step')}</li>
                                <li>${t('ui.camera.csi_restart_stream')}</li>
                            </ol>
                            <button type="button" class="btn btn-warning btn-sm" onclick="stopRtspForConfig()">
                                <i class="fas fa-stop"></i> ${t('ui.camera.csi_stop_stream_button')}
                            </button>
                        </div>
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="info-box warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        <div>
                            <strong>${t('ui.camera.csi_load_error_title')}</strong>
                            <p>${data.error || t('ui.errors.generic')}</p>
                            <button type="button" class="btn btn-sm btn-secondary" onclick="loadCSICameraControls()">
                                <i class="fas fa-redo"></i> ${t('ui.actions.retry')}
                            </button>
                        </div>
                    </div>
                `;
            }
            return;
        }
        
        advancedControlsData = data;
        renderCSIControls(data);
        
    } catch (error) {
        console.error('Error loading CSI controls:', error);
        container.innerHTML = `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${error.message}</p>`;
    }
}

/**
 * Stop RTSP stream temporarily to configure CSI camera
 */
async function stopRtspForConfig() {
    if (!confirm(t('ui.camera.csi_stop_stream_confirm'))) return;
    
    try {
        const response = await fetch('/api/service/rpi-av-rtsp-recorder/stop', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.csi_stream_stopped_loading'), 'success');
            // Wait a bit for camera to be released
            setTimeout(() => loadCSICameraControls(), 2000);
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Render CSI camera controls (Picamera2)
 */
function renderCSIControls(data) {
    const container = document.getElementById('advanced-camera-controls');
    const grouped = data.grouped || {};
    
    const categoryLabels = {
        'exposure': { icon: 'fa-sun', label: t('ui.camera.csi.category.exposure') },
        'color': { icon: 'fa-palette', label: t('ui.camera.csi.category.color') },
        'focus': { icon: 'fa-crosshairs', label: t('ui.camera.csi.category.focus') },
        'noise': { icon: 'fa-volume-off', label: t('ui.camera.csi.category.noise') },
        'auto': { icon: 'fa-magic', label: t('ui.camera.csi.category.auto') },
        'other': { icon: 'fa-sliders-h', label: t('ui.camera.csi.category.other') }
    };
    
    let html = `
        <div class="live-apply-notice csi-notice">
            <i class="fas fa-microchip"></i>
            <span>${t('ui.camera.csi.controls_title')}</span>
            <span class="live-apply-indicator">
                <i class="fas fa-save"></i> ${t('ui.camera.csi.controls_saved')}
            </span>
        </div>
    `;
    
    // Camera info if available
    if (data.camera_info) {
        html += `
            <div class="camera-info-box">
                <strong><i class="fas fa-camera"></i> ${data.camera_info.model || 'Caméra CSI'}</strong>
                ${data.camera_info.pixel_array_size ? `<span class="info-detail">${data.camera_info.pixel_array_size[0]}×${data.camera_info.pixel_array_size[1]} pixels</span>` : ''}
            </div>
        `;
    }
    
    for (const [category, controls] of Object.entries(grouped)) {
        if (Object.keys(controls).length === 0) continue;
        
        const catInfo = categoryLabels[category] || { icon: 'fa-cog', label: category };
        
        html += `
            <div class="control-category">
                <h5><i class="fas ${catInfo.icon}"></i> ${catInfo.label}</h5>
                <div class="control-items">
        `;
        
        for (const [name, ctrl] of Object.entries(controls)) {
            html += renderCSIControlItem(ctrl);
        }
        
        html += `
                </div>
            </div>
        `;
    }
    
    // Actions
    html += `
        <div class="csi-controls-actions">
            <button type="button" class="btn btn-secondary" onclick="loadCSICameraControls()">
                <i class="fas fa-sync"></i> Rafraîchir
            </button>
            <button type="button" class="btn btn-warning" onclick="resetCSIControls()">
                <i class="fas fa-undo"></i> Réinitialiser
            </button>
        </div>
    `;
    
    container.innerHTML = html;
}

/**
 * Human-readable labels and descriptions for CSI camera controls
 */
const CSI_CONTROL_LABELS = {
    // Exposure
    'ExposureTime': { label: 'Temps d\'exposition', desc: 'Durée d\'exposition en µs', unit: 'µs' },
    'AnalogueGain': { label: 'Gain analogique', desc: 'Amplification du signal capteur' },
    'ExposureValue': { label: 'Correction d\'exposition (EV)', desc: 'Ajustement luminosité (-8 à +8)' },
    'AeExposureMode': { label: 'Mode d\'exposition', desc: '0=Normal, 1=Court, 2=Long, 3=Personnalisé' },
    'ExposureTimeMode': { label: 'Mode temps expo', desc: '0=Auto, 1=Manuel' },
    'AnalogueGainMode': { label: 'Mode gain', desc: '0=Auto, 1=Manuel' },
    'ColourGains': { label: 'Gains couleur (R/B)', desc: 'Gains rouge/bleu manuels' },
    
    // Color
    'Brightness': { label: 'Luminosité', desc: 'Ajustement luminosité (-1 à +1)' },
    'Contrast': { label: 'Contraste', desc: 'Ratio de contraste' },
    'Saturation': { label: 'Saturation', desc: 'Intensité des couleurs' },
    'Sharpness': { label: 'Netteté', desc: 'Niveau de netteté de l\'image' },
    'ColourCorrectionMatrix': { label: 'Matrice couleur', desc: 'Correction colorimétrique' },
    'ColourTemperature': { label: 'Température couleur', desc: 'En Kelvin (2000K-10000K)' },
    
    // Auto
    'AeEnable': { label: 'Exposition auto', desc: 'Auto-exposition activée' },
    'AwbEnable': { label: 'Balance blancs auto', desc: 'AWB activée' },
    'AwbMode': { label: 'Mode AWB', desc: '0=Auto, 1=Tungstène, 2=Fluorescent, 3=Intérieur, 4=Soleil, 5=Nuageux, 6=Personnalisé' },
    'AeMeteringMode': { label: 'Mode mesure AE', desc: '0=Centre, 1=Spot, 2=Matrice, 3=Personnalisé' },
    'AeConstraintMode': { label: 'Contrainte AE', desc: '0=Normal, 1=Highlights, 2=Shadows, 3=Personnalisé' },
    'AeFlickerMode': { label: 'Anti-flicker', desc: '0=Off, 1=Manuel' },
    'AeFlickerPeriod': { label: 'Période flicker', desc: 'Pour 50Hz=10000µs, 60Hz=8333µs' },
    
    // Noise
    'NoiseReductionMode': { label: 'Réduction bruit', desc: '0=Off, 1=Rapide, 2=Haute qualité, 3=Minimal, 4=ZSL' },
    
    // Other
    'FrameDurationLimits': { label: 'Durée frame', desc: 'Min/Max durée d\'une frame en µs' },
    'HdrMode': { label: 'Mode HDR', desc: '0=Off, 1=Single, 2=Multi, 3=Night, 4=Personnalisé' },
    'ScalerCrop': { label: 'Zone de crop', desc: 'Région de recadrage' },
    'SyncMode': { label: 'Mode sync', desc: '0=Off, 1=Server, 2=Client' },
    'SyncFrames': { label: 'Frames sync', desc: 'Frames à synchroniser' }
};

/**
 * Render a single CSI control item
 */
function renderCSIControlItem(ctrl) {
    const { name, display_name, min, max, value, type, read_only, saved, is_array, array_size, array_labels } = ctrl;
    
    // Get human-readable label
    const labelInfo = CSI_CONTROL_LABELS[name] || { label: display_name, desc: '' };
    
    let inputHtml = '';
    const savedBadge = saved ? '<span class="saved-badge"><i class="fas fa-save"></i></span>' : '';
    
    // Handle array types (ColourGains, FrameDurationLimits, ScalerCrop, etc.)
    if (is_array && Array.isArray(value)) {
        const labels = array_labels || value.map((_, i) => `#${i+1}`);
        inputHtml = `<div class="array-control" data-array-name="${name}">`;
        
        for (let i = 0; i < value.length; i++) {
            const elemVal = value[i];
            const isFloat = type.includes('float') || typeof elemVal === 'number' && !Number.isInteger(elemVal);
            const step = isFloat ? '0.01' : '1';
            let elemMin = Array.isArray(min) ? (min[i] || 0) : (min || 0);
            let elemMax = Array.isArray(max) ? (max[i] || 100) : (max || 100);
            if (typeof elemVal === 'number') {
                if (Number.isFinite(elemMin)) {
                    elemMin = Math.min(elemMin, elemVal);
                }
                if (Number.isFinite(elemMax)) {
                    elemMax = Math.max(elemMax, elemVal);
                }
            }
            
            inputHtml += `
                <div class="array-element">
                    <span class="array-label">${labels[i] || '#' + (i+1)}</span>
                    <input type="number" 
                           id="csi-ctrl-${name}-${i}" 
                           class="array-input"
                           min="${elemMin}" 
                           max="${elemMax}" 
                           step="${step}"
                           value="${typeof elemVal === 'number' ? elemVal.toFixed(isFloat ? 2 : 0) : elemVal}"
                           ${read_only ? 'disabled' : ''}
                           onchange="setCSIArrayControl('${name}', ${value.length})">
                </div>
            `;
        }
        inputHtml += '</div>';
    } else if (type === 'bool') {
        inputHtml = `
            <label class="toggle-switch">
                <input type="checkbox" 
                       id="csi-ctrl-${name}" 
                       ${value ? 'checked' : ''} 
                       ${read_only ? 'disabled' : ''}
                       onchange="setCSIControl('${name}', this.checked)">
                <span class="toggle-slider"></span>
            </label>
        `;
    } else if (type === 'int' || type === 'float') {
        const step = type === 'float' ? '0.01' : '1';
        inputHtml = `
            <div class="range-control">
                <input type="range" 
                       id="csi-ctrl-${name}" 
                       min="${min}" 
                       max="${max}" 
                       step="${step}"
                       value="${value}"
                       ${read_only ? 'disabled' : ''}
                       oninput="document.getElementById('csi-val-${name}').textContent = this.value"
                       onchange="setCSIControl('${name}', parseFloat(this.value))">
                <span class="range-value" id="csi-val-${name}">${value}</span>
            </div>
            <div class="range-limits">
                <span>${min}</span>
                <span>${max}</span>
            </div>
        `;
    } else {
        inputHtml = `
            <input type="text" 
                   id="csi-ctrl-${name}" 
                   value="${value}"
                   ${read_only ? 'disabled' : ''}
                   onchange="setCSIControl('${name}', this.value)">
        `;
    }
    
    const descHtml = labelInfo.desc ? `<small class="control-desc">${labelInfo.desc}</small>` : '';
    const unitHtml = labelInfo.unit ? ` <span class="control-unit">${labelInfo.unit}</span>` : '';
    
    return `
        <div class="control-item ${read_only ? 'read-only' : ''}" title="${labelInfo.desc || name}">
            <label for="csi-ctrl-${name}">
                ${labelInfo.label}${unitHtml} ${savedBadge}
            </label>
            ${descHtml}
            ${inputHtml}
        </div>
    `;
}

/**
 * Set a CSI scalar control value
 */
async function setCSIControl(name, value) {
    try {
        const response = await fetch('/api/camera/csi/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ control: name, value: value, save: true })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.control_set', { name: name, value: value }), 'success');
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Set a CSI array control value (ColourGains, etc.)
 */
async function setCSIArrayControl(name, size) {
    const values = [];
    for (let i = 0; i < size; i++) {
        const input = document.getElementById(`csi-ctrl-${name}-${i}`);
        if (input) {
            values.push(parseFloat(input.value));
        }
    }
    
    try {
        const response = await fetch('/api/camera/csi/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ control: name, value: values, save: true })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.control_set', { name: name, value: `[${values.join(', ')}]` }), 'success');
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Reset CSI controls to defaults
 */
async function resetCSIControls() {
    if (!confirm(t('ui.camera.csi_reset_confirm'))) return;
    
    try {
        const response = await fetch('/api/camera/csi/tuning/reset', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.csi_settings_reset'), 'success');
            loadCSICameraControls();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Render advanced camera controls by category
 */
function renderAdvancedControls(data) {
    const container = document.getElementById('advanced-camera-controls');
    const grouped = data.grouped || {};
    
    const categoryLabels = {
        'focus': { icon: 'fa-crosshairs', label: t('ui.camera.advanced.category.focus') },
        'exposure': { icon: 'fa-sun', label: t('ui.camera.advanced.category.exposure') },
        'white_balance': { icon: 'fa-temperature-half', label: t('ui.camera.advanced.category.white_balance') },
        'color': { icon: 'fa-palette', label: t('ui.camera.advanced.category.color') },
        'power_line': { icon: 'fa-bolt', label: t('ui.camera.advanced.category.power_line') },
        'other': { icon: 'fa-sliders-h', label: t('ui.camera.advanced.category.other') }
    };
    
    // Live indicator at the top
    let html = `
        <div class="live-apply-notice">
            <i class="fas fa-broadcast-tower"></i>
            <span>${t('ui.camera.advanced.live_apply_notice')}</span>
            <span id="live-apply-indicator" class="live-apply-indicator">
                <i class="fas fa-check-circle"></i> ${t('ui.camera.advanced.applied')}
            </span>
        </div>
    `;
    
    for (const [category, controls] of Object.entries(grouped)) {
        if (controls.length === 0) continue;
        
        const catInfo = categoryLabels[category] || { icon: 'fa-cog', label: category };
        
        html += `
            <div class="control-category">
                <h5><i class="fas ${catInfo.icon}"></i> ${catInfo.label}</h5>
                <div class="control-items">
        `;
        
        for (const ctrl of controls) {
            html += renderControlInput(ctrl);
        }
        
        html += '</div></div>';
    }
    
    if (!html) {
        html = `<p class="info-text"><i class="fas fa-info-circle"></i> ${t('ui.camera.controls_none')}</p>`;
    }
    
    container.innerHTML = html;
}

/**
 * Render a single control input based on its type
 */
function renderControlInput(ctrl) {
    const { name, type, display_name, value, min, max, step, default: defaultVal, menu_items } = ctrl;
    
    let inputHtml = '';
    
    switch (type) {
        case 'bool':
            inputHtml = `
                <label class="toggle-switch">
                    <input type="checkbox" id="ctrl_${name}" 
                           ${value == 1 ? 'checked' : ''} 
                           onchange="setAdvancedControl('${name}', this.checked ? 1 : 0)">
                    <span class="toggle-slider"></span>
                </label>
            `;
            break;
            
        case 'int':
            inputHtml = `
                <div class="range-control">
                    <input type="range" id="ctrl_${name}" 
                           min="${min || 0}" max="${max || 255}" step="${step || 1}"
                           value="${value || 0}"
                           onchange="setAdvancedControl('${name}', parseInt(this.value))">
                    <span class="range-value" id="val_${name}">${value || 0}</span>
                </div>
            `;
            break;
            
        case 'menu':
            inputHtml = '<select id="ctrl_' + name + '" onchange="setAdvancedControl(\'' + name + '\', parseInt(this.value))">';
            if (menu_items) {
                for (const [idx, label] of Object.entries(menu_items)) {
                    inputHtml += `<option value="${idx}" ${parseInt(idx) == value ? 'selected' : ''}>${label}</option>`;
                }
            }
            inputHtml += '</select>';
            break;
            
        default:
            inputHtml = `<input type="number" id="ctrl_${name}" value="${value || 0}" 
                                onchange="setAdvancedControl('${name}', parseInt(this.value))">`;
    }
    
    return `
        <div class="control-item" data-control="${name}">
            <label for="ctrl_${name}" title="${name}">
                ${display_name}
                ${defaultVal !== undefined ? `<small class="default-hint">${t('ui.camera.default_hint', { value: defaultVal })}</small>` : ''}
            </label>
            ${inputHtml}
        </div>
    `;
}

/**
 * Set a single advanced camera control (applied in real-time to the live stream)
 */
async function setAdvancedControl(name, value) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        const controlItem = document.querySelector(`[data-control="${name}"]`);
        
        // Update display immediately for range inputs
        const valSpan = document.getElementById(`val_${name}`);
        if (valSpan) {
            valSpan.textContent = value;
        }
        
        // Visual feedback: show applying state
        if (controlItem) {
            controlItem.classList.add('control-applying');
        }
        
        const response = await fetch('/api/camera/control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, control: name, value })
        });
        
        const data = await response.json();
        
        if (controlItem) {
            controlItem.classList.remove('control-applying');
        }
        
        if (data.success) {
            // Visual feedback: flash green to indicate success
            if (controlItem) {
                controlItem.classList.add('control-applied');
                setTimeout(() => controlItem.classList.remove('control-applied'), 500);
            }
            // Update live indicator
            showLiveAppliedIndicator();
        } else {
            showToast(t('ui.errors.with_message', { message: `${name}: ${data.message}` }), 'error');
            if (controlItem) {
                controlItem.classList.add('control-error');
                setTimeout(() => controlItem.classList.remove('control-error'), 1000);
            }
        }
    } catch (error) {
        console.error(`Error setting control ${name}:`, error);
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Show a brief indicator that changes are applied live
 */
let liveIndicatorTimeout = null;
function showLiveAppliedIndicator() {
    const indicator = document.getElementById('live-apply-indicator');
    if (!indicator) return;
    
    indicator.classList.add('visible');
    
    if (liveIndicatorTimeout) {
        clearTimeout(liveIndicatorTimeout);
    }
    liveIndicatorTimeout = setTimeout(() => {
        indicator.classList.remove('visible');
    }, 2000);
}

/**
 * Restart the RTSP stream (useful if camera settings don't apply live)
 */
async function restartRtspStream() {
    if (!confirm(t('ui.camera.restart_stream_confirm'))) {
        return;
    }
    
    try {
        showToast(t('ui.camera.restarting_stream'), 'info');
        
        const response = await fetch('/api/service/restart', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.stream_restarted'), 'success');
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Reset all advanced controls to their default values
 */
async function resetAdvancedControls() {
    if (!advancedControlsData) return;
    
    const controls = advancedControlsData.controls || {};
    const toReset = {};
    
    for (const [name, ctrl] of Object.entries(controls)) {
        if (ctrl.default !== undefined) {
            toReset[name] = ctrl.default;
        }
    }
    
    if (Object.keys(toReset).length === 0) {
        showToast(t('ui.camera.no_defaults'), 'warning');
        return;
    }
    
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(t('ui.camera.reset_in_progress'), 'info');
        
        const response = await fetch('/api/camera/controls/set-multiple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, controls: toReset })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.controls_reset'), 'success');
            loadAdvancedCameraControls();
        } else {
            showToast(t('ui.camera.controls_reset_errors', { count: data.errors }), 'warning');
            loadAdvancedCameraControls();
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}


// ============================================================================
// Camera Profiles Management
// ============================================================================

let cameraProfiles = {};
let editingProfileId = null;

/**
 * Load camera profiles and scheduler status
 */
async function loadCameraProfiles() {
    try {
        const container = document.getElementById('camera-profiles-list');
        container.innerHTML = `<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> ${t('ui.loading')}</p>`;
        
        const response = await fetch('/api/camera/profiles');
        const data = await response.json();
        
        if (!data.success) {
            container.innerHTML = `<p class="error-text">${data.message}</p>`;
            return;
        }
        
        cameraProfiles = data.profiles || {};
        
        // Update scheduler toggle
        const schedulerToggle = document.getElementById('profiles_scheduler_enabled');
        const schedulerStatus = document.getElementById('scheduler-status');
        
        if (schedulerToggle) {
            schedulerToggle.checked = data.scheduler_enabled;
        }
        if (schedulerStatus) {
            const activeProfile = data.scheduler_active_profile || data.active_profile;
            if (data.scheduler_enabled && activeProfile) {
                schedulerStatus.textContent = t('ui.camera.profile.scheduler_active', { profile: activeProfile });
                schedulerStatus.className = 'control-status status-on';
            } else if (data.scheduler_enabled) {
                schedulerStatus.textContent = t('ui.camera.profile.scheduler_pending');
                schedulerStatus.className = 'control-status status-warning';
            } else {
                schedulerStatus.textContent = t('ui.status.disabled');
                schedulerStatus.className = 'control-status status-off';
            }
        }
        
        renderCameraProfiles(data.profiles, data.current_profile, data.scheduler_active_profile || data.active_profile);
        
    } catch (error) {
        console.error('Error loading profiles:', error);
        document.getElementById('camera-profiles-list').innerHTML = 
            `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}</p>`;
    }
}

/**
 * Render the list of camera profiles
 */
function renderCameraProfiles(profiles, appliedProfile, scheduledProfile) {
    const container = document.getElementById('camera-profiles-list');
    
    if (!profiles || Object.keys(profiles).length === 0) {
        container.innerHTML = `
            <p class="info-text">
                <i class="fas fa-info-circle"></i> ${t('ui.camera.profile.none_configured')}
                ${t('ui.camera.profile.none_configured_hint')}
            </p>
        `;
        return;
    }
    
    let html = '';
    
    for (const [id, profile] of Object.entries(profiles)) {
        const isApplied = id === appliedProfile;
        const isScheduled = id === scheduledProfile;
        const schedule = profile.schedule || {};
        const controlsCount = Object.keys(profile.controls || {}).length;
        
        html += `
            <div class="profile-card ${isApplied ? 'profile-active' : ''} ${!profile.enabled ? 'profile-disabled' : ''}">
                <div class="profile-header">
                    <h5>
                        <i class="fas ${isApplied ? 'fa-play-circle' : 'fa-clock'}"></i>
                        ${profile.display_name || profile.name || id}
                        ${isApplied ? `<span class="badge badge-success">${t('ui.camera.profile.applied')}</span>` : ''}
                        ${isScheduled && !isApplied ? `<span class="badge badge-info">${t('ui.camera.profile.scheduled')}</span>` : ''}
                        ${!profile.enabled ? `<span class="badge badge-muted">${t('ui.value.disabled')}</span>` : ''}
                    </h5>
                    <div class="profile-actions">
                        <button class="btn btn-sm btn-info" onclick="captureProfileSettings('${id}')" title="${t('ui.camera.profile.capture_current_title')}">
                            <i class="fas fa-camera"></i>
                        </button>
                        <button class="btn btn-sm btn-success" onclick="ghostFixProfile('${id}')" title="${t('ui.camera.profile.ghost_fix_title')}">
                            <i class="fas fa-magic"></i> ghost-fix
                        </button>
                        <button class="btn btn-sm btn-warning" onclick="showProfileSettings('${id}')" title="${t('ui.camera.profile.show_settings_title')}">
                            <i class="fas fa-cogs"></i>
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="editProfile('${id}')" title="${t('ui.actions.edit')}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="applyProfile('${id}')" title="${t('ui.actions.apply_now')}">
                            <i class="fas fa-play"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteProfile('${id}')" title="${t('ui.actions.delete')}">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="profile-info">
                    ${profile.description ? `<p class="profile-desc">${profile.description}</p>` : ''}
                    <div class="profile-schedule">
                        <i class="fas fa-clock"></i>
                        ${schedule.start && schedule.end
                            ? `${schedule.start} - ${schedule.end}`
                            : t('ui.camera.profile.no_schedule')}
                    </div>
                    <div class="profile-controls-count">
                        <i class="fas fa-sliders-h"></i> ${t('ui.camera.profile.controls_count', { count: controlsCount })}
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

/**
 * Toggle the camera profiles scheduler
 */
async function toggleProfilesScheduler(enabled) {
    try {
        // First update config
        const configResponse = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ CAMERA_PROFILES_ENABLED: enabled ? 'yes' : 'no' })
        });
        
        if (!configResponse.ok) {
            throw new Error(t('ui.errors.config_update_failed'));
        }
        
        // Then start/stop scheduler
        const action = enabled ? 'start' : 'stop';
        const response = await fetch(`/api/camera/profiles/scheduler/${action}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        showToast(
            enabled ? t('ui.camera.profile.scheduler_enabled') : t('ui.camera.profile.scheduler_disabled'),
            data.success ? 'success' : 'warning'
        );
        
        // Refresh status
        setTimeout(loadCameraProfiles, 500);
        
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Show profile settings in a modal
 */
function showProfileSettings(profileId) {
    const profile = cameraProfiles[profileId];
    if (!profile) {
        showToast(t('ui.camera.profile.not_found'), 'error');
        return;
    }
    
    const controls = profile.controls || {};
    const modal = document.getElementById('profile-settings-modal');
    if (!modal) return;

    document.getElementById('profile-settings-title').textContent =
        t('ui.camera.profile.settings_title', { profile: profile.display_name || profileId });

    const schedule = profile.schedule || {};
    const scheduleText = (schedule.start && schedule.end)
        ? `${schedule.start} - ${schedule.end}`
        : t('ui.camera.profile.no_schedule');
    const controlsCount = Object.keys(controls).length;
    const meta = `
        <div><i class="fas fa-clock"></i> ${scheduleText}</div>
        <div><i class="fas fa-sliders-h"></i> ${t('ui.camera.profile.controls_count', { count: controlsCount })}</div>
    `;
    const metaEl = document.getElementById('profile-settings-meta');
    if (metaEl) metaEl.innerHTML = meta;

    const contentEl = document.getElementById('profile-settings-content');
    if (!contentEl) return;

    if (controlsCount === 0) {
        contentEl.innerHTML = `<p class="info-text">${t('ui.camera.profile.no_settings')}</p>`;
    } else {
        const rows = Object.entries(controls).map(([ctrlName, value]) => {
            let displayValue = value;
            if (Array.isArray(value)) {
                displayValue = '[' + value.join(', ') + ']';
            } else if (value === null || value === undefined) {
                displayValue = t('ui.value.na');
            } else if (typeof value === 'object') {
                displayValue = JSON.stringify(value);
            }
            return `
                <tr>
                    <td class="profile-settings-key">${ctrlName}</td>
                    <td class="profile-settings-value">${displayValue}</td>
                </tr>
            `;
        }).join('');

        contentEl.innerHTML = `
            <table class="profile-settings-table">
                <thead>
                    <tr>
                        <th>${t('ui.camera.profile.table_param')}</th>
                        <th>${t('ui.camera.profile.table_value')}</th>
                    </tr>
                </thead>
                <tbody>
                    ${rows}
                </tbody>
            </table>
        `;
    }

    modal.style.display = 'flex';
}

function closeProfileSettingsModal() {
    const modal = document.getElementById('profile-settings-modal');
    if (modal) modal.style.display = 'none';
}

/**
 * Show the add/edit profile modal
 */
function showAddProfileModal() {
    editingProfileId = null;
    document.getElementById('profile-modal-title').textContent = t('ui.camera.profile.new_title');
    document.getElementById('profile-id').value = '';
    document.getElementById('profile-name').value = '';
    document.getElementById('profile-description').value = '';
    document.getElementById('profile-start').value = '07:00';
    document.getElementById('profile-end').value = '19:00';
    document.getElementById('profile-enabled').checked = true;
    document.getElementById('profile-controls-count').textContent = t('ui.camera.profile.controls_saved_count', { count: 0 });
    
    document.getElementById('profile-modal').style.display = 'flex';
}

/**
 * Edit an existing profile
 */
function editProfile(profileId) {
    const profile = cameraProfiles[profileId];
    if (!profile) return;
    
    editingProfileId = profileId;
    document.getElementById('profile-modal-title').textContent = t('ui.camera.profile.edit_title');
    document.getElementById('profile-id').value = profileId;
    document.getElementById('profile-name').value = profile.display_name || profile.name || profileId;
    document.getElementById('profile-description').value = profile.description || '';
    document.getElementById('profile-start').value = profile.schedule?.start || '';
    document.getElementById('profile-end').value = profile.schedule?.end || '';
    document.getElementById('profile-enabled').checked = profile.enabled === true;
    
    const controlsCount = Object.keys(profile.controls || {}).length;
    document.getElementById('profile-controls-count').textContent = t('ui.camera.profile.controls_saved_count', { count: controlsCount });
    
    document.getElementById('profile-modal').style.display = 'flex';
}

/**
 * Close the profile modal
 */
function closeProfileModal() {
    document.getElementById('profile-modal').style.display = 'none';
    editingProfileId = null;
}

/**
 * Save the profile (create or update)
 */
async function saveProfile(event) {
    if (event) event.preventDefault();
    
    const name = document.getElementById('profile-name').value.trim();
    if (!name) {
        showToast(t('ui.camera.profile.name_required'), 'error');
        return;
    }
    
    // Generate ID from name if new profile
    const profileId = editingProfileId || name.toLowerCase().replace(/[^a-z0-9]+/g, '_');
    
    // Get existing controls if editing
    const existingProfile = cameraProfiles[editingProfileId] || {};
    
    const profileData = {
        name: name,
        description: document.getElementById('profile-description').value,
        schedule: {
            start: document.getElementById('profile-start').value,
            end: document.getElementById('profile-end').value
        },
        enabled: document.getElementById('profile-enabled').checked,
        controls: existingProfile.controls || {}
    };
    
    try {
        const response = await fetch(`/api/camera/profiles/${profileId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(profileData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.profile.saved'), 'success');
            closeProfileModal();
            loadCameraProfiles();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Capture current camera settings into a specific profile
 */
async function captureProfileSettings(profileId) {
    if (!confirm(t('ui.camera.profile.capture_confirm', { profile: profileId }))) {
        return;
    }
    
    try {
        showToast(t('ui.camera.profile.capture_in_progress'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            const controlsCount = data.profile ? Object.keys(data.profile.controls || {}).length : 0;
            showToast(t('ui.camera.profile.captured_count_for', { count: controlsCount, profile: profileId }), 'success');
            
            // Reload profiles to update display
            loadCameraProfiles();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Apply ghost-fix controls to a profile (CSI only)
 */
async function ghostFixProfile(profileId) {
    if (!confirm(t('ui.camera.profile.ghost_fix_confirm', { profile: profileId }))) {
        return;
    }
    
    try {
        showToast(t('ui.camera.profile.ghost_fix_in_progress'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/ghost-fix`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || t('ui.camera.profile.ghost_fix_applied'), 'success');
            loadCameraProfiles();
            if (document.getElementById('advanced-camera-section').style.display !== 'none') {
                loadCSICameraControls();
            }
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Capture current camera settings into the profile being edited
 */
async function captureCurrentSettings() {
    const profileId = editingProfileId || document.getElementById('profile-name').value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
    
    if (!profileId) {
        showToast(t('ui.camera.profile.enter_name_first'), 'error');
        return;
    }
    
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(t('ui.camera.profile.capture_in_progress'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const controlsCount = data.profile ? Object.keys(data.profile.controls || {}).length : 0;
            document.getElementById('profile-controls-count').textContent =
                t('ui.camera.profile.captured_count', { count: controlsCount });
            showToast(t('ui.camera.profile.captured_count', { count: controlsCount }), 'success');
            
            // Reload profiles to update local cache
            const profilesResponse = await fetch('/api/camera/profiles');
            const profilesData = await profilesResponse.json();
            if (profilesData.success) {
                cameraProfiles = profilesData.profiles || {};
            }
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Apply a profile immediately
 */
async function applyProfile(profileId) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(t('ui.camera.profile.applying'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.profile.applied_toast', { profile: profileId }), 'success');
            loadCameraProfiles();
            // Also refresh advanced controls if visible
            if (document.getElementById('advanced-camera-section').style.display !== 'none') {
                loadAdvancedCameraControls();
            }
        } else {
            const errors = Array.isArray(data.errors) ? data.errors.join(', ') : '';
            const message = data.message || data.error || errors || t('ui.errors.generic');
            showToast(t('ui.errors.with_message', { message: message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Delete a profile
 */
async function deleteProfile(profileId) {
    if (!confirm(t('ui.camera.profile.delete_confirm', { profile: profileId }))) return;
    
    try {
        const response = await fetch(`/api/camera/profiles/${profileId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.camera.profile.deleted'), 'success');
            loadCameraProfiles();
        } else {
            const errors = Array.isArray(data.errors) ? data.errors.join(', ') : '';
            const message = data.message || data.error || errors || t('ui.errors.generic');
            showToast(t('ui.errors.with_message', { message: message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}


// ============================================================================

    window.startPreview = startPreview;
    window.stopPreview = stopPreview;
    window.takeSnapshot = takeSnapshot;
    window.checkPreviewStatus = checkPreviewStatus;
    window.loadCameraControls = loadCameraControls;
    window.setCameraAutofocus = setCameraAutofocus;
    window.setCameraFocus = setCameraFocus;
    window.triggerOneShotFocus = triggerOneShotFocus;
    window.showAdvancedCameraControls = showAdvancedCameraControls;
    window.loadAdvancedCameraControls = loadAdvancedCameraControls;
    window.loadCSICameraControls = loadCSICameraControls;
    window.stopRtspForConfig = stopRtspForConfig;
    window.renderCSIControls = renderCSIControls;
    window.renderCSIControlItem = renderCSIControlItem;
    window.setCSIControl = setCSIControl;
    window.setCSIArrayControl = setCSIArrayControl;
    window.resetCSIControls = resetCSIControls;
    window.renderAdvancedControls = renderAdvancedControls;
    window.renderControlInput = renderControlInput;
    window.setAdvancedControl = setAdvancedControl;
    window.showLiveAppliedIndicator = showLiveAppliedIndicator;
    window.restartRtspStream = restartRtspStream;
    window.resetAdvancedControls = resetAdvancedControls;
    window.loadCameraProfiles = loadCameraProfiles;
    window.renderCameraProfiles = renderCameraProfiles;
    window.toggleProfilesScheduler = toggleProfilesScheduler;
    window.showProfileSettings = showProfileSettings;
    window.closeProfileSettingsModal = closeProfileSettingsModal;
    window.showAddProfileModal = showAddProfileModal;
    window.editProfile = editProfile;
    window.closeProfileModal = closeProfileModal;
    window.saveProfile = saveProfile;
    window.captureProfileSettings = captureProfileSettings;
    window.ghostFixProfile = ghostFixProfile;
    window.captureCurrentSettings = captureCurrentSettings;
    window.applyProfile = applyProfile;
    window.deleteProfile = deleteProfile;
})();











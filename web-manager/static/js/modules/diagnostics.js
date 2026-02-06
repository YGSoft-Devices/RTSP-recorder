/**
 * RTSP Recorder Web Manager - Diagnostic functions
 * Version: 2.36.10
 */

(function () {
// Diagnostic Functions
// ============================================================================

/**
 * Run system diagnostic
 */
async function runDiagnostic() {
    try {
        showToast(I18n.t('diagnostics.run_in_progress', {}, 'Diagnostic running...'), 'info');
        
        const response = await fetch('/api/diagnostic');
        const data = await response.json();
        
        if (data.success) {
            displayDiagnostic(data.diagnostic);
            document.getElementById('diagnostic-results').style.display = 'block';
            showToast(I18n.t('diagnostics.run_done', {}, 'Diagnostic completed'), 'success');
        } else {
            showToast(I18n.t('diagnostics.run_error', {}, 'Diagnostic error'), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Display diagnostic results
 */
function displayDiagnostic(diag) {
    // Service section
    const serviceHtml = `
        <div class="diag-item">
            <span class="status-icon ${diag.service.active ? 'success' : 'error'}">
                <i class="fas fa-${diag.service.active ? 'check-circle' : 'times-circle'}"></i>
            </span>
            <span class="label">${I18n.t('diagnostics.service_status_label', {}, 'Service status')}:</span>
            <span class="value">${diag.service.status || I18n.t('diagnostics.unknown', {}, 'unknown')}</span>
        </div>
        <div class="diag-item">
            <span class="status-icon ${diag.service.script_exists ? 'success' : 'error'}">
                <i class="fas fa-${diag.service.script_exists ? 'check-circle' : 'times-circle'}"></i>
            </span>
            <span class="label">${I18n.t('diagnostics.rtsp_script_label', {}, 'RTSP script')}:</span>
            <span class="value">${diag.service.script_exists ? I18n.t('diagnostics.present', {}, 'Present') : I18n.t('diagnostics.missing', {}, 'Missing')} (${diag.service.script_path})</span>
        </div>
    `;
    document.getElementById('diag-service').innerHTML = serviceHtml;
    
    // GStreamer section
    const gstHtml = `
        <div class="diag-item">
            <span class="status-icon ${diag.gstreamer.installed ? 'success' : 'error'}">
                <i class="fas fa-${diag.gstreamer.installed ? 'check-circle' : 'times-circle'}"></i>
            </span>
            <span class="label">${I18n.t('diagnostics.gstreamer_label', {}, 'GStreamer')}:</span>
            <span class="value">${diag.gstreamer.installed ? diag.gstreamer.version : I18n.t('diagnostics.not_installed', {}, 'Not installed')}</span>
        </div>
        <div class="diag-item">
            <span class="status-icon ${diag.gstreamer.rtsp_plugin ? 'success' : 'error'}">
                <i class="fas fa-${diag.gstreamer.rtsp_plugin ? 'check-circle' : 'times-circle'}"></i>
            </span>
            <span class="label">${I18n.t('diagnostics.rtsp_plugin_label', {}, 'RTSP plugin')}:</span>
            <span class="value">${diag.gstreamer.rtsp_plugin ? I18n.t('diagnostics.installed', {}, 'Installed') : I18n.t('diagnostics.missing_plugin', {}, 'Missing (gst-rtsp-server)')}</span>
        </div>
    `;
    document.getElementById('diag-gstreamer').innerHTML = gstHtml;
    
    // Encoder section (H264 Hardware vs Software)
    if (diag.encoder) {
        const encoderType = diag.encoder.encoder_type || 'unknown';
        const isHardware = encoderType === 'hardware';
        const isSoftware = encoderType === 'software';
        const hasEncoder = isHardware || isSoftware;
        
        const encoderHtml = `
            <div class="diag-item">
                <span class="status-icon ${hasEncoder ? (isHardware ? 'success' : 'warning') : 'error'}">
                    <i class="fas fa-${hasEncoder ? (isHardware ? 'microchip' : 'microprocessor') : 'times-circle'}"></i>
                </span>
                <span class="label">${I18n.t('diagnostics.encoder_active_label', {}, 'Active encoder')}:</span>
                <span class="value">${diag.encoder.active_encoder || I18n.t('diagnostics.unknown', {}, 'unknown')}</span>
            </div>
            <div class="diag-item">
                <span class="status-icon ${isHardware ? 'success' : (isSoftware ? 'warning' : 'error')}">
                    <i class="fas fa-${isHardware ? 'bolt' : (isSoftware ? 'cog' : 'times-circle')}"></i>
                </span>
                <span class="label">${I18n.t('diagnostics.encoder_type_label', {}, 'Type')}:</span>
                <span class="value encoder-type-${encoderType}">${
                    isHardware ? I18n.t('diagnostics.encoder_type_hw', {}, 'HARDWARE (GPU VideoCore) - low CPU') : 
                    (isSoftware ? I18n.t('diagnostics.encoder_type_sw', {}, 'SOFTWARE (x264) - high CPU') : I18n.t('diagnostics.none', {}, 'None'))
                }</span>
            </div>
            <div class="diag-item">
                <span class="status-icon ${diag.encoder.hw_available ? 'success' : 'warning'}">
                    <i class="fas fa-${diag.encoder.hw_available ? 'check-circle' : 'exclamation-triangle'}"></i>
                </span>
                <span class="label">${I18n.t('diagnostics.encoder_hw_available_label', {}, 'HW available')}:</span>
                <span class="value">${diag.encoder.hw_available ? I18n.t('diagnostics.yes_hw', {}, 'Yes (v4l2h264enc)') : I18n.t('diagnostics.no', {}, 'No')}</span>
            </div>
            ${!diag.encoder.hw_available ? `
            <div class="diag-output" style="font-size: 0.85em; color: var(--text-muted);">
                Plugin: ${diag.encoder.hw_plugin_exists ? '✓' : '✗'} | 
                /dev/video11: ${diag.encoder.hw_device_exists ? '✓' : '✗'} | 
                bcm2835_codec: ${diag.encoder.hw_module_loaded ? '✓' : '✗'}
            </div>
            ` : ''}
        `;
        
        // Check if encoder section exists, if not create it
        let encoderSection = document.getElementById('diag-encoder');
        if (!encoderSection) {
            // Insert after gstreamer section
            const gstSection = document.getElementById('diag-gstreamer');
            if (gstSection && gstSection.parentElement) {
                const newSection = document.createElement('div');
                newSection.innerHTML = `
                    <h5><i class="fas fa-microchip"></i> ${I18n.t('diagnostics.encoder_h264_title', {}, 'H264 Encoder')}</h5>
                    <div id="diag-encoder"></div>
                `;
                gstSection.parentElement.insertBefore(newSection, gstSection.nextSibling);
                encoderSection = document.getElementById('diag-encoder');
            }
        }
        if (encoderSection) {
            encoderSection.innerHTML = encoderHtml;
        }
    }
    
    // Camera section
    let cameraHtml = `
        <div class="diag-item">
            <span class="status-icon ${diag.camera.devices_found ? 'success' : 'warning'}">
                <i class="fas fa-${diag.camera.devices_found ? 'check-circle' : 'exclamation-triangle'}"></i>
            </span>
            <span class="label">${I18n.t('diagnostics.camera_v4l2_label', {}, 'V4L2 camera')}:</span>
            <span class="value">${diag.camera.devices_found ? I18n.t('diagnostics.detected', {}, 'Detected') : I18n.t('diagnostics.not_detected', {}, 'Not detected')}</span>
        </div>
    `;
    if (diag.camera.v4l2_output) {
        cameraHtml += `<div class="diag-output">${escapeHtml(diag.camera.v4l2_output)}</div>`;
    }
    if (diag.camera.csi_detected !== undefined) {
        cameraHtml += `
            <div class="diag-item" style="margin-top: 10px;">
                <span class="status-icon ${diag.camera.csi_detected ? 'success' : 'warning'}">
                    <i class="fas fa-${diag.camera.csi_detected ? 'check-circle' : 'exclamation-triangle'}"></i>
                </span>
                <span class="label">${I18n.t('diagnostics.camera_csi_label', {}, 'CSI camera')}:</span>
                <span class="value">${diag.camera.csi_detected ? I18n.t('diagnostics.detected', {}, 'Detected') : I18n.t('diagnostics.not_detected', {}, 'Not detected')}</span>
            </div>
        `;
        if (diag.camera.libcamera_output) {
            cameraHtml += `<div class="diag-output">${escapeHtml(diag.camera.libcamera_output)}</div>`;
        }
    }
    document.getElementById('diag-camera').innerHTML = cameraHtml;
    
    // Audio section
    let audioHtml = `
        <div class="diag-item">
            <span class="status-icon ${diag.audio.devices_found ? 'success' : 'warning'}">
                <i class="fas fa-${diag.audio.devices_found ? 'check-circle' : 'exclamation-triangle'}"></i>
            </span>
            <span class="label">${I18n.t('diagnostics.microphone_label', {}, 'Microphone')}:</span>
            <span class="value">${diag.audio.devices_found ? I18n.t('diagnostics.detected', {}, 'Detected') : I18n.t('diagnostics.not_detected', {}, 'Not detected')}</span>
        </div>
    `;
    if (diag.audio.arecord_output) {
        audioHtml += `<div class="diag-output">${escapeHtml(diag.audio.arecord_output)}</div>`;
    }
    document.getElementById('diag-audio').innerHTML = audioHtml;
    
    // Network section
    const networkHtml = `
        <div class="diag-item">
            <span class="status-icon ${diag.network.rtsp_port_in_use ? 'success' : 'warning'}">
                <i class="fas fa-${diag.network.rtsp_port_in_use ? 'check-circle' : 'exclamation-triangle'}"></i>
            </span>
            <span class="label">${I18n.t('diagnostics.rtsp_port_label', {}, 'RTSP port')}:</span>
            <span class="value">${diag.network.rtsp_port_in_use ? I18n.t('diagnostics.listening', {}, 'Listening') : I18n.t('diagnostics.inactive', {}, 'Inactive')}</span>
        </div>
    `;
    document.getElementById('diag-network').innerHTML = networkHtml;
    
    // Errors section
    if (diag.errors && diag.errors.length > 0) {
        document.getElementById('diag-errors-section').style.display = 'block';
        const errorsHtml = diag.errors.map(err => `
            <div class="diag-error-item">
                <i class="fas fa-exclamation-circle"></i>
                <span>${escapeHtml(err)}</span>
            </div>
        `).join('');
        document.getElementById('diag-errors').innerHTML = errorsHtml;
    } else {
        document.getElementById('diag-errors-section').style.display = 'none';
    }
}

// ============================================================================
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
        <p>${I18n.t('diagnostics.preview_connecting_title', {}, 'Connecting...')}</p>
        <small>${I18n.t('diagnostics.preview_connecting_subtitle', {}, 'Initializing video stream')}</small>
    `;
    statusText.innerHTML = `<i class="fas fa-circle preview-status-dot" style="color: var(--warning-color);"></i> ${I18n.t('diagnostics.preview_status_connecting', {}, 'Connecting...')}`;
    
    // Set stream source
    streamImg.src = streamUrl;
    
    // Handle stream load success
    streamImg.onload = function() {
        placeholder.style.display = 'none';
        streamImg.style.display = 'block';
        btnStart.style.display = 'none';
        btnStop.style.display = 'inline-flex';
        statusText.innerHTML = `<i class="fas fa-circle preview-status-dot active"></i> ${I18n.t('diagnostics.preview_status_streaming', {}, 'Streaming...')}`;
        previewActive = true;
        showToast(I18n.t('diagnostics.preview_started_toast', {}, 'Preview started'), 'success');
    };
    
    // Handle stream errors
    streamImg.onerror = function() {
        if (!previewActive) {
            placeholder.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <p>${I18n.t('diagnostics.preview_error_title', {}, 'Connection error')}</p>
                <small>${I18n.t('diagnostics.preview_error_subtitle', {}, 'Unable to establish video stream')}</small>
            `;
            statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${I18n.t('diagnostics.preview_status_error', {}, 'Error')}`;
            showToast(I18n.t('diagnostics.preview_error_toast', {}, 'Video stream connection error'), 'error');
        } else {
            stopPreview();
            showToast(I18n.t('diagnostics.preview_interrupted_toast', {}, 'Video stream interrupted'), 'warning');
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
    statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${I18n.t('diagnostics.preview_status_inactive', {}, 'Inactive')}`;
    
    showToast(I18n.t('diagnostics.preview_stopped_toast', {}, 'Preview stopped'), 'info');
}

/**
 * Take a snapshot from the camera
 */
async function takeSnapshot() {
    const quality = document.getElementById('preview-quality').value;
    const [width, height] = quality.split('x');
    
    try {
        showToast(I18n.t('diagnostics.snapshot_in_progress', {}, 'Capturing...'), 'info');
        
        const response = await fetch(`/api/video/preview/snapshot?width=${width}&height=${height}`);
        
        if (!response.ok) {
            throw new Error(I18n.t('diagnostics.snapshot_failed', {}, 'Failed to capture snapshot'));
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
        
        showToast(I18n.t('diagnostics.snapshot_downloaded_toast', {}, 'Snapshot downloaded'), 'success');
    } catch (error) {
        console.error('Snapshot error:', error);
        showToast(I18n.t('diagnostics.snapshot_error_toast', {}, 'Snapshot error'), 'error');
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
                <p>${I18n.t('diagnostics.preview_unavailable_title', {}, 'Camera unavailable')}</p>
                <small>${I18n.t('diagnostics.preview_unavailable_subtitle', {}, 'Check that the camera is connected')}</small>
            `;
            statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${I18n.t('diagnostics.preview_status_unavailable', {}, 'Unavailable')}`;
        } else {
            const sourceLabel = data.preview_source === 'rtsp'
                ? I18n.t('diagnostics.preview_source_rtsp', {}, 'via RTSP')
                : I18n.t('diagnostics.preview_source_direct', {}, 'direct');
            statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> ${I18n.t('diagnostics.preview_ready', {}, 'Ready')} (${sourceLabel})`;
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
                autofocusStatus.textContent = af.autofocus_enabled
                    ? I18n.t('diagnostics.autofocus_enabled', {}, 'Enabled')
                    : I18n.t('diagnostics.autofocus_disabled', {}, 'Disabled');
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
                autofocusStatus.textContent = I18n.t('diagnostics.autofocus_unavailable', {}, 'Unavailable');
                autofocusStatus.className = 'control-status status-unavailable';
                manualFocusGroup.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading camera controls:', error);
        document.getElementById('autofocus-status').textContent = I18n.t('diagnostics.autofocus_error', {}, 'Error');
    }
}

/**
 * Set camera autofocus state
 */
async function setCameraAutofocus(enabled) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(
            enabled
                ? I18n.t('diagnostics.autofocus_enabling', {}, 'Enabling autofocus...')
                : I18n.t('diagnostics.autofocus_disabling', {}, 'Disabling autofocus...'),
            'info'
        );
        
        const response = await fetch('/api/camera/autofocus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const autofocusStatus = document.getElementById('autofocus-status');
            const manualFocusGroup = document.getElementById('manual-focus-group');
            
            autofocusStatus.textContent = enabled
                ? I18n.t('diagnostics.autofocus_enabled', {}, 'Enabled')
                : I18n.t('diagnostics.autofocus_disabled', {}, 'Disabled');
            autofocusStatus.className = 'control-status ' + (enabled ? 'status-on' : 'status-off');
            
            // Show manual focus slider when autofocus is disabled
            if (manualFocusGroup) {
                manualFocusGroup.style.display = enabled ? 'none' : 'block';
            }
            
            showToast(
                enabled
                    ? I18n.t('diagnostics.autofocus_on_toast', {}, 'Autofocus enabled')
                    : I18n.t('diagnostics.autofocus_off_toast', {}, 'Autofocus disabled - adjust focus manually'),
                'success'
            );
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
            // Revert checkbox
            document.getElementById('camera_autofocus').checked = !enabled;
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
            showToast(I18n.t('diagnostics.focus_error', { error: data.message }, `Focus error: ${data.message}`), 'error');
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
        
        showToast(I18n.t('diagnostics.oneshot_in_progress', {}, 'Focusing...'), 'info');
        
        const response = await fetch('/api/camera/oneshot-focus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('diagnostics.oneshot_done', {}, 'Focus complete and locked'), 'success');
            // Update autofocus checkbox to show it's now off (locked)
            const checkbox = document.getElementById('camera_autofocus');
            if (checkbox) {
                checkbox.checked = false;
            }
            const status = document.getElementById('autofocus-status');
            if (status) {
                status.textContent = I18n.t('diagnostics.autofocus_locked', {}, 'Locked');
                status.className = 'control-status status-off';
            }
            // Show manual focus slider
            const manualGroup = document.getElementById('manual-focus-group');
            if (manualGroup) {
                manualGroup.style.display = 'block';
            }
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
        
        container.innerHTML = `<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> ${I18n.t('diagnostics.controls_loading', {}, 'Loading controls...')}</p>`;
        
        const response = await fetch(`/api/camera/all-controls?device=${encodeURIComponent(device)}`);
        const data = await response.json();
        
        if (!data.success) {
            container.innerHTML = `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${data.error || I18n.t('diagnostics.load_error', {}, 'Load error')}</p>`;
            return;
        }
        
        advancedControlsData = data;
        renderAdvancedControls(data);
        
    } catch (error) {
        console.error('Error loading advanced controls:', error);
        document.getElementById('advanced-camera-controls').innerHTML = 
            `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`)}</p>`;
    }
}

/**
 * Load CSI camera controls via Picamera2
 */
async function loadCSICameraControls() {
    const container = document.getElementById('advanced-camera-controls');
    container.innerHTML = `<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> ${I18n.t('diagnostics.csi_controls_loading', {}, 'Loading Picamera2 controls...')}</p>`;
    
    try {
        // Check if CSI/Picamera2 is available
        const availResponse = await fetch('/api/camera/csi/available');
        const availData = await availResponse.json();
        
        if (!availData.available) {
            container.innerHTML = `
                <div class="info-box warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    <div>
                        <strong>${I18n.t('diagnostics.csi_not_installed_title', {}, 'Picamera2 not installed')}</strong>
                        <p>${I18n.t('diagnostics.csi_not_installed_body', {}, 'To control CSI camera settings, install Picamera2:')}</p>
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
                            <strong>${I18n.t('diagnostics.csi_starting_title', {}, 'CSI server starting...')}</strong>
                            <p>${I18n.t('diagnostics.csi_starting_body', {}, 'The CSI RTSP server is starting. Auto-reload in 3 seconds.')}</p>
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
                            <strong>${I18n.t('diagnostics.csi_busy_title', {}, 'Camera in use')}</strong>
                            <p>${I18n.t('diagnostics.csi_busy_body', {}, 'The CSI camera is currently used by the RTSP stream.')}</p>
                            <p>${I18n.t('diagnostics.csi_busy_steps_intro', {}, 'To change image settings:')}</p>
                            <ol style="margin: 10px 0; padding-left: 20px;">
                                <li>${I18n.t('diagnostics.csi_busy_step_stop', {}, 'Stop the RTSP stream (button below)')}</li>
                                <li>${I18n.t('diagnostics.csi_busy_step_change', {}, 'Change settings')}</li>
                                <li>${I18n.t('diagnostics.csi_busy_step_restart', {}, 'Restart the stream')}</li>
                            </ol>
                            <button type="button" class="btn btn-warning btn-sm" onclick="stopRtspForConfig()">
                                <i class="fas fa-stop"></i> ${I18n.t('diagnostics.csi_busy_stop_button', {}, 'Stop stream temporarily')}
                            </button>
                        </div>
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="info-box warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        <div>
                            <strong>${I18n.t('diagnostics.csi_load_error_title', {}, 'Load error')}</strong>
                            <p>${data.error || I18n.t('diagnostics.unknown_error', {}, 'Unknown error')}</p>
                            <button type="button" class="btn btn-sm btn-secondary" onclick="loadCSICameraControls()">
                                <i class="fas fa-redo"></i> ${I18n.t('diagnostics.retry', {}, 'Retry')}
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
        container.innerHTML = `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`)}</p>`;
    }
}

/**
 * Stop RTSP stream temporarily to configure CSI camera
 */
async function stopRtspForConfig() {
    if (!confirm(I18n.t('diagnostics.confirm_stop_rtsp', {}, 'Stop the RTSP stream to configure the camera?\\nConnected clients will be disconnected.'))) return;
    
    try {
        const response = await fetch('/api/service/rpi-av-rtsp-recorder/stop', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('diagnostics.rtsp_stopped_loading_controls', {}, 'RTSP stream stopped. Loading controls...'), 'success');
            // Wait a bit for camera to be released
            setTimeout(() => loadCSICameraControls(), 2000);
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Render CSI camera controls (Picamera2)
 */
function renderCSIControls(data) {
    const container = document.getElementById('advanced-camera-controls');
    const grouped = data.grouped || {};
    
    const categoryLabels = {
        'exposure': { icon: 'fa-sun', label: I18n.t('diagnostics.csi_category_exposure', {}, 'Exposure') },
        'color': { icon: 'fa-palette', label: I18n.t('diagnostics.csi_category_color', {}, 'Color / White balance') },
        'focus': { icon: 'fa-crosshairs', label: I18n.t('diagnostics.csi_category_focus', {}, 'Focus') },
        'noise': { icon: 'fa-volume-off', label: I18n.t('diagnostics.csi_category_noise', {}, 'Noise reduction') },
        'auto': { icon: 'fa-magic', label: I18n.t('diagnostics.csi_category_auto', {}, 'Automatic') },
        'other': { icon: 'fa-sliders-h', label: I18n.t('diagnostics.csi_category_other', {}, 'Other') }
    };
    
    let html = `
        <div class="live-apply-notice csi-notice">
            <i class="fas fa-microchip"></i>
            <span>${I18n.t('diagnostics.csi_controls_title', {}, 'CSI controls via Picamera2')}</span>
            <span class="live-apply-indicator">
                <i class="fas fa-save"></i> ${I18n.t('diagnostics.csi_controls_saved', {}, 'Values are saved')}
            </span>
        </div>
    `;
    
    // Camera info if available
    if (data.camera_info) {
        html += `
            <div class="camera-info-box">
                <strong><i class="fas fa-camera"></i> ${data.camera_info.model || I18n.t('diagnostics.csi_camera_label', {}, 'CSI Camera')}</strong>
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
                <i class="fas fa-sync"></i> ${I18n.t('diagnostics.refresh', {}, 'Refresh')}
            </button>
            <button type="button" class="btn btn-warning" onclick="resetCSIControls()">
                <i class="fas fa-undo"></i> ${I18n.t('diagnostics.reset', {}, 'Reset')}
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
    'ExposureTime': { label: I18n.t('diagnostics.csi_ctrl_exposure_time_label', {}, 'Exposure time'), desc: I18n.t('diagnostics.csi_ctrl_exposure_time_desc', {}, 'Exposure duration in µs'), unit: 'µs' },
    'AnalogueGain': { label: I18n.t('diagnostics.csi_ctrl_analogue_gain_label', {}, 'Analogue gain'), desc: I18n.t('diagnostics.csi_ctrl_analogue_gain_desc', {}, 'Sensor signal amplification') },
    'ExposureValue': { label: I18n.t('diagnostics.csi_ctrl_exposure_value_label', {}, 'Exposure compensation (EV)'), desc: I18n.t('diagnostics.csi_ctrl_exposure_value_desc', {}, 'Brightness adjustment (-8 to +8)') },
    'AeExposureMode': { label: I18n.t('diagnostics.csi_ctrl_ae_exposure_mode_label', {}, 'Exposure mode'), desc: I18n.t('diagnostics.csi_ctrl_ae_exposure_mode_desc', {}, '0=Normal, 1=Short, 2=Long, 3=Custom') },
    'ExposureTimeMode': { label: I18n.t('diagnostics.csi_ctrl_exposure_time_mode_label', {}, 'Exposure time mode'), desc: I18n.t('diagnostics.csi_ctrl_exposure_time_mode_desc', {}, '0=Auto, 1=Manual') },
    'AnalogueGainMode': { label: I18n.t('diagnostics.csi_ctrl_analogue_gain_mode_label', {}, 'Gain mode'), desc: I18n.t('diagnostics.csi_ctrl_analogue_gain_mode_desc', {}, '0=Auto, 1=Manual') },
    'ColourGains': { label: I18n.t('diagnostics.csi_ctrl_colour_gains_label', {}, 'Color gains (R/B)'), desc: I18n.t('diagnostics.csi_ctrl_colour_gains_desc', {}, 'Manual red/blue gains') },
    
    // Color
    'Brightness': { label: I18n.t('diagnostics.csi_ctrl_brightness_label', {}, 'Brightness'), desc: I18n.t('diagnostics.csi_ctrl_brightness_desc', {}, 'Brightness adjustment (-1 to +1)') },
    'Contrast': { label: I18n.t('diagnostics.csi_ctrl_contrast_label', {}, 'Contrast'), desc: I18n.t('diagnostics.csi_ctrl_contrast_desc', {}, 'Contrast ratio') },
    'Saturation': { label: I18n.t('diagnostics.csi_ctrl_saturation_label', {}, 'Saturation'), desc: I18n.t('diagnostics.csi_ctrl_saturation_desc', {}, 'Color intensity') },
    'Sharpness': { label: I18n.t('diagnostics.csi_ctrl_sharpness_label', {}, 'Sharpness'), desc: I18n.t('diagnostics.csi_ctrl_sharpness_desc', {}, 'Image sharpness level') },
    'ColourCorrectionMatrix': { label: I18n.t('diagnostics.csi_ctrl_colour_correction_matrix_label', {}, 'Color correction matrix'), desc: I18n.t('diagnostics.csi_ctrl_colour_correction_matrix_desc', {}, 'Color correction') },
    'ColourTemperature': { label: I18n.t('diagnostics.csi_ctrl_colour_temperature_label', {}, 'Color temperature'), desc: I18n.t('diagnostics.csi_ctrl_colour_temperature_desc', {}, 'In Kelvin (2000K-10000K)') },
    
    // Auto
    'AeEnable': { label: I18n.t('diagnostics.csi_ctrl_ae_enable_label', {}, 'Auto exposure'), desc: I18n.t('diagnostics.csi_ctrl_ae_enable_desc', {}, 'Auto exposure enabled') },
    'AwbEnable': { label: I18n.t('diagnostics.csi_ctrl_awb_enable_label', {}, 'Auto white balance'), desc: I18n.t('diagnostics.csi_ctrl_awb_enable_desc', {}, 'AWB enabled') },
    'AwbMode': { label: I18n.t('diagnostics.csi_ctrl_awb_mode_label', {}, 'AWB mode'), desc: I18n.t('diagnostics.csi_ctrl_awb_mode_desc', {}, '0=Auto, 1=Tungsten, 2=Fluorescent, 3=Indoor, 4=Sun, 5=Cloudy, 6=Custom') },
    'AeMeteringMode': { label: I18n.t('diagnostics.csi_ctrl_ae_metering_mode_label', {}, 'AE metering mode'), desc: I18n.t('diagnostics.csi_ctrl_ae_metering_mode_desc', {}, '0=Center, 1=Spot, 2=Matrix, 3=Custom') },
    'AeConstraintMode': { label: I18n.t('diagnostics.csi_ctrl_ae_constraint_mode_label', {}, 'AE constraint'), desc: I18n.t('diagnostics.csi_ctrl_ae_constraint_mode_desc', {}, '0=Normal, 1=Highlights, 2=Shadows, 3=Custom') },
    'AeFlickerMode': { label: I18n.t('diagnostics.csi_ctrl_ae_flicker_mode_label', {}, 'Anti-flicker'), desc: I18n.t('diagnostics.csi_ctrl_ae_flicker_mode_desc', {}, '0=Off, 1=Manual') },
    'AeFlickerPeriod': { label: I18n.t('diagnostics.csi_ctrl_ae_flicker_period_label', {}, 'Flicker period'), desc: I18n.t('diagnostics.csi_ctrl_ae_flicker_period_desc', {}, 'For 50Hz=10000µs, 60Hz=8333µs') },
    
    // Noise
    'NoiseReductionMode': { label: I18n.t('diagnostics.csi_ctrl_noise_reduction_mode_label', {}, 'Noise reduction'), desc: I18n.t('diagnostics.csi_ctrl_noise_reduction_mode_desc', {}, '0=Off, 1=Fast, 2=High quality, 3=Minimal, 4=ZSL') },
    
    // Other
    'FrameDurationLimits': { label: I18n.t('diagnostics.csi_ctrl_frame_duration_limits_label', {}, 'Frame duration'), desc: I18n.t('diagnostics.csi_ctrl_frame_duration_limits_desc', {}, 'Min/Max frame duration in µs') },
    'HdrMode': { label: I18n.t('diagnostics.csi_ctrl_hdr_mode_label', {}, 'HDR mode'), desc: I18n.t('diagnostics.csi_ctrl_hdr_mode_desc', {}, '0=Off, 1=Single, 2=Multi, 3=Night, 4=Custom') },
    'ScalerCrop': { label: I18n.t('diagnostics.csi_ctrl_scaler_crop_label', {}, 'Crop region'), desc: I18n.t('diagnostics.csi_ctrl_scaler_crop_desc', {}, 'Crop region') },
    'SyncMode': { label: I18n.t('diagnostics.csi_ctrl_sync_mode_label', {}, 'Sync mode'), desc: I18n.t('diagnostics.csi_ctrl_sync_mode_desc', {}, '0=Off, 1=Server, 2=Client') },
    'SyncFrames': { label: I18n.t('diagnostics.csi_ctrl_sync_frames_label', {}, 'Sync frames'), desc: I18n.t('diagnostics.csi_ctrl_sync_frames_desc', {}, 'Frames to synchronize') }
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
            showToast(`${name} = ${value}`, 'success');
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
            showToast(`${name} = [${values.join(', ')}]`, 'success');
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Reset CSI controls to defaults
 */
async function resetCSIControls() {
    if (!confirm(I18n.t('diagnostics.csi_reset_confirm', {}, 'Reset all CSI settings to default values?'))) return;
    
    try {
        const response = await fetch('/api/camera/csi/tuning/reset', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('diagnostics.csi_reset_done', {}, 'CSI settings reset'), 'success');
            loadCSICameraControls();
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Render advanced camera controls by category
 */
function renderAdvancedControls(data) {
    const container = document.getElementById('advanced-camera-controls');
    const grouped = data.grouped || {};
    
    const categoryLabels = {
        'focus': { icon: 'fa-crosshairs', label: I18n.t('diagnostics.adv_category_focus', {}, 'Focus / Zoom') },
        'exposure': { icon: 'fa-sun', label: I18n.t('diagnostics.adv_category_exposure', {}, 'Exposure') },
        'white_balance': { icon: 'fa-temperature-half', label: I18n.t('diagnostics.adv_category_white_balance', {}, 'White balance') },
        'color': { icon: 'fa-palette', label: I18n.t('diagnostics.adv_category_color', {}, 'Color') },
        'power_line': { icon: 'fa-bolt', label: I18n.t('diagnostics.adv_category_power_line', {}, 'Anti-flicker') },
        'other': { icon: 'fa-sliders-h', label: I18n.t('diagnostics.adv_category_other', {}, 'Other') }
    };
    
    // Live indicator at the top
    let html = `
        <div class="live-apply-notice">
            <i class="fas fa-broadcast-tower"></i>
            <span>${I18n.t('diagnostics.adv_live_apply_notice', {}, 'Changes are applied in real time to the video stream')}</span>
            <span id="live-apply-indicator" class="live-apply-indicator">
                <i class="fas fa-check-circle"></i> ${I18n.t('diagnostics.adv_applied', {}, 'Applied')}
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
        html = `<p class="info-text"><i class="fas fa-info-circle"></i> ${I18n.t('diagnostics.adv_no_controls', {}, 'No controls available for this camera')}</p>`;
    }
    
    container.innerHTML = html;
}

/**
 * Check if a V4L2 default value is valid (not a system flag)
 * V4L2 uses special values like 57343 (0xDFFF), -8193 (0xE001) when no real default is defined
 */
function isValidDefaultValue(defaultVal, min, max) {
    if (defaultVal === null || defaultVal === undefined) return false;
    // Known invalid V4L2 default values
    const invalidDefaults = [57343, -8193, 32767, -32768, 65535, -1];
    if (invalidDefaults.includes(defaultVal)) return false;
    // If default is outside the control range, it's likely invalid
    if (min !== null && max !== null) {
        if (defaultVal < min || defaultVal > max) return false;
    }
    return true;
}

/**
 * Render a single control input based on its type
 */
function renderControlInput(ctrl) {
    const { name, type, display_name, value, min, max, step, default: defaultVal, menu_items } = ctrl;
    
    // Validate the default value
    const validDefault = isValidDefaultValue(defaultVal, min, max);
    const displayDefault = validDefault ? defaultVal : null;
    
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
                <div class="slider-container">
                    <div class="range-control-enhanced">
                        <input type="range" id="ctrl_${name}" 
                               min="${min || 0}" max="${max || 255}" step="${step || 1}"
                               value="${value || 0}"
                               oninput="updateSliderDisplay('${name}', this.value)"
                               onchange="setAdvancedControl('${name}', parseInt(this.value))">
                        <span class="range-value-box" id="val_${name}">${value || 0}</span>
                    </div>
                    <div class="range-limits">
                        <span class="range-min">${min || 0}</span>
                        <span class="range-max">${max || 255}</span>
                    </div>
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
    
    // Build default hint if valid
    const defaultHint = displayDefault !== null 
        ? `<small class="default-hint">${I18n.t('diagnostics.adv_default_hint', { value: displayDefault }, `Default: ${displayDefault}`)}</small>` 
        : '';
    
    return `
        <div class="control-item" data-control="${name}">
            <label for="ctrl_${name}" title="${name}">
                ${display_name}
                ${defaultHint}
            </label>
            ${inputHtml}
        </div>
    `;
}

/**
 * Update slider value display in real-time
 */
function updateSliderDisplay(name, value) {
    const valDisplay = document.getElementById(`val_${name}`);
    if (valDisplay) {
        valDisplay.textContent = value;
    }
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
            showToast(I18n.t('diagnostics.control_error_with_name', { name, error: data.message }, `Error ${name}: ${data.message}`), 'error');
            if (controlItem) {
                controlItem.classList.add('control-error');
                setTimeout(() => controlItem.classList.remove('control-error'), 1000);
            }
        }
    } catch (error) {
        console.error(`Error setting control ${name}:`, error);
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
    if (!confirm(I18n.t('diagnostics.confirm_restart_rtsp', {}, 'Restart the RTSP stream? Connected clients will be disconnected.'))) {
        return;
    }
    
    try {
        showToast(I18n.t('diagnostics.rtsp_restarting', {}, 'Restarting stream...'), 'info');
        
        const response = await fetch('/api/service/restart', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('diagnostics.rtsp_restarted', {}, 'Stream restarted - settings are now active'), 'success');
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
        showToast(I18n.t('diagnostics.adv_no_defaults', {}, 'No default values available'), 'warning');
        return;
    }
    
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(I18n.t('diagnostics.adv_reset_in_progress', {}, 'Resetting...'), 'info');
        
        const response = await fetch('/api/camera/controls/set-multiple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, controls: toReset })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('diagnostics.adv_reset_done', {}, 'Controls reset'), 'success');
            loadAdvancedCameraControls();
        } else {
            showToast(I18n.t('diagnostics.adv_reset_partial', { count: data.errors }, `Errors: ${data.errors} control(s)`), 'warning');
            loadAdvancedCameraControls();
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
        container.innerHTML = `<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> ${I18n.t('diagnostics.loading', {}, 'Loading...')}</p>`;
        
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
                schedulerStatus.textContent = I18n.t('diagnostics.scheduler_active_profile', { profile: activeProfile }, `Active (profile: ${activeProfile})`);
                schedulerStatus.className = 'control-status status-on';
            } else if (data.scheduler_enabled) {
                schedulerStatus.textContent = I18n.t('diagnostics.scheduler_pending', {}, 'Pending (out of range)');
                schedulerStatus.className = 'control-status status-warning';
            } else {
                schedulerStatus.textContent = I18n.t('diagnostics.scheduler_disabled', {}, 'Disabled');
                schedulerStatus.className = 'control-status status-off';
            }
        }
        
        renderCameraProfiles(data.profiles, data.current_profile, data.scheduler_active_profile || data.active_profile);
        
    } catch (error) {
        console.error('Error loading profiles:', error);
        document.getElementById('camera-profiles-list').innerHTML = 
            `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`)}</p>`;
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
                <i class="fas fa-info-circle"></i> ${I18n.t('diagnostics.profiles_empty_title', {}, 'No profile configured.')}
                ${I18n.t('diagnostics.profiles_empty_body', {}, 'Create profiles to automate day/night settings.')}
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
                        ${isApplied ? `<span class="badge badge-success">${I18n.t('diagnostics.badge_applied', {}, 'Applied')}</span>` : ''}
                        ${isScheduled && !isApplied ? `<span class="badge badge-info">${I18n.t('diagnostics.badge_scheduled', {}, 'Scheduled')}</span>` : ''}
                        ${!profile.enabled ? `<span class="badge badge-muted">${I18n.t('diagnostics.badge_disabled', {}, 'Disabled')}</span>` : ''}
                    </h5>
                    <div class="profile-actions">
                        <button class="btn btn-sm btn-info" onclick="captureProfileSettings('${id}')" title="${I18n.t('diagnostics.profile_capture_title', {}, 'Capture current settings')}">
                            <i class="fas fa-camera"></i>
                        </button>
                        <button class="btn btn-sm btn-success" onclick="ghostFixProfile('${id}')" title="${I18n.t('diagnostics.profile_ghostfix_title', {}, 'Ghost-fix (disable AE/AWB + mid brightness)')}">
                            <i class="fas fa-magic"></i> ${I18n.t('diagnostics.profile_ghostfix_label', {}, 'ghost-fix')}
                        </button>
                        <button class="btn btn-sm btn-warning" onclick="showProfileSettings('${id}')" title="${I18n.t('diagnostics.profile_show_title', {}, 'Show saved settings')}">
                            <i class="fas fa-cogs"></i>
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="editProfile('${id}')" title="${I18n.t('diagnostics.profile_edit_title', {}, 'Edit')}">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="applyProfile('${id}')" title="${I18n.t('diagnostics.profile_apply_now_title', {}, 'Apply now')}">
                            <i class="fas fa-play"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteProfile('${id}')" title="${I18n.t('diagnostics.profile_delete_title', {}, 'Delete')}">
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
                            : I18n.t('diagnostics.profile_no_schedule', {}, 'No schedule')}
                    </div>
                    <div class="profile-controls-count">
                        <i class="fas fa-sliders-h"></i> ${I18n.t('diagnostics.profile_controls_count', { count: controlsCount }, `${controlsCount} control(s)`)}
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
            throw new Error(I18n.t('diagnostics.config_update_failed', {}, 'Failed to update config'));
        }
        
        // Then start/stop scheduler
        const action = enabled ? 'start' : 'stop';
        const response = await fetch(`/api/camera/profiles/scheduler/${action}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        showToast(
            enabled ? I18n.t('diagnostics.scheduler_enabled_toast', {}, 'Scheduler enabled') : I18n.t('diagnostics.scheduler_disabled_toast', {}, 'Scheduler disabled'),
            data.success ? 'success' : 'warning'
        );
        
        // Refresh status
        setTimeout(loadCameraProfiles, 500);
        
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Show profile settings in a modal
 */
function showProfileSettings(profileId) {
    const profile = cameraProfiles[profileId];
    if (!profile) {
        showToast(I18n.t('diagnostics.profile_not_found', {}, 'Profile not found'), 'error');
        return;
    }
    
    const controls = profile.controls || {};
    const modal = document.getElementById('profile-settings-modal');
    if (!modal) return;

    document.getElementById('profile-settings-title').textContent =
        I18n.t('diagnostics.profile_settings_title', { name: profile.display_name || profileId }, `Settings: ${profile.display_name || profileId}`);

    const schedule = profile.schedule || {};
    const scheduleText = (schedule.start && schedule.end)
        ? `${schedule.start} - ${schedule.end}`
        : I18n.t('diagnostics.profile_no_schedule', {}, 'No schedule');
    const controlsCount = Object.keys(controls).length;
    const meta = `
        <div><i class="fas fa-clock"></i> ${scheduleText}</div>
        <div><i class="fas fa-sliders-h"></i> ${I18n.t('diagnostics.profile_controls_count', { count: controlsCount }, `${controlsCount} control(s)`)} </div>
    `;
    const metaEl = document.getElementById('profile-settings-meta');
    if (metaEl) metaEl.innerHTML = meta;

    const contentEl = document.getElementById('profile-settings-content');
    if (!contentEl) return;

    if (controlsCount === 0) {
        contentEl.innerHTML = `<p class="info-text">${I18n.t('diagnostics.profile_no_controls', {}, 'No saved settings in this profile.')}</p>`;
    } else {
        const rows = Object.entries(controls).map(([ctrlName, value]) => {
            let displayValue = value;
            if (Array.isArray(value)) {
                displayValue = '[' + value.join(', ') + ']';
            } else if (value === null || value === undefined) {
                displayValue = I18n.t('diagnostics.value_not_available', {}, 'N/A');
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
                        <th>${I18n.t('diagnostics.profile_table_param', {}, 'Parameter')}</th>
                        <th>${I18n.t('diagnostics.profile_table_value', {}, 'Value')}</th>
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
    document.getElementById('profile-modal-title').textContent = I18n.t('diagnostics.profile_new_title', {}, 'New profile');
    document.getElementById('profile-id').value = '';
    document.getElementById('profile-name').value = '';
    document.getElementById('profile-description').value = '';
    document.getElementById('profile-start').value = '07:00';
    document.getElementById('profile-end').value = '19:00';
    document.getElementById('profile-enabled').checked = true;
    document.getElementById('profile-controls-count').textContent = I18n.t('diagnostics.profile_controls_count_zero', {}, '0 saved controls');
    
    document.getElementById('profile-modal').style.display = 'flex';
}

/**
 * Edit an existing profile
 */
function editProfile(profileId) {
    const profile = cameraProfiles[profileId];
    if (!profile) return;
    
    editingProfileId = profileId;
    document.getElementById('profile-modal-title').textContent = I18n.t('diagnostics.profile_edit_title_text', {}, 'Edit profile');
    document.getElementById('profile-id').value = profileId;
    document.getElementById('profile-name').value = profile.display_name || profile.name || profileId;
    document.getElementById('profile-description').value = profile.description || '';
    document.getElementById('profile-start').value = profile.schedule?.start || '';
    document.getElementById('profile-end').value = profile.schedule?.end || '';
    document.getElementById('profile-enabled').checked = profile.enabled === true;
    
    const controlsCount = Object.keys(profile.controls || {}).length;
    document.getElementById('profile-controls-count').textContent = I18n.t('diagnostics.profile_controls_count_saved', { count: controlsCount }, `${controlsCount} saved controls`);
    
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
        showToast(I18n.t('diagnostics.profile_name_required', {}, 'Profile name is required'), 'error');
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
            showToast(I18n.t('diagnostics.profile_saved', {}, 'Profile saved'), 'success');
            closeProfileModal();
            loadCameraProfiles();
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Capture current camera settings into a specific profile
 */
async function captureProfileSettings(profileId) {
    if (!confirm(I18n.t('diagnostics.profile_capture_confirm', { profile: profileId }, `Capture current settings into profile "${profileId}"?\nThis will replace existing settings.`))) {
        return;
    }
    
    try {
        showToast(I18n.t('diagnostics.profile_capture_in_progress', {}, 'Capturing settings...'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            const controlsCount = data.profile ? Object.keys(data.profile.controls || {}).length : 0;
            showToast(I18n.t('diagnostics.profile_capture_done', { count: controlsCount, profile: profileId }, `${controlsCount} controls captured in "${profileId}"`), 'success');
            
            // Reload profiles to update display
            loadCameraProfiles();
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Apply ghost-fix controls to a profile (CSI only)
 */
async function ghostFixProfile(profileId) {
    if (!confirm(I18n.t('diagnostics.profile_ghostfix_confirm', { profile: profileId }, `Apply ghost-fix to profile "${profileId}"?\nThis disables AE/AWB and centers brightness.`))) {
        return;
    }
    
    try {
        showToast(I18n.t('diagnostics.profile_ghostfix_in_progress', {}, 'Ghost-fix in progress...'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/ghost-fix`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || I18n.t('diagnostics.profile_ghostfix_done', {}, 'Ghost-fix applied'), 'success');
            loadCameraProfiles();
            if (document.getElementById('advanced-camera-section').style.display !== 'none') {
                loadCSICameraControls();
            }
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Capture current camera settings into the profile being edited
 */
async function captureCurrentSettings() {
    const profileId = editingProfileId || document.getElementById('profile-name').value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
    
    if (!profileId) {
        showToast(I18n.t('diagnostics.profile_name_first', {}, 'Enter a profile name first'), 'error');
        return;
    }
    
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(I18n.t('diagnostics.profile_capture_in_progress', {}, 'Capturing settings...'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const controlsCount = data.profile ? Object.keys(data.profile.controls || {}).length : 0;
            document.getElementById('profile-controls-count').textContent = 
                I18n.t('diagnostics.profile_controls_captured', { count: controlsCount }, `${controlsCount} captured controls`);
            showToast(I18n.t('diagnostics.profile_controls_captured', { count: controlsCount }, `${controlsCount} captured controls`), 'success');
            
            // Reload profiles to update local cache
            const profilesResponse = await fetch('/api/camera/profiles');
            const profilesData = await profilesResponse.json();
            if (profilesData.success) {
                cameraProfiles = profilesData.profiles || {};
            }
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Apply a profile immediately
 */
async function applyProfile(profileId) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(I18n.t('diagnostics.profile_apply_in_progress', {}, 'Applying profile...'), 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('diagnostics.profile_applied', { profile: profileId }, `Profile "${profileId}" applied`), 'success');
            loadCameraProfiles();
            // Also refresh advanced controls if visible
            if (document.getElementById('advanced-camera-section').style.display !== 'none') {
                loadAdvancedCameraControls();
            }
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Delete a profile
 */
async function deleteProfile(profileId) {
    if (!confirm(I18n.t('diagnostics.profile_delete_confirm', { profile: profileId }, `Delete profile "${profileId}"?`))) return;
    
    try {
        const response = await fetch(`/api/camera/profiles/${profileId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('diagnostics.profile_deleted', {}, 'Profile deleted'), 'success');
            loadCameraProfiles();
        } else {
            showToast(I18n.t('diagnostics.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('diagnostics.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}


// ============================================================================

    window.runDiagnostic = runDiagnostic;
    window.displayDiagnostic = displayDiagnostic;
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











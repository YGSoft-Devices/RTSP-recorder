/**
 * RTSP Recorder Web Manager - Frontend JavaScript
 * Version: 2.32.66
 */

// Valid tab IDs for URL navigation (debug is optional, checked dynamically)
const VALID_TABS = ['home', 'video', 'network', 'wifi', 'power', 'onvif', 'meeting', 'logs', 'recordings', 'system', 'advanced', 'debug'];

// Tab aliases for convenience (e.g., ?camera -> video)
const TAB_ALIASES = {
    'camera': 'video',
    'config': 'video',
    'settings': 'video',
    'stream': 'video',
    'rtsp': 'video',
    'ethernet': 'network',
    'net': 'network',
    'wlan': 'wifi',
    'wireless': 'wifi',
    'energy': 'power',
    'led': 'power',
    'leds': 'power',
    'gpu': 'power',
    'rec': 'recordings',
    'record': 'recordings',
    'files': 'recordings',
    'log': 'logs',
    'journal': 'logs',
    'update': 'system',
    'updates': 'system',
    'diagnostic': 'system',
    'diag': 'system',
    'about': 'system'
};

let backupFileAction = null;
let backupSelectedFile = null;
let updateFileSelected = null;
let updateFilePolling = null;
let updateFilePollFailures = 0;

/**
 * Get tab ID from URL (hash or query param)
 * Supports: #onvif, ?tab=onvif, ?onvif
 */
function getTabFromUrl() {
    // Check hash first (e.g., #onvif)
    if (window.location.hash) {
        const hashTab = window.location.hash.substring(1).toLowerCase();
        return resolveTabAlias(hashTab);
    }
    
    // Check query params (e.g., ?tab=onvif or ?onvif)
    const params = new URLSearchParams(window.location.search);
    
    // Check explicit tab param
    if (params.has('tab')) {
        return resolveTabAlias(params.get('tab').toLowerCase());
    }
    
    // Check for tab name as key (e.g., ?onvif)
    for (const key of params.keys()) {
        const resolved = resolveTabAlias(key.toLowerCase());
        if (resolved) {
            return resolved;
        }
    }
    
    return null;
}

/**
 * Resolve tab alias to actual tab ID
 */
function resolveTabAlias(alias) {
    if (!alias) return null;
    
    // Direct match
    if (VALID_TABS.includes(alias)) {
        return alias;
    }
    
    // Alias match
    if (TAB_ALIASES[alias]) {
        return TAB_ALIASES[alias];
    }
    
    return null;
}

/**
 * Update URL hash when changing tabs
 */
function updateUrlHash(tabId) {
    // Only update if not on home tab
    if (tabId && tabId !== 'home') {
        history.replaceState(null, '', `#${tabId}`);
    } else {
        // Remove hash for home tab
        history.replaceState(null, '', window.location.pathname + window.location.search);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
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
 * Initialize RTSP Authentication Status display
 */
function initRtspAuthStatus() {
    const userInput = document.getElementById('RTSP_USER');
    const passInput = document.getElementById('RTSP_PASSWORD');
    
    if (userInput && passInput) {
        // Initial update
        updateRtspAuthStatus();
        
        // Update on input change
        userInput.addEventListener('input', updateRtspAuthStatus);
        passInput.addEventListener('input', updateRtspAuthStatus);
    }
}

/**
 * Update RTSP Authentication Status display
 */
function updateRtspAuthStatus() {
    const userInput = document.getElementById('RTSP_USER');
    const passInput = document.getElementById('RTSP_PASSWORD');
    const statusDiv = document.getElementById('rtsp-auth-status');
    const messageSpan = document.getElementById('rtsp-auth-message');
    
    if (!statusDiv || !messageSpan) return;
    
    const user = userInput ? userInput.value.trim() : '';
    const pass = passInput ? passInput.value.trim() : '';
    
    if (user && pass) {
        statusDiv.className = 'alert alert-success';
        messageSpan.innerHTML = `<strong>Authentification activée</strong> - L'utilisateur "${user}" sera requis pour accéder au flux RTSP.<br><small>URL: rtsp://${user}:****@IP:PORT/PATH</small>`;
    } else if (user || pass) {
        statusDiv.className = 'alert alert-warning';
        messageSpan.innerHTML = '<strong>Authentification incomplète</strong> - Vous devez renseigner à la fois l\'utilisateur ET le mot de passe pour activer l\'authentification.';
    } else {
        statusDiv.className = 'alert alert-info';
        messageSpan.innerHTML = '<strong>Authentification désactivée</strong> - Le flux RTSP sera accessible sans mot de passe. Définissez un utilisateur et un mot de passe pour sécuriser l\'accès.';
    }
}

/**
 * Initialize tab navigation
 */
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;

            // Update active states
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`tab-${tabId}`).classList.add('active');

            // Update URL hash
            updateUrlHash(tabId);

            // Stop live logs when leaving logs tab
            if (tabId !== 'logs' && isLiveLogsActive) {
                stopLiveLogs();
            }
            
            // Reload resolutions when entering video tab (in case device changed)
            if (tabId === 'video' && detectedResolutions.length === 0) {
                loadResolutions();
            }
            
            // Load Meeting status when entering meeting tab
            if (tabId === 'meeting') {
                loadMeetingStatus();
            }
        });
    });
}

/**
 * Switch to a specific tab programmatically
 * @param {string} tabId - The tab to switch to
 * @param {boolean} updateUrl - Whether to update the URL hash (default: true)
 */
function switchToTab(tabId, updateUrl = true) {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    const targetBtn = document.querySelector(`[data-tab="${tabId}"]`);
    const targetContent = document.getElementById(`tab-${tabId}`);
    
    // If tab doesn't exist (e.g., debug hidden), fallback to home
    if (!targetBtn || !targetContent) {
        console.log(`Tab "${tabId}" not found, falling back to home`);
        tabId = 'home';
    }
    
    tabButtons.forEach(b => b.classList.remove('active'));
    tabContents.forEach(c => c.classList.remove('active'));
    
    const finalBtn = document.querySelector(`[data-tab="${tabId}"]`);
    const finalContent = document.getElementById(`tab-${tabId}`);
    
    if (finalBtn) finalBtn.classList.add('active');
    if (finalContent) finalContent.classList.add('active');
    
    // Update URL hash if requested
    if (updateUrl) {
        updateUrlHash(tabId);
    }
    
    // Stop live logs when leaving logs tab
    if (tabId !== 'logs' && isLiveLogsActive) {
        stopLiveLogs();
    }
    
    // Load data for specific tabs
    if (tabId === 'meeting') {
        loadMeetingStatus();
    } else if (tabId === 'video' && detectedResolutions.length === 0) {
        loadResolutions();
    }
}

/**
 * Load home page status
 */
async function loadHomeStatus() {
    try {
        // Load RTSP service status
        const statusResponse = await fetch('/api/status');
        const statusData = await statusResponse.json();
        updateHomeServiceStatus('home-rtsp-status', statusData.status === 'active');
        
        // Load config to check recording status
        const configResponse = await fetch('/api/config');
        const configData = await configResponse.json();
        // Check both RECORD_ENABLE and RECORD_ENABLED for compatibility
        const recordingEnabled = configData.config?.RECORD_ENABLE === 'yes' || configData.config?.RECORD_ENABLED === 'yes';
        updateHomeServiceStatus('home-recording-status', recordingEnabled, recordingEnabled ? 'Activé' : 'Désactivé');
        
        // Load ONVIF status
        const onvifResponse = await fetch('/api/onvif/status');
        const onvifData = await onvifResponse.json();
        if (onvifData.success) {
            updateHomeServiceStatus('home-onvif-status', onvifData.running);
            
            // Update device name
            const deviceNameEl = document.getElementById('home-device-name');
            if (deviceNameEl) {
                deviceNameEl.textContent = onvifData.config?.name || 'UNPROVISIONNED';
            }
            
            // Update ONVIF URL
            const onvifUrlEl = document.getElementById('home-onvif-url');
            if (onvifUrlEl && onvifData.preferred_ip) {
                const port = onvifData.config?.port || 8080;
                onvifUrlEl.textContent = `http://${onvifData.preferred_ip}:${port}/onvif/device_service`;
            }
            
            // Also update the ONVIF tab URL display
            const onvifUrlDisplay = document.getElementById('onvif-url-display');
            if (onvifUrlDisplay && onvifData.preferred_ip) {
                const port = onvifData.config?.port || 8080;
                onvifUrlDisplay.textContent = `http://${onvifData.preferred_ip}:${port}/onvif/device_service`;
            }
        }
        
        // Load Meeting status
        const meetingResponse = await fetch('/api/meeting/status');
        const meetingData = await meetingResponse.json();
        if (meetingData.success) {
            // connected is directly in meetingData, not in meetingData.status
            const connected = meetingData.connected === true || meetingData.status?.connected === true;
            const configured = meetingData.configured === true || meetingData.status?.configured === true;
            updateHomeServiceStatus('home-meeting-status', connected, connected ? 'Connecté' : (configured ? 'Déconnecté' : 'Non configuré'));
        }
        
    } catch (error) {
        console.error('Error loading home status:', error);
    }
}

/**
 * Update home service status badge
 */
function updateHomeServiceStatus(elementId, isActive, customText = null) {
    const badge = document.getElementById(elementId);
    if (!badge) return;
    
    badge.className = 'status-badge ' + (isActive ? 'active' : 'inactive');
    const text = badge.querySelector('span:last-child');
    if (text) {
        text.textContent = customText || (isActive ? 'Actif' : 'Inactif');
    }
}

/**
 * Copy ONVIF URL to clipboard
 */
function copyOnvifUrl() {
    const urlEl = document.getElementById('onvif-url-display');
    if (urlEl) {
        copyToClipboard(urlEl.textContent);
    }
}

/**
 * Initialize form submission
 */
function initForm() {
    const form = document.getElementById('config-form');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveConfig();
    });
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    toast.innerHTML = `<i class="fas ${icons[type]}"></i> ${message}`;
    container.appendChild(toast);

    // Remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/**
 * Copy RTSP URL to clipboard
 */
function copyRtspUrl() {
    const url = document.getElementById('rtsp-url').textContent;
    navigator.clipboard.writeText(url).then(() => {
        showToast('URL RTSP copiée !', 'success');
    }).catch(() => {
        showToast('Erreur lors de la copie', 'error');
    });
}

/**
 * Copy any text to clipboard (works on HTTP and HTTPS)
 */
function copyToClipboard(text) {
    // Modern API (HTTPS only)
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copié !', 'success');
        }).catch(() => {
            fallbackCopyToClipboard(text);
        });
    } else {
        // Fallback for HTTP
        fallbackCopyToClipboard(text);
    }
}

/**
 * Fallback copy method using execCommand (works on HTTP)
 */
function fallbackCopyToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-9999px';
    textArea.style.top = '-9999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            showToast('Copié !', 'success');
        } else {
            showToast('Erreur lors de la copie', 'error');
        }
    } catch (err) {
        showToast('Erreur lors de la copie', 'error');
    }
    
    document.body.removeChild(textArea);
}

/**
 * Update service status
 */
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        if (data.success) {
            const badge = document.getElementById('service-status');
            const dot = badge.querySelector('.status-dot');
            const text = badge.querySelector('.status-text');
            
            dot.className = 'status-dot ' + (data.status === 'active' ? 'active' : 'inactive');
            text.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
        }
    } catch (error) {
        console.error('Error updating status:', error);
    }
}

/**
 * Control service (start/stop/restart) - Legacy function for backward compatibility
 */
async function controlService(action) {
    return controlServiceAction(action, 'rpi-av-rtsp-recorder');
}

/**
 * Control any service (start/stop/restart)
 */
async function controlServiceAction(action, serviceName = null) {
    try {
        // Get service from selector if not provided
        if (!serviceName) {
            const serviceSelect = document.getElementById('service-select');
            serviceName = serviceSelect ? serviceSelect.value : 'rpi-av-rtsp-recorder';
        }
        
        const serviceLabel = {
            'rpi-av-rtsp-recorder': 'RTSP Streaming',
            'rtsp-watchdog': 'Watchdog',
            'rpi-cam-onvif': 'ONVIF',
            'rpi-cam-webmanager': 'Web Manager'
        }[serviceName] || serviceName;
        
        // Special case: self-restart warning
        const isSelfRestart = serviceName === 'rpi-cam-webmanager' && (action === 'restart' || action === 'stop');
        
        if (isSelfRestart) {
            showToast(`${serviceLabel}: ${action} en cours... La page va se recharger.`, 'warning');
        } else {
            showToast(`${serviceLabel}: ${action} en cours...`, 'info');
        }
        
        const response = await fetch(`/api/service/${serviceName}/${action}`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            if (data.self_restart || isSelfRestart) {
                // Wait for service to restart then reload page
                showToast(`${serviceLabel}: redémarrage en cours...`, 'warning');
                setTimeout(() => {
                    showToast('Rechargement de la page...', 'info');
                    setTimeout(() => location.reload(), 1000);
                }, 3000);
            } else {
                showToast(`${serviceLabel}: ${action} effectué`, 'success');
                updateStatus();
                loadHomeStatus();
            }
        } else {
            showToast(`Erreur: ${data.message || data.error}`, 'error');
        }
    } catch (error) {
        // If it's a self-restart, the error is expected (connection lost)
        if (serviceName === 'rpi-cam-webmanager') {
            showToast('Service redémarré, rechargement...', 'warning');
            setTimeout(() => location.reload(), 3000);
        } else {
            showToast(`Erreur: ${error.message}`, 'error');
        }
    }
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
            showToast(`Erreur: ${data.message}`, 'error');
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
            showToast(`Erreur: ${data.message || data.error}`, 'error');
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
        
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        const response = await fetch(`/api/camera/formats?device=${encodeURIComponent(device)}`);
        const data = await response.json();
        
        if (data.success && data.formats.length > 0) {
            detectedResolutions = [];
            let options = '<option value="">-- Sélectionnez une résolution --</option>';
            
            // Get current values to pre-select
            const currentWidth = parseInt(document.getElementById('VIDEO_WIDTH')?.value) || 0;
            const currentHeight = parseInt(document.getElementById('VIDEO_HEIGHT')?.value) || 0;
            
            for (const fmt of data.formats) {
                // Add optgroup for each format
                options += `<optgroup label="${fmt.format}">`;
                
                for (const res of fmt.resolutions) {
                    const fps = res.framerates.length > 0 ? Math.floor(res.framerates[0]) : 30;
                    const allFps = res.framerates.map(f => Math.floor(f)).join(', ');
                    const megapixels = ((res.width * res.height) / 1000000).toFixed(1);
                    
                    // Store resolution data for later use
                    const resIndex = detectedResolutions.length;
                    detectedResolutions.push({
                        format: fmt.format,
                        width: res.width,
                        height: res.height,
                        fps: fps,
                        framerates: res.framerates.map(f => Math.floor(f)),
                        megapixels: megapixels
                    });
                    
                    const isSelected = (res.width === currentWidth && res.height === currentHeight);
                    const selectedAttr = isSelected ? ' selected' : '';
                    
                    options += `<option value="${resIndex}"${selectedAttr}>`;
                    options += `${res.width}×${res.height} @ ${fps}fps (${megapixels}MP)`;
                    options += `</option>`;
                }
                
                options += '</optgroup>';
            }
            
            select.innerHTML = options;
            select.disabled = false;
            
            // Trigger change to show details if something is selected
            if (select.value) {
                onResolutionSelectChange();
            }
            
            console.log(`Loaded ${detectedResolutions.length} resolutions`);
        } else {
            select.innerHTML = '<option value="">❌ Aucune résolution détectée</option>';
            select.disabled = true;
        }
    } catch (error) {
        console.error('Error loading resolutions:', error);
        select.innerHTML = '<option value="">❌ Erreur de détection</option>';
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
        showToast('Application des paramètres vidéo...', 'info');
        
        const config = {
            VIDEO_WIDTH: document.getElementById('VIDEO_WIDTH').value,
            VIDEO_HEIGHT: document.getElementById('VIDEO_HEIGHT').value,
            VIDEO_FPS: document.getElementById('VIDEO_FPS').value,
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
            showToast('Paramètres vidéo sauvegardés! Redémarrage du service...', 'success');
            
            // Restart RTSP service to apply changes
            try {
                const restartResponse = await fetch('/api/service/rpi-av-rtsp-recorder/restart', {
                    method: 'POST'
                });
                const restartData = await restartResponse.json();
                if (restartData.success) {
                    showToast('Service RTSP redémarré avec succès', 'success');
                } else {
                    showToast('Config sauvée mais redémarrage échoué: ' + restartData.error, 'warning');
                }
            } catch (e) {
                showToast('Config sauvée, redémarrage manuel requis', 'warning');
            }
        } else {
            showToast('Erreur: ' + (data.error || 'Échec de la sauvegarde'), 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Load recordings list
 */
async function loadRecordings() {
    try {
        const response = await fetch('/api/recordings');
        const data = await response.json();
        
        const listContainer = document.getElementById('recordings-list');
        
        if (data.success && data.recordings.length > 0) {
            listContainer.innerHTML = data.recordings.map(rec => `
                <div class="recording-item">
                    <input type="checkbox" name="recording" value="${rec.name}">
                    <span class="file-name">${rec.name}</span>
                    <span class="file-size">${rec.size_mb} Mo</span>
                </div>
            `).join('');
        } else {
            listContainer.innerHTML = '<p class="text-muted" style="padding: 15px;">Aucun enregistrement trouvé</p>';
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Delete selected recordings
 */
async function deleteSelectedRecordings() {
    const checkboxes = document.querySelectorAll('#recordings-list input[type="checkbox"]:checked');
    const files = Array.from(checkboxes).map(cb => cb.value);
    
    if (files.length === 0) {
        showToast('Veuillez sélectionner des fichiers à supprimer', 'warning');
        return;
    }
    
    if (!confirm(`Êtes-vous sûr de vouloir supprimer ${files.length} fichier(s) ?`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/recordings/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ files })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`${data.deleted} fichier(s) supprimé(s)`, 'success');
            loadRecordings();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// Files Tab Functions (Enhanced Recording Files Management)
// ============================================================================

let filesData = [];         // Current page files from server
let selectedFiles = new Set();  // Currently selected file names
let filesPagination = {     // Pagination state
    page: 1,
    perPage: 20,
    totalPages: 1,
    totalFiltered: 0
};

/**
 * Load files list from server with pagination
 */
async function loadFilesList(page = 1) {
    const listContainer = document.getElementById('files-list');
    listContainer.innerHTML = '<div class="files-loading"><i class="fas fa-spinner fa-spin"></i> Chargement des fichiers...</div>';
    
    // Get filter/sort/search parameters
    const filter = document.getElementById('files-filter')?.value || 'all';
    const sort = document.getElementById('files-sort')?.value || 'date-desc';
    const search = document.getElementById('files-search')?.value || '';
    const perPage = parseInt(document.getElementById('files-per-page')?.value) || 20;
    
    try {
        const params = new URLSearchParams({
            page: page,
            per_page: perPage,
            filter: filter,
            sort: sort,
            search: search
        });
        
        const response = await fetch(`/api/recordings/list?${params}`);
        const data = await response.json();
        
        if (data.success) {
            filesData = data.recordings || [];
            
            // Update pagination state
            filesPagination = {
                page: data.pagination.page,
                perPage: data.pagination.per_page,
                totalPages: data.pagination.total_pages,
                totalFiltered: data.pagination.total_filtered,
                hasPrev: data.pagination.has_prev,
                hasNext: data.pagination.has_next,
                startIndex: data.pagination.start_index,
                endIndex: data.pagination.end_index
            };
            
            // Clear selection when changing pages
            selectedFiles.clear();
            
            // Update storage info
            document.getElementById('files-total-count').textContent = data.pagination.total_filtered || 0;
            document.getElementById('files-total-size').textContent = data.total_size_display || '0 o';
            
            // Display usable space (disk available minus safety margin)
            const availableEl = document.getElementById('files-disk-available');
            const usedEl = document.getElementById('files-disk-used');
            const totalEl = document.getElementById('files-disk-total');
            const marginEl = document.getElementById('files-quota-info');
            const maxQuotaEl = document.getElementById('files-max-quota-info');
            
            if (data.storage_info && data.storage_info.usable_bytes !== undefined) {
                // Check if disk is full (below safety margin)
                if (data.storage_info.disk_full) {
                    availableEl.textContent = '0 o';
                    availableEl.classList.add('disk-full');
                    if (marginEl) {
                        marginEl.innerHTML = `<i class="fas fa-exclamation-triangle"></i> DISQUE PLEIN (marge ${data.storage_info.min_free_display} non atteinte)`;
                        marginEl.classList.add('disk-full-warning');
                        marginEl.style.display = 'flex';
                    }
                } else {
                    // Show usable space (after safety margin)
                    availableEl.textContent = data.storage_info.usable_display || '-';
                    availableEl.classList.remove('disk-full');
                    if (marginEl) {
                        if (data.storage_info.min_free_bytes > 0) {
                            marginEl.innerHTML = `<i class="fas fa-shield-alt"></i> Marge: ${data.storage_info.min_free_display} réservés`;
                            marginEl.classList.remove('disk-full-warning');
                            marginEl.style.display = 'flex';
                        } else {
                            marginEl.style.display = 'none';
                        }
                    }
                }
            } else {
                // Fallback to raw disk available
                availableEl.textContent = data.disk_info?.available_display || '-';
                availableEl.classList.remove('disk-full');
                if (marginEl) marginEl.style.display = 'none';
            }

            if (data.disk_info) {
                if (usedEl) {
                    const percent = data.disk_info.percent ?? 0;
                    usedEl.textContent = `${data.disk_info.used_display || '-'} (${percent}%)`;
                }
                if (totalEl) {
                    totalEl.textContent = data.disk_info.total_display || '-';
                }
            } else {
                if (usedEl) usedEl.textContent = '-';
                if (totalEl) totalEl.textContent = '-';
            }

            if (maxQuotaEl) {
                if (data.storage_info?.max_disk_enabled) {
                    maxQuotaEl.innerHTML = `<i class="fas fa-database"></i> Quota: ${data.storage_info.recordings_size_display} / ${data.storage_info.max_disk_display}`;
                    maxQuotaEl.style.display = 'flex';
                } else {
                    maxQuotaEl.style.display = 'none';
                }
            }
            
            const dirEl = document.getElementById('files-directory');
            dirEl.textContent = data.directory || '-';
            dirEl.title = data.directory || '';
            
            // Render files and pagination
            renderFilesList();
            renderPagination();
            updateFilesSelectionInfo();
        } else {
            listContainer.innerHTML = `<div class="files-error"><i class="fas fa-exclamation-triangle"></i> Erreur: ${data.message}</div>`;
        }
    } catch (error) {
        listContainer.innerHTML = `<div class="files-error"><i class="fas fa-exclamation-triangle"></i> Erreur de connexion: ${error.message}</div>`;
    }
}

/**
 * Render files list as grid (gallery view)
 */
function renderFilesList() {
    const listContainer = document.getElementById('files-list');
    
    if (filesData.length === 0) {
        listContainer.innerHTML = '<div class="files-empty"><i class="fas fa-folder-open"></i> Aucun fichier trouvé</div>';
        return;
    }
    
    const html = filesData.map(file => {
        const isSelected = selectedFiles.has(file.name);
        const lockIcon = file.locked ? 'fa-lock' : 'fa-lock-open';
        const thumbUrl = `/api/recordings/thumbnail/${encodeURIComponent(file.name)}`;
        
        // Extract date/time from filename (rec_YYYYMMDD_HHMMSS.ts)
        const match = file.name.match(/rec_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
        const dateLabel = match ? `${match[3]}/${match[2]} ${match[4]}:${match[5]}` : file.modified_display;
        
        return `
            <div class="file-card ${isSelected ? 'selected' : ''} ${file.locked ? 'is-locked' : ''}" data-filename="${file.name}">
                <div class="file-card-select">
                    <input type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleFileSelection('${file.name}')">
                </div>
                ${file.locked ? '<div class="file-card-lock"><i class="fas fa-lock"></i></div>' : ''}
                <div class="file-card-thumb" onclick="playFile('${file.name}')" title="Cliquer pour lire">
                    <img src="${thumbUrl}" alt="" loading="lazy" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                    <div class="thumb-placeholder" style="display:none;"><i class="fas fa-film"></i></div>
                    <div class="thumb-play-overlay"><i class="fas fa-play-circle"></i></div>
                </div>
                <div class="file-card-info">
                    <span class="file-card-date" title="${file.modified_iso}">${dateLabel}</span>
                    <span class="file-card-size">${file.size_display}</span>
                </div>
                <div class="file-card-actions">
                    <button class="btn-icon btn-download" onclick="downloadFile('${file.name}')" title="Télécharger">
                        <i class="fas fa-download"></i>
                    </button>
                    <button class="btn-icon btn-lock" onclick="toggleFileLock('${file.name}', ${!file.locked})" title="${file.locked ? 'Déverrouiller' : 'Verrouiller'}">
                        <i class="fas ${file.locked ? 'fa-lock-open' : 'fa-lock'}"></i>
                    </button>
                    <button class="btn-icon btn-delete" onclick="deleteSingleFile('${file.name}')" title="Supprimer">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');
    
    listContainer.innerHTML = html;
}

/**
 * Render pagination controls
 */
function renderPagination() {
    const { page, totalPages, totalFiltered, startIndex, endIndex, hasPrev, hasNext } = filesPagination;
    
    // Update range info
    document.getElementById('pagination-range').textContent = 
        totalFiltered > 0 ? `${startIndex}-${endIndex}` : '0';
    document.getElementById('pagination-total').textContent = totalFiltered;
    
    // Update navigation buttons
    document.getElementById('btn-first-page').disabled = !hasPrev;
    document.getElementById('btn-prev-page').disabled = !hasPrev;
    document.getElementById('btn-next-page').disabled = !hasNext;
    document.getElementById('btn-last-page').disabled = !hasNext;
    
    // Generate page numbers
    const pagesContainer = document.getElementById('pagination-pages');
    let pagesHtml = '';
    
    // Calculate visible page range (show max 5 pages)
    let startPage = Math.max(1, page - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }
    
    // First page + ellipsis if needed
    if (startPage > 1) {
        pagesHtml += `<button class="btn-page" onclick="goToPage(1)">1</button>`;
        if (startPage > 2) {
            pagesHtml += `<span class="pagination-ellipsis">...</span>`;
        }
    }
    
    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
        const activeClass = i === page ? 'active' : '';
        pagesHtml += `<button class="btn-page ${activeClass}" onclick="goToPage(${i})">${i}</button>`;
    }
    
    // Last page + ellipsis if needed
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            pagesHtml += `<span class="pagination-ellipsis">...</span>`;
        }
        pagesHtml += `<button class="btn-page" onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }
    
    pagesContainer.innerHTML = pagesHtml;
}

/**
 * Navigate to specific page
 */
function goToPage(page) {
    if (page === 'last') {
        page = filesPagination.totalPages;
    }
    loadFilesList(page);
}

/**
 * Navigate to previous page
 */
function goToPrevPage() {
    if (filesPagination.page > 1) {
        loadFilesList(filesPagination.page - 1);
    }
}

/**
 * Navigate to next page
 */
function goToNextPage() {
    if (filesPagination.page < filesPagination.totalPages) {
        loadFilesList(filesPagination.page + 1);
    }
}

/**
 * Change items per page
 */
function changePerPage() {
    loadFilesList(1);  // Reset to page 1 when changing per_page
}

/**
 * Toggle file selection
 */
function toggleFileSelection(filename) {
    if (selectedFiles.has(filename)) {
        selectedFiles.delete(filename);
    } else {
        selectedFiles.add(filename);
    }
    
    // Update visual state
    const item = document.querySelector(`.file-item[data-filename="${filename}"]`);
    if (item) {
        item.classList.toggle('selected', selectedFiles.has(filename));
    }
    
    updateFilesSelectionInfo();
    updateSelectAllCheckbox();
}

/**
 * Toggle select all files (current page only)
 */
function toggleSelectAllFiles() {
    const checkbox = document.getElementById('files-select-all');
    const selectAll = checkbox.checked;
    
    if (selectAll) {
        filesData.forEach(file => selectedFiles.add(file.name));
    } else {
        selectedFiles.clear();
    }
    
    renderFilesList();
    updateFilesSelectionInfo();
}

/**
 * Update select all checkbox state
 */
function updateSelectAllCheckbox() {
    const checkbox = document.getElementById('files-select-all');
    if (checkbox) {
        const allSelected = filesData.length > 0 && filesData.every(f => selectedFiles.has(f.name));
        const someSelected = filesData.some(f => selectedFiles.has(f.name));
        checkbox.checked = allSelected;
        checkbox.indeterminate = someSelected && !allSelected;
    }
}

/**
 * Update selection info bar
 */
function updateFilesSelectionInfo() {
    const infoBar = document.getElementById('files-selection-info');
    const countEl = document.getElementById('files-selected-count');
    const sizeEl = document.getElementById('files-selected-size');
    
    if (selectedFiles.size > 0) {
        // Calculate total size of selected files (from current page data)
        let totalSize = 0;
        filesData.forEach(file => {
            if (selectedFiles.has(file.name)) {
                totalSize += file.size_bytes;
            }
        });
        
        countEl.textContent = selectedFiles.size;
        sizeEl.textContent = formatFileSize(totalSize);
        infoBar.style.display = 'flex';
    } else {
        infoBar.style.display = 'none';
    }
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    const units = ['o', 'Ko', 'Mo', 'Go', 'To'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

/**
 * Apply filter to files list (server-side filtering)
 */
function applyFilesFilter() {
    loadFilesList(1);  // Reset to page 1 when filtering
}

/**
 * Apply sort to files list (server-side sorting)
 */
function applyFilesSort() {
    loadFilesList(1);  // Reset to page 1 when sorting
}

/**
 * Apply search filter (with debounce)
 */
let filesSearchTimeout = null;
function applyFilesSearch() {
    clearTimeout(filesSearchTimeout);
    filesSearchTimeout = setTimeout(() => {
        loadFilesList(1);  // Reset to page 1 when searching
    }, 300);  // Debounce 300ms
}

/**
 * Play video file
 */
function playFile(filename) {
    const modal = document.getElementById('video-player-modal');
    const player = document.getElementById('video-player');
    const titleEl = document.getElementById('video-player-title');
    const errorEl = document.getElementById('video-player-error');
    
    // Extract nice date from filename
    const match = filename.match(/rec_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
    const dateLabel = match ? `${match[3]}/${match[2]}/${match[1]} à ${match[4]}:${match[5]}:${match[6]}` : filename;
    titleEl.textContent = dateLabel;
    
    // Reset error state
    if (errorEl) errorEl.style.display = 'none';
    player.style.display = 'block';
    
    // Set video source directly (better browser compatibility)
    const streamUrl = `/api/recordings/stream/${encodeURIComponent(filename)}`;
    player.src = streamUrl;
    
    // Handle video errors
    player.onerror = function() {
        console.error('Video playback error:', player.error);
        if (errorEl) {
            errorEl.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Impossible de lire ce fichier.<br>
                <small>Format .ts - <a href="${streamUrl}" download="${filename}">Télécharger pour lire localement</a></small>`;
            errorEl.style.display = 'flex';
        }
        player.style.display = 'none';
    };
    
    modal.style.display = 'flex';
    player.play().catch(e => {
        console.log('Autoplay prevented:', e);
    });
    
    // Get file info for display
    const file = filesData.find(f => f.name === filename);
    if (file) {
        document.getElementById('video-size').textContent = file.size_display;
    }
    
    // Try to get duration info
    fetchFileInfo(filename);
}

/**
 * Fetch detailed file info
 */
async function fetchFileInfo(filename) {
    try {
        const response = await fetch(`/api/recordings/info/${encodeURIComponent(filename)}`);
        const data = await response.json();
        
        if (data.success && data.info) {
            const durationEl = document.getElementById('video-duration');
            if (data.info.duration_display) {
                durationEl.textContent = data.info.duration_display;
            }
        }
    } catch (error) {
        console.log('Could not fetch file info:', error);
    }
}

/**
 * Close video player
 */
function closeVideoPlayer() {
    const modal = document.getElementById('video-player-modal');
    const player = document.getElementById('video-player');
    
    player.pause();
    player.src = '';
    player.onerror = null;
    
    modal.style.display = 'none';
}

/**
 * Download file
 */
function downloadFile(filename) {
    const link = document.createElement('a');
    link.href = `/api/recordings/download/${encodeURIComponent(filename)}`;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast(`Téléchargement de ${filename} démarré`, 'success');
}

/**
 * Toggle lock on single file
 */
async function toggleFileLock(filename, lock) {
    try {
        const response = await fetch('/api/recordings/lock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filename], lock: lock })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Fichier ${lock ? 'verrouillé' : 'déverrouillé'}`, 'success');
            // Update local data
            const file = filesData.find(f => f.name === filename);
            if (file) file.locked = lock;
            renderFilesList();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Lock selected files
 */
async function lockSelectedFiles() {
    if (selectedFiles.size === 0) {
        showToast('Aucun fichier sélectionné', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/recordings/lock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: Array.from(selectedFiles), lock: true })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`${data.modified} fichier(s) verrouillé(s)`, 'success');
            loadFilesList();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Unlock selected files
 */
async function unlockSelectedFiles() {
    if (selectedFiles.size === 0) {
        showToast('Aucun fichier sélectionné', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/recordings/lock', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: Array.from(selectedFiles), lock: false })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`${data.modified} fichier(s) déverrouillé(s)`, 'success');
            loadFilesList();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Delete single file
 */
async function deleteSingleFile(filename) {
    // Check if file is locked
    const file = filesData.find(f => f.name === filename);
    if (file && file.locked) {
        if (!confirm(`Le fichier "${filename}" est verrouillé.\n\nVoulez-vous quand même le supprimer ?`)) {
            return;
        }
    } else {
        if (!confirm(`Êtes-vous sûr de vouloir supprimer "${filename}" ?`)) {
            return;
        }
    }
    
    try {
        const response = await fetch('/api/recordings/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: [filename], force: file?.locked })
        });
        
        const data = await response.json();
        
        if (data.success && data.deleted > 0) {
            showToast('Fichier supprimé', 'success');
            loadFilesList();
        } else if (data.skipped_locked?.length > 0) {
            showToast('Fichier verrouillé - impossible de supprimer', 'warning');
        } else {
            showToast(`Erreur: ${data.message || 'Impossible de supprimer'}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Delete selected files
 */
async function deleteSelectedFiles() {
    if (selectedFiles.size === 0) {
        showToast('Aucun fichier sélectionné', 'warning');
        return;
    }
    
    // Check for locked files
    const lockedCount = Array.from(selectedFiles).filter(name => {
        const file = filesData.find(f => f.name === name);
        return file && file.locked;
    }).length;
    
    let confirmMsg = `Êtes-vous sûr de vouloir supprimer ${selectedFiles.size} fichier(s) ?`;
    if (lockedCount > 0) {
        confirmMsg += `\n\n⚠️ ${lockedCount} fichier(s) verrouillé(s) seront ignorés.`;
    }
    
    if (!confirm(confirmMsg)) {
        return;
    }
    
    try {
        const response = await fetch('/api/recordings/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: Array.from(selectedFiles), force: false })
        });
        
        const data = await response.json();
        
        if (data.success) {
            let message = `${data.deleted} fichier(s) supprimé(s)`;
            if (data.skipped_locked?.length > 0) {
                message += ` (${data.skipped_locked.length} verrouillé(s) ignoré(s))`;
            }
            showToast(message, 'success');
            loadFilesList();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// Auto-load files when switching to files tab
document.addEventListener('DOMContentLoaded', () => {
    const filesTabBtn = document.querySelector('[data-tab="files"]');
    if (filesTabBtn) {
        filesTabBtn.addEventListener('click', () => {
            if (filesData.length === 0) {
                loadFilesList();
            }
        });
    }
});

// ============================================================================
// Logs Functions
// ============================================================================

let logsEventSource = null;
let isLiveLogsActive = false;

/**
 * Load logs from server
 */
async function loadLogs() {
    try {
        const source = document.getElementById('logs-source')?.value || 'all';
        const lines = document.getElementById('logs-lines')?.value || 100;
        
        updateLogsStatus('Chargement...');
        
        const response = await fetch(`/api/logs?lines=${lines}&source=${source}`);
        const data = await response.json();
        
        const logsContent = document.getElementById('logs-content');
        
        if (data.success) {
            let logsText = '';
            if (data.logs_text) {
                logsText = data.logs_text;
            } else if (Array.isArray(data.logs)) {
                logsText = formatLogEntries(data.logs);
            } else if (typeof data.logs === 'string') {
                logsText = data.logs;
            }

            logsContent.textContent = logsText || 'Aucun log disponible';
            logsContent.scrollTop = logsContent.scrollHeight;
            updateLogsStatus(`Dernière mise à jour: ${new Date().toLocaleTimeString()}`);
        } else {
            logsContent.textContent = 'Erreur lors du chargement des logs';
            updateLogsStatus('Erreur');
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        updateLogsStatus('Erreur de connexion');
    }
}

/**
 * Toggle live logs streaming
 */
function toggleLiveLogs() {
    if (isLiveLogsActive) {
        stopLiveLogs();
    } else {
        startLiveLogs();
    }
}

/**
 * Start live logs streaming via SSE
 */
function startLiveLogs() {
    if (logsEventSource) {
        logsEventSource.close();
    }
    
    const logsContent = document.getElementById('logs-content');
    logsContent.textContent = '=== Logs en direct ===\nConnexion au flux de logs...\n\n';
    
    logsEventSource = new EventSource('/api/logs/stream');
    isLiveLogsActive = true;
    
    // Update UI
    const btn = document.getElementById('btn-live-logs');
    btn.innerHTML = '<i class="fas fa-stop"></i> Arrêter';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-danger');
    
    document.getElementById('live-indicator').style.display = 'flex';
    updateLogsStatus('Streaming en direct...');
    
    logsEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.log) {
                logsContent.textContent += data.log + '\n';
                // Keep only last 1000 lines
                const lines = logsContent.textContent.split('\n');
                if (lines.length > 1000) {
                    logsContent.textContent = lines.slice(-1000).join('\n');
                }
                logsContent.scrollTop = logsContent.scrollHeight;
            } else if (data.error) {
                logsContent.textContent += `[ERREUR] ${data.error}\n`;
            }
        } catch (e) {
            // Ignore parse errors for heartbeats
        }
    };
    
    logsEventSource.onerror = function(error) {
        console.error('SSE Error:', error);
        logsContent.textContent += '\n[Connexion perdue. Tentative de reconnexion...]\n';
        updateLogsStatus('Reconnexion...');
    };
    
    showToast('Logs en direct activés', 'success');
}

/**
 * Stop live logs streaming
 */
function stopLiveLogs() {
    if (logsEventSource) {
        logsEventSource.close();
        logsEventSource = null;
    }
    isLiveLogsActive = false;
    
    // Update UI
    const btn = document.getElementById('btn-live-logs');
    btn.innerHTML = '<i class="fas fa-play"></i> Logs en direct';
    btn.classList.remove('btn-danger');
    btn.classList.add('btn-primary');
    
    document.getElementById('live-indicator').style.display = 'none';
    updateLogsStatus('Streaming arrêté');
    
    const logsContent = document.getElementById('logs-content');
    logsContent.textContent += '\n\n=== Streaming arrêté ===\n';
    
    showToast('Logs en direct désactivés', 'info');
}

/**
 * Clear logs display
 */
function clearLogsDisplay() {
    const logsContent = document.getElementById('logs-content');
    logsContent.textContent = '';
    updateLogsStatus('Affichage effacé');
}

/**
 * Clean server log files (delete/truncate actual log files)
 */
async function cleanServerLogs() {
    if (!confirm('Voulez-vous vraiment nettoyer les fichiers de logs sur le serveur ?\n\nCette action va :\n- Tronquer le fichier log principal (garder 100 dernières lignes)\n- Supprimer les logs GStreamer\n- Supprimer les vieux fichiers de log (> 7 jours)\n- Vider le cache journald')) {
        return;
    }
    
    try {
        showToast('Nettoyage des logs en cours...', 'info');
        
        const response = await fetch('/api/logs/clean', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            // Reload logs to show the cleaned state
            loadLogs();
        } else {
            showToast(data.message || 'Erreur lors du nettoyage', 'error');
        }
    } catch (error) {
        console.error('Error cleaning logs:', error);
        showToast('Erreur lors du nettoyage des logs', 'error');
    }
}

/**
 * Update logs status text
 */
function updateLogsStatus(text) {
    const statusText = document.getElementById('logs-status-text');
    if (statusText) {
        statusText.textContent = text;
    }
}

// ============================================================================
// Diagnostic Functions
// ============================================================================

/**
 * Run system diagnostic
 */
async function runDiagnostic() {
    try {
        showToast('Diagnostic en cours...', 'info');
        
        const response = await fetch('/api/diagnostic');
        const data = await response.json();
        
        if (data.success) {
            displayDiagnostic(data.diagnostic);
            document.getElementById('diagnostic-results').style.display = 'block';
            showToast('Diagnostic terminé', 'success');
        } else {
            showToast('Erreur lors du diagnostic', 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
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
            <span class="label">État du service:</span>
            <span class="value">${diag.service.status || 'inconnu'}</span>
        </div>
        <div class="diag-item">
            <span class="status-icon ${diag.service.script_exists ? 'success' : 'error'}">
                <i class="fas fa-${diag.service.script_exists ? 'check-circle' : 'times-circle'}"></i>
            </span>
            <span class="label">Script RTSP:</span>
            <span class="value">${diag.service.script_exists ? 'Présent' : 'Absent'} (${diag.service.script_path})</span>
        </div>
    `;
    document.getElementById('diag-service').innerHTML = serviceHtml;
    
    // GStreamer section
    const gstHtml = `
        <div class="diag-item">
            <span class="status-icon ${diag.gstreamer.installed ? 'success' : 'error'}">
                <i class="fas fa-${diag.gstreamer.installed ? 'check-circle' : 'times-circle'}"></i>
            </span>
            <span class="label">GStreamer:</span>
            <span class="value">${diag.gstreamer.installed ? diag.gstreamer.version : 'Non installé'}</span>
        </div>
        <div class="diag-item">
            <span class="status-icon ${diag.gstreamer.rtsp_plugin ? 'success' : 'error'}">
                <i class="fas fa-${diag.gstreamer.rtsp_plugin ? 'check-circle' : 'times-circle'}"></i>
            </span>
            <span class="label">Plugin RTSP:</span>
            <span class="value">${diag.gstreamer.rtsp_plugin ? 'Installé' : 'Manquant (gst-rtsp-server)'}</span>
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
                <span class="label">Encodeur actif:</span>
                <span class="value">${diag.encoder.active_encoder || 'inconnu'}</span>
            </div>
            <div class="diag-item">
                <span class="status-icon ${isHardware ? 'success' : (isSoftware ? 'warning' : 'error')}">
                    <i class="fas fa-${isHardware ? 'bolt' : (isSoftware ? 'cog' : 'times-circle')}"></i>
                </span>
                <span class="label">Type:</span>
                <span class="value encoder-type-${encoderType}">${
                    isHardware ? 'HARDWARE (GPU VideoCore) - CPU faible' : 
                    (isSoftware ? 'SOFTWARE (x264) - CPU élevé' : 'Aucun')
                }</span>
            </div>
            <div class="diag-item">
                <span class="status-icon ${diag.encoder.hw_available ? 'success' : 'warning'}">
                    <i class="fas fa-${diag.encoder.hw_available ? 'check-circle' : 'exclamation-triangle'}"></i>
                </span>
                <span class="label">HW disponible:</span>
                <span class="value">${diag.encoder.hw_available ? 'Oui (v4l2h264enc)' : 'Non'}</span>
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
                    <h5><i class="fas fa-microchip"></i> Encodeur H264</h5>
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
            <span class="label">Caméra V4L2:</span>
            <span class="value">${diag.camera.devices_found ? 'Détectée' : 'Non détectée'}</span>
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
                <span class="label">Caméra CSI:</span>
                <span class="value">${diag.camera.csi_detected ? 'Détectée' : 'Non détectée'}</span>
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
            <span class="label">Microphone:</span>
            <span class="value">${diag.audio.devices_found ? 'Détecté' : 'Non détecté'}</span>
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
            <span class="label">Port RTSP:</span>
            <span class="value">${diag.network.rtsp_port_in_use ? 'En écoute' : 'Non actif'}</span>
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
// WiFi Functions
// ============================================================================

/**
 * Scan for available WiFi networks
 */
async function scanWifi() {
    try {
        showToast('Scan WiFi en cours...', 'info');
        
        const response = await fetch('/api/wifi/scan');
        const data = await response.json();
        
        const listContainer = document.getElementById('wifi-list');
        
        if (data.success && data.networks.length > 0) {
            // Remove duplicates
            const uniqueNetworks = data.networks.filter((network, index, self) =>
                index === self.findIndex((n) => n.ssid === network.ssid)
            );
            
            listContainer.innerHTML = uniqueNetworks.map(net => `
                <div class="detection-item" onclick="selectWifi('${escapeHtml(net.ssid)}')">
                    <span class="device-name">
                        <i class="fas fa-wifi"></i> ${escapeHtml(net.ssid)}
                    </span>
                    <span class="wifi-details">
                        <span class="signal">${net.signal}%</span>
                        <span class="security">${net.security}</span>
                    </span>
                </div>
            `).join('');
            showToast(`${uniqueNetworks.length} réseau(x) trouvé(s)`, 'success');
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucun réseau trouvé</span></div>';
            showToast('Aucun réseau WiFi trouvé', 'warning');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Select a WiFi network from scan results
 */
function selectWifi(ssid) {
    document.getElementById('wifi_ssid').value = ssid;
    document.getElementById('wifi-list').innerHTML = '';
    document.getElementById('wifi_password').focus();
}

/**
 * Connect to WiFi network
 */
async function connectWifi(isFallback = false) {
    try {
        const ssidField = isFallback ? 'wifi_fallback_ssid' : 'wifi_ssid';
        const passField = isFallback ? 'wifi_fallback_password' : 'wifi_password';
        
        const ssid = document.getElementById(ssidField).value;
        const password = document.getElementById(passField).value;
        
        if (!ssid) {
            showToast('Veuillez entrer un SSID', 'warning');
            return;
        }
        
        showToast(`Connexion à ${ssid}...`, 'info');
        
        const response = await fetch('/api/wifi/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password, fallback: isFallback })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(isFallback ? 'Réseau de secours ajouté' : 'Connexion réussie !', 'success');
            // Clear password field for security
            document.getElementById(passField).value = '';
            // Refresh status after a delay
            setTimeout(updateStatus, 3000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Toggle password visibility
 */
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.nextElementSibling.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// ============================================================================
// Network Interface Functions
// ============================================================================

let networkInterfacesOrder = [];

/**
 * Load network interfaces and display them
 */
async function loadNetworkInterfaces() {
    try {
        const listContainer = document.getElementById('network-interfaces-list');
        listContainer.innerHTML = '<div class="loading-placeholder"><i class="fas fa-spinner fa-spin"></i> Chargement des interfaces...</div>';
        
        const response = await fetch('/api/network/interfaces');
        const data = await response.json();
        
        if (data.success && data.interfaces.length > 0) {
            networkInterfacesOrder = data.priority.length > 0 ? data.priority : data.interfaces.map(i => i.name);
            
            // Sort interfaces by priority
            const sortedInterfaces = [...data.interfaces].sort((a, b) => {
                const aIndex = networkInterfacesOrder.indexOf(a.name);
                const bIndex = networkInterfacesOrder.indexOf(b.name);
                return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
            });
            
            listContainer.innerHTML = sortedInterfaces.map((iface, index) => `
                <div class="network-interface-item ${iface.connected ? 'connected' : ''}" 
                     draggable="true" 
                     data-interface="${iface.name}"
                     ondragstart="handleDragStart(event)"
                     ondragover="handleDragOver(event)"
                     ondrop="handleDrop(event)"
                     ondragend="handleDragEnd(event)">
                    <span class="drag-handle">
                        <i class="fas fa-grip-vertical"></i>
                    </span>
                    <span class="interface-icon">
                        ${getInterfaceIcon(iface.type)}
                    </span>
                    <span class="interface-info">
                        <span class="interface-name">${iface.name}</span>
                        <span class="interface-type">${getInterfaceTypeLabel(iface.type)}</span>
                        ${iface.mac ? `<span class="interface-mac">${iface.mac}</span>` : ''}
                    </span>
                    <span class="interface-status">
                        ${iface.ip ? `<span class="interface-ip">${iface.ip}</span>` : ''}
                        <span class="status-badge ${iface.connected ? 'connected' : 'disconnected'}">${iface.connected ? 'Connecté' : 'Déconnecté'}</span>
                    </span>
                    <span class="priority-badge">#${index + 1}</span>
                </div>
            `).join('');
            
            // Update interface select dropdowns
            updateInterfaceSelects(data.interfaces);
            
            // Update header status badge - show primary connected interface
            updateNetworkHeaderStatus(sortedInterfaces);
            
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucune interface réseau trouvée</span></div>';
        }
    } catch (error) {
        console.error('Error loading interfaces:', error);
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Update the network header status badge based on interfaces
 */
function updateNetworkHeaderStatus(interfaces) {
    const indicator = document.getElementById('network-header-indicator');
    const ssidEl = document.getElementById('network-header-ssid');
    const ipEl = document.getElementById('network-header-ip');
    
    if (!indicator) return;
    
    // Find first connected interface (already sorted by priority)
    const connectedIface = interfaces.find(iface => iface.connected && iface.name !== 'lo');
    
    if (connectedIface) {
        indicator.className = 'status-indicator connected';
        indicator.textContent = 'Connecté';
        ssidEl.textContent = connectedIface.name;
        ipEl.textContent = connectedIface.ip || '';
    } else {
        indicator.className = 'status-indicator disconnected';
        indicator.textContent = 'Déconnecté';
        ssidEl.textContent = '';
        ipEl.textContent = '';
    }
}

/**
 * Get icon for interface type
 */
function getInterfaceIcon(type) {
    switch (type) {
        case 'wifi':
            return '<i class="fas fa-wifi"></i>';
        case 'ethernet':
            return '<i class="fas fa-ethernet"></i>';
        case 'loopback':
            return '<i class="fas fa-redo"></i>';
        default:
            return '<i class="fas fa-network-wired"></i>';
    }
}

/**
 * Get label for interface type
 */
function getInterfaceTypeLabel(type) {
    switch (type) {
        case 'wifi':
            return 'WiFi';
        case 'ethernet':
            return 'Ethernet';
        case 'loopback':
            return 'Loopback';
        default:
            return 'Réseau';
    }
}

/**
 * Update interface select dropdowns
 */
function updateInterfaceSelects(interfaces) {
    const networkSelect = document.getElementById('network_interface_select');
    
    // Filter out loopback
    const usableInterfaces = interfaces.filter(i => i.type !== 'loopback');
    
    // Update network interface select
    if (networkSelect) {
        networkSelect.innerHTML = '<option value="">Sélectionnez une interface...</option>' +
            usableInterfaces.map(i => {
                const mac = i.mac ? ` | ${i.mac}` : '';
                const ip = i.ip ? ` - ${i.ip}` : '';
                return `<option value="${i.name}">${i.name} (${getInterfaceTypeLabel(i.type)}${ip}${mac})</option>`;
            }).join('');
    }
}

function exportLogs() {
    const source = document.getElementById('logs-source')?.value || 'all';
    const lines = document.getElementById('logs-lines')?.value || 100;
    const url = `/api/logs/export?lines=${encodeURIComponent(lines)}&service=${encodeURIComponent(source)}`;
    const link = document.createElement('a');
    link.href = url;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('Export des logs en cours...', 'info');
}

// Drag and drop handlers
let draggedItem = null;

function handleDragStart(e) {
    draggedItem = e.target.closest('.network-interface-item');
    draggedItem.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const target = e.target.closest('.network-interface-item');
    if (target && target !== draggedItem) {
        const list = document.getElementById('network-interfaces-list');
        const items = [...list.querySelectorAll('.network-interface-item')];
        const draggedIndex = items.indexOf(draggedItem);
        const targetIndex = items.indexOf(target);
        
        if (draggedIndex < targetIndex) {
            target.parentNode.insertBefore(draggedItem, target.nextSibling);
        } else {
            target.parentNode.insertBefore(draggedItem, target);
        }
    }
}

function handleDrop(e) {
    e.preventDefault();
}

function handleDragEnd(e) {
    if (draggedItem) {
        draggedItem.classList.remove('dragging');
        draggedItem = null;
        
        // Update priority badges
        const items = document.querySelectorAll('.network-interface-item');
        items.forEach((item, index) => {
            const badge = item.querySelector('.priority-badge');
            if (badge) badge.textContent = `#${index + 1}`;
        });
        
        // Update order array
        networkInterfacesOrder = [...items].map(item => item.dataset.interface);
    }
}

/**
 * Save interface priority order
 */
async function saveInterfacePriority() {
    try {
        const items = document.querySelectorAll('.network-interface-item');
        const interfacesOrder = [...items].map(item => item.dataset.interface);
        
        showToast('Application de la priorité...', 'info');
        
        const response = await fetch('/api/network/priority', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interfaces: interfacesOrder })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Priorité des interfaces mise à jour', 'success');
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Toggle network mode display
 */
function toggleNetworkMode() {
    const mode = document.querySelector('input[name="network_mode"]:checked').value;
    const staticConfig = document.getElementById('static-ip-config');
    
    if (mode === 'static') {
        staticConfig.style.display = 'block';
    } else {
        staticConfig.style.display = 'none';
    }
}

/**
 * Apply network configuration (DHCP or Static)
 */
async function applyNetworkConfig() {
    try {
        const iface = document.getElementById('network_interface_select').value;
        const mode = document.querySelector('input[name="network_mode"]:checked').value;
        
        if (!iface) {
            showToast('Veuillez sélectionner une interface', 'warning');
            return;
        }
        
        showToast(`Configuration de ${iface}...`, 'info');
        
        let response;
        
        if (mode === 'dhcp') {
            response = await fetch('/api/network/dhcp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ interface: iface })
            });
        } else {
            const ip = document.getElementById('network_static_ip').value;
            const gateway = document.getElementById('network_gateway').value;
            const dns = document.getElementById('network_dns').value;
            
            if (!ip || !gateway) {
                showToast('Veuillez remplir l\'adresse IP et la passerelle', 'warning');
                return;
            }
            
            response = await fetch('/api/network/static', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ interface: iface, ip, gateway, dns })
            });
        }
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration réseau appliquée', 'success');
            // Refresh interfaces after a delay
            setTimeout(loadNetworkInterfaces, 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// WiFi Simple Configuration Functions (for single WiFi adapter)
// ============================================================================

/**
 * Toggle WiFi simple static IP configuration visibility
 */
function toggleWifiSimpleIpMode() {
    const mode = document.querySelector('input[name="wifi_simple_ip_mode"]:checked')?.value;
    const staticConfig = document.getElementById('wifi-simple-static-config');
    if (staticConfig) {
        staticConfig.style.display = mode === 'static' ? '' : 'none';
    }
}

/**
 * Load WiFi simple status and config
 */
async function loadWifiSimpleStatus() {
    try {
        const response = await fetch('/api/wifi/simple/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            
            // Update status banner
            const statusEl = document.getElementById('wifi-simple-status');
            if (statusEl) {
                if (status.connected) {
                    statusEl.innerHTML = `
                        <div class="wifi-status-connected">
                            <i class="fas fa-check-circle"></i>
                            <span>Connecté à <strong>${status.ssid || 'Réseau WiFi'}</strong></span>
                            <span class="wifi-ip">${status.ip || ''}</span>
                        </div>
                    `;
                } else {
                    statusEl.innerHTML = `
                        <div class="wifi-status-disconnected">
                            <i class="fas fa-times-circle"></i>
                            <span>Non connecté</span>
                        </div>
                    `;
                }
            }
            
            // Pre-fill SSID from current connection if no saved config
            const ssidField = document.getElementById('wifi_simple_ssid');
            if (ssidField) {
                // Use saved config first, or current connection as fallback
                ssidField.value = status.saved_ssid || status.ssid || '';
            }
            
            // Password placeholder
            const pwdField = document.getElementById('wifi_simple_password');
            if (pwdField) {
                pwdField.value = '';
                pwdField.placeholder = status.has_saved_password ? '•••••••• (enregistré)' : 'Mot de passe WiFi';
            }
            
            // IP Mode
            const ipMode = status.ip_mode || 'dhcp';
            const ipModeRadio = document.querySelector(`input[name="wifi_simple_ip_mode"][value="${ipMode}"]`);
            if (ipModeRadio) {
                ipModeRadio.checked = true;
                toggleWifiSimpleIpMode();
            }
            
            // Static IP fields
            if (ipMode === 'static') {
                const staticIp = document.getElementById('wifi_simple_static_ip');
                const gateway = document.getElementById('wifi_simple_gateway');
                const dns = document.getElementById('wifi_simple_dns');
                if (staticIp) staticIp.value = status.static_ip || '';
                if (gateway) gateway.value = status.gateway || '';
                if (dns) dns.value = status.dns || '8.8.8.8';
            }
        }
    } catch (error) {
        console.error('Error loading WiFi simple status:', error);
    }
}

/**
 * Save WiFi simple configuration
 */
async function saveWifiSimpleConfig() {
    const ssid = document.getElementById('wifi_simple_ssid')?.value;
    const password = document.getElementById('wifi_simple_password')?.value;
    const ipMode = document.querySelector('input[name="wifi_simple_ip_mode"]:checked')?.value || 'dhcp';
    
    if (!ssid) {
        showToast('Veuillez entrer un SSID', 'error');
        return;
    }
    
    const config = {
        ssid: ssid,
        ip_mode: ipMode
    };
    
    // Only send password if user entered one
    if (password) {
        config.password = password;
    }
    
    if (ipMode === 'static') {
        config.static_ip = document.getElementById('wifi_simple_static_ip')?.value || '';
        config.gateway = document.getElementById('wifi_simple_gateway')?.value || '';
        config.dns = document.getElementById('wifi_simple_dns')?.value || '8.8.8.8';
    }
    
    try {
        const response = await fetch('/api/wifi/simple/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration WiFi enregistrée', 'success');
            loadWifiSimpleStatus();
        } else {
            showToast(data.message || 'Erreur lors de l\'enregistrement', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Connect to WiFi with simple config
 */
async function connectWifiSimple() {
    const ssid = document.getElementById('wifi_simple_ssid')?.value;
    const password = document.getElementById('wifi_simple_password')?.value;
    
    if (!ssid) {
        showToast('Veuillez entrer un SSID', 'error');
        return;
    }
    
    try {
        showToast('Connexion en cours...', 'info');
        
        const response = await fetch('/api/wifi/simple/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || 'Connexion réussie', 'success');
            // Wait a bit then reload status
            setTimeout(() => {
                loadWifiSimpleStatus();
                loadNetworkInterfaces();
            }, 3000);
        } else {
            showToast(data.message || 'Erreur de connexion', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

// ============================================================================
// WiFi Failover Functions
// ============================================================================

/**
 * Load WiFi status and show appropriate section (simple or failover)
 */
async function loadWifiConfig() {
    try {
        const response = await fetch('/api/wifi/failover/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            const wifiInterfaces = status.wifi_interfaces || [];
            
            const simpleSection = document.getElementById('wifi-simple-section');
            const failoverSection = document.getElementById('wifi-failover-section');
            
            if (wifiInterfaces.length >= 2) {
                // 2+ WiFi adapters: show failover config
                if (simpleSection) simpleSection.style.display = 'none';
                if (failoverSection) failoverSection.style.display = '';
                loadWifiFailoverStatus();
            } else if (wifiInterfaces.length === 1) {
                // 1 WiFi adapter: show simple config
                if (simpleSection) simpleSection.style.display = '';
                if (failoverSection) failoverSection.style.display = 'none';
                loadWifiSimpleStatus();
            } else {
                // No WiFi: hide both
                if (simpleSection) simpleSection.style.display = 'none';
                if (failoverSection) failoverSection.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading WiFi config:', error);
    }
}

/**
 * Load WiFi failover status and update UI
 */
async function loadWifiFailoverStatus() {
    try {
        const response = await fetch('/api/wifi/failover/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            
            // Check if we have at least 2 WiFi interfaces for failover to make sense
            const wifiInterfaces = status.wifi_interfaces || [];
            const failoverSection = document.getElementById('wifi-failover-section');
            const simpleSection = document.getElementById('wifi-simple-section');
            
            if (wifiInterfaces.length < 2) {
                // Less than 2 adapters: show simple config instead
                if (failoverSection) failoverSection.style.display = 'none';
                if (simpleSection && wifiInterfaces.length === 1) {
                    simpleSection.style.display = '';
                    loadWifiSimpleStatus();
                }
                console.log('[WiFi] Showing simple config -', wifiInterfaces.length, 'interface(s) detected');
                return;
            }
            
            // Show failover section
            if (failoverSection) failoverSection.style.display = '';
            if (simpleSection) simpleSection.style.display = 'none';
            
            // Update hardware failover toggle
            const hwToggle = document.getElementById('wifi_hardware_failover_enabled');
            const hwToggleStatus = document.getElementById('wifi-hw-failover-status');
            if (hwToggle) {
                hwToggle.checked = status.hardware_failover_enabled !== false;
                if (hwToggleStatus) {
                    hwToggleStatus.textContent = hwToggle.checked ? 'Activé' : 'Désactivé';
                }
            }
            
            // Update network failover toggle
            const netToggle = document.getElementById('wifi_network_failover_enabled');
            const netToggleStatus = document.getElementById('wifi-net-failover-status');
            if (netToggle) {
                netToggle.checked = status.network_failover_enabled !== false;
                if (netToggleStatus) {
                    netToggleStatus.textContent = netToggle.checked ? 'Activé' : 'Désactivé';
                }
            }
            
            // Update interface selects
            const primarySelect = document.getElementById('wifi_primary_interface');
            const secondarySelect = document.getElementById('wifi_secondary_interface');
            if (primarySelect) primarySelect.value = status.primary_interface || 'wlan1';
            if (secondarySelect) secondarySelect.value = status.secondary_interface || 'wlan0';
            
            // Update primary SSID/password
            const primarySsid = document.getElementById('wifi_primary_ssid');
            if (primarySsid) primarySsid.value = status.primary_ssid || '';
            
            // Show password placeholder if password is configured (don't show actual password)
            const primaryPwd = document.getElementById('wifi_primary_password');
            if (primaryPwd) {
                primaryPwd.value = '';  // Always clear (don't expose password)
                primaryPwd.placeholder = status.has_primary_password ? '•••••••• (enregistré)' : 'Aucun mot de passe';
            }
            
            // Update secondary SSID/password
            const secondarySsid = document.getElementById('wifi_secondary_ssid');
            if (secondarySsid) secondarySsid.value = status.secondary_ssid || '';
            
            const secondaryPwd = document.getElementById('wifi_secondary_password');
            if (secondaryPwd) {
                secondaryPwd.value = '';  // Always clear
                secondaryPwd.placeholder = status.has_secondary_password ? '•••••••• (enregistré)' : 'Aucun mot de passe';
            }
            
            // Update IP mode
            const ipMode = status.ip_mode || 'dhcp';
            const ipModeRadio = document.querySelector(`input[name="wifi_failover_ip_mode"][value="${ipMode}"]`);
            if (ipModeRadio) {
                ipModeRadio.checked = true;
                toggleWifiFailoverIpMode();
            }
            
            // Update static IP fields
            if (ipMode === 'static') {
                const staticIp = document.getElementById('wifi_failover_static_ip');
                const gateway = document.getElementById('wifi_failover_gateway');
                const dns = document.getElementById('wifi_failover_dns');
                if (staticIp) staticIp.value = status.static_ip || '';
                if (gateway) gateway.value = status.gateway || '';
                if (dns) dns.value = status.dns || '8.8.8.8';
            }

            const checkIntervalInput = document.getElementById('wifi_failover_check_interval');
            if (checkIntervalInput) {
                checkIntervalInput.value = status.check_interval || 30;
            }
            
            // Update status banner
            updateWifiFailoverStatusBanner(status);
            
            // Update interfaces grid
            updateWifiInterfacesGrid(status.wifi_interfaces, status.active_interface);
        }
    } catch (error) {
        console.error('Error loading WiFi failover status:', error);
        showToast('Erreur chargement statut WiFi', 'error');
    }
}

/**
 * Update the WiFi failover status banner
 */
function updateWifiFailoverStatusBanner(status) {
    const banner = document.getElementById('wifi-failover-status');
    if (!banner) return;
    
    let html = '';
    
    if (status.active_interface) {
        const isPrimaryIface = status.active_interface === status.primary_interface;
        const isPrimarySsid = status.active_ssid === status.primary_ssid;
        
        // Determine badge and class
        let modeClass = 'primary';
        let modeLabel = 'Normal';
        let modeIcon = 'fa-check-circle';
        
        if (!isPrimaryIface && !isPrimarySsid) {
            modeClass = 'failover';
            modeLabel = 'Double Failover';
            modeIcon = 'fa-exclamation-triangle';
        } else if (!isPrimaryIface) {
            modeClass = 'failover';
            modeLabel = 'HW Failover';
            modeIcon = 'fa-microchip';
        } else if (!isPrimarySsid) {
            modeClass = 'failover';
            modeLabel = 'Net Failover';
            modeIcon = 'fa-broadcast-tower';
        }
        
        html = `
            <div class="wifi-status-banner ${modeClass}">
                <div class="wifi-status-icon">
                    <i class="fas fa-wifi"></i>
                </div>
                <div class="wifi-status-info">
                    <div class="wifi-status-main">
                        <strong>${status.active_interface}</strong> 
                        <span class="mode-badge ${modeClass}"><i class="fas ${modeIcon}"></i> ${modeLabel}</span>
                    </div>
                    <div class="wifi-status-details">
                        ${status.active_ssid ? `<span><i class="fas fa-broadcast-tower"></i> ${status.active_ssid}</span>` : ''}
                        ${status.active_ip ? `<span><i class="fas fa-network-wired"></i> ${status.active_ip}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    } else {
        html = `
            <div class="wifi-status-banner disconnected">
                <div class="wifi-status-icon">
                    <i class="fas fa-wifi-slash"></i>
                </div>
                <div class="wifi-status-info">
                    <div class="wifi-status-main">
                        <strong>WiFi Déconnecté</strong>
                    </div>
                    <div class="wifi-status-details">
                        <span>Aucune interface WiFi active</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    banner.innerHTML = html;
}

/**
 * Update the WiFi interfaces grid
 */
function updateWifiInterfacesGrid(interfaces, activeInterface) {
    const grid = document.getElementById('wifi-interfaces-grid');
    if (!grid || !interfaces) return;
    
    const html = interfaces.map(iface => {
        const isActive = iface.name === activeInterface;
        const isAvailable = iface.phy_exists;
        const statusClass = isActive ? 'active' : (isAvailable ? 'available' : 'unavailable');
        const statusLabel = isActive ? 'Actif' : (isAvailable ? 'Disponible' : 'Non détecté');
        const typeLabel = iface.is_usb ? 'USB Dongle' : 'Intégré';
        
        return `
            <div class="wifi-interface-card ${statusClass}">
                <div class="interface-header">
                    <span class="interface-name">${iface.name}</span>
                    <span class="interface-type">${typeLabel}</span>
                </div>
                <div class="interface-body">
                    <div class="interface-status">
                        <span class="status-indicator ${statusClass}"></span>
                        <span>${statusLabel}</span>
                    </div>
                    ${iface.ssid ? `<div class="interface-ssid"><i class="fas fa-broadcast-tower"></i> ${iface.ssid}</div>` : ''}
                    ${iface.ip ? `<div class="interface-ip"><i class="fas fa-network-wired"></i> ${iface.ip}</div>` : ''}
                    <div class="interface-mac"><i class="fas fa-fingerprint"></i> ${iface.mac || 'N/A'}</div>
                </div>
            </div>
        `;
    }).join('');
    
    grid.innerHTML = html || '<p class="text-muted">Aucune interface WiFi détectée</p>';
}

/**
 * Toggle WiFi failover IP mode display
 */
function toggleWifiFailoverIpMode() {
    const mode = document.querySelector('input[name="wifi_failover_ip_mode"]:checked')?.value || 'dhcp';
    const staticConfig = document.getElementById('wifi-failover-static-config');
    if (staticConfig) {
        staticConfig.style.display = mode === 'static' ? 'block' : 'none';
    }
}

/**
 * Save WiFi failover configuration
 */
async function saveWifiFailoverConfig() {
    try {
        // Debug: check if elements exist
        const elements = {
            hw_toggle: document.getElementById('wifi_hardware_failover_enabled'),
            primary_iface: document.getElementById('wifi_primary_interface'),
            secondary_iface: document.getElementById('wifi_secondary_interface'),
            net_toggle: document.getElementById('wifi_network_failover_enabled'),
            primary_ssid: document.getElementById('wifi_primary_ssid'),
            primary_pwd: document.getElementById('wifi_primary_password'),
            secondary_ssid: document.getElementById('wifi_secondary_ssid'),
            secondary_pwd: document.getElementById('wifi_secondary_password'),
            ip_mode: document.querySelector('input[name="wifi_failover_ip_mode"]:checked'),
            static_ip: document.getElementById('wifi_failover_static_ip'),
            gateway: document.getElementById('wifi_failover_gateway'),
            dns: document.getElementById('wifi_failover_dns'),
            check_interval: document.getElementById('wifi_failover_check_interval')
        };
        
        console.log('[WiFi Config] Elements found:', elements);
        
        const config = {
            // Hardware failover
            hardware_failover_enabled: elements.hw_toggle?.checked ?? true,
            primary_interface: elements.primary_iface?.value || 'wlan1',
            secondary_interface: elements.secondary_iface?.value || 'wlan0',
            
            // Network failover
            network_failover_enabled: elements.net_toggle?.checked ?? true,
            primary_ssid: elements.primary_ssid?.value || '',
            primary_password: elements.primary_pwd?.value || '',
            secondary_ssid: elements.secondary_ssid?.value || '',
            secondary_password: elements.secondary_pwd?.value || '',
            
            // IP config
            ip_mode: elements.ip_mode?.value || 'dhcp',
            static_ip: elements.static_ip?.value || '',
            gateway: elements.gateway?.value || '',
            dns: elements.dns?.value || '8.8.8.8',
            check_interval: parseInt(elements.check_interval?.value, 10) || 30
        };
        
        console.log('[WiFi Config] Saving config:', config);
        
        if (!config.primary_ssid) {
            showToast('Veuillez entrer un SSID principal', 'warning');
            return false;
        }
        
        showToast('Enregistrement...', 'info');
        
        const response = await fetch('/api/wifi/failover/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration WiFi enregistrée', 'success');
            return true;
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
            return false;
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
        return false;
    }
}

/**
 * Apply WiFi failover - connect the appropriate interface
 */
async function applyWifiFailover() {
    try {
        // First save config
        const saved = await saveWifiFailoverConfig();
        if (!saved) return;
        
        showToast('Application de la configuration WiFi...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            const result = data.result;
            
            switch (result.action) {
                case 'none':
                    showToast(result.reason, 'info');
                    break;
                case 'connected_primary':
                    showToast(result.reason, 'success');
                    break;
                case 'hardware_failover':
                    showToast(`⚙️ ${result.reason}`, 'warning');
                    break;
                case 'network_failover':
                    showToast(`📡 ${result.reason}`, 'warning');
                    break;
                case 'full_failover':
                    showToast(`⚠️ ${result.reason}`, 'warning');
                    break;
                default:
                    showToast(result.reason, 'success');
            }
            
            // Refresh status after a delay
            setTimeout(loadWifiFailoverStatus, 3000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply only hardware failover settings (interface priority)
 */
async function applyHardwareFailover() {
    try {
        const config = {
            hardware_failover_enabled: document.getElementById('wifi_hardware_failover_enabled')?.checked ?? true,
            primary_interface: document.getElementById('wifi_primary_interface')?.value || 'wlan1',
            secondary_interface: document.getElementById('wifi_secondary_interface')?.value || 'wlan0'
        };
        
        showToast('Application du failover hardware...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply/hardware', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            let message = 'Failover hardware appliqué';
            if (data.auto_config?.action === 'cloned_and_connected') {
                message += ` - ${data.auto_config.ssid} cloné et connecté sur ${config.secondary_interface}`;
            } else if (data.auto_config?.action === 'cloned') {
                message += ` - Configuration clonée vers ${config.secondary_interface}`;
            }
            showToast(message, 'success');
            loadWifiFailoverStatus();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply only network failover settings (SSID configuration)
 */
async function applyNetworkFailover() {
    try {
        const primarySsid = document.getElementById('wifi_primary_ssid')?.value;
        
        if (!primarySsid) {
            showToast('Veuillez entrer un SSID principal', 'warning');
            return;
        }
        
        const config = {
            network_failover_enabled: document.getElementById('wifi_network_failover_enabled')?.checked ?? true,
            primary_ssid: primarySsid,
            primary_password: document.getElementById('wifi_primary_password')?.value || '',
            secondary_ssid: document.getElementById('wifi_secondary_ssid')?.value || '',
            secondary_password: document.getElementById('wifi_secondary_password')?.value || ''
        };
        
        showToast('Application du failover réseau...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply/network', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            let message = 'Failover réseau appliqué';
            if (data.connection?.success) {
                message += ` - Connecté à ${primarySsid}`;
            }
            showToast(message, 'success');
            setTimeout(loadWifiFailoverStatus, 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply only IP configuration settings
 */
async function applyIpConfig() {
    try {
        const ipMode = document.querySelector('input[name="wifi_failover_ip_mode"]:checked')?.value || 'dhcp';
        
        const config = {
            ip_mode: ipMode,
            static_ip: document.getElementById('wifi_failover_static_ip')?.value || '',
            gateway: document.getElementById('wifi_failover_gateway')?.value || '',
            dns: document.getElementById('wifi_failover_dns')?.value || '8.8.8.8'
        };
        
        if (ipMode === 'static' && !config.static_ip) {
            showToast('Veuillez entrer une adresse IP statique', 'warning');
            return;
        }
        
        showToast('Application de la configuration IP...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply/ip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            const ifaceCount = data.interfaces?.length || 0;
            showToast(`Configuration IP appliquée à ${ifaceCount} interface(s)`, 'success');
            setTimeout(loadWifiFailoverStatus, 2000);
            setTimeout(loadNetworkInterfaces, 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Scan WiFi networks for a specific field
 */
async function scanWifiForField(fieldId) {
    try {
        const listId = fieldId.replace('_ssid', '-ssid-list').replace('wifi_', 'wifi-');
        const listContainer = document.getElementById(listId);
        
        if (!listContainer) {
            console.error('List container not found:', listId);
            return;
        }
        
        listContainer.innerHTML = '<div class="detection-item"><i class="fas fa-spinner fa-spin"></i> Scan en cours...</div>';
        listContainer.classList.add('visible');
        listContainer.style.display = 'block';
        
        const response = await fetch('/api/wifi/scan');
        const data = await response.json();
        
        if (data.success && data.networks.length > 0) {
            listContainer.innerHTML = data.networks.map(net => `
                <div class="detection-item wifi-network" onclick="selectWifiForField('${fieldId}', '${escapeHtml(net.ssid)}')">
                    <span class="wifi-ssid">${escapeHtml(net.ssid)}</span>
                    <span class="wifi-signal">${net.signal || ''} ${net.security || ''}</span>
                </div>
            `).join('');
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucun réseau trouvé</span></div>';
        }
        
        // Auto-hide after 30 seconds
        setTimeout(() => {
            listContainer.style.display = 'none';
            listContainer.classList.remove('visible');
        }, 30000);
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Select a WiFi network for a specific field
 */
function selectWifiForField(fieldId, ssid) {
    const field = document.getElementById(fieldId);
    if (field) field.value = ssid;
    
    const listId = fieldId.replace('_ssid', '-ssid-list').replace('wifi_', 'wifi-');
    const listContainer = document.getElementById(listId);
    if (listContainer) {
        listContainer.style.display = 'none';
        listContainer.classList.remove('visible');
    }
    
    // Focus password field
    const passwordFieldId = fieldId.replace('_ssid', '_password');
    const passwordField = document.getElementById(passwordFieldId);
    if (passwordField) passwordField.focus();
}

// ============================================================================
// Ethernet/WiFi Auto-Management Functions
// ============================================================================

/**
 * Load Ethernet and WiFi override status
 */
async function loadEthernetWifiStatus() {
    try {
        const response = await fetch('/api/network/wifi/override');
        const data = await response.json();
        
        if (data.success) {
            // Update Ethernet status
            const ethBadge = document.getElementById('eth-status-badge');
            if (ethBadge) {
                if (data.ethernet.connected) {
                    ethBadge.textContent = 'Connecté';
                    ethBadge.className = 'badge badge-success';
                } else if (data.ethernet.present) {
                    ethBadge.textContent = 'Déconnecté';
                    ethBadge.className = 'badge badge-warning';
                } else {
                    ethBadge.textContent = 'Non détecté';
                    ethBadge.className = 'badge badge-secondary';
                }
            }
            
            // Update wlan0 status badge
            const wlan0Badge = document.getElementById('wlan0-status-badge');
            if (wlan0Badge) {
                if (data.wlan0) {
                    if (data.wlan0.ap_mode) {
                        wlan0Badge.textContent = 'Mode AP';
                        wlan0Badge.className = 'badge badge-info';
                    } else if (data.wlan0.connected) {
                        wlan0Badge.textContent = 'Connecté';
                        wlan0Badge.className = 'badge badge-success';
                    } else if (data.wlan0.managed) {
                        wlan0Badge.textContent = 'Désactivé (Eth prioritaire)';
                        wlan0Badge.className = 'badge badge-secondary';
                    } else {
                        wlan0Badge.textContent = 'Déconnecté';
                        wlan0Badge.className = 'badge badge-warning';
                    }
                } else {
                    wlan0Badge.textContent = 'Non détecté';
                    wlan0Badge.className = 'badge badge-secondary';
                }
            }
            
            // Update WiFi override checkbox
            const overrideCheckbox = document.getElementById('wifi_manual_override');
            if (overrideCheckbox) {
                overrideCheckbox.checked = data.override;
            }
            
            // Update status text
            const overrideStatus = document.getElementById('wifi-override-status');
            if (overrideStatus) {
                overrideStatus.textContent = data.override ? 'Forcé ON' : 'Auto';
                overrideStatus.className = `control-status ${data.override ? 'status-active' : ''}`;
            }
        }
    } catch (error) {
        console.error('Error loading Ethernet/WiFi status:', error);
    }
}

/**
 * Apply WiFi manual override setting
 */
async function applyWifiOverride() {
    const checkbox = document.getElementById('wifi_manual_override');
    const enable = checkbox ? checkbox.checked : false;
    
    try {
        showToast('Application en cours...', 'info');
        
        const response = await fetch('/api/network/wifi/override', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const action = data.wifi_management?.action || '';
            let message = enable ? 'WiFi forcé actif' : 'Mode automatique activé';
            if (action === 'reconnected') {
                message = 'WiFi reconnecté';
            } else if (action === 'disabled') {
                message = 'WiFi désactivé (Ethernet prioritaire)';
            }
            showToast(message, 'success');
            // Reload status to reflect changes
            loadEthernetWifiStatus();
            loadNetworkInterfaces();
        } else {
            showToast(data.message || data.error || 'Erreur', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

// Legacy function name for compatibility
async function setWifiManualOverride() {
    await applyWifiOverride();
}

// ============================================================================
// Access Point (AP) Functions
// ============================================================================

/**
 * Load Access Point status and configuration
 */
async function loadApStatus() {
    try {
        const response = await fetch('/api/network/ap/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            const config = data.config;
            
            // Update status banner
            const statusBanner = document.getElementById('ap-status-banner');
            const statusIcon = document.getElementById('ap-status-icon');
            const statusText = document.getElementById('ap-status-text');
            const clientsCount = document.getElementById('ap-clients-count');
            
            if (status.active) {
                statusBanner.className = 'ap-status-banner ap-active';
                statusIcon.className = 'fas fa-circle status-active';
                statusText.textContent = `Point d'accès actif: ${status.ssid} (${status.ip})`;
                if (clientsCount) {
                    clientsCount.style.display = 'inline';
                    clientsCount.textContent = `${status.clients} client${status.clients !== 1 ? 's' : ''}`;
                }
            } else {
                statusBanner.className = 'ap-status-banner ap-inactive';
                statusIcon.className = 'fas fa-circle status-inactive';
                statusText.textContent = 'Point d\'accès inactif';
                if (clientsCount) clientsCount.style.display = 'none';
            }
            
            // Update form fields from config (Meeting values)
            const apSsidField = document.getElementById('ap_ssid');
            const apPasswordField = document.getElementById('ap_password');
            const apIpField = document.getElementById('ap_ip');
            
            if (apSsidField && config.ap_ssid) apSsidField.value = config.ap_ssid;
            if (apPasswordField && config.ap_password) apPasswordField.value = config.ap_password;
            if (apIpField && config.ap_ip) apIpField.value = config.ap_ip;
            
            // Update buttons visibility
            const btnStart = document.getElementById('btn-start-ap');
            const btnStop = document.getElementById('btn-stop-ap');
            if (btnStart) btnStart.style.display = status.active ? 'none' : 'inline-flex';
            if (btnStop) btnStop.style.display = status.active ? 'inline-flex' : 'none';
            
            // Show/hide warning
            const warningAlert = document.getElementById('ap-warning-alert');
            if (warningAlert) {
                warningAlert.style.display = status.active ? 'flex' : 'none';
            }
            
            // If no config from Meeting, try to load it (silently)
            if (!config.ap_ssid || !config.ap_password) {
                loadApConfigFromMeeting(true);
            }
        }
    } catch (error) {
        console.error('Error loading AP status:', error);
        const statusText = document.getElementById('ap-status-text');
        if (statusText) statusText.textContent = 'Erreur de chargement';
    }
}

/**
 * Save Access Point configuration
 */
async function saveApConfig() {
    const config = {
        ap_ssid: document.getElementById('ap_ssid').value,
        ap_password: document.getElementById('ap_password').value,
        ap_channel: parseInt(document.getElementById('ap_channel').value) || 7,
        ap_ip: document.getElementById('ap_ip').value,
        dhcp_range_start: document.getElementById('dhcp_range_start').value,
        dhcp_range_end: document.getElementById('dhcp_range_end').value
    };
    
    // Validation
    if (!config.ap_ssid) {
        showToast('Le SSID est requis', 'error');
        return false;
    }
    if (config.ap_password && config.ap_password.length < 8) {
        showToast('Le mot de passe doit faire au moins 8 caractères', 'error');
        return false;
    }
    
    try {
        const response = await fetch('/api/network/ap/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration AP enregistrée', 'success');
            return true;
        } else {
            showToast(data.message || 'Erreur sauvegarde', 'error');
            return false;
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
        return false;
    }
}

/**
 * Load AP configuration from Meeting (auto-called if no config)
 */
async function loadApConfigFromMeeting(silent = false) {
    try {
        if (!silent) showToast('Récupération des paramètres Meeting...', 'info');
        
        const response = await fetch('/api/network/ap/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from_meeting: true })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (!silent) showToast('Paramètres AP récupérés depuis Meeting', 'success');
            // Update form fields directly from response
            if (data.config) {
                const apSsidField = document.getElementById('ap_ssid');
                const apPasswordField = document.getElementById('ap_password');
                const apChannelField = document.getElementById('ap_channel');
                const apChannelDisplayField = document.getElementById('ap_channel_display');
                
                if (apSsidField && data.config.ap_ssid) apSsidField.value = data.config.ap_ssid;
                if (apPasswordField && data.config.ap_password) apPasswordField.value = data.config.ap_password;
                if (apChannelField && data.config.ap_channel) {
                    apChannelField.value = data.config.ap_channel;
                    // Update display (map channel to frequency)
                    const freqMap = {1: 2412, 6: 2437, 11: 2462};
                    const freq = freqMap[data.config.ap_channel] || (2407 + data.config.ap_channel * 5);
                    if (apChannelDisplayField) {
                        apChannelDisplayField.value = `Canal ${data.config.ap_channel} (${freq} MHz)`;
                    }
                }
            }
        } else {
            if (!silent) showToast(data.message || 'Erreur récupération Meeting', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Start Access Point
 */
async function startAccessPoint() {
    // Check if Meeting config is available
    const apSsid = document.getElementById('ap_ssid')?.value;
    const apPassword = document.getElementById('ap_password')?.value;
    const apChannel = document.getElementById('ap_channel')?.value || 11;
    
    // Check for placeholder values
    if (!apSsid || apSsid.includes('non configuré')) {
        showToast('Configuration AP manquante. Vérifiez que Meeting est provisionné.', 'error');
        return;
    }
    if (!apPassword || apPassword.includes('non configuré')) {
        showToast('Mot de passe AP manquant. Vérifiez que Meeting est provisionné.', 'error');
        return;
    }
    
    try {
        showToast('Démarrage du point d\'accès...', 'info');
        
        const response = await fetch('/api/network/ap/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ssid: apSsid,
                password: apPassword,
                channel: parseInt(apChannel)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(loadApStatus, 2000);
            setTimeout(loadEthernetWifiStatus, 2000);
        } else {
            showToast(data.message || 'Erreur démarrage AP', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Stop Access Point
 */
async function stopAccessPoint() {
    try {
        showToast('Arrêt du point d\'accès...', 'info');
        
        const response = await fetch('/api/network/ap/stop', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(loadApStatus, 1000);
            setTimeout(loadEthernetWifiStatus, 1000);
        } else {
            showToast(data.message || 'Erreur arrêt AP', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Toggle collapsible section
 */
function toggleSection(header) {
    const section = header.closest('.collapsed-section');
    section.classList.toggle('expanded');
}

// ============================================================================
// LED Functions
// ============================================================================

/**
 * Set LED state
 * Always persists to boot config by default
 */
async function setLedState(led, enabled) {
    try {
        // Always persist to boot config for LEDs to be disabled from boot
        const response = await fetch('/api/leds/set', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                led, 
                enabled, 
                persist: true  // Always persist for boot-time effect
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update visual indicator
            const ledIcon = document.querySelector(`.led-icon.${led}`);
            if (ledIcon) {
                ledIcon.classList.toggle('on', enabled);
                ledIcon.classList.toggle('off', !enabled);
            }
            return true;
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
            return false;
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
        return false;
    }
}

// ============================================================================
// GPU Memory Functions
// ============================================================================

/**
 * Set GPU memory allocation
 */
async function setGpuMem() {
    try {
        const gpuMem = document.getElementById('gpu_mem').value;
        
        if (!confirm(`Modifier la mémoire GPU à ${gpuMem} Mo ?\nUn redémarrage sera nécessaire.`)) {
            return;
        }
        
        showToast('Application en cours...', 'info');
        
        const response = await fetch('/api/gpu', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ memory: parseInt(gpuMem) })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            if (data.requires_reboot || data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 800);
            }
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// Power Management Functions (Energy Saving)
// ============================================================================

// Track if power settings have changed
let powerSettingsChanged = false;

/**
 * Mark that power settings have been modified
 */
function markPowerSettingsChanged() {
    powerSettingsChanged = true;
    const applyBtn = document.getElementById('btn-apply-power');
    const indicator = document.getElementById('power-changes-indicator');
    
    if (applyBtn) {
        applyBtn.disabled = false;
        applyBtn.classList.add('btn-warning');
    }
    if (indicator) {
        indicator.style.display = 'inline-flex';
    }
    
    // Update visual indicators for LEDs
    updateLedVisualState();
}

/**
 * Update LED visual state based on checkbox
 */
function updateLedVisualState() {
    const pwrChecked = document.getElementById('led_pwr')?.checked;
    const actChecked = document.getElementById('led_act')?.checked;
    
    const pwrIcon = document.querySelector('.led-icon.pwr');
    const actIcon = document.querySelector('.led-icon.act');
    
    if (pwrIcon) {
        pwrIcon.classList.toggle('on', pwrChecked);
        pwrIcon.classList.toggle('off', !pwrChecked);
    }
    if (actIcon) {
        actIcon.classList.toggle('on', actChecked);
        actIcon.classList.toggle('off', !actChecked);
    }
}

/**
 * Reset power settings changed state
 */
function resetPowerSettingsChanged() {
    powerSettingsChanged = false;
    const applyBtn = document.getElementById('btn-apply-power');
    const indicator = document.getElementById('power-changes-indicator');
    
    if (applyBtn) {
        applyBtn.disabled = true;
        applyBtn.classList.remove('btn-warning');
    }
    if (indicator) {
        indicator.style.display = 'none';
    }
}

/**
 * Load power management status on tab switch
 */
async function loadPowerStatus() {
    try {
        const response = await fetch('/api/power/status');
        const data = await response.json();
        
        if (data.success) {
            const current = data.current;
            const bootConfig = data.boot_config;
            
            // Update UI with boot config state (what will be active after reboot)
            document.getElementById('power_bt').checked = bootConfig.bluetooth_enabled;
            document.getElementById('power_hdmi').checked = bootConfig.hdmi_enabled;
            document.getElementById('power_audio').checked = bootConfig.audio_enabled;
            
            // WiFi integrated
            const wifiCheckbox = document.getElementById('power_wifi');
            if (wifiCheckbox) {
                wifiCheckbox.checked = bootConfig.wifi_enabled !== false;
            }
            
            // LEDs
            const ledPwr = document.getElementById('led_pwr');
            const ledAct = document.getElementById('led_act');
            const ledCameraCsi = document.getElementById('led_camera_csi');
            if (ledPwr) ledPwr.checked = bootConfig.pwr_led_enabled !== false;
            if (ledAct) ledAct.checked = bootConfig.act_led_enabled !== false;
            if (ledCameraCsi) ledCameraCsi.checked = bootConfig.camera_led_csi_enabled !== false;
            
            // Update status texts
            updatePowerStatusText('bt', bootConfig.bluetooth_enabled);
            updatePowerStatusText('hdmi', bootConfig.hdmi_enabled);
            updatePowerStatusText('audio', bootConfig.audio_enabled);
            updatePowerStatusText('wifi-integrated', bootConfig.wifi_enabled !== false);
            
            // Update LED visual state
            updateLedVisualState();
            
            // Update estimated savings
            const savingsElement = document.getElementById('estimated-savings-ma');
            if (savingsElement) {
                savingsElement.textContent = `${current.estimated_savings_ma} mA`;
            }
        }
        
        // Load services status separately (from boot-config endpoint)
        const bootResponse = await fetch('/api/power/boot-config');
        const bootData = await bootResponse.json();
        
        if (bootData.success && bootData.services) {
            const services = bootData.services;
            
            // Update service checkboxes
            const serviceCheckboxes = {
                'service_modemmanager': services.modemmanager?.enabled,
                'service_avahi': services.avahi?.enabled,
                'service_cloudinit': services.cloudinit?.enabled,
                'service_serial': services.serial?.enabled,
                'service_tty1': services.tty1?.enabled,
                'service_udisks2': services.udisks2?.enabled
            };
            
            for (const [id, enabled] of Object.entries(serviceCheckboxes)) {
                const checkbox = document.getElementById(id);
                if (checkbox && enabled !== null) {
                    checkbox.checked = enabled;
                }
            }
            
            // Update service status texts
            updateServiceStatusText('modemmanager', services.modemmanager?.enabled);
            updateServiceStatusText('avahi', services.avahi?.enabled);
            updateServiceStatusText('cloudinit', services.cloudinit?.enabled);
            updateServiceStatusText('serial', services.serial?.enabled);
            updateServiceStatusText('tty1', services.tty1?.enabled);
            updateServiceStatusText('udisks2', services.udisks2?.enabled);
        }
        
        // Reset changed state after loading
        resetPowerSettingsChanged();
        
    } catch (error) {
        console.error('Error loading power status:', error);
    }
}

/**
 * Update status text for services
 */
function updateServiceStatusText(service, enabled) {
    const statusElement = document.getElementById(`${service}-status`);
    if (!statusElement) return;
    
    // Keep the original description but add status icon
    const descriptions = {
        'modemmanager': 'Gestion modems 3G/4G (inutile sans modem)',
        'avahi': 'Découverte réseau Bonjour/Zeroconf',
        'cloudinit': 'Provisioning cloud (inutile hors cloud)',
        'serial': 'Getty sur port série (debug uniquement)',
        'tty1': 'Login sur écran HDMI (inutile si headless)',
        'udisks2': 'Automontage disques USB'
    };
    
    const description = descriptions[service] || '';
    const icon = enabled 
        ? '<i class="fas fa-check-circle" style="color: var(--success-color);"></i>' 
        : '<i class="fas fa-times-circle" style="color: var(--danger-color);"></i>';
    
    statusElement.innerHTML = `${icon} ${description}`;
}

/**
 * Update status text for power components
 */
function updatePowerStatusText(component, enabled) {
    const statusElement = document.getElementById(`${component}-status`);
    if (!statusElement) return;
    
    if (enabled) {
        statusElement.innerHTML = '<i class="fas fa-check-circle" style="color: var(--success-color);"></i> Activé';
    } else {
        statusElement.innerHTML = '<i class="fas fa-times-circle" style="color: var(--danger-color);"></i> Désactivé';
    }
}

/**
 * Apply all power settings at once
 */
async function applyPowerSettings() {
    const applyBtn = document.getElementById('btn-apply-power');
    const originalText = applyBtn ? applyBtn.innerHTML : '';
    
    // Show a full-screen loading overlay
    const overlay = document.createElement('div');
    overlay.id = 'power-settings-overlay';
    overlay.innerHTML = `
        <div class="power-overlay-content">
            <div class="power-spinner">
                <div class="spinner-ring"></div>
                <i class="bi bi-gear-fill power-icon"></i>
            </div>
            <h2>Application des paramètres</h2>
            <p class="power-status">Configuration des services système...</p>
            <p class="power-hint">Cette opération peut prendre quelques secondes</p>
        </div>
    `;
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('visible'));
    
    try {
        // Disable button
        if (applyBtn) {
            applyBtn.disabled = true;
            applyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Application...';
        }
        
        // Gather all settings (hardware + services)
        const settings = {
            // Hardware settings - LEDs
            led_pwr: document.getElementById('led_pwr')?.checked ?? true,
            led_act: document.getElementById('led_act')?.checked ?? true,
            led_camera_csi: document.getElementById('led_camera_csi')?.checked ?? true,
            // Hardware settings - Components
            bluetooth: document.getElementById('power_bt')?.checked ?? true,
            wifi: document.getElementById('power_wifi')?.checked ?? true,
            hdmi: document.getElementById('power_hdmi')?.checked ?? true,
            audio: document.getElementById('power_audio')?.checked ?? true,
            // Service settings
            service_modemmanager: document.getElementById('service_modemmanager')?.checked ?? true,
            service_avahi: document.getElementById('service_avahi')?.checked ?? true,
            service_cloudinit: document.getElementById('service_cloudinit')?.checked ?? true,
            service_serial: document.getElementById('service_serial')?.checked ?? true,
            service_tty1: document.getElementById('service_tty1')?.checked ?? true,
            service_udisks2: document.getElementById('service_udisks2')?.checked ?? true
        };
        
        // Send all settings to backend
        const response = await fetch('/api/power/apply-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        
        const data = await response.json();
        
        // Remove overlay
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 300);
        
        if (data.success) {
            showToast(`Paramètres enregistrés! Économies estimées: ${data.estimated_savings_ma} mA`, 'success');
            resetPowerSettingsChanged();
            
            if (data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 800);
            }
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        // Remove overlay on error
        overlay.classList.remove('visible');
        setTimeout(() => overlay.remove(), 300);
        showToast(`Erreur: ${error.message}`, 'error');
    } finally {
        // Restore button
        if (applyBtn) {
            applyBtn.disabled = false;
            applyBtn.innerHTML = originalText || '<i class="bi bi-check-lg me-2"></i>Appliquer les changements';
        }
    }
}

/**
 * Show reboot overlay with countdown and auto-reconnect detection
 */
function showRebootOverlay() {
    // Remove existing overlay if any
    const existingOverlay = document.getElementById('reboot-overlay');
    if (existingOverlay) existingOverlay.remove();
    
    // Create overlay HTML
    const overlay = document.createElement('div');
    overlay.id = 'reboot-overlay';
    overlay.innerHTML = `
        <div class="reboot-overlay-content">
            <div class="reboot-spinner">
                <div class="spinner-ring"></div>
                <i class="bi bi-arrow-repeat reboot-icon"></i>
            </div>
            <h2>Redémarrage en cours</h2>
            <p class="reboot-status" id="reboot-status">Arrêt du système...</p>
            <div class="reboot-progress-container">
                <div class="reboot-progress-bar" id="reboot-progress-bar"></div>
            </div>
            <div class="reboot-countdown" id="reboot-countdown">
                <span class="countdown-value" id="countdown-value">60</span>
                <span class="countdown-label">secondes</span>
            </div>
            <p class="reboot-hint" id="reboot-hint">Le système va redémarrer automatiquement...</p>
        </div>
    `;
    
    document.body.appendChild(overlay);
    
    // Animation entrance
    requestAnimationFrame(() => {
        overlay.classList.add('visible');
    });
    
    return overlay;
}

/**
 * Update reboot overlay progress
 */
function updateRebootProgress(elapsed, total, status, hint) {
    const progressBar = document.getElementById('reboot-progress-bar');
    const countdownValue = document.getElementById('countdown-value');
    const statusEl = document.getElementById('reboot-status');
    const hintEl = document.getElementById('reboot-hint');
    
    const remaining = Math.max(0, total - elapsed);
    const percent = Math.min(100, (elapsed / total) * 100);
    
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (countdownValue) countdownValue.textContent = remaining;
    if (statusEl && status) statusEl.textContent = status;
    if (hintEl && hint) hintEl.textContent = hint;
}

/**
 * Check if server is back online
 */
async function checkServerOnline() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);
        
        const response = await fetch('/api/system/info', {
            method: 'GET',
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        return response.ok;
    } catch (error) {
        return false;
    }
}

/**
 * Perform system reboot with visual feedback
 */
async function performReboot() {
    try {
        // Show overlay immediately
        showRebootOverlay();
        
        const response = await fetch('/api/system/reboot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})  // Must send empty JSON body
        });
        
        const data = await response.json();
        
        if (!data.success) {
            // Remove overlay and show error
            const overlay = document.getElementById('reboot-overlay');
            if (overlay) overlay.remove();
            showToast(`Erreur: ${data.message}`, 'error');
            return;
        }
        
        // Start countdown and monitoring
        startRebootMonitoring();
        
    } catch (error) {
        // Connection lost during reboot request - this is expected
        // The reboot was likely initiated, continue with monitoring
        startRebootMonitoring();
    }
}

/**
 * Start monitoring the reboot process
 */
function startRebootMonitoring() {
    const TOTAL_SECONDS = 90;  // Expected reboot time
    const SHUTDOWN_PHASE = 10; // First 10 seconds: shutdown
    const BOOT_PHASE = 50;     // 10-60 seconds: booting
    const CHECK_START = 30;    // Start checking after 30 seconds
    
    let elapsed = 0;
    let serverBackOnline = false;
    
    const interval = setInterval(async () => {
        elapsed++;
        
        // Update status based on phase
        let status, hint;
        if (elapsed < SHUTDOWN_PHASE) {
            status = "Arrêt du système...";
            hint = "Les services s'arrêtent proprement";
        } else if (elapsed < BOOT_PHASE) {
            status = "Redémarrage du noyau...";
            hint = "Le Raspberry Pi redémarre";
        } else {
            status = "Démarrage des services...";
            hint = "Connexion en attente...";
        }
        
        updateRebootProgress(elapsed, TOTAL_SECONDS, status, hint);
        
        // Start checking if server is back online after CHECK_START seconds
        if (elapsed >= CHECK_START && !serverBackOnline) {
            const isOnline = await checkServerOnline();
            if (isOnline) {
                serverBackOnline = true;
                clearInterval(interval);
                
                // Show success state
                updateRebootProgress(TOTAL_SECONDS, TOTAL_SECONDS, "Système en ligne !", "Rechargement de la page...");
                
                const overlay = document.getElementById('reboot-overlay');
                if (overlay) overlay.classList.add('success');
                
                // Reload page after short delay
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            }
        }
        
        // Timeout - force reload
        if (elapsed >= TOTAL_SECONDS + 30) {
            clearInterval(interval);
            updateRebootProgress(100, 100, "Délai dépassé", "Tentative de reconnexion...");
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
        
    }, 1000);
}

/**
 * Set power state for a component (legacy - now handled by applyPowerSettings)
 */
async function setPowerState(component, enabled) {
    // Just mark as changed, don't apply immediately
    markPowerSettingsChanged();
}

/**
 * Set CPU frequency
 */
async function setCpuFrequency(freqMhz) {
    try {
        showToast('Modification de la fréquence CPU...', 'info');
        
        const response = await fetch('/api/power/cpu-freq', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ freq_mhz: parseInt(freqMhz) })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            // Reload power status
            setTimeout(() => loadPowerStatus(), 500);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// System Functions
// ============================================================================

/**
 * Confirm and execute system reboot - uses the overlay with countdown
 */
async function confirmReboot() {
    if (!confirm('Êtes-vous sûr de vouloir redémarrer le Raspberry Pi ?\nLa connexion sera perdue pendant quelques minutes.')) {
        return;
    }
    
    // Use the performReboot function which shows the overlay
    performReboot();
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
        <p>Connexion en cours...</p>
        <small>Initialisation du flux vidéo</small>
    `;
    statusText.innerHTML = '<i class="fas fa-circle preview-status-dot" style="color: var(--warning-color);"></i> Connexion...';
    
    // Set stream source
    streamImg.src = streamUrl;
    
    // Handle stream load success
    streamImg.onload = function() {
        placeholder.style.display = 'none';
        streamImg.style.display = 'block';
        btnStart.style.display = 'none';
        btnStop.style.display = 'inline-flex';
        statusText.innerHTML = '<i class="fas fa-circle preview-status-dot active"></i> Streaming...';
        previewActive = true;
        showToast('Aperçu démarré', 'success');
    };
    
    // Handle stream errors
    streamImg.onerror = function() {
        if (!previewActive) {
            placeholder.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <p>Erreur de connexion</p>
                <small>Impossible d'établir le flux vidéo</small>
            `;
            statusText.innerHTML = '<i class="fas fa-circle preview-status-dot inactive"></i> Erreur';
            showToast('Erreur de connexion au flux vidéo', 'error');
        } else {
            stopPreview();
            showToast('Flux vidéo interrompu', 'warning');
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
    statusText.innerHTML = '<i class="fas fa-circle preview-status-dot inactive"></i> Inactif';
    
    showToast('Aperçu arrêté', 'info');
}

/**
 * Take a snapshot from the camera
 */
async function takeSnapshot() {
    const quality = document.getElementById('preview-quality').value;
    const [width, height] = quality.split('x');
    
    try {
        showToast('Capture en cours...', 'info');
        
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
        
        showToast('Capture téléchargée !', 'success');
    } catch (error) {
        console.error('Snapshot error:', error);
        showToast('Erreur lors de la capture', 'error');
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
                <p>Caméra non disponible</p>
                <small>Vérifiez que la caméra est connectée</small>
            `;
            statusText.innerHTML = '<i class="fas fa-circle preview-status-dot inactive"></i> Non disponible';
        } else {
            const sourceLabel = data.preview_source === 'rtsp' ? 'via RTSP' : 'directe';
            statusText.innerHTML = `<i class="fas fa-circle preview-status-dot inactive"></i> Prêt (${sourceLabel})`;
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
                autofocusStatus.textContent = af.autofocus_enabled ? 'Activé' : 'Désactivé';
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
                autofocusStatus.textContent = 'Non disponible';
                autofocusStatus.className = 'control-status status-unavailable';
                manualFocusGroup.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading camera controls:', error);
        document.getElementById('autofocus-status').textContent = 'Erreur';
    }
}

/**
 * Set camera autofocus state
 */
async function setCameraAutofocus(enabled) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast(enabled ? 'Activation autofocus...' : 'Désactivation autofocus...', 'info');
        
        const response = await fetch('/api/camera/autofocus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const autofocusStatus = document.getElementById('autofocus-status');
            const manualFocusGroup = document.getElementById('manual-focus-group');
            
            autofocusStatus.textContent = enabled ? 'Activé' : 'Désactivé';
            autofocusStatus.className = 'control-status ' + (enabled ? 'status-on' : 'status-off');
            
            // Show manual focus slider when autofocus is disabled
            if (manualFocusGroup) {
                manualFocusGroup.style.display = enabled ? 'none' : 'block';
            }
            
            showToast(enabled ? 'Autofocus activé' : 'Autofocus désactivé - Ajustez le focus manuellement', 'success');
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
            // Revert checkbox
            document.getElementById('camera_autofocus').checked = !enabled;
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
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
            showToast(`Erreur focus: ${data.message}`, 'error');
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
        
        showToast('Mise au point en cours...', 'info');
        
        const response = await fetch('/api/camera/oneshot-focus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Mise au point effectuée et verrouillée', 'success');
            // Update autofocus checkbox to show it's now off (locked)
            const checkbox = document.getElementById('camera_autofocus');
            if (checkbox) {
                checkbox.checked = false;
            }
            const status = document.getElementById('autofocus-status');
            if (status) {
                status.textContent = 'Verrouillé';
                status.className = 'control-status status-off';
            }
            // Show manual focus slider
            const manualGroup = document.getElementById('manual-focus-group');
            if (manualGroup) {
                manualGroup.style.display = 'block';
            }
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
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
        
        container.innerHTML = '<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> Chargement des contrôles...</p>';
        
        const response = await fetch(`/api/camera/all-controls?device=${encodeURIComponent(device)}`);
        const data = await response.json();
        
        if (!data.success) {
            container.innerHTML = `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${data.error || 'Erreur de chargement'}</p>`;
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
    container.innerHTML = '<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> Chargement des contrôles Picamera2...</p>';
    
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
                            <p>La caméra CSI est actuellement utilisée par le flux RTSP.</p>
                            <p>Pour modifier les paramètres d'image :</p>
                            <ol style="margin: 10px 0; padding-left: 20px;">
                                <li>Arrêtez le flux RTSP (bouton ci-dessous)</li>
                                <li>Modifiez les paramètres</li>
                                <li>Redémarrez le flux</li>
                            </ol>
                            <button type="button" class="btn btn-warning btn-sm" onclick="stopRtspForConfig()">
                                <i class="fas fa-stop"></i> Arrêter le flux temporairement
                            </button>
                        </div>
                    </div>
                `;
            } else {
                container.innerHTML = `
                    <div class="info-box warning">
                        <i class="fas fa-exclamation-triangle"></i>
                        <div>
                            <strong>Erreur de chargement</strong>
                            <p>${data.error || 'Erreur inconnue'}</p>
                            <button type="button" class="btn btn-sm btn-secondary" onclick="loadCSICameraControls()">
                                <i class="fas fa-redo"></i> Réessayer
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
    if (!confirm('Arrêter le flux RTSP pour configurer la caméra ?\\nLes clients connectés seront déconnectés.')) return;
    
    try {
        const response = await fetch('/api/service/rpi-av-rtsp-recorder/stop', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast('Flux RTSP arrêté. Chargement des contrôles...', 'success');
            // Wait a bit for camera to be released
            setTimeout(() => loadCSICameraControls(), 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Render CSI camera controls (Picamera2)
 */
function renderCSIControls(data) {
    const container = document.getElementById('advanced-camera-controls');
    const grouped = data.grouped || {};
    
    const categoryLabels = {
        'exposure': { icon: 'fa-sun', label: 'Exposition' },
        'color': { icon: 'fa-palette', label: 'Couleur / Balance des blancs' },
        'focus': { icon: 'fa-crosshairs', label: 'Focus' },
        'noise': { icon: 'fa-volume-off', label: 'Réduction de bruit' },
        'auto': { icon: 'fa-magic', label: 'Automatique' },
        'other': { icon: 'fa-sliders-h', label: 'Autres' }
    };
    
    let html = `
        <div class="live-apply-notice csi-notice">
            <i class="fas fa-microchip"></i>
            <span>Contrôles CSI via Picamera2</span>
            <span class="live-apply-indicator">
                <i class="fas fa-save"></i> Les valeurs sont sauvegardées
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
            showToast(`${name} = ${value}`, 'success');
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
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
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Reset CSI controls to defaults
 */
async function resetCSIControls() {
    if (!confirm('Réinitialiser tous les paramètres CSI aux valeurs par défaut ?')) return;
    
    try {
        const response = await fetch('/api/camera/csi/tuning/reset', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Paramètres CSI réinitialisés', 'success');
            loadCSICameraControls();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Render advanced camera controls by category
 */
function renderAdvancedControls(data) {
    const container = document.getElementById('advanced-camera-controls');
    const grouped = data.grouped || {};
    
    const categoryLabels = {
        'focus': { icon: 'fa-crosshairs', label: 'Focus / Zoom' },
        'exposure': { icon: 'fa-sun', label: 'Exposition' },
        'white_balance': { icon: 'fa-temperature-half', label: 'Balance des blancs' },
        'color': { icon: 'fa-palette', label: 'Couleur' },
        'power_line': { icon: 'fa-bolt', label: 'Anti-scintillement' },
        'other': { icon: 'fa-sliders-h', label: 'Autres' }
    };
    
    // Live indicator at the top
    let html = `
        <div class="live-apply-notice">
            <i class="fas fa-broadcast-tower"></i>
            <span>Les modifications sont appliquées en temps réel au flux vidéo</span>
            <span id="live-apply-indicator" class="live-apply-indicator">
                <i class="fas fa-check-circle"></i> Appliqué
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
        html = '<p class="info-text"><i class="fas fa-info-circle"></i> Aucun contrôle disponible pour cette caméra</p>';
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
                ${defaultVal !== undefined ? `<small class="default-hint">(défaut: ${defaultVal})</small>` : ''}
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
            showToast(`Erreur ${name}: ${data.message}`, 'error');
            if (controlItem) {
                controlItem.classList.add('control-error');
                setTimeout(() => controlItem.classList.remove('control-error'), 1000);
            }
        }
    } catch (error) {
        console.error(`Error setting control ${name}:`, error);
        showToast(`Erreur: ${error.message}`, 'error');
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
    if (!confirm('Redémarrer le flux RTSP ? Les clients connectés seront déconnectés.')) {
        return;
    }
    
    try {
        showToast('Redémarrage du flux...', 'info');
        
        const response = await fetch('/api/service/restart', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Flux redémarré - les réglages sont maintenant actifs', 'success');
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
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
        showToast('Pas de valeurs par défaut disponibles', 'warning');
        return;
    }
    
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast('Réinitialisation en cours...', 'info');
        
        const response = await fetch('/api/camera/controls/set-multiple', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device, controls: toReset })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Contrôles réinitialisés', 'success');
            loadAdvancedCameraControls();
        } else {
            showToast(`Erreurs: ${data.errors} contrôle(s)`, 'warning');
            loadAdvancedCameraControls();
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
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
        container.innerHTML = '<p class="loading-text"><i class="fas fa-spinner fa-spin"></i> Chargement...</p>';
        
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
                schedulerStatus.textContent = `Actif (profil: ${activeProfile})`;
                schedulerStatus.className = 'control-status status-on';
            } else if (data.scheduler_enabled) {
                schedulerStatus.textContent = 'En attente (hors plage)';
                schedulerStatus.className = 'control-status status-warning';
            } else {
                schedulerStatus.textContent = 'Désactivé';
                schedulerStatus.className = 'control-status status-off';
            }
        }
        
        renderCameraProfiles(data.profiles, data.current_profile, data.scheduler_active_profile || data.active_profile);
        
    } catch (error) {
        console.error('Error loading profiles:', error);
        document.getElementById('camera-profiles-list').innerHTML = 
            `<p class="error-text"><i class="fas fa-exclamation-triangle"></i> ${error.message}</p>`;
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
                <i class="fas fa-info-circle"></i> Aucun profil configuré. 
                Créez des profils pour automatiser les réglages jour/nuit.
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
                        ${isApplied ? '<span class="badge badge-success">Appliqué</span>' : ''}
                        ${isScheduled && !isApplied ? '<span class="badge badge-info">Planifié</span>' : ''}
                        ${!profile.enabled ? '<span class="badge badge-muted">Désactivé</span>' : ''}
                    </h5>
                    <div class="profile-actions">
                        <button class="btn btn-sm btn-info" onclick="captureProfileSettings('${id}')" title="Capturer les réglages actuels">
                            <i class="fas fa-camera"></i>
                        </button>
                        <button class="btn btn-sm btn-success" onclick="ghostFixProfile('${id}')" title="Ghost-fix (désactive AE/AWB + brightness milieu)">
                            <i class="fas fa-magic"></i> ghost-fix
                        </button>
                        <button class="btn btn-sm btn-warning" onclick="showProfileSettings('${id}')" title="Afficher les paramètres enregistrés">
                            <i class="fas fa-cogs"></i>
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="editProfile('${id}')" title="Modifier">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-primary" onclick="applyProfile('${id}')" title="Appliquer maintenant">
                            <i class="fas fa-play"></i>
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteProfile('${id}')" title="Supprimer">
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
                            : 'Pas de planification'}
                    </div>
                    <div class="profile-controls-count">
                        <i class="fas fa-sliders-h"></i> ${controlsCount} réglage(s)
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
            throw new Error('Failed to update config');
        }
        
        // Then start/stop scheduler
        const action = enabled ? 'start' : 'stop';
        const response = await fetch(`/api/camera/profiles/scheduler/${action}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        showToast(enabled ? 'Scheduler activé' : 'Scheduler désactivé', data.success ? 'success' : 'warning');
        
        // Refresh status
        setTimeout(loadCameraProfiles, 500);
        
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Show profile settings in a modal
 */
function showProfileSettings(profileId) {
    const profile = cameraProfiles[profileId];
    if (!profile) {
        showToast('Profil non trouvé', 'error');
        return;
    }
    
    const controls = profile.controls || {};
    const modal = document.getElementById('profile-settings-modal');
    if (!modal) return;

    document.getElementById('profile-settings-title').textContent =
        `Paramètres: ${profile.display_name || profileId}`;

    const schedule = profile.schedule || {};
    const scheduleText = (schedule.start && schedule.end)
        ? `${schedule.start} - ${schedule.end}`
        : 'Pas de planification';
    const controlsCount = Object.keys(controls).length;
    const meta = `
        <div><i class="fas fa-clock"></i> ${scheduleText}</div>
        <div><i class="fas fa-sliders-h"></i> ${controlsCount} réglage(s)</div>
    `;
    const metaEl = document.getElementById('profile-settings-meta');
    if (metaEl) metaEl.innerHTML = meta;

    const contentEl = document.getElementById('profile-settings-content');
    if (!contentEl) return;

    if (controlsCount === 0) {
        contentEl.innerHTML = '<p class="info-text">Aucun réglage enregistré dans ce profil.</p>';
    } else {
        const rows = Object.entries(controls).map(([ctrlName, value]) => {
            let displayValue = value;
            if (Array.isArray(value)) {
                displayValue = '[' + value.join(', ') + ']';
            } else if (value === null || value === undefined) {
                displayValue = 'N/A';
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
                        <th>Paramètre</th>
                        <th>Valeur</th>
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
    document.getElementById('profile-modal-title').textContent = 'Nouveau profil';
    document.getElementById('profile-id').value = '';
    document.getElementById('profile-name').value = '';
    document.getElementById('profile-description').value = '';
    document.getElementById('profile-start').value = '07:00';
    document.getElementById('profile-end').value = '19:00';
    document.getElementById('profile-enabled').checked = true;
    document.getElementById('profile-controls-count').textContent = '0 réglages enregistrés';
    
    document.getElementById('profile-modal').style.display = 'flex';
}

/**
 * Edit an existing profile
 */
function editProfile(profileId) {
    const profile = cameraProfiles[profileId];
    if (!profile) return;
    
    editingProfileId = profileId;
    document.getElementById('profile-modal-title').textContent = 'Modifier le profil';
    document.getElementById('profile-id').value = profileId;
    document.getElementById('profile-name').value = profile.display_name || profile.name || profileId;
    document.getElementById('profile-description').value = profile.description || '';
    document.getElementById('profile-start').value = profile.schedule?.start || '';
    document.getElementById('profile-end').value = profile.schedule?.end || '';
    document.getElementById('profile-enabled').checked = profile.enabled === true;
    
    const controlsCount = Object.keys(profile.controls || {}).length;
    document.getElementById('profile-controls-count').textContent = `${controlsCount} réglages enregistrés`;
    
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
        showToast('Le nom du profil est requis', 'error');
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
            showToast('Profil enregistré', 'success');
            closeProfileModal();
            loadCameraProfiles();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Capture current camera settings into a specific profile
 */
async function captureProfileSettings(profileId) {
    if (!confirm(`Êtes-vous sûr de vouloir capturer les réglages actuels dans le profil "${profileId}" ?\nCela remplacera les réglages existants.`)) {
        return;
    }
    
    try {
        showToast('Capture des réglages...', 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            const controlsCount = data.profile ? Object.keys(data.profile.controls || {}).length : 0;
            showToast(`${controlsCount} réglages capturés dans "${profileId}"`, 'success');
            
            // Reload profiles to update display
            loadCameraProfiles();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply ghost-fix controls to a profile (CSI only)
 */
async function ghostFixProfile(profileId) {
    if (!confirm(`Appliquer le ghost-fix au profil "${profileId}" ?\nCela désactive AE/AWB et recentre la luminosité.`)) {
        return;
    }
    
    try {
        showToast('Ghost-fix en cours...', 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/ghost-fix`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || 'Ghost-fix appliqué', 'success');
            loadCameraProfiles();
            if (document.getElementById('advanced-camera-section').style.display !== 'none') {
                loadCSICameraControls();
            }
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

function formatLogEntries(entries) {
    return entries.map(entry => {
        if (!entry) return '';
        if (typeof entry === 'string') return entry;
        const source = entry.source ? `[${entry.source}] ` : '';
        const message = entry.message || entry.log || '';
        return `${source}${message}`.trim();
    }).filter(Boolean).join('\n');
}

/**
 * Capture current camera settings into the profile being edited
 */
async function captureCurrentSettings() {
    const profileId = editingProfileId || document.getElementById('profile-name').value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_');
    
    if (!profileId) {
        showToast('Entrez un nom de profil d\'abord', 'error');
        return;
    }
    
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast('Capture des réglages...', 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/capture`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const controlsCount = data.profile ? Object.keys(data.profile.controls || {}).length : 0;
            document.getElementById('profile-controls-count').textContent = 
                `${controlsCount} réglages capturés`;
            showToast(`${controlsCount} réglages capturés`, 'success');
            
            // Reload profiles to update local cache
            const profilesResponse = await fetch('/api/camera/profiles');
            const profilesData = await profilesResponse.json();
            if (profilesData.success) {
                cameraProfiles = profilesData.profiles || {};
            }
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply a profile immediately
 */
async function applyProfile(profileId) {
    try {
        const device = document.getElementById('VIDEO_DEVICE')?.value || '/dev/video0';
        
        showToast('Application du profil...', 'info');
        
        const response = await fetch(`/api/camera/profiles/${profileId}/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ device })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Profil "${profileId}" appliqué`, 'success');
            loadCameraProfiles();
            // Also refresh advanced controls if visible
            if (document.getElementById('advanced-camera-section').style.display !== 'none') {
                loadAdvancedCameraControls();
            }
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Delete a profile
 */
async function deleteProfile(profileId) {
    if (!confirm(`Supprimer le profil "${profileId}" ?`)) return;
    
    try {
        const response = await fetch(`/api/camera/profiles/${profileId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Profil supprimé', 'success');
            loadCameraProfiles();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}


// ============================================================================
// Meeting API Integration
// ============================================================================

/**
 * Toggle Meeting config fields visibility based on enabled state
 */
function toggleMeetingConfig() {
    const enabled = document.getElementById('MEETING_ENABLED')?.value === 'yes';
    const configFields = document.getElementById('meeting-config-fields');
    if (configFields) {
        configFields.style.opacity = enabled ? '1' : '0.5';
    }
}

/**
 * Toggle password visibility
 */
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.type = input.type === 'password' ? 'text' : 'password';
    }
}

/**
 * Test Meeting API connection
 */
async function testMeetingConnection() {
    const resultDiv = document.getElementById('meeting-test-result');
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Test de connexion en cours...';
    
    try {
        const response = await fetch('/api/meeting/test', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message}`;
            if (data.data) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.data, null, 2)}</pre>`;
            }
            showToast('Connexion Meeting réussie', 'success');
            updateMeetingStatus(true);
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            if (data.details) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.details, null, 2)}</pre>`;
            }
            showToast('Échec de connexion Meeting', 'error');
            updateMeetingStatus(false);
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Erreur: ${error.message}`;
        showToast('Erreur de test Meeting', 'error');
        updateMeetingStatus(false);
    }
}

/**
 * Send heartbeat to Meeting API
 */
async function sendMeetingHeartbeat() {
    const resultDiv = document.getElementById('meeting-test-result');
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Envoi du heartbeat...';
    
    try {
        const response = await fetch('/api/meeting/heartbeat', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `<i class="fas fa-heartbeat"></i> ${data.message || 'Heartbeat envoyé'}`;
            if (data.payload) {
                resultDiv.innerHTML += `<pre>Données envoyées:\n${JSON.stringify(data.payload, null, 2)}</pre>`;
            }
            showToast('Heartbeat envoyé', 'success');
            updateMeetingStatus(true);
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || data.message || 'Échec'}`;
            showToast('Échec du heartbeat', 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Erreur: ${error.message}`;
        showToast('Erreur heartbeat', 'error');
    }
}

/**
 * Get device availability from Meeting API
 */
async function getMeetingAvailability() {
    const resultDiv = document.getElementById('meeting-test-result');
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vérification de la disponibilité...';
    
    try {
        const response = await fetch('/api/meeting/availability');
        const data = await response.json();
        
        if (data.success) {
            const avail = data.data || data;
            // API Meeting returns status: "Available" or "Unavailable"
            const isOnline = avail.online === true || avail.status === 'Available' || avail.status === 'available';
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `
                <i class="fas fa-info-circle"></i> État de disponibilité
                <div class="availability-info">
                    <p><strong>En ligne:</strong> ${isOnline ? 'Oui ✓' : 'Non ✗'}</p>
                    <p><strong>Status:</strong> ${avail.status || 'N/A'}</p>
                    ${avail.last_heartbeat ? `<p><strong>Dernier heartbeat:</strong> ${avail.last_heartbeat}</p>` : ''}
                    ${avail.last_seen ? `<p><strong>Dernière connexion:</strong> ${new Date(avail.last_seen).toLocaleString()}</p>` : ''}
                    ${avail.uptime ? `<p><strong>Uptime:</strong> ${avail.uptime} minutes</p>` : ''}
                    ${avail.ip ? `<p><strong>IP:</strong> ${avail.ip}</p>` : ''}
                </div>
            `;
            showToast('Disponibilité récupérée', 'success');
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || data.message || 'Échec'}`;
            showToast('Échec récupération disponibilité', 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Erreur: ${error.message}`;
        showToast('Erreur disponibilité', 'error');
    }
}

/**
 * Fetch device info from Meeting API
 */
async function fetchMeetingDeviceInfo() {
    const infoDiv = document.getElementById('meeting-device-info');
    infoDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Chargement des informations...';
    
    try {
        // Fetch both device info and availability in parallel
        const [deviceResponse, availResponse] = await Promise.all([
            fetch('/api/meeting/device'),
            fetch('/api/meeting/availability')
        ]);
        
        const deviceData = await deviceResponse.json();
        const availData = await availResponse.json();
        
        if (deviceData.success && deviceData.data) {
            const device = deviceData.data;
            const avail = availData.success ? (availData.data || {}) : {};
            
            // Map API fields to expected fields
            // Name = product_serial (not device_name which is just the key)
            const deviceName = device.product_serial || device.name || device.device_name || 'Non défini';
            // IP from device info
            const deviceIp = device.ip_address || device.ip || 'N/A';
            // Online status from availability API
            const isOnline = avail.status === 'Available' || avail.status === 'available' || avail.online === true;
            // Last seen from availability
            const lastSeen = avail.last_heartbeat || avail.last_seen || device.last_seen;
            
            // Format last_seen date
            let lastSeenStr = 'N/A';
            if (lastSeen) {
                try {
                    // Handle various date formats
                    if (lastSeen.includes('T') || lastSeen.includes('Z')) {
                        lastSeenStr = new Date(lastSeen).toLocaleString();
                    } else {
                        // Format: "2026-01-16 23:19:38"
                        lastSeenStr = lastSeen;
                    }
                } catch(e) {
                    lastSeenStr = lastSeen;
                }
            }
            
            // Format services - handle array of strings (simple names like "ssh")
            let servicesHtml = '';
            if (device.services && Array.isArray(device.services) && device.services.length > 0) {
                const serviceBadges = device.services.map(s => {
                    // Services are simple strings like "ssh", "http", etc.
                    const serviceName = (typeof s === 'string') ? s : (s.name || 'unknown');
                    return `<span class="service-badge"><i class="fas fa-plug"></i> ${serviceName}</span>`;
                }).join('');
                
                servicesHtml = `
                    <div class="services-section">
                        <label><i class="fas fa-cogs"></i> Services déclarés</label>
                        <div class="services-badges">${serviceBadges}</div>
                    </div>
                `;
            } else {
                servicesHtml = `
                    <div class="services-section">
                        <label><i class="fas fa-cogs"></i> Services déclarés</label>
                        <div class="services-badges"><span class="service-badge service-none">Aucun service</span></div>
                    </div>
                `;
            }
            
            // WiFi AP section (if available)
            let wifiApHtml = '';
            if (device.ap_ssid || device.ap_password) {
                wifiApHtml = `
                    <div class="wifi-ap-section">
                        <label><i class="fas fa-wifi"></i> Point d'accès WiFi</label>
                        <div class="wifi-ap-info">
                            <div class="wifi-ap-item">
                                <span class="wifi-label">SSID</span>
                                <span class="wifi-value mono">${device.ap_ssid || 'N/A'}</span>
                            </div>
                            <div class="wifi-ap-item">
                                <span class="wifi-label">Mot de passe</span>
                                <span class="wifi-value mono">${device.ap_password || 'N/A'}</span>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Note section (full width)
            let noteHtml = '';
            if (device.note) {
                noteHtml = `
                    <div class="note-section">
                        <label><i class="fas fa-sticky-note"></i> Note</label>
                        <p class="note-content">${device.note}</p>
                    </div>
                `;
            }
            
            infoDiv.innerHTML = `
                <div class="device-info-grid">
                    <div class="info-item">
                        <label><i class="fas fa-key"></i> Device Key</label>
                        <span class="mono">${device.device_key || 'N/A'}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-tag"></i> Nom</label>
                        <span>${deviceName}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-circle ${isOnline ? 'text-success' : 'text-danger'}"></i> Statut</label>
                        <span>${isOnline ? 'En ligne' : 'Hors ligne'}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-network-wired"></i> IP</label>
                        <span class="mono">${deviceIp}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-clock"></i> Dernière activité</label>
                        <span>${lastSeenStr}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-coins"></i> Tokens</label>
                        <span>${device.token_count !== undefined ? device.token_count : 'N/A'}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-check-circle ${device.authorized ? 'text-success' : 'text-danger'}"></i> Autorisé</label>
                        <span>${device.authorized ? 'Oui' : 'Non'}</span>
                    </div>
                </div>
                ${noteHtml}
                ${wifiApHtml}
                ${servicesHtml}
            `;
            showToast('Informations du device chargées', 'success');
        } else {
            infoDiv.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-circle"></i> ${data.error || data.message || 'Impossible de charger les informations'}</p>`;
            showToast('Échec chargement device info', 'error');
        }
    } catch (error) {
        infoDiv.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-triangle"></i> Erreur: ${error.message}</p>`;
        showToast('Erreur chargement device info', 'error');
    }
}

/**
 * Request a tunnel from Meeting API
 */
async function requestMeetingTunnel() {
    const service = document.getElementById('meeting-tunnel-service')?.value || 'ssh';
    const resultDiv = document.getElementById('meeting-tunnel-result');
    
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Demande de tunnel ${service}...`;
    
    try {
        const response = await fetch('/api/meeting/tunnel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service })
        });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result success';
            let html = `<i class="fas fa-check-circle"></i> ${data.message}`;
            
            if (data.data) {
                if (data.data.tunnel_url) {
                    html += `<p><strong>URL du tunnel:</strong> <code>${data.data.tunnel_url}</code></p>`;
                }
                if (data.data.port) {
                    html += `<p><strong>Port distant:</strong> <code>${data.data.port}</code></p>`;
                }
                if (data.data.expires_at) {
                    html += `<p><strong>Expire:</strong> ${new Date(data.data.expires_at).toLocaleString()}</p>`;
                }
            }
            resultDiv.innerHTML = html;
            showToast(`Tunnel ${service} créé`, 'success');
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            if (data.details) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.details, null, 2)}</pre>`;
            }
            showToast('Échec création tunnel', 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Erreur: ${error.message}`;
        showToast('Erreur tunnel', 'error');
    }
}

/**
 * Update Meeting connection status indicator
 */
function updateMeetingStatus(connected) {
    const statusEl = document.getElementById('meeting-connection-status');
    const detailsEl = document.getElementById('meeting-status-details');
    
    if (statusEl) {
        if (connected) {
            statusEl.className = 'status-indicator connected';
            statusEl.innerHTML = '<i class="fas fa-circle"></i> Connecté';
        } else {
            statusEl.className = 'status-indicator disconnected';
            statusEl.innerHTML = '<i class="fas fa-circle"></i> Déconnecté';
        }
    }
    
    if (detailsEl && connected) {
        detailsEl.innerHTML = `<small>Dernière connexion: ${new Date().toLocaleTimeString()}</small>`;
    }
}

function updateMeetingConfigStatus() {
    const enabledToggle = document.getElementById('meeting_enabled_toggle');
    const autoToggle = document.getElementById('meeting_auto_connect');
    const enabledStatus = document.getElementById('meeting-enabled-status');
    const autoStatus = document.getElementById('meeting-auto-connect-status');

    if (enabledStatus && enabledToggle) {
        enabledStatus.textContent = enabledToggle.checked ? 'Activé' : 'Désactivé';
    }
    if (autoStatus && autoToggle) {
        autoStatus.textContent = autoToggle.checked ? 'Activé' : 'Désactivé';
    }
}

async function loadMeetingConfig() {
    try {
        const response = await fetch('/api/meeting/config');
        const data = await response.json();

        if (!data.success) {
            return;
        }

        const config = data.config || {};
        const enabledToggle = document.getElementById('meeting_enabled_toggle');
        const autoToggle = document.getElementById('meeting_auto_connect');
        const apiUrlInput = document.getElementById('meeting_config_api_url');
        const deviceKeyInput = document.getElementById('meeting_config_device_key');
        const tokenInput = document.getElementById('meeting_config_token_code');
        const heartbeatInput = document.getElementById('meeting_config_heartbeat_interval');
        const provisionedBadge = document.getElementById('meeting_config_provisioned');

        if (enabledToggle) enabledToggle.checked = !!config.enabled;
        if (autoToggle) autoToggle.checked = !!config.auto_connect;
        if (apiUrlInput) apiUrlInput.value = config.api_url || '';
        if (deviceKeyInput) deviceKeyInput.value = config.device_key || '';
        if (heartbeatInput) heartbeatInput.value = config.heartbeat_interval || 30;
        if (tokenInput) {
            tokenInput.value = '';
            tokenInput.placeholder = config.has_token ? '•••••••• (enregistré)' : 'Aucun token';
        }
        if (provisionedBadge) {
            if (config.provisioned) {
                provisionedBadge.textContent = 'Oui';
                provisionedBadge.className = 'badge badge-success';
            } else {
                provisionedBadge.textContent = 'Non';
                provisionedBadge.className = 'badge badge-warning';
            }
        }

        updateMeetingConfigStatus();
    } catch (error) {
        console.error('Error loading Meeting config:', error);
    }
}

async function saveMeetingConfig() {
    try {
        const enabledToggle = document.getElementById('meeting_enabled_toggle');
        const autoToggle = document.getElementById('meeting_auto_connect');
        const apiUrlInput = document.getElementById('meeting_config_api_url');
        const deviceKeyInput = document.getElementById('meeting_config_device_key');
        const tokenInput = document.getElementById('meeting_config_token_code');
        const heartbeatInput = document.getElementById('meeting_config_heartbeat_interval');

        const config = {
            enabled: enabledToggle?.checked ?? false,
            auto_connect: autoToggle?.checked ?? true,
            api_url: apiUrlInput?.value?.trim() || '',
            device_key: deviceKeyInput?.value?.trim() || '',
            heartbeat_interval: parseInt(heartbeatInput?.value, 10) || 30
        };

        const tokenValue = tokenInput?.value?.trim();
        if (tokenValue) {
            config.token_code = tokenValue;
        }

        showToast('Enregistrement Meeting...', 'info');

        const response = await fetch('/api/meeting/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            showToast('Configuration Meeting enregistrée', 'success');
            loadMeetingStatus();
            loadMeetingConfig();
        } else {
            showToast(`Erreur: ${data.message || data.error}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Load Meeting status on tab open - handles provisioning state
 */
async function loadMeetingStatus() {
    try {
        const response = await fetch('/api/meeting/status');
        const data = await response.json();
        
        if (data.success && data.status) {
            const status = data.status;
            const statusEl = document.getElementById('meeting-connection-status');
            const detailsEl = document.getElementById('meeting-status-details');
            
            // Show/hide sections based on provisioning state
            const provisioningSection = document.getElementById('meeting-provisioning-section');
            const provisionedConfig = document.getElementById('meeting-provisioned-config');
            const actionsSection = document.getElementById('meeting-actions-section');
            const provisionedBanner = document.getElementById('meeting-provisioned-banner');
            const provisionedDeviceKey = document.getElementById('provisioned-device-key');
            
            if (status.provisioned) {
                // Device is provisioned - show locked config
                if (provisioningSection) provisioningSection.style.display = 'none';
                if (provisionedConfig) provisionedConfig.style.display = 'block';
                if (actionsSection) actionsSection.style.display = 'block';
                if (provisionedBanner) provisionedBanner.style.display = 'flex';
                if (provisionedDeviceKey) {
                    provisionedDeviceKey.textContent = status.device_key_full || status.device_key;
                }
            } else {
                // Not provisioned - show provisioning form
                if (provisioningSection) provisioningSection.style.display = 'block';
                if (provisionedConfig) provisionedConfig.style.display = 'none';
                if (actionsSection) actionsSection.style.display = 'none';
                if (provisionedBanner) provisionedBanner.style.display = 'none';
            }
            
            // Update connection status
            if (!status.configured && !status.provisioned) {
                // Not configured
                if (statusEl) {
                    statusEl.className = 'status-indicator disconnected';
                    statusEl.innerHTML = '<i class="fas fa-circle"></i> Non provisionné';
                }
                if (detailsEl) {
                    detailsEl.innerHTML = '<small>Entrez vos credentials pour provisionner ce device</small>';
                }
            } else if (status.connected) {
                // Connected and heartbeat working
                if (statusEl) {
                    statusEl.className = 'status-indicator connected';
                    statusEl.innerHTML = '<i class="fas fa-circle"></i> Connecté';
                }
                if (detailsEl) {
                    let details = `<small>Device: ${status.device_key}`;
                    if (status.last_heartbeat_ago !== null) {
                        details += ` • Dernier heartbeat: il y a ${status.last_heartbeat_ago}s`;
                    }
                    if (status.heartbeat_thread_running) {
                        details += ` • Intervalle: ${status.heartbeat_interval}s`;
                    }
                    details += '</small>';
                    detailsEl.innerHTML = details;
                }
            } else if (status.enabled) {
                // Configured and enabled but not yet connected (or connection failed)
                if (statusEl) {
                    if (status.last_error) {
                        statusEl.className = 'status-indicator disconnected';
                        statusEl.innerHTML = '<i class="fas fa-circle"></i> Erreur de connexion';
                    } else {
                        statusEl.className = 'status-indicator pending';
                        statusEl.innerHTML = '<i class="fas fa-circle"></i> En attente de connexion';
                    }
                }
                if (detailsEl) {
                    if (status.last_error) {
                        detailsEl.innerHTML = `<small>Device: ${status.device_key} • ${status.last_error}</small>`;
                    } else {
                        detailsEl.innerHTML = `<small>Device: ${status.device_key} • En attente du premier heartbeat</small>`;
                    }
                }
            } else {
                // Configured but disabled
                if (statusEl) {
                    statusEl.className = 'status-indicator disconnected';
                    statusEl.innerHTML = '<i class="fas fa-circle"></i> Désactivé';
                }
                if (detailsEl) {
                    detailsEl.innerHTML = `<small>Device: ${status.device_key} • Meeting désactivé</small>`;
                }
            }

            loadMeetingConfig();
        }
    } catch (error) {
        console.error('Error loading Meeting status:', error);
    }
}

/**
 * Validate Meeting credentials before provisioning
 */
async function validateMeetingCredentials() {
    const apiUrl = document.getElementById('provision_api_url')?.value?.trim();
    const deviceKey = document.getElementById('provision_device_key')?.value?.trim().toUpperCase();
    const tokenCode = document.getElementById('provision_token_code')?.value?.trim();
    
    const resultDiv = document.getElementById('provision-validation-result');
    const provisionBtn = document.getElementById('btn-provision');
    
    // Validation
    if (!apiUrl || !deviceKey || !tokenCode) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result validation-error';
        resultDiv.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Veuillez remplir tous les champs';
        if (provisionBtn) provisionBtn.disabled = true;
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Validation des credentials en cours...';
    if (provisionBtn) provisionBtn.disabled = true;
    
    try {
        const response = await fetch('/api/meeting/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_url: apiUrl,
                device_key: deviceKey,
                token_code: tokenCode
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.valid) {
            const device = data.device;
            resultDiv.className = 'meeting-result validation-success';
            
            let tokenClass = 'success';
            let tokenWarning = '';
            if (device.token_count === 0) {
                tokenClass = 'danger';
                tokenWarning = '<br><strong style="color: var(--danger-color);">⚠️ Aucun token disponible ! Provisioning impossible.</strong>';
                if (provisionBtn) provisionBtn.disabled = true;
            } else if (device.token_count === 1) {
                tokenClass = 'warning';
                tokenWarning = '<br><small style="color: var(--warning-color);">⚠️ Dernier token disponible</small>';
                if (provisionBtn) provisionBtn.disabled = false;
            } else {
                if (provisionBtn) provisionBtn.disabled = false;
            }
            
            resultDiv.innerHTML = `
                <i class="fas fa-check-circle"></i> <strong>Credentials valides !</strong>
                <div class="provision-info">
                    <div class="provision-info-item">
                        <span class="label">Device</span>
                        <span class="value">${device.name || 'Sans nom'}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">Autorisé</span>
                        <span class="value ${device.authorized ? 'success' : 'danger'}">${device.authorized ? 'Oui ✓' : 'Non ✗'}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">Tokens disponibles</span>
                        <span class="value ${tokenClass}">${device.token_count}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">En ligne</span>
                        <span class="value">${device.online ? 'Oui' : 'Non'}</span>
                    </div>
                </div>
                ${tokenWarning}
                ${device.token_count > 0 && device.authorized ? '<p style="margin-top: 10px;"><i class="fas fa-info-circle"></i> Cliquez sur "Provisionner le device" pour continuer. Cette opération consommera 1 token.</p>' : ''}
            `;
            
            if (!device.authorized) {
                resultDiv.innerHTML += '<p style="color: var(--danger-color); margin-top: 10px;"><i class="fas fa-ban"></i> Ce device n\'est pas autorisé dans Meeting.</p>';
                if (provisionBtn) provisionBtn.disabled = true;
            }
            
            showToast('Credentials validés', 'success');
        } else {
            resultDiv.className = 'meeting-result validation-error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> <strong>Validation échouée</strong><br>${data.message}`;
            if (provisionBtn) provisionBtn.disabled = true;
            showToast('Credentials invalides', 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result validation-error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Erreur: ${error.message}`;
        if (provisionBtn) provisionBtn.disabled = true;
        showToast('Erreur de validation', 'error');
    }
}

/**
 * Provision the device with Meeting
 */
async function provisionDevice() {
    const apiUrl = document.getElementById('provision_api_url')?.value?.trim();
    const deviceKey = document.getElementById('provision_device_key')?.value?.trim().toUpperCase();
    const tokenCode = document.getElementById('provision_token_code')?.value?.trim();
    
    const resultDiv = document.getElementById('provision-validation-result');
    const provisionBtn = document.getElementById('btn-provision');
    
    if (!confirm('Êtes-vous sûr de vouloir provisionner ce device ?\n\nCette action va :\n- Consommer 1 token de provisioning\n- Changer le hostname du device\n- Verrouiller la configuration Meeting')) {
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Provisioning en cours... Veuillez patienter.';
    if (provisionBtn) provisionBtn.disabled = true;
    
    try {
        const response = await fetch('/api/meeting/provision', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_url: apiUrl,
                device_key: deviceKey,
                token_code: tokenCode
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result validation-success';
            resultDiv.innerHTML = `
                <i class="fas fa-check-circle"></i> <strong>Provisioning réussi !</strong>
                <div class="provision-info">
                    <div class="provision-info-item">
                        <span class="label">Nouveau hostname</span>
                        <span class="value">${data.hostname}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">Token consommé</span>
                        <span class="value success">Oui</span>
                    </div>
                </div>
                <p style="margin-top: 15px; color: var(--warning-color);">
                    <i class="fas fa-exclamation-triangle"></i> <strong>Important:</strong> Le hostname a changé. 
                    Après quelques secondes, vous pourrez accéder à l'interface via:
                    <br><code>http://${data.hostname}.local</code>
                </p>
            `;
            showToast('Device provisionné avec succès!', 'success');
            
            // Reload status after a short delay
            setTimeout(() => {
                loadMeetingStatus();
            }, 2000);
        } else {
            resultDiv.className = 'meeting-result validation-error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> <strong>Échec du provisioning</strong><br>${data.message}`;
            if (provisionBtn) provisionBtn.disabled = false;
            showToast('Échec du provisioning', 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result validation-error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> Erreur: ${error.message}`;
        if (provisionBtn) provisionBtn.disabled = false;
        showToast('Erreur de provisioning', 'error');
    }
}

/**
 * Show the master reset modal
 */
function showMasterResetModal() {
    const modal = document.getElementById('master-reset-modal');
    if (modal) {
        modal.style.display = 'flex';
        document.getElementById('master_reset_code').value = '';
        document.getElementById('master_reset_code').focus();
    }
}

/**
 * Close the master reset modal
 */
function closeMasterResetModal() {
    const modal = document.getElementById('master-reset-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Execute master reset
 */
async function executeMasterReset() {
    const code = document.getElementById('master_reset_code')?.value?.trim();
    
    if (!code) {
        showToast('Veuillez entrer le code master', 'warning');
        return;
    }
    
    try {
        showToast('Réinitialisation en cours...', 'info');
        
        const response = await fetch('/api/meeting/master-reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_code: code })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeMasterResetModal();
            showToast('Configuration Meeting réinitialisée', 'success');
            loadMeetingStatus();
            // Reload page to refresh all config
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showToast(data.message || 'Échec de la réinitialisation', 'error');
        }
    } catch (error) {
        showToast('Erreur: ' + error.message, 'error');
    }
}


// Load camera controls when video tab is opened
document.addEventListener('DOMContentLoaded', () => {
    // Add listener for video tab
    const videoTabBtn = document.querySelector('[data-tab="video"]');
    if (videoTabBtn) {
        videoTabBtn.addEventListener('click', () => {
            setTimeout(() => {
                loadCameraControls();
                loadCameraProfiles();
            }, 100);
        });
    }
    
    // Add listener for meeting tab
    const meetingTabBtn = document.querySelector('[data-tab="meeting"]');
    if (meetingTabBtn) {
        meetingTabBtn.addEventListener('click', () => {
            setTimeout(() => {
                loadMeetingStatus();
            }, 100);
        });
    }

    const meetingEnabledToggle = document.getElementById('meeting_enabled_toggle');
    const meetingAutoConnectToggle = document.getElementById('meeting_auto_connect');
    if (meetingEnabledToggle) {
        meetingEnabledToggle.addEventListener('change', updateMeetingConfigStatus);
    }
    if (meetingAutoConnectToggle) {
        meetingAutoConnectToggle.addEventListener('change', updateMeetingConfigStatus);
    }
    
    // Update focus value display when slider moves
    const focusSlider = document.getElementById('camera_focus');
    if (focusSlider) {
        focusSlider.addEventListener('input', (e) => {
            document.getElementById('focus-value').textContent = e.target.value;
        });
    }
    
    // Close modal when clicking outside
    document.getElementById('profile-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'profile-modal') {
            closeProfileModal();
        }
    });
    document.getElementById('profile-settings-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'profile-settings-modal') {
            closeProfileSettingsModal();
        }
    });
    
    // Add listener for system tab
    const systemTabBtn = document.querySelector('[data-tab="system"]');
    if (systemTabBtn) {
        systemTabBtn.addEventListener('click', () => {
            setTimeout(() => {
                loadNtpConfig();
                loadRtcConfig();
                loadSnmpConfig();
                loadRebootSchedule();
                checkForUpdates();
            }, 100);
        });
    }

    setTimeout(() => {
        loadNtpConfig();
        loadRtcConfig();
        loadSnmpConfig();
        loadRebootSchedule();
    }, 200);
});

// ============================================================================
// NTP Configuration Functions
// ============================================================================

/**
 * Load NTP configuration and status
 */
async function loadNtpConfig() {
    try {
        const response = await fetch('/api/system/ntp');
        const data = await response.json();
        
        if (data.success) {
            const ntpInput = document.getElementById('ntp_server');
            if (ntpInput && data.server) {
                ntpInput.value = data.server;
            }
            
            updateNtpStatus(data);
        } else {
            updateNtpStatus({
                synchronized: false,
                server: null,
                current_time: null,
                timezone: null,
                error: data.message || 'Erreur NTP'
            });
        }
    } catch (error) {
        console.error('Error loading NTP config:', error);
        updateNtpStatus({
            synchronized: false,
            server: null,
            current_time: null,
            timezone: null,
            error: error.message || 'Erreur NTP'
        });
    }
}

/**
 * Update NTP status display
 */
function updateNtpStatus(data) {
    const statusDiv = document.getElementById('ntp-status');
    if (!statusDiv) return;
    
    let html = `<div class="status-indicator ${data.synchronized ? 'synced' : 'not-synced'}">`;
    html += `<i class="fas fa-${data.synchronized ? 'check-circle' : 'exclamation-triangle'}"></i>`;
    html += `<span>${data.synchronized ? 'Synchronisé' : 'Non synchronisé'}</span>`;
    html += `</div>`;
    
    if (data.error) {
        html += `<div class="ntp-details"><span><strong>Erreur:</strong> ${data.error}</span></div>`;
    } else if (data.server || data.current_time) {
        html += `<div class="ntp-details">`;
        if (data.server) html += `<span><strong>Serveur:</strong> ${data.server}</span>`;
        if (data.current_time) html += `<span><strong>Heure système:</strong> ${data.current_time}</span>`;
        if (data.timezone) html += `<span><strong>Fuseau:</strong> ${data.timezone}</span>`;
        html += `</div>`;
    }
    
    statusDiv.innerHTML = html;
}

/**
 * Save NTP configuration
 */
async function saveNtpConfig() {
    const server = document.getElementById('ntp_server')?.value?.trim();
    
    if (!server) {
        showToast('Veuillez entrer un serveur NTP', 'warning');
        return;
    }
    
    try {
        showToast('Configuration NTP...', 'info');
        
        const response = await fetch('/api/system/ntp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Serveur NTP configuré', 'success');
            loadNtpConfig();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Force NTP synchronization now
 */
async function syncNtpNow() {
    try {
        showToast('Synchronisation en cours...', 'info');
        
        const response = await fetch('/api/system/ntp/sync', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Heure synchronisée', 'success');
            loadNtpConfig();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// RTC Configuration Functions
// ============================================================================

/**
 * Load RTC configuration and status
 */
async function loadRtcConfig() {
    try {
        const response = await fetch('/api/system/rtc');
        const data = await response.json();

        if (data.success) {
            const rtcMode = document.getElementById('rtc_mode');
            if (rtcMode && data.mode) {
                rtcMode.value = data.mode;
            }

            updateRtcStatus(data);
        } else {
            updateRtcStatus({
                success: false,
                error: data.message || 'Erreur RTC'
            });
        }
    } catch (error) {
        console.error('Error loading RTC config:', error);
        updateRtcStatus({
            success: false,
            error: error.message || 'Erreur RTC'
        });
    }
}

/**
 * Update RTC status display
 */
function updateRtcStatus(data) {
    const statusDiv = document.getElementById('rtc-status');
    if (!statusDiv) return;

    if (data && data.success === false && data.error) {
        statusDiv.innerHTML = `
            <div class="status-indicator not-synced">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Erreur RTC</span>
            </div>
            <div class="rtc-details"><span><strong>Erreur:</strong> ${data.error}</span></div>
        `;
        return;
    }

    const enabled = !!data.effective_enabled;
    const detected = !!data.detected;
    const indicatorClass = enabled ? 'synced' : 'not-synced';
    const indicatorLabel = enabled ? 'Actif' : 'Inactif';
    const modeLabel = data.mode || 'auto';
    const viaLabel = data.detected_via ? ` (${data.detected_via})` : '';

    let html = `<div class="status-indicator ${indicatorClass}">`;
    html += `<i class="fas fa-${enabled ? 'check-circle' : 'exclamation-triangle'}"></i>`;
    html += `<span>RTC ${indicatorLabel}</span>`;
    html += `</div>`;
    html += `<div class="rtc-details">`;
    html += `<span><strong>Mode:</strong> ${modeLabel}</span>`;
    html += `<span><strong>Détecté:</strong> ${detected ? 'Oui' : 'Non'}${detected ? viaLabel : ''}</span>`;
    html += `<span><strong>Overlay:</strong> ${data.overlay_configured ? 'Configuré' : 'Non configuré'}</span>`;
    html += `<span><strong>I2C:</strong> ${data.i2c_enabled ? 'Activé' : 'Désactivé'}</span>`;
    if (data.auto_pending) {
        if (!data.i2c_enabled) {
            html += `<span><strong>Auto:</strong> I2C désactivé, appliquez pour activer</span>`;
        } else {
            html += `<span><strong>Auto:</strong> Module détecté, appliquez pour activer</span>`;
        }
    }
    html += `</div>`;

    statusDiv.innerHTML = html;
}

/**
 * Save RTC configuration
 */
async function saveRtcConfig() {
    const rtcMode = document.getElementById('rtc_mode')?.value || 'auto';

    try {
        showToast('Application RTC...', 'info');

        const response = await fetch('/api/system/rtc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: rtcMode })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message || 'RTC configuré', 'success');
            loadRtcConfig();
            if (data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 800);
            }
        } else {
            showToast(`Erreur RTC: ${data.message || "Impossible d'appliquer"}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur RTC: ${error.message}`, 'error');
    }
}

// ============================================================================
// SNMP Configuration Functions
// ============================================================================

function updateSnmpUiState() {
    const enabled = document.getElementById('snmp_enabled')?.checked === true;
    const host = document.getElementById('snmp_host');
    const port = document.getElementById('snmp_port');
    if (host) host.disabled = !enabled;
    if (port) port.disabled = !enabled;
}

// ============================================================================
// Scheduled Reboot
// ============================================================================

function updateRebootScheduleUiState() {
    const enabled = document.getElementById('reboot_schedule_enabled')?.checked === true;
    const hour = document.getElementById('reboot_schedule_hour');
    const minute = document.getElementById('reboot_schedule_minute');
    const days = document.getElementById('reboot-schedule-days');
    if (hour) hour.disabled = !enabled;
    if (minute) minute.disabled = !enabled;
    if (days) days.querySelectorAll('input').forEach(input => { input.disabled = !enabled; });
}

function _populateRebootScheduleSelects() {
    const hourSelect = document.getElementById('reboot_schedule_hour');
    const minuteSelect = document.getElementById('reboot_schedule_minute');
    if (hourSelect && hourSelect.options.length === 0) {
        for (let h = 0; h < 24; h += 1) {
            const opt = document.createElement('option');
            opt.value = h;
            opt.textContent = h.toString().padStart(2, '0');
            hourSelect.appendChild(opt);
        }
    }
    if (minuteSelect && minuteSelect.options.length === 0) {
        for (let m = 0; m < 60; m += 5) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m.toString().padStart(2, '0');
            minuteSelect.appendChild(opt);
        }
    }
}

async function loadRebootSchedule() {
    _populateRebootScheduleSelects();
    try {
        const response = await fetch('/api/system/reboot/schedule');
        const data = await response.json();
        if (!data.success) return;

        const enabledEl = document.getElementById('reboot_schedule_enabled');
        const hourEl = document.getElementById('reboot_schedule_hour');
        const minuteEl = document.getElementById('reboot_schedule_minute');
        const daysEl = document.getElementById('reboot-schedule-days');

        if (enabledEl) enabledEl.checked = data.enabled === true;
        if (hourEl) hourEl.value = data.hour ?? 3;
        if (minuteEl) minuteEl.value = data.minute ?? 0;

        if (daysEl) {
            const days = Array.isArray(data.days) ? data.days.map(String) : ['all'];
            daysEl.querySelectorAll('input').forEach(input => {
                input.checked = days.includes(input.value);
            });
        }

        updateRebootScheduleUiState();
    } catch (error) {
        console.error('Error loading reboot schedule:', error);
    }
}

async function saveRebootSchedule() {
    const enabled = document.getElementById('reboot_schedule_enabled')?.checked === true;
    const hour = parseInt(document.getElementById('reboot_schedule_hour')?.value || '3', 10);
    const minute = parseInt(document.getElementById('reboot_schedule_minute')?.value || '0', 10);
    const daysEl = document.getElementById('reboot-schedule-days');
    let days = [];
    if (daysEl) {
        days = Array.from(daysEl.querySelectorAll('input'))
            .filter(input => input.checked)
            .map(input => input.value);
    }
    if (days.includes('all')) {
        days = ['all'];
    }

    try {
        showToast('Enregistrement du schedule...', 'info');
        const response = await fetch('/api/system/reboot/schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, hour, minute, days })
        });
        const data = await response.json();
        if (data.success) {
            showToast('Schedule reboot enregistré', 'success');
            loadRebootSchedule();
        } else {
            showToast(`Erreur: ${data.message || 'Impossible de sauvegarder'}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

async function loadSnmpConfig() {
    try {
        const response = await fetch('/api/system/snmp');
        const data = await response.json();
        if (!data.success) return;

        const enabledEl = document.getElementById('snmp_enabled');
        const hostEl = document.getElementById('snmp_host');
        const portEl = document.getElementById('snmp_port');

        if (enabledEl) enabledEl.checked = data.enabled === true;
        if (hostEl) hostEl.value = data.host || '';
        if (portEl) portEl.value = data.port || 162;

        updateSnmpUiState();
    } catch (error) {
        console.error('Error loading SNMP config:', error);
    }
}

async function saveSnmpConfig() {
    const enabled = document.getElementById('snmp_enabled')?.checked === true;
    const host = document.getElementById('snmp_host')?.value?.trim() || '';
    const port = parseInt(document.getElementById('snmp_port')?.value || '162', 10);

    try {
        showToast('Configuration SNMP...', 'info');
        const response = await fetch('/api/system/snmp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, host, port })
        });
        const data = await response.json();
        if (data.success) {
            showToast('Configuration SNMP appliquée', 'success');
            loadSnmpConfig();
        } else {
            showToast(`Erreur: ${data.message || 'Impossible de sauvegarder'}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

async function testSnmpConfig() {
    const enabled = document.getElementById('snmp_enabled')?.checked === true;
    const host = document.getElementById('snmp_host')?.value?.trim() || '';
    const port = parseInt(document.getElementById('snmp_port')?.value || '162', 10);

    try {
        showToast('Test SNMP...', 'info');
        const response = await fetch('/api/system/snmp/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, host, port })
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message || 'SNMP OK', 'success');
        } else {
            showToast(`Erreur: ${data.message || 'Test SNMP échoué'}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// GitHub Updater Functions
// ============================================================================

const GITHUB_REPO = 'votre-user/RTSP-Full';  // À configurer
const CURRENT_VERSION = '2.30.27';

/**
 * Check for available updates on GitHub
 */
async function checkForUpdates() {
    const latestVersionEl = document.getElementById('latest-version');
    const updateBtn = document.getElementById('btn-update');
    
    if (latestVersionEl) {
        latestVersionEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vérification...';
        latestVersionEl.className = 'version';
    }
    
    try {
        const response = await fetch('/api/system/update/check');
        const data = await response.json();
        
        if (data.success) {
            if (latestVersionEl) {
                latestVersionEl.textContent = data.latest_version || 'v' + CURRENT_VERSION;
                
                if (data.update_available) {
                    latestVersionEl.classList.add('new-available');
                    if (updateBtn) updateBtn.disabled = false;
                    showToast(`Mise à jour disponible: ${data.latest_version}`, 'info');
                } else {
                    latestVersionEl.classList.add('up-to-date');
                    latestVersionEl.textContent += ' ✓';
                    if (updateBtn) updateBtn.disabled = true;
                }
            }
            
            // Show changelog if available
            if (data.changelog) {
                const logDiv = document.getElementById('update-log');
                if (logDiv) {
                    logDiv.style.display = 'block';
                    logDiv.querySelector('pre').innerHTML = `<span class="log-info">Changelog:</span>\n${data.changelog}`;
                }
            }
        } else {
            if (latestVersionEl) {
                latestVersionEl.textContent = 'Erreur';
                latestVersionEl.classList.add('outdated');
            }
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        if (latestVersionEl) {
            latestVersionEl.textContent = 'Non disponible';
        }
        console.error('Error checking updates:', error);
    }
}

/**
 * Perform system update from GitHub
 */
async function performUpdate() {
    if (!confirm('Voulez-vous lancer la mise à jour ?\n\nLe service sera redémarré après la mise à jour.')) {
        return;
    }
    
    const logDiv = document.getElementById('update-log');
    const logPre = logDiv?.querySelector('pre');
    const updateBtn = document.getElementById('btn-update');
    
    if (logDiv) logDiv.style.display = 'block';
    if (logPre) logPre.innerHTML = '<span class="log-info">Démarrage de la mise à jour...</span>\n';
    if (updateBtn) updateBtn.disabled = true;
    
    try {
        const response = await fetch('/api/system/update/perform', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (logPre) {
                logPre.innerHTML += `<span class="log-success">${data.message}</span>\n`;
                if (data.log) logPre.innerHTML += data.log;
            }
            showToast('Mise à jour réussie! Redémarrage du service...', 'success');
            
            // Refresh page after delay
            setTimeout(() => {
                window.location.reload();
            }, 5000);
        } else {
            if (logPre) {
                logPre.innerHTML += `<span class="log-error">Erreur: ${data.message}</span>\n`;
                if (data.log) logPre.innerHTML += data.log;
            }
            showToast(`Erreur mise à jour: ${data.message}`, 'error');
            if (updateBtn) updateBtn.disabled = false;
        }
    } catch (error) {
        if (logPre) {
            logPre.innerHTML += `<span class="log-error">Erreur: ${error.message}</span>\n`;
        }
        showToast(`Erreur: ${error.message}`, 'error');
        if (updateBtn) updateBtn.disabled = false;
    }
}

// ============================================================================
// Backup / Restore Functions
// ============================================================================

function updateBackupStatus(text, state = null) {
    const statusEl = document.getElementById('backup-status-text');
    if (!statusEl) return;

    statusEl.textContent = text;
    statusEl.className = 'status-value';
    if (state) {
        statusEl.classList.add(state);
    }
}

function openBackupFilePicker(action) {
    backupFileAction = action;
    const input = document.getElementById('backup-file-input');
    if (!input) {
        updateBackupStatus('Champ fichier introuvable', 'error');
        return;
    }
    input.value = '';
    input.click();
}

function handleBackupFileSelected(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    backupSelectedFile = file;
    if (backupFileAction === 'check') {
        checkBackupFile(file);
    } else if (backupFileAction === 'restore') {
        restoreBackupFile(file);
    } else {
        updateBackupStatus('Action de backup invalide', 'error');
    }
}

async function backupConfiguration() {
    const includeLogs = confirm('Inclure les logs dans le backup ?');
    updateBackupStatus('Preparation du backup...', 'checking');

    try {
        const response = await fetch('/api/system/backup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ include_logs: includeLogs })
        });

        const contentType = response.headers.get('content-type') || '';
        if (!response.ok || contentType.includes('application/json')) {
            const data = await response.json();
            const message = data.message || 'Erreur backup';
            updateBackupStatus(message, 'error');
            showToast(message, 'error');
            return;
        }

        const blob = await response.blob();
        const disposition = response.headers.get('content-disposition') || '';
        const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/);
        const filename = filenameMatch ? filenameMatch[1] : 'rpi-cam-backup.tar.gz';

        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);

        updateBackupStatus('Backup telecharge', 'success');
        showToast('Backup genere', 'success');
    } catch (error) {
        updateBackupStatus(`Erreur: ${error.message}`, 'error');
        showToast(`Erreur backup: ${error.message}`, 'error');
    }
}

async function checkBackupFile(file) {
    updateBackupStatus('Verification du backup...', 'checking');

    try {
        const formData = new FormData();
        formData.append('backup', file);

        const response = await fetch('/api/system/backup/check', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || 'Backup invalide';
            updateBackupStatus(message, 'error');
            showToast(message, 'error');
            return;
        }

        const info = `Backup valide (v${data.version || 'N/A'}, ${data.files_count || 0} fichiers)`;
        updateBackupStatus(info, 'success');
        showToast(info, 'success');

        if (confirm(`${info}\n\nVoulez-vous restaurer ce backup ?`)) {
            restoreBackupFile(file, true);
        }
    } catch (error) {
        updateBackupStatus(`Erreur: ${error.message}`, 'error');
        showToast(`Erreur check: ${error.message}`, 'error');
    }
}

async function restoreBackupFile(file, skipConfirm = false) {
    if (!skipConfirm) {
        const proceed = confirm('Restaurer la configuration depuis ce backup ?\n\nLe Raspberry Pi va redemarrer.');
        if (!proceed) return;
    }

    updateBackupStatus('Restauration en cours...', 'updating');

    try {
        const formData = new FormData();
        formData.append('backup', file);

        const response = await fetch('/api/system/backup/restore', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || 'Restauration echouee';
            updateBackupStatus(message, 'error');
            showToast(message, 'error');
            return;
        }

        updateBackupStatus('Restauration reussie, reboot en cours...', 'success');
        showToast('Restauration reussie, redemarrage...', 'success');

        showRebootOverlay();
        startRebootMonitoring();
    } catch (error) {
        updateBackupStatus(`Erreur: ${error.message}`, 'error');
        showToast(`Erreur restore: ${error.message}`, 'error');
    }
}

// ============================================================================
// Update from file
// ============================================================================

function openUpdateFilePicker() {
    const input = document.getElementById('update-file-input');
    if (!input) {
        showToast('Champ fichier introuvable', 'error');
        return;
    }
    input.value = '';
    input.click();
}

function handleUpdateFileSelected(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    updateFileSelected = file;
    showUpdateFileModal();
    checkUpdateFile(file);
}

function showUpdateFileModal() {
    const modal = document.getElementById('update-file-modal');
    if (!modal) return;

    document.getElementById('update-file-name').textContent = updateFileSelected?.name || '-';
    document.getElementById('update-current-version').textContent = document.getElementById('current-version')?.textContent || '-';
    document.getElementById('update-new-version').textContent = '-';
    const forceCheckbox = document.getElementById('update-file-force');
    if (forceCheckbox) forceCheckbox.checked = false;
    const resetCheckbox = document.getElementById('update-file-reset');
    if (resetCheckbox) resetCheckbox.checked = false;
    const depsCheckbox = document.getElementById('update-file-install-deps');
    if (depsCheckbox) depsCheckbox.checked = true;
    const depsGroup = document.getElementById('update-file-deps-group');
    if (depsGroup) depsGroup.style.display = 'none';
    const depsInfo = document.getElementById('update-file-deps-info');
    if (depsInfo) depsInfo.textContent = '';
    updateUpdateFileStatus('Verification en cours...', 'checking');
    updateUpdateFileLog('');

    const applyBtn = document.getElementById('update-file-apply-btn');
    if (applyBtn) applyBtn.disabled = true;

    modal.style.display = 'flex';
}

function closeUpdateFileModal() {
    const modal = document.getElementById('update-file-modal');
    if (modal) modal.style.display = 'none';
    if (updateFilePolling) {
        clearInterval(updateFilePolling);
        updateFilePolling = null;
    }
    updateFilePollFailures = 0;
}

function updateUpdateFileStatus(text, state = null) {
    const statusEl = document.getElementById('update-file-status-text');
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = 'status-value';
    if (state) statusEl.classList.add(state);
}

function updateUpdateFileLog(text) {
    const log = document.getElementById('update-file-log');
    const pre = log?.querySelector('pre');
    if (!log || !pre) return;
    if (text) {
        log.style.display = 'block';
        pre.textContent = text;
    } else {
        log.style.display = 'none';
        pre.textContent = '';
    }
}

function onUpdateFileForceChanged() {
    if (updateFileSelected) {
        checkUpdateFile(updateFileSelected);
    }
}

async function checkUpdateFile(file) {
    updateUpdateFileStatus('Verification en cours...', 'checking');
    updateUpdateFileLog('');

    try {
        const formData = new FormData();
        formData.append('update', file);
        const force = document.getElementById('update-file-force')?.checked;
        if (force) formData.append('force', '1');

        const response = await fetch('/api/system/update/file/check', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || 'Update invalide';
            updateUpdateFileStatus(message, 'error');
            updateUpdateFileLog(message);
            return;
        }

        document.getElementById('update-new-version').textContent = data.version || '-';
        if (data.requires_reboot) {
            updateUpdateFileLog(`Redemarrage requis apres update (version ${data.version || '-'})`);
        }
        const sameVersion = data.same_version === true;
        if (sameVersion && !data.reapply_allowed) {
            updateUpdateFileStatus('Version identique (forcer pour reinstaller)', 'error');
            updateUpdateFileLog('Version identique, cochez "forcer" pour continuer.');
            return;
        }

        const depsGroup = document.getElementById('update-file-deps-group');
        const depsInfo = document.getElementById('update-file-deps-info');
        const depsCheckbox = document.getElementById('update-file-install-deps');
        if (data.missing_packages && data.missing_packages.length) {
            if (depsGroup) depsGroup.style.display = 'block';
            if (depsInfo) depsInfo.textContent = `Manquantes: ${data.missing_packages.join(', ')}`;
            if (depsCheckbox) depsCheckbox.checked = true;
        } else {
            if (depsGroup) depsGroup.style.display = 'none';
            if (depsInfo) depsInfo.textContent = '';
        }

        updateUpdateFileStatus('Update valide, pret a appliquer', 'success');
        updateUpdateFileLog(`Fichiers: ${data.files_count || 0}`);

        const applyBtn = document.getElementById('update-file-apply-btn');
        if (applyBtn) applyBtn.disabled = false;
    } catch (error) {
        updateUpdateFileStatus(`Erreur: ${error.message}`, 'error');
        updateUpdateFileLog(error.message);
    }
}

async function applyUpdateFile() {
    if (!updateFileSelected) {
        updateUpdateFileStatus('Aucun fichier selectionne', 'error');
        return;
    }

    const depsGroup = document.getElementById('update-file-deps-group');
    const depsCheckbox = document.getElementById('update-file-install-deps');
    if (depsGroup && depsGroup.style.display !== 'none' && depsCheckbox && !depsCheckbox.checked) {
        updateUpdateFileStatus('Dependances manquantes non installees', 'error');
        updateUpdateFileLog('Cochez "Installer les dependances manquantes" pour continuer.');
        return;
    }

    if (!confirm('Appliquer la mise a jour depuis ce fichier ?')) {
        return;
    }

    const applyBtn = document.getElementById('update-file-apply-btn');
    if (applyBtn) applyBtn.disabled = true;
    updateUpdateFileStatus('Mise a jour en cours...', 'running');

    try {
        const formData = new FormData();
        formData.append('update', updateFileSelected);
        const force = document.getElementById('update-file-force')?.checked;
        if (force) formData.append('force', '1');
        const resetSettings = document.getElementById('update-file-reset')?.checked;
        if (resetSettings) formData.append('reset_settings', '1');
        const installDeps = document.getElementById('update-file-install-deps');
        if (installDeps && installDeps.checked) {
            formData.append('install_deps', '1');
        }

        const response = await fetch('/api/system/update/file/apply', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || 'Demarrage update echoue';
            updateUpdateFileStatus(message, 'error');
            updateUpdateFileLog(message);
            return;
        }

        updateUpdateFileStatus('Update demarree, suivi en cours...', 'running');
        updateUpdateFileLog('Suivi en cours...');
        pollUpdateFileStatus();
    } catch (error) {
        updateUpdateFileStatus(`Erreur: ${error.message}`, 'error');
        updateUpdateFileLog(error.message);
    }
}

function pollUpdateFileStatus() {
    if (updateFilePolling) clearInterval(updateFilePolling);

    const fetchStatus = async () => {
        try {
            const response = await fetch('/api/system/update/file/status');
            const data = await response.json();
            updateFilePollFailures = 0;

            const state = data.state || 'idle';
            const message = data.message || 'Etat inconnu';
            updateUpdateFileStatus(message, state === 'error' ? 'error' : (state === 'success' ? 'success' : 'running'));

            if (data.log && data.log.length) {
                updateUpdateFileLog(data.log.join('\n'));
            }

            if (state === 'success') {
                const requiresReboot = data.details?.requires_reboot === true || data.requires_reboot === true;
                if (requiresReboot) {
                    updateUpdateFileStatus('Update appliquee, redemarrage en cours...', 'success');
                    showRebootOverlay();
                    startRebootMonitoring();
                } else {
                    updateUpdateFileStatus('Update appliquee, relance en cours...', 'success');
                    setTimeout(() => {
                        window.location.reload();
                    }, 4000);
                }
                clearInterval(updateFilePolling);
                updateFilePolling = null;
            } else if (state === 'error') {
                clearInterval(updateFilePolling);
                updateFilePolling = null;
            } else if (state === 'rebooting') {
                updateUpdateFileStatus('Redemarrage en cours...', 'running');
                showRebootOverlay();
                startRebootMonitoring();
            }
        } catch (error) {
            updateFilePollFailures += 1;
            updateUpdateFileStatus('Reconnexion en cours...', 'running');
            if (updateFilePollFailures >= 5) {
                updateUpdateFileStatus('Erreur de suivi update', 'error');
                clearInterval(updateFilePolling);
                updateFilePolling = null;
            }
        }
    };

    fetchStatus();
    updateFilePolling = setInterval(fetchStatus, 2000);
}

// ============================================================================
// ONVIF Configuration Functions
// ============================================================================

/**
 * Load ONVIF status and configuration
 */
async function loadOnvifStatus() {
    try {
        const response = await fetch('/api/onvif/status');
        const data = await response.json();
        
        if (data.success) {
            updateOnvifStatusDisplay(data);
            
            // Update form fields
            const enabledToggle = document.getElementById('onvif_enabled');
            if (enabledToggle) {
                enabledToggle.checked = data.enabled;
                toggleOnvifConfig();
            }
            
            if (data.config) {
                const portInput = document.getElementById('onvif_port');
                const nameInput = document.getElementById('onvif_name');
                const usernameInput = document.getElementById('onvif_username');
                const passwordInput = document.getElementById('onvif_password');
                const rtspPortInput = document.getElementById('onvif_rtsp_port');
                const rtspPathInput = document.getElementById('onvif_rtsp_path');
                const nameSourceBadge = document.getElementById('onvif_name_source');
                const nameHint = document.getElementById('onvif_name_hint');
                
                if (portInput) portInput.value = data.config.port || 8080;
                if (nameInput) nameInput.value = data.config.name || 'UNPROVISIONNED';
                if (usernameInput) usernameInput.value = data.config.username || '';
                if (passwordInput) {
                    passwordInput.value = '';
                    passwordInput.placeholder = data.config.has_password ? '•••••••• (enregistré)' : 'Aucun mot de passe';
                }
                if (rtspPortInput) rtspPortInput.value = data.config.rtsp_port || 8554;
                if (rtspPathInput) rtspPathInput.value = data.config.rtsp_path || '/stream';
                
                // Show/hide Meeting API badge based on source
                if (nameSourceBadge) {
                    if (data.config.name_from_meeting) {
                        nameSourceBadge.style.display = 'inline';
                        if (nameHint) nameHint.textContent = 'Nom récupéré automatiquement depuis Meeting API (product_serial)';
                    } else {
                        nameSourceBadge.style.display = 'none';
                        if (nameHint) nameHint.textContent = 'Meeting API non configurée - nom par défaut utilisé';
                    }
                }
                
            }
            
            // Update ONVIF video info from video settings
            updateOnvifVideoInfo(data.video_settings);
        }
    } catch (error) {
        console.error('Error loading ONVIF status:', error);
    }
}

/**
 * Update ONVIF video info display
 */
function updateOnvifVideoInfo(settings) {
    if (!settings) return;
    
    const resEl = document.getElementById('onvif-resolution');
    const fpsEl = document.getElementById('onvif-fps');
    const bitrateEl = document.getElementById('onvif-bitrate');
    
    if (resEl) resEl.textContent = `${settings.width}x${settings.height}`;
    if (fpsEl) fpsEl.textContent = `${settings.fps} fps`;
    if (bitrateEl) {
        const bitrate = settings.bitrate ? `${settings.bitrate} kbps` : 'Auto';
        bitrateEl.textContent = bitrate;
    }
}

/**
 * Update ONVIF status display
 */
function updateOnvifStatusDisplay(data) {
    const statusDiv = document.getElementById('onvif-status');
    if (!statusDiv) return;
    
    let html = '';
    
    // Use preferred_ip from API (respects interface priority) or fallback to window.location.hostname
    const onvifHost = data.preferred_ip || window.location.hostname;
    
    if (data.enabled && data.running) {
        html = `
            <div class="status-indicator synced">
                <i class="fas fa-check-circle"></i>
                <span>Service ONVIF actif</span>
            </div>
            <div class="onvif-details">
                <span><strong>Port:</strong> ${data.config?.port || 8080}</span>
                <span><strong>Nom:</strong> ${data.config?.name || 'RPI-CAM'}</span>
                <span><strong>URL:</strong> http://${onvifHost}:${data.config?.port || 8080}/onvif/device_service</span>
            </div>
        `;
    } else if (data.enabled) {
        html = `
            <div class="status-indicator not-synced">
                <i class="fas fa-exclamation-triangle"></i>
                <span>Service ONVIF arrêté</span>
            </div>
        `;
    } else {
        html = `
            <div class="status-indicator">
                <i class="fas fa-power-off"></i>
                <span>Service ONVIF désactivé</span>
            </div>
        `;
    }
    
    statusDiv.innerHTML = html;
}

/**
 * Toggle ONVIF config section visibility
 */
function toggleOnvifConfig() {
    const enabled = document.getElementById('onvif_enabled')?.checked;
    const configDiv = document.getElementById('onvif-config');
    if (configDiv) {
        configDiv.style.display = enabled ? 'block' : 'none';
    }
}

/**
 * Save ONVIF configuration
 */
async function saveOnvifConfig() {
    try {
        const passwordValue = document.getElementById('onvif_password')?.value || '';
        const config = {
            enabled: document.getElementById('onvif_enabled')?.checked || false,
            port: parseInt(document.getElementById('onvif_port')?.value) || 8080,
            name: document.getElementById('onvif_name')?.value || '',
            username: document.getElementById('onvif_username')?.value || '',
            rtsp_port: parseInt(document.getElementById('onvif_rtsp_port')?.value) || 8554,
            rtsp_path: document.getElementById('onvif_rtsp_path')?.value || '/stream'
        };
        if (passwordValue) {
            config.password = passwordValue;
        }
        
        showToast('Enregistrement ONVIF...', 'info');
        
        const response = await fetch('/api/onvif/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration ONVIF enregistrée', 'success');
            loadOnvifStatus();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Restart ONVIF service
 */
async function restartOnvifService() {
    try {
        showToast('Redémarrage du service ONVIF...', 'info');
        
        const response = await fetch('/api/onvif/restart', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Service ONVIF redémarré', 'success');
            setTimeout(loadOnvifStatus, 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// Debug Tab Functions
// ============================================================================

/**
 * Check for Raspberry Pi firmware updates
 */
async function checkFirmwareUpdate() {
    const btn = document.getElementById('btn-check-firmware');
    const statusText = document.getElementById('firmware-status-text');
    const details = document.getElementById('firmware-details');
    const methodDiv = document.getElementById('firmware-method');
    const methodBadge = document.getElementById('firmware-method-badge');
    const outputContainer = document.getElementById('firmware-output-container');
    const output = document.getElementById('firmware-output');
    const updateBtn = document.getElementById('btn-update-firmware');
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vérification...';
    statusText.textContent = 'Vérification en cours...';
    statusText.className = 'status-value checking';
    
    try {
        const response = await fetch('/api/debug/firmware/check');
        const data = await response.json();
        
        outputContainer.style.display = 'block';
        output.textContent = data.output || data.message;
        
        // Show method badge
        if (data.method) {
            methodDiv.style.display = 'block';
            methodBadge.textContent = `${data.model} • ${data.method}`;
            // Store method for update confirmation
            updateBtn.dataset.method = data.method;
        }
        
        if (data.success) {
            // Check if firmware update is disabled (initramfs system)
            if (data.can_update === false || data.use_apt === true) {
                statusText.textContent = 'Utiliser apt upgrade';
                statusText.className = 'status-value use-apt';
                details.innerHTML = `<small>Kernel: ${data.current_version}<br>⚠️ initramfs détecté - rpi-update non supporté</small>`;
                updateBtn.disabled = true;
                updateBtn.title = 'initramfs détecté - utilisez apt upgrade ci-dessous';
            } else if (data.update_available) {
                statusText.textContent = 'Mise à jour disponible';
                statusText.className = 'status-value update-available';
                details.innerHTML = `<small>Version actuelle: ${data.current_version}</small>`;
                updateBtn.disabled = false;
            } else {
                statusText.textContent = 'À jour';
                statusText.className = 'status-value up-to-date';
                details.innerHTML = `<small>Version: ${data.current_version}</small>`;
                updateBtn.disabled = true;
            }
            // Update last check date
            document.getElementById('firmware-last-date').textContent = 'à l\'instant';
        } else {
            statusText.textContent = 'Erreur';
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            updateBtn.disabled = true;
        }
    } catch (error) {
        statusText.textContent = 'Erreur';
        statusText.className = 'status-value error';
        details.innerHTML = `<small>${error.message}</small>`;
        showToast(`Erreur: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search"></i> Vérifier';
    }
}

/**
 * Run firmware update
 */
async function runFirmwareUpdate() {
    const updateBtn = document.getElementById('btn-update-firmware');
    const method = updateBtn.dataset.method || 'unknown';
    
    // Different warning for rpi-update (experimental firmware)
    let confirmMessage = 'Voulez-vous mettre à jour le firmware?\n\nUn redémarrage sera nécessaire après la mise à jour.';
    if (method === 'rpi-update') {
        confirmMessage = '⚠️ ATTENTION: rpi-update installe un firmware EXPÉRIMENTAL!\n\n' +
            'Cela peut causer des instabilités système.\n' +
            'Utilisez uniquement si vous savez ce que vous faites.\n\n' +
            'Voulez-vous continuer?';
    }
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    const btn = document.getElementById('btn-update-firmware');
    const statusText = document.getElementById('firmware-status-text');
    const output = document.getElementById('firmware-output');
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Mise à jour...';
    statusText.textContent = 'Mise à jour en cours...';
    statusText.className = 'status-value updating';
    output.textContent = 'Téléchargement et installation du firmware...\nCela peut prendre plusieurs minutes, veuillez patienter...';
    
    try {
        const response = await fetch('/api/debug/firmware/update', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        // Show warning if present
        if (data.warning) {
            output.textContent += '\n\n⚠️ ' + data.warning;
        }
        
        if (data.success) {
            statusText.textContent = 'Redémarrage requis';
            statusText.className = 'status-value reboot-required';
            showToast('Firmware mis à jour! Redémarrez pour finaliser.', 'success');
            
            if (data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 1000);
            }
        } else {
            statusText.textContent = 'Erreur';
            statusText.className = 'status-value error';
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        statusText.textContent = 'Erreur';
        statusText.className = 'status-value error';
        showToast(`Erreur: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-download"></i> Mettre à jour';
    }
}

/**
 * Run apt update
 */
async function runAptUpdate() {
    const btn = document.getElementById('btn-apt-update');
    const statusText = document.getElementById('apt-update-status-text');
    const details = document.getElementById('apt-update-details');
    const outputContainer = document.getElementById('apt-update-output-container');
    const output = document.getElementById('apt-update-output');
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exécution...';
    statusText.textContent = 'En cours...';
    statusText.className = 'status-value running';
    outputContainer.style.display = 'block';
    output.textContent = 'Rafraîchissement des listes de paquets...\nCela peut prendre quelques minutes...';
    
    try {
        const response = await fetch('/api/debug/apt/update', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        if (data.success) {
            statusText.textContent = 'Terminé';
            statusText.className = 'status-value success';
            details.innerHTML = `<small>${data.hit_count} sources, ${data.get_count} mises à jour</small>`;
            document.getElementById('apt-update-last-date').textContent = 'à l\'instant';
            showToast(data.message, 'success');
        } else {
            statusText.textContent = 'Erreur';
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        statusText.textContent = 'Erreur';
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(`Erreur: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync"></i> Exécuter apt update';
    }
}

/**
 * Check upgradable packages
 */
async function checkAptUpgradable() {
    const btn = document.getElementById('btn-check-upgradable');
    const statusText = document.getElementById('apt-upgrade-status-text');
    const details = document.getElementById('apt-upgrade-details');
    const outputContainer = document.getElementById('apt-upgrade-output-container');
    const output = document.getElementById('apt-upgrade-output');
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Vérification...';
    statusText.textContent = 'Vérification...';
    statusText.className = 'status-value checking';
    
    try {
        const response = await fetch('/api/debug/apt/upgradable');
        const data = await response.json();
        
        outputContainer.style.display = 'block';
        
        if (data.success) {
            if (data.count > 0) {
                statusText.textContent = `${data.count} mises à jour`;
                statusText.className = 'status-value update-available';
                details.innerHTML = `<small>${data.count} paquets peuvent être mis à jour</small>`;
                
                // Format output nicely
                let formattedOutput = `=== ${data.count} paquets peuvent être mis à jour ===\n\n`;
                data.packages.forEach(pkg => {
                    formattedOutput += `• ${pkg.name} → ${pkg.version}\n`;
                });
                output.textContent = formattedOutput;
            } else {
                statusText.textContent = 'À jour';
                statusText.className = 'status-value up-to-date';
                details.innerHTML = '<small>Tous les paquets sont à jour</small>';
                output.textContent = 'Aucune mise à jour disponible.';
            }
        } else {
            statusText.textContent = 'Erreur';
            statusText.className = 'status-value error';
            output.textContent = data.message;
        }
    } catch (error) {
        statusText.textContent = 'Erreur';
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(`Erreur: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-list"></i> Voir paquets';
    }
}

/**
 * Run apt upgrade
 */
async function runAptUpgrade() {
    if (!confirm('Voulez-vous mettre à jour tous les paquets?\n\nCette opération peut prendre plusieurs minutes.')) {
        return;
    }
    
    const btn = document.getElementById('btn-apt-upgrade');
    const statusText = document.getElementById('apt-upgrade-status-text');
    const details = document.getElementById('apt-upgrade-details');
    const outputContainer = document.getElementById('apt-upgrade-output-container');
    const output = document.getElementById('apt-upgrade-output');
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Mise à jour...';
    statusText.textContent = 'En cours...';
    statusText.className = 'status-value running';
    outputContainer.style.display = 'block';
    output.textContent = 'Installation des mises à jour en cours...\nCela peut prendre plusieurs minutes, veuillez patienter...';
    
    try {
        const response = await fetch('/api/debug/apt/upgrade', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        if (data.success) {
            statusText.textContent = 'Terminé';
            statusText.className = 'status-value success';
            details.innerHTML = `<small>${data.upgraded} paquets mis à jour, ${data.newly_installed} nouveaux</small>`;
            document.getElementById('apt-upgrade-last-date').textContent = 'à l\'instant';
            showToast(data.message, 'success');
        } else {
            statusText.textContent = 'Erreur';
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        statusText.textContent = 'Erreur';
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(`Erreur: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-arrow-up"></i> Mettre à jour';
    }
}

/**
 * Toggle debug output visibility
 */
function toggleDebugOutput(section) {
    const container = document.getElementById(`${section}-output-container`);
    const toggle = document.getElementById(`${section}-output-toggle`);
    const output = container.querySelector('.debug-output');
    
    if (output.style.display === 'none') {
        output.style.display = 'block';
        toggle.className = 'fas fa-chevron-up';
    } else {
        output.style.display = 'none';
        toggle.className = 'fas fa-chevron-down';
    }
}

// Note: confirmReboot() is defined earlier in the file and uses performReboot() with the overlay

/**
 * Load system uptime for debug tab
 */
async function loadSystemUptime() {
    try {
        const response = await fetch('/api/debug/system/uptime');
        const data = await response.json();
        
        if (data.success) {
            const uptimeEl = document.getElementById('system-uptime');
            if (uptimeEl) {
                uptimeEl.textContent = data.uptime;
            }
        }
    } catch (error) {
        console.error('Error loading uptime:', error);
    }
}

/**
 * Load RTC debug information
 */
async function loadRtcDebug() {
    const statusText = document.getElementById('rtc-debug-status-text');
    const details = document.getElementById('rtc-debug-details');
    const outputContainer = document.getElementById('rtc-output-container');
    const output = document.getElementById('rtc-debug-output');
    const toggle = document.getElementById('rtc-output-toggle');

    try {
        const response = await fetch('/api/debug/rtc');
        const data = await response.json();

        if (!statusText || !details || !outputContainer || !output) {
            return;
        }

        outputContainer.style.display = 'block';
        output.textContent = JSON.stringify(data, null, 2);
        output.style.display = 'block';
        if (toggle) {
            toggle.className = 'fas fa-chevron-up';
        }

        if (data.success && data.status) {
            const enabled = data.status.effective_enabled;
            statusText.textContent = enabled ? 'Actif' : 'Inactif';
            statusText.className = `status-value ${enabled ? 'synced' : 'not-synced'}`;

            const detected = data.status.detected ? 'détecté' : 'non détecté';
            const mode = data.status.mode || 'auto';
            details.innerHTML = `<small>Mode: ${mode} • RTC ${detected} • Overlay: ${data.status.overlay_configured ? 'ok' : 'absent'}</small>`;
        } else {
            statusText.textContent = 'Erreur';
            statusText.className = 'status-value warning';
            details.innerHTML = `<small>${data.message || 'Erreur RTC'}</small>`;
        }
    } catch (error) {
        if (statusText) {
            statusText.textContent = 'Erreur';
            statusText.className = 'status-value warning';
        }
        if (details) {
            details.innerHTML = `<small>${error.message}</small>`;
        }
    }
}

/**
 * Load last action dates for debug operations
 */
async function loadDebugLastActions() {
    try {
        const response = await fetch('/api/debug/last-actions');
        const data = await response.json();
        
        if (data.success && data.last_actions) {
            const actions = data.last_actions;
            
            // Firmware check
            if (actions.firmware_check) {
                document.getElementById('firmware-last-date').textContent = formatLastActionDate(actions.firmware_check);
            }
            
            // APT update
            if (actions.apt_update) {
                document.getElementById('apt-update-last-date').textContent = formatLastActionDate(actions.apt_update);
            }
            
            // APT upgrade
            if (actions.apt_upgrade) {
                document.getElementById('apt-upgrade-last-date').textContent = formatLastActionDate(actions.apt_upgrade);
            }
        }
    } catch (error) {
        console.error('Error loading last actions:', error);
    }
}

/**
 * Format a date string for display
 */
function formatLastActionDate(dateStr) {
    if (!dateStr) return 'jamais';
    
    try {
        const date = new Date(dateStr.replace(' ', 'T'));
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'à l\'instant';
        if (diffMins < 60) return `il y a ${diffMins} min`;
        if (diffHours < 24) return `il y a ${diffHours}h`;
        if (diffDays < 7) return `il y a ${diffDays} jour${diffDays > 1 ? 's' : ''}`;
        
        // Format as date
        return date.toLocaleDateString('fr-FR', { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return dateStr;
    }
}

/**
 * Load APT scheduler configuration
 */
async function loadAptScheduler() {
    try {
        const response = await fetch('/api/debug/apt/scheduler');
        const data = await response.json();
        
        if (data.success && data.scheduler) {
            const scheduler = data.scheduler;
            
            // Set toggle state
            const enabledCheckbox = document.getElementById('apt-scheduler-enabled');
            enabledCheckbox.checked = scheduler.enabled;
            
            // Update status text
            const statusText = document.getElementById('scheduler-status-text');
            statusText.textContent = scheduler.enabled ? 'Activé' : 'Désactivé';
            
            // Show/hide config
            document.getElementById('scheduler-config').style.display = scheduler.enabled ? 'block' : 'none';
            
            // Set values
            document.getElementById('scheduler-update-hour').value = scheduler.update_hour || 3;
            document.getElementById('scheduler-update-minute').value = scheduler.update_minute || 0;
            document.getElementById('scheduler-upgrade-enabled').checked = scheduler.upgrade_enabled || false;
            document.getElementById('scheduler-upgrade-day').value = scheduler.upgrade_day || 0;
            
            // Show/hide upgrade day selector
            document.getElementById('scheduler-upgrade-day-row').style.display = 
                scheduler.upgrade_enabled ? 'flex' : 'none';
        }
    } catch (error) {
        console.error('Error loading apt scheduler:', error);
    }
}

/**
 * Toggle APT scheduler on/off
 */
function toggleAptScheduler() {
    const enabled = document.getElementById('apt-scheduler-enabled').checked;
    const configDiv = document.getElementById('scheduler-config');
    const statusText = document.getElementById('scheduler-status-text');
    
    configDiv.style.display = enabled ? 'block' : 'none';
    statusText.textContent = enabled ? 'Configuration...' : 'Désactivé';
    
    // If disabling, save immediately
    if (!enabled) {
        saveAptScheduler();
    }
}

/**
 * Update scheduler config UI based on selections
 */
function updateSchedulerConfig() {
    const upgradeEnabled = document.getElementById('scheduler-upgrade-enabled').checked;
    document.getElementById('scheduler-upgrade-day-row').style.display = upgradeEnabled ? 'flex' : 'none';
}

/**
 * Save APT scheduler configuration
 */
async function saveAptScheduler() {
    const btn = document.getElementById('btn-save-scheduler');
    const statusText = document.getElementById('scheduler-status-text');
    
    const config = {
        enabled: document.getElementById('apt-scheduler-enabled').checked,
        update_hour: parseInt(document.getElementById('scheduler-update-hour').value),
        update_minute: parseInt(document.getElementById('scheduler-update-minute').value),
        upgrade_enabled: document.getElementById('scheduler-upgrade-enabled').checked,
        upgrade_day: parseInt(document.getElementById('scheduler-upgrade-day').value)
    };
    
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enregistrement...';
    }
    
    try {
        const response = await fetch('/api/debug/apt/scheduler', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await response.json();
        
        if (data.success) {
            statusText.textContent = config.enabled ? 'Activé' : 'Désactivé';
            showToast(data.message || 'Planification enregistrée', 'success');
        } else {
            showToast(data.message || 'Erreur', 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-save"></i> Enregistrer';
        }
    }
}

// ============================================================================
// WEB TERMINAL FUNCTIONS
// ============================================================================

let terminalHistory = [];
let terminalHistoryIndex = -1;

/**
 * Handle terminal keydown events (Enter, Up/Down arrows)
 */
function handleTerminalKeydown(event) {
    const input = document.getElementById('terminal-input');
    
    if (event.key === 'Enter') {
        event.preventDefault();
        executeTerminalCommand();
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (terminalHistoryIndex < terminalHistory.length - 1) {
            terminalHistoryIndex++;
            input.value = terminalHistory[terminalHistory.length - 1 - terminalHistoryIndex];
        }
    } else if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (terminalHistoryIndex > 0) {
            terminalHistoryIndex--;
            input.value = terminalHistory[terminalHistory.length - 1 - terminalHistoryIndex];
        } else if (terminalHistoryIndex === 0) {
            terminalHistoryIndex = -1;
            input.value = '';
        }
    }
}

/**
 * Execute a terminal command
 */
async function executeTerminalCommand() {
    const input = document.getElementById('terminal-input');
    const output = document.getElementById('terminal-output');
    const command = input.value.trim();
    
    if (!command) return;
    
    // Add to history
    terminalHistory.push(command);
    terminalHistoryIndex = -1;
    input.value = '';
    
    // Handle special commands
    if (command === 'clear') {
        clearTerminal();
        return;
    }
    
    if (command === 'help') {
        showAllowedCommands();
        return;
    }
    
    // Display command
    appendTerminalLine(command, 'terminal-command');
    
    try {
        const response = await fetch('/api/debug/terminal/exec', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command, timeout: 30 })
        });
        
        const data = await response.json();
        
        if (response.status === 403) {
            appendTerminalLine(`Commande non autorisée: ${command.split(' ')[0]}`, 'terminal-error');
            appendTerminalLine('Tapez "help" pour voir les commandes autorisées.', 'terminal-info');
        } else if (data.success) {
            if (data.stdout) {
                appendTerminalLine(data.stdout, 'terminal-stdout');
            }
            if (data.stderr) {
                appendTerminalLine(data.stderr, 'terminal-stderr');
            }
            if (data.returncode !== 0 && !data.stdout && !data.stderr) {
                appendTerminalLine(`Commande terminée avec code ${data.returncode}`, 'terminal-info');
            }
        } else {
            appendTerminalLine(`Erreur: ${data.error}`, 'terminal-error');
        }
    } catch (error) {
        appendTerminalLine(`Erreur réseau: ${error.message}`, 'terminal-error');
    }
    
    // Scroll to bottom
    output.scrollTop = output.scrollHeight;
}

/**
 * Append a line to terminal output
 */
function appendTerminalLine(text, className = '') {
    const output = document.getElementById('terminal-output');
    const line = document.createElement('div');
    line.className = `terminal-line ${className}`;
    line.textContent = text;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;
}

/**
 * Clear terminal output
 */
function clearTerminal() {
    const output = document.getElementById('terminal-output');
    output.innerHTML = '';
    appendTerminalLine('Terminal effacé.', 'terminal-info');
}

/**
 * Show allowed commands
 */
async function showAllowedCommands() {
    appendTerminalLine('Chargement des commandes autorisées...', 'terminal-info');
    
    try {
        const response = await fetch('/api/debug/terminal/allowed');
        const data = await response.json();
        
        if (data.success) {
            appendTerminalLine('=== Commandes autorisées ===', 'terminal-success');
            
            // Group commands by category
            const categories = {
                'Système': ['ls', 'cat', 'head', 'tail', 'grep', 'find', 'df', 'du', 'free', 'top', 'ps', 'uptime', 'date', 'hostname', 'uname', 'whoami', 'id', 'pwd'],
                'Journaux': ['journalctl', 'dmesg'],
                'Services': ['systemctl', 'service'],
                'Réseau': ['ip', 'ifconfig', 'iwconfig', 'nmcli', 'netstat', 'ss', 'ping', 'traceroute', 'curl', 'wget'],
                'Matériel': ['vcgencmd', 'pinctrl', 'lsusb', 'lspci', 'lsblk', 'lscpu', 'lshw', 'lsmod', 'v4l2-ctl'],
                'Média': ['ffprobe', 'ffmpeg', 'gst-launch-1.0', 'gst-inspect-1.0', 'test-launch'],
                'Paquets': ['apt', 'apt-get', 'apt-cache', 'dpkg'],
                'Utilitaires': ['echo', 'which', 'whereis', 'file', 'stat', 'wc', 'sort', 'uniq', 'awk', 'sed', 'cut', 'tr', 'tee']
            };
            
            for (const [category, cmds] of Object.entries(categories)) {
                const available = cmds.filter(c => data.commands.includes(c));
                if (available.length > 0) {
                    appendTerminalLine(`\n${category}: ${available.join(', ')}`, 'terminal-stdout');
                }
            }
            
            appendTerminalLine('\nNote: Utilisez "sudo" devant une commande pour les droits root.', 'terminal-info');
        } else {
            appendTerminalLine('Erreur lors du chargement des commandes.', 'terminal-error');
        }
    } catch (error) {
        appendTerminalLine(`Erreur: ${error.message}`, 'terminal-error');
    }
}

// Load uptime and debug data when debug tab is shown
document.addEventListener('DOMContentLoaded', () => {
    // Add observer for debug tab
    const debugTab = document.getElementById('tab-debug');
    if (debugTab) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.target.classList.contains('active')) {
                    loadSystemUptime();
                    loadDebugLastActions();
                    loadAptScheduler();
                    loadRtcDebug();
                }
            });
        });
        observer.observe(debugTab, { attributes: true, attributeFilter: ['class'] });
    }
});

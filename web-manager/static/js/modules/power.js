/**
 * RTSP Recorder Web Manager - Power and reboot functions
 * Version: 2.32.95
 */

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





/**
 * RTSP Recorder Web Manager - Meeting/NTP/RTC functions
 * Version: 2.32.83
 */

(function () {
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

const CURRENT_VERSION = (window.APP_VERSION || '').replace(/^v/, '') || '0.0.0';

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

    window.toggleMeetingConfig = toggleMeetingConfig;
    window.togglePassword = togglePassword;
    window.testMeetingConnection = testMeetingConnection;
    window.sendMeetingHeartbeat = sendMeetingHeartbeat;
    window.getMeetingAvailability = getMeetingAvailability;
    window.fetchMeetingDeviceInfo = fetchMeetingDeviceInfo;
    window.requestMeetingTunnel = requestMeetingTunnel;
    window.updateMeetingStatus = updateMeetingStatus;
    window.updateMeetingConfigStatus = updateMeetingConfigStatus;
    window.loadMeetingConfig = loadMeetingConfig;
    window.saveMeetingConfig = saveMeetingConfig;
    window.loadMeetingStatus = loadMeetingStatus;
    window.validateMeetingCredentials = validateMeetingCredentials;
    window.provisionDevice = provisionDevice;
    window.showMasterResetModal = showMasterResetModal;
    window.closeMasterResetModal = closeMasterResetModal;
    window.executeMasterReset = executeMasterReset;
    window.loadNtpConfig = loadNtpConfig;
    window.updateNtpStatus = updateNtpStatus;
    window.saveNtpConfig = saveNtpConfig;
    window.syncNtpNow = syncNtpNow;
    window.loadRtcConfig = loadRtcConfig;
    window.updateRtcStatus = updateRtcStatus;
    window.saveRtcConfig = saveRtcConfig;
    window.updateSnmpUiState = updateSnmpUiState;
    window.updateRebootScheduleUiState = updateRebootScheduleUiState;
    window._populateRebootScheduleSelects = _populateRebootScheduleSelects;
    window.loadRebootSchedule = loadRebootSchedule;
    window.saveRebootSchedule = saveRebootSchedule;
    window.loadSnmpConfig = loadSnmpConfig;
    window.saveSnmpConfig = saveSnmpConfig;
    window.testSnmpConfig = testSnmpConfig;
    window.checkForUpdates = checkForUpdates;
    window.performUpdate = performUpdate;
    window.updateBackupStatus = updateBackupStatus;
    window.openBackupFilePicker = openBackupFilePicker;
    window.handleBackupFileSelected = handleBackupFileSelected;
    window.backupConfiguration = backupConfiguration;
    window.checkBackupFile = checkBackupFile;
    window.restoreBackupFile = restoreBackupFile;
    window.openUpdateFilePicker = openUpdateFilePicker;
    window.handleUpdateFileSelected = handleUpdateFileSelected;
    window.showUpdateFileModal = showUpdateFileModal;
    window.closeUpdateFileModal = closeUpdateFileModal;
    window.updateUpdateFileStatus = updateUpdateFileStatus;
    window.updateUpdateFileLog = updateUpdateFileLog;
    window.onUpdateFileForceChanged = onUpdateFileForceChanged;
    window.checkUpdateFile = checkUpdateFile;
    window.applyUpdateFile = applyUpdateFile;
    window.pollUpdateFileStatus = pollUpdateFileStatus;
    window.loadOnvifStatus = loadOnvifStatus;
    window.updateOnvifVideoInfo = updateOnvifVideoInfo;
    window.updateOnvifStatusDisplay = updateOnvifStatusDisplay;
    window.toggleOnvifConfig = toggleOnvifConfig;
    window.saveOnvifConfig = saveOnvifConfig;
    window.restartOnvifService = restartOnvifService;
    window.checkFirmwareUpdate = checkFirmwareUpdate;
    window.runFirmwareUpdate = runFirmwareUpdate;
    window.runAptUpdate = runAptUpdate;
    window.checkAptUpgradable = checkAptUpgradable;
    window.runAptUpgrade = runAptUpgrade;
    window.toggleDebugOutput = toggleDebugOutput;
    window.loadSystemUptime = loadSystemUptime;
    window.loadRtcDebug = loadRtcDebug;
    window.loadDebugLastActions = loadDebugLastActions;
    window.formatLastActionDate = formatLastActionDate;
    window.loadAptScheduler = loadAptScheduler;
    window.toggleAptScheduler = toggleAptScheduler;
    window.updateSchedulerConfig = updateSchedulerConfig;
    window.saveAptScheduler = saveAptScheduler;
    window.handleTerminalKeydown = handleTerminalKeydown;
    window.executeTerminalCommand = executeTerminalCommand;
    window.appendTerminalLine = appendTerminalLine;
    window.clearTerminal = clearTerminal;
    window.showAllowedCommands = showAllowedCommands;
})();

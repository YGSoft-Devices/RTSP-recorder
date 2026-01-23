/**
 * RTSP Recorder Web Manager - Meeting/NTP/RTC functions
 * Version: 2.33.06
 */

(function () {
const t = window.t || function (key) { return key; };
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
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.meeting.test_in_progress')}`;
    
    try {
        const response = await fetch('/api/meeting/test', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message}`;
            if (data.data) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.data, null, 2)}</pre>`;
            }
            showToast(t('ui.meeting.connection_success'), 'success');
            updateMeetingStatus(true);
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            if (data.details) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.details, null, 2)}</pre>`;
            }
            showToast(t('ui.meeting.connection_failed'), 'error');
            updateMeetingStatus(false);
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}`;
        showToast(t('ui.meeting.test_error'), 'error');
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
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.meeting.heartbeat_sending')}`;
    
    try {
        const response = await fetch('/api/meeting/heartbeat', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `<i class="fas fa-heartbeat"></i> ${data.message || t('ui.meeting.heartbeat_sent')}`;
            if (data.payload) {
                resultDiv.innerHTML += `<pre>${t('ui.meeting.heartbeat_payload')}:\n${JSON.stringify(data.payload, null, 2)}</pre>`;
            }
            showToast(t('ui.meeting.heartbeat_sent'), 'success');
            updateMeetingStatus(true);
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || data.message || t('ui.errors.generic')}`;
            showToast(t('ui.meeting.heartbeat_failed'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}`;
        showToast(t('ui.meeting.heartbeat_error'), 'error');
    }
}

/**
 * Get device availability from Meeting API
 */
async function getMeetingAvailability() {
    const resultDiv = document.getElementById('meeting-test-result');
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.meeting.availability_checking')}`;
    
    try {
        const response = await fetch('/api/meeting/availability');
        const data = await response.json();
        
        if (data.success) {
            const avail = data.data || data;
            // API Meeting returns status: "Available" or "Unavailable"
            const isOnline = avail.online === true || avail.status === 'Available' || avail.status === 'available';
            const onlineText = isOnline ? t('ui.value.yes') : t('ui.value.no');
            const statusText = avail.status || t('ui.value.na');
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `
                <i class="fas fa-info-circle"></i> ${t('ui.meeting.availability_status')}
                <div class="availability-info">
                    <p><strong>${t('ui.meeting.availability.online_label')}</strong> ${onlineText}</p>
                    <p><strong>${t('ui.meeting.availability.status_label')}</strong> ${statusText}</p>
                    ${avail.last_heartbeat ? `<p><strong>${t('ui.meeting.availability.last_heartbeat_label')}</strong> ${avail.last_heartbeat}</p>` : ''}
                    ${avail.last_seen ? `<p><strong>${t('ui.meeting.availability.last_seen_label')}</strong> ${new Date(avail.last_seen).toLocaleString()}</p>` : ''}
                    ${avail.uptime ? `<p><strong>${t('ui.meeting.availability.uptime_label')}</strong> ${t('ui.meeting.availability.uptime_minutes', { minutes: avail.uptime })}</p>` : ''}
                    ${avail.ip ? `<p><strong>${t('ui.meeting.availability.ip_label')}</strong> ${avail.ip}</p>` : ''}
                </div>
            `;
            showToast(t('ui.meeting.availability_retrieved'), 'success');
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || data.message || t('ui.errors.generic')}`;
            showToast(t('ui.meeting.availability_failed'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}`;
        showToast(t('ui.meeting.availability_error'), 'error');
    }
}

/**
 * Fetch device info from Meeting API
 */
async function fetchMeetingDeviceInfo() {
    const infoDiv = document.getElementById('meeting-device-info');
    infoDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.meeting.device_info_loading')}`;
    
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
            const deviceName = device.product_serial || device.name || device.device_name || t('ui.status.unknown');
            // IP from device info
            const deviceIp = device.ip_address || device.ip || t('ui.value.na');
            // Online status from availability API
            const isOnline = avail.status === 'Available' || avail.status === 'available' || avail.online === true;
            // Last seen from availability
            const lastSeen = avail.last_heartbeat || avail.last_seen || device.last_seen;
            
            // Format last_seen date
            let lastSeenStr = t('ui.value.na');
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
                    const serviceName = (typeof s === 'string') ? s : (s.name || t('ui.status.unknown'));
                    return `<span class="service-badge"><i class="fas fa-plug"></i> ${serviceName}</span>`;
                }).join('');
                
                servicesHtml = `
                    <div class="services-section">
                        <label><i class="fas fa-cogs"></i> ${t('ui.meeting.services_label')}</label>
                        <div class="services-badges">${serviceBadges}</div>
                    </div>
                `;
            } else {
                servicesHtml = `
                    <div class="services-section">
                        <label><i class="fas fa-cogs"></i> ${t('ui.meeting.services_label')}</label>
                        <div class="services-badges"><span class="service-badge service-none">${t('ui.meeting.services_none')}</span></div>
                    </div>
                `;
            }
            
            // WiFi AP section (if available)
            let wifiApHtml = '';
            if (device.ap_ssid || device.ap_password) {
                wifiApHtml = `
                    <div class="wifi-ap-section">
                        <label><i class="fas fa-wifi"></i> ${t('ui.meeting.wifi_ap_label')}</label>
                        <div class="wifi-ap-info">
                            <div class="wifi-ap-item">
                                <span class="wifi-label">SSID</span>
                                <span class="wifi-value mono">${device.ap_ssid || t('ui.value.na')}</span>
                            </div>
                            <div class="wifi-ap-item">
                                <span class="wifi-label">${t('ui.meeting.wifi_password_label')}</span>
                                <span class="wifi-value mono">${device.ap_password || t('ui.value.na')}</span>
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
                        <label><i class="fas fa-sticky-note"></i> ${t('ui.meeting.note_label')}</label>
                        <p class="note-content">${device.note}</p>
                    </div>
                `;
            }
            
            infoDiv.innerHTML = `
                <div class="device-info-grid">
                    <div class="info-item">
                        <label><i class="fas fa-key"></i> ${t('ui.meeting.device_key_label')}</label>
                        <span class="mono">${device.device_key || t('ui.value.na')}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-tag"></i> ${t('ui.meeting.device_name_label')}</label>
                        <span>${deviceName}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-circle ${isOnline ? 'text-success' : 'text-danger'}"></i> ${t('ui.meeting.device_status_label')}</label>
                        <span>${isOnline ? t('ui.status.online') : t('ui.status.offline')}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-network-wired"></i> ${t('ui.meeting.device_ip_label')}</label>
                        <span class="mono">${deviceIp}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-clock"></i> ${t('ui.meeting.device_last_activity_label')}</label>
                        <span>${lastSeenStr}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-coins"></i> ${t('ui.meeting.device_tokens_label')}</label>
                        <span>${device.token_count !== undefined ? device.token_count : t('ui.value.na')}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-check-circle ${device.authorized ? 'text-success' : 'text-danger'}"></i> ${t('ui.meeting.device_authorized_label')}</label>
                        <span>${device.authorized ? t('ui.value.yes') : t('ui.value.no')}</span>
                    </div>
                </div>
                ${noteHtml}
                ${wifiApHtml}
                ${servicesHtml}
            `;
            showToast(t('ui.meeting.device_info_loaded'), 'success');
        } else {
            infoDiv.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-circle"></i> ${deviceData.error || deviceData.message || t('ui.meeting.device_info_load_failed')}</p>`;
            showToast(t('ui.meeting.device_info_load_failed'), 'error');
        }
    } catch (error) {
        infoDiv.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}</p>`;
        showToast(t('ui.meeting.device_info_load_error'), 'error');
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
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.meeting.tunnel_requesting', { service: service })}`;
    
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
                    html += `<p><strong>${t('ui.meeting.tunnel_url_label')}</strong> <code>${data.data.tunnel_url}</code></p>`;
                }
                if (data.data.port) {
                    html += `<p><strong>${t('ui.meeting.tunnel_remote_port_label')}</strong> <code>${data.data.port}</code></p>`;
                }
                if (data.data.expires_at) {
                    html += `<p><strong>${t('ui.meeting.tunnel_expires_label')}</strong> ${new Date(data.data.expires_at).toLocaleString()}</p>`;
                }
            }
            resultDiv.innerHTML = html;
            showToast(t('ui.meeting.tunnel_created', { service: service }), 'success');
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            if (data.details) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.details, null, 2)}</pre>`;
            }
            showToast(t('ui.meeting.tunnel_failed'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}`;
        showToast(t('ui.meeting.tunnel_error'), 'error');
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
            statusEl.innerHTML = `<i class="fas fa-circle"></i> ${t('ui.status.connected')}`;
        } else {
            statusEl.className = 'status-indicator disconnected';
            statusEl.innerHTML = `<i class="fas fa-circle"></i> ${t('ui.status.disconnected')}`;
        }
    }
    
    if (detailsEl && connected) {
        detailsEl.innerHTML = `<small>${t('ui.meeting.last_connection_label')} ${new Date().toLocaleTimeString()}</small>`;
    }
}

function updateMeetingConfigStatus() {
    const enabledToggle = document.getElementById('meeting_enabled_toggle');
    const autoToggle = document.getElementById('meeting_auto_connect');
    const enabledStatus = document.getElementById('meeting-enabled-status');
    const autoStatus = document.getElementById('meeting-auto-connect-status');

    if (enabledStatus && enabledToggle) {
        enabledStatus.textContent = enabledToggle.checked ? t('ui.value.enabled') : t('ui.value.disabled');
    }
    if (autoStatus && autoToggle) {
        autoStatus.textContent = autoToggle.checked ? t('ui.value.enabled') : t('ui.value.disabled');
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
            tokenInput.placeholder = config.has_token ? t('ui.meeting.token_placeholder_saved') : t('ui.meeting.token_placeholder_none');
        }
        if (provisionedBadge) {
            if (config.provisioned) {
                provisionedBadge.textContent = t('ui.value.yes');
                provisionedBadge.className = 'badge badge-success';
            } else {
                provisionedBadge.textContent = t('ui.value.no');
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

        showToast(t('ui.meeting.saving'), 'info');

        const response = await fetch('/api/meeting/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            showToast(t('ui.meeting.saved'), 'success');
            loadMeetingStatus();
            loadMeetingConfig();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message || data.error || t('ui.errors.generic') }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
                    statusEl.innerHTML = `<i class="fas fa-circle"></i> ${t('ui.meeting.status.not_provisioned')}`;
                }
                if (detailsEl) {
                    detailsEl.innerHTML = `<small>${t('ui.meeting.status.enter_credentials')}</small>`;
                }
            } else if (status.connected) {
                // Connected and heartbeat working
                if (statusEl) {
                    statusEl.className = 'status-indicator connected';
                    statusEl.innerHTML = `<i class="fas fa-circle"></i> ${t('ui.status.connected')}`;
                }
                if (detailsEl) {
                    let details = `<small>${t('ui.meeting.device_label')}: ${status.device_key}`;
                    if (status.last_heartbeat_ago !== null) {
                        details += ` ? ${t('ui.meeting.last_heartbeat_ago', { seconds: status.last_heartbeat_ago })}`;
                    }
                    if (status.heartbeat_thread_running) {
                        details += ` ? ${t('ui.meeting.heartbeat_interval_status', { seconds: status.heartbeat_interval })}`;
                    }
                    details += '</small>';
                    detailsEl.innerHTML = details;
                }
            } else if (status.enabled) {
                // Configured and enabled but not yet connected (or connection failed)
                if (statusEl) {
                    if (status.last_error) {
                        statusEl.className = 'status-indicator disconnected';
                        statusEl.innerHTML = `<i class="fas fa-circle"></i> ${t('ui.meeting.connection_error_status')}`;
                    } else {
                        statusEl.className = 'status-indicator pending';
                        statusEl.innerHTML = `<i class="fas fa-circle"></i> ${t('ui.meeting.connection_pending_status')}`;
                    }
                }
                if (detailsEl) {
                    if (status.last_error) {
                        detailsEl.innerHTML = `<small>${t('ui.meeting.device_label')}: ${status.device_key} ? ${status.last_error}</small>`;
                    } else {
                        detailsEl.innerHTML = `<small>${t('ui.meeting.device_label')}: ${status.device_key} ? ${t('ui.meeting.awaiting_first_heartbeat')}</small>`;
                    }
                }
            } else {
                // Configured but disabled
                if (statusEl) {
                    statusEl.className = 'status-indicator disconnected';
                    statusEl.innerHTML = `<i class="fas fa-circle"></i> ${t('ui.value.disabled')}`;
                }
                if (detailsEl) {
                    detailsEl.innerHTML = `<small>${t('ui.meeting.device_label')}: ${status.device_key} ? ${t('ui.meeting.disabled_status')}</small>`;
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
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('ui.meeting.validation.fill_all_fields')}`;
        if (provisionBtn) provisionBtn.disabled = true;
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.meeting.validation.in_progress')}`;
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
                tokenWarning = `<br><strong style="color: var(--danger-color);">${t('ui.meeting.validation.token_none')}</strong>`;
                if (provisionBtn) provisionBtn.disabled = true;
            } else if (device.token_count === 1) {
                tokenClass = 'warning';
                tokenWarning = `<br><small style="color: var(--warning-color);">${t('ui.meeting.validation.token_last')}</small>`;
                if (provisionBtn) provisionBtn.disabled = false;
            } else {
                if (provisionBtn) provisionBtn.disabled = false;
            }
            
            resultDiv.innerHTML = `
                <i class="fas fa-check-circle"></i> <strong>${t('ui.meeting.validation.valid')}</strong>
                <div class="provision-info">
                    <div class="provision-info-item">
                        <span class="label">${t('ui.meeting.validation.device_label')}</span>
                        <span class="value">${device.name || t('ui.meeting.validation.device_name_fallback')}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${t('ui.meeting.validation.authorized_label')}</span>
                        <span class="value ${device.authorized ? 'success' : 'danger'}">${device.authorized ? t('ui.value.yes') : t('ui.value.no')}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${t('ui.meeting.validation.tokens_available_label')}</span>
                        <span class="value ${tokenClass}">${device.token_count}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${t('ui.meeting.validation.online_label')}</span>
                        <span class="value">${device.online ? t('ui.value.yes') : t('ui.value.no')}</span>
                    </div>
                </div>
                ${tokenWarning}
                ${device.token_count > 0 && device.authorized ? `<p style="margin-top: 10px;"><i class="fas fa-info-circle"></i> ${t('ui.meeting.validation.provision_hint')}</p>` : ''}
            `;
            
            if (!device.authorized) {
                resultDiv.innerHTML += `<p style="color: var(--danger-color); margin-top: 10px;"><i class="fas fa-ban"></i> ${t('ui.meeting.validation.not_authorized')}</p>`;
                if (provisionBtn) provisionBtn.disabled = true;
            }
            
            showToast(t('ui.meeting.validation.valid_toast'), 'success');
        } else {
            resultDiv.className = 'meeting-result validation-error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> <strong>${t('ui.meeting.validation.invalid')}</strong><br>${data.message}`;
            if (provisionBtn) provisionBtn.disabled = true;
            showToast(t('ui.meeting.validation.invalid_toast'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result validation-error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}`;
        if (provisionBtn) provisionBtn.disabled = true;
        showToast(t('ui.meeting.validation.error'), 'error');
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
    
    if (!confirm(t('ui.meeting.provision.confirm'))) {
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.meeting.provision.in_progress')}`;
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
                <i class="fas fa-check-circle"></i> <strong>${t('ui.meeting.provision.success_title')}</strong>
                <div class="provision-info">
                    <div class="provision-info-item">
                        <span class="label">${t('ui.meeting.provision.hostname_label')}</span>
                        <span class="value">${data.hostname}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${t('ui.meeting.provision.token_consumed_label')}</span>
                        <span class="value success">${t('ui.value.yes')}</span>
                    </div>
                </div>
                <p style="margin-top: 15px; color: var(--warning-color);">
                    <i class="fas fa-exclamation-triangle"></i> <strong>${t('ui.meeting.provision.important_label')}</strong> ${t('ui.meeting.provision.hostname_changed')}
                    ${t('ui.meeting.provision.access_hint')}
                    <br><code>http://${data.hostname}.local</code>
                </p>
            `;
            showToast(t('ui.meeting.provision.success_toast'), 'success');
            
            // Reload status after a short delay
            setTimeout(() => {
                loadMeetingStatus();
            }, 2000);
        } else {
            resultDiv.className = 'meeting-result validation-error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> <strong>${t('ui.meeting.provision.failed_title')}</strong><br>${data.message}`;
            if (provisionBtn) provisionBtn.disabled = false;
            showToast(t('ui.meeting.provision.failed_toast'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result validation-error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${t('ui.errors.with_message', { message: error.message })}`;
        if (provisionBtn) provisionBtn.disabled = false;
        showToast(t('ui.meeting.provision.error'), 'error');
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
        showToast(t('ui.meeting.master_reset.code_required'), 'warning');
        return;
    }
    
    try {
        showToast(t('ui.meeting.master_reset.in_progress'), 'info');
        
        const response = await fetch('/api/meeting/master-reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_code: code })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeMasterResetModal();
            showToast(t('ui.meeting.master_reset.success'), 'success');
            loadMeetingStatus();
            // Reload page to refresh all config
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showToast(data.message || t('ui.meeting.master_reset.failed'), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
                checkUpdateRepo();
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
                error: data.message || t('ui.system.ntp.error')
            });
        }
    } catch (error) {
        console.error('Error loading NTP config:', error);
        updateNtpStatus({
            synchronized: false,
            server: null,
            current_time: null,
            timezone: null,
            error: error.message || t('ui.system.ntp.error')
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
    html += `<span>${data.synchronized ? t('ui.system.ntp.synced') : t('ui.system.ntp.not_synced')}</span>`;
    html += `</div>`;
    
    if (data.error) {
        html += `<div class="ntp-details"><span><strong>${t('ui.system.ntp.error_label')}</strong> ${data.error}</span></div>`;
    } else if (data.server || data.current_time) {
        html += `<div class="ntp-details">`;
        if (data.server) html += `<span><strong>${t('ui.system.ntp.server_label')}</strong> ${data.server}</span>`;
        if (data.current_time) html += `<span><strong>${t('ui.system.ntp.system_time_label')}</strong> ${data.current_time}</span>`;
        if (data.timezone) html += `<span><strong>${t('ui.system.ntp.timezone_label')}</strong> ${data.timezone}</span>`;
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
        showToast(t('ui.system.ntp.server_required'), 'warning');
        return;
    }
    
    try {
        showToast(t('ui.system.ntp.configuring'), 'info');
        
        const response = await fetch('/api/system/ntp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.system.ntp.configured'), 'success');
            loadNtpConfig();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Force NTP synchronization now
 */
async function syncNtpNow() {
    try {
        showToast(t('ui.system.ntp.syncing'), 'info');
        
        const response = await fetch('/api/system/ntp/sync', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.system.ntp.synced_toast'), 'success');
            loadNtpConfig();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
                error: data.message || t('ui.system.rtc.error')
            });
        }
    } catch (error) {
        console.error('Error loading RTC config:', error);
        updateRtcStatus({
            success: false,
            error: error.message || t('ui.system.rtc.error')
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
                <span>${t('ui.system.rtc.error')}</span>
            </div>
            <div class="rtc-details"><span><strong>${t('ui.system.rtc.error_label')}</strong> ${data.error}</span></div>
        `;
        return;
    }

    const enabled = !!data.effective_enabled;
    const detected = !!data.detected;
    const indicatorClass = enabled ? 'synced' : 'not-synced';
    const indicatorLabel = enabled ? t('ui.system.rtc.active') : t('ui.system.rtc.inactive');
    const modeLabel = data.mode || 'auto';
    const viaLabel = data.detected_via ? ` (${data.detected_via})` : '';

    let html = `<div class="status-indicator ${indicatorClass}">`;
    html += `<i class="fas fa-${enabled ? 'check-circle' : 'exclamation-triangle'}"></i>`;
    html += `<span>RTC ${indicatorLabel}</span>`;
    html += `</div>`;
    html += `<div class="rtc-details">`;
    html += `<span><strong>${t('ui.system.rtc.mode_label')}</strong> ${modeLabel}</span>`;
    html += `<span><strong>${t('ui.system.rtc.detected_label')}</strong> ${detected ? t('ui.value.yes') : t('ui.value.no')}${detected ? viaLabel : ''}</span>`;
    html += `<span><strong>${t('ui.system.rtc.overlay_label')}</strong> ${data.overlay_configured ? t('ui.system.rtc.overlay_configured') : t('ui.system.rtc.overlay_not_configured')}</span>`;
    html += `<span><strong>${t('ui.system.rtc.i2c_label')}</strong> ${data.i2c_enabled ? t('ui.value.enabled') : t('ui.value.disabled')}</span>`;
    if (data.auto_pending) {
        if (!data.i2c_enabled) {
            html += `<span><strong>${t('ui.value.auto')}:</strong> ${t('ui.system.rtc.auto_i2c_disabled')}</span>`;
        } else {
            html += `<span><strong>${t('ui.value.auto')}:</strong> ${t('ui.system.rtc.auto_module_detected')}</span>`;
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
        showToast(t('ui.system.rtc.applying'), 'info');

        const response = await fetch('/api/system/rtc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: rtcMode })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message || t('ui.system.rtc.configured'), 'success');
            loadRtcConfig();
            if (data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 800);
            }
        } else {
            showToast(t('ui.errors.with_message', { message: data.message || t('ui.system.rtc.apply_failed') }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
        showToast(t('ui.system.reboot_schedule.saving'), 'info');
        const response = await fetch('/api/system/reboot/schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, hour, minute, days })
        });
        const data = await response.json();
        if (data.success) {
            showToast(t('ui.system.reboot_schedule.saved'), 'success');
            loadRebootSchedule();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message || t('ui.system.reboot_schedule.save_failed') }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
        showToast(t('ui.system.snmp.configuring'), 'info');
        const response = await fetch('/api/system/snmp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, host, port })
        });
        const data = await response.json();
        if (data.success) {
            showToast(t('ui.system.snmp.configured'), 'success');
            loadSnmpConfig();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message || t('ui.system.snmp.save_failed') }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

async function testSnmpConfig() {
    const enabled = document.getElementById('snmp_enabled')?.checked === true;
    const host = document.getElementById('snmp_host')?.value?.trim() || '';
    const port = parseInt(document.getElementById('snmp_port')?.value || '162', 10);

    try {
        showToast(t('ui.system.snmp.testing'), 'info');
        const response = await fetch('/api/system/snmp/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, host, port })
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message || t('ui.system.snmp.ok'), 'success');
        } else {
            showToast(t('ui.errors.with_message', { message: data.message || t('ui.system.snmp.test_failed') }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
        updateBackupStatus(t('ui.backup.file_field_missing'), 'error');
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
        updateBackupStatus(t('ui.backup.invalid_action'), 'error');
    }
}

async function backupConfiguration() {
    const includeLogs = confirm(t('ui.backup.include_logs_confirm'));
    updateBackupStatus(t('ui.backup.preparing'), 'checking');

    try {
        const response = await fetch('/api/system/backup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ include_logs: includeLogs })
        });

        const contentType = response.headers.get('content-type') || '';
        if (!response.ok || contentType.includes('application/json')) {
            const data = await response.json();
            const message = data.message || t('ui.backup.error');
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

        updateBackupStatus(t('ui.backup.downloaded'), 'success');
        showToast(t('ui.backup.generated'), 'success');
    } catch (error) {
        updateBackupStatus(t('ui.errors.with_message', { message: error.message }), 'error');
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

async function checkBackupFile(file) {
    updateBackupStatus(t('ui.backup.checking'), 'checking');

    try {
        const formData = new FormData();
        formData.append('backup', file);

        const response = await fetch('/api/system/backup/check', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || t('ui.backup.invalid');
            updateBackupStatus(message, 'error');
            showToast(message, 'error');
            return;
        }

        const info = t('ui.backup.valid_info', {
            version: data.version || t('ui.value.na'),
            count: data.files_count || 0
        });
        updateBackupStatus(info, 'success');
        showToast(info, 'success');

        if (confirm(t('ui.backup.confirm_restore_after_check', { info: info }))) {
            restoreBackupFile(file, true);
        }
    } catch (error) {
        updateBackupStatus(t('ui.errors.with_message', { message: error.message }), 'error');
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

async function restoreBackupFile(file, skipConfirm = false) {
    if (!skipConfirm) {
        const proceed = confirm(t('ui.backup.confirm_restore'));
        if (!proceed) return;
    }

    updateBackupStatus(t('ui.backup.restoring'), 'updating');

    try {
        const formData = new FormData();
        formData.append('backup', file);

        const response = await fetch('/api/system/backup/restore', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || t('ui.backup.restore_failed');
            updateBackupStatus(message, 'error');
            showToast(message, 'error');
            return;
        }

        updateBackupStatus(t('ui.backup.restore_success_status'), 'success');
        showToast(t('ui.backup.restore_success_toast'), 'success');

        showRebootOverlay();
        startRebootMonitoring();
    } catch (error) {
        updateBackupStatus(t('ui.errors.with_message', { message: error.message }), 'error');
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
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
                if (nameInput) nameInput.value = data.config.name || t('ui.onvif.name_default_unprovisioned');
                if (usernameInput) usernameInput.value = data.config.username || '';
                if (passwordInput) {
                    passwordInput.value = '';
                    passwordInput.placeholder = data.config.has_password
                        ? t('ui.onvif.password_placeholder_saved')
                        : t('ui.onvif.password_placeholder_none');
                }
                if (rtspPortInput) rtspPortInput.value = data.config.rtsp_port || 8554;
                if (rtspPathInput) rtspPathInput.value = data.config.rtsp_path || '/stream';
                
                // Show/hide Meeting API badge based on source
                if (nameSourceBadge) {
                    if (data.config.name_from_meeting) {
                        nameSourceBadge.style.display = 'inline';
                        if (nameHint) nameHint.textContent = t('ui.onvif.name_hint_from_meeting');
                    } else {
                        nameSourceBadge.style.display = 'none';
                        if (nameHint) nameHint.textContent = t('ui.onvif.name_hint_default');
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
    if (fpsEl) fpsEl.textContent = `${settings.fps} ${t('ui.units.fps_suffix')}`;
    if (bitrateEl) {
        const bitrate = settings.bitrate ? `${settings.bitrate} ${t('ui.units.kbps_suffix')}` : t('ui.value.auto');
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
                <span>${t('ui.onvif.status.active')}</span>
            </div>
            <div class="onvif-details">
                <span><strong>${t('ui.onvif.port_label')}</strong> ${data.config?.port || 8080}</span>
                <span><strong>${t('ui.onvif.name_label')}</strong> ${data.config?.name || 'RPI-CAM'}</span>
                <span><strong>${t('ui.onvif.url_label')}</strong> http://${onvifHost}:${data.config?.port || 8080}/onvif/device_service</span>
            </div>
        `;
    } else if (data.enabled) {
        html = `
            <div class="status-indicator not-synced">
                <i class="fas fa-exclamation-triangle"></i>
                <span>${t('ui.onvif.status.stopped')}</span>
            </div>
        `;
    } else {
        html = `
            <div class="status-indicator">
                <i class="fas fa-power-off"></i>
                <span>${t('ui.onvif.status.disabled')}</span>
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
        
        showToast(t('ui.onvif.saving'), 'info');
        
        const response = await fetch('/api/onvif/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.onvif.saved'), 'success');
            loadOnvifStatus();
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    }
}

/**
 * Restart ONVIF service
 */
async function restartOnvifService() {
    try {
        showToast(t('ui.onvif.restarting'), 'info');
        
        const response = await fetch('/api/onvif/restart', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(t('ui.onvif.restarted'), 'success');
            setTimeout(loadOnvifStatus, 2000);
        } else {
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
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
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.debug.firmware.checking')}`;
    statusText.textContent = t('ui.debug.firmware.checking_status');
    statusText.className = 'status-value checking';
    
    try {
        const response = await fetch('/api/debug/firmware/check');
        const data = await response.json();
        
        outputContainer.style.display = 'block';
        output.textContent = data.output || data.message;
        
        // Show method badge
        if (data.method) {
            methodDiv.style.display = 'block';
            methodBadge.textContent = t('ui.debug.firmware.method_display', { model: data.model, method: data.method });
            // Store method for update confirmation
            updateBtn.dataset.method = data.method;
        }
        
        if (data.success) {
            // Check if firmware update is disabled (initramfs system)
            if (data.can_update === false || data.use_apt === true) {
                statusText.textContent = t('ui.debug.firmware.use_apt');
                statusText.className = 'status-value use-apt';
                details.innerHTML = `<small>${t('ui.debug.firmware.kernel_version', { version: data.current_version })}<br>${t('ui.debug.firmware.initramfs_detected')}</small>`;
                updateBtn.disabled = true;
                updateBtn.title = t('ui.debug.firmware.use_apt_title');
            } else if (data.update_available) {
                statusText.textContent = t('ui.debug.firmware.update_available');
                statusText.className = 'status-value update-available';
                details.innerHTML = `<small>${t('ui.debug.firmware.current_version', { version: data.current_version })}</small>`;
                updateBtn.disabled = false;
            } else {
                statusText.textContent = t('ui.debug.firmware.up_to_date');
                statusText.className = 'status-value up-to-date';
                details.innerHTML = `<small>${t('ui.debug.firmware.version_label', { version: data.current_version })}</small>`;
                updateBtn.disabled = true;
            }
            // Update last check date
            document.getElementById('firmware-last-date').textContent = t('ui.status.just_now');
        } else {
            statusText.textContent = t('ui.errors.generic');
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            updateBtn.disabled = true;
        }
    } catch (error) {
        statusText.textContent = t('ui.errors.generic');
        statusText.className = 'status-value error';
        details.innerHTML = `<small>${error.message}</small>`;
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-search"></i> ${t('ui.actions.check')}`;
    }
}

/**
 * Run firmware update
 */
async function runFirmwareUpdate() {
    const updateBtn = document.getElementById('btn-update-firmware');
    const method = updateBtn.dataset.method || 'unknown';
    
    // Different warning for rpi-update (experimental firmware)
    let confirmMessage = t('ui.debug.firmware.confirm_update');
    if (method === 'rpi-update') {
        confirmMessage = t('ui.debug.firmware.confirm_experimental');
    }
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    const btn = document.getElementById('btn-update-firmware');
    const statusText = document.getElementById('firmware-status-text');
    const output = document.getElementById('firmware-output');
    
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.debug.firmware.updating_button')}`;
    statusText.textContent = t('ui.debug.firmware.updating_status');
    statusText.className = 'status-value updating';
    output.textContent = t('ui.debug.firmware.downloading');
    
    try {
        const response = await fetch('/api/debug/firmware/update', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        // Show warning if present
        if (data.warning) {
            output.textContent += `\n\n${t('ui.notifications.warning_prefix')} ${data.warning}`;
        }
        
        if (data.success) {
            statusText.textContent = t('ui.debug.firmware.reboot_required');
            statusText.className = 'status-value reboot-required';
            showToast(t('ui.debug.firmware.updated_restart'), 'success');
            
            if (data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 1000);
            }
        } else {
            statusText.textContent = t('ui.errors.generic');
            statusText.className = 'status-value error';
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        statusText.textContent = t('ui.errors.generic');
        statusText.className = 'status-value error';
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-download"></i> ${t('ui.actions.update')}`;
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
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.debug.apt_update.running_button')}`;
    statusText.textContent = t('ui.status.running');
    statusText.className = 'status-value running';
    outputContainer.style.display = 'block';
    output.textContent = t('ui.debug.apt_update.running_output');
    
    try {
        const response = await fetch('/api/debug/apt/update', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        if (data.success) {
            statusText.textContent = t('ui.status.completed');
            statusText.className = 'status-value success';
            details.innerHTML = `<small>${t('ui.debug.apt_update.details_summary', { hit_count: data.hit_count, get_count: data.get_count })}</small>`;
            document.getElementById('apt-update-last-date').textContent = t('ui.status.just_now');
            showToast(data.message, 'success');
        } else {
            statusText.textContent = t('ui.errors.generic');
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        statusText.textContent = t('ui.errors.generic');
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-sync"></i> ${t('ui.debug.run_apt_update')}`;
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
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.debug.apt_upgrade.checking_button')}`;
    statusText.textContent = t('ui.debug.apt_upgrade.checking_status');
    statusText.className = 'status-value checking';
    
    try {
        const response = await fetch('/api/debug/apt/upgradable');
        const data = await response.json();
        
        outputContainer.style.display = 'block';
        
        if (data.success) {
            if (data.count > 0) {
                statusText.textContent = t('ui.debug.apt_upgrade.available_count', { count: data.count });
                statusText.className = 'status-value update-available';
                details.innerHTML = `<small>${t('ui.debug.apt_upgrade.available_details', { count: data.count })}</small>`;
                
                // Format output nicely
                let formattedOutput = `${t('ui.debug.apt_upgrade.available_header', { count: data.count })}\n\n`;
                data.packages.forEach(pkg => {
                    formattedOutput += `${t('ui.debug.apt_upgrade.package_line', { name: pkg.name, version: pkg.version })}\n`;
                });
                output.textContent = formattedOutput;
            } else {
                statusText.textContent = t('ui.debug.apt_upgrade.up_to_date');
                statusText.className = 'status-value up-to-date';
                details.innerHTML = `<small>${t('ui.debug.apt_upgrade.all_up_to_date')}</small>`;
                output.textContent = t('ui.debug.apt_upgrade.none_available');
            }
        } else {
            statusText.textContent = t('ui.errors.generic');
            statusText.className = 'status-value error';
            output.textContent = data.message;
        }
    } catch (error) {
        statusText.textContent = t('ui.errors.generic');
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-list"></i> ${t('ui.debug.view_packages')}`;
    }
}

/**
 * Run apt upgrade
 */
async function runAptUpgrade() {
    if (!confirm(t('ui.debug.apt_upgrade.confirm'))) {
        return;
    }
    
    const btn = document.getElementById('btn-apt-upgrade');
    const statusText = document.getElementById('apt-upgrade-status-text');
    const details = document.getElementById('apt-upgrade-details');
    const outputContainer = document.getElementById('apt-upgrade-output-container');
    const output = document.getElementById('apt-upgrade-output');
    
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.debug.apt_upgrade.updating_button')}`;
    statusText.textContent = t('ui.status.running');
    statusText.className = 'status-value running';
    outputContainer.style.display = 'block';
    output.textContent = t('ui.debug.apt_upgrade.running_output');
    
    try {
        const response = await fetch('/api/debug/apt/upgrade', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        if (data.success) {
            statusText.textContent = t('ui.status.completed');
            statusText.className = 'status-value success';
            details.innerHTML = `<small>${t('ui.debug.apt_upgrade.summary', { upgraded: data.upgraded, newly_installed: data.newly_installed })}</small>`;
            document.getElementById('apt-upgrade-last-date').textContent = t('ui.status.just_now');
            showToast(data.message, 'success');
        } else {
            statusText.textContent = t('ui.errors.generic');
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        statusText.textContent = t('ui.errors.generic');
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-arrow-up"></i> ${t('ui.actions.update')}`;
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
            statusText.textContent = enabled ? t('ui.system.rtc.active') : t('ui.system.rtc.inactive');
            statusText.className = `status-value ${enabled ? 'synced' : 'not-synced'}`;

            const detected = data.status.detected ? t('ui.value.yes') : t('ui.value.no');
            const mode = data.status.mode || 'auto';
            details.innerHTML = `<small>${t('ui.system.rtc.mode_label')} ${mode} - ${t('ui.system.rtc.detected_label')} ${detected} - ${t('ui.system.rtc.overlay_label')} ${data.status.overlay_configured ? t('ui.system.rtc.overlay_configured') : t('ui.system.rtc.overlay_not_configured')}</small>`;
        } else {
            statusText.textContent = t('ui.errors.generic');
            statusText.className = 'status-value warning';
            details.innerHTML = `<small>${data.message || t('ui.system.rtc.error')}</small>`;
        }
    } catch (error) {
        if (statusText) {
            statusText.textContent = t('ui.errors.generic');
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
    if (!dateStr) return t('ui.status.never');
    
    try {
        const date = new Date(dateStr.replace(' ', 'T'));
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return t('ui.status.just_now');
        if (diffMins < 60) return t('ui.time.ago_minutes', { minutes: diffMins });
        if (diffHours < 24) return t('ui.time.ago_hours', { hours: diffHours });
        if (diffDays < 7) return t('ui.time.ago_days', { days: diffDays });
        
        // Format as date
        const locale = document.documentElement.lang || 'fr-FR';
        return date.toLocaleDateString(locale, {
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
            statusText.textContent = scheduler.enabled ? t('ui.value.enabled') : t('ui.value.disabled');
            
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
    statusText.textContent = enabled ? t('ui.status.configuring') : t('ui.value.disabled');
    
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
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.debug.scheduler.saving')}`;
    }
    
    try {
        const response = await fetch('/api/debug/apt/scheduler', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await response.json();
        
        if (data.success) {
            statusText.textContent = config.enabled ? t('ui.value.enabled') : t('ui.value.disabled');
            showToast(data.message || t('ui.debug.scheduler.saved'), 'success');
        } else {
            showToast(data.message || t('ui.errors.generic'), 'error');
        }
    } catch (error) {
        showToast(t('ui.errors.with_message', { message: error.message }), 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-save"></i> ${t('ui.actions.save')}`;
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
            appendTerminalLine(t('ui.debug.terminal.command_not_allowed', { command: command.split(' ')[0] }), 'terminal-error');
            appendTerminalLine(t('ui.debug.terminal.help_hint'), 'terminal-info');
        } else if (data.success) {
            if (data.stdout) {
                appendTerminalLine(data.stdout, 'terminal-stdout');
            }
            if (data.stderr) {
                appendTerminalLine(data.stderr, 'terminal-stderr');
            }
            if (data.returncode !== 0 && !data.stdout && !data.stderr) {
                appendTerminalLine(t('ui.debug.terminal.command_exit_code', { code: data.returncode }), 'terminal-info');
            }
        } else {
            appendTerminalLine(t('ui.errors.with_message', { message: data.error }), 'terminal-error');
        }
    } catch (error) {
        appendTerminalLine(t('ui.debug.terminal.network_error', { message: error.message }), 'terminal-error');
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
    appendTerminalLine(t('ui.debug.terminal.cleared'), 'terminal-info');
}

/**
 * Show allowed commands
 */
async function showAllowedCommands() {
    appendTerminalLine(t('ui.debug.terminal.loading_allowed'), 'terminal-info');
    
    try {
        const response = await fetch('/api/debug/terminal/allowed');
        const data = await response.json();
        
        if (data.success) {
            appendTerminalLine(t('ui.debug.terminal.allowed_header'), 'terminal-success');
            
            // Group commands by category
            const categories = {
                [t('ui.debug.terminal.category.system')]: ['ls', 'cat', 'head', 'tail', 'grep', 'find', 'df', 'du', 'free', 'top', 'ps', 'uptime', 'date', 'hostname', 'uname', 'whoami', 'id', 'pwd'],
                [t('ui.debug.terminal.category.logs')]: ['journalctl', 'dmesg'],
                [t('ui.debug.terminal.category.services')]: ['systemctl', 'service'],
                [t('ui.debug.terminal.category.network')]: ['ip', 'ifconfig', 'iwconfig', 'nmcli', 'netstat', 'ss', 'ping', 'traceroute', 'curl', 'wget'],
                [t('ui.debug.terminal.category.hardware')]: ['vcgencmd', 'pinctrl', 'lsusb', 'lspci', 'lsblk', 'lscpu', 'lshw', 'lsmod', 'v4l2-ctl'],
                [t('ui.debug.terminal.category.media')]: ['ffprobe', 'ffmpeg', 'gst-launch-1.0', 'gst-inspect-1.0', 'test-launch'],
                [t('ui.debug.terminal.category.packages')]: ['apt', 'apt-get', 'apt-cache', 'dpkg'],
                [t('ui.debug.terminal.category.utilities')]: ['echo', 'which', 'whereis', 'file', 'stat', 'wc', 'sort', 'uniq', 'awk', 'sed', 'cut', 'tr', 'tee']
            };
            
            for (const [category, cmds] of Object.entries(categories)) {
                const available = cmds.filter(c => data.commands.includes(c));
                if (available.length > 0) {
                    appendTerminalLine(`\n${category}: ${available.join(', ')}`, 'terminal-stdout');
                }
            }
            
            appendTerminalLine(`\n${t('ui.debug.terminal.note_sudo')}`, 'terminal-info');
        } else {
            appendTerminalLine(t('ui.debug.terminal.load_error'), 'terminal-error');
        }
    } catch (error) {
        appendTerminalLine(t('ui.errors.with_message', { message: error.message }), 'terminal-error');
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
    window.updateBackupStatus = updateBackupStatus;
    window.openBackupFilePicker = openBackupFilePicker;
    window.handleBackupFileSelected = handleBackupFileSelected;
    window.backupConfiguration = backupConfiguration;
    window.checkBackupFile = checkBackupFile;
    window.restoreBackupFile = restoreBackupFile;
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











/**
 * RTSP Recorder Web Manager - Meeting/NTP/RTC functions
 * Version: 2.36.10
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
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.test_in_progress', {}, 'Testing connection...')}`;
    
    try {
        const response = await fetch('/api/meeting/test', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message}`;
            if (data.data) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.data, null, 2)}</pre>`;
            }
            showToast(I18n.t('meeting.test_success_toast', {}, 'Meeting connection successful'), 'success');
            updateMeetingStatus(true);
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            if (data.details) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.details, null, 2)}</pre>`;
            }
            showToast(I18n.t('meeting.test_fail_toast', {}, 'Meeting connection failed'), 'error');
            updateMeetingStatus(false);
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        showToast(I18n.t('meeting.test_error_toast', {}, 'Meeting test error'), 'error');
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
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.heartbeat_in_progress', {}, 'Sending heartbeat...')}`;
    
    try {
        // Use debug endpoint to get both payload and response
        const response = await fetch('/api/meeting/heartbeat/debug', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            resultDiv.className = 'meeting-result success';
            let html = `<i class="fas fa-heartbeat"></i> ${I18n.t('meeting.heartbeat_success', {}, 'Heartbeat sent successfully')}`;
            
            // Show endpoint
            if (data.api_url && data.endpoint) {
                html += `<br><small>➡️ ${data.api_url}${data.endpoint}</small>`;
            }
            
            // Show payload sent
            if (data.payload_sent) {
                html += `<details style="margin-top: 10px;"><summary><strong>📤 ${I18n.t('meeting.payload_sent', {}, 'Payload sent')}</strong></summary>`;
                html += `<pre style="background:#1a1a2e; padding:10px; border-radius:5px; overflow-x:auto; font-size:11px;">${JSON.stringify(data.payload_sent, null, 2)}</pre></details>`;
            }
            
            // Show response received
            if (data.response) {
                html += `<details style="margin-top: 5px;"><summary><strong>📥 ${I18n.t('meeting.response_meeting', {}, 'Meeting response')}</strong></summary>`;
                html += `<pre style="background:#1a1a2e; padding:10px; border-radius:5px; overflow-x:auto; font-size:11px;">${JSON.stringify(data.response, null, 2)}</pre></details>`;
            }
            
            resultDiv.innerHTML = html;
            showToast(I18n.t('meeting.heartbeat_success_toast', {}, 'Heartbeat sent'), 'success');
            updateMeetingStatus(true);
        } else {
            resultDiv.className = 'meeting-result error';
            let html = `<i class="fas fa-times-circle"></i> ${data.response?.error || data.response?.message || I18n.t('meeting.generic_failure', {}, 'Failed')}`;
            
            // Still show what was attempted
            if (data.payload_sent) {
                html += `<details style="margin-top: 10px;"><summary><strong>📤 ${I18n.t('meeting.payload_attempted', {}, 'Payload attempted')}</strong></summary>`;
                html += `<pre style="background:#1a1a2e; padding:10px; border-radius:5px; overflow-x:auto; font-size:11px;">${JSON.stringify(data.payload_sent, null, 2)}</pre></details>`;
            }
            
            resultDiv.innerHTML = html;
            showToast(I18n.t('meeting.heartbeat_fail_toast', {}, 'Heartbeat failed'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        showToast(I18n.t('meeting.heartbeat_error_toast', {}, 'Heartbeat error'), 'error');
    }
}

/**
 * Get device availability from Meeting API
 */
async function getMeetingAvailability() {
    const resultDiv = document.getElementById('meeting-test-result');
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.availability_checking', {}, 'Checking availability...')}`;
    
    try {
        const response = await fetch('/api/meeting/availability');
        const data = await response.json();
        
        if (data.success) {
            const avail = data.data || data;
            // API Meeting returns status: "Available" or "Unavailable"
            const isOnline = avail.online === true || avail.status === 'Available' || avail.status === 'available';
            resultDiv.className = 'meeting-result success';
            resultDiv.innerHTML = `
                <i class="fas fa-info-circle"></i> ${I18n.t('meeting.availability_title', {}, 'Availability status')}
                <div class="availability-info">
                    <p><strong>${I18n.t('meeting.availability_online', {}, 'Online')}:</strong> ${isOnline ? I18n.t('meeting.online_yes', {}, 'Yes ✓') : I18n.t('meeting.online_no', {}, 'No ✗')}</p>
                    <p><strong>${I18n.t('meeting.availability_status', {}, 'Status')}:</strong> ${avail.status || I18n.t('common.na', {}, 'N/A')}</p>
                    ${avail.last_heartbeat ? `<p><strong>${I18n.t('meeting.availability_last_heartbeat', {}, 'Last heartbeat')}:</strong> ${avail.last_heartbeat}</p>` : ''}
                    ${avail.last_seen ? `<p><strong>${I18n.t('meeting.availability_last_seen', {}, 'Last seen')}:</strong> ${new Date(avail.last_seen).toLocaleString()}</p>` : ''}
                    ${avail.uptime ? `<p><strong>${I18n.t('meeting.availability_uptime', {}, 'Uptime')}:</strong> ${avail.uptime} ${I18n.t('meeting.availability_minutes', {}, 'minutes')}</p>` : ''}
                    ${avail.ip ? `<p><strong>${I18n.t('meeting.availability_ip', {}, 'IP')}:</strong> ${avail.ip}</p>` : ''}
                </div>
            `;
            showToast(I18n.t('meeting.availability_success_toast', {}, 'Availability retrieved'), 'success');
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || data.message || I18n.t('meeting.generic_failure', {}, 'Failed')}`;
            showToast(I18n.t('meeting.availability_fail_toast', {}, 'Availability check failed'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        showToast(I18n.t('meeting.availability_error_toast', {}, 'Availability error'), 'error');
    }
}

/**
 * Fetch device info from Meeting API
 */
async function fetchMeetingDeviceInfo() {
    const infoDiv = document.getElementById('meeting-device-info');
    infoDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.device_info_loading', {}, 'Loading information...')}`;
    
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
            const deviceName = device.product_serial || device.name || device.device_name || I18n.t('meeting.device_name_undefined', {}, 'Not set');
            // IP from device info
            const deviceIp = device.ip_address || device.ip || I18n.t('common.na', {}, 'N/A');
            // Online status from availability API
            const isOnline = avail.status === 'Available' || avail.status === 'available' || avail.online === true;
            // Last seen from availability
            const lastSeen = avail.last_heartbeat || avail.last_seen || device.last_seen;
            
            // Format last_seen date
            let lastSeenStr = I18n.t('common.na', {}, 'N/A');
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
                        <label><i class="fas fa-cogs"></i> ${I18n.t('meeting.services_declared', {}, 'Declared services')}</label>
                        <div class="services-badges">${serviceBadges}</div>
                    </div>
                `;
            } else {
                servicesHtml = `
                    <div class="services-section">
                        <label><i class="fas fa-cogs"></i> ${I18n.t('meeting.services_declared', {}, 'Declared services')}</label>
                        <div class="services-badges"><span class="service-badge service-none">${I18n.t('meeting.no_service', {}, 'No service')}</span></div>
                    </div>
                `;
            }
            
            // WiFi AP section (if available)
            let wifiApHtml = '';
            if (device.ap_ssid || device.ap_password) {
                wifiApHtml = `
                    <div class="wifi-ap-section">
                        <label><i class="fas fa-wifi"></i> ${I18n.t('meeting.wifi_ap_label', {}, 'WiFi access point')}</label>
                        <div class="wifi-ap-info">
                            <div class="wifi-ap-item">
                                <span class="wifi-label">${I18n.t('meeting.wifi_ssid_label', {}, 'SSID')}</span>
                                <span class="wifi-value mono">${device.ap_ssid || I18n.t('meeting.device_name_undefined', {}, 'N/A')}</span>
                            </div>
                            <div class="wifi-ap-item">
                                <span class="wifi-label">${I18n.t('meeting.wifi_password_label', {}, 'Password')}</span>
                                <span class="wifi-value mono">${device.ap_password || I18n.t('meeting.device_name_undefined', {}, 'N/A')}</span>
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
                        <label><i class="fas fa-sticky-note"></i> ${I18n.t('meeting.note_label', {}, 'Note')}</label>
                        <p class="note-content">${device.note}</p>
                    </div>
                `;
            }
            
            infoDiv.innerHTML = `
                <div class="device-info-grid">
                    <div class="info-item">
                        <label><i class="fas fa-key"></i> ${I18n.t('meeting.device_key_label', {}, 'Device Key')}</label>
                        <span class="mono">${device.device_key || I18n.t('meeting.device_name_undefined', {}, 'N/A')}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-tag"></i> ${I18n.t('meeting.device_name_label', {}, 'Name')}</label>
                        <span>${deviceName}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-circle ${isOnline ? 'text-success' : 'text-danger'}"></i> ${I18n.t('meeting.availability_status', {}, 'Status')}</label>
                        <span>${isOnline ? I18n.t('meeting.availability_online', {}, 'Online') : I18n.t('meeting.availability_offline', {}, 'Offline')}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-network-wired"></i> IP</label>
                        <span class="mono">${deviceIp}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-clock"></i> ${I18n.t('meeting.last_activity_label', {}, 'Last activity')}</label>
                        <span>${lastSeenStr}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-coins"></i> ${I18n.t('meeting.tokens_label', {}, 'Tokens')}</label>
                        <span>${device.token_count !== undefined ? device.token_count : I18n.t('meeting.device_name_undefined', {}, 'N/A')}</span>
                    </div>
                    <div class="info-item">
                        <label><i class="fas fa-check-circle ${device.authorized ? 'text-success' : 'text-danger'}"></i> ${I18n.t('meeting.authorized_label', {}, 'Authorized')}</label>
                        <span>${device.authorized ? I18n.t('common.yes', {}, 'Yes') : I18n.t('common.no', {}, 'No')}</span>
                    </div>
                </div>
                ${noteHtml}
                ${wifiApHtml}
                ${servicesHtml}
            `;
            showToast(I18n.t('meeting.device_info_loaded', {}, 'Device info loaded'), 'success');
        } else {
            infoDiv.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-circle"></i> ${data.error || data.message || I18n.t('meeting.device_info_load_failed', {}, 'Unable to load information')}</p>`;
            showToast(I18n.t('meeting.device_info_load_failed_toast', {}, 'Failed to load device info'), 'error');
        }
    } catch (error) {
        infoDiv.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}</p>`;
        showToast(I18n.t('meeting.device_info_load_error_toast', {}, 'Device info load error'), 'error');
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
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.tunnel_requesting', { service }, `Requesting ${service} tunnel...`)}`;
    
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
                    html += `<p><strong>${I18n.t('meeting.tunnel_url_label', {}, 'Tunnel URL')}:</strong> <code>${data.data.tunnel_url}</code></p>`;
                }
                if (data.data.port) {
                    html += `<p><strong>${I18n.t('meeting.tunnel_port_label', {}, 'Remote port')}:</strong> <code>${data.data.port}</code></p>`;
                }
                if (data.data.expires_at) {
                    html += `<p><strong>${I18n.t('meeting.tunnel_expires_label', {}, 'Expires')}:</strong> ${new Date(data.data.expires_at).toLocaleString()}</p>`;
                }
            }
            resultDiv.innerHTML = html;
            showToast(I18n.t('meeting.tunnel_created', { service }, `Tunnel ${service} created`), 'success');
        } else {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.message}`;
            if (data.details) {
                resultDiv.innerHTML += `<pre>${JSON.stringify(data.details, null, 2)}</pre>`;
            }
            showToast(I18n.t('meeting.tunnel_create_failed', {}, 'Failed to create tunnel'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        showToast(I18n.t('meeting.tunnel_error', {}, 'Tunnel error'), 'error');
    }
}

// ============================================================================
// Services Declaration Management
// ============================================================================

/**
 * Load and display declared services (authorized by Meeting API)
 */
async function loadMeetingServices() {
    const container = document.getElementById('meeting-services-grid');
    if (!container) return;
    
    const allServices = ['ssh', 'http', 'vnc', 'scp', 'debug'];
    
    try {
        // Fetch services authorized by Meeting API
        const response = await fetch('/api/meeting/services?source=meeting');
        const data = await response.json();
        
        // services is a dict {serviceName: bool}, convert to array of enabled services
        const servicesDict = data.success ? (data.services || {}) : {};
        const enabledServices = Object.keys(servicesDict).filter(k => servicesDict[k]);
        
        container.innerHTML = allServices.map(service => {
            const isEnabled = enabledServices.includes(service);
            const icons = {
                'ssh': 'fa-terminal',
                'http': 'fa-globe',
                'vnc': 'fa-desktop',
                'scp': 'fa-file-upload',
                'debug': 'fa-bug'
            };
            return `
                <div class="service-item ${isEnabled ? 'active' : ''}">
                    <span class="service-icon"><i class="fas ${icons[service] || 'fa-plug'}"></i></span>
                    <span class="service-name">${service}</span>
                    <span class="service-status ${isEnabled ? 'enabled' : 'disabled'}">
                        ${isEnabled ? I18n.t('common.active', {}, 'Active') : I18n.t('common.inactive', {}, 'Inactive')}
                    </span>
                </div>
            `;
        }).join('');
        
    } catch (error) {
        container.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}</p>`;
    }
}

// ============================================================================
// SSH Key Management
// ============================================================================

/**
 * Load SSH keys status indicators
 * Shows whether device key exists and Meeting pubkey is installed
 */
async function loadSshKeysStatus() {
    const deviceKeyStatus = document.getElementById('device-key-status');
    const meetingKeyStatus = document.getElementById('meeting-key-status');
    
    if (!deviceKeyStatus || !meetingKeyStatus) return;
    
    try {
        const response = await fetch('/api/meeting/ssh/keys/status');
        const data = await response.json();
        
        if (data.success) {
            // Device key status
            if (data.device_key_exists) {
                deviceKeyStatus.innerHTML = `<i class="fas fa-check-circle text-success"></i> ${I18n.t('meeting.device_key_label', {}, 'Device Key')}: <span class="text-success">${I18n.t('meeting.key_present', {}, 'Present')}</span>`;
            } else {
                deviceKeyStatus.innerHTML = `<i class="fas fa-times-circle text-danger"></i> ${I18n.t('meeting.device_key_label', {}, 'Device Key')}: <span class="text-danger">${I18n.t('meeting.key_absent', {}, 'Missing')}</span>`;
            }
            
            // Meeting key status
            if (data.meeting_key_installed) {
                meetingKeyStatus.innerHTML = `<i class="fas fa-check-circle text-success"></i> ${I18n.t('meeting.meeting_key_label', {}, 'Meeting Key')}: <span class="text-success">${I18n.t('meeting.key_installed', {}, 'Installed')}</span>`;
            } else {
                meetingKeyStatus.innerHTML = `<i class="fas fa-times-circle text-danger"></i> ${I18n.t('meeting.meeting_key_label', {}, 'Meeting Key')}: <span class="text-danger">${I18n.t('meeting.key_not_installed', {}, 'Not installed')}</span>`;
            }
        } else {
            deviceKeyStatus.innerHTML = `<i class="fas fa-exclamation-triangle text-warning"></i> ${I18n.t('meeting.device_key_label', {}, 'Device Key')}: <span class="text-warning">${I18n.t('meeting.key_error', {}, 'Error')}</span>`;
            meetingKeyStatus.innerHTML = `<i class="fas fa-exclamation-triangle text-warning"></i> ${I18n.t('meeting.meeting_key_label', {}, 'Meeting Key')}: <span class="text-warning">${I18n.t('meeting.key_error', {}, 'Error')}</span>`;
        }
    } catch (error) {
        deviceKeyStatus.innerHTML = `<i class="fas fa-exclamation-triangle text-danger"></i> ${I18n.t('meeting.key_check_error', {}, 'Verification error')}`;
        meetingKeyStatus.innerHTML = `<i class="fas fa-exclamation-triangle text-danger"></i> ${I18n.t('meeting.key_check_error', {}, 'Verification error')}`;
    }
}

/**
 * Ensure SSH keys are properly configured for Meeting integration
 * Auto-generates device key if missing and installs Meeting pubkey
 */
async function ensureSshKeysConfigured() {
    const resultDiv = document.getElementById('ssh-key-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result loading';
        resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.ssh_auto_configuring', {}, 'Auto-configuring SSH keys...')}`;
    }
    
    try {
        const response = await fetch('/api/meeting/ssh/keys/ensure', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                let html = `<i class="fas fa-check-circle"></i> ${data.message || I18n.t('meeting.ssh_keys_configured', {}, 'SSH keys configured')}<br><ul>`;
                if (data.details) {
                    for (const detail of data.details) {
                        html += `<li>✓ ${detail}</li>`;
                    }
                }
                html += '</ul>';
                resultDiv.innerHTML = html;
            }
            showToast(I18n.t('meeting.ssh_keys_configured', {}, 'SSH keys configured'), 'success');
            // Refresh status indicators
            loadSshKeysStatus();
            loadDeviceSshKey();
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.ssh_config_failed', {}, 'Configuration failed')}`;
            }
            showToast(I18n.t('meeting.ssh_config_failed_toast', {}, 'SSH keys configuration failed'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
        showToast(I18n.t('meeting.ssh_config_error', {}, 'SSH keys configuration error'), 'error');
    }
}

/**
 * Load device SSH key information
 */
async function loadDeviceSshKey() {
    const infoDiv = document.getElementById('ssh-key-info');
    if (!infoDiv) return;
    
    infoDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.loading', {}, 'Loading...')}`;
    
    try {
        const response = await fetch('/api/meeting/ssh/key');
        const data = await response.json();
        
        if (data.success && data.pubkey) {
            // pubkey format: "ssh-ed25519 AAAA... comment"
            const pubkeyParts = data.pubkey.split(' ');
            const keyType = pubkeyParts[0] || 'ed25519';
            const pubkeyShort = data.pubkey.length > 80 ? data.pubkey.substring(0, 77) + '...' : data.pubkey;
            infoDiv.innerHTML = `
                <label>${I18n.t('meeting.ssh_key_type_label', {}, 'Type')}:</label>
                <span>${keyType}</span>
                <label>${I18n.t('meeting.ssh_public_key_label', {}, 'Public key')}:</label>
                <span class="mono-truncate" title="${data.pubkey}">${pubkeyShort}</span>
                <label>${I18n.t('meeting.status_label', {}, 'Status')}:</label>
                <span class="text-success"><i class="fas fa-check-circle"></i> ${I18n.t('meeting.key_generated', {}, 'Generated')}</span>
            `;
        } else {
            infoDiv.innerHTML = `
                <label>${I18n.t('meeting.status_label', {}, 'Status')}:</label>
                <span class="text-warning"><i class="fas fa-exclamation-circle"></i> ${I18n.t('meeting.key_not_generated', {}, 'SSH key not generated')}</span>
            `;
        }
    } catch (error) {
        infoDiv.innerHTML = `<p class="text-error"><i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}</p>`;
    }
}

/**
 * Generate a new device SSH key
 */
async function generateDeviceSshKey() {
    if (!confirm(I18n.t('meeting.ssh_key_generate_confirm', {}, 'Generate a new SSH key? The old key will be overwritten.'))) {
        return;
    }
    
    const resultDiv = document.getElementById('ssh-key-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result loading';
        resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.ssh_key_generating', {}, 'Generating key...')}`;
    }
    
    try {
        const response = await fetch('/api/meeting/ssh/key/generate', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message || I18n.t('meeting.ssh_key_generated', {}, 'Key generated successfully')}`;
            }
            showToast(I18n.t('meeting.ssh_key_generated_toast', {}, 'SSH key generated'), 'success');
            loadDeviceSshKey();
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.ssh_key_generate_failed', {}, 'Generation failed')}`;
            }
            showToast(I18n.t('meeting.ssh_key_generate_failed_toast', {}, 'SSH key generation failed'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
        showToast(I18n.t('meeting.ssh_key_generate_error', {}, 'Key generation error'), 'error');
    }
}

/**
 * Publish device SSH key to Meeting API
 */
async function publishDeviceSshKey() {
    const resultDiv = document.getElementById('ssh-key-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result loading';
        resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.ssh_key_publishing', {}, 'Publishing key...')}`;
    }
    
    try {
        const response = await fetch('/api/meeting/ssh/key/publish', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message || I18n.t('meeting.ssh_key_published', {}, 'Key published')}`;
            }
            showToast(I18n.t('meeting.ssh_key_published_toast', {}, 'SSH key published to Meeting'), 'success');
            loadDeviceSshKey();
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.ssh_key_publish_failed', {}, 'Publish failed')}`;
            }
            showToast(I18n.t('meeting.ssh_key_publish_failed_toast', {}, 'SSH key publish failed'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
        showToast(I18n.t('meeting.ssh_key_publish_error', {}, 'Key publish error'), 'error');
    }
}

/**
 * Sync SSH hostkey from Meeting API
 */
async function syncSshHostkey() {
    const resultDiv = document.getElementById('ssh-key-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result loading';
        resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.ssh_hostkey_syncing', {}, 'Syncing hostkey...')}`;
    }
    
    try {
        const response = await fetch('/api/meeting/ssh/hostkey/sync', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message || I18n.t('meeting.ssh_hostkey_synced', {}, 'Hostkey synced')}`;
            }
            showToast(I18n.t('meeting.ssh_hostkey_synced_toast', {}, 'Hostkey synced'), 'success');
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.ssh_hostkey_sync_failed', {}, 'Sync failed')}`;
            }
            showToast(I18n.t('meeting.ssh_hostkey_sync_failed_toast', {}, 'Hostkey sync failed'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
        showToast(I18n.t('meeting.ssh_hostkey_sync_error', {}, 'Hostkey sync error'), 'error');
    }
}

/**
 * Full SSH setup (generate + publish + sync)
 */
async function fullSshSetup() {
    if (!confirm(I18n.t('meeting.ssh_full_setup_confirm', {}, 'Start full SSH setup?\n\n• Key generation\n• Publish to Meeting\n• Hostkey sync'))) {
        return;
    }
    
    const resultDiv = document.getElementById('ssh-key-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result loading';
        resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.ssh_full_setup_in_progress', {}, 'SSH setup in progress...')}`;
    }
    
    try {
        const response = await fetch('/api/meeting/ssh/setup', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                let html = `<i class="fas fa-check-circle"></i> ${I18n.t('meeting.ssh_full_setup_done', {}, 'SSH setup complete!')}<br><ul>`;
                if (data.results) {
                    for (const [step, result] of Object.entries(data.results)) {
                        const icon = result.success ? '✓' : '✗';
                        html += `<li>${icon} ${step}: ${result.message || (result.success ? I18n.t('meeting.ok', {}, 'OK') : I18n.t('meeting.failure', {}, 'Failed'))}</li>`;
                    }
                }
                html += '</ul>';
                resultDiv.innerHTML = html;
            }
            showToast(I18n.t('meeting.ssh_full_setup_done_toast', {}, 'SSH setup complete'), 'success');
            loadDeviceSshKey();
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.ssh_config_failed', {}, 'Configuration failed')}`;
            }
            showToast(I18n.t('meeting.ssh_config_failed_toast', {}, 'SSH configuration failed'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
        showToast(I18n.t('meeting.ssh_config_error', {}, 'SSH configuration error'), 'error');
    }
}

// ============================================================================
// Tunnel Agent Management
// ============================================================================

/**
 * Load tunnel agent status
 */
async function loadTunnelAgentStatus() {
    const statusDiv = document.getElementById('tunnel-agent-status');
    const autostartDiv = document.getElementById('tunnel-agent-autostart');
    
    if (!statusDiv) return;
    
    try {
        const response = await fetch('/api/meeting/tunnel/agent/status');
        const data = await response.json();
        
        if (data.success && data.status) {
            const { active, enabled, state } = data.status;
            
            if (active) {
                statusDiv.className = 'status-indicator connected';
                statusDiv.innerHTML = `<i class="fas fa-circle"></i> <span>${I18n.t('common.active', {}, 'Active')}</span>`;
            } else {
                statusDiv.className = 'status-indicator disconnected';
                statusDiv.innerHTML = `<i class="fas fa-circle"></i> <span>${I18n.t('meeting.stopped', {}, 'Stopped')}</span>`;
            }
            
            if (autostartDiv) {
                autostartDiv.innerHTML = enabled 
                    ? `<i class="fas fa-check text-success"></i> ${I18n.t('meeting.autostart_enabled', {}, 'Autostart enabled')}`
                    : `<i class="fas fa-times text-muted"></i> ${I18n.t('meeting.autostart_disabled', {}, 'Autostart disabled')}`;
            }
        } else {
            statusDiv.className = 'status-indicator disconnected';
            statusDiv.innerHTML = `<i class="fas fa-circle"></i> <span>${I18n.t('meeting.not_installed', {}, 'Not installed')}</span>`;
        }
    } catch (error) {
        statusDiv.className = 'status-indicator disconnected';
        statusDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> <span>${I18n.t('meeting.error', {}, 'Error')}</span>`;
    }
}

/**
 * Start tunnel agent
 */
async function startTunnelAgent() {
    const resultDiv = document.getElementById('tunnel-agent-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result loading';
        resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.tunnel_agent_starting', {}, 'Starting tunnel agent...')}`;
    }
    
    try {
        const response = await fetch('/api/meeting/tunnel/agent/start', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message || I18n.t('meeting.tunnel_agent_started', {}, 'Tunnel agent started')}`;
            }
            showToast(I18n.t('meeting.tunnel_agent_started', {}, 'Tunnel agent started'), 'success');
            setTimeout(loadTunnelAgentStatus, 1000);
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.failure', {}, 'Failed')}`;
            }
            showToast(I18n.t('meeting.tunnel_agent_start_failed', {}, 'Failed to start agent'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
        showToast(I18n.t('meeting.tunnel_agent_start_error', {}, 'Agent start error'), 'error');
    }
}

/**
 * Stop tunnel agent
 */
async function stopTunnelAgent() {
    const resultDiv = document.getElementById('tunnel-agent-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'meeting-result loading';
        resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.tunnel_agent_stopping', {}, 'Stopping tunnel agent...')}`;
    }
    
    try {
        const response = await fetch('/api/meeting/tunnel/agent/stop', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message || I18n.t('meeting.tunnel_agent_stopped', {}, 'Tunnel agent stopped')}`;
            }
            showToast(I18n.t('meeting.tunnel_agent_stopped', {}, 'Tunnel agent stopped'), 'success');
            setTimeout(loadTunnelAgentStatus, 1000);
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.failure', {}, 'Failed')}`;
            }
            showToast(I18n.t('meeting.tunnel_agent_stop_failed', {}, 'Failed to stop agent'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
        showToast(I18n.t('meeting.tunnel_agent_stop_error', {}, 'Agent stop error'), 'error');
    }
}

/**
 * Toggle tunnel agent autostart
 */
async function toggleTunnelAgentAutostart() {
    const resultDiv = document.getElementById('tunnel-agent-result');
    
    try {
        // Check current state first
        const statusResponse = await fetch('/api/meeting/tunnel/agent/status');
        const statusData = await statusResponse.json();
        const currentlyEnabled = statusData.success && statusData.status?.enabled;
        
        const endpoint = currentlyEnabled 
            ? '/api/meeting/tunnel/agent/disable'
            : '/api/meeting/tunnel/agent/enable';
        
        if (resultDiv) {
            resultDiv.style.display = 'block';
            resultDiv.className = 'meeting-result loading';
            resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.autostart_updating', {}, 'Updating autostart...')}`;
        }
        
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            if (resultDiv) {
                resultDiv.className = 'meeting-result success';
                resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${data.message}`;
            }
            showToast(data.message, 'success');
            loadTunnelAgentStatus();
        } else {
            if (resultDiv) {
                resultDiv.className = 'meeting-result error';
                    resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> ${data.error || I18n.t('meeting.failure', {}, 'Failed')}`;
            }
                showToast(I18n.t('meeting.autostart_update_failed', {}, 'Autostart update failed'), 'error');
        }
    } catch (error) {
        if (resultDiv) {
            resultDiv.className = 'meeting-result error';
                resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        }
            showToast(I18n.t('meeting.error', {}, 'Error'), 'error');
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
            statusEl.innerHTML = `<i class="fas fa-circle"></i> ${I18n.t('common.connected', {}, 'Connected')}`;
        } else {
            statusEl.className = 'status-indicator disconnected';
            statusEl.innerHTML = `<i class="fas fa-circle"></i> ${I18n.t('common.disconnected', {}, 'Disconnected')}`;
        }
    }
    
    if (detailsEl && connected) {
        detailsEl.innerHTML = `<small>${I18n.t('meeting.last_connection_label', {}, 'Last connection')}: ${new Date().toLocaleTimeString()}</small>`;
    }
}

function updateMeetingConfigStatus() {
    const enabledToggle = document.getElementById('meeting_enabled_toggle');
    const autoToggle = document.getElementById('meeting_auto_connect');
    const enabledStatus = document.getElementById('meeting-enabled-status');
    const autoStatus = document.getElementById('meeting-auto-connect-status');

    if (enabledStatus && enabledToggle) {
        enabledStatus.textContent = enabledToggle.checked ? I18n.t('common.enabled', {}, 'Enabled') : I18n.t('common.disabled', {}, 'Disabled');
    }
    if (autoStatus && autoToggle) {
        autoStatus.textContent = autoToggle.checked ? I18n.t('common.enabled', {}, 'Enabled') : I18n.t('common.disabled', {}, 'Disabled');
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
            tokenInput.placeholder = config.has_token
                ? I18n.t('meeting.token_saved_placeholder', {}, '•••••••• (saved)')
                : I18n.t('meeting.no_token', {}, 'No token');
        }
        if (provisionedBadge) {
            if (config.provisioned) {
                provisionedBadge.textContent = I18n.t('common.yes', {}, 'Yes');
                provisionedBadge.className = 'badge badge-success';
            } else {
                provisionedBadge.textContent = I18n.t('common.no', {}, 'No');
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

        showToast(I18n.t('meeting.save_in_progress', {}, 'Saving Meeting...'), 'info');

        const response = await fetch('/api/meeting/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            showToast(I18n.t('meeting.config_saved', {}, 'Meeting configuration saved'), 'success');
            loadMeetingStatus();
            loadMeetingConfig();
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message || data.error }, `Error: ${data.message || data.error}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
                    statusEl.innerHTML = `<i class="fas fa-circle"></i> ${I18n.t('meeting.status_not_provisioned', {}, 'Not provisioned')}`;
                }
                if (detailsEl) {
                    detailsEl.innerHTML = `<small>${I18n.t('meeting.status_enter_credentials', {}, 'Enter your credentials to provision this device')}</small>`;
                }
            } else if (status.connected) {
                // Connected and heartbeat working
                if (statusEl) {
                    statusEl.className = 'status-indicator connected';
                    statusEl.innerHTML = `<i class="fas fa-circle"></i> ${I18n.t('common.connected', {}, 'Connected')}`;
                }
                if (detailsEl) {
                    let details = `<small>${I18n.t('meeting.status_device', { device: status.device_key }, `Device: ${status.device_key}`)}`;
                    if (status.last_heartbeat_ago !== null) {
                        details += ` • ${I18n.t('meeting.status_last_heartbeat_ago', { seconds: status.last_heartbeat_ago }, `Last heartbeat: ${status.last_heartbeat_ago}s ago`)}`;
                    }
                    if (status.heartbeat_thread_running) {
                        details += ` • ${I18n.t('meeting.status_interval', { seconds: status.heartbeat_interval }, `Interval: ${status.heartbeat_interval}s`)}`;
                    }
                    details += '</small>';
                    detailsEl.innerHTML = details;
                }
            } else if (status.enabled) {
                // Configured and enabled but not yet connected (or connection failed)
                if (statusEl) {
                    if (status.last_error) {
                        statusEl.className = 'status-indicator disconnected';
                        statusEl.innerHTML = `<i class="fas fa-circle"></i> ${I18n.t('meeting.status_connection_error', {}, 'Connection error')}`;
                    } else {
                        statusEl.className = 'status-indicator pending';
                        statusEl.innerHTML = `<i class="fas fa-circle"></i> ${I18n.t('meeting.status_pending_connection', {}, 'Waiting for connection')}`;
                    }
                }
                if (detailsEl) {
                    if (status.last_error) {
                        detailsEl.innerHTML = `<small>${I18n.t('meeting.status_device_with_error', { device: status.device_key, error: status.last_error }, `Device: ${status.device_key} • ${status.last_error}`)}</small>`;
                    } else {
                        detailsEl.innerHTML = `<small>${I18n.t('meeting.status_waiting_first_heartbeat', { device: status.device_key }, `Device: ${status.device_key} • Waiting for first heartbeat`)}</small>`;
                    }
                }
            } else {
                // Configured but disabled
                if (statusEl) {
                    statusEl.className = 'status-indicator disconnected';
                    statusEl.innerHTML = `<i class="fas fa-circle"></i> ${I18n.t('common.disabled', {}, 'Disabled')}`;
                }
                if (detailsEl) {
                    detailsEl.innerHTML = `<small>${I18n.t('meeting.status_meeting_disabled', { device: status.device_key }, `Device: ${status.device_key} • Meeting disabled`)}</small>`;
                }
            }

            // Load config form values
            loadMeetingConfig();
            
            // If provisioned, also load the additional sections
            if (status.provisioned) {
                loadMeetingServices();
                loadSshKeysStatus();
                loadDeviceSshKey();
                loadTunnelAgentStatus();
            }
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
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.fill_all_fields', {}, 'Please fill in all fields')}`;
        if (provisionBtn) provisionBtn.disabled = true;
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.validating_credentials', {}, 'Validating credentials...')}`;
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
                tokenWarning = `<br><strong style="color: var(--danger-color);">⚠️ ${I18n.t('meeting.no_token_available', {}, 'No token available! Provisioning impossible.')}</strong>`;
                if (provisionBtn) provisionBtn.disabled = true;
            } else if (device.token_count === 1) {
                tokenClass = 'warning';
                tokenWarning = `<br><small style="color: var(--warning-color);">⚠️ ${I18n.t('meeting.last_token_available', {}, 'Last token available')}</small>`;
                if (provisionBtn) provisionBtn.disabled = false;
            } else {
                if (provisionBtn) provisionBtn.disabled = false;
            }
            
            resultDiv.innerHTML = `
                <i class="fas fa-check-circle"></i> <strong>${I18n.t('meeting.credentials_valid', {}, 'Credentials valid!')}</strong>
                <div class="provision-info">
                    <div class="provision-info-item">
                        <span class="label">${I18n.t('meeting.device_label', {}, 'Device')}</span>
                        <span class="value">${device.name || I18n.t('meeting.device_name_unknown', {}, 'Unnamed')}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${I18n.t('meeting.authorized_label', {}, 'Authorized')}</span>
                        <span class="value ${device.authorized ? 'success' : 'danger'}">${device.authorized ? I18n.t('meeting.online_yes', {}, 'Yes ✓') : I18n.t('meeting.online_no', {}, 'No ✗')}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${I18n.t('meeting.tokens_available_label', {}, 'Tokens available')}</span>
                        <span class="value ${tokenClass}">${device.token_count}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${I18n.t('meeting.online_label', {}, 'Online')}</span>
                        <span class="value">${device.online ? I18n.t('common.yes', {}, 'Yes') : I18n.t('common.no', {}, 'No')}</span>
                    </div>
                </div>
                ${tokenWarning}
                ${device.token_count > 0 && device.authorized ? `<p style="margin-top: 10px;"><i class="fas fa-info-circle"></i> ${I18n.t('meeting.provision_click_to_continue', {}, 'Click "Provision device" to continue. This will consume 1 token.')}</p>` : ''}
            `;
            
            if (!device.authorized) {
                resultDiv.innerHTML += `<p style="color: var(--danger-color); margin-top: 10px;"><i class="fas fa-ban"></i> ${I18n.t('meeting.device_not_authorized', {}, 'This device is not authorized in Meeting.')}</p>`;
                if (provisionBtn) provisionBtn.disabled = true;
            }
            
            showToast(I18n.t('meeting.credentials_valid_toast', {}, 'Credentials validated'), 'success');
        } else {
            resultDiv.className = 'meeting-result validation-error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> <strong>${I18n.t('meeting.validation_failed', {}, 'Validation failed')}</strong><br>${data.message}`;
            if (provisionBtn) provisionBtn.disabled = true;
            showToast(I18n.t('meeting.credentials_invalid_toast', {}, 'Invalid credentials'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result validation-error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        if (provisionBtn) provisionBtn.disabled = true;
        showToast(I18n.t('meeting.validation_error_toast', {}, 'Validation error'), 'error');
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
    
    if (!confirm(I18n.t('meeting.provision_confirm', {}, 'Are you sure you want to provision this device?\n\nThis will:\n- Consume 1 provisioning token\n- Change the device hostname\n- Lock Meeting configuration'))) {
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.className = 'meeting-result loading';
    resultDiv.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.provision_in_progress', {}, 'Provisioning in progress... Please wait.')}`;
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
                <i class="fas fa-check-circle"></i> <strong>${I18n.t('meeting.provision_success', {}, 'Provisioning successful!')}</strong>
                <div class="provision-info">
                    <div class="provision-info-item">
                        <span class="label">${I18n.t('meeting.new_hostname_label', {}, 'New hostname')}</span>
                        <span class="value">${data.hostname}</span>
                    </div>
                    <div class="provision-info-item">
                        <span class="label">${I18n.t('meeting.token_consumed_label', {}, 'Token consumed')}</span>
                        <span class="value success">${I18n.t('common.yes', {}, 'Yes')}</span>
                    </div>
                </div>
                <p style="margin-top: 15px; color: var(--warning-color);">
                    <i class="fas fa-exclamation-triangle"></i> <strong>${I18n.t('meeting.important_label', {}, 'Important')}:</strong> ${I18n.t('meeting.hostname_changed', {}, 'Hostname has changed.')}
                    ${I18n.t('meeting.hostname_access_hint', {}, 'After a few seconds, you can access the UI at:')}
                    <br><code>http://${data.hostname}.local</code>
                </p>
            `;
            showToast(I18n.t('meeting.provision_success_toast', {}, 'Device provisioned successfully!'), 'success');
            
            // Reload status after a short delay
            setTimeout(() => {
                loadMeetingStatus();
            }, 2000);
        } else {
            resultDiv.className = 'meeting-result validation-error';
            resultDiv.innerHTML = `<i class="fas fa-times-circle"></i> <strong>${I18n.t('meeting.provision_failed', {}, 'Provisioning failed')}</strong><br>${data.message}`;
            if (provisionBtn) provisionBtn.disabled = false;
            showToast(I18n.t('meeting.provision_failed_toast', {}, 'Provisioning failed'), 'error');
        }
    } catch (error) {
        resultDiv.className = 'meeting-result validation-error';
        resultDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`)}`;
        if (provisionBtn) provisionBtn.disabled = false;
        showToast(I18n.t('meeting.provision_error_toast', {}, 'Provisioning error'), 'error');
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
        showToast(I18n.t('meeting.master_code_required', {}, 'Please enter the master code'), 'warning');
        return;
    }
    
    try {
        showToast(I18n.t('meeting.reset_in_progress', {}, 'Reset in progress...'), 'info');
        
        const response = await fetch('/api/meeting/master-reset', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ master_code: code })
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeMasterResetModal();
            showToast(I18n.t('meeting.reset_done', {}, 'Meeting configuration reset'), 'success');
            loadMeetingStatus();
            // Reload page to refresh all config
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showToast(data.message || I18n.t('meeting.reset_failed', {}, 'Reset failed'), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
                error: data.message || I18n.t('meeting.ntp_error', {}, 'NTP error')
            });
        }
    } catch (error) {
        console.error('Error loading NTP config:', error);
        updateNtpStatus({
            synchronized: false,
            server: null,
            current_time: null,
            timezone: null,
            error: error.message || I18n.t('meeting.ntp_error', {}, 'NTP error')
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
    html += `<span>${data.synchronized ? I18n.t('meeting.ntp_synced', {}, 'Synchronized') : I18n.t('meeting.ntp_not_synced', {}, 'Not synchronized')}</span>`;
    html += `</div>`;
    
    if (data.error) {
        html += `<div class="ntp-details"><span><strong>${I18n.t('meeting.error_label', {}, 'Error')}:</strong> ${data.error}</span></div>`;
    } else if (data.server || data.current_time) {
        html += `<div class="ntp-details">`;
        if (data.server) html += `<span><strong>${I18n.t('meeting.ntp_server_label', {}, 'Server')}:</strong> ${data.server}</span>`;
        if (data.current_time) html += `<span><strong>${I18n.t('meeting.ntp_system_time_label', {}, 'System time')}:</strong> ${data.current_time}</span>`;
        if (data.timezone) html += `<span><strong>${I18n.t('meeting.ntp_timezone_label', {}, 'Timezone')}:</strong> ${data.timezone}</span>`;
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
        showToast(I18n.t('meeting.ntp_server_required', {}, 'Please enter an NTP server'), 'warning');
        return;
    }
    
    try {
        showToast(I18n.t('meeting.ntp_configuring', {}, 'Configuring NTP...'), 'info');
        
        const response = await fetch('/api/system/ntp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ server })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('meeting.ntp_server_configured', {}, 'NTP server configured'), 'success');
            loadNtpConfig();
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Force NTP synchronization now
 */
async function syncNtpNow() {
    try {
        showToast(I18n.t('meeting.ntp_sync_in_progress', {}, 'Synchronization in progress...'), 'info');
        
        const response = await fetch('/api/system/ntp/sync', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('meeting.ntp_time_synced', {}, 'Time synchronized'), 'success');
            loadNtpConfig();
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
                error: data.message || I18n.t('meeting.rtc_error', {}, 'RTC error')
            });
        }
    } catch (error) {
        console.error('Error loading RTC config:', error);
        updateRtcStatus({
            success: false,
            error: error.message || I18n.t('meeting.rtc_error', {}, 'RTC error')
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
                <span>${I18n.t('meeting.rtc_error', {}, 'RTC error')}</span>
            </div>
            <div class="rtc-details"><span><strong>${I18n.t('meeting.error_label', {}, 'Error')}:</strong> ${data.error}</span></div>
        `;
        return;
    }

    const enabled = !!data.effective_enabled;
    const detected = !!data.detected;
    const indicatorClass = enabled ? 'synced' : 'not-synced';
    const indicatorLabel = enabled ? I18n.t('common.active', {}, 'Active') : I18n.t('common.inactive', {}, 'Inactive');
    const modeLabel = data.mode || I18n.t('common.auto', {}, 'auto');
    const viaLabel = data.detected_via ? ` (${data.detected_via})` : '';

    let html = `<div class="status-indicator ${indicatorClass}">`;
    html += `<i class="fas fa-${enabled ? 'check-circle' : 'exclamation-triangle'}"></i>`;
    html += `<span>${I18n.t('meeting.rtc_status', { status: indicatorLabel }, `RTC ${indicatorLabel}`)}</span>`;
    html += `</div>`;
    html += `<div class="rtc-details">`;
    html += `<span><strong>${I18n.t('meeting.rtc_mode_label', {}, 'Mode')}:</strong> ${modeLabel}</span>`;
    html += `<span><strong>${I18n.t('meeting.rtc_detected_label', {}, 'Detected')}:</strong> ${detected ? I18n.t('common.yes', {}, 'Yes') : I18n.t('common.no', {}, 'No')}${detected ? viaLabel : ''}</span>`;
    html += `<span><strong>${I18n.t('meeting.rtc_overlay_label', {}, 'Overlay')}:</strong> ${data.overlay_configured ? I18n.t('meeting.rtc_configured', {}, 'Configured') : I18n.t('meeting.rtc_not_configured', {}, 'Not configured')}</span>`;
    html += `<span><strong>${I18n.t('meeting.rtc_i2c_label', {}, 'I2C')}:</strong> ${data.i2c_enabled ? I18n.t('common.enabled', {}, 'Enabled') : I18n.t('common.disabled', {}, 'Disabled')}</span>`;
    if (data.auto_pending) {
        if (!data.i2c_enabled) {
            html += `<span><strong>${I18n.t('common.auto', {}, 'Auto')}:</strong> ${I18n.t('meeting.rtc_auto_i2c_disabled', {}, 'I2C disabled, apply to enable')}</span>`;
        } else {
            html += `<span><strong>${I18n.t('common.auto', {}, 'Auto')}:</strong> ${I18n.t('meeting.rtc_auto_module_detected', {}, 'Module detected, apply to enable')}</span>`;
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
        showToast(I18n.t('meeting.rtc_applying', {}, 'Applying RTC...'), 'info');

        const response = await fetch('/api/system/rtc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: rtcMode })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message || I18n.t('meeting.rtc_configured', {}, 'RTC configured'), 'success');
            loadRtcConfig();
            if (data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 800);
            }
        } else {
            showToast(I18n.t('meeting.rtc_error_with_message', { error: data.message || I18n.t('meeting.rtc_apply_failed', {}, 'Unable to apply') }, `RTC error: ${data.message || "Unable to apply"}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.rtc_error_with_message', { error: error.message }, `RTC error: ${error.message}`), 'error');
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
        showToast(I18n.t('meeting.reboot_schedule_saving', {}, 'Saving schedule...'), 'info');
        const response = await fetch('/api/system/reboot/schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, hour, minute, days })
        });
        const data = await response.json();
        if (data.success) {
            showToast(I18n.t('meeting.reboot_schedule_saved', {}, 'Reboot schedule saved'), 'success');
            loadRebootSchedule();
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message || I18n.t('meeting.reboot_schedule_save_failed', {}, 'Unable to save') }, `Error: ${data.message || 'Unable to save'}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
        showToast(I18n.t('meeting.snmp_configuring', {}, 'Configuring SNMP...'), 'info');
        const response = await fetch('/api/system/snmp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, host, port })
        });
        const data = await response.json();
        if (data.success) {
            showToast(I18n.t('meeting.snmp_configured', {}, 'SNMP configuration applied'), 'success');
            loadSnmpConfig();
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message || I18n.t('meeting.snmp_save_failed', {}, 'Unable to save') }, `Error: ${data.message || 'Unable to save'}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

async function testSnmpConfig() {
    const enabled = document.getElementById('snmp_enabled')?.checked === true;
    const host = document.getElementById('snmp_host')?.value?.trim() || '';
    const port = parseInt(document.getElementById('snmp_port')?.value || '162', 10);

    try {
        showToast(I18n.t('meeting.snmp_test_in_progress', {}, 'SNMP test...'), 'info');
        const response = await fetch('/api/system/snmp/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, host, port })
        });
        const data = await response.json();
        if (data.success) {
            showToast(data.message || I18n.t('meeting.snmp_ok', {}, 'SNMP OK'), 'success');
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message || I18n.t('meeting.snmp_test_failed', {}, 'SNMP test failed') }, `Error: ${data.message || 'SNMP test failed'}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
        updateBackupStatus(I18n.t('meeting.backup_invalid_action', {}, 'Invalid backup action'), 'error');
    }
}

async function backupConfiguration() {
    const includeLogs = confirm(I18n.t('meeting.backup_include_logs_confirm', {}, 'Include logs in the backup?'));
    updateBackupStatus(I18n.t('meeting.backup_preparing', {}, 'Preparing backup...'), 'checking');

    try {
        const response = await fetch('/api/system/backup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ include_logs: includeLogs })
        });

        const contentType = response.headers.get('content-type') || '';
        if (!response.ok || contentType.includes('application/json')) {
            const data = await response.json();
            const message = data.message || I18n.t('meeting.backup_error', {}, 'Backup error');
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

        updateBackupStatus(I18n.t('meeting.backup_downloaded', {}, 'Backup downloaded'), 'success');
        showToast(I18n.t('meeting.backup_generated', {}, 'Backup generated'), 'success');
    } catch (error) {
        updateBackupStatus(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
        showToast(I18n.t('meeting.backup_error_with_message', { error: error.message }, `Backup error: ${error.message}`), 'error');
    }
}

async function checkBackupFile(file) {
    updateBackupStatus(I18n.t('meeting.backup_checking', {}, 'Checking backup...'), 'checking');

    try {
        const formData = new FormData();
        formData.append('backup', file);

        const response = await fetch('/api/system/backup/check', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || I18n.t('meeting.backup_invalid', {}, 'Invalid backup');
            updateBackupStatus(message, 'error');
            showToast(message, 'error');
            return;
        }

        const info = I18n.t('meeting.backup_valid_info', { version: data.version || 'N/A', files: data.files_count || 0 }, `Valid backup (v${data.version || 'N/A'}, ${data.files_count || 0} files)`);
        updateBackupStatus(info, 'success');
        showToast(info, 'success');

        if (confirm(I18n.t('meeting.backup_restore_confirm', { info }, `${info}\n\nDo you want to restore this backup?`))) {
            restoreBackupFile(file, true);
        }
    } catch (error) {
        updateBackupStatus(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
        showToast(I18n.t('meeting.backup_check_error_with_message', { error: error.message }, `Check error: ${error.message}`), 'error');
    }
}

async function restoreBackupFile(file, skipConfirm = false) {
    if (!skipConfirm) {
        const proceed = confirm(I18n.t('meeting.backup_restore_confirm_reboot', {}, 'Restore configuration from this backup?\n\nThe Raspberry Pi will reboot.'));
        if (!proceed) return;
    }

    updateBackupStatus(I18n.t('meeting.backup_restore_in_progress', {}, 'Restore in progress...'), 'updating');

    try {
        const formData = new FormData();
        formData.append('backup', file);

        const response = await fetch('/api/system/backup/restore', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || I18n.t('meeting.backup_restore_failed', {}, 'Restore failed');
            updateBackupStatus(message, 'error');
            showToast(message, 'error');
            return;
        }

        updateBackupStatus(I18n.t('meeting.backup_restore_success_reboot', {}, 'Restore successful, reboot in progress...'), 'success');
        showToast(I18n.t('meeting.backup_restore_success_reboot_toast', {}, 'Restore successful, rebooting...'), 'success');

        showRebootOverlay();
        startRebootMonitoring();
    } catch (error) {
        updateBackupStatus(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
        showToast(I18n.t('meeting.backup_restore_error_with_message', { error: error.message }, `Restore error: ${error.message}`), 'error');
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
                if (nameInput) nameInput.value = data.config.name || I18n.t('meeting.onvif_name_unprovisioned', {}, 'UNPROVISIONED');
                if (usernameInput) usernameInput.value = data.config.username || '';
                if (passwordInput) {
                    passwordInput.value = '';
                    passwordInput.placeholder = data.config.has_password
                        ? I18n.t('meeting.onvif_password_saved_placeholder', {}, '•••••••• (saved)')
                        : I18n.t('meeting.onvif_no_password', {}, 'No password');
                }
                if (rtspPortInput) rtspPortInput.value = data.config.rtsp_port || 8554;
                if (rtspPathInput) rtspPathInput.value = data.config.rtsp_path || '/stream';
                
                // Show/hide Meeting API badge based on source
                if (nameSourceBadge) {
                    if (data.config.name_from_meeting) {
                        nameSourceBadge.style.display = 'inline';
                        if (nameHint) nameHint.textContent = I18n.t('meeting.onvif_name_from_meeting', {}, 'Name retrieved automatically from Meeting API (product_serial)');
                    } else {
                        nameSourceBadge.style.display = 'none';
                        if (nameHint) nameHint.textContent = I18n.t('meeting.onvif_name_default_hint', {}, 'Meeting API not configured - default name used');
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
        const bitrate = settings.bitrate ? `${settings.bitrate} kbps` : I18n.t('common.auto', {}, 'Auto');
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
                <span>${I18n.t('meeting.onvif_service_active', {}, 'ONVIF service active')}</span>
            </div>
            <div class="onvif-details">
                <span><strong>${I18n.t('meeting.onvif_port_label', {}, 'Port')}:</strong> ${data.config?.port || 8080}</span>
                <span><strong>${I18n.t('meeting.onvif_name_label', {}, 'Name')}:</strong> ${data.config?.name || 'RPI-CAM'}</span>
                <span><strong>${I18n.t('meeting.onvif_url_label', {}, 'URL')}:</strong> http://${onvifHost}:${data.config?.port || 8080}/onvif/device_service</span>
            </div>
        `;
    } else if (data.enabled) {
        html = `
            <div class="status-indicator not-synced">
                <i class="fas fa-exclamation-triangle"></i>
                <span>${I18n.t('meeting.onvif_service_stopped', {}, 'ONVIF service stopped')}</span>
            </div>
        `;
    } else {
        html = `
            <div class="status-indicator">
                <i class="fas fa-power-off"></i>
                <span>${I18n.t('meeting.onvif_service_disabled', {}, 'ONVIF service disabled')}</span>
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
        
        showToast(I18n.t('meeting.onvif_saving', {}, 'Saving ONVIF...'), 'info');
        
        const response = await fetch('/api/onvif/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('meeting.onvif_saved', {}, 'ONVIF configuration saved'), 'success');
            loadOnvifStatus();
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    }
}

/**
 * Restart ONVIF service
 */
async function restartOnvifService() {
    try {
        showToast(I18n.t('meeting.onvif_restarting', {}, 'Restarting ONVIF service...'), 'info');
        
        const response = await fetch('/api/onvif/restart', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(I18n.t('meeting.onvif_restarted', {}, 'ONVIF service restarted'), 'success');
            setTimeout(loadOnvifStatus, 2000);
        } else {
            showToast(I18n.t('meeting.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
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
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.firmware_checking', {}, 'Checking...')}`;
    statusText.textContent = I18n.t('meeting.firmware_check_in_progress', {}, 'Check in progress...');
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
                statusText.textContent = I18n.t('meeting.firmware_use_apt', {}, 'Use apt upgrade');
                statusText.className = 'status-value use-apt';
                details.innerHTML = `<small>${I18n.t('meeting.firmware_kernel_label', {}, 'Kernel')}: ${data.current_version}<br>⚠️ ${I18n.t('meeting.firmware_initramfs_detected', {}, 'initramfs detected - rpi-update not supported')}</small>`;
                updateBtn.disabled = true;
                updateBtn.title = I18n.t('meeting.firmware_initramfs_tooltip', {}, 'initramfs detected - use apt upgrade below');
            } else if (data.update_available) {
                statusText.textContent = I18n.t('meeting.firmware_update_available', {}, 'Update available');
                statusText.className = 'status-value update-available';
                details.innerHTML = `<small>${I18n.t('meeting.firmware_current_version', {}, 'Current version')}: ${data.current_version}</small>`;
                updateBtn.disabled = false;
            } else {
                statusText.textContent = I18n.t('meeting.firmware_up_to_date', {}, 'Up to date');
                statusText.className = 'status-value up-to-date';
                details.innerHTML = `<small>${I18n.t('meeting.firmware_version', {}, 'Version')}: ${data.current_version}</small>`;
                updateBtn.disabled = true;
            }
            // Update last check date
            document.getElementById('firmware-last-date').textContent = I18n.t('meeting.last_action_now', {}, 'just now');
        } else {
            statusText.textContent = I18n.t('common.error', {}, 'Error');
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            updateBtn.disabled = true;
        }
    } catch (error) {
        statusText.textContent = I18n.t('common.error', {}, 'Error');
        statusText.className = 'status-value error';
        details.innerHTML = `<small>${error.message}</small>`;
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-search"></i> ${I18n.t('meeting.firmware_check_button', {}, 'Check')}`;
    }
}

/**
 * Run firmware update
 */
async function runFirmwareUpdate() {
    const updateBtn = document.getElementById('btn-update-firmware');
    const method = updateBtn.dataset.method || 'unknown';
    
    // Different warning for rpi-update (experimental firmware)
    let confirmMessage = I18n.t('meeting.firmware_update_confirm', {}, 'Do you want to update the firmware?\n\nA reboot will be required after the update.');
    if (method === 'rpi-update') {
        confirmMessage = I18n.t('meeting.firmware_update_warning_rpi', {}, '⚠️ WARNING: rpi-update installs EXPERIMENTAL firmware!\n\nThis may cause system instability.\nUse only if you know what you are doing.\n\nDo you want to continue?');
    }
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    const btn = document.getElementById('btn-update-firmware');
    const statusText = document.getElementById('firmware-status-text');
    const output = document.getElementById('firmware-output');
    
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.firmware_updating', {}, 'Updating...')}`;
    statusText.textContent = I18n.t('meeting.firmware_update_in_progress', {}, 'Update in progress...');
    statusText.className = 'status-value updating';
    output.textContent = I18n.t('meeting.firmware_download_install', {}, 'Downloading and installing firmware...\nThis may take several minutes, please wait...');
    
    try {
        const response = await fetch('/api/debug/firmware/update', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        // Show warning if present
        if (data.warning) {
            output.textContent += '\n\n⚠️ ' + data.warning;
        }
        
        if (data.success) {
            statusText.textContent = I18n.t('meeting.firmware_reboot_required', {}, 'Reboot required');
            statusText.className = 'status-value reboot-required';
            showToast(I18n.t('meeting.firmware_updated_toast', {}, 'Firmware updated! Reboot to finalize.'), 'success');
            
            if (data.reboot_required) {
                setTimeout(() => {
                    performReboot();
                }, 1000);
            }
        } else {
            statusText.textContent = I18n.t('common.error', {}, 'Error');
            statusText.className = 'status-value error';
            showToast(I18n.t('meeting.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        statusText.textContent = I18n.t('common.error', {}, 'Error');
        statusText.className = 'status-value error';
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-download"></i> ${I18n.t('meeting.firmware_update_button', {}, 'Update')}`;
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
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.apt_running', {}, 'Running...')}`;
    statusText.textContent = I18n.t('meeting.apt_running', {}, 'Running...');
    statusText.className = 'status-value running';
    outputContainer.style.display = 'block';
    output.textContent = I18n.t('meeting.apt_refreshing', {}, 'Refreshing package lists...\nThis may take a few minutes...');
    
    try {
        const response = await fetch('/api/debug/apt/update', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        if (data.success) {
            statusText.textContent = I18n.t('meeting.apt_done', {}, 'Done');
            statusText.className = 'status-value success';
            details.innerHTML = `<small>${I18n.t('meeting.apt_update_details', { sources: data.hit_count, updates: data.get_count }, `${data.hit_count} sources, ${data.get_count} updates`)}</small>`;
            document.getElementById('apt-update-last-date').textContent = I18n.t('meeting.last_action_now', {}, 'just now');
            showToast(data.message, 'success');
        } else {
            statusText.textContent = I18n.t('common.error', {}, 'Error');
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            showToast(I18n.t('meeting.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        statusText.textContent = I18n.t('common.error', {}, 'Error');
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-sync"></i> ${I18n.t('meeting.apt_update_button', {}, 'Run apt update')}`;
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
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.apt_checking', {}, 'Checking...')}`;
    statusText.textContent = I18n.t('meeting.apt_checking', {}, 'Checking...');
    statusText.className = 'status-value checking';
    
    try {
        const response = await fetch('/api/debug/apt/upgradable');
        const data = await response.json();
        
        outputContainer.style.display = 'block';
        
        if (data.success) {
            if (data.count > 0) {
                statusText.textContent = I18n.t('meeting.apt_updates_count', { count: data.count }, `${data.count} updates`);
                statusText.className = 'status-value update-available';
                details.innerHTML = `<small>${I18n.t('meeting.apt_packages_upgradable', { count: data.count }, `${data.count} packages can be upgraded`)}</small>`;
                
                // Format output nicely
                let formattedOutput = I18n.t('meeting.apt_packages_header', { count: data.count }, `=== ${data.count} packages can be upgraded ===\n\n`);
                data.packages.forEach(pkg => {
                    formattedOutput += `• ${pkg.name} → ${pkg.version}\n`;
                });
                output.textContent = formattedOutput;
            } else {
                statusText.textContent = I18n.t('meeting.apt_up_to_date', {}, 'Up to date');
                statusText.className = 'status-value up-to-date';
                details.innerHTML = `<small>${I18n.t('meeting.apt_all_up_to_date', {}, 'All packages are up to date')}</small>`;
                output.textContent = I18n.t('meeting.apt_no_updates', {}, 'No updates available.');
            }
        } else {
            statusText.textContent = I18n.t('common.error', {}, 'Error');
            statusText.className = 'status-value error';
            output.textContent = data.message;
        }
    } catch (error) {
        statusText.textContent = I18n.t('common.error', {}, 'Error');
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-list"></i> ${I18n.t('meeting.apt_view_packages_button', {}, 'View packages')}`;
    }
}

/**
 * Run apt upgrade
 */
async function runAptUpgrade() {
    if (!confirm(I18n.t('meeting.apt_upgrade_confirm', {}, 'Do you want to update all packages?\n\nThis may take several minutes.'))) {
        return;
    }
    
    const btn = document.getElementById('btn-apt-upgrade');
    const statusText = document.getElementById('apt-upgrade-status-text');
    const details = document.getElementById('apt-upgrade-details');
    const outputContainer = document.getElementById('apt-upgrade-output-container');
    const output = document.getElementById('apt-upgrade-output');
    
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.apt_upgrading', {}, 'Updating...')}`;
    statusText.textContent = I18n.t('meeting.apt_running', {}, 'Running...');
    statusText.className = 'status-value running';
    outputContainer.style.display = 'block';
    output.textContent = I18n.t('meeting.apt_installing', {}, 'Installing updates...\nThis may take several minutes, please wait...');
    
    try {
        const response = await fetch('/api/debug/apt/upgrade', { method: 'POST' });
        const data = await response.json();
        
        output.textContent = data.output || data.message;
        
        if (data.success) {
            statusText.textContent = I18n.t('meeting.apt_done', {}, 'Done');
            statusText.className = 'status-value success';
            details.innerHTML = `<small>${I18n.t('meeting.apt_upgrade_details', { upgraded: data.upgraded, newly_installed: data.newly_installed }, `${data.upgraded} upgraded, ${data.newly_installed} new`)}</small>`;
            document.getElementById('apt-upgrade-last-date').textContent = I18n.t('meeting.last_action_now', {}, 'just now');
            showToast(data.message, 'success');
        } else {
            statusText.textContent = I18n.t('common.error', {}, 'Error');
            statusText.className = 'status-value error';
            details.innerHTML = `<small>${data.message}</small>`;
            showToast(I18n.t('meeting.error_with_message', { error: data.message }, `Error: ${data.message}`), 'error');
        }
    } catch (error) {
        statusText.textContent = I18n.t('common.error', {}, 'Error');
        statusText.className = 'status-value error';
        output.textContent = error.message;
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-arrow-up"></i> ${I18n.t('meeting.apt_upgrade_button', {}, 'Update')}`;
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
            statusText.textContent = enabled ? I18n.t('common.active', {}, 'Active') : I18n.t('common.inactive', {}, 'Inactive');
            statusText.className = `status-value ${enabled ? 'synced' : 'not-synced'}`;

            const detected = data.status.detected ? I18n.t('meeting.rtc_debug_detected', {}, 'detected') : I18n.t('meeting.rtc_debug_not_detected', {}, 'not detected');
            const mode = data.status.mode || I18n.t('common.auto', {}, 'auto');
            details.innerHTML = `<small>${I18n.t('meeting.rtc_debug_details', { mode, detected, overlay: data.status.overlay_configured ? I18n.t('meeting.rtc_debug_overlay_ok', {}, 'ok') : I18n.t('meeting.rtc_debug_overlay_missing', {}, 'missing') }, `Mode: ${mode} • RTC ${detected} • Overlay: ${data.status.overlay_configured ? 'ok' : 'missing'}`)}</small>`;
        } else {
            statusText.textContent = I18n.t('common.error', {}, 'Error');
            statusText.className = 'status-value warning';
            details.innerHTML = `<small>${data.message || I18n.t('meeting.rtc_error', {}, 'RTC error')}</small>`;
        }
    } catch (error) {
        if (statusText) {
            statusText.textContent = I18n.t('common.error', {}, 'Error');
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
    if (!dateStr) return I18n.t('meeting.last_action_never', {}, 'never');
    
    try {
        const date = new Date(dateStr.replace(' ', 'T'));
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return I18n.t('meeting.last_action_now', {}, 'just now');
        if (diffMins < 60) return I18n.t('meeting.last_action_minutes', { count: diffMins }, `${diffMins} min ago`);
        if (diffHours < 24) return I18n.t('meeting.last_action_hours', { count: diffHours }, `${diffHours}h ago`);
        if (diffDays < 7) return I18n.t('meeting.last_action_days', { count: diffDays, plural: diffDays > 1 ? 's' : '' }, `${diffDays} day${diffDays > 1 ? 's' : ''} ago`);
        
        // Format as date
        const locale = I18n.currentLanguage === 'fr' ? 'fr-FR' : 'en-US';
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
            statusText.textContent = scheduler.enabled ? I18n.t('common.enabled', {}, 'Enabled') : I18n.t('common.disabled', {}, 'Disabled');
            
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
    statusText.textContent = enabled ? I18n.t('meeting.scheduler_configuring', {}, 'Configuring...') : I18n.t('common.disabled', {}, 'Disabled');
    
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
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${I18n.t('meeting.scheduler_saving', {}, 'Saving...')}`;
    }
    
    try {
        const response = await fetch('/api/debug/apt/scheduler', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await response.json();
        
        if (data.success) {
            statusText.textContent = config.enabled ? I18n.t('common.enabled', {}, 'Enabled') : I18n.t('common.disabled', {}, 'Disabled');
            showToast(data.message || I18n.t('meeting.scheduler_saved', {}, 'Schedule saved'), 'success');
        } else {
            showToast(data.message || I18n.t('common.error', {}, 'Error'), 'error');
        }
    } catch (error) {
        showToast(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-save"></i> ${I18n.t('common.save', {}, 'Save')}`;
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
            appendTerminalLine(I18n.t('meeting.terminal_command_not_allowed', { command: command.split(' ')[0] }, `Command not allowed: ${command.split(' ')[0]}`), 'terminal-error');
            appendTerminalLine(I18n.t('meeting.terminal_help_hint', {}, 'Type "help" to see allowed commands.'), 'terminal-info');
        } else if (data.success) {
            if (data.stdout) {
                appendTerminalLine(data.stdout, 'terminal-stdout');
            }
            if (data.stderr) {
                appendTerminalLine(data.stderr, 'terminal-stderr');
            }
            if (data.returncode !== 0 && !data.stdout && !data.stderr) {
                appendTerminalLine(I18n.t('meeting.terminal_return_code', { code: data.returncode }, `Command finished with code ${data.returncode}`), 'terminal-info');
            }
        } else {
            appendTerminalLine(I18n.t('meeting.error_with_message', { error: data.error }, `Error: ${data.error}`), 'terminal-error');
        }
    } catch (error) {
        appendTerminalLine(I18n.t('meeting.terminal_network_error', { error: error.message }, `Network error: ${error.message}`), 'terminal-error');
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
    appendTerminalLine(I18n.t('meeting.terminal_cleared', {}, 'Terminal cleared.'), 'terminal-info');
}

/**
 * Show allowed commands
 */
async function showAllowedCommands() {
    appendTerminalLine(I18n.t('meeting.terminal_allowed_loading', {}, 'Loading allowed commands...'), 'terminal-info');
    
    try {
        const response = await fetch('/api/debug/terminal/allowed');
        const data = await response.json();
        
        if (data.success) {
            appendTerminalLine(I18n.t('meeting.terminal_allowed_header', {}, '=== Allowed commands ==='), 'terminal-success');
            
            // Group commands by category
            const categories = {
                [I18n.t('meeting.terminal_category_system', {}, 'System')]: ['ls', 'cat', 'head', 'tail', 'grep', 'find', 'df', 'du', 'free', 'top', 'ps', 'uptime', 'date', 'hostname', 'uname', 'whoami', 'id', 'pwd'],
                [I18n.t('meeting.terminal_category_logs', {}, 'Logs')]: ['journalctl', 'dmesg'],
                [I18n.t('meeting.terminal_category_services', {}, 'Services')]: ['systemctl', 'service'],
                [I18n.t('meeting.terminal_category_network', {}, 'Network')]: ['ip', 'ifconfig', 'iwconfig', 'nmcli', 'netstat', 'ss', 'ping', 'traceroute', 'curl', 'wget'],
                [I18n.t('meeting.terminal_category_hardware', {}, 'Hardware')]: ['vcgencmd', 'pinctrl', 'lsusb', 'lspci', 'lsblk', 'lscpu', 'lshw', 'lsmod', 'v4l2-ctl'],
                [I18n.t('meeting.terminal_category_media', {}, 'Media')]: ['ffprobe', 'ffmpeg', 'gst-launch-1.0', 'gst-inspect-1.0', 'test-launch'],
                [I18n.t('meeting.terminal_category_packages', {}, 'Packages')]: ['apt', 'apt-get', 'apt-cache', 'dpkg'],
                [I18n.t('meeting.terminal_category_utils', {}, 'Utilities')]: ['echo', 'which', 'whereis', 'file', 'stat', 'wc', 'sort', 'uniq', 'awk', 'sed', 'cut', 'tr', 'tee']
            };
            
            for (const [category, cmds] of Object.entries(categories)) {
                const available = cmds.filter(c => data.commands.includes(c));
                if (available.length > 0) {
                    appendTerminalLine(`\n${category}: ${available.join(', ')}`, 'terminal-stdout');
                }
            }
            
            appendTerminalLine(I18n.t('meeting.terminal_sudo_note', {}, 'Note: Use "sudo" before a command for root privileges.'), 'terminal-info');
        } else {
            appendTerminalLine(I18n.t('meeting.terminal_allowed_error', {}, 'Error loading commands.'), 'terminal-error');
        }
    } catch (error) {
        appendTerminalLine(I18n.t('meeting.error_with_message', { error: error.message }, `Error: ${error.message}`), 'terminal-error');
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
    window.loadMeetingServices = loadMeetingServices;
    window.loadSshKeysStatus = loadSshKeysStatus;
    window.ensureSshKeysConfigured = ensureSshKeysConfigured;
    window.loadDeviceSshKey = loadDeviceSshKey;
    window.generateDeviceSshKey = generateDeviceSshKey;
    window.publishDeviceSshKey = publishDeviceSshKey;
    window.syncSshHostkey = syncSshHostkey;
    window.fullSshSetup = fullSshSetup;
    window.loadTunnelAgentStatus = loadTunnelAgentStatus;
    window.startTunnelAgent = startTunnelAgent;
    window.stopTunnelAgent = stopTunnelAgent;
    window.toggleTunnelAgentAutostart = toggleTunnelAgentAutostart;
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











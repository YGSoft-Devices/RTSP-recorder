/**
 * RTSP Recorder Web Manager - Home status and service controls
 * Version: 2.33.02
 */
(function () {
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
            updateHomeServiceStatus('home-recording-status', recordingEnabled, recordingEnabled ? 'Activ?' : 'D?sactiv?');
            
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
                updateHomeServiceStatus('home-meeting-status', connected, connected ? 'Connect?' : (configured ? 'D?connect?' : 'Non configur?'));
            }
            
        } catch (error) {
            console.error('Error loading home status:', error);
        }
    }
    
    function updateHomeServiceStatus(elementId, isActive, customText = null) {
        const badge = document.getElementById(elementId);
        if (!badge) return;
        
        badge.className = 'status-badge ' + (isActive ? 'active' : 'inactive');
        const text = badge.querySelector('span:last-child');
        if (text) {
            text.textContent = customText || (isActive ? 'Actif' : 'Inactif');
        }
    }
    
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
    
    async function controlService(action) {
        return controlServiceAction(action, 'rpi-av-rtsp-recorder');
    }
    
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
                window.showToast(`${serviceLabel}: ${action} en cours... La page va se recharger.`, 'warning');
            } else {
                window.showToast(`${serviceLabel}: ${action} en cours...`, 'info');
            }
            
            const response = await fetch(`/api/service/${serviceName}/${action}`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                if (data.self_restart || isSelfRestart) {
                    // Wait for service to restart then reload page
                    window.showToast(`${serviceLabel}: red?marrage en cours...`, 'warning');
                    setTimeout(() => {
                        window.showToast('Rechargement de la page...', 'info');
                        setTimeout(() => location.reload(), 1000);
                    }, 3000);
                } else {
                    window.showToast(`${serviceLabel}: ${action} effectu?`, 'success');
                    updateStatus();
                    loadHomeStatus();
                }
            } else {
                window.showToast(`Erreur: ${data.message || data.error}`, 'error');
            }
        } catch (error) {
            // If it's a self-restart, the error is expected (connection lost)
            if (serviceName === 'rpi-cam-webmanager') {
                window.showToast('Service red?marr?, rechargement...', 'warning');
                setTimeout(() => location.reload(), 3000);
            } else {
                window.showToast(`Erreur: ${error.message}`, 'error');
            }
        }
    }
    
    window.loadHomeStatus = loadHomeStatus;
    window.updateHomeServiceStatus = updateHomeServiceStatus;
    window.updateStatus = updateStatus;
    window.controlService = controlService;
    window.controlServiceAction = controlServiceAction;
})();











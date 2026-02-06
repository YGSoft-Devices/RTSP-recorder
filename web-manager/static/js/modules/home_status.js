/**
 * RTSP Recorder Web Manager - Home status and service controls
 * Version: 2.36.08
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
            updateHomeServiceStatus(
                'home-recording-status',
                recordingEnabled,
                recordingEnabled
                    ? I18n.t('common.enabled', {}, 'Enabled')
                    : I18n.t('common.disabled', {}, 'Disabled')
            );
            
            // Load ONVIF status
            const onvifResponse = await fetch('/api/onvif/status');
            const onvifData = await onvifResponse.json();
            if (onvifData.success) {
                updateHomeServiceStatus('home-onvif-status', onvifData.running);
                
                // Update device name
                const deviceNameEl = document.getElementById('home-device-name');
                if (deviceNameEl) {
                    deviceNameEl.textContent = onvifData.config?.name || I18n.t('common.unprovisioned', {}, 'UNPROVISIONED');
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
                updateHomeServiceStatus(
                    'home-meeting-status',
                    connected,
                    connected
                        ? I18n.t('common.connected', {}, 'Connected')
                        : (configured
                            ? I18n.t('common.disconnected', {}, 'Disconnected')
                            : I18n.t('common.not_configured', {}, 'Not configured'))
                );
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
            text.textContent = customText || (isActive
                ? I18n.t('common.active', {}, 'Active')
                : I18n.t('common.inactive', {}, 'Inactive'));
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
                const statusKey = `common.${data.status}`;
                text.textContent = I18n.t(statusKey, {}, data.status);
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
                'rpi-av-rtsp-recorder': I18n.t('services.rtsp_streaming', {}, 'RTSP Streaming'),
                'rtsp-watchdog': I18n.t('services.watchdog', {}, 'Watchdog'),
                'rpi-cam-onvif': I18n.t('services.onvif', {}, 'ONVIF'),
                'rpi-cam-webmanager': I18n.t('services.web_manager', {}, 'Web Manager')
            }[serviceName] || serviceName;

            const actionLabel = I18n.t(`common.${action}`, {}, action);
            
            // Special case: self-restart warning
            const isSelfRestart = serviceName === 'rpi-cam-webmanager' && (action === 'restart' || action === 'stop');
            
            if (isSelfRestart) {
                window.showToast(
                    I18n.t('home.service_action_in_progress_reload', {
                        service: serviceLabel,
                        action: actionLabel
                    }, `${serviceLabel}: ${actionLabel} in progress... The page will reload.`),
                    'warning'
                );
            } else {
                window.showToast(
                    I18n.t('home.service_action_in_progress', {
                        service: serviceLabel,
                        action: actionLabel
                    }, `${serviceLabel}: ${actionLabel} in progress...`),
                    'info'
                );
            }
            
            const response = await fetch(`/api/service/${serviceName}/${action}`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                if (data.self_restart || isSelfRestart) {
                    // Wait for service to restart then reload page
                    window.showToast(
                        I18n.t('home.service_restart_in_progress', {
                            service: serviceLabel
                        }, `${serviceLabel}: restarting...`),
                        'warning'
                    );
                    setTimeout(() => {
                        window.showToast(I18n.t('home.page_reload', {}, 'Reloading the page...'), 'info');
                        setTimeout(() => location.reload(), 1000);
                    }, 3000);
                } else {
                    window.showToast(
                        I18n.t('home.service_action_done', {
                            service: serviceLabel,
                            action: actionLabel
                        }, `${serviceLabel}: ${actionLabel} done`),
                        'success'
                    );
                    updateStatus();
                    loadHomeStatus();
                }
            } else {
                window.showToast(
                    I18n.t('home.service_error', {
                        error: data.message || data.error
                    }, `Error: ${data.message || data.error}`),
                    'error'
                );
            }
        } catch (error) {
            // If it's a self-restart, the error is expected (connection lost)
            if (serviceName === 'rpi-cam-webmanager') {
                window.showToast(I18n.t('home.service_restarted_reload', {}, 'Service restarted, reloading...'), 'warning');
                setTimeout(() => location.reload(), 3000);
            } else {
                window.showToast(
                    I18n.t('home.service_error', { error: error.message }, `Error: ${error.message}`),
                    'error'
                );
            }
        }
    }
    
    window.loadHomeStatus = loadHomeStatus;
    window.updateHomeServiceStatus = updateHomeServiceStatus;
    window.updateStatus = updateStatus;
    window.controlService = controlService;
    window.controlServiceAction = controlServiceAction;
})();











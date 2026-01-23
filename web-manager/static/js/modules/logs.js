/**
 * RTSP Recorder Web Manager - Logs functions
 * Version: 2.33.06
 */
(function () {
    const t = window.t || function (key) { return key; };
    let logsEventSource = null;
    window.isLiveLogsActive = false;
    
    async function loadLogs() {
        try {
            const source = document.getElementById('logs-source')?.value || 'all';
            const lines = document.getElementById('logs-lines')?.value || 100;
            
            updateLogsStatus(t('ui.logs.loading'));
            
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
    
                logsContent.textContent = logsText || t('ui.logs.none_available');
                logsContent.scrollTop = logsContent.scrollHeight;
                updateLogsStatus(t('ui.logs.updated_at', { time: new Date().toLocaleTimeString() }));
            } else {
                logsContent.textContent = t('ui.logs.load_error');
                updateLogsStatus(t('ui.errors.generic'));
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            updateLogsStatus(t('ui.logs.connection_error'));
        }
    }
    
    function toggleLiveLogs() {
        if (window.isLiveLogsActive) {
            stopLiveLogs();
        } else {
            startLiveLogs();
        }
    }
    
    function startLiveLogs() {
        if (logsEventSource) {
            logsEventSource.close();
        }
        
        const logsContent = document.getElementById('logs-content');
        logsContent.textContent = `${t('ui.logs.live_header')}\n${t('ui.logs.live_connecting')}\n\n`;
        
        logsEventSource = new EventSource('/api/logs/stream');
        window.isLiveLogsActive = true;
        
        // Update UI
        const btn = document.getElementById('btn-live-logs');
        btn.innerHTML = `<i class="fas fa-stop"></i> ${t('ui.actions.stop')}`;
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-danger');
        
        document.getElementById('live-indicator').style.display = 'flex';
        updateLogsStatus(t('ui.logs.live_status'));
        
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
                    logsContent.textContent += `${t('ui.logs.error_prefix')} ${data.error}\n`;
                }
            } catch (e) {
                // Ignore parse errors for heartbeats
            }
        };
        
        logsEventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            logsContent.textContent += `\n${t('ui.logs.connection_lost')}\n`;
            updateLogsStatus(t('ui.logs.reconnecting'));
        };
        
        window.showToast(t('ui.logs.live_enabled'), 'success');
    }
    
    function stopLiveLogs() {
        if (logsEventSource) {
            logsEventSource.close();
            logsEventSource = null;
        }
        window.isLiveLogsActive = false;
        
        // Update UI
        const btn = document.getElementById('btn-live-logs');
        btn.innerHTML = `<i class="fas fa-play"></i> ${t('ui.logs.live_button')}`;
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-primary');
        
        document.getElementById('live-indicator').style.display = 'none';
        updateLogsStatus(t('ui.logs.live_stopped'));
        
        const logsContent = document.getElementById('logs-content');
        logsContent.textContent += `\n\n${t('ui.logs.stream_stopped')}\n`;
        
        window.showToast(t('ui.logs.live_disabled'), 'info');
    }
    
    function clearLogsDisplay() {
        const logsContent = document.getElementById('logs-content');
        logsContent.textContent = '';
        updateLogsStatus(t('ui.logs.display_cleared'));
    }
    
    async function cleanServerLogs() {
        if (!confirm(t('ui.logs.clean_confirm'))) {
            return;
        }
        
        try {
            window.showToast(t('ui.logs.cleaning'), 'info');
            
            const response = await fetch('/api/logs/clean', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                window.showToast(data.message, 'success');
                // Reload logs to show the cleaned state
                loadLogs();
            } else {
                window.showToast(data.message || t('ui.logs.clean_error'), 'error');
            }
        } catch (error) {
            console.error('Error cleaning logs:', error);
            window.showToast(t('ui.logs.clean_error'), 'error');
        }
    }
    
    function updateLogsStatus(text) {
        const statusText = document.getElementById('logs-status-text');
        if (statusText) {
            statusText.textContent = text;
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
    
    window.loadLogs = loadLogs;
    window.toggleLiveLogs = toggleLiveLogs;
    window.startLiveLogs = startLiveLogs;
    window.stopLiveLogs = stopLiveLogs;
    window.clearLogsDisplay = clearLogsDisplay;
    window.cleanServerLogs = cleanServerLogs;
    window.updateLogsStatus = updateLogsStatus;
    window.formatLogEntries = formatLogEntries;
})();











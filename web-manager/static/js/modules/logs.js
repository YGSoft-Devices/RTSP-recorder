/**
 * RTSP Recorder Web Manager - Logs functions
 * Version: 2.33.06
 */
(function () {
    let logsEventSource = null;
    window.isLiveLogsActive = false;
    
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
                updateLogsStatus(`Derni?re mise ? jour: ${new Date().toLocaleTimeString()}`);
            } else {
                logsContent.textContent = 'Erreur lors du chargement des logs';
                updateLogsStatus('Erreur');
            }
        } catch (error) {
            console.error('Error loading logs:', error);
            updateLogsStatus('Erreur de connexion');
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
        logsContent.textContent = '=== Logs en direct ===\nConnexion au flux de logs...\n\n';
        
        logsEventSource = new EventSource('/api/logs/stream');
        window.isLiveLogsActive = true;
        
        // Update UI
        const btn = document.getElementById('btn-live-logs');
        btn.innerHTML = '<i class="fas fa-stop"></i> Arr?ter';
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
        
        window.showToast('Logs en direct activ?s', 'success');
    }
    
    function stopLiveLogs() {
        if (logsEventSource) {
            logsEventSource.close();
            logsEventSource = null;
        }
        window.isLiveLogsActive = false;
        
        // Update UI
        const btn = document.getElementById('btn-live-logs');
        btn.innerHTML = '<i class="fas fa-play"></i> Logs en direct';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-primary');
        
        document.getElementById('live-indicator').style.display = 'none';
        updateLogsStatus('Streaming arr?t?');
        
        const logsContent = document.getElementById('logs-content');
        logsContent.textContent += '\n\n=== Streaming arr?t? ===\n';
        
        window.showToast('Logs en direct d?sactiv?s', 'info');
    }
    
    function clearLogsDisplay() {
        const logsContent = document.getElementById('logs-content');
        logsContent.textContent = '';
        updateLogsStatus('Affichage effac?');
    }
    
    async function cleanServerLogs() {
        if (!confirm('Voulez-vous vraiment nettoyer les fichiers de logs sur le serveur ?\n\nCette action va :\n- Tronquer le fichier log principal (garder 100 derni?res lignes)\n- Supprimer les logs GStreamer\n- Supprimer les vieux fichiers de log (> 7 jours)\n- Vider le cache journald')) {
            return;
        }
        
        try {
            window.showToast('Nettoyage des logs en cours...', 'info');
            
            const response = await fetch('/api/logs/clean', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                window.showToast(data.message, 'success');
                // Reload logs to show the cleaned state
                loadLogs();
            } else {
                window.showToast(data.message || 'Erreur lors du nettoyage', 'error');
            }
        } catch (error) {
            console.error('Error cleaning logs:', error);
            window.showToast('Erreur lors du nettoyage des logs', 'error');
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











/**
 * RTSP Recorder Web Manager - Navigation and tab helpers
 * Version: 2.32.95
 */
(function () {
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
    
    function updateUrlHash(tabId) {
        // Only update if not on home tab
        if (tabId && tabId !== 'home') {
            history.replaceState(null, '', `#${tabId}`);
        } else {
            // Remove hash for home tab
            history.replaceState(null, '', window.location.pathname + window.location.search);
        }
    }
    
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
                if (tabId !== 'logs' && window.isLiveLogsActive) {
                    window.stopLiveLogs();
                }
                
                // Reload resolutions when entering video tab (in case device changed)
                if (tabId === 'video' && window.detectedResolutions && window.detectedResolutions.length === 0) {
                    window.loadResolutions();
                }
                
                // Load Meeting status when entering meeting tab
                if (tabId === 'meeting') {
                    window.loadMeetingStatus();
                }
            });
        });
    }
    
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
        if (tabId !== 'logs' && window.isLiveLogsActive) {
            window.stopLiveLogs();
        }
        
        // Load data for specific tabs
        if (tabId === 'meeting') {
            window.loadMeetingStatus();
        } else if (tabId === 'video' && window.detectedResolutions && window.detectedResolutions.length === 0) {
            window.loadResolutions();
        }
    }
    
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
    
    window.getTabFromUrl = getTabFromUrl;
    window.resolveTabAlias = resolveTabAlias;
    window.updateUrlHash = updateUrlHash;
    window.initTabs = initTabs;
    window.switchToTab = switchToTab;
    window.initRtspAuthStatus = initRtspAuthStatus;
    window.updateRtspAuthStatus = updateRtspAuthStatus;
})();





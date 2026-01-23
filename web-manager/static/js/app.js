/**
 * RTSP Recorder Web Manager - Frontend JavaScript
 * Version: 2.33.03
 */

let backupFileAction = null;
let backupSelectedFile = null;


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
 * Initialize form submission
 */

// ============================================================================











/**
 * RTSP Recorder Web Manager - Utility functions
 * Version: 2.34.00
 */
(function () {
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    window.escapeHtml = escapeHtml;
})();











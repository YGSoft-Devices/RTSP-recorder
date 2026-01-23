/**
 * RTSP Recorder Web Manager - UI utilities
 * Version: 2.33.06
 */
(function () {
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        toast.innerHTML = `<i class="fas ${icons[type]}"></i> ${message}`;
        container.appendChild(toast);

        // Remove after 4 seconds
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function copyRtspUrl() {
        const url = document.getElementById('rtsp-url').textContent;
        navigator.clipboard.writeText(url).then(() => {
            showToast('URL RTSP copi?e !', 'success');
        }).catch(() => {
            showToast('Erreur lors de la copie', 'error');
        });
    }

    function copyToClipboard(text) {
        // Modern API (HTTPS only)
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                showToast('Copi? !', 'success');
            }).catch(() => {
                fallbackCopyToClipboard(text);
            });
        } else {
            // Fallback for HTTP
            fallbackCopyToClipboard(text);
        }
    }

    function fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        textArea.style.top = '-9999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                showToast('Copi? !', 'success');
            } else {
                showToast('Erreur lors de la copie', 'error');
            }
        } catch (err) {
            showToast('Erreur lors de la copie', 'error');
        }
        
        document.body.removeChild(textArea);
    }

    function copyOnvifUrl() {
        const urlEl = document.getElementById('onvif-url-display');
        if (urlEl) {
            copyToClipboard(urlEl.textContent);
        }
    }

    window.showToast = showToast;
    window.copyRtspUrl = copyRtspUrl;
    window.copyToClipboard = copyToClipboard;
    window.fallbackCopyToClipboard = fallbackCopyToClipboard;
    window.copyOnvifUrl = copyOnvifUrl;
})();











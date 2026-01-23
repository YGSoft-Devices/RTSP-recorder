/**
 * RTSP-Full ESP32 Web UI
 * Version: 0.1.2
 */

async function apiGet(path) {
    const res = await fetch(path, { cache: 'no-store' });
    if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
    return res.json();
}

async function apiPost(path, payload) {
    const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
    });
    if (!res.ok) throw new Error(`POST ${path} failed (${res.status})`);
    return res.json();
}

function $(id) {
    return document.getElementById(id);
}

function setBadge(ok, text) {
    const dot = $('statusDot');
    const label = $('statusText');
    dot.className = `status-dot ${ok ? 'active' : 'inactive'}`;
    label.textContent = text;
}

function setActiveTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach((el) => {
        el.classList.toggle('active', el.id === `tab-${tabId}`);
    });
}

function computeStreamUrl(status) {
    const ip = status && status.ip ? status.ip : window.location.host;
    const origin = `${window.location.protocol}//${ip}`;
    return `${origin}/stream`;
}

async function copyToClipboard(text) {
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch (_) {
        // fallback below
    }

    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-1000px';
    ta.style.top = '-1000px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
        document.execCommand('copy');
        return true;
    } catch (_) {
        return false;
    } finally {
        document.body.removeChild(ta);
    }
}

function setFormFromConfig(cfg) {
    $('ssid').value = (cfg.wifi && cfg.wifi.ssid) ? cfg.wifi.ssid : '';
    $('password').value = '';

    const cam = cfg.camera || {};
    if (typeof cam.frame_size === 'number') $('frameSize').value = String(cam.frame_size);
    if (typeof cam.jpeg_quality === 'number') $('jpegQuality').value = String(cam.jpeg_quality);
    if (typeof cam.brightness === 'number') $('brightness').value = String(cam.brightness);
    if (typeof cam.contrast === 'number') $('contrast').value = String(cam.contrast);
    if (typeof cam.saturation === 'number') $('saturation').value = String(cam.saturation);
    $('vflip').checked = !!cam.vflip;
    $('hmirror').checked = !!cam.hmirror;

    const meeting = cfg.meeting || {};
    $('meetingEnabled').checked = !!meeting.enabled;
    if (typeof meeting.heartbeat_interval === 'number') $('meetingInterval').value = String(meeting.heartbeat_interval);
    $('meetingApiUrl').value = meeting.api_url || '';
    $('meetingDeviceKey').value = meeting.device_key || '';
}

function cameraPayloadFromForm() {
    return {
        camera: {
            frame_size: parseInt($('frameSize').value, 10),
            jpeg_quality: parseInt($('jpegQuality').value, 10),
            brightness: parseInt($('brightness').value, 10),
            contrast: parseInt($('contrast').value, 10),
            saturation: parseInt($('saturation').value, 10),
            vflip: $('vflip').checked,
            hmirror: $('hmirror').checked
        }
    };
}

function wifiPayloadFromForm() {
    const ssid = $('ssid').value.trim();
    const password = $('password').value;
    return { wifi: { ssid, password } };
}

function meetingPayloadFromForm() {
    return {
        meeting: {
            enabled: $('meetingEnabled').checked,
            api_url: $('meetingApiUrl').value.trim(),
            device_key: $('meetingDeviceKey').value.trim(),
            heartbeat_interval: parseInt($('meetingInterval').value, 10)
        }
    };
}

function renderSystem(status) {
    const details = $('systemDetails');
    const metrics = $('systemMetrics');

    const parts = [];
    parts.push(`IP: ${status.ip || 'N/A'}`);
    parts.push(`WiFi: ${status.wifi_mode || 'N/A'}`);
    if (status.mac) parts.push(`MAC: ${status.mac}`);
    details.textContent = parts.join(' • ');

    const metricItems = [
        `Heap: ${status.free_heap ?? 'N/A'}`,
        `PSRAM: ${status.psram ? 'yes' : 'no'}`,
        `RSSI: ${status.rssi ?? 'N/A'}`,
        `Sensor: ${status.sensor || 'N/A'}`
    ];
    metrics.innerHTML = metricItems.map((t) => `<div class="metric">${t}</div>`).join('');

    const streamUrl = computeStreamUrl(status);
    const streamEl = $('streamUrl');
    streamEl.textContent = streamUrl;
    streamEl.title = streamUrl;
}

function renderMeeting(status) {
    const el = $('meetingHint');
    if (!el) return;
    const mt = (status && status.meeting) ? status.meeting : null;
    if (!mt) {
        el.textContent = 'Meeting: non disponible.';
        return;
    }
    const ago = typeof mt.last_heartbeat_ago_ms === 'number' && mt.last_heartbeat_ago_ms > 0
        ? `${Math.floor(mt.last_heartbeat_ago_ms / 1000)}s`
        : 'N/A';
    const err = mt.last_error ? ` • erreur: ${mt.last_error}` : '';
    el.textContent = `Meeting: ${mt.enabled ? 'ON' : 'OFF'} • configured: ${mt.configured ? 'yes' : 'no'} • connected: ${mt.connected ? 'yes' : 'no'} • last: ${ago}${err}`;
}

async function refreshAll() {
    const [status, cfg] = await Promise.all([
        apiGet('/api/status'),
        apiGet('/api/config')
    ]);

    setBadge(!!status.camera_ready, status.camera_ready ? `OK (${status.sensor})` : 'Caméra indisponible');
    $('subheader').textContent = `Version: ${status.version} • Heap: ${status.free_heap} • RSSI: ${status.rssi}`;
    $('statusJson').textContent = JSON.stringify(status, null, 2);
    setFormFromConfig(cfg);
    renderSystem(status);
    renderMeeting(status);
}

function reloadStream() {
    const img = $('stream');
    const base = '/stream';
    img.src = `${base}?t=${Date.now()}`;
}

async function onSaveCamera() {
    const res = await apiPost('/api/config', cameraPayloadFromForm());
    reloadStream();
    await refreshAll();
    return res;
}

async function onSaveWifi() {
    const res = await apiPost('/api/config', wifiPayloadFromForm());
    await refreshAll();
    return res;
}

async function onSaveMeeting() {
    const res = await apiPost('/api/config', meetingPayloadFromForm());
    await refreshAll();
    return res;
}

async function onMeetingHeartbeatNow() {
    return apiPost('/api/meeting/heartbeat', {});
}

async function onReboot() {
    await apiPost('/api/reboot', {});
}

async function onFactoryReset() {
    await apiPost('/api/factory_reset', {});
}

function wireUi() {
    // Tabs
    document.querySelectorAll('.tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => setActiveTab(btn.dataset.tab));
    });

    // Actions (top)
    $('btnReload').addEventListener('click', async () => {
        reloadStream();
        await refreshAll();
    });
    $('btnReloadStream').addEventListener('click', reloadStream);

    $('btnSaveCamera').addEventListener('click', async () => {
        try { await onSaveCamera(); } catch (e) { alert(String(e)); }
    });
    $('btnSaveWifi').addEventListener('click', async () => {
        try {
            const res = await onSaveWifi();
            if (res && res.note) alert(res.note);
        } catch (e) { alert(String(e)); }
    });

    $('btnSaveMeeting').addEventListener('click', async () => {
        try {
            const res = await onSaveMeeting();
            if (res && res.note) alert(res.note);
        } catch (e) { alert(String(e)); }
    });

    $('btnMeetingHeartbeat').addEventListener('click', async () => {
        try {
            const res = await onMeetingHeartbeatNow();
            if (res && res.meeting && res.meeting.last_error) alert(res.meeting.last_error);
            await refreshAll();
        } catch (e) { alert(String(e)); }
    });
    $('btnReboot').addEventListener('click', async () => {
        if (!confirm('Reboot ?')) return;
        try { await onReboot(); } catch (e) { alert(String(e)); }
    });
    $('btnFactory').addEventListener('click', async () => {
        if (!confirm('Reset WiFi (efface SSID/mot de passe) puis reboot ?')) return;
        try { await onFactoryReset(); } catch (e) { alert(String(e)); }
    });

    $('btnCopyStream').addEventListener('click', async () => {
        const url = $('streamUrl').textContent || '';
        const ok = await copyToClipboard(url);
        if (!ok) alert('Impossible de copier.');
    });
    $('btnOpenStream').addEventListener('click', () => {
        const url = $('streamUrl').textContent || '/stream';
        window.open(url, '_blank');
    });
}

async function main() {
    wireUi();
    setActiveTab('home');
    try {
        await refreshAll();
        setInterval(refreshAll, 5000);
    } catch (e) {
        setBadge(false, 'Erreur API');
        $('statusJson').textContent = String(e);
    }
}

document.addEventListener('DOMContentLoaded', main);

/**
 * RTSP Recorder Web Manager - Updates (repo + file)
 * Version: 2.33.06
 */

const CURRENT_VERSION = (window.APP_VERSION || '').replace(/^v/, '') || '0.0.0';
let repoUpdateAvailable = false;
const t = window.t || function (key) { return key; };

let updateFileSelected = null;
let updateFilePolling = null;
let updateFilePollFailures = 0;

function updateRepoApplyState() {
    const applyBtn = document.getElementById('update-repo-apply-btn');
    const forceCheckbox = document.getElementById('update-repo-force');
    const forceEnabled = forceCheckbox ? forceCheckbox.checked : false;

    if (applyBtn) {
        applyBtn.disabled = !(repoUpdateAvailable || forceEnabled);
    }
}

function updateRepoStatus(text, state = null) {
    const statusEl = document.getElementById('update-repo-status-text');
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = 'status-value';
    if (state) statusEl.classList.add(state);
    setUpdateStatusSpinner('update-repo-status-spinner', state);
}

function updateRepoLog(text) {
    const log = document.getElementById('update-repo-log');
    const pre = log?.querySelector('pre');
    if (!log || !pre) return;
    if (text) {
        log.style.display = 'block';
        pre.textContent = text;
    } else {
        log.style.display = 'none';
        pre.textContent = '';
    }
}

function setRepoVersionFields(currentVersion, latestVersion) {
    const currentEl = document.getElementById('update-repo-current-version');
    const latestEl = document.getElementById('update-repo-latest-version');
    if (currentEl) currentEl.textContent = currentVersion ? `v${currentVersion}` : '-';
    if (latestEl) latestEl.textContent = latestVersion ? `v${latestVersion}` : '-';
}

function setMainVersionFields(currentVersion, latestVersion, updateAvailable) {
    const currentEl = document.getElementById('current-version');
    const latestEl = document.getElementById('latest-version');

    if (currentEl && currentVersion) {
        currentEl.textContent = `v${currentVersion}`;
    }
    if (latestEl) {
        latestEl.className = 'version';
        if (latestVersion) {
            latestEl.textContent = `v${latestVersion}`;
            if (updateAvailable) {
                latestEl.classList.add('new-available');
            } else {
                latestEl.classList.add('up-to-date');
                latestEl.textContent += ` ${t('ui.updates.version_suffix_uptodate')}`;
            }
        } else {
            latestEl.textContent = t('ui.updates.not_available');
        }
    }
}

async function checkUpdateRepo() {
    const latestVersionEl = document.getElementById('latest-version');
    if (latestVersionEl) {
        latestVersionEl.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('ui.updates.checking')}`;
        latestVersionEl.className = 'version';
    }

    repoUpdateAvailable = false;
    updateRepoApplyState();
    updateRepoStatus(t('ui.updates.checking_in_progress'), 'checking');
    updateRepoLog('');

    try {
        const response = await fetch('/api/system/update/check');
        const data = await response.json();

        if (data.success) {
            const currentVersion = data.current_version || CURRENT_VERSION;
            const latestVersion = data.latest_version || currentVersion;
            repoUpdateAvailable = data.update_available === true;
            setMainVersionFields(currentVersion, latestVersion, repoUpdateAvailable);
            setRepoVersionFields(currentVersion, latestVersion);
            updateRepoStatus(t(repoUpdateAvailable ? 'ui.updates.available' : 'ui.updates.up_to_date'), 'success');
            updateRepoApplyState();
            if (repoUpdateAvailable) {
                showToast(t('ui.updates.available_toast', { version: `v${latestVersion}` }), 'info');
            }
        } else {
            setMainVersionFields(CURRENT_VERSION, null, false);
            setRepoVersionFields(CURRENT_VERSION, null);
            updateRepoStatus(data.message || t('ui.errors.generic'), 'error');
            updateRepoApplyState();
            showToast(t('ui.errors.with_message', { message: data.message }), 'error');
        }
    } catch (error) {
        setMainVersionFields(CURRENT_VERSION, null, false);
        setRepoVersionFields(CURRENT_VERSION, null);
        updateRepoStatus(t('ui.errors.with_message', { message: error.message }), 'error');
        updateRepoApplyState();
        console.error('Error checking updates:', error);
    }
}

function openUpdateRepoModal() {
    const modal = document.getElementById('update-repo-modal');
    if (!modal) return;

    const forceCheckbox = document.getElementById('update-repo-force');
    if (forceCheckbox) forceCheckbox.checked = false;
    const resetCheckbox = document.getElementById('update-repo-reset');
    if (resetCheckbox) resetCheckbox.checked = false;

    updateRepoStatus(t('ui.updates.checking_in_progress'), 'checking');
    updateRepoLog('');
    setRepoVersionFields(CURRENT_VERSION, null);
    updateRepoApplyState();

    modal.style.display = 'flex';
    checkUpdateRepo();
}

function closeUpdateRepoModal() {
    const modal = document.getElementById('update-repo-modal');
    if (modal) modal.style.display = 'none';
}

async function applyUpdateRepo() {
    const forceCheckbox = document.getElementById('update-repo-force');
    const resetCheckbox = document.getElementById('update-repo-reset');
    const forceEnabled = forceCheckbox ? forceCheckbox.checked : false;
    const resetSettings = resetCheckbox ? resetCheckbox.checked : false;

    if (!repoUpdateAvailable && !forceEnabled) {
        updateRepoStatus(t('ui.updates.same_version_force_required'), 'error');
        updateRepoLog(t('ui.updates.force_reinstall_prompt'));
        return;
    }

    if (!confirm(t('ui.updates.confirm_repo_update'))) {
        return;
    }

    const applyBtn = document.getElementById('update-repo-apply-btn');
    if (applyBtn) applyBtn.disabled = true;
    updateRepoStatus(t('ui.updates.applying'), 'running');
    updateRepoLog('');

    try {
        const response = await fetch('/api/system/update/perform', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                force: forceEnabled,
                reset_settings: resetSettings
            })
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || t('ui.updates.failed');
            updateRepoStatus(message, 'error');
            updateRepoLog(message);
            updateRepoApplyState();
            return;
        }

        updateRepoStatus(t('ui.updates.applied_restart'), 'success');
        updateRepoLog(data.message || t('ui.updates.finished'));
        showToast(t('ui.updates.success_restart'), 'success');

        setTimeout(() => {
            window.location.reload();
        }, 5000);
    } catch (error) {
        updateRepoStatus(t('ui.errors.with_message', { message: error.message }), 'error');
        updateRepoLog(error.message);
        updateRepoApplyState();
    }
}

// ============================================================================
// Update from file
// ============================================================================

function openUpdateFilePicker() {
    const input = document.getElementById('update-file-input');
    if (!input) {
        showToast(t('ui.updates.file_field_missing'), 'error');
        return;
    }
    input.value = '';
    input.click();
}

function handleUpdateFileSelected(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    updateFileSelected = file;
    showUpdateFileModal();
    checkUpdateFile(file);
}

function showUpdateFileModal() {
    const modal = document.getElementById('update-file-modal');
    if (!modal) return;

    document.getElementById('update-file-name').textContent = updateFileSelected?.name || '-';
    document.getElementById('update-current-version').textContent = document.getElementById('current-version')?.textContent || '-';
    document.getElementById('update-new-version').textContent = '-';
    const forceCheckbox = document.getElementById('update-file-force');
    if (forceCheckbox) forceCheckbox.checked = false;
    const resetCheckbox = document.getElementById('update-file-reset');
    if (resetCheckbox) resetCheckbox.checked = false;
    const depsGroup = document.getElementById('update-file-deps-group');
    if (depsGroup) depsGroup.style.display = 'none';
    const depsInfo = document.getElementById('update-file-deps-info');
    if (depsInfo) depsInfo.textContent = '';
    updateUpdateFileStatus(t('ui.updates.checking_in_progress'), 'checking');
    updateUpdateFileLog('');

    const applyBtn = document.getElementById('update-file-apply-btn');
    if (applyBtn) applyBtn.disabled = true;

    modal.style.display = 'flex';
}

function closeUpdateFileModal() {
    const modal = document.getElementById('update-file-modal');
    if (modal) modal.style.display = 'none';
    if (updateFilePolling) {
        clearInterval(updateFilePolling);
        updateFilePolling = null;
    }
    updateFilePollFailures = 0;
}

function updateUpdateFileStatus(text, state = null) {
    const statusEl = document.getElementById('update-file-status-text');
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.className = 'status-value';
    if (state) statusEl.classList.add(state);
    setUpdateStatusSpinner('update-file-status-spinner', state);
}

function setUpdateStatusSpinner(spinnerId, state) {
    const spinner = document.getElementById(spinnerId);
    if (!spinner) return;
    const spinningStates = ['checking', 'running', 'dependencies', 'applying', 'rebooting', 'restarting'];
    spinner.style.display = state && spinningStates.includes(state) ? 'inline-flex' : 'none';
}

function updateUpdateFileLog(text) {
    const log = document.getElementById('update-file-log');
    const pre = log?.querySelector('pre');
    if (!log || !pre) return;
    if (text) {
        log.style.display = 'block';
        pre.textContent = text;
    } else {
        log.style.display = 'none';
        pre.textContent = '';
    }
}

function onUpdateFileForceChanged() {
    if (updateFileSelected) {
        checkUpdateFile(updateFileSelected);
    }
}

async function checkUpdateFile(file) {
    updateUpdateFileStatus(t('ui.updates.checking_in_progress'), 'checking');
    updateUpdateFileLog('');

    try {
        const formData = new FormData();
        formData.append('update', file);
        const force = document.getElementById('update-file-force')?.checked;
        if (force) formData.append('force', '1');

        const response = await fetch('/api/system/update/file/check', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || t('ui.updates.invalid');
            updateUpdateFileStatus(message, 'error');
            updateUpdateFileLog(message);
            return;
        }

        document.getElementById('update-new-version').textContent = data.version || '-';
        if (data.requires_reboot) {
            updateUpdateFileLog(t('ui.updates.reboot_required', { version: data.version || '-' }));
        }
        const sameVersion = data.same_version === true;
        if (sameVersion && !data.reapply_allowed) {
            updateUpdateFileStatus(t('ui.updates.same_version_force_required'), 'error');
            updateUpdateFileLog(t('ui.updates.force_reapply_prompt'));
            return;
        }

        const missingApt = data.missing_apt_packages || data.missing_packages || [];
        const missingPip = data.missing_pip_packages || [];
        const depsGroup = document.getElementById('update-file-deps-group');
        const depsInfo = document.getElementById('update-file-deps-info');
        if (missingApt.length || missingPip.length) {
            if (depsGroup) depsGroup.style.display = 'block';
            const aptText = missingApt.length ? `APT: ${missingApt.join(', ')}` : '';
            const pipText = missingPip.length ? `PIP: ${missingPip.join(', ')}` : '';
            const details = [aptText, pipText].filter(Boolean).join(' | ');
            if (depsInfo) depsInfo.textContent = details;
            updateUpdateFileLog(t('ui.updates.missing_dependencies'));
        } else {
            if (depsGroup) depsGroup.style.display = 'none';
            if (depsInfo) depsInfo.textContent = '';
        }

        updateUpdateFileStatus(t('ui.updates.valid_ready'), 'success');
        updateUpdateFileLog(t('ui.updates.files_count', { count: data.files_count || 0 }));

        const applyBtn = document.getElementById('update-file-apply-btn');
        if (applyBtn) applyBtn.disabled = false;
    } catch (error) {
        updateUpdateFileStatus(t('ui.errors.with_message', { message: error.message }), 'error');
        updateUpdateFileLog(error.message);
    }
}

async function applyUpdateFile() {
    if (!updateFileSelected) {
        updateUpdateFileStatus(t('ui.updates.no_file_selected'), 'error');
        return;
    }

    if (!confirm(t('ui.updates.confirm_file_update'))) {
        return;
    }

    const applyBtn = document.getElementById('update-file-apply-btn');
    if (applyBtn) applyBtn.disabled = true;
    updateUpdateFileStatus(t('ui.updates.applying'), 'running');

    try {
        const formData = new FormData();
        formData.append('update', updateFileSelected);
        const force = document.getElementById('update-file-force')?.checked;
        if (force) formData.append('force', '1');
        const resetSettings = document.getElementById('update-file-reset')?.checked;
        if (resetSettings) formData.append('reset_settings', '1');
        formData.append('install_deps', '1');

        const response = await fetch('/api/system/update/file/apply', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!data.success) {
            const message = data.message || t('ui.updates.start_failed');
            updateUpdateFileStatus(message, 'error');
            updateUpdateFileLog(message);
            return;
        }

        updateUpdateFileStatus(t('ui.updates.started_following'), 'running');
        updateUpdateFileLog(t('ui.updates.following'));
        pollUpdateFileStatus();
    } catch (error) {
        updateUpdateFileStatus(t('ui.errors.with_message', { message: error.message }), 'error');
        updateUpdateFileLog(error.message);
    }
}

function pollUpdateFileStatus() {
    if (updateFilePolling) clearInterval(updateFilePolling);

    const fetchStatus = async () => {
        try {
            const response = await fetch('/api/system/update/file/status');
            const data = await response.json();
            updateFilePollFailures = 0;

            const state = data.state || 'idle';
            const message = data.message || t('ui.status.unknown');
            updateUpdateFileStatus(message, state === 'error' ? 'error' : (state === 'success' ? 'success' : 'running'));

            if (data.log && data.log.length) {
                updateUpdateFileLog(data.log.join('\n'));
            }

            if (state === 'success') {
                const requiresReboot = data.details?.requires_reboot === true || data.requires_reboot === true;
                if (requiresReboot) {
                    updateUpdateFileStatus(t('ui.updates.applied_rebooting'), 'success');
                    showRebootOverlay();
                    startRebootMonitoring();
                } else {
                    updateUpdateFileStatus(t('ui.updates.applied_restart'), 'success');
                    setTimeout(() => {
                        window.location.reload();
                    }, 4000);
                }
                clearInterval(updateFilePolling);
                updateFilePolling = null;
            } else if (state === 'error') {
                clearInterval(updateFilePolling);
                updateFilePolling = null;
            } else if (state === 'rebooting') {
                updateUpdateFileStatus(t('ui.updates.rebooting'), 'running');
                showRebootOverlay();
                startRebootMonitoring();
            }
        } catch (error) {
            updateFilePollFailures += 1;
            updateUpdateFileStatus(t('ui.updates.reconnecting'), 'running');
            if (updateFilePollFailures >= 5) {
                updateUpdateFileStatus(t('ui.updates.follow_error'), 'error');
                clearInterval(updateFilePolling);
                updateFilePolling = null;
            }
        }
    };

    fetchStatus();
    updateFilePolling = setInterval(fetchStatus, 2000);
}

window.checkUpdateRepo = checkUpdateRepo;
window.openUpdateRepoModal = openUpdateRepoModal;
window.closeUpdateRepoModal = closeUpdateRepoModal;
window.applyUpdateRepo = applyUpdateRepo;
window.updateRepoApplyState = updateRepoApplyState;
window.openUpdateFilePicker = openUpdateFilePicker;
window.handleUpdateFileSelected = handleUpdateFileSelected;
window.showUpdateFileModal = showUpdateFileModal;
window.closeUpdateFileModal = closeUpdateFileModal;
window.updateUpdateFileStatus = updateUpdateFileStatus;
window.updateUpdateFileLog = updateUpdateFileLog;
window.onUpdateFileForceChanged = onUpdateFileForceChanged;
window.checkUpdateFile = checkUpdateFile;
window.applyUpdateFile = applyUpdateFile;
window.pollUpdateFileStatus = pollUpdateFileStatus;











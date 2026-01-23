/**
 * RTSP Recorder Web Manager - Network and WiFi functions
 * Version: 2.32.93
 */

// WiFi Functions
// ============================================================================

/**
 * Scan for available WiFi networks
 */
async function scanWifi() {
    try {
        showToast('Scan WiFi en cours...', 'info');
        
        const response = await fetch('/api/wifi/scan');
        const data = await response.json();
        
        const listContainer = document.getElementById('wifi-list');
        
        if (data.success && data.networks.length > 0) {
            // Remove duplicates
            const uniqueNetworks = data.networks.filter((network, index, self) =>
                index === self.findIndex((n) => n.ssid === network.ssid)
            );
            
            listContainer.innerHTML = uniqueNetworks.map(net => `
                <div class="detection-item" onclick="selectWifi('${escapeHtml(net.ssid)}')">
                    <span class="device-name">
                        <i class="fas fa-wifi"></i> ${escapeHtml(net.ssid)}
                    </span>
                    <span class="wifi-details">
                        <span class="signal">${net.signal}%</span>
                        <span class="security">${net.security}</span>
                    </span>
                </div>
            `).join('');
            showToast(`${uniqueNetworks.length} réseau(x) trouvé(s)`, 'success');
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucun réseau trouvé</span></div>';
            showToast('Aucun réseau WiFi trouvé', 'warning');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Select a WiFi network from scan results
 */
function selectWifi(ssid) {
    document.getElementById('wifi_ssid').value = ssid;
    document.getElementById('wifi-list').innerHTML = '';
    document.getElementById('wifi_password').focus();
}

/**
 * Connect to WiFi network
 */
async function connectWifi(isFallback = false) {
    try {
        const ssidField = isFallback ? 'wifi_fallback_ssid' : 'wifi_ssid';
        const passField = isFallback ? 'wifi_fallback_password' : 'wifi_password';
        
        const ssid = document.getElementById(ssidField).value;
        const password = document.getElementById(passField).value;
        
        if (!ssid) {
            showToast('Veuillez entrer un SSID', 'warning');
            return;
        }
        
        showToast(`Connexion à ${ssid}...`, 'info');
        
        const response = await fetch('/api/wifi/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password, fallback: isFallback })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(isFallback ? 'Réseau de secours ajouté' : 'Connexion réussie !', 'success');
            // Clear password field for security
            document.getElementById(passField).value = '';
            // Refresh status after a delay
            setTimeout(updateStatus, 3000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Toggle password visibility
 */
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.nextElementSibling.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// ============================================================================
// Network Interface Functions
// ============================================================================

let networkInterfacesOrder = [];

/**
 * Load network interfaces and display them
 */
async function loadNetworkInterfaces() {
    try {
        const listContainer = document.getElementById('network-interfaces-list');
        listContainer.innerHTML = '<div class="loading-placeholder"><i class="fas fa-spinner fa-spin"></i> Chargement des interfaces...</div>';
        
        const response = await fetch('/api/network/interfaces');
        const data = await response.json();
        
        if (data.success && data.interfaces.length > 0) {
            networkInterfacesOrder = data.priority.length > 0 ? data.priority : data.interfaces.map(i => i.name);
            
            // Sort interfaces by priority
            const sortedInterfaces = [...data.interfaces].sort((a, b) => {
                const aIndex = networkInterfacesOrder.indexOf(a.name);
                const bIndex = networkInterfacesOrder.indexOf(b.name);
                return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
            });
            
            listContainer.innerHTML = sortedInterfaces.map((iface, index) => `
                <div class="network-interface-item ${iface.connected ? 'connected' : ''}" 
                     draggable="true" 
                     data-interface="${iface.name}"
                     ondragstart="handleDragStart(event)"
                     ondragover="handleDragOver(event)"
                     ondrop="handleDrop(event)"
                     ondragend="handleDragEnd(event)">
                    <span class="drag-handle">
                        <i class="fas fa-grip-vertical"></i>
                    </span>
                    <span class="interface-icon">
                        ${getInterfaceIcon(iface.type)}
                    </span>
                    <span class="interface-info">
                        <span class="interface-name">${iface.name}</span>
                        <span class="interface-type">${getInterfaceTypeLabel(iface.type)}</span>
                        ${iface.mac ? `<span class="interface-mac">${iface.mac}</span>` : ''}
                    </span>
                    <span class="interface-status">
                        ${iface.ip ? `<span class="interface-ip">${iface.ip}</span>` : ''}
                        <span class="status-badge ${iface.connected ? 'connected' : 'disconnected'}">${iface.connected ? 'Connecté' : 'Déconnecté'}</span>
                    </span>
                    <span class="priority-badge">#${index + 1}</span>
                </div>
            `).join('');
            
            // Update interface select dropdowns
            updateInterfaceSelects(data.interfaces);
            
            // Update header status badge - show primary connected interface
            updateNetworkHeaderStatus(sortedInterfaces);
            
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucune interface réseau trouvée</span></div>';
        }
    } catch (error) {
        console.error('Error loading interfaces:', error);
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Update the network header status badge based on interfaces
 */
function updateNetworkHeaderStatus(interfaces) {
    const indicator = document.getElementById('network-header-indicator');
    const ssidEl = document.getElementById('network-header-ssid');
    const ipEl = document.getElementById('network-header-ip');
    
    if (!indicator) return;
    
    // Find first connected interface (already sorted by priority)
    const connectedIface = interfaces.find(iface => iface.connected && iface.name !== 'lo');
    
    if (connectedIface) {
        indicator.className = 'status-indicator connected';
        indicator.textContent = 'Connecté';
        ssidEl.textContent = connectedIface.name;
        ipEl.textContent = connectedIface.ip || '';
    } else {
        indicator.className = 'status-indicator disconnected';
        indicator.textContent = 'Déconnecté';
        ssidEl.textContent = '';
        ipEl.textContent = '';
    }
}

/**
 * Get icon for interface type
 */
function getInterfaceIcon(type) {
    switch (type) {
        case 'wifi':
            return '<i class="fas fa-wifi"></i>';
        case 'ethernet':
            return '<i class="fas fa-ethernet"></i>';
        case 'loopback':
            return '<i class="fas fa-redo"></i>';
        default:
            return '<i class="fas fa-network-wired"></i>';
    }
}

/**
 * Get label for interface type
 */
function getInterfaceTypeLabel(type) {
    switch (type) {
        case 'wifi':
            return 'WiFi';
        case 'ethernet':
            return 'Ethernet';
        case 'loopback':
            return 'Loopback';
        default:
            return 'Réseau';
    }
}

/**
 * Update interface select dropdowns
 */
function updateInterfaceSelects(interfaces) {
    const networkSelect = document.getElementById('network_interface_select');
    
    // Filter out loopback
    const usableInterfaces = interfaces.filter(i => i.type !== 'loopback');
    
    // Update network interface select
    if (networkSelect) {
        networkSelect.innerHTML = '<option value="">Sélectionnez une interface...</option>' +
            usableInterfaces.map(i => {
                const mac = i.mac ? ` | ${i.mac}` : '';
                const ip = i.ip ? ` - ${i.ip}` : '';
                return `<option value="${i.name}">${i.name} (${getInterfaceTypeLabel(i.type)}${ip}${mac})</option>`;
            }).join('');
    }
}

function exportLogs() {
    const source = document.getElementById('logs-source')?.value || 'all';
    const lines = document.getElementById('logs-lines')?.value || 100;
    const url = `/api/logs/export?lines=${encodeURIComponent(lines)}&service=${encodeURIComponent(source)}`;
    const link = document.createElement('a');
    link.href = url;
    link.download = '';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('Export des logs en cours...', 'info');
}

// Drag and drop handlers
let draggedItem = null;

function handleDragStart(e) {
    draggedItem = e.target.closest('.network-interface-item');
    draggedItem.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    
    const target = e.target.closest('.network-interface-item');
    if (target && target !== draggedItem) {
        const list = document.getElementById('network-interfaces-list');
        const items = [...list.querySelectorAll('.network-interface-item')];
        const draggedIndex = items.indexOf(draggedItem);
        const targetIndex = items.indexOf(target);
        
        if (draggedIndex < targetIndex) {
            target.parentNode.insertBefore(draggedItem, target.nextSibling);
        } else {
            target.parentNode.insertBefore(draggedItem, target);
        }
    }
}

function handleDrop(e) {
    e.preventDefault();
}

function handleDragEnd(e) {
    if (draggedItem) {
        draggedItem.classList.remove('dragging');
        draggedItem = null;
        
        // Update priority badges
        const items = document.querySelectorAll('.network-interface-item');
        items.forEach((item, index) => {
            const badge = item.querySelector('.priority-badge');
            if (badge) badge.textContent = `#${index + 1}`;
        });
        
        // Update order array
        networkInterfacesOrder = [...items].map(item => item.dataset.interface);
    }
}

/**
 * Save interface priority order
 */
async function saveInterfacePriority() {
    try {
        const items = document.querySelectorAll('.network-interface-item');
        const interfacesOrder = [...items].map(item => item.dataset.interface);
        
        showToast('Application de la priorité...', 'info');
        
        const response = await fetch('/api/network/priority', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interfaces: interfacesOrder })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Priorité des interfaces mise à jour', 'success');
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Toggle network mode display
 */
function toggleNetworkMode() {
    const mode = document.querySelector('input[name="network_mode"]:checked').value;
    const staticConfig = document.getElementById('static-ip-config');
    
    if (mode === 'static') {
        staticConfig.style.display = 'block';
    } else {
        staticConfig.style.display = 'none';
    }
}

/**
 * Apply network configuration (DHCP or Static)
 */
async function applyNetworkConfig() {
    try {
        const iface = document.getElementById('network_interface_select').value;
        const mode = document.querySelector('input[name="network_mode"]:checked').value;
        
        if (!iface) {
            showToast('Veuillez sélectionner une interface', 'warning');
            return;
        }
        
        showToast(`Configuration de ${iface}...`, 'info');
        
        let response;
        
        if (mode === 'dhcp') {
            response = await fetch('/api/network/dhcp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ interface: iface })
            });
        } else {
            const ip = document.getElementById('network_static_ip').value;
            const gateway = document.getElementById('network_gateway').value;
            const dns = document.getElementById('network_dns').value;
            
            if (!ip || !gateway) {
                showToast('Veuillez remplir l\'adresse IP et la passerelle', 'warning');
                return;
            }
            
            response = await fetch('/api/network/static', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ interface: iface, ip, gateway, dns })
            });
        }
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration réseau appliquée', 'success');
            // Refresh interfaces after a delay
            setTimeout(loadNetworkInterfaces, 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

// ============================================================================
// WiFi Simple Configuration Functions (for single WiFi adapter)
// ============================================================================

/**
 * Toggle WiFi simple static IP configuration visibility
 */
function toggleWifiSimpleIpMode() {
    const mode = document.querySelector('input[name="wifi_simple_ip_mode"]:checked')?.value;
    const staticConfig = document.getElementById('wifi-simple-static-config');
    if (staticConfig) {
        staticConfig.style.display = mode === 'static' ? '' : 'none';
    }
}

/**
 * Load WiFi simple status and config
 */
async function loadWifiSimpleStatus() {
    try {
        const response = await fetch('/api/wifi/simple/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            
            // Update status banner
            const statusEl = document.getElementById('wifi-simple-status');
            if (statusEl) {
                if (status.connected) {
                    statusEl.innerHTML = `
                        <div class="wifi-status-connected">
                            <i class="fas fa-check-circle"></i>
                            <span>Connecté à <strong>${status.ssid || 'Réseau WiFi'}</strong></span>
                            <span class="wifi-ip">${status.ip || ''}</span>
                        </div>
                    `;
                } else {
                    statusEl.innerHTML = `
                        <div class="wifi-status-disconnected">
                            <i class="fas fa-times-circle"></i>
                            <span>Non connecté</span>
                        </div>
                    `;
                }
            }
            
            // Pre-fill SSID from current connection if no saved config
            const ssidField = document.getElementById('wifi_simple_ssid');
            if (ssidField) {
                // Use saved config first, or current connection as fallback
                ssidField.value = status.saved_ssid || status.ssid || '';
            }
            
            // Password placeholder
            const pwdField = document.getElementById('wifi_simple_password');
            if (pwdField) {
                pwdField.value = '';
                pwdField.placeholder = status.has_saved_password ? '•••••••• (enregistré)' : 'Mot de passe WiFi';
            }
            
            // IP Mode
            const ipMode = status.ip_mode || 'dhcp';
            const ipModeRadio = document.querySelector(`input[name="wifi_simple_ip_mode"][value="${ipMode}"]`);
            if (ipModeRadio) {
                ipModeRadio.checked = true;
                toggleWifiSimpleIpMode();
            }
            
            // Static IP fields
            if (ipMode === 'static') {
                const staticIp = document.getElementById('wifi_simple_static_ip');
                const gateway = document.getElementById('wifi_simple_gateway');
                const dns = document.getElementById('wifi_simple_dns');
                if (staticIp) staticIp.value = status.static_ip || '';
                if (gateway) gateway.value = status.gateway || '';
                if (dns) dns.value = status.dns || '8.8.8.8';
            }
        }
    } catch (error) {
        console.error('Error loading WiFi simple status:', error);
    }
}

/**
 * Save WiFi simple configuration
 */
async function saveWifiSimpleConfig() {
    const ssid = document.getElementById('wifi_simple_ssid')?.value;
    const password = document.getElementById('wifi_simple_password')?.value;
    const ipMode = document.querySelector('input[name="wifi_simple_ip_mode"]:checked')?.value || 'dhcp';
    
    if (!ssid) {
        showToast('Veuillez entrer un SSID', 'error');
        return;
    }
    
    const config = {
        ssid: ssid,
        ip_mode: ipMode
    };
    
    // Only send password if user entered one
    if (password) {
        config.password = password;
    }
    
    if (ipMode === 'static') {
        config.static_ip = document.getElementById('wifi_simple_static_ip')?.value || '';
        config.gateway = document.getElementById('wifi_simple_gateway')?.value || '';
        config.dns = document.getElementById('wifi_simple_dns')?.value || '8.8.8.8';
    }
    
    try {
        const response = await fetch('/api/wifi/simple/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration WiFi enregistrée', 'success');
            loadWifiSimpleStatus();
        } else {
            showToast(data.message || 'Erreur lors de l\'enregistrement', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Connect to WiFi with simple config
 */
async function connectWifiSimple() {
    const ssid = document.getElementById('wifi_simple_ssid')?.value;
    const password = document.getElementById('wifi_simple_password')?.value;
    
    if (!ssid) {
        showToast('Veuillez entrer un SSID', 'error');
        return;
    }
    
    try {
        showToast('Connexion en cours...', 'info');
        
        const response = await fetch('/api/wifi/simple/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || 'Connexion réussie', 'success');
            // Wait a bit then reload status
            setTimeout(() => {
                loadWifiSimpleStatus();
                loadNetworkInterfaces();
            }, 3000);
        } else {
            showToast(data.message || 'Erreur de connexion', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

// ============================================================================
// WiFi Failover Functions
// ============================================================================

/**
 * Load WiFi status and show appropriate section (simple or failover)
 */
async function loadWifiConfig() {
    try {
        const response = await fetch('/api/wifi/failover/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            const wifiInterfaces = status.wifi_interfaces || [];
            
            const simpleSection = document.getElementById('wifi-simple-section');
            const failoverSection = document.getElementById('wifi-failover-section');
            
            if (wifiInterfaces.length >= 2) {
                // 2+ WiFi adapters: show failover config
                if (simpleSection) simpleSection.style.display = 'none';
                if (failoverSection) failoverSection.style.display = '';
                loadWifiFailoverStatus();
            } else if (wifiInterfaces.length === 1) {
                // 1 WiFi adapter: show simple config
                if (simpleSection) simpleSection.style.display = '';
                if (failoverSection) failoverSection.style.display = 'none';
                loadWifiSimpleStatus();
            } else {
                // No WiFi: hide both
                if (simpleSection) simpleSection.style.display = 'none';
                if (failoverSection) failoverSection.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading WiFi config:', error);
    }
}

/**
 * Load WiFi failover status and update UI
 */
async function loadWifiFailoverStatus() {
    try {
        const response = await fetch('/api/wifi/failover/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            
            // Check if we have at least 2 WiFi interfaces for failover to make sense
            const wifiInterfaces = status.wifi_interfaces || [];
            const failoverSection = document.getElementById('wifi-failover-section');
            const simpleSection = document.getElementById('wifi-simple-section');
            
            if (wifiInterfaces.length < 2) {
                // Less than 2 adapters: show simple config instead
                if (failoverSection) failoverSection.style.display = 'none';
                if (simpleSection && wifiInterfaces.length === 1) {
                    simpleSection.style.display = '';
                    loadWifiSimpleStatus();
                }
                console.log('[WiFi] Showing simple config -', wifiInterfaces.length, 'interface(s) detected');
                return;
            }
            
            // Show failover section
            if (failoverSection) failoverSection.style.display = '';
            if (simpleSection) simpleSection.style.display = 'none';
            
            // Update hardware failover toggle
            const hwToggle = document.getElementById('wifi_hardware_failover_enabled');
            const hwToggleStatus = document.getElementById('wifi-hw-failover-status');
            if (hwToggle) {
                hwToggle.checked = status.hardware_failover_enabled !== false;
                if (hwToggleStatus) {
                    hwToggleStatus.textContent = hwToggle.checked ? 'Activé' : 'Désactivé';
                }
            }
            
            // Update network failover toggle
            const netToggle = document.getElementById('wifi_network_failover_enabled');
            const netToggleStatus = document.getElementById('wifi-net-failover-status');
            if (netToggle) {
                netToggle.checked = status.network_failover_enabled !== false;
                if (netToggleStatus) {
                    netToggleStatus.textContent = netToggle.checked ? 'Activé' : 'Désactivé';
                }
            }
            
            // Update interface selects
            const primarySelect = document.getElementById('wifi_primary_interface');
            const secondarySelect = document.getElementById('wifi_secondary_interface');
            if (primarySelect) primarySelect.value = status.primary_interface || 'wlan1';
            if (secondarySelect) secondarySelect.value = status.secondary_interface || 'wlan0';
            
            // Update primary SSID/password
            const primarySsid = document.getElementById('wifi_primary_ssid');
            if (primarySsid) primarySsid.value = status.primary_ssid || '';
            
            // Show password placeholder if password is configured (don't show actual password)
            const primaryPwd = document.getElementById('wifi_primary_password');
            if (primaryPwd) {
                primaryPwd.value = '';  // Always clear (don't expose password)
                primaryPwd.placeholder = status.has_primary_password ? '•••••••• (enregistré)' : 'Aucun mot de passe';
            }
            
            // Update secondary SSID/password
            const secondarySsid = document.getElementById('wifi_secondary_ssid');
            if (secondarySsid) secondarySsid.value = status.secondary_ssid || '';
            
            const secondaryPwd = document.getElementById('wifi_secondary_password');
            if (secondaryPwd) {
                secondaryPwd.value = '';  // Always clear
                secondaryPwd.placeholder = status.has_secondary_password ? '•••••••• (enregistré)' : 'Aucun mot de passe';
            }
            
            // Update IP mode
            const ipMode = status.ip_mode || 'dhcp';
            const ipModeRadio = document.querySelector(`input[name="wifi_failover_ip_mode"][value="${ipMode}"]`);
            if (ipModeRadio) {
                ipModeRadio.checked = true;
                toggleWifiFailoverIpMode();
            }
            
            // Update static IP fields
            if (ipMode === 'static') {
                const staticIp = document.getElementById('wifi_failover_static_ip');
                const gateway = document.getElementById('wifi_failover_gateway');
                const dns = document.getElementById('wifi_failover_dns');
                if (staticIp) staticIp.value = status.static_ip || '';
                if (gateway) gateway.value = status.gateway || '';
                if (dns) dns.value = status.dns || '8.8.8.8';
            }

            const checkIntervalInput = document.getElementById('wifi_failover_check_interval');
            if (checkIntervalInput) {
                checkIntervalInput.value = status.check_interval || 30;
            }
            
            // Update status banner
            updateWifiFailoverStatusBanner(status);
            
            // Update interfaces grid
            updateWifiInterfacesGrid(status.wifi_interfaces, status.active_interface);
        }
    } catch (error) {
        console.error('Error loading WiFi failover status:', error);
        showToast('Erreur chargement statut WiFi', 'error');
    }
}

/**
 * Update the WiFi failover status banner
 */
function updateWifiFailoverStatusBanner(status) {
    const banner = document.getElementById('wifi-failover-status');
    if (!banner) return;
    
    let html = '';
    
    if (status.active_interface) {
        const isPrimaryIface = status.active_interface === status.primary_interface;
        const isPrimarySsid = status.active_ssid === status.primary_ssid;
        
        // Determine badge and class
        let modeClass = 'primary';
        let modeLabel = 'Normal';
        let modeIcon = 'fa-check-circle';
        
        if (!isPrimaryIface && !isPrimarySsid) {
            modeClass = 'failover';
            modeLabel = 'Double Failover';
            modeIcon = 'fa-exclamation-triangle';
        } else if (!isPrimaryIface) {
            modeClass = 'failover';
            modeLabel = 'HW Failover';
            modeIcon = 'fa-microchip';
        } else if (!isPrimarySsid) {
            modeClass = 'failover';
            modeLabel = 'Net Failover';
            modeIcon = 'fa-broadcast-tower';
        }
        
        html = `
            <div class="wifi-status-banner ${modeClass}">
                <div class="wifi-status-icon">
                    <i class="fas fa-wifi"></i>
                </div>
                <div class="wifi-status-info">
                    <div class="wifi-status-main">
                        <strong>${status.active_interface}</strong> 
                        <span class="mode-badge ${modeClass}"><i class="fas ${modeIcon}"></i> ${modeLabel}</span>
                    </div>
                    <div class="wifi-status-details">
                        ${status.active_ssid ? `<span><i class="fas fa-broadcast-tower"></i> ${status.active_ssid}</span>` : ''}
                        ${status.active_ip ? `<span><i class="fas fa-network-wired"></i> ${status.active_ip}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    } else {
        html = `
            <div class="wifi-status-banner disconnected">
                <div class="wifi-status-icon">
                    <i class="fas fa-wifi-slash"></i>
                </div>
                <div class="wifi-status-info">
                    <div class="wifi-status-main">
                        <strong>WiFi Déconnecté</strong>
                    </div>
                    <div class="wifi-status-details">
                        <span>Aucune interface WiFi active</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    banner.innerHTML = html;
}

/**
 * Update the WiFi interfaces grid
 */
function updateWifiInterfacesGrid(interfaces, activeInterface) {
    const grid = document.getElementById('wifi-interfaces-grid');
    if (!grid || !interfaces) return;
    
    const html = interfaces.map(iface => {
        const isActive = iface.name === activeInterface;
        const isAvailable = iface.phy_exists;
        const statusClass = isActive ? 'active' : (isAvailable ? 'available' : 'unavailable');
        const statusLabel = isActive ? 'Actif' : (isAvailable ? 'Disponible' : 'Non détecté');
        const typeLabel = iface.is_usb ? 'USB Dongle' : 'Intégré';
        
        return `
            <div class="wifi-interface-card ${statusClass}">
                <div class="interface-header">
                    <span class="interface-name">${iface.name}</span>
                    <span class="interface-type">${typeLabel}</span>
                </div>
                <div class="interface-body">
                    <div class="interface-status">
                        <span class="status-indicator ${statusClass}"></span>
                        <span>${statusLabel}</span>
                    </div>
                    ${iface.ssid ? `<div class="interface-ssid"><i class="fas fa-broadcast-tower"></i> ${iface.ssid}</div>` : ''}
                    ${iface.ip ? `<div class="interface-ip"><i class="fas fa-network-wired"></i> ${iface.ip}</div>` : ''}
                    <div class="interface-mac"><i class="fas fa-fingerprint"></i> ${iface.mac || 'N/A'}</div>
                </div>
            </div>
        `;
    }).join('');
    
    grid.innerHTML = html || '<p class="text-muted">Aucune interface WiFi détectée</p>';
}

/**
 * Toggle WiFi failover IP mode display
 */
function toggleWifiFailoverIpMode() {
    const mode = document.querySelector('input[name="wifi_failover_ip_mode"]:checked')?.value || 'dhcp';
    const staticConfig = document.getElementById('wifi-failover-static-config');
    if (staticConfig) {
        staticConfig.style.display = mode === 'static' ? 'block' : 'none';
    }
}

/**
 * Save WiFi failover configuration
 */
async function saveWifiFailoverConfig() {
    try {
        // Debug: check if elements exist
        const elements = {
            hw_toggle: document.getElementById('wifi_hardware_failover_enabled'),
            primary_iface: document.getElementById('wifi_primary_interface'),
            secondary_iface: document.getElementById('wifi_secondary_interface'),
            net_toggle: document.getElementById('wifi_network_failover_enabled'),
            primary_ssid: document.getElementById('wifi_primary_ssid'),
            primary_pwd: document.getElementById('wifi_primary_password'),
            secondary_ssid: document.getElementById('wifi_secondary_ssid'),
            secondary_pwd: document.getElementById('wifi_secondary_password'),
            ip_mode: document.querySelector('input[name="wifi_failover_ip_mode"]:checked'),
            static_ip: document.getElementById('wifi_failover_static_ip'),
            gateway: document.getElementById('wifi_failover_gateway'),
            dns: document.getElementById('wifi_failover_dns'),
            check_interval: document.getElementById('wifi_failover_check_interval')
        };
        
        console.log('[WiFi Config] Elements found:', elements);
        
        const config = {
            // Hardware failover
            hardware_failover_enabled: elements.hw_toggle?.checked ?? true,
            primary_interface: elements.primary_iface?.value || 'wlan1',
            secondary_interface: elements.secondary_iface?.value || 'wlan0',
            
            // Network failover
            network_failover_enabled: elements.net_toggle?.checked ?? true,
            primary_ssid: elements.primary_ssid?.value || '',
            primary_password: elements.primary_pwd?.value || '',
            secondary_ssid: elements.secondary_ssid?.value || '',
            secondary_password: elements.secondary_pwd?.value || '',
            
            // IP config
            ip_mode: elements.ip_mode?.value || 'dhcp',
            static_ip: elements.static_ip?.value || '',
            gateway: elements.gateway?.value || '',
            dns: elements.dns?.value || '8.8.8.8',
            check_interval: parseInt(elements.check_interval?.value, 10) || 30
        };
        
        console.log('[WiFi Config] Saving config:', config);
        
        if (!config.primary_ssid) {
            showToast('Veuillez entrer un SSID principal', 'warning');
            return false;
        }
        
        showToast('Enregistrement...', 'info');
        
        const response = await fetch('/api/wifi/failover/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration WiFi enregistrée', 'success');
            return true;
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
            return false;
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
        return false;
    }
}

/**
 * Apply WiFi failover - connect the appropriate interface
 */
async function applyWifiFailover() {
    try {
        // First save config
        const saved = await saveWifiFailoverConfig();
        if (!saved) return;
        
        showToast('Application de la configuration WiFi...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            const result = data.result;
            
            switch (result.action) {
                case 'none':
                    showToast(result.reason, 'info');
                    break;
                case 'connected_primary':
                    showToast(result.reason, 'success');
                    break;
                case 'hardware_failover':
                    showToast(`⚙️ ${result.reason}`, 'warning');
                    break;
                case 'network_failover':
                    showToast(`📡 ${result.reason}`, 'warning');
                    break;
                case 'full_failover':
                    showToast(`⚠️ ${result.reason}`, 'warning');
                    break;
                default:
                    showToast(result.reason, 'success');
            }
            
            // Refresh status after a delay
            setTimeout(loadWifiFailoverStatus, 3000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply only hardware failover settings (interface priority)
 */
async function applyHardwareFailover() {
    try {
        const config = {
            hardware_failover_enabled: document.getElementById('wifi_hardware_failover_enabled')?.checked ?? true,
            primary_interface: document.getElementById('wifi_primary_interface')?.value || 'wlan1',
            secondary_interface: document.getElementById('wifi_secondary_interface')?.value || 'wlan0'
        };
        
        showToast('Application du failover hardware...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply/hardware', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            let message = 'Failover hardware appliqué';
            if (data.auto_config?.action === 'cloned_and_connected') {
                message += ` - ${data.auto_config.ssid} cloné et connecté sur ${config.secondary_interface}`;
            } else if (data.auto_config?.action === 'cloned') {
                message += ` - Configuration clonée vers ${config.secondary_interface}`;
            }
            showToast(message, 'success');
            loadWifiFailoverStatus();
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply only network failover settings (SSID configuration)
 */
async function applyNetworkFailover() {
    try {
        const primarySsid = document.getElementById('wifi_primary_ssid')?.value;
        
        if (!primarySsid) {
            showToast('Veuillez entrer un SSID principal', 'warning');
            return;
        }
        
        const config = {
            network_failover_enabled: document.getElementById('wifi_network_failover_enabled')?.checked ?? true,
            primary_ssid: primarySsid,
            primary_password: document.getElementById('wifi_primary_password')?.value || '',
            secondary_ssid: document.getElementById('wifi_secondary_ssid')?.value || '',
            secondary_password: document.getElementById('wifi_secondary_password')?.value || ''
        };
        
        showToast('Application du failover réseau...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply/network', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            let message = 'Failover réseau appliqué';
            if (data.connection?.success) {
                message += ` - Connecté à ${primarySsid}`;
            }
            showToast(message, 'success');
            setTimeout(loadWifiFailoverStatus, 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Apply only IP configuration settings
 */
async function applyIpConfig() {
    try {
        const ipMode = document.querySelector('input[name="wifi_failover_ip_mode"]:checked')?.value || 'dhcp';
        
        const config = {
            ip_mode: ipMode,
            static_ip: document.getElementById('wifi_failover_static_ip')?.value || '',
            gateway: document.getElementById('wifi_failover_gateway')?.value || '',
            dns: document.getElementById('wifi_failover_dns')?.value || '8.8.8.8'
        };
        
        if (ipMode === 'static' && !config.static_ip) {
            showToast('Veuillez entrer une adresse IP statique', 'warning');
            return;
        }
        
        showToast('Application de la configuration IP...', 'info');
        
        const response = await fetch('/api/wifi/failover/apply/ip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            const ifaceCount = data.interfaces?.length || 0;
            showToast(`Configuration IP appliquée à ${ifaceCount} interface(s)`, 'success');
            setTimeout(loadWifiFailoverStatus, 2000);
            setTimeout(loadNetworkInterfaces, 2000);
        } else {
            showToast(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Scan WiFi networks for a specific field
 */
async function scanWifiForField(fieldId) {
    try {
        const listId = fieldId.replace('_ssid', '-ssid-list').replace('wifi_', 'wifi-');
        const listContainer = document.getElementById(listId);
        
        if (!listContainer) {
            console.error('List container not found:', listId);
            return;
        }
        
        listContainer.innerHTML = '<div class="detection-item"><i class="fas fa-spinner fa-spin"></i> Scan en cours...</div>';
        listContainer.classList.add('visible');
        listContainer.style.display = 'block';
        
        const response = await fetch('/api/wifi/scan');
        const data = await response.json();
        
        if (data.success && data.networks.length > 0) {
            listContainer.innerHTML = data.networks.map(net => `
                <div class="detection-item wifi-network" onclick="selectWifiForField('${fieldId}', '${escapeHtml(net.ssid)}')">
                    <span class="wifi-ssid">${escapeHtml(net.ssid)}</span>
                    <span class="wifi-signal">${net.signal || ''} ${net.security || ''}</span>
                </div>
            `).join('');
        } else {
            listContainer.innerHTML = '<div class="detection-item"><span class="text-muted">Aucun réseau trouvé</span></div>';
        }
        
        // Auto-hide after 30 seconds
        setTimeout(() => {
            listContainer.style.display = 'none';
            listContainer.classList.remove('visible');
        }, 30000);
    } catch (error) {
        showToast(`Erreur: ${error.message}`, 'error');
    }
}

/**
 * Select a WiFi network for a specific field
 */
function selectWifiForField(fieldId, ssid) {
    const field = document.getElementById(fieldId);
    if (field) field.value = ssid;
    
    const listId = fieldId.replace('_ssid', '-ssid-list').replace('wifi_', 'wifi-');
    const listContainer = document.getElementById(listId);
    if (listContainer) {
        listContainer.style.display = 'none';
        listContainer.classList.remove('visible');
    }
    
    // Focus password field
    const passwordFieldId = fieldId.replace('_ssid', '_password');
    const passwordField = document.getElementById(passwordFieldId);
    if (passwordField) passwordField.focus();
}

// ============================================================================
// Ethernet/WiFi Auto-Management Functions
// ============================================================================

/**
 * Load Ethernet and WiFi override status
 */
async function loadEthernetWifiStatus() {
    try {
        const response = await fetch('/api/network/wifi/override');
        const data = await response.json();
        
        if (data.success) {
            // Update Ethernet status
            const ethBadge = document.getElementById('eth-status-badge');
            if (ethBadge) {
                if (data.ethernet.connected) {
                    ethBadge.textContent = 'Connecté';
                    ethBadge.className = 'badge badge-success';
                } else if (data.ethernet.present) {
                    ethBadge.textContent = 'Déconnecté';
                    ethBadge.className = 'badge badge-warning';
                } else {
                    ethBadge.textContent = 'Non détecté';
                    ethBadge.className = 'badge badge-secondary';
                }
            }
            
            // Update wlan0 status badge
            const wlan0Badge = document.getElementById('wlan0-status-badge');
            if (wlan0Badge) {
                if (data.wlan0) {
                    if (data.wlan0.ap_mode) {
                        wlan0Badge.textContent = 'Mode AP';
                        wlan0Badge.className = 'badge badge-info';
                    } else if (data.wlan0.connected) {
                        wlan0Badge.textContent = 'Connecté';
                        wlan0Badge.className = 'badge badge-success';
                    } else if (data.wlan0.managed) {
                        wlan0Badge.textContent = 'Désactivé (Eth prioritaire)';
                        wlan0Badge.className = 'badge badge-secondary';
                    } else {
                        wlan0Badge.textContent = 'Déconnecté';
                        wlan0Badge.className = 'badge badge-warning';
                    }
                } else {
                    wlan0Badge.textContent = 'Non détecté';
                    wlan0Badge.className = 'badge badge-secondary';
                }
            }
            
            // Update WiFi override checkbox
            const overrideCheckbox = document.getElementById('wifi_manual_override');
            if (overrideCheckbox) {
                overrideCheckbox.checked = data.override;
            }
            
            // Update status text
            const overrideStatus = document.getElementById('wifi-override-status');
            if (overrideStatus) {
                overrideStatus.textContent = data.override ? 'Forcé ON' : 'Auto';
                overrideStatus.className = `control-status ${data.override ? 'status-active' : ''}`;
            }
        }
    } catch (error) {
        console.error('Error loading Ethernet/WiFi status:', error);
    }
}

/**
 * Apply WiFi manual override setting
 */
async function applyWifiOverride() {
    const checkbox = document.getElementById('wifi_manual_override');
    const enable = checkbox ? checkbox.checked : false;
    
    try {
        showToast('Application en cours...', 'info');
        
        const response = await fetch('/api/network/wifi/override', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const action = data.wifi_management?.action || '';
            let message = enable ? 'WiFi forcé actif' : 'Mode automatique activé';
            if (action === 'reconnected') {
                message = 'WiFi reconnecté';
            } else if (action === 'disabled') {
                message = 'WiFi désactivé (Ethernet prioritaire)';
            }
            showToast(message, 'success');
            // Reload status to reflect changes
            loadEthernetWifiStatus();
            loadNetworkInterfaces();
        } else {
            showToast(data.message || data.error || 'Erreur', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

// Legacy function name for compatibility
async function setWifiManualOverride() {
    await applyWifiOverride();
}

// ============================================================================
// Access Point (AP) Functions
// ============================================================================

/**
 * Load Access Point status and configuration
 */
async function loadApStatus() {
    try {
        const response = await fetch('/api/network/ap/status');
        const data = await response.json();
        
        if (data.success) {
            const status = data.status;
            const config = data.config;
            
            // Update status banner
            const statusBanner = document.getElementById('ap-status-banner');
            const statusIcon = document.getElementById('ap-status-icon');
            const statusText = document.getElementById('ap-status-text');
            const clientsCount = document.getElementById('ap-clients-count');
            
            if (status.active) {
                statusBanner.className = 'ap-status-banner ap-active';
                statusIcon.className = 'fas fa-circle status-active';
                statusText.textContent = `Point d'accès actif: ${status.ssid} (${status.ip})`;
                if (clientsCount) {
                    clientsCount.style.display = 'inline';
                    clientsCount.textContent = `${status.clients} client${status.clients !== 1 ? 's' : ''}`;
                }
            } else {
                statusBanner.className = 'ap-status-banner ap-inactive';
                statusIcon.className = 'fas fa-circle status-inactive';
                statusText.textContent = 'Point d\'accès inactif';
                if (clientsCount) clientsCount.style.display = 'none';
            }
            
            // Update form fields from config (Meeting values)
            const apSsidField = document.getElementById('ap_ssid');
            const apPasswordField = document.getElementById('ap_password');
            const apIpField = document.getElementById('ap_ip');
            
            if (apSsidField && config.ap_ssid) apSsidField.value = config.ap_ssid;
            if (apPasswordField && config.ap_password) apPasswordField.value = config.ap_password;
            if (apIpField && config.ap_ip) apIpField.value = config.ap_ip;
            
            // Update buttons visibility
            const btnStart = document.getElementById('btn-start-ap');
            const btnStop = document.getElementById('btn-stop-ap');
            if (btnStart) btnStart.style.display = status.active ? 'none' : 'inline-flex';
            if (btnStop) btnStop.style.display = status.active ? 'inline-flex' : 'none';
            
            // Show/hide warning
            const warningAlert = document.getElementById('ap-warning-alert');
            if (warningAlert) {
                warningAlert.style.display = status.active ? 'flex' : 'none';
            }
            
            // If no config from Meeting, try to load it (silently)
            if (!config.ap_ssid || !config.ap_password) {
                loadApConfigFromMeeting(true);
            }
        }
    } catch (error) {
        console.error('Error loading AP status:', error);
        const statusText = document.getElementById('ap-status-text');
        if (statusText) statusText.textContent = 'Erreur de chargement';
    }
}

/**
 * Save Access Point configuration
 */
async function saveApConfig() {
    const config = {
        ap_ssid: document.getElementById('ap_ssid').value,
        ap_password: document.getElementById('ap_password').value,
        ap_channel: parseInt(document.getElementById('ap_channel').value) || 7,
        ap_ip: document.getElementById('ap_ip').value,
        dhcp_range_start: document.getElementById('dhcp_range_start').value,
        dhcp_range_end: document.getElementById('dhcp_range_end').value
    };
    
    // Validation
    if (!config.ap_ssid) {
        showToast('Le SSID est requis', 'error');
        return false;
    }
    if (config.ap_password && config.ap_password.length < 8) {
        showToast('Le mot de passe doit faire au moins 8 caractères', 'error');
        return false;
    }
    
    try {
        const response = await fetch('/api/network/ap/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration AP enregistrée', 'success');
            return true;
        } else {
            showToast(data.message || 'Erreur sauvegarde', 'error');
            return false;
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
        return false;
    }
}

/**
 * Load AP configuration from Meeting (auto-called if no config)
 */
async function loadApConfigFromMeeting(silent = false) {
    try {
        if (!silent) showToast('Récupération des paramètres Meeting...', 'info');
        
        const response = await fetch('/api/network/ap/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from_meeting: true })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (!silent) showToast('Paramètres AP récupérés depuis Meeting', 'success');
            // Update form fields directly from response
            if (data.config) {
                const apSsidField = document.getElementById('ap_ssid');
                const apPasswordField = document.getElementById('ap_password');
                const apChannelField = document.getElementById('ap_channel');
                const apChannelDisplayField = document.getElementById('ap_channel_display');
                
                if (apSsidField && data.config.ap_ssid) apSsidField.value = data.config.ap_ssid;
                if (apPasswordField && data.config.ap_password) apPasswordField.value = data.config.ap_password;
                if (apChannelField && data.config.ap_channel) {
                    apChannelField.value = data.config.ap_channel;
                    // Update display (map channel to frequency)
                    const freqMap = {1: 2412, 6: 2437, 11: 2462};
                    const freq = freqMap[data.config.ap_channel] || (2407 + data.config.ap_channel * 5);
                    if (apChannelDisplayField) {
                        apChannelDisplayField.value = `Canal ${data.config.ap_channel} (${freq} MHz)`;
                    }
                }
            }
        } else {
            if (!silent) showToast(data.message || 'Erreur récupération Meeting', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Start Access Point
 */
async function startAccessPoint() {
    // Check if Meeting config is available
    const apSsid = document.getElementById('ap_ssid')?.value;
    const apPassword = document.getElementById('ap_password')?.value;
    const apChannel = document.getElementById('ap_channel')?.value || 11;
    
    // Check for placeholder values
    if (!apSsid || apSsid.includes('non configuré')) {
        showToast('Configuration AP manquante. Vérifiez que Meeting est provisionné.', 'error');
        return;
    }
    if (!apPassword || apPassword.includes('non configuré')) {
        showToast('Mot de passe AP manquant. Vérifiez que Meeting est provisionné.', 'error');
        return;
    }
    
    try {
        showToast('Démarrage du point d\'accès...', 'info');
        
        const response = await fetch('/api/network/ap/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ssid: apSsid,
                password: apPassword,
                channel: parseInt(apChannel)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(loadApStatus, 2000);
            setTimeout(loadEthernetWifiStatus, 2000);
        } else {
            showToast(data.message || 'Erreur démarrage AP', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Stop Access Point
 */
async function stopAccessPoint() {
    try {
        showToast('Arrêt du point d\'accès...', 'info');
        
        const response = await fetch('/api/network/ap/stop', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message, 'success');
            setTimeout(loadApStatus, 1000);
            setTimeout(loadEthernetWifiStatus, 1000);
        } else {
            showToast(data.message || 'Erreur arrêt AP', 'error');
        }
    } catch (error) {
        showToast('Erreur de connexion', 'error');
    }
}

/**
 * Toggle collapsible section
 */
function toggleSection(header) {
    const section = header.closest('.collapsed-section');
    section.classList.toggle('expanded');
}

// ============================================================================



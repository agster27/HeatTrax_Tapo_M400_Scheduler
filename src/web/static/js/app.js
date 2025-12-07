// Module-level variables to track the last full config
let lastAnnotatedConfig = null;
let lastRawConfig = null;

// Deep merge helper function
// Recursively merges source into target, replacing arrays entirely
function deepMerge(target, source) {
    const result = {};
    
    // Copy all properties from target
    for (const key in target) {
        if (target.hasOwnProperty(key)) {
            result[key] = target[key];
        }
    }
    
    // Merge properties from source
    for (const key in source) {
        if (source.hasOwnProperty(key)) {
            if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key]) &&
                result[key] && typeof result[key] === 'object' && !Array.isArray(result[key])) {
                // Recursively merge nested objects
                result[key] = deepMerge(result[key], source[key]);
            } else {
                // Replace value (including arrays)
                result[key] = source[key];
            }
        }
    }
    
    return result;
}

// Tab switching
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    
    document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Stop notification polling when leaving status tab
    if (typeof stopNotificationPolling === 'function') {
        stopNotificationPolling();
    }
    
    if (tabName === 'status') {
        refreshStatus();
        refreshVacationMode();
        // Start notification polling when entering status tab
        if (typeof startNotificationPolling === 'function') {
            startNotificationPolling();
        }
    } else if (tabName === 'schedules') {
        refreshSchedules();
    } else if (tabName === 'groups') {
        refreshGroups();
    } else if (tabName === 'config') {
        loadConfig();
    } else if (tabName === 'health') {
        refreshHealth();
    } else if (tabName === 'weather') {
        refreshWeather();
    }
}

// Check for security warning
async function checkSecurity() {
    try {
        const response = await fetch('/api/config');
        const annotatedConfig = await response.json();
        const config = extractConfigValues(annotatedConfig);
        
        if (config.web && config.web.bind_host && config.web.bind_host.value !== '127.0.0.1' && config.web.bind_host.value !== 'localhost') {
            const bindHost = config.web.bind_host.value || config.web.bind_host;
            if (bindHost !== '127.0.0.1' && bindHost !== 'localhost') {
                document.getElementById('security-warning').style.display = 'block';
            }
        }
    } catch (e) {
        console.error('Failed to check security:', e);
    }
}

// Check and display setup mode banner
async function checkSetupMode() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        
        const setupBanner = document.getElementById('setup-mode-banner');
        const setupReason = document.getElementById('setup-reason');
        
        if (status.setup_mode) {
            setupReason.textContent = status.setup_reason || 'Tapo credentials are missing or invalid.';
            setupBanner.style.display = 'block';
        } else {
            setupBanner.style.display = 'none';
        }
    } catch (e) {
        console.error('Failed to check setup mode:', e);
    }
}

// Refresh status
async function refreshStatus() {
    const statusContent = document.getElementById('status-content');
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        
        // Check for setup mode
        if (status.setup_mode !== undefined) {
            const setupBanner = document.getElementById('setup-mode-banner');
            const setupReason = document.getElementById('setup-reason');
            
            if (status.setup_mode) {
                setupReason.textContent = status.setup_reason || 'Tapo credentials are missing or invalid.';
                setupBanner.style.display = 'block';
            } else {
                setupBanner.style.display = 'none';
            }
        }
        
        let html = '';
        
        // Setup mode status
        if (status.setup_mode !== undefined) {
            html += `
                <div class="status-item" style="border-left-color: ${status.setup_mode ? '#ff9800' : '#27ae60'};">
                    <label>Mode</label>
                    <value>${status.setup_mode ? '🔧 Setup Mode (Device Control Disabled)' : '✓ Normal Mode (Device Control Enabled)'}</value>
                </div>
            `;
        }
        
        // Config info
        if (status.config_path) {
            html += `
                <div class="status-item">
                    <label>Config Path</label>
                    <value>${status.config_path}</value>
                </div>
            `;
        }
        
        if (status.config_last_modified) {
            html += `
                <div class="status-item">
                    <label>Config Last Modified</label>
                    <value>${new Date(status.config_last_modified).toLocaleString()}</value>
                </div>
            `;
        }
        
        // Weather info
        if (status.weather_enabled !== undefined) {
            html += `
                <div class="status-item">
                    <label>Weather Mode</label>
                    <value>${status.weather_enabled ? 'Enabled' : 'Disabled'}</value>
                </div>
            `;
        }
        
        if (status.last_weather_fetch) {
            html += `
                <div class="status-item">
                    <label>Last Weather Fetch</label>
                    <value>${new Date(status.last_weather_fetch).toLocaleString()}</value>
                </div>
            `;
        }
        
        // Device info
        if (status.device_groups) {
            for (const [groupName, groupInfo] of Object.entries(status.device_groups)) {
                html += `
                    <div class="status-item">
                        <label>Group: ${groupName}</label>
                        <value>Devices: ${groupInfo.device_count || 0}</value>
                    </div>
                `;
            }
        }
        
        // Last error
        if (status.last_error) {
            html += `
                <div class="status-item" style="border-left-color: #e74c3c;">
                    <label>Last Error</label>
                    <value>${status.last_error}</value>
                </div>
            `;
        }
        
        statusContent.innerHTML = html || '<div class="status-item"><label>No status information available</label></div>';
        
        // Also refresh group controls
        await refreshGroupControls();
        
    } catch (e) {
        statusContent.innerHTML = `<div class="error">Failed to load status: ${e.message}</div>`;
    }
}

// Refresh group controls in status tab
async function refreshGroupControls() {
    const groupControlsContent = document.getElementById('group-controls-content');
    
    if (!groupControlsContent) {
        return; // Element not found, probably not on status tab
    }
    
    try {
        // Fetch both status and device status
        const [statusResponse, devicesResponse] = await Promise.all([
            fetch('/api/status'),
            fetch('/api/devices/status')
        ]);
        
        const status = await statusResponse.json();
        let devicesData = null;
        
        // Check if devices endpoint is available (might fail in setup mode)
        if (devicesResponse.ok) {
            devicesData = await devicesResponse.json();
        }
        
        const deviceGroups = status.device_groups || {};
        const setupMode = status.setup_mode || false;
        
        if (Object.keys(deviceGroups).length === 0) {
            groupControlsContent.innerHTML = '<div class="status-item"><label>No device groups configured</label></div>';
            return;
        }
        
        // Calculate power state for each group
        const groupPowerStates = {};
        if (devicesData && devicesData.devices) {
            for (const device of devicesData.devices) {
                const groupName = device.group;
                if (!groupPowerStates[groupName]) {
                    groupPowerStates[groupName] = { on: 0, off: 0, total: 0, reachable: false };
                }
                
                if (device.reachable && device.initialized) {
                    groupPowerStates[groupName].reachable = true;
                    
                    if (device.outlets && device.outlets.length > 0) {
                        // Device has outlets
                        for (const outlet of device.outlets) {
                            groupPowerStates[groupName].total++;
                            if (outlet.is_on) {
                                groupPowerStates[groupName].on++;
                            } else {
                                groupPowerStates[groupName].off++;
                            }
                        }
                    } else {
                        // Device without outlets (single power state)
                        // Note: Current API doesn't provide power state for non-outlet devices
                        // We treat them as OFF until API is enhanced to provide this information
                        groupPowerStates[groupName].total++;
                        groupPowerStates[groupName].off++;
                    }
                }
            }
        }
        
        // Render group controls
        let html = '<div class="group-controls-grid">';
        
        for (const [groupName, groupInfo] of Object.entries(deviceGroups)) {
            const powerState = groupPowerStates[groupName] || { on: 0, off: 0, total: 0, reachable: false };
            
            let statusBadge = '';
            let statusClass = '';
            
            if (powerState.total === 0 || !powerState.reachable) {
                statusBadge = '<span class="group-status off">Offline</span>';
                statusClass = 'off';
            } else if (powerState.on === powerState.total) {
                statusBadge = '<span class="group-status on">All ON</span>';
                statusClass = 'on';
            } else if (powerState.off === powerState.total) {
                statusBadge = '<span class="group-status off">All OFF</span>';
                statusClass = 'off';
            } else {
                statusBadge = `<span class="group-status mixed">${powerState.on}/${powerState.total} ON</span>`;
                statusClass = 'mixed';
            }
            
            const disabled = setupMode || !powerState.reachable;
            const disabledAttr = disabled ? 'disabled' : '';
            
            html += `
                <div class="group-control-item">
                    <h3>
                        ${groupName}
                        ${statusBadge}
                    </h3>
                    <div class="group-info">
                        ${groupInfo.device_count || 0} device(s) • ${powerState.total} outlet(s)
                    </div>
                    <div class="group-control-buttons">
                        <button class="btn-group-control btn-group-on" 
                                onclick="controlGroupFromStatus('${groupName}', 'on')"
                                ${disabledAttr}
                                title="Turn ON all outlets in ${groupName}">
                            ⚡ Turn ON
                        </button>
                        <button class="btn-group-control btn-group-off" 
                                onclick="controlGroupFromStatus('${groupName}', 'off')"
                                ${disabledAttr}
                                title="Turn OFF all outlets in ${groupName}">
                            🔌 Turn OFF
                        </button>
                    </div>
                    <div id="group-control-msg-${sanitizeDeviceName(groupName)}" class="group-control-message"></div>
                </div>
            `;
        }
        
        html += '</div>';
        groupControlsContent.innerHTML = html;
        
    } catch (e) {
        console.error('Failed to refresh group controls:', e);
        groupControlsContent.innerHTML = `<div class="error">Failed to load group controls: ${e.message}</div>`;
    }
}

// Control group from status tab
async function controlGroupFromStatus(groupName, action) {
    const messageId = `group-control-msg-${sanitizeDeviceName(groupName)}`;
    const messageDiv = document.getElementById(messageId);
    
    if (messageDiv) {
        messageDiv.className = 'group-control-message info';
        messageDiv.style.display = 'block';
        messageDiv.textContent = `Sending ${action.toUpperCase()} command...`;
    }
    
    try {
        const response = await fetch(`/api/groups/${groupName}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ action: action })
        });
        
        const result = await response.json();
        
        if (result.success) {
            if (messageDiv) {
                messageDiv.className = 'group-control-message success';
                messageDiv.textContent = `✓ ${result.successful} outlet(s) turned ${action.toUpperCase()}`;
                
                // Hide message after 3 seconds
                setTimeout(() => {
                    messageDiv.style.display = 'none';
                }, 3000);
            }
            
            // Refresh group controls after delay to allow devices to update state
            // 1 second provides reasonable UX without overwhelming the API
            const REFRESH_DELAY_MS = 1000;
            setTimeout(() => {
                refreshGroupControls();
            }, REFRESH_DELAY_MS);
        } else {
            if (messageDiv) {
                messageDiv.className = 'group-control-message error';
                messageDiv.textContent = `✗ Error: ${result.error || 'Failed to control group'}`;
            }
        }
    } catch (e) {
        console.error('Failed to control group:', e);
        if (messageDiv) {
            messageDiv.className = 'group-control-message error';
            messageDiv.textContent = `✗ Error: ${e.message}`;
        }
    }
}

// Refresh groups and automation controls
async function refreshGroups() {
    const groupsContent = document.getElementById('groups-content');
    
    try {
        // Fetch config to get list of groups
        const configResponse = await fetch('/api/config');
        const annotatedConfig = await configResponse.json();
        const config = extractConfigValues(annotatedConfig);
        
        const groups = config.devices?.groups;
        if (!groups || Object.keys(groups).length === 0) {
            groupsContent.innerHTML = '<p>No device groups configured.</p>';
            return;
        }
        
        let html = '';
        
        for (const [groupName, groupConfig] of Object.entries(groups)) {
            // Fetch schedules for this group
            try {
                const schedulesResponse = await fetch(`/api/groups/${groupName}/schedules`);
                if (!schedulesResponse.ok) {
                    throw new Error(`HTTP ${schedulesResponse.status}: ${schedulesResponse.statusText}`);
                }
                const schedulesData = await schedulesResponse.json();
                
                if (schedulesData.error) {
                    html += `<div class="group-card">
                        <h3>${groupName}</h3>
                        <p class="error">${schedulesData.error}</p>
                    </div>`;
                    continue;
                }
                
                const schedules = schedulesData.schedules || [];
                const enabled = groupConfig.enabled !== false;
                
                html += `<div class="group-card">
                    <h3>${groupName}</h3>
                    <div class="group-control-row">
                        <div class="group-control-item">
                            <label class="automation-toggle">
                                <input type="checkbox" ${enabled ? 'checked' : ''} 
                                       onchange="toggleGroupEnabled('${groupName}', this.checked)">
                                <span class="automation-slider"></span>
                            </label>
                            <span class="control-label">Group Enabled</span>
                        </div>
                    </div>`;
                
                // Show schedules
                if (schedules.length > 0) {
                    html += `<div class="schedules-list">
                        <h4>📅 Schedules</h4>`;
                    
                    schedules.forEach((schedule, index) => {
                        const enabledBadge = schedule.enabled ? '<span class="badge-enabled">✓ Enabled</span>' : '<span class="badge-disabled">Disabled</span>';
                        const priorityBadge = schedule.priority ? `<span class="badge-priority">${schedule.priority}</span>` : '';
                        
                        // Helper function to format solar time with offset
                        const formatSolarTime = (icon, type, offset) => {
                            if (!offset || offset === 0) return `${icon} ${type}`;
                            const sign = offset > 0 ? '+' : '-';
                            const absOffset = Math.abs(offset);
                            return `${icon} ${type} ${sign} ${absOffset}m`;
                        };
                        
                        // Format ON time
                        let onTime = '';
                        if (schedule.on?.type === 'time') {
                            onTime = schedule.on.value;
                        } else if (schedule.on?.type === 'sunrise') {
                            onTime = formatSolarTime('🌅', 'Sunrise', schedule.on.offset);
                        } else if (schedule.on?.type === 'sunset') {
                            onTime = formatSolarTime('🌇', 'Sunset', schedule.on.offset);
                        }
                        
                        // Format OFF time
                        let offTime = '';
                        if (schedule.off?.type === 'time') {
                            offTime = schedule.off.value;
                        } else if (schedule.off?.type === 'sunrise') {
                            offTime = formatSolarTime('🌅', 'Sunrise', schedule.off.offset);
                        } else if (schedule.off?.type === 'sunset') {
                            offTime = formatSolarTime('🌇', 'Sunset', schedule.off.offset);
                        } else if (schedule.off?.type === 'duration') {
                            offTime = `Duration: ${schedule.off.hours}h`;
                        }
                        
                        // Format conditions
                        let conditions = [];
                        if (schedule.conditions?.temperature_max) {
                            conditions.push(`Temp ≤ ${schedule.conditions.temperature_max}°F`);
                        }
                        if (schedule.conditions?.precipitation_active) {
                            conditions.push('Precipitation');
                        }
                        const conditionsText = conditions.length > 0 ? 
                            `<div class="schedule-conditions">Conditions: ${conditions.join(', ')}</div>` : '';
                        
                        html += `<div class="schedule-item">
                            <div class="schedule-header">
                                <strong>${schedule.name || 'Unnamed Schedule'}</strong>
                                ${enabledBadge} ${priorityBadge}
                            </div>
                            <div class="schedule-times">
                                <span>ON: ${onTime}</span> → <span>OFF: ${offTime}</span>
                            </div>
                            ${conditionsText}
                        </div>`;
                    });
                    
                    html += `</div>`;
                } else {
                    html += `<div class="info-text" style="margin-top: 15px;">
                        No schedules configured. Add schedules in config.yaml to enable automation.
                    </div>`;
                }
                
                html += '</div>';
                
            } catch (e) {
                html += `<div class="group-card">
                    <h3>${groupName}</h3>
                    <p class="error">Failed to load group data: ${e.message}</p>
                </div>`;
            }
        }
        
        groupsContent.innerHTML = html;
        
    } catch (e) {
        groupsContent.innerHTML = `<div class="error">Failed to load groups: ${e.message}</div>`;
    }
}

async function toggleGroupEnabled(groupName, enabled) {
    try {
        // Update config to enable/disable the group
        const configResponse = await fetch('/api/config');
        const annotatedConfig = await configResponse.json();
        const config = extractConfigValues(annotatedConfig);
        
        if (!config.devices?.groups?.[groupName]) {
            alert(`Group '${groupName}' not found`);
            await refreshGroups();
            return;
        }
        
        // Update the enabled flag
        config.devices.groups[groupName].enabled = enabled;
        
        // Save config
        const saveResponse = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        if (!saveResponse.ok) {
            const error = await saveResponse.json();
            alert(`Failed to update group: ${error.error || 'Unknown error'}`);
            await refreshGroups();
            return;
        }
        
        showMessage('config-message', `Group '${groupName}' ${enabled ? 'enabled' : 'disabled'}`, 'success');
        
        // Refresh to show updated state
        await refreshGroups();
        
    } catch (e) {
        alert(`Failed to update group: ${e.message}`);
        await refreshGroups();
    }
}

// Store expanded state of accordions
// Contains sanitized accordion IDs to persist expand/collapse state across view changes
let expandedAccordions = new Set();

// Get current health view preference
function getHealthViewPreference() {
    return localStorage.getItem('healthViewPreference') || 'device';
}

// Set health view preference
function setHealthViewPreference(view) {
    localStorage.setItem('healthViewPreference', view);
}

// Toggle accordion
function toggleAccordion(accordionId) {
    const content = document.getElementById(`accordion-content-${accordionId}`);
    const toggle = document.getElementById(`accordion-toggle-${accordionId}`);
    
    if (!content || !toggle) return;
    
    const isExpanded = content.classList.contains('expanded');
    
    if (isExpanded) {
        content.classList.remove('expanded');
        toggle.classList.remove('expanded');
        expandedAccordions.delete(accordionId);
    } else {
        content.classList.add('expanded');
        toggle.classList.add('expanded');
        expandedAccordions.add(accordionId);
    }
}

// Switch health view
function switchHealthView(view) {
    setHealthViewPreference(view);
    const checkbox = document.getElementById('health-view-toggle');
    if (checkbox) {
        checkbox.checked = (view === 'group');
    }
    renderHealthView();
}

// Render health view based on preference
async function renderHealthView() {
    const view = getHealthViewPreference();
    const deviceHealthContent = document.getElementById('device-health-content');
    
    if (!deviceHealthContent) return;
    
    try {
        // Fetch both status data and device control data in parallel
        const [statusResponse, deviceControlResponse] = await Promise.all([
            fetch('/api/status'),
            fetch('/api/devices/status')
        ]);
        
        // Check response status
        if (!statusResponse.ok) {
            throw new Error(`Failed to fetch status data (HTTP ${statusResponse.status})`);
        }
        if (!deviceControlResponse.ok) {
            throw new Error(`Failed to fetch device control data (HTTP ${deviceControlResponse.status})`);
        }
        
        const status = await statusResponse.json();
        const deviceControlData = await deviceControlResponse.json();
        
        if (!status.device_expectations || status.device_expectations.length === 0) {
            // Show empty state
            deviceHealthContent.innerHTML = renderEmptyState(status);
            return;
        }
        
        if (view === 'device') {
            deviceHealthContent.innerHTML = renderDeviceView(status.device_expectations, deviceControlData);
        } else {
            deviceHealthContent.innerHTML = renderGroupView(status.device_expectations, deviceControlData);
        }
        
        // Restore expanded state
        for (const accordionId of expandedAccordions) {
            const content = document.getElementById(`accordion-content-${accordionId}`);
            const toggle = document.getElementById(`accordion-toggle-${accordionId}`);
            if (content && toggle) {
                content.classList.add('expanded');
                toggle.classList.add('expanded');
            }
        }
        
    } catch (e) {
        deviceHealthContent.innerHTML = `<div class="error">Error loading health view: ${e.message}</div>`;
    }
}

// Render empty state
function renderEmptyState(status) {
    if (status.device_groups) {
        let totalConfigured = 0;
        for (const groupInfo of Object.values(status.device_groups)) {
            totalConfigured += groupInfo.device_count || 0;
        }
        if (totalConfigured > 0) {
            return `
                <div class="info-text empty">
                    <strong>⚠️ No Device Status Available</strong><br><br>
                    ${totalConfigured} device(s) configured, but device status/expectations not available.
                    This may indicate devices failed to initialize or scheduler not fully started.
                    Check Device Control tab and logs for details.
                </div>
            `;
        }
    }
    return '<div class="info-text empty">No devices configured</div>';
}

// Generate sanitized accordion ID from key
function generateAccordionId(key, prefix = '') {
    const sanitized = key.replace(/[^a-zA-Z0-9]/g, '-');
    return prefix ? `${prefix}-${sanitized}` : sanitized;
}

// Sanitize device name for use in HTML IDs
function sanitizeDeviceName(deviceName) {
    return deviceName.replace(/[^a-zA-Z0-9]/g, '-');
}

// Get overall health status for a device
function getDeviceHealthStatus(outlets) {
    let hasError = false;
    let hasWarning = false;
    let allHealthy = true;
    
    for (const outlet of outlets) {
        if (outlet.current_state !== outlet.expected_state) {
            hasWarning = true;
            allHealthy = false;
        }
        if (outlet.last_error) {
            hasError = true;
            allHealthy = false;
        }
    }
    
    if (hasError) return { status: 'error', icon: '❌', text: 'Error' };
    if (hasWarning) return { status: 'warning', icon: '⚠️', text: 'Warning' };
    return { status: 'healthy', icon: '✓', text: 'Healthy' };
}

// Render device view
function renderDeviceView(expectations, deviceControlData) {
    // Group by device
    const deviceMap = new Map();
    
    for (const exp of expectations) {
        const deviceKey = `${exp.device_name}-${exp.ip_address}`;
        if (!deviceMap.has(deviceKey)) {
            deviceMap.set(deviceKey, {
                name: exp.device_name,
                ip: exp.ip_address,
                groups: new Set(),
                outlets: []
            });
        }
        
        const device = deviceMap.get(deviceKey);
        device.groups.add(exp.group);
        device.outlets.push(exp);
    }
    
    // Create a map of device control data by device name and IP
    const deviceControlMap = new Map();
    if (deviceControlData && deviceControlData.devices) {
        for (const controlDevice of deviceControlData.devices) {
            const key = `${controlDevice.name}-${controlDevice.ip_address}`;
            deviceControlMap.set(key, controlDevice);
        }
    }
    
    let html = '';
    
    for (const [deviceKey, device] of deviceMap) {
        const healthStatus = getDeviceHealthStatus(device.outlets);
        const accordionId = generateAccordionId(deviceKey);
        const controlDevice = deviceControlMap.get(deviceKey);
        
        // Determine online/offline status from control data
        const isReachable = controlDevice ? controlDevice.reachable : false;
        const isInitialized = controlDevice ? (controlDevice.initialized !== false) : true;
        const statusBadgeClass = isReachable ? 'online' : 'offline';
        const statusText = isReachable ? '● Online' : (isInitialized ? '● Offline' : '● Not Initialized');
        
        html += `
            <div class="accordion-card ${healthStatus.status}">
                <div class="accordion-header" onclick="toggleAccordion('${accordionId}')">
                    <div class="accordion-header-left">
                        <div>
                            <div class="accordion-header-title">${device.name}</div>
                            <div class="accordion-header-subtitle">${device.ip}</div>
                            <div class="group-tags">
                                ${Array.from(device.groups).map(g => `<span class="group-tag">${g}</span>`).join('')}
                            </div>
                        </div>
                    </div>
                    <div class="accordion-header-right">
                        <span class="device-status-badge ${statusBadgeClass}">${statusText}</span>
                        <span class="status-badge ${healthStatus.status}">${healthStatus.icon} ${healthStatus.text}</span>
                        <span class="accordion-toggle" id="accordion-toggle-${accordionId}">▼</span>
                    </div>
                </div>
                <div class="accordion-content" id="accordion-content-${accordionId}">
                    <div class="accordion-body">
                        <div class="outlet-details-grid">
                            ${device.outlets.map(outlet => renderOutletDetailWithControl(outlet, controlDevice)).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    return html;
}

// Render group view
function renderGroupView(expectations, deviceControlData) {
    // Group by group name
    const groupMap = new Map();
    
    for (const exp of expectations) {
        if (!groupMap.has(exp.group)) {
            groupMap.set(exp.group, []);
        }
        groupMap.get(exp.group).push(exp);
    }
    
    // Create a map of device control data by device name and group
    const deviceControlMap = new Map();
    if (deviceControlData && deviceControlData.devices) {
        for (const controlDevice of deviceControlData.devices) {
            const key = `${controlDevice.group}-${controlDevice.name}`;
            deviceControlMap.set(key, controlDevice);
        }
    }
    
    let html = '';
    
    for (const [groupName, outlets] of groupMap) {
        const healthStatus = getDeviceHealthStatus(outlets);
        const accordionId = generateAccordionId(groupName, 'group');
        
        // Get all devices in this group for group control
        const groupDevices = deviceControlData && deviceControlData.devices ? 
            deviceControlData.devices.filter(d => d.group === groupName) : [];
        
        // Check if any device in group is reachable
        const anyReachable = groupDevices.some(d => d.reachable);
        
        html += `
            <div class="accordion-card ${healthStatus.status}">
                <div class="accordion-header">
                    <div class="accordion-header-left">
                        <div onclick="toggleAccordion('${accordionId}')" style="flex: 1; cursor: pointer;">
                            <div class="accordion-header-title">${groupName}</div>
                            <div class="accordion-header-subtitle">${outlets.length} outlet(s)</div>
                        </div>
                    </div>
                    <div class="accordion-header-right">
                        <div class="group-control-buttons" onclick="event.stopPropagation();">
                            <button class="btn-control btn-on btn-group" 
                                    onclick="controlGroup('${groupName}', 'on')"
                                    ${!anyReachable ? 'disabled' : ''}
                                    title="Turn ON all outlets in this group">
                                ⚡ Turn ON All
                            </button>
                            <button class="btn-control btn-off btn-group" 
                                    onclick="controlGroup('${groupName}', 'off')"
                                    ${!anyReachable ? 'disabled' : ''}
                                    title="Turn OFF all outlets in this group">
                                🔌 Turn OFF All
                            </button>
                        </div>
                        <span class="status-badge ${healthStatus.status}">${healthStatus.icon} ${healthStatus.text}</span>
                        <span class="accordion-toggle" id="accordion-toggle-${accordionId}" onclick="toggleAccordion('${accordionId}')">▼</span>
                    </div>
                </div>
                <div class="accordion-content" id="accordion-content-${accordionId}">
                    <div class="accordion-body">
                        <div id="group-control-message-${sanitizeDeviceName(groupName)}" class="control-message" style="display: none; margin-bottom: 15px;"></div>
                        <div class="outlet-details-grid">
                            ${outlets.map(outlet => renderOutletDetailWithDeviceAndControl(outlet, deviceControlMap)).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    return html;
}

// Render outlet detail card
function renderOutletDetail(outlet) {
    const isMatch = outlet.current_state === outlet.expected_state;
    const matchClass = isMatch ? 'match' : 'mismatch';
    const stateIcon = isMatch ? '✓' : '⚠️';
    
    return `
        <div class="outlet-detail-card ${matchClass}">
            <div class="outlet-detail-header">
                <span>Outlet ${outlet.outlet}</span>
                <span class="state-indicator ${matchClass}">${stateIcon}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Group:</span>
                <span class="outlet-detail-value">${outlet.group}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Current State:</span>
                <span class="outlet-detail-value">${outlet.current_state.toUpperCase()}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Expected State:</span>
                <span class="outlet-detail-value">${outlet.expected_state.toUpperCase()}</span>
            </div>
            ${outlet.expected_on_from ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected ON from:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_on_from).toLocaleString()}</span>
                </div>
            ` : ''}
            ${outlet.expected_off_at ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected OFF at:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_off_at).toLocaleString()}</span>
                </div>
            ` : ''}
            ${outlet.last_state_change ? `
                <div class="timestamp-display">Last change: ${new Date(outlet.last_state_change).toLocaleString()}</div>
            ` : ''}
        </div>
    `;
}

// Render outlet detail with integrated controls (for device view)
function renderOutletDetailWithControl(outlet, controlDevice) {
    const isMatch = outlet.current_state === outlet.expected_state;
    const matchClass = isMatch ? 'match' : 'mismatch';
    const stateIcon = isMatch ? '✓' : '⚠️';
    
    // Find the specific outlet control data
    const isReachable = controlDevice ? controlDevice.reachable : false;
    const isInitialized = controlDevice ? (controlDevice.initialized !== false) : true;
    
    let outletControl = null;
    if (controlDevice && controlDevice.outlets) {
        outletControl = controlDevice.outlets.find(o => o.index === outlet.outlet);
    }
    
    const outletState = outletControl ? (outletControl.is_on ? 'on' : 'off') : 'unknown';
    const outletStateText = outletControl ? (outletControl.is_on ? 'ON' : 'OFF') : 'UNKNOWN';
    const outletIsOn = outletControl ? outletControl.is_on : false;
    
    // Determine schedule status
    const hasSchedule = outlet.expected_on_from || outlet.expected_off_at;
    const scheduleStatus = hasSchedule ? '📅 Scheduled' : '⚪ Manual';
    
    return `
        <div class="outlet-detail-card ${matchClass}">
            <div class="outlet-detail-header">
                <span>Outlet ${outlet.outlet}</span>
                <span class="state-indicator ${matchClass}">${stateIcon}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Group:</span>
                <span class="outlet-detail-value">${outlet.group}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">IP Address:</span>
                <span class="outlet-detail-value">${outlet.ip_address}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Current State:</span>
                <span class="outlet-detail-value">${outlet.current_state.toUpperCase()}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Expected State:</span>
                <span class="outlet-detail-value">${outlet.expected_state.toUpperCase()}</span>
            </div>
            ${outlet.last_state_change ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Last Updated:</span>
                    <span class="outlet-detail-value">${new Date(outlet.last_state_change).toLocaleString()}</span>
                </div>
            ` : ''}
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Schedule Status:</span>
                <span class="outlet-detail-value">${scheduleStatus}</span>
            </div>
            ${outlet.expected_on_from ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected ON from:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_on_from).toLocaleString()}</span>
                </div>
            ` : ''}
            ${outlet.expected_off_at ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected OFF at:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_off_at).toLocaleString()}</span>
                </div>
            ` : ''}
            ${controlDevice ? `
                <div class="outlet-controls-inline">
                    <div class="outlet-control-buttons">
                        <button class="btn-control btn-on" 
                                onclick="controlOutlet('${outlet.group}', '${outlet.device_name}', ${outlet.outlet}, 'on')"
                                ${!isReachable || outletIsOn ? 'disabled' : ''}>
                            Turn ON
                        </button>
                        <button class="btn-control btn-off" 
                                onclick="controlOutlet('${outlet.group}', '${outlet.device_name}', ${outlet.outlet}, 'off')"
                                ${!isReachable || !outletIsOn ? 'disabled' : ''}>
                            Turn OFF
                        </button>
                    </div>
                    <div id="control-message-${sanitizeDeviceName(outlet.device_name)}-${outlet.outlet}" class="control-message-inline" style="display: none;"></div>
                </div>
            ` : ''}
        </div>
    `;
}

// Render outlet detail with device info (for group view)
function renderOutletDetailWithDevice(outlet) {
    const isMatch = outlet.current_state === outlet.expected_state;
    const matchClass = isMatch ? 'match' : 'mismatch';
    const stateIcon = isMatch ? '✓' : '⚠️';
    
    return `
        <div class="outlet-detail-card ${matchClass}">
            <div class="outlet-detail-header">
                <span>${outlet.device_name} - Outlet ${outlet.outlet}</span>
                <span class="state-indicator ${matchClass}">${stateIcon}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">IP Address:</span>
                <span class="outlet-detail-value">${outlet.ip_address}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Current State:</span>
                <span class="outlet-detail-value">${outlet.current_state.toUpperCase()}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Expected State:</span>
                <span class="outlet-detail-value">${outlet.expected_state.toUpperCase()}</span>
            </div>
            ${outlet.expected_on_from ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected ON from:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_on_from).toLocaleString()}</span>
                </div>
            ` : ''}
            ${outlet.expected_off_at ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected OFF at:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_off_at).toLocaleString()}</span>
                </div>
            ` : ''}
            ${outlet.last_state_change ? `
                <div class="timestamp-display">Last change: ${new Date(outlet.last_state_change).toLocaleString()}</div>
            ` : ''}
        </div>
    `;
}

// Render outlet detail with device info and integrated controls (for group view)
function renderOutletDetailWithDeviceAndControl(outlet, deviceControlMap) {
    const isMatch = outlet.current_state === outlet.expected_state;
    const matchClass = isMatch ? 'match' : 'mismatch';
    const stateIcon = isMatch ? '✓' : '⚠️';
    
    // Find the control device for this outlet
    const deviceKey = `${outlet.group}-${outlet.device_name}`;
    const controlDevice = deviceControlMap.get(deviceKey);
    const isReachable = controlDevice ? controlDevice.reachable : false;
    const isInitialized = controlDevice ? (controlDevice.initialized !== false) : true;
    
    // Find the specific outlet control data
    let outletControl = null;
    if (controlDevice && controlDevice.outlets) {
        outletControl = controlDevice.outlets.find(o => o.index === outlet.outlet);
    }
    
    const outletState = outletControl ? (outletControl.is_on ? 'on' : 'off') : 'unknown';
    const outletStateText = outletControl ? (outletControl.is_on ? 'ON' : 'OFF') : 'UNKNOWN';
    const outletIsOn = outletControl ? outletControl.is_on : false;
    
    // Determine schedule status
    const hasSchedule = outlet.expected_on_from || outlet.expected_off_at;
    const scheduleStatus = hasSchedule ? '📅 Scheduled' : '⚪ Manual';
    
    return `
        <div class="outlet-detail-card ${matchClass}">
            <div class="outlet-detail-header">
                <span>${outlet.device_name} - Outlet ${outlet.outlet}</span>
                <span class="state-indicator ${matchClass}">${stateIcon}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">IP Address:</span>
                <span class="outlet-detail-value">${outlet.ip_address}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Current State:</span>
                <span class="outlet-detail-value">${outlet.current_state.toUpperCase()}</span>
            </div>
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Expected State:</span>
                <span class="outlet-detail-value">${outlet.expected_state.toUpperCase()}</span>
            </div>
            ${outlet.last_state_change ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Last Updated:</span>
                    <span class="outlet-detail-value">${new Date(outlet.last_state_change).toLocaleString()}</span>
                </div>
            ` : ''}
            <div class="outlet-detail-row">
                <span class="outlet-detail-label">Schedule Status:</span>
                <span class="outlet-detail-value">${scheduleStatus}</span>
            </div>
            ${outlet.expected_on_from ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected ON from:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_on_from).toLocaleString()}</span>
                </div>
            ` : ''}
            ${outlet.expected_off_at ? `
                <div class="outlet-detail-row">
                    <span class="outlet-detail-label">Expected OFF at:</span>
                    <span class="outlet-detail-value">${new Date(outlet.expected_off_at).toLocaleString()}</span>
                </div>
            ` : ''}
            ${controlDevice ? `
                <div class="outlet-controls-inline">
                    <div class="outlet-control-buttons">
                        <button class="btn-control btn-on" 
                                onclick="controlOutlet('${outlet.group}', '${outlet.device_name}', ${outlet.outlet}, 'on')"
                                ${!isReachable || outletIsOn ? 'disabled' : ''}>
                            Turn ON
                        </button>
                        <button class="btn-control btn-off" 
                                onclick="controlOutlet('${outlet.group}', '${outlet.device_name}', ${outlet.outlet}, 'off')"
                                ${!isReachable || !outletIsOn ? 'disabled' : ''}>
                            Turn OFF
                        </button>
                    </div>
                    <div id="control-message-${sanitizeDeviceName(outlet.device_name)}-${outlet.outlet}" class="control-message-inline" style="display: none;"></div>
                </div>
            ` : ''}
        </div>
    `;
}

// Refresh health information
async function refreshHealth() {
    const healthSummary = document.getElementById('health-summary');
    const healthChecksContent = document.getElementById('health-checks-content');
    
    try {
        // Fetch health and status data in parallel
        const [healthResponse, statusResponse] = await Promise.all([
            fetch('/api/health'),
            fetch('/api/status')
        ]);
        
        const health = await healthResponse.json();
        const status = await statusResponse.json();
        
        // Update health summary
        let summaryHtml = `
            <div class="health-summary-item">
                <div class="value">${health.status === 'ok' ? '✅' : '❌'}</div>
                <div class="label">System Health</div>
            </div>
            <div class="health-summary-item">
                <div class="value">${health.config_loaded ? 'Yes' : 'No'}</div>
                <div class="label">Config Loaded</div>
            </div>
        `;
        
        // Add device group counts if available
        if (status.device_groups) {
            const enabledGroups = Object.values(status.device_groups).filter(g => g.enabled).length;
            const totalGroups = Object.keys(status.device_groups).length;
            summaryHtml += `
                <div class="health-summary-item">
                    <div class="value">${enabledGroups}/${totalGroups}</div>
                    <div class="label">Active Groups</div>
                </div>
            `;
        }
        
        // Add weather fetch time if available
        if (status.last_weather_fetch) {
            const lastFetch = new Date(status.last_weather_fetch);
            const now = new Date();
            const minutesAgo = Math.floor((now - lastFetch) / 60000);
            summaryHtml += `
                <div class="health-summary-item">
                    <div class="value">${minutesAgo}m ago</div>
                    <div class="label">Last Weather Fetch</div>
                </div>
            `;
        }
        
        healthSummary.innerHTML = summaryHtml;
        
        // Update health checks card
        let healthChecksHtml = '<div class="status-grid">';
        healthChecksHtml += `
            <div class="status-item">
                <label>Status</label>
                <value>${health.status}</value>
            </div>
            <div class="status-item">
                <label>Timestamp</label>
                <value>${new Date(health.timestamp).toLocaleString()}</value>
            </div>
            <div class="status-item">
                <label>Config Loaded</label>
                <value>${health.config_loaded ? 'Yes' : 'No'}</value>
            </div>
        `;
        healthChecksHtml += '</div>';
        healthChecksContent.innerHTML = healthChecksHtml;
        
        // Render the device health view
        await renderHealthView();
        
    } catch (e) {
        healthSummary.innerHTML = '<div class="error">Failed to load health data</div>';
        healthChecksContent.innerHTML = `<div class="error">Error: ${e.message}</div>`;
        const deviceHealthContent = document.getElementById('device-health-content');
        if (deviceHealthContent) {
            deviceHealthContent.innerHTML = `<div class="error">Error: ${e.message}</div>`;
        }
    }
}

// Refresh weather tab
async function refreshWeather() {
    const weatherInfo = document.getElementById('weather-info');
    const weatherForecastTable = document.getElementById('weather-forecast-table');
    const weatherMatTimelines = document.getElementById('weather-mat-timelines');
    
    // Conversion factor for precipitation units (25.4 mm per inch)
    const MM_PER_INCH = 25.4;
    // Default forecast hours if not configured
    const DEFAULT_FORECAST_HOURS = 12;
    
    try {
        // Fetch both weather forecast and mat forecast in parallel
        const [forecastResponse, matForecastResponse] = await Promise.all([
            fetch('/api/weather/forecast'),
            fetch('/api/weather/mat-forecast')
        ]);
        
        const forecastData = await forecastResponse.json();
        const matForecastData = await matForecastResponse.json();
        
        // Update weather summary
        let summaryHtml = '';
        
        if (forecastData.status === 'ok') {
            const lastUpdated = forecastData.last_updated ? new Date(forecastData.last_updated).toLocaleString() : 'Unknown';
            const cacheAge = forecastData.cache_age_hours ? `${forecastData.cache_age_hours.toFixed(1)} hours` : 'N/A';
            
            summaryHtml = `
                <div class="status-item">
                    <label>Provider</label>
                    <value>${forecastData.provider || 'Unknown'}</value>
                </div>
                <div class="status-item">
                    <label>Last Updated</label>
                    <value>${lastUpdated}</value>
                </div>
                <div class="status-item">
                    <label>Cache Age</label>
                    <value>${cacheAge}</value>
                </div>
                <div class="status-item">
                    <label>Weather State</label>
                    <value>${forecastData.weather_state || 'Unknown'}</value>
                </div>
                <div class="status-item">
                    <label>Forecast Hours</label>
                    <value>${forecastData.forecast_hours || (forecastData.hours ? forecastData.hours.length : 0)}</value>
                </div>
            `;
            
            if (forecastData.alerts && forecastData.alerts.length > 0) {
                summaryHtml += `
                    <div class="status-item" style="border-left-color: #e74c3c;">
                        <label>Active Alerts</label>
                        <value>${forecastData.alerts.length}</value>
                    </div>
                `;
            }
        } else {
            summaryHtml = `
                <div class="status-item" style="border-left-color: #f39c12;">
                    <label>Status</label>
                    <value>${forecastData.status}</value>
                </div>
                <div class="status-item">
                    <label>Reason</label>
                    <value>${forecastData.reason || 'No data available'}</value>
                </div>
            `;
        }
        
        weatherInfo.innerHTML = summaryHtml;
        
        // Update forecast table
        if (forecastData.status === 'ok' && forecastData.hours && forecastData.hours.length > 0) {
            let tableHtml = `
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f8f9fa; border-bottom: 2px solid #ddd;">
                            <th style="padding: 10px; text-align: left;">Time</th>
                            <th style="padding: 10px; text-align: left;">Temp (°F)</th>
                            <th style="padding: 10px; text-align: left;">Precip (in)</th>
                            <th style="padding: 10px; text-align: left;">Type</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            // Limit the number of hours displayed to forecast_hours
            // Use configured forecast_hours, with fallback to default
            // Ensure we have a positive integer value
            let forecastHours = forecastData.forecast_hours ?? DEFAULT_FORECAST_HOURS;
            if (!Number.isInteger(forecastHours) || forecastHours < 1) {
                forecastHours = DEFAULT_FORECAST_HOURS;
            }
            const hoursToDisplay = forecastData.hours.slice(0, forecastHours);
            
            for (const hour of hoursToDisplay) {
                const hourTime = new Date(hour.time);
                const time = hourTime.toLocaleString();
                const temp = hour.temp_f !== null ? hour.temp_f.toFixed(1) : 'N/A';
                // Convert precipitation from mm to inches
                const precipMm = hour.precip_intensity !== null ? hour.precip_intensity : 0;
                const precipInches = precipMm / MM_PER_INCH;
                const precip = precipInches.toFixed(2);
                const precipType = hour.precip_type || '-';
                
                tableHtml += `
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 8px;">${time}</td>
                        <td style="padding: 8px;">${temp}</td>
                        <td style="padding: 8px;">${precip}</td>
                        <td style="padding: 8px;">${precipType}</td>
                    </tr>
                `;
            }
            
            tableHtml += `
                    </tbody>
                </table>
            `;
            
            weatherForecastTable.innerHTML = tableHtml;
        } else {
            weatherForecastTable.innerHTML = `<p>${forecastData.reason || 'No forecast data available'}</p>`;
        }
        
        // Update mat timelines
        if (matForecastData.status === 'ok' && matForecastData.groups) {
            let timelinesHtml = '';
            
            for (const [groupName, windows] of Object.entries(matForecastData.groups)) {
                timelinesHtml += `
                    <div class="group-card">
                        <h3>${groupName}</h3>
                `;
                
                if (windows.length === 0) {
                    timelinesHtml += '<p>No predicted activity in forecast horizon.</p>';
                } else {
                    timelinesHtml += `
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background: #f8f9fa; border-bottom: 2px solid #ddd;">
                                    <th style="padding: 8px; text-align: left;">State</th>
                                    <th style="padding: 8px; text-align: left;">Start</th>
                                    <th style="padding: 8px; text-align: left;">End</th>
                                    <th style="padding: 8px; text-align: left;">Reason</th>
                                </tr>
                            </thead>
                            <tbody>
                    `;
                    
                    for (const window of windows) {
                        const stateColor = window.state === 'on' ? '#27ae60' : '#95a5a6';
                        const stateIcon = window.state === 'on' ? '✅' : '⭕';
                        
                        timelinesHtml += `
                            <tr style="border-bottom: 1px solid #eee;">
                                <td style="padding: 8px; color: ${stateColor}; font-weight: 600;">
                                    ${stateIcon} ${window.state.toUpperCase()}
                                </td>
                                <td style="padding: 8px;">${new Date(window.start).toLocaleString()}</td>
                                <td style="padding: 8px;">${new Date(window.end).toLocaleString()}</td>
                                <td style="padding: 8px;">${window.reason}</td>
                            </tr>
                        `;
                    }
                    
                    timelinesHtml += `
                            </tbody>
                        </table>
                    `;
                }
                
                timelinesHtml += '</div>';
            }
            
            weatherMatTimelines.innerHTML = timelinesHtml;
        } else {
            weatherMatTimelines.innerHTML = `<p>${matForecastData.reason || 'No mat forecast data available'}</p>`;
        }
        
    } catch (e) {
        weatherInfo.innerHTML = `<div class="error">Failed to load weather data: ${e.message}</div>`;
        weatherForecastTable.innerHTML = `<div class="error">Error: ${e.message}</div>`;
        weatherMatTimelines.innerHTML = `<div class="error">Error: ${e.message}</div>`;
    }
}

// Control a device outlet
async function controlOutlet(group, deviceName, outletIndex, action) {
    // Try to find the inline message div first, fall back to old location
    let messageId = `control-message-${sanitizeDeviceName(deviceName)}-${outletIndex}`;
    let messageDiv = document.getElementById(messageId);
    
    if (!messageDiv) {
        messageId = 'control-message-' + sanitizeDeviceName(deviceName);
        messageDiv = document.getElementById(messageId);
    }
    
    if (!messageDiv) {
        // Create a toast notification if message div not found
        showToast(`Sending ${action.toUpperCase()} command...`, 'info');
    } else {
        // Show loading message
        messageDiv.className = messageDiv.classList.contains('control-message-inline') ? 'control-message-inline' : 'control-message';
        messageDiv.style.display = 'block';
        messageDiv.textContent = `Sending ${action.toUpperCase()} command...`;
    }
    
    try {
        const response = await fetch('/api/devices/control', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group: group,
                device: deviceName,
                outlet: outletIndex,
                action: action
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const outletText = outletIndex !== null ? ` outlet ${outletIndex}` : '';
            const successMsg = `✓ Successfully turned ${action.toUpperCase()}${outletText}`;
            
            if (messageDiv) {
                messageDiv.className = messageDiv.classList.contains('control-message-inline') ? 'control-message-inline success' : 'control-message success';
                messageDiv.textContent = successMsg;
            } else {
                showToast(successMsg, 'success');
            }
            
            // Refresh health view after 1 second
            setTimeout(() => {
                renderHealthView();
            }, 1000);
        } else {
            const errorMsg = `✗ Failed: ${result.error || 'Unknown error'}`;
            
            if (messageDiv) {
                messageDiv.className = messageDiv.classList.contains('control-message-inline') ? 'control-message-inline error' : 'control-message error';
                messageDiv.textContent = errorMsg;
            } else {
                showToast(errorMsg, 'error');
            }
        }
        
        // Hide message after 5 seconds
        if (messageDiv) {
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        }
        
    } catch (e) {
        console.error('Control request failed:', e);
        const errorMsg = `✗ Error: ${e.message}`;
        
        if (messageDiv) {
            messageDiv.className = messageDiv.classList.contains('control-message-inline') ? 'control-message-inline error' : 'control-message error';
            messageDiv.textContent = errorMsg;
            
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        } else {
            showToast(errorMsg, 'error');
        }
    }
}

// Control all outlets in a group
async function controlGroup(groupName, action) {
    const messageId = `group-control-message-${sanitizeDeviceName(groupName)}`;
    const messageDiv = document.getElementById(messageId);
    
    if (!messageDiv) {
        showToast(`Sending ${action.toUpperCase()} command to group...`, 'info');
    } else {
        // Show loading message
        messageDiv.className = 'control-message';
        messageDiv.style.display = 'block';
        messageDiv.textContent = `Sending ${action.toUpperCase()} command to all outlets in group...`;
    }
    
    try {
        const response = await fetch(`/api/groups/${groupName}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: action
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const successMsg = `✓ Group ${action.toUpperCase()}: ${result.successful} successful, ${result.failed} failed`;
            
            if (messageDiv) {
                messageDiv.className = 'control-message success';
                messageDiv.textContent = successMsg;
            } else {
                showToast(successMsg, 'success');
            }
            
            // Refresh health view after 1 second
            setTimeout(() => {
                renderHealthView();
            }, 1000);
        } else {
            const errorMsg = `✗ Failed to control group: ${result.error || 'Unknown error'}`;
            
            if (messageDiv) {
                messageDiv.className = 'control-message error';
                messageDiv.textContent = errorMsg;
            } else {
                showToast(errorMsg, 'error');
            }
        }
        
        // Hide message after 5 seconds
        if (messageDiv) {
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        }
        
    } catch (e) {
        console.error('Group control request failed:', e);
        const errorMsg = `✗ Error: ${e.message}`;
        
        if (messageDiv) {
            messageDiv.className = 'control-message error';
            messageDiv.textContent = errorMsg;
            
            setTimeout(() => {
                messageDiv.style.display = 'none';
            }, 5000);
        } else {
            showToast(errorMsg, 'error');
        }
    }
}

// Show toast notification
function showToast(message, type) {
    // Create toast if it doesn't exist
    let toast = document.getElementById('toast-notification');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast-notification';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }
    
    // Set message and type
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    // Hide after 4 seconds
    setTimeout(() => {
        toast.className = 'toast';
    }, 4000);
}

// Extract plain config values from annotated config (recursively)
function extractConfigValues(annotated) {
    if (!annotated || typeof annotated !== 'object') {
        return annotated;
    }
    
    // Check if this is a field with metadata
    if (annotated.hasOwnProperty('value') && annotated.hasOwnProperty('source')) {
        return annotated.value;
    }
    
    // Recursively process nested objects
    const result = {};
    for (const [key, value] of Object.entries(annotated)) {
        result[key] = extractConfigValues(value);
    }
    return result;
}

// Get field metadata from annotated config
function getFieldMetadata(annotated, path) {
    const parts = path.split('.');
    let current = annotated;
    
    for (const part of parts) {
        if (!current || typeof current !== 'object') {
            return null;
        }
        current = current[part];
    }
    
    if (current && current.hasOwnProperty('value') && current.hasOwnProperty('source')) {
        return current;
    }
    return null;
}

// Form field definitions with labels and types
const FORM_FIELDS = {
    'Location': [
        { path: 'location.latitude', label: 'Latitude', type: 'number', step: 'any' },
        { path: 'location.longitude', label: 'Longitude', type: 'number', step: 'any' },
        { path: 'location.timezone', label: 'Timezone', type: 'text' }
    ],
    'Weather': [
        { path: 'weather_api.enabled', label: 'Weather Enabled', type: 'checkbox' },
        { path: 'weather_api.provider', label: 'Weather Provider', type: 'select', options: ['open-meteo', 'openweathermap'] },
        { path: 'weather_api.openweathermap.api_key', label: 'OpenWeatherMap API Key', type: 'password' }
    ],
    'Device Credentials': [
        { path: 'devices.credentials.username', label: 'Tapo Username', type: 'text', 
          helper: '🔧 Enter your Tapo account email/username. Changes require restart to apply.' },
        { path: 'devices.credentials.password', label: 'Tapo Password', type: 'password',
          helper: '🔧 Enter your Tapo account password. Changes require restart to apply.' }
    ],
    'Scheduler': [
        { path: 'scheduler.check_interval_minutes', label: 'Check Interval (minutes)', type: 'number',
          helper: 'How often the scheduler checks weather and evaluates schedules (default: 10)' },
        { path: 'scheduler.forecast_hours', label: 'Forecast Hours', type: 'number',
          helper: 'How far ahead to look for weather conditions (default: 12)' }
    ],
    'Safety Limits': [
        { path: 'safety.max_runtime_hours', label: 'Max Runtime (hours)', type: 'number', step: '0.1',
          helper: 'Global default maximum continuous runtime. Can be overridden per schedule.' },
        { path: 'safety.cooldown_minutes', label: 'Cooldown (minutes)', type: 'number',
          helper: 'Global default cooldown period after max runtime. Can be overridden per schedule.' }
    ],
    'Logging': [
        { path: 'logging.level', label: 'Log Level', type: 'select', options: ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] }
    ],
    'Health & Reboot': [
        { path: 'health_check.interval_hours', label: 'Health Check Interval (hours)', type: 'number', step: '0.1' },
        { path: 'health_check.max_consecutive_failures', label: 'Max Consecutive Failures', type: 'number' },
        { path: 'reboot.pause_seconds', label: 'Reboot Pause (seconds)', type: 'number' },
        { path: 'health_server.enabled', label: 'Enable Health Check API', type: 'checkbox' },
        { path: 'health_server.host', label: 'Health Check API Host', type: 'text' },
        { path: 'health_server.port', label: 'Health Check API Port (default: 4329)', type: 'number' }
    ],
    'Notifications - Global': [
        { path: 'notifications.required', label: 'Notifications Required', type: 'checkbox' },
        { path: 'notifications.test_on_startup', label: 'Test Notifications on Startup', type: 'checkbox' }
    ],
    'Notifications - Email': [
        { path: 'notifications.email.enabled', label: 'Email Enabled', type: 'checkbox' },
        { path: 'notifications.email.smtp_host', label: 'SMTP Host', type: 'text' },
        { path: 'notifications.email.smtp_port', label: 'SMTP Port', type: 'number' },
        { path: 'notifications.email.smtp_username', label: 'SMTP Username', type: 'text' },
        { path: 'notifications.email.smtp_password', label: 'SMTP Password', type: 'password' },
        { path: 'notifications.email.from_email', label: 'From Email', type: 'email' },
        { path: 'notifications.email.to_emails', label: 'To Emails (comma-separated)', type: 'text' },
        { path: 'notifications.email.use_tls', label: 'Use TLS', type: 'checkbox' }
    ],
    'Notifications - Webhook': [
        { path: 'notifications.webhook.enabled', label: 'Webhook Enabled', type: 'checkbox' },
        { path: 'notifications.webhook.url', label: 'Webhook URL', type: 'url' }
    ],
    'Web UI': [
        { path: 'web.bind_host', label: 'Bind Host', type: 'text' },
        { path: 'web.port', label: 'Port', type: 'number' }
    ]
};

// Create a form field
function createFormField(fieldDef, metadata, value) {
    const isReadonly = metadata && metadata.readonly;
    const envVar = metadata && metadata.env_var;
    
    let inputHtml = '';
    const fieldId = 'field-' + fieldDef.path.replace(/\./g, '-');
    
    if (fieldDef.type === 'checkbox') {
        const checked = value ? 'checked' : '';
        const disabled = isReadonly ? 'disabled' : '';
        inputHtml = `<input type="checkbox" id="${fieldId}" ${checked} ${disabled}>`;
    } else if (fieldDef.type === 'select') {
        const disabled = isReadonly ? 'disabled' : '';
        inputHtml = `<select id="${fieldId}" ${disabled}>`;
        for (const option of fieldDef.options) {
            const selected = value === option ? 'selected' : '';
            inputHtml += `<option value="${option}" ${selected}>${option}</option>`;
        }
        inputHtml += '</select>';
    } else {
        const type = fieldDef.type;
        const disabled = isReadonly ? 'disabled' : '';
        const step = fieldDef.step ? `step="${fieldDef.step}"` : '';
        const min = fieldDef.min ? `min="${fieldDef.min}"` : '';
        const max = fieldDef.max ? `max="${fieldDef.max}"` : '';
        const displayValue = (type === 'password' && value) ? '********' : (value || '');
        inputHtml = `<input type="${type}" id="${fieldId}" value="${displayValue}" ${disabled} ${step} ${min} ${max}>`;
    }
    
    let helperHtml = '';
    if (isReadonly && envVar) {
        helperHtml = `<div class="helper-text">Set via env: <code>${envVar}</code></div>`;
    } else if (fieldDef.helper) {
        helperHtml = `<div class="helper-text">${fieldDef.helper}</div>`;
    }
    
    return `
        <div class="form-group">
            <label for="${fieldId}">${fieldDef.label}</label>
            ${inputHtml}
            ${helperHtml}
        </div>
    `;
}

// Build Device Groups section
function buildDeviceGroupsSection(config) {
    const groups = config.devices?.groups || {};
    let html = '<h3>Device Groups</h3>';
    html += '<div id="device-groups-container">';
    
    // Render each group
    for (const [groupKey, groupConfig] of Object.entries(groups)) {
        html += buildDeviceGroupCard(groupKey, groupConfig);
    }
    
    html += '</div>';
    html += '<div style="margin-top: 15px;"><button type="button" onclick="addDeviceGroup()" style="background: #27ae60;">➕ Add Group</button></div>';
    
    return html;
}

// Build a single device group card
function buildDeviceGroupCard(groupKey, groupConfig) {
    const groupId = `group-${groupKey.replace(/[^a-zA-Z0-9]/g, '-')}`;
    const enabled = groupConfig.enabled !== false;  // Default true
    const items = groupConfig.items || [];
    
    let html = `<div class="device-group-card" id="${groupId}" data-group-key="${groupKey}" style="background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; border: 2px solid #ddd;">`;
    
    // Header with group name and enabled checkbox
    html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px;">';
    html += '<div style="flex: 1;">';
    html += `<label style="font-weight: 600; margin-right: 10px;">Group Name:</label>`;
    html += `<input type="text" class="group-name-input" value="${groupKey}" style="padding: 8px; font-size: 16px; font-weight: 600; border: 1px solid #ddd; border-radius: 4px; min-width: 250px;" onchange="updateGroupKey('${groupKey}', this.value)">`;
    html += '</div>';
    html += '<div>';
    html += `<label style="margin-right: 10px;"><input type="checkbox" class="group-enabled-input" ${enabled ? 'checked' : ''}> Enabled</label>`;
    html += `<button type="button" onclick="deleteDeviceGroup('${groupKey}')" style="background: #e74c3c; margin-left: 10px;">🗑️ Delete Group</button>`;
    html += '</div>';
    html += '</div>';
    
    // Items table
    html += '<div class="group-items-container">';
    html += '<table style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr style="background: #ecf0f1;">';
    html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Device Name</th>';
    html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">IP Address</th>';
    html += '<th style="padding: 10px; text-align: left; border: 1px solid #ddd;">Outlets (CSV)</th>';
    html += '<th style="padding: 10px; text-align: center; border: 1px solid #ddd; width: 100px;">Actions</th>';
    html += '</tr></thead>';
    html += '<tbody class="group-items-tbody">';
    
    items.forEach((item, idx) => {
        html += buildDeviceItemRow(groupKey, item, idx);
    });
    
    html += '</tbody>';
    html += '</table>';
    html += `<div style="margin-top: 10px;"><button type="button" onclick="addDeviceItem('${groupKey}')" style="background: #3498db;">➕ Add Device</button></div>`;
    html += '</div>';
    
    html += '</div>';
    return html;
}

// Build a single device item row
function buildDeviceItemRow(groupKey, item, idx) {
    const outlets = item.outlets ? item.outlets.join(', ') : '';
    const rowId = `item-${groupKey}-${idx}`;
    
    let html = `<tr id="${rowId}" class="device-item-row" data-group-key="${groupKey}">`;
    html += `<td style="padding: 10px; border: 1px solid #ddd;"><input type="text" class="item-name-input" value="${item.name || ''}" placeholder="Device Name (required)" style="width: 100%; padding: 5px; border: 1px solid #ddd; border-radius: 3px;"></td>`;
    html += `<td style="padding: 10px; border: 1px solid #ddd;"><input type="text" class="item-ip-input" value="${item.ip_address || ''}" placeholder="192.168.1.100 (required)" style="width: 100%; padding: 5px; border: 1px solid #ddd; border-radius: 3px;"></td>`;
    html += `<td style="padding: 10px; border: 1px solid #ddd;"><input type="text" class="item-outlets-input" value="${outlets}" placeholder="0, 1 (optional)" style="width: 100%; padding: 5px; border: 1px solid #ddd; border-radius: 3px;"></td>`;
    html += `<td style="padding: 10px; border: 1px solid #ddd; text-align: center;"><button type="button" onclick="deleteDeviceItem('${groupKey}', ${idx})" style="background: #e74c3c; padding: 5px 10px;">🗑️</button></td>`;
    html += '</tr>';
    return html;
}

// Add a new device group
function addDeviceGroup() {
    const newGroupName = prompt('Enter a name for the new device group:');
    if (!newGroupName || newGroupName.trim() === '') {
        return;
    }
    
    // Normalize group name (replace spaces with underscores, lowercase)
    const normalizedName = newGroupName.trim().toLowerCase().replace(/\\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    
    // Check if group already exists
    const container = document.getElementById('device-groups-container');
    const existingGroups = container.querySelectorAll('.device-group-card');
    for (const card of existingGroups) {
        if (card.dataset.groupKey === normalizedName) {
            alert(`A group named "${normalizedName}" already exists!`);
            return;
        }
    }
    
    // Create new group card
    const newGroupConfig = {
        enabled: true,
        items: []
    };
    
    const newCardHtml = buildDeviceGroupCard(normalizedName, newGroupConfig);
    container.insertAdjacentHTML('beforeend', newCardHtml);
}

// Delete a device group
function deleteDeviceGroup(groupKey) {
    if (!confirm(`Are you sure you want to delete group '${groupKey}'?`)) {
        return;
    }
    
    const groupCard = document.querySelector(`.device-group-card[data-group-key="${groupKey}"]`);
    if (groupCard) {
        groupCard.remove();
    }
}

// Add a device item to a group
function addDeviceItem(groupKey) {
    const groupCard = document.querySelector(`.device-group-card[data-group-key="${groupKey}"]`);
    if (!groupCard) return;
    
    const tbody = groupCard.querySelector('.group-items-tbody');
    const currentItems = tbody.querySelectorAll('.device-item-row').length;
    
    const newItem = {
        name: '',
        ip_address: '',
        outlets: []
    };
    
    const newRowHtml = buildDeviceItemRow(groupKey, newItem, currentItems);
    tbody.insertAdjacentHTML('beforeend', newRowHtml);
}

// Delete a device item
function deleteDeviceItem(groupKey, itemIdx) {
    const groupCard = document.querySelector(`.device-group-card[data-group-key="${groupKey}"]`);
    if (!groupCard) return;
    
    const rows = groupCard.querySelectorAll('.device-item-row');
    if (rows[itemIdx]) {
        rows[itemIdx].remove();
    }
}

// Update group key when group name is changed
function updateGroupKey(oldKey, newKey) {
    if (!newKey || newKey.trim() === '') {
        alert('Group name cannot be empty!');
        // Restore old value
        const groupCard = document.querySelector(`.device-group-card[data-group-key="${oldKey}"]`);
        if (groupCard) {
            const input = groupCard.querySelector('.group-name-input');
            if (input) input.value = oldKey;
        }
        return;
    }
    
    // Normalize new key
    const normalizedKey = newKey.trim().toLowerCase().replace(/\\s+/g, '_').replace(/[^a-z0-9_]/g, '');
    
    // Check if already exists
    if (normalizedKey !== oldKey) {
        const existingCard = document.querySelector(`.device-group-card[data-group-key="${normalizedKey}"]`);
        if (existingCard) {
            alert(`A group named "${normalizedKey}" already exists!`);
            // Restore old value
            const groupCard = document.querySelector(`.device-group-card[data-group-key="${oldKey}"]`);
            if (groupCard) {
                const input = groupCard.querySelector('.group-name-input');
                if (input) input.value = oldKey;
            }
            return;
        }
    }
    
    // Update the card's data attribute
    const groupCard = document.querySelector(`.device-group-card[data-group-key="${oldKey}"]`);
    if (groupCard) {
        groupCard.dataset.groupKey = normalizedKey;
        // Update input value to normalized version
        const input = groupCard.querySelector('.group-name-input');
        if (input) input.value = normalizedKey;
    }
}

// Build the form from annotated config
function buildConfigForm(annotatedConfig) {
    const config = extractConfigValues(annotatedConfig);
    const form = document.getElementById('config-form');
    let html = '';
    
    for (const [sectionName, fields] of Object.entries(FORM_FIELDS)) {
        html += `<h3>${sectionName}</h3>`;
        
        for (const fieldDef of fields) {
            const metadata = getFieldMetadata(annotatedConfig, fieldDef.path);
            const value = getValueByPath(config, fieldDef.path);
            
            // Special handling for to_emails (array to comma-separated string)
            let displayValue = value;
            if (fieldDef.path === 'notifications.email.to_emails' && Array.isArray(value)) {
                displayValue = value.join(', ');
            }
            
            html += createFormField(fieldDef, metadata, displayValue);
        }
    }
    
    // Add Device Groups section after Device Credentials
    html += buildDeviceGroupsSection(config);
    
    form.innerHTML = html;
    
    // Show environment overrides info if any
    showEnvOverridesInfo(annotatedConfig);
}

// Get value by dot-separated path
function getValueByPath(obj, path) {
    const parts = path.split('.');
    let current = obj;
    
    for (const part of parts) {
        if (current && typeof current === 'object' && part in current) {
            current = current[part];
        } else {
            return undefined;
        }
    }
    
    return current;
}

// Set value by dot-separated path
function setValueByPath(obj, path, value) {
    const parts = path.split('.');
    let current = obj;
    
    // Guard against prototype pollution
    const dangerousKeys = ['__proto__', 'constructor', 'prototype'];
    
    for (let i = 0; i < parts.length - 1; i++) {
        const part = parts[i];
        
        // Prevent prototype pollution
        if (dangerousKeys.includes(part)) {
            console.error('Attempt to set dangerous property:', part);
            return;
        }
        
        if (!(part in current)) {
            current[part] = {};
        }
        current = current[part];
    }
    
    const finalPart = parts[parts.length - 1];
    
    // Prevent prototype pollution on final key
    if (dangerousKeys.includes(finalPart)) {
        console.error('Attempt to set dangerous property:', finalPart);
        return;
    }
    
    current[finalPart] = value;
}

// Collect form values into config object
function collectFormValues() {
    const config = {};
    
    for (const [sectionName, fields] of Object.entries(FORM_FIELDS)) {
        for (const fieldDef of fields) {
            const fieldId = 'field-' + fieldDef.path.replace(/\./g, '-');
            const element = document.getElementById(fieldId);
            
            if (!element) continue;
            
            let value;
            if (fieldDef.type === 'checkbox') {
                value = element.checked;
            } else if (fieldDef.type === 'number') {
                value = element.value ? parseFloat(element.value) : 0;
            } else {
                value = element.value;
            }
            
            // Special handling for to_emails (comma-separated string to array)
            if (fieldDef.path === 'notifications.email.to_emails' && typeof value === 'string') {
                value = value.split(',').map(e => e.trim()).filter(e => e.length > 0);
            }
            
            setValueByPath(config, fieldDef.path, value);
        }
    }
    
    // Collect device groups
    config.devices = config.devices || {};
    config.devices.groups = collectDeviceGroups();
    
    return config;
}

// Collect device groups from the UI
function collectDeviceGroups() {
    const groups = {};
    const groupCards = document.querySelectorAll('.device-group-card');
    
    groupCards.forEach(card => {
        const groupKey = card.dataset.groupKey;
        const enabledInput = card.querySelector('.group-enabled-input');
        const enabled = enabledInput ? enabledInput.checked : true;
        
        // Collect items
        const items = [];
        const itemRows = card.querySelectorAll('.device-item-row');
        
        itemRows.forEach(row => {
            const nameInput = row.querySelector('.item-name-input');
            const ipInput = row.querySelector('.item-ip-input');
            const outletsInput = row.querySelector('.item-outlets-input');
            
            const name = nameInput ? nameInput.value.trim() : '';
            const ip_address = ipInput ? ipInput.value.trim() : '';
            const outletsStr = outletsInput ? outletsInput.value.trim() : '';
            
            // Only include items with both name and IP
            if (name && ip_address) {
                const item = {
                    name: name,
                    ip_address: ip_address
                };
                
                // Parse outlets if provided
                if (outletsStr) {
                    const outlets = outletsStr.split(',')
                        .map(s => parseInt(s.trim()))
                        .filter(n => !isNaN(n) && n >= 0);
                    
                    if (outlets.length > 0) {
                        item.outlets = outlets;
                    }
                }
                
                items.push(item);
            }
        });
        
        groups[groupKey] = {
            enabled: enabled,
            items: items
        };
    });
    
    return groups;
}

// Show environment overrides info
function showEnvOverridesInfo(annotatedConfig) {
    const container = document.getElementById('env-overrides-info');
    const overrides = collectEnvOverrides(annotatedConfig);
    
    if (overrides.length > 0) {
        let html = '<div class="card" style="background: #e8f4f8; border-left: 4px solid #17a2b8;">';
        html += '<h3 style="margin-top: 0;">🔒 Environment Variable Overrides</h3>';
        html += '<p style="margin-bottom: 15px;">The following settings are overridden by environment variables and are read-only in this form:</p>';
        html += '<div class="status-grid">';
        
        for (const override of overrides) {
            let displayValue = override.value;
            // Mask sensitive values
            if (override.path.includes('password') || override.path.includes('api_key')) {
                displayValue = '********';
            }
            
            html += `
                <div class="status-item" style="border-left-color: #17a2b8;">
                    <label>${override.path}</label>
                    <value><code>${override.env_var}</code> = ${displayValue}</value>
                </div>
            `;
        }
        
        html += '</div></div>';
        container.innerHTML = html;
    } else {
        container.innerHTML = '';
    }
}

// Collect environment overrides from annotated config
function collectEnvOverrides(annotated, path = '') {
    const overrides = [];
    
    if (!annotated || typeof annotated !== 'object') {
        return overrides;
    }
    
    // Check if this is a field with env override
    if (annotated.source === 'env' && annotated.env_var) {
        overrides.push({
            path: path,
            env_var: annotated.env_var,
            value: annotated.value
        });
        return overrides;
    }
    
    // Recursively process nested objects
    for (const [key, value] of Object.entries(annotated)) {
        const newPath = path ? `${path}.${key}` : key;
        overrides.push(...collectEnvOverrides(value, newPath));
    }
    
    return overrides;
}

// Load configuration
async function loadConfig() {
    const message = document.getElementById('config-message');
    message.innerHTML = '';
    
    try {
        const response = await fetch('/api/config');
        const annotatedConfig = await response.json();
        
        // Store the last full config for merging during save
        lastAnnotatedConfig = annotatedConfig;
        lastRawConfig = extractConfigValues(annotatedConfig);
        
        // Build the form
        buildConfigForm(annotatedConfig);
        
    } catch (e) {
        message.innerHTML = `<div class="error">Failed to load configuration: ${e.message}</div>`;
    }
}

// Save configuration
async function saveConfig() {
    const message = document.getElementById('config-message');
    message.innerHTML = '';
    
    try {
        // Ensure we have a baseline config to merge into
        if (!lastRawConfig) {
            // If for some reason we don't have lastRawConfig, fetch it now
            try {
                const response = await fetch('/api/config');
                const annotatedConfig = await response.json();
                lastAnnotatedConfig = annotatedConfig;
                lastRawConfig = extractConfigValues(annotatedConfig);
            } catch (fetchError) {
                message.innerHTML = '<div class="error">❌ Error: Could not load current configuration. Please reload the page and try again.</div>';
                return;
            }
        }
        
        // Collect form values (these are the edited values)
        const formConfig = collectFormValues();
        
        // Merge form values into the last raw config to ensure all required sections are present
        // Use structuredClone to avoid modifying lastRawConfig
        const fullConfig = deepMerge(structuredClone(lastRawConfig), formConfig);
        
        // Send the full merged config to API
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(fullConfig)
        });
        
        const result = await response.json();
        
        if (result.status === 'ok') {
            // Update lastRawConfig with the successfully saved config
            lastRawConfig = fullConfig;
            
            message.innerHTML = '<div class="success">✅ Configuration saved successfully! Restarting...</div>';
            
            // Trigger restart after a short delay to let the message render
            setTimeout(async () => {
                try {
                    await fetch('/api/restart', {
                        method: 'POST'
                    });
                    // After restart is triggered, show additional message
                    message.innerHTML = '<div class="success">✅ Configuration saved! Application is restarting. This page will become unavailable temporarily.</div>';
                } catch (e) {
                    // Connection will be lost when the process exits, this is expected
                    message.innerHTML = '<div class="success">✅ Configuration saved! Application is restarting. Please wait a moment and refresh the page.</div>';
                }
            }, 500);
        } else {
            message.innerHTML = `<div class="error">❌ Failed to save: ${result.message}</div>`;
        }
        
    } catch (e) {
        message.innerHTML = `<div class="error">❌ Error: ${e.message}</div>`;
    }
}

// Vacation mode management
async function refreshVacationMode() {
    try {
        const response = await fetch('/api/vacation_mode');
        const data = await response.json();
        
        const toggle = document.getElementById('vacation-mode-toggle');
        const status = document.getElementById('vacation-mode-status');
        
        if (toggle && status) {
            toggle.checked = data.enabled;
            updateVacationModeUI(data.enabled);
        }
    } catch (e) {
        console.error('Failed to fetch vacation mode:', e);
    }
}

function updateVacationModeUI(enabled) {
    const status = document.getElementById('vacation-mode-status');
    const card = document.getElementById('vacation-mode-card');
    
    if (enabled) {
        status.textContent = '🏖️ Vacation Mode Active';
        status.style.color = '#f39c12';
        if (card) {
            card.style.borderLeft = '4px solid #f39c12';
        }
    } else {
        status.textContent = '✓ Normal Operation';
        status.style.color = '#27ae60';
        if (card) {
            card.style.borderLeft = '4px solid #27ae60';
        }
    }
}

async function toggleVacationMode(enabled) {
    const messageDiv = document.getElementById('vacation-mode-message');
    
    // Show confirmation dialog
    const action = enabled ? 'enable' : 'disable';
    const message = enabled 
        ? 'Enable Vacation Mode?\n\nThis will:\n• Disable all schedules\n• Turn OFF all devices\n• Manual control will still work'
        : 'Disable Vacation Mode?\n\nThis will:\n• Re-enable all schedules\n• Resume normal automated operation';
    
    if (!confirm(message)) {
        // Revert toggle
        document.getElementById('vacation-mode-toggle').checked = !enabled;
        return;
    }
    
    if (messageDiv) {
        messageDiv.style.display = 'block';
        messageDiv.className = 'info';
        messageDiv.textContent = `${enabled ? 'Enabling' : 'Disabling'} vacation mode...`;
    }
    
    try {
        const response = await fetch('/api/vacation_mode', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: enabled })
        });
        
        const result = await response.json();
        
        if (result.success) {
            updateVacationModeUI(enabled);
            if (messageDiv) {
                messageDiv.className = 'success';
                messageDiv.textContent = `✓ Vacation mode ${enabled ? 'enabled' : 'disabled'} successfully`;
                setTimeout(() => {
                    messageDiv.style.display = 'none';
                }, 3000);
            }
        } else {
            if (messageDiv) {
                messageDiv.className = 'error';
                messageDiv.textContent = `✗ Failed to ${action} vacation mode: ${result.error || 'Unknown error'}`;
            }
            // Revert toggle
            document.getElementById('vacation-mode-toggle').checked = !enabled;
        }
    } catch (e) {
        console.error('Failed to toggle vacation mode:', e);
        if (messageDiv) {
            messageDiv.className = 'error';
            messageDiv.textContent = `✗ Error: ${e.message}`;
        }
        // Revert toggle
        document.getElementById('vacation-mode-toggle').checked = !enabled;
    }
}

// Schedule management functions
async function refreshSchedules() {
    const schedulesContent = document.getElementById('schedules-content');
    const solarTimesCard = document.getElementById('solar-times-card');
    const solarTimesContent = document.getElementById('solar-times-content');
    
    try {
        // Fetch config to get all groups and schedules
        const configResponse = await fetch('/api/config');
        const annotatedConfig = await configResponse.json();
        const config = extractConfigValues(annotatedConfig);
        
        const groups = config.devices?.groups;
        if (!groups || Object.keys(groups).length === 0) {
            schedulesContent.innerHTML = '<p>No device groups configured.</p>';
            return;
        }
        
        // Fetch solar times
        let solarTimes = null;
        try {
            const solarResponse = await fetch('/api/solar_times');
            if (solarResponse.ok) {
                solarTimes = await solarResponse.json();
                if (solarTimes && !solarTimes.error) {
                    solarTimesCard.style.display = 'block';
                    let solarHtml = `
                        <div class="status-item">
                            <label>Date</label>
                            <value>${solarTimes.date}</value>
                        </div>
                        <div class="status-item">
                            <label>☀️ Sunrise</label>
                            <value>${solarTimes.sunrise}</value>
                        </div>
                        <div class="status-item">
                            <label>🌙 Sunset</label>
                            <value>${solarTimes.sunset}</value>
                        </div>
                        <div class="status-item">
                            <label>Timezone</label>
                            <value>${solarTimes.timezone}</value>
                        </div>
                    `;
                    solarTimesContent.innerHTML = solarHtml;
                }
            }
        } catch (e) {
            console.error('Failed to fetch solar times:', e);
        }
        
        let html = '';
        
        for (const [groupName, groupConfig] of Object.entries(groups)) {
            const schedules = groupConfig.schedules || [];
            const groupEnabled = groupConfig.enabled !== false;
            
            html += `<div class="schedule-group-card">
                <div class="schedule-group-header">
                    <h3>${groupName}</h3>
                    <span class="group-status-badge ${groupEnabled ? 'enabled' : 'disabled'}">
                        ${groupEnabled ? '✓ Enabled' : '⚪ Disabled'}
                    </span>
                </div>`;
            
            if (schedules.length === 0) {
                html += '<p class="no-schedules">No schedules configured for this group.</p>';
            } else {
                html += '<div class="schedules-list">';
                schedules.forEach((schedule, index) => {
                    html += renderScheduleCard(groupName, schedule, index, solarTimes);
                });
                html += '</div>';
            }
            
            html += `<div class="schedule-actions">
                <button class="btn-add-schedule" onclick="showAddScheduleDialog('${groupName}')">
                    ➕ Add Schedule
                </button>
            </div>`;
            
            html += '</div>';
        }
        
        schedulesContent.innerHTML = html;
        
    } catch (e) {
        schedulesContent.innerHTML = `<div class="error">Failed to load schedules: ${e.message}</div>`;
    }
}

function renderScheduleCard(groupName, schedule, index, solarTimes) {
    const enabled = schedule.enabled !== false;
    const priority = schedule.priority || 'normal';
    const days = schedule.days || [1,2,3,4,5,6,7];
    const daysText = formatDays(days);
    const isAllDay = schedule.all_day === true;
    
    // Format ON/OFF time
    let timeHtml = '';
    if (isAllDay) {
        timeHtml = `
            <div class="schedule-time-row">
                <span class="schedule-time-label">Time:</span>
                <span class="schedule-time-value all-day-badge">🕐 All Day (24 hours)</span>
            </div>
        `;
    } else {
        const onTime = formatScheduleTime(schedule.on, 'on', solarTimes);
        const offTime = formatScheduleTime(schedule.off, 'off', solarTimes);
        timeHtml = `
            <div class="schedule-time-row">
                <span class="schedule-time-label">ON:</span>
                <span class="schedule-time-value">${onTime}</span>
            </div>
            <div class="schedule-time-row">
                <span class="schedule-time-label">OFF:</span>
                <span class="schedule-time-value">${offTime}</span>
            </div>
        `;
    }
    
    // Format conditions
    const conditions = schedule.conditions || {};
    let conditionsHtml = '';
    if (Object.keys(conditions).length > 0) {
        conditionsHtml = '<div class="schedule-conditions">';
        conditionsHtml += '<strong>Conditions:</strong> ';
        const condParts = [];
        if (conditions.temperature_max !== undefined) {
            condParts.push(`Temp ≤ ${conditions.temperature_max}°F`);
        }
        if (conditions.precipitation_active) {
            condParts.push('Precipitation active');
        }
        conditionsHtml += condParts.join(', ');
        conditionsHtml += '</div>';
    }
    
    return `
        <div class="schedule-card ${enabled ? 'enabled' : 'disabled'} priority-${priority}">
            <div class="schedule-header">
                <div class="schedule-title">
                    <span class="schedule-name">${schedule.name || 'Unnamed Schedule'}</span>
                    <span class="schedule-priority-badge ${priority}">${priority}</span>
                </div>
                <label class="schedule-toggle-switch">
                    <input type="checkbox" ${enabled ? 'checked' : ''} 
                           onchange="toggleScheduleEnabled('${groupName}', ${index}, this.checked)">
                    <span class="schedule-toggle-slider"></span>
                </label>
            </div>
            <div class="schedule-details">
                ${timeHtml}
                <div class="schedule-days">
                    <strong>Days:</strong> ${daysText}
                </div>
                ${conditionsHtml}
            </div>
            <div class="schedule-actions">
                <button class="btn-edit" onclick="editSchedule('${groupName}', ${index})" title="Edit schedule">
                    ✏️ Edit
                </button>
                <button class="btn-delete" onclick="deleteSchedule('${groupName}', ${index})" title="Delete schedule">
                    🗑️ Delete
                </button>
            </div>
        </div>
    `;
}

function formatScheduleTime(timeConfig, label, solarTimes) {
    if (!timeConfig || !timeConfig.type) {
        return 'Not configured';
    }
    
    const type = timeConfig.type;
    
    if (type === 'time') {
        return `⏰ ${timeConfig.value}`;
    } else if (type === 'sunrise' || type === 'sunset') {
        const offset = timeConfig.offset || 0;
        const offsetText = offset === 0 ? '' : (offset > 0 ? `+${offset}min` : `${offset}min`);
        const icon = type === 'sunrise' ? '☀️' : '🌙';
        const fallback = timeConfig.fallback || '??:??';
        
        // Calculate actual time if solarTimes available
        let actualTime = fallback;
        if (solarTimes) {
            const baseTime = type === 'sunrise' ? solarTimes.sunrise : solarTimes.sunset;
            if (baseTime) {
                const [hours, minutes] = baseTime.split(':').map(Number);
                const totalMinutes = hours * 60 + minutes + offset;
                const actualHours = Math.floor(totalMinutes / 60) % 24;
                const actualMinutes = totalMinutes % 60;
                actualTime = `${String(actualHours).padStart(2, '0')}:${String(actualMinutes).padStart(2, '0')}`;
            }
        }
        
        return `${icon} ${type}${offsetText} (${actualTime})`;
    } else if (type === 'duration') {
        const hours = timeConfig.value || 0;
        return `⏱️ ${hours}h after ON`;
    }
    
    return 'Unknown';
}

function formatDays(days) {
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    if (!days || days.length === 0) return 'None';
    if (days.length === 7) return 'Every day';
    
    return days.map(d => dayNames[d - 1]).join(', ');
}

async function toggleScheduleEnabled(groupName, scheduleIndex, enabled) {
    try {
        const response = await fetch(`/api/groups/${groupName}/schedules/${scheduleIndex}/enabled`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled: enabled })
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Failed to toggle schedule: ${error.error || 'Unknown error'}`);
            // Refresh to revert UI
            await refreshSchedules();
            return;
        }
        
        // Refresh schedules to update UI
        await refreshSchedules();
        
    } catch (e) {
        alert(`Failed to toggle schedule: ${e.message}`);
        await refreshSchedules();
    }
}

// Schedule modal management
let currentScheduleGroupName = null;
let currentScheduleIndex = null;

function showAddScheduleDialog(groupName) {
    currentScheduleGroupName = groupName;
    currentScheduleIndex = null;
    
    // Reset form
    document.getElementById('schedule-form').reset();
    document.getElementById('schedule-modal-title').textContent = `Add Schedule to ${groupName}`;
    
    // Set defaults
    document.getElementById('schedule-enabled').checked = true;
    document.getElementById('schedule-priority').value = 'normal';
    
    // Reset all_day checkbox and show time config section
    document.getElementById('schedule-all-day').checked = false;
    document.getElementById('time-config-section').style.display = 'block';
    
    // Check all days by default
    document.querySelectorAll('.days-selector input[type="checkbox"]').forEach(cb => {
        cb.checked = true;
    });
    
    // Reset time type fields to default state
    document.getElementById('on-type').value = 'time';
    document.getElementById('off-type').value = 'time';
    updateOnTimeFields();
    updateOffTimeFields();
    
    // Show modal
    document.getElementById('schedule-modal').style.display = 'flex';
}

async function editSchedule(groupName, scheduleIndex) {
    currentScheduleGroupName = groupName;
    currentScheduleIndex = scheduleIndex;
    
    try {
        // Fetch the schedule
        const response = await fetch(`/api/groups/${groupName}/schedules/${scheduleIndex}`);
        if (!response.ok) {
            alert('Failed to fetch schedule');
            return;
        }
        
        const data = await response.json();
        const schedule = data.schedule;
        
        // Populate form
        document.getElementById('schedule-modal-title').textContent = `Edit Schedule: ${schedule.name}`;
        document.getElementById('schedule-name').value = schedule.name || '';
        document.getElementById('schedule-priority').value = schedule.priority || 'normal';
        document.getElementById('schedule-enabled').checked = schedule.enabled !== false;
        
        // Set days
        document.querySelectorAll('.days-selector input[type="checkbox"]').forEach(cb => {
            cb.checked = schedule.days && schedule.days.includes(parseInt(cb.value));
        });
        
        // Set all_day flag
        const isAllDay = schedule.all_day === true;
        document.getElementById('schedule-all-day').checked = isAllDay;
        toggleAllDay(isAllDay);
        
        // Set ON time (only if not all_day)
        if (!isAllDay && schedule.on) {
            document.getElementById('on-type').value = schedule.on.type || 'time';
            updateOnTimeFields();
            
            if (schedule.on.type === 'time') {
                document.getElementById('on-time-value').value = schedule.on.value || '';
            } else if (schedule.on.type === 'sunrise' || schedule.on.type === 'sunset') {
                document.getElementById('on-offset').value = schedule.on.offset || 0;
                document.getElementById('on-fallback').value = schedule.on.fallback || '';
            }
        }
        
        // Set OFF time (only if not all_day)
        if (!isAllDay && schedule.off) {
            document.getElementById('off-type').value = schedule.off.type || 'time';
            updateOffTimeFields();
            
            if (schedule.off.type === 'time') {
                document.getElementById('off-time-value').value = schedule.off.value || '';
            } else if (schedule.off.type === 'sunrise' || schedule.off.type === 'sunset') {
                document.getElementById('off-offset').value = schedule.off.offset || 0;
                document.getElementById('off-fallback').value = schedule.off.fallback || '';
            } else if (schedule.off.type === 'duration') {
                document.getElementById('off-duration').value = schedule.off.value || 1;
            }
        }
        
        // Set conditions
        if (schedule.conditions) {
            document.getElementById('condition-temp-max').value = schedule.conditions.temperature_max || '';
            document.getElementById('condition-precip').checked = schedule.conditions.precipitation_active || false;
        }
        
        // Set safety
        if (schedule.safety) {
            document.getElementById('safety-max-runtime').value = schedule.safety.max_runtime_hours || '';
            document.getElementById('safety-cooldown').value = schedule.safety.cooldown_minutes || '';
        }
        
        // Show modal
        document.getElementById('schedule-modal').style.display = 'flex';
        
    } catch (e) {
        alert(`Failed to load schedule: ${e.message}`);
    }
}

function closeScheduleModal() {
    document.getElementById('schedule-modal').style.display = 'none';
    currentScheduleGroupName = null;
    currentScheduleIndex = null;
}

function updateOnTimeFields() {
    const type = document.getElementById('on-type').value;
    const timeField = document.getElementById('on-time-field');
    const solarFields = document.getElementById('on-solar-fields');
    
    if (type === 'time') {
        timeField.style.display = 'block';
        solarFields.style.display = 'none';
        document.getElementById('on-time-value').required = true;
    } else {
        timeField.style.display = 'none';
        solarFields.style.display = 'block';
        document.getElementById('on-time-value').required = false;
        document.getElementById('on-fallback').required = true;
    }
}

function updateOffTimeFields() {
    const type = document.getElementById('off-type').value;
    const timeField = document.getElementById('off-time-field');
    const solarFields = document.getElementById('off-solar-fields');
    const durationField = document.getElementById('off-duration-field');
    
    if (type === 'time') {
        timeField.style.display = 'block';
        solarFields.style.display = 'none';
        durationField.style.display = 'none';
        document.getElementById('off-time-value').required = true;
    } else if (type === 'duration') {
        timeField.style.display = 'none';
        solarFields.style.display = 'none';
        durationField.style.display = 'block';
        document.getElementById('off-time-value').required = false;
    } else {
        timeField.style.display = 'none';
        solarFields.style.display = 'block';
        durationField.style.display = 'none';
        document.getElementById('off-time-value').required = false;
        document.getElementById('off-fallback').required = true;
    }
}

function toggleAllDay(checked) {
    const timeConfigSection = document.getElementById('time-config-section');
    const onTimeValue = document.getElementById('on-time-value');
    const offTimeValue = document.getElementById('off-time-value');
    
    if (checked) {
        // Hide ON/OFF time sections
        timeConfigSection.style.display = 'none';
        // Remove required attributes when hidden
        onTimeValue.required = false;
        offTimeValue.required = false;
    } else {
        // Show ON/OFF time sections
        timeConfigSection.style.display = 'block';
        // Restore required attributes based on current type selections
        updateOnTimeFields();
        updateOffTimeFields();
    }
}

async function saveSchedule() {
    if (!currentScheduleGroupName) {
        alert('Error: No group selected');
        return;
    }
    
    // Check if all_day is enabled
    const isAllDay = document.getElementById('schedule-all-day').checked;
    
    // Collect form data
    const schedule = {
        name: document.getElementById('schedule-name').value,
        priority: document.getElementById('schedule-priority').value,
        enabled: document.getElementById('schedule-enabled').checked,
        days: [],
        all_day: isAllDay
    };
    
    // Collect selected days
    document.querySelectorAll('.days-selector input[type="checkbox"]:checked').forEach(cb => {
        schedule.days.push(parseInt(cb.value));
    });
    
    if (schedule.days.length === 0) {
        alert('Please select at least one day of the week');
        return;
    }
    
    // Only collect ON/OFF times if not all_day
    if (!isAllDay) {
        // ON time
        const onType = document.getElementById('on-type').value;
        schedule.on = { type: onType };
        
        if (onType === 'time') {
            schedule.on.value = document.getElementById('on-time-value').value;
            if (!schedule.on.value) {
                alert('Please specify ON time');
                return;
            }
        } else {
            schedule.on.offset = parseInt(document.getElementById('on-offset').value) || 0;
            schedule.on.fallback = document.getElementById('on-fallback').value;
            if (!schedule.on.fallback) {
                alert('Please specify fallback time for ON');
                return;
            }
        }
        
        // OFF time
        const offType = document.getElementById('off-type').value;
        schedule.off = { type: offType };
        
        if (offType === 'time') {
            schedule.off.value = document.getElementById('off-time-value').value;
            if (!schedule.off.value) {
                alert('Please specify OFF time');
                return;
            }
        } else if (offType === 'duration') {
            schedule.off.value = parseFloat(document.getElementById('off-duration').value);
            if (!schedule.off.value || schedule.off.value <= 0) {
                alert('Please specify a valid duration');
                return;
            }
        } else {
            schedule.off.offset = parseInt(document.getElementById('off-offset').value) || 0;
            schedule.off.fallback = document.getElementById('off-fallback').value;
            if (!schedule.off.fallback) {
                alert('Please specify fallback time for OFF');
                return;
            }
        }
    }
    
    // Conditions
    const tempMax = document.getElementById('condition-temp-max').value;
    const precip = document.getElementById('condition-precip').checked;
    
    if (tempMax || precip) {
        schedule.conditions = {};
        if (tempMax) {
            schedule.conditions.temperature_max = parseFloat(tempMax);
        }
        if (precip) {
            schedule.conditions.precipitation_active = true;
        }
    }
    
    // Safety
    const maxRuntime = document.getElementById('safety-max-runtime').value;
    const cooldown = document.getElementById('safety-cooldown').value;
    
    if (maxRuntime || cooldown) {
        schedule.safety = {};
        if (maxRuntime) {
            schedule.safety.max_runtime_hours = parseFloat(maxRuntime);
        }
        if (cooldown) {
            schedule.safety.cooldown_minutes = parseInt(cooldown);
        }
    }
    
    try {
        let url, method;
        
        if (currentScheduleIndex !== null) {
            // Edit existing schedule
            url = `/api/groups/${currentScheduleGroupName}/schedules/${currentScheduleIndex}`;
            method = 'PUT';
        } else {
            // Add new schedule
            url = `/api/groups/${currentScheduleGroupName}/schedules`;
            method = 'POST';
        }
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(schedule)
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Failed to save schedule: ${error.error || 'Unknown error'}\n${error.details || ''}`);
            return;
        }
        
        // Close modal and refresh
        closeScheduleModal();
        await refreshSchedules();
        
    } catch (e) {
        alert(`Failed to save schedule: ${e.message}`);
    }
}

async function deleteSchedule(groupName, scheduleIndex) {
    if (!confirm('Are you sure you want to delete this schedule?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/groups/${groupName}/schedules/${scheduleIndex}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Failed to delete schedule: ${error.error || 'Unknown error'}`);
            return;
        }
        
        // Refresh schedules
        await refreshSchedules();
        
    } catch (e) {
        alert(`Failed to delete schedule: ${e.message}`);
    }
}

// Initialize on load
window.addEventListener('load', () => {
    checkSetupMode();
    checkSecurity();
    refreshStatus();
    refreshVacationMode();
    
    // Start notification polling since Status tab is active by default
    if (typeof startNotificationPolling === 'function') {
        startNotificationPolling();
    }
    
    // Initialize health view toggle based on saved preference
    const healthViewToggle = document.getElementById('health-view-toggle');
    if (healthViewToggle) {
        const currentView = getHealthViewPreference();
        healthViewToggle.checked = (currentView === 'group');
    }
});

/**
 * Download current config.yaml file
 */
async function downloadConfig() {
    try {
        const response = await fetch('/api/config/download');
        
        if (!response.ok) {
            const error = await response.json();
            showConfigUploadMessage('error', `Failed to download: ${error.error || 'Unknown error'}`);
            return;
        }
        
        // Create blob and trigger download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'config.yaml';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showConfigUploadMessage('success', '✓ Configuration downloaded successfully');
    } catch (error) {
        console.error('Download failed:', error);
        showConfigUploadMessage('error', `Download failed: ${error.message}`);
    }
}

/**
 * Upload and validate config.yaml file
 */
async function uploadConfig(file) {
    if (!file) {
        return;
    }
    
    // Check file extension
    if (!file.name.endsWith('.yaml') && !file.name.endsWith('.yml')) {
        showConfigUploadMessage('error', 'Please select a YAML file (.yaml or .yml)');
        return;
    }
    
    // Show loading message
    showConfigUploadMessage('info', 'Uploading and validating configuration...');
    
    try {
        const formData = new FormData();
        formData.append('config_file', file);
        
        const response = await fetch('/api/config/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok && result.status === 'ok') {
            showConfigUploadMessage('success', `✓ ${result.message || 'Configuration uploaded and validated successfully'}`);
            if (result.backup_created) {
                showConfigUploadMessage('success', `Backup created: ${result.backup_file}`, true);
            }
            // Optionally refresh status
            setTimeout(() => refreshStatus(), 1000);
        } else {
            let errorMsg = result.message || result.error || 'Upload failed';
            if (result.validation_errors && result.validation_errors.length > 0) {
                errorMsg += '\n\nValidation errors:\n' + result.validation_errors.join('\n');
            }
            showConfigUploadMessage('error', errorMsg);
        }
    } catch (error) {
        console.error('Upload failed:', error);
        showConfigUploadMessage('error', `Upload failed: ${error.message}`);
    }
    
    // Reset file input
    document.getElementById('config-upload-input').value = '';
}

/**
 * Show message for config upload/download
 */
function showConfigUploadMessage(type, message, append = false) {
    const messageDiv = document.getElementById('config-upload-message');
    
    if (!append) {
        messageDiv.innerHTML = '';
    }
    
    const msgElement = document.createElement('div');
    msgElement.className = type; // 'success', 'error', or 'info'
    msgElement.style.marginTop = '10px';
    msgElement.style.whiteSpace = 'pre-wrap';
    msgElement.textContent = message;
    
    messageDiv.appendChild(msgElement);
    
    // Auto-clear success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            msgElement.remove();
        }, 5000);
    }
}

// Collapsible section toggle
function toggleCollapsible(header) {
    const section = header.parentElement;
    const content = section.querySelector('.collapsible-section-content');
    const toggle = header.querySelector('.collapsible-section-toggle');
    
    const isExpanded = content.classList.contains('expanded');
    
    if (isExpanded) {
        content.classList.remove('expanded');
        toggle.classList.remove('expanded');
    } else {
        content.classList.add('expanded');
        toggle.classList.add('expanded');
    }
}

// Refresh current tab (for FAB button)
function refreshCurrentTab() {
    const activeTab = document.querySelector('.tab.active');
    if (!activeTab) {
        refreshStatus();
        return;
    }
    
    const tabName = activeTab.textContent.trim().toLowerCase();
    
    if (tabName.includes('status')) {
        refreshStatus();
        refreshVacationMode();
    } else if (tabName.includes('schedule')) {
        refreshSchedules();
    } else if (tabName.includes('group')) {
        refreshGroups();
    } else if (tabName.includes('config')) {
        loadConfig();
    } else if (tabName.includes('health')) {
        refreshHealth();
    } else if (tabName.includes('weather')) {
        refreshWeather();
    } else {
        refreshStatus();
    }
    
    // Show feedback
    showToast('Refreshed!', 'success');
}

// Mobile menu toggle functions
function toggleMobileMenu() {
    const tabs = document.getElementById('main-tabs');
    const overlay = document.querySelector('.mobile-nav-overlay');
    
    if (tabs.classList.contains('mobile-menu-open')) {
        closeMobileMenu();
    } else {
        tabs.classList.add('mobile-menu-open');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeMobileMenu() {
    const tabs = document.getElementById('main-tabs');
    const overlay = document.querySelector('.mobile-nav-overlay');
    
    tabs.classList.remove('mobile-menu-open');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Add event listeners for mobile enhancements
document.addEventListener('DOMContentLoaded', function() {
    // Close mobile menu when any tab is clicked
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            closeMobileMenu();
        });
    });
    
    // Handle day checkbox styling for browsers without :has() support
    const dayCheckboxes = document.querySelectorAll('.day-checkbox');
    dayCheckboxes.forEach(dayCheckbox => {
        const checkbox = dayCheckbox.querySelector('input[type="checkbox"]');
        if (checkbox) {
            // Set initial state
            if (checkbox.checked) {
                dayCheckbox.classList.add('checked');
            }
            
            // Update on change
            checkbox.addEventListener('change', function() {
                if (this.checked) {
                    dayCheckbox.classList.add('checked');
                } else {
                    dayCheckbox.classList.remove('checked');
                }
            });
        }
    });
});

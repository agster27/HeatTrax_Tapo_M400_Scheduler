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
        
    } catch (e) {
        statusContent.innerHTML = `<div class="error">Failed to load status: ${e.message}</div>`;
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
            // Fetch automation data for this group
            try {
                const automationResponse = await fetch(`/api/groups/${groupName}/automation`);
                const automationData = await automationResponse.json();
                
                if (automationData.error) {
                    html += `<div class="group-card">
                        <h3>${groupName}</h3>
                        <p class="error">${automationData.error}</p>
                    </div>`;
                    continue;
                }
                
                const base = automationData.base || {};
                const overrides = automationData.overrides || {};
                const effective = automationData.effective || {};
                const schedule = automationData.schedule || {};
                
                html += `<div class="group-card">
                    <h3>${groupName}</h3>
                    <div class="automation-panel">
                        ${createAutomationToggle('weather_control', 'Weather Control', groupName, effective.weather_control, base.weather_control, overrides.weather_control !== undefined)}
                        ${createAutomationToggle('precipitation_control', 'Precipitation Control', groupName, effective.precipitation_control, base.precipitation_control, overrides.precipitation_control !== undefined)}
                        ${createAutomationToggle('morning_mode', 'Morning Mode', groupName, effective.morning_mode, base.morning_mode, overrides.morning_mode !== undefined)}
                        ${createAutomationToggle('schedule_control', 'Schedule Control', groupName, effective.schedule_control, base.schedule_control, overrides.schedule_control !== undefined)}
                    </div>`;
                
                // Show schedule info if available
                if (schedule.valid) {
                    html += `<div class="schedule-info">
                        <strong>📅 Schedule (from config.yaml):</strong>
                        <code>${schedule.on_time} → ${schedule.off_time}</code>
                    </div>`;
                } else if (effective.schedule_control) {
                    html += `<div class="schedule-info" style="background: #fff3cd;">
                        <strong>⚠️ Schedule Control Enabled</strong>
                        <p>No valid schedule configured in config.yaml. Add <code>schedule.on_time</code> and <code>schedule.off_time</code> to enable schedule-based control.</p>
                    </div>`;
                }
                
                html += '</div>';
                
            } catch (e) {
                html += `<div class="group-card">
                    <h3>${groupName}</h3>
                    <p class="error">Failed to load automation: ${e.message}</p>
                </div>`;
            }
        }
        
        groupsContent.innerHTML = html;
        
    } catch (e) {
        groupsContent.innerHTML = `<div class="error">Failed to load groups: ${e.message}</div>`;
    }
}

function createAutomationToggle(flagName, displayName, groupName, effectiveValue, baseValue, isOverridden) {
    const toggleId = `toggle-${groupName}-${flagName}`;
    const checked = effectiveValue ? 'checked' : '';
    const overrideBadge = isOverridden ? '<span class="override-badge">overridden</span>' : '';
    
    return `<div class="automation-row">
        <div class="automation-label">
            ${displayName}
            ${overrideBadge}
        </div>
        <label class="automation-toggle">
            <input type="checkbox" id="${toggleId}" ${checked} 
                   onchange="toggleAutomation('${groupName}', '${flagName}', this.checked)">
            <span class="automation-slider"></span>
        </label>
    </div>`;
}

async function toggleAutomation(groupName, flagName, value) {
    try {
        const payload = {};
        payload[flagName] = value;
        
        const response = await fetch(`/api/groups/${groupName}/automation`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert(`Failed to update automation: ${error.error || 'Unknown error'}`);
            // Revert the toggle
            document.getElementById(`toggle-${groupName}-${flagName}`).checked = !value;
            return;
        }
        
        // Refresh groups to update override badges
        await refreshGroups();
        
    } catch (e) {
        alert(`Failed to update automation: ${e.message}`);
        // Revert the toggle
        document.getElementById(`toggle-${groupName}-${flagName}`).checked = !value;
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
                    <value>${forecastData.hours ? forecastData.hours.length : 0}</value>
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
            // Build a map of times to mat ON status from mat forecast
            const matOnByTime = {};
            if (matForecastData.status === 'ok' && matForecastData.groups) {
                for (const [groupName, windows] of Object.entries(matForecastData.groups)) {
                    for (const window of windows) {
                        if (window.state === 'on') {
                            const start = new Date(window.start);
                            const end = new Date(window.end);
                            
                            // Mark all hours in this window as having mats ON
                            for (const hour of forecastData.hours) {
                                const hourTime = new Date(hour.time);
                                if (hourTime >= start && hourTime <= end) {
                                    matOnByTime[hour.time] = true;
                                }
                            }
                        }
                    }
                }
            }
            
            let tableHtml = `
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f8f9fa; border-bottom: 2px solid #ddd;">
                            <th style="padding: 10px; text-align: left;">Time</th>
                            <th style="padding: 10px; text-align: left;">Temp (°F)</th>
                            <th style="padding: 10px; text-align: left;">Precip (mm)</th>
                            <th style="padding: 10px; text-align: left;">Type</th>
                            <th style="padding: 10px; text-align: center;">Mats ON?</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            for (const hour of forecastData.hours) {
                const time = new Date(hour.time).toLocaleString();
                const temp = hour.temp_f !== null ? hour.temp_f.toFixed(1) : 'N/A';
                const precip = hour.precip_intensity !== null ? hour.precip_intensity.toFixed(2) : '0.00';
                const precipType = hour.precip_type || '-';
                const matsOn = matOnByTime[hour.time] ? '✅' : '-';
                
                tableHtml += `
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 8px;">${time}</td>
                        <td style="padding: 8px;">${temp}</td>
                        <td style="padding: 8px;">${precip}</td>
                        <td style="padding: 8px;">${precipType}</td>
                        <td style="padding: 8px; text-align: center;">${matsOn}</td>
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
    'Thresholds & Scheduler': [
        { path: 'thresholds.temperature_f', label: 'Threshold Temperature (°F)', type: 'number', step: '0.1' },
        { path: 'thresholds.lead_time_minutes', label: 'Lead Time (minutes)', type: 'number' },
        { path: 'thresholds.trailing_time_minutes', label: 'Trailing Time (minutes)', type: 'number' },
        { path: 'scheduler.check_interval_minutes', label: 'Check Interval (minutes)', type: 'number' },
        { path: 'scheduler.forecast_hours', label: 'Forecast Hours', type: 'number' }
    ],
    'Safety & Morning Mode': [
        { path: 'safety.max_runtime_hours', label: 'Max Runtime (hours)', type: 'number', step: '0.1' },
        { path: 'safety.cooldown_minutes', label: 'Cooldown (minutes)', type: 'number' },
        { path: 'morning_mode.enabled', label: 'Morning Mode Enabled', type: 'checkbox' },
        { path: 'morning_mode.start_hour', label: 'Morning Mode Start Hour', type: 'number', min: '0', max: '23' },
        { path: 'morning_mode.end_hour', label: 'Morning Mode End Hour', type: 'number', min: '0', max: '23' }
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
    
    // Format ON time
    const onTime = formatScheduleTime(schedule.on, 'on', solarTimes);
    const offTime = formatScheduleTime(schedule.off, 'off', solarTimes);
    
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
                <div class="schedule-time-row">
                    <span class="schedule-time-label">ON:</span>
                    <span class="schedule-time-value">${onTime}</span>
                </div>
                <div class="schedule-time-row">
                    <span class="schedule-time-label">OFF:</span>
                    <span class="schedule-time-value">${offTime}</span>
                </div>
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

function showAddScheduleDialog(groupName) {
    // TODO: Implement add schedule dialog
    alert(`Add schedule dialog for group '${groupName}' - To be implemented`);
}

function editSchedule(groupName, scheduleIndex) {
    // TODO: Implement edit schedule dialog
    alert(`Edit schedule dialog for group '${groupName}', index ${scheduleIndex} - To be implemented`);
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

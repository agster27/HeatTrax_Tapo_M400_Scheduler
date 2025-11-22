/**
 * Notification Provider Status and Testing Client
 * 
 * This module handles polling for notification provider status and triggering test notifications.
 */

// Track polling state
let notificationPollingInterval = null;
let notificationPollingActive = false;
let aggressivePollingInterval = null;

/**
 * Initialize notification status polling
 */
function initNotificationPolling() {
    // Initial fetch
    refreshNotificationStatus();
}

/**
 * Start polling (called when status tab is shown)
 */
function startNotificationPolling() {
    notificationPollingActive = true;
    refreshNotificationStatus();
    
    // Clear any existing interval to prevent memory leaks
    if (notificationPollingInterval) {
        clearInterval(notificationPollingInterval);
    }
    
    // Start polling every 10 seconds while active
    notificationPollingInterval = setInterval(() => {
        refreshNotificationStatus();
    }, 10000); // 10 seconds
}

/**
 * Stop polling (called when status tab is hidden)
 */
function stopNotificationPolling() {
    notificationPollingActive = false;
    
    // Clear the polling interval
    if (notificationPollingInterval) {
        clearInterval(notificationPollingInterval);
        notificationPollingInterval = null;
    }
    
    // Clear aggressive polling if active
    if (aggressivePollingInterval) {
        clearInterval(aggressivePollingInterval);
        aggressivePollingInterval = null;
    }
}

/**
 * Refresh notification provider status
 */
async function refreshNotificationStatus() {
    const container = document.getElementById('notification-providers-grid');
    if (!container) return;
    
    try {
        const response = await fetch('/api/notifications/status');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'ok' && data.providers) {
            renderNotificationProviders(data.providers);
        } else {
            container.innerHTML = `
                <div class="status-item">
                    <label>Error</label>
                    <value>${data.error || 'Unknown error'}</value>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to fetch notification status:', error);
        container.innerHTML = `
            <div class="status-item">
                <label>Error</label>
                <value>Failed to fetch status: ${error.message}</value>
            </div>
        `;
    }
}

/**
 * Render notification provider status cards
 */
function renderNotificationProviders(providers) {
    const container = document.getElementById('notification-providers-grid');
    if (!container) return;
    
    const providerCards = Object.entries(providers).map(([name, status]) => {
        const healthBadge = getHealthBadge(status.health);
        const enabledText = status.enabled ? 'Enabled' : 'Disabled';
        const lastCheck = status.last_check ? formatTimestamp(status.last_check) : 'Never';
        const lastSuccess = status.last_success ? formatTimestamp(status.last_success) : 'Never';
        const errorText = status.last_error || 'None';
        const failureCount = status.consecutive_failures || 0;
        
        return `
            <div class="status-item" style="border-left-color: ${getHealthColor(status.health)};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <label style="margin: 0; font-size: 16px; text-transform: capitalize;">${name}</label>
                    ${healthBadge}
                </div>
                
                <div style="font-size: 13px; color: #666; margin-bottom: 8px;">
                    <strong>Status:</strong> ${enabledText}
                </div>
                
                <div style="font-size: 12px; color: #888; margin-bottom: 4px;">
                    <strong>Last Check:</strong> ${lastCheck}
                </div>
                
                <div style="font-size: 12px; color: #888; margin-bottom: 4px;">
                    <strong>Last Success:</strong> ${lastSuccess}
                </div>
                
                ${failureCount > 0 ? `
                    <div style="font-size: 12px; color: #e74c3c; margin-bottom: 4px;">
                        <strong>Failures:</strong> ${failureCount} consecutive
                    </div>
                ` : ''}
                
                ${status.last_error ? `
                    <div style="font-size: 11px; color: #e74c3c; background: #fadbd8; padding: 6px; border-radius: 4px; margin-top: 8px; word-break: break-word;">
                        <strong>Error:</strong> ${escapeHtml(errorText)}
                    </div>
                ` : ''}
                
                ${status.enabled ? `
                    <button 
                        onclick="testNotificationProvider('${name}')" 
                        style="margin-top: 10px; width: 100%; padding: 6px; font-size: 13px;"
                    >
                        📧 Test ${name}
                    </button>
                ` : ''}
            </div>
        `;
    }).join('');
    
    container.innerHTML = providerCards || `
        <div class="status-item">
            <label>No Providers</label>
            <value>No notification providers configured</value>
        </div>
    `;
}

/**
 * Get health badge HTML
 */
function getHealthBadge(health) {
    const healthMap = {
        'healthy': { class: 'healthy', icon: '✓', text: 'Healthy' },
        'degraded': { class: 'warning', icon: '⚠', text: 'Degraded' },
        'failed': { class: 'error', icon: '✗', text: 'Failed' },
        'unknown': { class: 'offline', icon: '?', text: 'Unknown' }
    };
    
    const info = healthMap[health] || healthMap['unknown'];
    return `<span class="status-badge ${info.class}">${info.icon} ${info.text}</span>`;
}

/**
 * Get health color for border
 */
function getHealthColor(health) {
    const colorMap = {
        'healthy': '#27ae60',
        'degraded': '#f39c12',
        'failed': '#e74c3c',
        'unknown': '#95a5a6'
    };
    return colorMap[health] || colorMap['unknown'];
}

/**
 * Format ISO timestamp to human-readable format
 */
function formatTimestamp(isoString) {
    if (!isoString) return 'Never';
    
    try {
        const date = new Date(isoString);
        
        // Validate that the date is valid
        if (isNaN(date.getTime())) {
            return isoString;
        }
        
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHr = Math.floor(diffMin / 60);
        
        // Show relative time for recent events
        if (diffSec < 60) {
            return `${diffSec}s ago`;
        } else if (diffMin < 60) {
            return `${diffMin}m ago`;
        } else if (diffHr < 24) {
            return `${diffHr}h ago`;
        }
        
        // Otherwise show formatted date/time
        return date.toLocaleString();
    } catch (e) {
        return isoString;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Test a specific notification provider
 */
async function testNotificationProvider(providerName) {
    const messageDiv = document.getElementById('notification-message');
    if (!messageDiv) return;
    
    // Show queued message
    messageDiv.innerHTML = `
        <div class="success">
            📤 Test notification queued for <strong>${providerName}</strong>...
        </div>
    `;
    
    try {
        const response = await fetch('/api/notifications/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                subject: `HeatTrax Test - ${providerName}`,
                body: `This is a test notification for the ${providerName} provider. Sent at ${new Date().toLocaleString()}`
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'queued') {
            messageDiv.innerHTML = `
                <div class="success">
                    ✓ Test notification queued successfully. Check your ${providerName} shortly.
                </div>
            `;
            
            // Start aggressive polling for a minute to catch status updates
            startAggressivePolling(60000); // 60 seconds
        } else {
            messageDiv.innerHTML = `
                <div class="error">
                    ✗ Failed to queue test notification: ${data.error || 'Unknown error'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to test notification:', error);
        messageDiv.innerHTML = `
            <div class="error">
                ✗ Failed to test notification: ${error.message}
            </div>
        `;
    }
    
    // Clear message after 10 seconds
    setTimeout(() => {
        if (messageDiv) {
            messageDiv.innerHTML = '';
        }
    }, 10000);
}

/**
 * Test all enabled notification providers
 */
async function testAllNotifications() {
    const messageDiv = document.getElementById('notification-message');
    if (!messageDiv) return;
    
    messageDiv.innerHTML = `
        <div class="success">
            📤 Test notification queued for all enabled providers...
        </div>
    `;
    
    try {
        const response = await fetch('/api/notifications/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                subject: 'HeatTrax Test - All Providers',
                body: `This is a test notification for all enabled providers. Sent at ${new Date().toLocaleString()}`
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'queued') {
            messageDiv.innerHTML = `
                <div class="success">
                    ✓ Test notification queued successfully. Check all enabled providers shortly.
                </div>
            `;
            
            // Start aggressive polling for a minute to catch status updates
            startAggressivePolling(60000); // 60 seconds
        } else {
            messageDiv.innerHTML = `
                <div class="error">
                    ✗ Failed to queue test notification: ${data.error || 'Unknown error'}
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to test notifications:', error);
        messageDiv.innerHTML = `
            <div class="error">
                ✗ Failed to test notifications: ${error.message}
            </div>
        `;
    }
    
    // Clear message after 10 seconds
    setTimeout(() => {
        if (messageDiv) {
            messageDiv.innerHTML = '';
        }
    }, 10000);
}

/**
 * Start aggressive polling for a duration (to catch test completion)
 */
function startAggressivePolling(durationMs) {
    const pollInterval = 2000; // Poll every 2 seconds
    let elapsed = 0;
    
    // Clear any existing aggressive polling to prevent multiple intervals
    if (aggressivePollingInterval) {
        clearInterval(aggressivePollingInterval);
    }
    
    aggressivePollingInterval = setInterval(() => {
        elapsed += pollInterval;
        
        // Stop polling if duration elapsed OR if polling is no longer active
        if (elapsed >= durationMs || !notificationPollingActive) {
            clearInterval(aggressivePollingInterval);
            aggressivePollingInterval = null;
        } else {
            refreshNotificationStatus();
        }
    }, pollInterval);
}

// Note: initNotificationPolling() is intentionally NOT called on page load.
// Polling is started only when the Status tab becomes active via startNotificationPolling()
// which is called from app.js switchTab() function.

// Control page JavaScript for HeatTrax mobile interface

let currentGroup = null;
let autoRefreshInterval = null;
let countdownInterval = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeControlPage();
});

/**
 * Initialize the control page
 */
function initializeControlPage() {
    // Set up event listeners
    document.getElementById('controlBtn').addEventListener('click', handleControlClick);
    document.getElementById('resetBtn').addEventListener('click', handleResetClick);
    document.getElementById('refreshBtn').addEventListener('click', () => fetchStatus(true));
    document.getElementById('groupSelect').addEventListener('change', handleGroupChange);
    
    // Initial status fetch
    fetchStatus();
    
    // Set up auto-refresh (every 10 seconds)
    autoRefreshInterval = setInterval(() => fetchStatus(), 10000);
}

/**
 * Fetch current status from API
 */
async function fetchStatus(showLoading = false) {
    if (showLoading) {
        showLoadingScreen();
    } else {
        showDeviceStateLoading();
    }
    
    try {
        const response = await fetch('/api/mat/status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.status === 401) {
            // Session expired, redirect to login
            window.location.href = '/control/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            updateUI(data.groups);
            hideLoadingScreen();
            hideDeviceStateLoading();
            hideError();
        } else {
            throw new Error(data.error || 'Failed to fetch status');
        }
    } catch (error) {
        console.error('Failed to fetch status:', error);
        showError('Failed to load status. ' + error.message);
        hideLoadingScreen();
        hideDeviceStateLoading();
    }
}

/**
 * Update UI with status data
 */
function updateUI(groups) {
    const groupNames = Object.keys(groups);
    
    if (groupNames.length === 0) {
        showError('No device groups configured');
        return;
    }
    
    // Set up group selector if multiple groups
    if (groupNames.length > 1) {
        setupGroupSelector(groupNames);
    } else {
        document.getElementById('groupSelector').style.display = 'none';
    }
    
    // Use current group or default to first group
    if (!currentGroup || !groups[currentGroup]) {
        currentGroup = groupNames[0];
    }
    
    const groupStatus = groups[currentGroup];
    
    // Update status indicator
    const statusIndicator = document.querySelector('.status-indicator');
    const statusText = document.querySelector('.status-text');
    const controlBtn = document.getElementById('controlBtn');
    
    // Show actual device state
    if (groupStatus.is_on) {
        statusIndicator.classList.add('on');
        statusIndicator.classList.remove('off');
        statusText.textContent = 'ON';
        statusText.style.color = 'var(--success-color)';
        
        controlBtn.classList.add('on');
        controlBtn.classList.remove('off', 'loading');
        controlBtn.querySelector('.btn-text').textContent = 'TURN OFF';
        controlBtn.disabled = false;
    } else {
        statusIndicator.classList.add('off');
        statusIndicator.classList.remove('on');
        statusText.textContent = 'OFF';
        statusText.style.color = 'var(--text-secondary)';
        
        controlBtn.classList.add('off');
        controlBtn.classList.remove('on', 'loading');
        controlBtn.querySelector('.btn-text').textContent = 'TURN ON';
        controlBtn.disabled = false;
    }
    
    // Update mode badge based on schedule availability
    const modeBadge = document.querySelector('.mode-badge');
    
    if (!groupStatus.has_schedule) {
        // Group has no schedule - manual control only
        modeBadge.textContent = '🎮 MANUAL';
        modeBadge.classList.add('manual-only');
        modeBadge.classList.remove('auto', 'manual');
    } else if (groupStatus.mode === 'manual') {
        // Group has schedule but in manual override
        modeBadge.textContent = '🔧 MANUAL';
        modeBadge.classList.add('manual');
        modeBadge.classList.remove('auto', 'manual-only');
    } else {
        // Group has schedule and in auto mode
        modeBadge.textContent = '🤖 AUTO';
        modeBadge.classList.add('auto');
        modeBadge.classList.remove('manual', 'manual-only');
    }
    
    // Update temperature (if available)
    if (groupStatus.temperature !== null && groupStatus.temperature !== undefined) {
        document.getElementById('tempRow').style.display = 'flex';
        document.getElementById('temperature').textContent = `${groupStatus.temperature}°C`;
    } else {
        document.getElementById('tempRow').style.display = 'none';
    }
    
    // Update override info - only show for groups with schedules
    if (groupStatus.has_schedule && groupStatus.mode === 'manual' && groupStatus.override_expires_at) {
        document.getElementById('overrideInfo').style.display = 'flex';
        document.getElementById('resetSection').style.display = 'block';
        updateCountdown(groupStatus.override_expires_at);
    } else {
        document.getElementById('overrideInfo').style.display = 'none';
        document.getElementById('resetSection').style.display = 'none';
        clearCountdown();
    }
    
    // Show error if device query failed
    if (groupStatus.error) {
        showError(groupStatus.error);
    }
    
    // Update last updated time
    const now = new Date();
    document.getElementById('lastUpdated').textContent = formatTime(now);
}

/**
 * Set up group selector dropdown
 */
function setupGroupSelector(groupNames) {
    const selector = document.getElementById('groupSelector');
    const select = document.getElementById('groupSelect');
    
    // Clear existing options
    select.innerHTML = '';
    
    // Add options for each group
    groupNames.forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        if (name === currentGroup) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    
    selector.style.display = 'block';
}

/**
 * Handle group selection change
 */
function handleGroupChange(e) {
    currentGroup = e.target.value;
    fetchStatus();
}

/**
 * Handle control button click
 */
async function handleControlClick() {
    const controlBtn = document.getElementById('controlBtn');
    const isCurrentlyOn = controlBtn.classList.contains('on');
    const action = isCurrentlyOn ? 'off' : 'on';
    
    // Set loading state
    controlBtn.classList.add('loading');
    controlBtn.classList.remove('on', 'off');
    controlBtn.querySelector('.btn-text').textContent = 'LOADING...';
    controlBtn.disabled = true;
    
    try {
        const response = await fetch('/api/mat/control', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                group: currentGroup,
                action: action
            })
        });
        
        if (response.status === 401) {
            window.location.href = '/control/login';
            return;
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Update UI with new status
            updateUI(data.groups);
            hideError();
        } else {
            throw new Error(data.error || 'Control action failed');
        }
    } catch (error) {
        console.error('Control action failed:', error);
        showError('Failed to control device. ' + error.message);
        
        // Refresh status to get current state
        await fetchStatus();
    }
}

/**
 * Handle reset to auto mode button click
 */
async function handleResetClick() {
    const resetBtn = document.getElementById('resetBtn');
    
    // Confirm action
    if (!confirm('Return to automatic scheduling mode?')) {
        return;
    }
    
    // Set loading state
    resetBtn.disabled = true;
    const originalText = resetBtn.textContent;
    resetBtn.innerHTML = '<span class="spinner small"></span> Resetting...';
    
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
        
        const response = await fetch('/api/mat/reset-auto', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                group: currentGroup
            }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (response.status === 401) {
            window.location.href = '/control/login';
            return;
        }
        
        if (response.status === 504) {
            throw new Error('Operation timed out. Check device connectivity.');
        }
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Reset action failed');
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Update UI with new status
            updateUI(data.groups);
            hideError();
        } else {
            throw new Error(data.error || 'Reset action failed');
        }
    } catch (error) {
        console.error('Reset action failed:', error);
        
        if (error.name === 'AbortError') {
            showError('Operation timed out. Devices may be slow to respond.');
        } else {
            showError('Failed to reset: ' + error.message);
        }
    } finally {
        resetBtn.disabled = false;
        resetBtn.textContent = originalText;
    }
}

/**
 * Update countdown timer for override expiration
 */
function updateCountdown(expiresAt) {
    // Clear existing interval
    clearCountdown();
    
    const updateTimer = () => {
        const now = new Date();
        const expiry = new Date(expiresAt);
        const diff = expiry - now;
        
        if (diff <= 0) {
            document.getElementById('overrideExpiry').textContent = 'Expired';
            clearCountdown();
            // Refresh status to update UI
            fetchStatus();
            return;
        }
        
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        
        let timeStr = '';
        if (hours > 0) {
            timeStr = `in ${hours}h ${minutes}m`;
        } else if (minutes > 0) {
            timeStr = `in ${minutes}m ${seconds}s`;
        } else {
            timeStr = `in ${seconds}s`;
        }
        
        document.getElementById('overrideExpiry').textContent = timeStr;
    };
    
    // Update immediately
    updateTimer();
    
    // Update every second
    countdownInterval = setInterval(updateTimer, 1000);
}

/**
 * Clear countdown interval
 */
function clearCountdown() {
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
}

/**
 * Format time for display
 */
function formatTime(date) {
    return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    });
}

/**
 * Show loading screen
 */
function showLoadingScreen() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('content').style.display = 'none';
}

/**
 * Hide loading screen
 */
function hideLoadingScreen() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('content').style.display = 'block';
}

/**
 * Show error message
 */
function showError(message) {
    const errorDiv = document.getElementById('error');
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorDiv.style.display = 'block';
}

/**
 * Hide error message
 */
function hideError() {
    document.getElementById('error').style.display = 'none';
}

/**
 * Show device state loading spinner
 */
function showDeviceStateLoading() {
    const statusIndicator = document.querySelector('.status-indicator');
    if (statusIndicator) {
        statusIndicator.classList.add('loading');
    }
}

/**
 * Hide device state loading spinner
 */
function hideDeviceStateLoading() {
    const statusIndicator = document.querySelector('.status-indicator');
    if (statusIndicator) {
        statusIndicator.classList.remove('loading');
    }
}

// Clean up intervals when page is unloaded
window.addEventListener('beforeunload', () => {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    clearCountdown();
});

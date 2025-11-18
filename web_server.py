"""Flask web server for HeatTrax Scheduler UI and API."""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path

logger = logging.getLogger(__name__)


class WebServer:
    """
    Flask-based web server providing:
    - JSON API for status and configuration
    - Static HTML UI for monitoring and configuration
    """
    
    def __init__(self, config_manager, scheduler=None):
        """
        Initialize web server.
        
        Args:
            config_manager: ConfigManager instance for config operations
            scheduler: Optional scheduler instance for status information
        """
        self.config_manager = config_manager
        self.scheduler = scheduler
        
        # Create Flask app
        self.app = Flask(__name__, 
                         static_folder='web/static',
                         template_folder='web/templates')
        
        # Disable Flask's default logging to stdout (use our logging)
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(logging.WARNING)
        
        # Register routes
        self._register_routes()
        
        logger.info("WebServer initialized")
    
    def _build_annotated_config(self, config: Dict[str, Any], env_overridden_paths: Dict[str, str], 
                                 current_path: str = "") -> Dict[str, Any]:
        """
        Build annotated configuration with source metadata for each field.
        
        Args:
            config: Configuration dictionary
            env_overridden_paths: Mapping of config paths to env var names
            current_path: Current path in config tree (for recursion)
            
        Returns:
            Dictionary with fields annotated with source metadata
        """
        if not isinstance(config, dict):
            # Leaf value - determine source
            path = current_path.rstrip('.')
            if path in env_overridden_paths:
                return {
                    'value': config,
                    'source': 'env',
                    'env_var': env_overridden_paths[path],
                    'readonly': True
                }
            else:
                return {
                    'value': config,
                    'source': 'yaml',
                    'readonly': False
                }
        
        # Recursively annotate nested structures
        result = {}
        for key, value in config.items():
            new_path = f"{current_path}{key}."
            
            if isinstance(value, dict):
                # Check if this entire dict is overridden by env
                path_without_dot = new_path.rstrip('.')
                if path_without_dot in env_overridden_paths:
                    result[key] = {
                        'value': value,
                        'source': 'env',
                        'env_var': env_overridden_paths[path_without_dot],
                        'readonly': True
                    }
                else:
                    # Recurse into nested dict
                    result[key] = self._build_annotated_config(value, env_overridden_paths, new_path)
            elif isinstance(value, list):
                # For lists, check if the path is overridden
                path_without_dot = new_path.rstrip('.')
                if path_without_dot in env_overridden_paths:
                    result[key] = {
                        'value': value,
                        'source': 'env',
                        'env_var': env_overridden_paths[path_without_dot],
                        'readonly': True
                    }
                else:
                    result[key] = {
                        'value': value,
                        'source': 'yaml',
                        'readonly': False
                    }
            else:
                # Scalar value - check if overridden
                path_without_dot = new_path.rstrip('.')
                if path_without_dot in env_overridden_paths:
                    result[key] = {
                        'value': value,
                        'source': 'env',
                        'env_var': env_overridden_paths[path_without_dot],
                        'readonly': True
                    }
                else:
                    result[key] = {
                        'value': value,
                        'source': 'yaml',
                        'readonly': False
                    }
        
        return result
    
    def _register_routes(self):
        """Register Flask routes."""
        
        @self.app.route('/')
        def index():
            """Serve main UI page."""
            return self._serve_ui_file('index.html')
        
        @self.app.route('/ui')
        def ui():
            """Serve main UI page (alternative route)."""
            return self._serve_ui_file('index.html')
        
        @self.app.route('/api/health', methods=['GET'])
        def api_health():
            """
            Health check endpoint.
            
            Returns:
                JSON: Health status
            """
            try:
                config = self.config_manager.get_config(include_secrets=False)
                
                return jsonify({
                    'status': 'ok',
                    'timestamp': datetime.now().isoformat(),
                    'config_loaded': True
                })
            except Exception as e:
                logger.error(f"Health check failed: {e}", exc_info=True)
                return jsonify({
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/ping', methods=['GET'])
        def api_ping():
            """
            Simple ping endpoint.
            
            Returns:
                JSON: Pong response
            """
            return jsonify({'status': 'ok', 'message': 'pong'})
        
        @self.app.route('/api/status', methods=['GET'])
        def api_status():
            """
            Get system status.
            
            Returns:
                JSON: System status including device states and schedule
            """
            try:
                status = self._get_system_status()
                return jsonify(status)
            except Exception as e:
                logger.error(f"Failed to get status: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to get system status',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/config', methods=['GET'])
        def api_config_get():
            """
            Get current configuration with source metadata.
            
            Returns:
                JSON: Configuration with metadata for each field including:
                    - value: the actual value
                    - source: 'env' or 'yaml'
                    - env_var: env variable name (if source is 'env')
                    - readonly: boolean indicating if field is env-overridden
            """
            try:
                # Get config without secrets and env overridden paths
                config = self.config_manager.get_config(include_secrets=False)
                env_overridden_paths = self.config_manager.get_env_overridden_paths()
                
                # Build annotated config with metadata
                annotated_config = self._build_annotated_config(config, env_overridden_paths)
                
                return jsonify(annotated_config)
            except Exception as e:
                logger.error(f"Failed to get config: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to get configuration',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/config', methods=['PUT', 'POST'])
        def api_config_put():
            """
            Update configuration.
            
            Expects:
                JSON: New configuration
                
            Returns:
                JSON: Update result with status and restart_required flag
            """
            try:
                if not request.is_json:
                    return jsonify({
                        'status': 'error',
                        'message': 'Request must be JSON'
                    }), 400
                
                new_config = request.get_json()
                
                if not isinstance(new_config, dict):
                    return jsonify({
                        'status': 'error',
                        'message': 'Configuration must be a dictionary'
                    }), 400
                
                # Update configuration
                result = self.config_manager.update_config(new_config, preserve_secrets=True)
                
                if result['status'] == 'ok':
                    return jsonify(result)
                else:
                    return jsonify(result), 400
                    
            except Exception as e:
                logger.error(f"Failed to update config: {e}", exc_info=True)
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to update configuration: {str(e)}'
                }), 500
        
        @self.app.route('/api/restart', methods=['POST'])
        def api_restart():
            """
            Trigger application restart by exiting the process.
            
            This endpoint should only be called after saving configuration.
            When running in Docker with a restart policy (e.g., restart: always),
            the container will automatically restart and load the new configuration.
            
            Returns:
                JSON: Confirmation message before process exits
            """
            logger.warning("Restart requested via Web UI. Process will exit now.")
            logger.warning("Container should restart automatically with restart policy.")
            
            # Flush all log handlers to ensure messages are written
            for handler in logging.root.handlers:
                handler.flush()
            
            # Return response first
            response = jsonify({
                'status': 'ok',
                'message': 'Application is restarting...'
            })
            
            # Schedule exit after response is sent
            # Use os._exit(0) to immediately terminate without cleanup
            # This is intentional - we want Docker to restart the container
            import threading
            def delayed_exit():
                import time
                time.sleep(0.5)  # Give time for response to be sent
                os._exit(0)
            
            threading.Thread(target=delayed_exit, daemon=True).start()
            
            return response
        
        @self.app.route('/web/<path:filename>')
        def serve_web_file(filename):
            """Serve static web files."""
            return self._serve_ui_file(filename)
    
    def _serve_ui_file(self, filename: str):
        """
        Serve a UI file from the web directory.
        
        Args:
            filename: File to serve
            
        Returns:
            File content or 404
        """
        web_dir = Path(__file__).parent / 'web'
        file_path = web_dir / filename
        
        if file_path.exists() and file_path.is_file():
            return send_from_directory(web_dir, filename)
        else:
            # If file doesn't exist, return a basic HTML page
            if filename == 'index.html':
                return self._get_default_index_html()
            return "File not found", 404
    
    def _get_default_index_html(self) -> str:
        """
        Get default index.html content if file doesn't exist.
        
        Returns:
            HTML string
        """
        return r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HeatTrax Scheduler</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .warning {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .card h2 {
            margin-top: 0;
            color: #2c3e50;
        }
        .card h3 {
            margin-top: 20px;
            margin-bottom: 15px;
            color: #34495e;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 8px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .status-item {
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }
        .status-item label {
            font-weight: 600;
            color: #555;
            display: block;
            margin-bottom: 5px;
        }
        .status-item value {
            color: #2c3e50;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            font-weight: 600;
            color: #555;
            margin-bottom: 5px;
        }
        .form-group input,
        .form-group select {
            width: 100%;
            padding: 8px 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            box-sizing: border-box;
        }
        .form-group input[type="checkbox"] {
            width: auto;
            margin-right: 8px;
        }
        .form-group input:disabled,
        .form-group select:disabled {
            background: #f5f5f5;
            color: #888;
            cursor: not-allowed;
        }
        .form-group .helper-text {
            font-size: 12px;
            color: #17a2b8;
            margin-top: 4px;
        }
        .form-group .helper-text code {
            background: #e8f4f8;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        button {
            background: #3498db;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background: #2980b9;
        }
        .error {
            color: #e74c3c;
            padding: 10px;
            background: #fadbd8;
            border-radius: 4px;
            margin-top: 10px;
        }
        .success {
            color: #27ae60;
            padding: 10px;
            background: #d5f4e6;
            border-radius: 4px;
            margin-top: 10px;
        }
        .button-group {
            margin-top: 15px;
            display: flex;
            gap: 10px;
        }
        .tab-container {
            margin-bottom: 20px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            border-bottom: 2px solid #ddd;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background: none;
            border: none;
            border-bottom: 3px solid transparent;
            color: #000;
        }
        .tab.active {
            border-bottom-color: #3498db;
            font-weight: 600;
            color: #000;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .device-health-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        .device-health-item {
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }
        .device-health-item.match {
            border-left-color: #27ae60;
        }
        .device-health-item.mismatch {
            border-left-color: #e74c3c;
        }
        .device-health-item .device-name {
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 8px;
            font-size: 16px;
        }
        .device-health-item .device-detail {
            font-size: 13px;
            color: #555;
            margin: 4px 0;
        }
        .device-health-item .device-detail label {
            font-weight: 600;
            margin-right: 5px;
        }
        .health-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .health-summary-item {
            padding: 15px;
            background: #e8f4f8;
            border-radius: 4px;
            text-align: center;
        }
        .health-summary-item .value {
            font-size: 24px;
            font-weight: 600;
            color: #2c3e50;
        }
        .health-summary-item .label {
            font-size: 12px;
            color: #555;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔥 HeatTrax Scheduler</h1>
        <p>Weather-based automation for heated mats and smart devices</p>
    </div>

    <div id="security-warning" class="warning" style="display: none;">
        <strong>⚠️ Security Warning:</strong> Web UI is accessible over the network and authentication is disabled. 
        Do not expose this service directly to the internet.
    </div>

    <div class="tab-container">
        <div class="tabs">
            <button class="tab active" onclick="switchTab('status')">Status</button>
            <button class="tab" onclick="switchTab('config')">Configuration</button>
            <button class="tab" onclick="switchTab('health')">Health</button>
        </div>
    </div>

    <div id="status-tab" class="tab-content active">
        <div class="card">
            <h2>System Status</h2>
            <button onclick="refreshStatus()">🔄 Refresh</button>
            <div id="status-content" class="status-grid">
                <div class="status-item">
                    <label>Loading...</label>
                </div>
            </div>
        </div>
    </div>

    <div id="config-tab" class="tab-content">
        <div id="env-overrides-info"></div>
        <div class="card">
            <h2>Configuration Editor</h2>
            <p>Configure your HeatTrax Scheduler settings below. Fields marked as read-only are controlled by environment variables.</p>
            <form id="config-form">
                <!-- Form sections will be populated here -->
            </form>
            <div class="button-group">
                <button onclick="loadConfig()">🔄 Reload</button>
                <button onclick="saveConfig()">💾 Save Configuration</button>
            </div>
            <div id="config-message"></div>
        </div>
    </div>

    <div id="health-tab" class="tab-content">
        <div class="card">
            <h2>Health Summary</h2>
            <button onclick="refreshHealth()">🔄 Refresh</button>
            <div id="health-summary" class="health-summary">
                <div class="health-summary-item">
                    <div class="value">-</div>
                    <div class="label">System Status</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Health Checks</h2>
            <div id="health-checks-content">
                <p>Loading health information...</p>
            </div>
        </div>
        
        <div class="card">
            <h2>Device Health</h2>
            <div id="device-health-content" class="device-health-grid">
                <div class="device-health-item">
                    <div class="device-name">Loading...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
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
            
            if (tabName === 'status') {
                refreshStatus();
            } else if (tabName === 'config') {
                loadConfig();
            } else if (tabName === 'health') {
                refreshHealth();
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

        // Refresh status
        async function refreshStatus() {
            const statusContent = document.getElementById('status-content');
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                
                let html = '';
                
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

        // Refresh health information
        async function refreshHealth() {
            const healthSummary = document.getElementById('health-summary');
            const healthChecksContent = document.getElementById('health-checks-content');
            const deviceHealthContent = document.getElementById('device-health-content');
            
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
                
                // Update device health
                if (status.device_expectations && status.device_expectations.length > 0) {
                    let deviceHtml = '';
                    
                    for (const device of status.device_expectations) {
                        const isMatch = device.current_state === device.expected_state;
                        const cssClass = isMatch ? 'match' : 'mismatch';
                        
                        deviceHtml += `
                            <div class="device-health-item ${cssClass}">
                                <div class="device-name">${device.device_name || 'Unknown Device'}</div>
                                <div class="device-detail">
                                    <label>Group:</label> ${device.group || 'N/A'}
                                </div>
                                <div class="device-detail">
                                    <label>IP:</label> ${device.ip_address || 'N/A'}
                                </div>
                                <div class="device-detail">
                                    <label>Outlet:</label> ${device.outlet !== undefined ? device.outlet : 'N/A'}
                                </div>
                                <div class="device-detail">
                                    <label>Current State:</label> ${device.current_state || 'unknown'}
                                </div>
                                <div class="device-detail">
                                    <label>Expected State:</label> ${device.expected_state || 'unknown'}
                                </div>
                        `;
                        
                        if (device.expected_on_from) {
                            deviceHtml += `
                                <div class="device-detail">
                                    <label>Expected ON from:</label> ${new Date(device.expected_on_from).toLocaleString()}
                                </div>
                            `;
                        }
                        
                        if (device.expected_off_at) {
                            deviceHtml += `
                                <div class="device-detail">
                                    <label>Expected OFF at:</label> ${new Date(device.expected_off_at).toLocaleString()}
                                </div>
                            `;
                        }
                        
                        if (device.last_state_change) {
                            deviceHtml += `
                                <div class="device-detail">
                                    <label>Last State Change:</label> ${new Date(device.last_state_change).toLocaleString()}
                                </div>
                            `;
                        }
                        
                        if (device.last_error) {
                            deviceHtml += `
                                <div class="device-detail" style="color: #e74c3c;">
                                    <label>Last Error:</label> ${device.last_error}
                                </div>
                            `;
                        }
                        
                        deviceHtml += '</div>';
                    }
                    
                    deviceHealthContent.innerHTML = deviceHtml;
                } else {
                    deviceHealthContent.innerHTML = '<div class="status-item"><label>No device expectations available</label></div>';
                }
                
            } catch (e) {
                healthSummary.innerHTML = '<div class="error">Failed to load health data</div>';
                healthChecksContent.innerHTML = `<div class="error">Error: ${e.message}</div>`;
                deviceHealthContent.innerHTML = `<div class="error">Error: ${e.message}</div>`;
            }
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
                { path: 'devices.credentials.username', label: 'Tapo Username', type: 'text' },
                { path: 'devices.credentials.password', label: 'Tapo Password', type: 'password' }
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
            
            for (let i = 0; i < parts.length - 1; i++) {
                const part = parts[i];
                if (!(part in current)) {
                    current[part] = {};
                }
                current = current[part];
            }
            
            current[parts[parts.length - 1]] = value;
        }

        // Collect form values into config object
        function collectFormValues() {
            const config = {};
            
            for (const [sectionName, fields] of Object.entries(FORM_FIELDS)) {
                for (const fieldDef of fields) {
                    const fieldId = 'field-' + fieldDef.path.replace(/\\./g, '-');
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

        // Initialize on load
        window.addEventListener('load', () => {
            checkSecurity();
            refreshStatus();
        });
    </script>
</body>
</html>"""
    
    def _get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status.
        
        Returns:
            Dictionary with system status
        """
        status = {}
        
        # Add config metadata
        config_status = self.config_manager.get_status()
        status.update(config_status)
        
        # Add scheduler-specific status if available
        if self.scheduler:
            try:
                # Get weather enabled status
                config = self.config_manager.get_config(include_secrets=False)
                status['weather_enabled'] = config.get('weather_api', {}).get('enabled', True)
                
                # Get device groups info
                devices = config.get('devices', {})
                groups = devices.get('groups', {})
                
                device_groups = {}
                for group_name, group_config in groups.items():
                    items = group_config.get('items', [])
                    device_groups[group_name] = {
                        'enabled': group_config.get('enabled', True),
                        'device_count': len(items)
                    }
                
                status['device_groups'] = device_groups
                
                # Try to get weather service status
                if hasattr(self.scheduler, 'weather') and self.scheduler.weather:
                    weather = self.scheduler.weather
                    if hasattr(weather, 'last_successful_fetch'):
                        status['last_weather_fetch'] = weather.last_successful_fetch.isoformat() if weather.last_successful_fetch else None
                    if hasattr(weather, 'state'):
                        status['weather_state'] = weather.state
                
                # Get device expectations for health monitoring
                if hasattr(self.scheduler, 'get_device_expectations'):
                    try:
                        # This is an async method, so we need to run it in an event loop
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            expectations = loop.run_until_complete(self.scheduler.get_device_expectations())
                            status['device_expectations'] = expectations
                        finally:
                            loop.close()
                    except Exception as e:
                        logger.warning(f"Could not get device expectations: {e}")
                        status['device_expectations'] = []
                
            except Exception as e:
                logger.warning(f"Could not get full scheduler status: {e}")
                status['last_error'] = str(e)
        
        status['timestamp'] = datetime.now().isoformat()
        
        return status
    
    def run(self, host: str = '127.0.0.1', port: int = 4328, debug: bool = False):
        """
        Run the web server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            debug: Enable debug mode
        """
        # Log security warning if binding to non-local address
        if host not in ['127.0.0.1', 'localhost']:
            logger.warning("=" * 80)
            logger.warning("SECURITY WARNING: Web UI is accessible over the network")
            logger.warning(f"Binding to: {host}:{port}")
            
            config = self.config_manager.get_config(include_secrets=False)
            auth_enabled = config.get('web', {}).get('auth', {}).get('enabled', False)
            
            if not auth_enabled:
                logger.warning("Authentication is DISABLED")
                logger.warning("Do not expose this service directly to the internet")
            
            logger.warning("=" * 80)
        
        logger.info(f"Starting web server on {host}:{port}")
        
        # Run Flask app
        self.app.run(host=host, port=port, debug=debug, use_reloader=False)

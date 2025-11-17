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
        return """<!DOCTYPE html>
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
        textarea {
            width: 100%;
            min-height: 400px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
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
        }
        .tab.active {
            border-bottom-color: #3498db;
            font-weight: 600;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
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
        <div class="card">
            <h2>Configuration Editor</h2>
            <p>Edit the configuration below. Changes are validated before saving.</p>
            <textarea id="config-editor">Loading configuration...</textarea>
            <div class="button-group">
                <button onclick="loadConfig()">🔄 Reload</button>
                <button onclick="saveConfig()">💾 Save Configuration</button>
            </div>
            <div id="config-message"></div>
        </div>
    </div>

    <script>
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
            }
        }

        // Check for security warning
        async function checkSecurity() {
            try {
                const response = await fetch('/api/config');
                const config = await response.json();
                
                if (config.web && config.web.bind_host && config.web.bind_host !== '127.0.0.1' && config.web.bind_host !== 'localhost') {
                    if (config.web.auth && !config.web.auth.enabled) {
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

        // Load configuration
        async function loadConfig() {
            const editor = document.getElementById('config-editor');
            const message = document.getElementById('config-message');
            message.innerHTML = '';
            
            try {
                const response = await fetch('/api/config');
                const config = await response.json();
                
                // Pretty print JSON
                editor.value = JSON.stringify(config, null, 2);
            } catch (e) {
                message.innerHTML = `<div class="error">Failed to load configuration: ${e.message}</div>`;
            }
        }

        // Save configuration
        async function saveConfig() {
            const editor = document.getElementById('config-editor');
            const message = document.getElementById('config-message');
            message.innerHTML = '';
            
            try {
                // Parse JSON
                const config = JSON.parse(editor.value);
                
                // Send to API
                const response = await fetch('/api/config', {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(config)
                });
                
                const result = await response.json();
                
                if (result.status === 'ok') {
                    let msg = '<div class="success">✅ Configuration saved successfully!</div>';
                    if (result.restart_required === 'true') {
                        msg += '<div class="warning" style="margin-top: 10px;">⚠️ Some changes require a restart to take effect.</div>';
                    }
                    message.innerHTML = msg;
                    
                    // Reload config to show any server-side changes
                    setTimeout(loadConfig, 1000);
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

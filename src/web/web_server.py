"""Flask web server for HeatTrax Scheduler UI and API."""

import logging
import os
import re
import shutil
import threading
import time
import yaml
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from flask import Flask, request, jsonify, send_from_directory, render_template, abort, send_file
from pathlib import Path
from werkzeug.utils import secure_filename

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
        # Static and template folders are relative to this module's location
        module_dir = Path(__file__).parent
        self.app = Flask(__name__, 
                         static_folder=str(module_dir / 'static'),
                         template_folder=str(module_dir / 'templates'))
        
        # Disable Flask's default logging to stdout (use our logging)
        import logging as flask_logging
        flask_log = flask_logging.getLogger('werkzeug')
        flask_log.setLevel(logging.WARNING)
        
        # Initialize manual override manager
        # Use scheduler's manual override if available, otherwise create new one
        if scheduler and hasattr(scheduler, 'manual_override'):
            self.manual_override = scheduler.manual_override
            logger.info("Using scheduler's manual override manager")
        else:
            from src.state.manual_override import ManualOverrideManager
            config = config_manager.get_config(include_secrets=False)
            timezone = config.get('location', {}).get('timezone', 'America/New_York')
            self.manual_override = ManualOverrideManager(timezone=timezone)
            logger.info("Created new manual override manager")
        
        # Initialize authentication for mobile control
        from src.web.auth import init_auth
        config = config_manager.get_config(include_secrets=False)
        web_config = config.get('web', {})
        pin = web_config.get('pin', '1234')
        init_auth(self.app, pin)
        
        # Register routes
        self._register_routes()
        
        logger.info("WebServer initialized")
    
    def _schedule_restart(self, delay: float = 0.5):
        """
        Schedule application restart after a delay.
        
        Args:
            delay: Delay in seconds before exit (default: 0.5)
        """
        def delayed_exit():
            time.sleep(delay)
            os._exit(0)
        
        threading.Thread(target=delayed_exit, daemon=True).start()
    
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
        
        @self.app.route('/api/credentials', methods=['POST'])
        def api_credentials_update():
            """
            Update Tapo credentials.
            
            This endpoint specifically handles updating Tapo username and password.
            When credentials are updated via the Web UI, they will be persisted to config.yaml.
            
            Expects:
                JSON: {"username": "user@example.com", "password": "password123"}
                
            Returns:
                JSON: Update result with status and restart_required flag
            """
            try:
                if not request.is_json:
                    return jsonify({
                        'status': 'error',
                        'message': 'Request must be JSON'
                    }), 400
                
                data = request.get_json()
                
                if 'username' not in data or 'password' not in data:
                    return jsonify({
                        'status': 'error',
                        'message': 'Both username and password are required'
                    }), 400
                
                username = data['username']
                password = data['password']
                
                # Validate credentials using the validator
                from src.config.credential_validator import is_valid_credential
                is_valid, reason = is_valid_credential(username, password)
                
                if not is_valid:
                    return jsonify({
                        'status': 'error',
                        'message': f'Invalid credentials: {reason}'
                    }), 400
                
                # Get current config
                current_config = self.config_manager.get_config(include_secrets=True)
                
                # Update credentials section
                if 'devices' not in current_config:
                    current_config['devices'] = {}
                if 'credentials' not in current_config['devices']:
                    current_config['devices']['credentials'] = {}
                
                current_config['devices']['credentials']['username'] = username
                current_config['devices']['credentials']['password'] = password
                
                # Update configuration (will persist to config.yaml)
                result = self.config_manager.update_config(current_config, preserve_secrets=False)
                
                if result['status'] == 'ok':
                    logger.info("Tapo credentials updated successfully via Web UI")
                    logger.info("Credentials have been written to config.yaml")
                    
                    # Always require restart after credential changes
                    result['restart_required'] = 'true'
                    result['message'] = 'Credentials updated successfully and saved to config.yaml. Restart required to enable device control.'
                    
                    return jsonify(result)
                else:
                    return jsonify(result), 400
                    
            except Exception as e:
                logger.error(f"Failed to update credentials: {e}", exc_info=True)
                return jsonify({
                    'status': 'error',
                    'message': f'Failed to update credentials: {str(e)}'
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
            self._schedule_restart(delay=0.5)
            
            return response
        
        @self.app.route('/api/config/download', methods=['GET'])
        def api_config_download():
            """
            Download current config.yaml file.
            
            Returns:
                File: config.yaml file for download
            """
            try:
                config_path = self.config_manager.config_path
                
                if not config_path.exists():
                    return jsonify({
                        'error': 'Configuration file not found'
                    }), 404
                
                # Send file with appropriate headers for download
                return send_file(
                    str(config_path),
                    mimetype='application/x-yaml',
                    as_attachment=True,
                    download_name='config.yaml'
                )
                
            except Exception as e:
                logger.error(f"Failed to download config: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to download configuration file',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/config/upload', methods=['POST'])
        def api_config_upload():
            """
            Upload and validate new config.yaml file.
            
            Expects:
                multipart/form-data with 'config_file' field
            
            Returns:
                JSON: Upload result with validation status
            """
            try:
                # Check if file is present in request
                if 'config_file' not in request.files:
                    return jsonify({
                        'status': 'error',
                        'message': 'No file uploaded',
                        'error': 'Missing config_file in request'
                    }), 400
                
                file = request.files['config_file']
                
                # Check if file was selected
                if file.filename == '':
                    return jsonify({
                        'status': 'error',
                        'message': 'No file selected',
                        'error': 'Empty filename'
                    }), 400
                
                # Validate file extension
                filename = secure_filename(file.filename)
                if not (filename.endswith('.yaml') or filename.endswith('.yml')):
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid file type',
                        'error': 'File must have .yaml or .yml extension'
                    }), 400
                
                # Read file content
                try:
                    file_content = file.read().decode('utf-8')
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to read file',
                        'error': f'Could not decode file content: {str(e)}'
                    }), 400
                
                # Parse YAML
                try:
                    new_config = yaml.safe_load(file_content)
                except yaml.YAMLError as e:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid YAML syntax',
                        'error': str(e),
                        'validation_errors': [f'YAML parsing error: {str(e)}']
                    }), 400
                
                # Validate configuration structure and content
                validation_errors = self._validate_uploaded_config(new_config)
                
                if validation_errors:
                    return jsonify({
                        'status': 'error',
                        'message': 'Configuration validation failed',
                        'validation_errors': validation_errors,
                        'help': 'Common issues: missing outlets field, invalid web port (must be 1-65535), invalid IP addresses, invalid coordinates.'
                    }), 400
                
                # Create backup of current config
                config_path = self.config_manager.config_path
                backup_file = None
                
                if config_path.exists():
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_path = config_path.parent / f"config.yaml.backup.{timestamp}"
                    
                    try:
                        shutil.copy2(str(config_path), str(backup_path))
                        backup_file = backup_path.name
                        logger.info(f"Created config backup: {backup_path}")
                    except Exception as e:
                        logger.error(f"Failed to create backup: {e}", exc_info=True)
                        return jsonify({
                            'status': 'error',
                            'message': 'Failed to create backup',
                            'error': str(e)
                        }), 500
                
                # Write new config to disk
                try:
                    with open(config_path, 'w') as f:
                        yaml.safe_dump(new_config, f, default_flow_style=False, sort_keys=False)
                    logger.info(f"Successfully wrote new config to {config_path}")
                except Exception as e:
                    logger.error(f"Failed to write new config: {e}", exc_info=True)
                    
                    # Try to restore backup if write failed
                    if backup_file:
                        backup_path = config_path.parent / backup_file
                        try:
                            shutil.copy2(str(backup_path), str(config_path))
                            logger.info("Restored backup after write failure")
                        except Exception as restore_error:
                            logger.error(f"Failed to restore backup: {restore_error}")
                    
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to write configuration file',
                        'error': str(e)
                    }), 500
                
                # Note: Configuration is written to disk. Application restart is required
                # to fully reload the configuration. The config_manager could be reloaded here,
                # but since environment variables and other startup processes may affect the
                # configuration, a full restart is the safest approach.
                logger.info("Configuration file updated successfully. Restart required to apply changes.")
                
                response = jsonify({
                    'status': 'ok',
                    'message': 'Configuration uploaded and validated successfully',
                    'backup_created': backup_file is not None,
                    'backup_file': backup_file,
                    'restart_required': True
                })
                
                # Trigger automatic restart after successful config upload
                logger.warning("Config upload successful. Initiating automatic restart...")
                self._schedule_restart(delay=0.5)
                
                return response
                
            except Exception as e:
                logger.error(f"Failed to upload config: {e}", exc_info=True)
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to upload configuration',
                    'error': str(e)
                }), 500
        
        @self.app.route('/api/devices/status', methods=['GET'])
        def api_devices_status():
            """
            Get detailed status of all devices and outlets.
            
            This endpoint returns real-time status information for all configured
            devices including their reachability, outlet states, and any errors.
            Also includes initialization summary to help diagnose when devices
            fail to initialize (e.g., timeout during discovery).
            
            Returns:
                JSON: List of devices with outlet states, reachability info, and initialization summary
                {
                    "status": "ok",
                    "devices": [
                        {
                            "name": "Device Name",
                            "ip_address": "192.168.1.100",
                            "group": "group_name",
                            "reachable": true/false,
                            "initialized": true/false,
                            "has_outlets": true/false,
                            "outlets": [
                                {
                                    "index": 0,
                                    "is_on": true/false,
                                    "alias": "Outlet 0",
                                    "controlled": true/false
                                }
                            ],
                            "error": null or error message,
                            "initialization_error": null or error message from initialization
                        }
                    ],
                    "initialization_summary": {
                        "total_groups": 1,
                        "overall": {
                            "configured_devices": 1,
                            "initialized_devices": 0,
                            "failed_devices": 1
                        },
                        "groups": {
                            "group_name": {
                                "configured_count": 1,
                                "initialized_count": 0,
                                "failed_count": 1,
                                "failed_devices": [...]
                            }
                        }
                    },
                    "timestamp": "2024-01-01T12:00:00"
                }
            """
            try:
                if not self.scheduler:
                    return jsonify({
                        'error': 'Scheduler not available'
                    }), 503
                
                if self.scheduler.device_manager is None:
                    return jsonify({
                        'error': 'Device manager not available',
                        'setup_mode': True,
                        'message': 'Configure valid Tapo credentials to enable device control'
                    }), 503
                
                # Check if scheduler has the run_coro_in_loop method (for thread-safe async execution)
                if hasattr(self.scheduler, 'run_coro_in_loop'):
                    # Use the scheduler's event loop to avoid python-kasa async issues
                    # This prevents "Timeout context manager should be used inside a task" errors
                    try:
                        devices_status = self.scheduler.run_coro_in_loop(
                            self.scheduler.device_manager.get_all_devices_status()
                        )
                    except RuntimeError as e:
                        logger.error(f"Scheduler loop not available: {e}")
                        return jsonify({
                            'error': 'Async operations not available',
                            'details': str(e)
                        }), 500
                else:
                    # Fallback for backward compatibility (though this may cause kasa errors)
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        devices_status = loop.run_until_complete(
                            self.scheduler.device_manager.get_all_devices_status()
                        )
                    finally:
                        loop.close()
                
                # Get initialization summary
                init_summary = self.scheduler.device_manager.get_initialization_summary()
                
                return jsonify({
                    'status': 'ok',
                    'devices': devices_status,
                    'initialization_summary': init_summary,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Failed to get devices status: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to get devices status',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/devices/control', methods=['POST'])
        def api_devices_control():
            """
            Control a specific device or outlet.
            
            This endpoint allows manual control of devices and individual outlets.
            Manual control overrides scheduled behavior temporarily. The scheduler
            will reassert control on its next cycle (typically within check_interval_minutes).
            
            For best practices:
            - Manual ON: Device stays on until scheduler turns it off or max_runtime_hours exceeded
            - Manual OFF: Device stays off until scheduler turns it on based on conditions
            - The scheduler does not track manual overrides; it simply evaluates conditions
              and sets the desired state on each cycle
            
            Expects JSON:
                {
                    "group": "group_name",
                    "device": "device_name",
                    "outlet": outlet_index or null,  # null for entire device
                    "action": "on" or "off"
                }
            
            Returns:
                JSON: Control operation result
                {
                    "success": true/false,
                    "device": "device_name",
                    "outlet": outlet_index or null,
                    "action": "on" or "off",
                    "error": null or error message
                }
            """
            try:
                if not self.scheduler:
                    return jsonify({
                        'success': False,
                        'error': 'Scheduler not available'
                    }), 503
                
                if self.scheduler.device_manager is None:
                    return jsonify({
                        'success': False,
                        'error': 'Device manager not available',
                        'setup_mode': True,
                        'message': 'Configure valid Tapo credentials to enable device control'
                    }), 503
                
                if not request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Request must be JSON'
                    }), 400
                
                data = request.get_json()
                
                # Validate required fields
                required_fields = ['group', 'device', 'action']
                for field in required_fields:
                    if field not in data:
                        return jsonify({
                            'success': False,
                            'error': f"Missing required field: {field}"
                        }), 400
                
                group_name = data['group']
                device_name = data['device']
                outlet_index = data.get('outlet')  # May be None
                action = data['action']
                
                # Validate action
                if action not in ['on', 'off']:
                    return jsonify({
                        'success': False,
                        'error': f"Invalid action: {action}. Must be 'on' or 'off'"
                    }), 400
                
                # Control the device asynchronously using scheduler's event loop
                # Check if scheduler has the run_coro_in_loop method (for thread-safe async execution)
                if hasattr(self.scheduler, 'run_coro_in_loop'):
                    # Use the scheduler's event loop to avoid python-kasa async issues
                    # This prevents "Timeout context manager should be used inside a task" errors
                    try:
                        result = self.scheduler.run_coro_in_loop(
                            self.scheduler.device_manager.control_device_outlet(
                                group_name, device_name, outlet_index, action
                            )
                        )
                    except RuntimeError as e:
                        logger.error(f"Scheduler loop not available: {e}")
                        return jsonify({
                            'success': False,
                            'error': 'Async operations not available',
                            'details': str(e)
                        }), 500
                else:
                    # Fallback for backward compatibility (though this may cause kasa errors)
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            self.scheduler.device_manager.control_device_outlet(
                                group_name, device_name, outlet_index, action
                            )
                        )
                    finally:
                        loop.close()
                
                if result['success']:
                    logger.info(
                        f"Manual control via WebUI: {action.upper()} device '{device_name}' "
                        f"outlet {outlet_index} in group '{group_name}'"
                    )
                    return jsonify(result)
                else:
                    return jsonify(result), 400
                
            except Exception as e:
                logger.error(f"Failed to control device: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': 'Failed to control device',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/groups/<group_name>/control', methods=['POST'])
        def api_groups_control(group_name):
            """
            Control all outlets in a device group simultaneously.
            
            This endpoint allows turning all outlets in a group ON or OFF at once.
            This provides a convenient way to control multiple devices with a single action.
            Manual control overrides scheduled behavior temporarily until the next scheduled action.
            
            Expects JSON:
                {
                    "action": "on" or "off"
                }
            
            Returns:
                JSON: Control operation result
                {
                    "success": true/false,
                    "group": "group_name",
                    "action": "on" or "off",
                    "results": [
                        {
                            "device": "device_name",
                            "outlet": outlet_index,
                            "success": true/false,
                            "error": null or error message
                        }
                    ],
                    "total": number,
                    "successful": number,
                    "failed": number,
                    "error": null or error message if complete failure
                }
            """
            try:
                if not self.scheduler:
                    return jsonify({
                        'success': False,
                        'error': 'Scheduler not available'
                    }), 503
                
                if self.scheduler.device_manager is None:
                    return jsonify({
                        'success': False,
                        'error': 'Device manager not available',
                        'setup_mode': True,
                        'message': 'Configure valid Tapo credentials to enable device control'
                    }), 503
                
                if not request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Request must be JSON'
                    }), 400
                
                data = request.get_json()
                
                # Validate required fields
                if 'action' not in data:
                    return jsonify({
                        'success': False,
                        'error': "Missing required field: action"
                    }), 400
                
                action = data['action']
                
                # Validate action
                if action not in ['on', 'off']:
                    return jsonify({
                        'success': False,
                        'error': f"Invalid action: {action}. Must be 'on' or 'off'"
                    }), 400
                
                # Get group config
                config = self.config_manager.get_config(include_secrets=False)
                groups = config.get('devices', {}).get('groups', {})
                
                if group_name not in groups:
                    return jsonify({
                        'success': False,
                        'error': f"Group '{group_name}' not found"
                    }), 404
                
                group_config = groups[group_name]
                items = group_config.get('items', [])
                
                if not items:
                    return jsonify({
                        'success': False,
                        'error': f"Group '{group_name}' has no configured devices"
                    }), 400
                
                # Control each outlet in the group
                results = []
                successful = 0
                failed = 0
                
                for item in items:
                    device_name = item.get('name')
                    outlets = item.get('outlets', [])
                    
                    # If no outlets specified, control the entire device (outlet=None)
                    if not outlets:
                        outlets = [None]
                    
                    for outlet_index in outlets:
                        try:
                            # Control the device asynchronously using scheduler's event loop
                            if hasattr(self.scheduler, 'run_coro_in_loop'):
                                result = self.scheduler.run_coro_in_loop(
                                    self.scheduler.device_manager.control_device_outlet(
                                        group_name, device_name, outlet_index, action
                                    )
                                )
                            else:
                                # Fallback for backward compatibility
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    result = loop.run_until_complete(
                                        self.scheduler.device_manager.control_device_outlet(
                                            group_name, device_name, outlet_index, action
                                        )
                                    )
                                finally:
                                    loop.close()
                            
                            results.append({
                                'device': device_name,
                                'outlet': outlet_index,
                                'success': result.get('success', False),
                                'error': result.get('error')
                            })
                            
                            if result.get('success'):
                                successful += 1
                            else:
                                failed += 1
                                
                        except Exception as e:
                            logger.error(f"Failed to control {device_name} outlet {outlet_index}: {e}")
                            results.append({
                                'device': device_name,
                                'outlet': outlet_index,
                                'success': False,
                                'error': str(e)
                            })
                            failed += 1
                
                logger.info(
                    f"Group control via WebUI: {action.upper()} group '{group_name}' "
                    f"({successful} successful, {failed} failed)"
                )
                
                return jsonify({
                    'success': successful > 0,
                    'group': group_name,
                    'action': action,
                    'results': results,
                    'total': len(results),
                    'successful': successful,
                    'failed': failed
                })
                
            except Exception as e:
                logger.error(f"Failed to control group: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': 'Failed to control group',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/groups/<group_name>/automation', methods=['GET'])
        def api_get_group_automation(group_name):
            """
            Get automation configuration for a specific group.
            
            Returns base automation from config.yaml, any overrides from state file,
            and the effective merged automation values.
            
            Args:
                group_name: Name of the device group
                
            Returns:
                JSON: {
                    "group": "group_name",
                    "base": {...},         # From config.yaml
                    "overrides": {...},    # From automation_overrides.json
                    "effective": {...},    # Merged result
                    "schedule": {          # Schedule info (read-only)
                        "on_time": "HH:MM",
                        "off_time": "HH:MM",
                        "valid": true/false
                    }
                }
            """
            try:
                if not self.scheduler:
                    return jsonify({
                        'error': 'Scheduler not available'
                    }), 503
                
                # Get group config
                config = self.config_manager.get_config(include_secrets=False)
                groups = config.get('devices', {}).get('groups', {})
                
                if group_name not in groups:
                    return jsonify({
                        'error': f"Group '{group_name}' not found"
                    }), 404
                
                group_config = groups[group_name]
                base_automation = group_config.get('automation', {})
                
                # Get overrides and effective automation
                overrides = self.scheduler.automation_overrides.get_group_overrides(group_name)
                effective = self.scheduler.automation_overrides.get_effective_automation(
                    group_name, base_automation
                )
                
                # Return schedules info from the new unified format
                schedules = group_config.get('schedules', [])
                
                return jsonify({
                    'group': group_name,
                    'base': base_automation,
                    'overrides': overrides,
                    'effective': effective,
                    'schedules_count': len(schedules)
                })
                
            except Exception as e:
                logger.error(f"Failed to get group automation: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to get group automation',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/groups/<group_name>/automation', methods=['PATCH'])
        def api_update_group_automation(group_name):
            """
            Update automation overrides for a specific group.
            
            Accepts a JSON body with automation flags to override. Set a flag to
            true/false to override, or null to clear the override and fall back
            to config.yaml value.
            
            Args:
                group_name: Name of the device group
                
            Expects JSON:
                {
                    "weather_control": true/false/null,
                    "precipitation_control": true/false/null,
                    "morning_mode": true/false/null
                }
            
            Note: schedule_control has been removed. Schedule-based automation
            is now handled via the unified schedules: array in config.yaml.
            
            Returns:
                JSON: Same structure as GET endpoint with updated values
            """
            try:
                if not self.scheduler:
                    return jsonify({
                        'error': 'Scheduler not available'
                    }), 503
                
                if not request.is_json:
                    return jsonify({
                        'error': 'Request must be JSON'
                    }), 400
                
                # Get group config
                config = self.config_manager.get_config(include_secrets=False)
                groups = config.get('devices', {}).get('groups', {})
                
                if group_name not in groups:
                    return jsonify({
                        'error': f"Group '{group_name}' not found"
                    }), 404
                
                data = request.get_json()
                
                # Valid automation flags (schedule_control removed - use unified schedules: array)
                valid_flags = [
                    'weather_control',
                    'precipitation_control',
                    'morning_mode'
                ]
                
                # Update each flag in the request
                for flag_name, flag_value in data.items():
                    if flag_name not in valid_flags:
                        logger.warning(f"Ignoring unknown automation flag: {flag_name}")
                        continue
                    
                    # Validate value is bool or None
                    if flag_value is not None and not isinstance(flag_value, bool):
                        return jsonify({
                            'error': f"Invalid value for {flag_name}: must be true, false, or null"
                        }), 400
                    
                    # Set the override
                    self.scheduler.automation_overrides.set_flag(group_name, flag_name, flag_value)
                    logger.info(f"Updated automation override: {group_name}.{flag_name} = {flag_value}")
                
                # Return updated state (same as GET endpoint)
                group_config = groups[group_name]
                base_automation = group_config.get('automation', {})
                overrides = self.scheduler.automation_overrides.get_group_overrides(group_name)
                effective = self.scheduler.automation_overrides.get_effective_automation(
                    group_name, base_automation
                )
                
                # Return schedules info from the new unified format
                schedules = group_config.get('schedules', [])
                
                return jsonify({
                    'group': group_name,
                    'base': base_automation,
                    'overrides': overrides,
                    'effective': effective,
                    'schedules_count': len(schedules)
                })
                
            except Exception as e:
                logger.error(f"Failed to update group automation: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to update group automation',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/vacation_mode', methods=['GET', 'PUT'])
        def api_vacation_mode():
            """
            Get or set vacation mode.
            
            GET: Returns current vacation mode status
            PUT: Updates vacation mode (expects JSON: {"enabled": true/false})
            """
            try:
                if request.method == 'GET':
                    if not self.scheduler:
                        return jsonify({'error': 'Scheduler not available'}), 503
                    
                    return jsonify({
                        'enabled': self.scheduler.vacation_mode
                    })
                
                elif request.method == 'PUT':
                    data = request.get_json()
                    if not data or 'enabled' not in data:
                        return jsonify({'error': 'Missing "enabled" field'}), 400
                    
                    enabled = bool(data['enabled'])
                    
                    # Update scheduler
                    if self.scheduler:
                        self.scheduler.vacation_mode = enabled
                        logger.info(f"Vacation mode {'enabled' if enabled else 'disabled'} via API")
                    
                    # Update config file
                    config = self.config_manager.get_config(include_secrets=True)
                    config['vacation_mode'] = enabled
                    
                    self.config_manager._write_config_to_disk(config)
                    
                    return jsonify({
                        'success': True,
                        'enabled': enabled
                    })
                    
            except Exception as e:
                logger.error(f"Failed to handle vacation mode: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to handle vacation mode',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/solar_times', methods=['GET'])
        def api_solar_times():
            """
            Get today's sunrise and sunset times.
            
            Returns:
                JSON: {
                    "date": "YYYY-MM-DD",
                    "sunrise": "HH:MM",
                    "sunset": "HH:MM",
                    "timezone": "America/New_York"
                }
            """
            try:
                if not self.scheduler or not self.scheduler.solar_calculator:
                    return jsonify({'error': 'Solar calculator not available'}), 503
                
                from datetime import date
                today = date.today()
                
                sunrise_time, sunset_time = self.scheduler.solar_calculator.calculate_solar_times(today)
                
                return jsonify({
                    'date': today.isoformat(),
                    'sunrise': sunrise_time.strftime('%H:%M'),
                    'sunset': sunset_time.strftime('%H:%M'),
                    'timezone': str(self.scheduler.timezone)
                })
                
            except Exception as e:
                logger.error(f"Failed to get solar times: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to get solar times',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/groups/<group_name>/schedules', methods=['GET', 'POST'])
        def api_group_schedules(group_name):
            """
            Get or add schedules for a group.
            
            GET: Returns all schedules for the group
            POST: Adds a new schedule to the group
            """
            try:
                config = self.config_manager.get_config(include_secrets=True)
                groups = config.get('devices', {}).get('groups', {})
                
                if group_name not in groups:
                    return jsonify({'error': f"Group '{group_name}' not found"}), 404
                
                if request.method == 'GET':
                    schedules = groups[group_name].get('schedules', [])
                    return jsonify({
                        'group': group_name,
                        'schedules': schedules
                    })
                
                elif request.method == 'POST':
                    new_schedule = request.get_json()
                    if not new_schedule:
                        return jsonify({'error': 'Missing schedule data'}), 400
                    
                    # Validate schedule
                    from src.scheduler.schedule_types import validate_schedules
                    is_valid, errors = validate_schedules([new_schedule])
                    if not is_valid:
                        return jsonify({
                            'error': 'Invalid schedule',
                            'details': errors
                        }), 400
                    
                    # Add schedule to group
                    schedules = groups[group_name].get('schedules', [])
                    schedules.append(new_schedule)
                    groups[group_name]['schedules'] = schedules
                    
                    # Save config
                    self.config_manager._write_config_to_disk(config)
                    
                    # Reload config from disk to sync in-memory cache
                    self.config_manager.reload_config()
                    
                    # Reload scheduler schedules
                    if self.scheduler:
                        from src.scheduler.schedule_types import parse_schedules
                        self.scheduler.group_schedules[group_name] = parse_schedules(schedules)
                    
                    logger.info(f"Added schedule '{new_schedule.get('name')}' to group '{group_name}'")
                    
                    return jsonify({
                        'success': True,
                        'schedule': new_schedule
                    }), 201
                    
            except Exception as e:
                logger.error(f"Failed to handle group schedules: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to handle group schedules',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/groups/<group_name>/schedules/<int:schedule_index>', methods=['GET', 'PUT', 'DELETE'])
        def api_group_schedule(group_name, schedule_index):
            """
            Get, update, or delete a specific schedule.
            
            GET: Returns the schedule at the given index
            PUT: Updates the schedule at the given index
            DELETE: Deletes the schedule at the given index
            """
            try:
                config = self.config_manager.get_config(include_secrets=True)
                groups = config.get('devices', {}).get('groups', {})
                
                if group_name not in groups:
                    return jsonify({'error': f"Group '{group_name}' not found"}), 404
                
                schedules = groups[group_name].get('schedules', [])
                
                if schedule_index < 0 or schedule_index >= len(schedules):
                    return jsonify({'error': f"Schedule index {schedule_index} out of range"}), 404
                
                if request.method == 'GET':
                    return jsonify({
                        'group': group_name,
                        'index': schedule_index,
                        'schedule': schedules[schedule_index]
                    })
                
                elif request.method == 'PUT':
                    updated_schedule = request.get_json()
                    if not updated_schedule:
                        return jsonify({'error': 'Missing schedule data'}), 400
                    
                    # Validate schedule
                    from src.scheduler.schedule_types import validate_schedules
                    is_valid, errors = validate_schedules([updated_schedule])
                    if not is_valid:
                        return jsonify({
                            'error': 'Invalid schedule',
                            'details': errors
                        }), 400
                    
                    # Update schedule
                    schedules[schedule_index] = updated_schedule
                    groups[group_name]['schedules'] = schedules
                    
                    # Save config
                    self.config_manager._write_config_to_disk(config)
                    
                    # Reload config from disk to sync in-memory cache
                    self.config_manager.reload_config()
                    
                    # Reload scheduler schedules
                    if self.scheduler:
                        from src.scheduler.schedule_types import parse_schedules
                        self.scheduler.group_schedules[group_name] = parse_schedules(schedules)
                    
                    logger.info(f"Updated schedule {schedule_index} for group '{group_name}'")
                    
                    return jsonify({
                        'success': True,
                        'schedule': updated_schedule
                    })
                
                elif request.method == 'DELETE':
                    # Remove schedule
                    removed_schedule = schedules.pop(schedule_index)
                    groups[group_name]['schedules'] = schedules
                    
                    # Save config
                    self.config_manager._write_config_to_disk(config)
                    
                    # Reload config from disk to sync in-memory cache
                    self.config_manager.reload_config()
                    
                    # Reload scheduler schedules
                    if self.scheduler:
                        from src.scheduler.schedule_types import parse_schedules
                        self.scheduler.group_schedules[group_name] = parse_schedules(schedules)
                    
                    logger.info(f"Deleted schedule {schedule_index} from group '{group_name}'")
                    
                    return jsonify({
                        'success': True,
                        'deleted': removed_schedule
                    })
                    
            except Exception as e:
                logger.error(f"Failed to handle group schedule: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to handle group schedule',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/groups/<group_name>/schedules/<int:schedule_index>/enabled', methods=['PUT'])
        def api_toggle_schedule_enabled(group_name, schedule_index):
            """
            Toggle a schedule's enabled status.
            
            Expects JSON: {"enabled": true/false}
            """
            try:
                data = request.get_json()
                if not data or 'enabled' not in data:
                    return jsonify({'error': 'Missing "enabled" field'}), 400
                
                enabled = bool(data['enabled'])
                
                config = self.config_manager.get_config(include_secrets=True)
                groups = config.get('devices', {}).get('groups', {})
                
                if group_name not in groups:
                    return jsonify({'error': f"Group '{group_name}' not found"}), 404
                
                schedules = groups[group_name].get('schedules', [])
                
                if schedule_index < 0 or schedule_index >= len(schedules):
                    return jsonify({'error': f"Schedule index {schedule_index} out of range"}), 404
                
                # Update enabled status
                schedules[schedule_index]['enabled'] = enabled
                groups[group_name]['schedules'] = schedules
                
                # Save config
                self.config_manager._write_config_to_disk(config)
                
                # Reload config from disk to sync in-memory cache
                self.config_manager.reload_config()
                
                # Reload scheduler schedules
                if self.scheduler:
                    from src.scheduler.schedule_types import parse_schedules
                    self.scheduler.group_schedules[group_name] = parse_schedules(schedules)
                
                logger.info(
                    f"{'Enabled' if enabled else 'Disabled'} schedule {schedule_index} "
                    f"for group '{group_name}'"
                )
                
                return jsonify({
                    'success': True,
                    'enabled': enabled
                })
                
            except Exception as e:
                logger.error(f"Failed to toggle schedule enabled: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to toggle schedule enabled',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/weather/forecast', methods=['GET'])
        def api_weather_forecast():
            """
            Get cached weather forecast data.
            
            This is a strictly read-only endpoint that returns cached weather data.
            Does NOT trigger any outbound network calls to weather providers.
            
            Returns:
                JSON: Weather forecast with hourly data, alerts, and metadata
            """
            try:
                if not self.scheduler:
                    return jsonify({
                        'status': 'no_data',
                        'reason': 'Scheduler not available'
                    }), 200
                
                # Check if weather is enabled
                config = self.config_manager.get_config(include_secrets=False)
                weather_enabled = config.get('weather_api', {}).get('enabled', True)
                
                if not weather_enabled:
                    return jsonify({
                        'status': 'no_data',
                        'reason': 'Weather service is disabled in configuration'
                    }), 200
                
                # Get weather service
                weather = getattr(self.scheduler, 'weather', None)
                if not weather:
                    return jsonify({
                        'status': 'no_data',
                        'reason': 'Weather service not initialized'
                    }), 200
                
                # Get cached data
                cache = getattr(weather, 'cache', None)
                if not cache or not cache.cache_data:
                    return jsonify({
                        'status': 'no_data',
                        'reason': 'No cached weather data available'
                    }), 200
                
                # Check cache validity
                cache_age_hours = cache.get_cache_age_hours()
                cache_valid_hours = config.get('weather_api', {}).get('resilience', {}).get(
                    'cache_valid_hours', 6.0
                )
                
                # Build response from cached data
                cache_data = cache.cache_data
                
                # Get provider info
                provider = config.get('weather_api', {}).get('provider', 'open-meteo')
                
                # Get timezone from location config
                timezone = config.get('location', {}).get('timezone', 'auto')
                
                # Get last fetch time
                last_updated = cache_data.get('fetched_at')
                
                # Build hourly forecast data
                hours = []
                forecast_list = cache_data.get('forecast', [])
                
                # Get black ice detection config
                thresholds = config.get('thresholds', {})
                black_ice_config = thresholds.get('black_ice_detection', {})
                black_ice_enabled = black_ice_config.get('enabled', True)
                temp_max = black_ice_config.get('temperature_max_f', 36.0)
                dew_spread_max = black_ice_config.get('dew_point_spread_f', 4.0)
                humidity_min = black_ice_config.get('humidity_min_percent', 80.0)
                
                for entry in forecast_list:
                    temp_f = entry.get('temperature_f')
                    dewpoint_f = entry.get('dewpoint_f')
                    humidity = entry.get('humidity_percent')
                    
                    # Calculate black ice risk
                    black_ice_risk = False
                    if black_ice_enabled and temp_f is not None and dewpoint_f is not None and humidity is not None:
                        dew_spread = temp_f - dewpoint_f
                        if temp_f <= temp_max and dew_spread <= dew_spread_max and humidity >= humidity_min:
                            black_ice_risk = True
                    
                    hour_data = {
                        'time': entry.get('timestamp'),
                        'temp_f': temp_f,
                        'temp_c': round((temp_f - 32) * 5/9, 1) if temp_f else None,
                        'dewpoint_f': dewpoint_f,
                        'dewpoint_c': round((dewpoint_f - 32) * 5/9, 1) if dewpoint_f else None,
                        'humidity_percent': humidity,
                        'black_ice_risk': black_ice_risk,
                        'precip_prob': None,  # Not stored in current cache format
                        'precip_intensity': entry.get('precipitation_mm'),
                        'precip_type': 'snow' if temp_f and temp_f <= 32 and entry.get('precipitation_mm', 0) > 0 else ('rain' if entry.get('precipitation_mm', 0) > 0 else None),
                        'wind_speed_mph': None,  # Not stored in current cache format
                        'wind_gust_mph': None,  # Not stored in current cache format
                        'alerts': [],
                        'raw': entry
                    }
                    hours.append(hour_data)
                
                # Get weather state
                weather_state = None
                if hasattr(weather, 'state'):
                    state = weather.state
                    if hasattr(state, 'value'):
                        weather_state = state.value
                    elif hasattr(state, 'name'):
                        weather_state = state.name
                    else:
                        weather_state = str(state)
                
                # Get configured forecast hours from scheduler config and validate
                forecast_hours = config.get('scheduler', {}).get('forecast_hours', 12)
                if not isinstance(forecast_hours, int) or forecast_hours < 1:
                    forecast_hours = 12
                
                return jsonify({
                    'status': 'ok',
                    'last_updated': last_updated,
                    'provider': provider,
                    'timezone': timezone,
                    'cache_age_hours': cache_age_hours,
                    'cache_valid_hours': cache_valid_hours,
                    'forecast_hours': forecast_hours,
                    'hours': hours,
                    'alerts': [],  # Would need additional data source for alerts
                    'weather_state': weather_state
                })
                
            except Exception as e:
                logger.error(f"Failed to get weather forecast: {e}", exc_info=True)
                return jsonify({
                    'status': 'error',
                    'error': 'Failed to retrieve weather forecast',
                    'details': str(e)
                }), 500
        
        @self.app.route('/api/weather/mat-forecast', methods=['GET'])
        def api_weather_mat_forecast():
            """
            Get predicted mat ON/OFF windows per group over the configured forecast horizon.
            
            This is a strictly read-only endpoint that predicts future mat behavior.
            Does NOT perform device control or external network calls.
            
            Returns:
                JSON: Per-group predicted ON/OFF windows
            """
            try:
                if not self.scheduler:
                    return jsonify({
                        'status': 'no_data',
                        'reason': 'Scheduler not available'
                    }), 200
                
                # Get configuration
                config = self.config_manager.get_config(include_secrets=False)
                
                # Get forecast horizon from config
                forecast_hours = config.get('scheduler', {}).get('forecast_hours', 12)
                
                # Use 60-minute step as default (hourly granularity)
                step_minutes = 60
                
                # Call scheduler prediction method
                try:
                    groups_data = self.scheduler.predict_group_windows(
                        horizon_hours=forecast_hours,
                        step_minutes=step_minutes
                    )
                except Exception as e:
                    logger.error(f"Error calling predict_group_windows: {e}", exc_info=True)
                    return jsonify({
                        'status': 'error',
                        'error': 'Failed to predict mat forecast',
                        'details': str(e)
                    }), 500
                
                return jsonify({
                    'status': 'ok',
                    'horizon_hours': forecast_hours,
                    'step_minutes': step_minutes,
                    'generated_at': datetime.now().isoformat(),
                    'groups': groups_data
                })
                
            except Exception as e:
                logger.error(f"Failed to get mat forecast: {e}", exc_info=True)
                return jsonify({
                    'status': 'error',
                    'error': 'Failed to retrieve mat forecast',
                    'details': str(e)
                }), 500
        
        # Mobile control routes
        @self.app.route('/control/login')
        def control_login():
            """Serve mobile control login page."""
            return render_template('login.html')
        
        @self.app.route('/control')
        def control_page():
            """Serve mobile control page."""
            from src.web.auth import require_auth
            from flask import session
            
            # Check authentication
            if not session.get('authenticated'):
                from flask import redirect, url_for
                return redirect(url_for('control_login'))
            
            # Check session expiration
            auth_time = session.get('authenticated_at')
            if auth_time:
                try:
                    from datetime import datetime
                    auth_datetime = datetime.fromisoformat(auth_time)
                    now = datetime.now()
                    
                    # Session expires after 24 hours
                    if now - auth_datetime > timedelta(hours=24):
                        logger.info("Session expired")
                        session.clear()
                        from flask import redirect, url_for
                        return redirect(url_for('control_login'))
                except Exception as e:
                    logger.error(f"Failed to check session expiration: {e}")
            
            return render_template('control.html')
        
        @self.app.route('/api/auth/login', methods=['POST'])
        def api_auth_login():
            """
            Authenticate with PIN.
            
            Expects:
                JSON: {"pin": "1234"}
            
            Returns:
                JSON: {"success": true/false, "error": "...", "session_expires": "..."}
            """
            from src.web.auth import check_pin, create_session
            
            try:
                if not request.is_json:
                    return jsonify({
                        'success': False,
                        'error': 'Request must be JSON'
                    }), 400
                
                data = request.get_json()
                pin = data.get('pin', '')
                
                if not pin:
                    return jsonify({
                        'success': False,
                        'error': 'PIN is required'
                    }), 400
                
                # Check PIN
                if check_pin(self.app, pin):
                    create_session()
                    
                    # Calculate session expiration
                    expires_at = datetime.now() + timedelta(hours=24)
                    
                    return jsonify({
                        'success': True,
                        'session_expires': expires_at.isoformat()
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid PIN'
                    }), 401
            
            except Exception as e:
                logger.error(f"Login failed: {e}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': 'Login failed'
                }), 500
        
        @self.app.route('/api/mat/status', methods=['GET'])
        def api_mat_status():
            """
            Get current mat status for all groups.
            
            Returns:
                JSON: Status for all device groups
            """
            from src.web.auth import require_auth
            
            @require_auth
            def get_mat_status():
                try:
                    if not self.scheduler or not self.scheduler.device_manager:
                        return jsonify({
                            'success': False,
                            'error': 'Scheduler or device manager not available'
                        }), 503
                    
                    config = self.config_manager.get_config(include_secrets=False)
                    groups = config.get('devices', {}).get('groups', {})
                    
                    result = {}
                    
                    for group_name, group_config in groups.items():
                        # Query actual device state from hardware
                        is_on = False
                        device_error = None
                        
                        try:
                            is_on = self.scheduler.run_coro_in_loop(
                                self.scheduler.device_manager.get_group_actual_state(
                                    group_name, timeout_seconds=10
                                )
                            )
                        except TimeoutError as e:
                            device_error = "Devices are slow to respond"
                            logger.warning(f"Timeout querying state for group '{group_name}': {e}")
                        except Exception as e:
                            device_error = "Cannot get device status"
                            logger.error(f"Failed to query state for group '{group_name}': {e}")
                        
                        # Check manual override status
                        # Call is_active() first to ensure expired overrides are auto-cleared
                        if self.manual_override.is_active(group_name):
                            override = self.manual_override.get_status(group_name)
                        else:
                            override = None
                        
                        # Check if group has schedule
                        has_schedule = self._group_has_schedule(group_name)
                        
                        # Get temperature (optional, from weather service)
                        temperature = None
                        try:
                            if self.scheduler.weather:
                                conditions = self.scheduler.run_coro_in_loop(
                                    self.scheduler.weather.get_current_conditions()
                                )
                                if conditions:
                                    temp_f, precip_mm = conditions
                                    # Convert to Celsius
                                    temperature = round((temp_f - 32) * 5/9, 1)
                        except Exception as e:
                            logger.debug(f"Failed to get temperature: {e}")
                        
                        # Determine mode
                        if override:
                            mode = 'manual'
                        elif has_schedule:
                            mode = 'auto'
                        else:
                            mode = 'manual_only'  # No schedule, manual control only
                        
                        # Build group status
                        group_status = {
                            'is_on': is_on,
                            'mode': mode,
                            'has_schedule': has_schedule,
                            'temperature': temperature,
                            'last_updated': datetime.now().isoformat()
                        }
                        
                        if device_error:
                            group_status['error'] = device_error
                        
                        if override:
                            group_status['override_expires_at'] = override.get('expires_at')
                            
                            # Calculate time remaining in human-readable format
                            try:
                                from zoneinfo import ZoneInfo
                                expires_at = datetime.fromisoformat(override.get('expires_at'))
                                now = datetime.now(ZoneInfo(config.get('location', {}).get('timezone', 'America/New_York')))
                                diff = expires_at - now
                                
                                if diff.total_seconds() > 0:
                                    hours = int(diff.total_seconds() // 3600)
                                    minutes = int((diff.total_seconds() % 3600) // 60)
                                    seconds = int(diff.total_seconds() % 60)
                                    
                                    if hours > 0:
                                        group_status['time_remaining'] = f"in {hours}h {minutes}m"
                                    elif minutes > 0:
                                        group_status['time_remaining'] = f"in {minutes}m {seconds}s"
                                    else:
                                        group_status['time_remaining'] = f"in {seconds}s"
                            except Exception as e:
                                logger.debug(f"Failed to calculate time remaining: {e}")
                        
                        # TODO: Add next scheduled event time
                        group_status['next_scheduled_event'] = None
                        
                        result[group_name] = group_status
                    
                    return jsonify({
                        'success': True,
                        'groups': result
                    })
                
                except Exception as e:
                    logger.error(f"Failed to get mat status: {e}", exc_info=True)
                    return jsonify({
                        'success': False,
                        'error': 'Failed to get status',
                        'details': str(e)
                    }), 500
            
            return get_mat_status()
        
        @self.app.route('/api/mat/control', methods=['POST'])
        def api_mat_control():
            """
            Control a specific device group.
            
            Expects:
                JSON: {"group": "group_name", "action": "on" or "off"}
            
            Returns:
                JSON: Control operation result
            """
            from src.web.auth import require_auth
            
            @require_auth
            def control_mat():
                try:
                    if not request.is_json:
                        return jsonify({
                            'success': False,
                            'error': 'Request must be JSON'
                        }), 400
                    
                    data = request.get_json()
                    group_name = data.get('group')
                    action = data.get('action')
                    
                    if not group_name or not action:
                        return jsonify({
                            'success': False,
                            'error': 'Missing required fields: group and action'
                        }), 400
                    
                    if action not in ['on', 'off']:
                        return jsonify({
                            'success': False,
                            'error': f"Invalid action: {action}. Must be 'on' or 'off'"
                        }), 400
                    
                    if not self.scheduler or not self.scheduler.device_manager:
                        return jsonify({
                            'success': False,
                            'error': 'Scheduler or device manager not available'
                        }), 503
                    
                    config = self.config_manager.get_config(include_secrets=False)
                    groups = config.get('devices', {}).get('groups', {})
                    
                    if group_name not in groups:
                        return jsonify({
                            'success': False,
                            'error': f"Group '{group_name}' not found"
                        }), 404
                    
                    # Get timeout from group-specific config or fall back to global
                    timeout_hours = self._get_manual_override_hours(group_name)
                    
                    # Set manual override
                    self.manual_override.set_override(group_name, action, timeout_hours)
                    
                    # Control the devices
                    group_config = groups[group_name]
                    items = group_config.get('items', [])
                    
                    for item in items:
                        device_name = item.get('name')
                        outlets = item.get('outlets', [])
                        
                        if not outlets:
                            outlets = [None]
                        
                        for outlet_index in outlets:
                            try:
                                self.scheduler.run_coro_in_loop(
                                    self.scheduler.device_manager.control_device_outlet(
                                        group_name, device_name, outlet_index, action
                                    )
                                )
                            except Exception as e:
                                logger.error(f"Failed to control {device_name} outlet {outlet_index}: {e}")
                    
                    # Return updated status
                    return api_mat_status()
                
                except Exception as e:
                    logger.error(f"Failed to control mat: {e}", exc_info=True)
                    return jsonify({
                        'success': False,
                        'error': 'Control action failed',
                        'details': str(e)
                    }), 500
            
            return control_mat()
        
        @self.app.route('/api/mat/reset-auto', methods=['POST'])
        def api_mat_reset_auto():
            """
            Clear manual override for a specific group and apply schedule logic.
            
            Expects:
                JSON: {"group": "group_name"}
            
            Returns:
                JSON: Reset operation result
            """
            from src.web.auth import require_auth
            
            @require_auth
            def reset_auto():
                try:
                    if not request.is_json:
                        return jsonify({
                            'success': False,
                            'error': 'Request must be JSON'
                        }), 400
                    
                    data = request.get_json()
                    group_name = data.get('group')
                    
                    if not group_name:
                        return jsonify({
                            'success': False,
                            'error': 'Missing required field: group'
                        }), 400
                    
                    if not self.scheduler or not self.scheduler.device_manager:
                        return jsonify({
                            'success': False,
                            'error': 'Scheduler or device manager not available'
                        }), 503
                    
                    # Clear manual override
                    self.manual_override.clear_override(group_name)
                    
                    # If group has schedule, check and apply it
                    if self._group_has_schedule(group_name):
                        logger.info(f"Applying schedule logic for group '{group_name}' after clearing override")
                        
                        try:
                            # Check if schedule says devices should be ON or OFF right now
                            should_be_on = self._check_schedule_for_group(group_name)
                            
                            # Apply the schedule state
                            if should_be_on:
                                logger.info(f"Schedule indicates '{group_name}' should be ON, turning on")
                                self.scheduler.run_coro_in_loop(
                                    self.scheduler.device_manager.turn_on_group(group_name)
                                )
                            else:
                                logger.info(f"Schedule indicates '{group_name}' should be OFF, turning off")
                                self.scheduler.run_coro_in_loop(
                                    self.scheduler.device_manager.turn_off_group(group_name)
                                )
                        except TimeoutError as e:
                            logger.error(f"Timeout applying schedule for group '{group_name}': {e}")
                            return jsonify({
                                'success': False,
                                'error': 'Operation timed out. Check device connectivity.'
                            }), 504
                        except Exception as e:
                            logger.error(f"Failed to apply schedule for group '{group_name}': {e}")
                            return jsonify({
                                'success': False,
                                'error': 'Failed to apply schedule',
                                'details': str(e)
                            }), 500
                    
                    # Return updated status
                    return api_mat_status()
                
                except Exception as e:
                    logger.error(f"Failed to reset to auto: {e}", exc_info=True)
                    return jsonify({
                        'success': False,
                        'error': 'Reset action failed',
                        'details': str(e)
                    }), 500
            
            return reset_auto()
        
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
        # Use Flask's render_template for index.html to support Jinja2 templating
        # (e.g., url_for() for static assets)
        if filename == 'index.html':
            return render_template('index.html')
        
        # For other files, serve directly from web directory
        web_dir = Path(__file__).parent / 'web'
        file_path = web_dir / filename
        
        if file_path.exists() and file_path.is_file():
            return send_from_directory(web_dir, filename)
        
        abort(404)
    
    def _group_has_schedule(self, group_name: str) -> bool:
        """Check if a group has any schedule defined.
        
        Args:
            group_name: Name of the device group
            
        Returns:
            True if group has at least one schedule, False otherwise
        """
        if not self.scheduler or not hasattr(self.scheduler, 'group_schedules'):
            return False
        
        schedules = self.scheduler.group_schedules.get(group_name, [])
        return len(schedules) > 0
    
    def _check_schedule_for_group(self, group_name: str) -> bool:
        """Check if schedule says group should be ON right now.
        
        Args:
            group_name: Name of the device group
            
        Returns:
            True if schedule indicates devices should be ON, False otherwise
        """
        if not self.scheduler:
            return False
        
        try:
            # Use the scheduler's method to check if devices should turn on
            should_be_on = self.scheduler.run_coro_in_loop(
                self.scheduler.should_turn_on_group(group_name)
            )
            return should_be_on
        except Exception as e:
            logger.error(f"Failed to check schedule for group '{group_name}': {e}")
            return False
    
    def _get_manual_override_hours(self, group_name: str) -> float:
        """Get manual override duration for a group (defaults to 3.0).
        
        Args:
            group_name: Name of the device group
            
        Returns:
            Override duration in hours (default: 3.0)
        """
        config = self.config_manager.get_config(include_secrets=False)
        
        # Check group-specific override hours first
        groups = config.get('devices', {}).get('groups', {})
        group_config = groups.get(group_name, {})
        group_override_hours = group_config.get('manual_override_hours')
        
        if group_override_hours is not None:
            return float(group_override_hours)
        
        # Fall back to global web config
        web_config = config.get('web', {})
        return float(web_config.get('manual_override_timeout_hours', 3.0))
    
    def _get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status.
        
        Returns:
            Dictionary with system status
        """
        status = {}
        
        # Add setup mode status
        setup_mode, setup_reason = self.config_manager.is_setup_mode()
        status['setup_mode'] = setup_mode
        status['setup_reason'] = setup_reason
        
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
                
                # Add vacation mode status
                status['vacation_mode'] = getattr(self.scheduler, 'vacation_mode', False)
                
                # Try to get weather service status
                if hasattr(self.scheduler, 'weather') and self.scheduler.weather:
                    weather = self.scheduler.weather
                    if hasattr(weather, 'last_successful_fetch'):
                        status['last_weather_fetch'] = weather.last_successful_fetch.isoformat() if weather.last_successful_fetch else None
                    if hasattr(weather, 'state'):
                        # Normalize weather_state to a JSON-serializable primitive
                        # (enums are not JSON-serializable by default)
                        state = weather.state
                        if hasattr(state, 'value'):
                            status['weather_state'] = state.value
                        elif hasattr(state, 'name'):
                            status['weather_state'] = state.name
                        else:
                            status['weather_state'] = str(state)
                    
                    # Add weather offline status
                    if hasattr(weather, 'is_offline'):
                        status['weather_offline'] = weather.is_offline()
                    if hasattr(weather, 'get_cache_age_hours'):
                        cache_age = weather.get_cache_age_hours()
                        if cache_age is not None:
                            status['weather_cache_age_hours'] = round(cache_age, 2)
                
                # Get device expectations for health monitoring
                if hasattr(self.scheduler, 'get_device_expectations'):
                    try:
                        # Use scheduler's event loop if available to avoid python-kasa async issues
                        if hasattr(self.scheduler, 'run_coro_in_loop'):
                            try:
                                expectations = self.scheduler.run_coro_in_loop(
                                    self.scheduler.get_device_expectations()
                                )
                                status['device_expectations'] = expectations
                            except RuntimeError as e:
                                logger.warning(f"Scheduler loop not available: {e}")
                                status['device_expectations'] = []
                        else:
                            # Fallback for backward compatibility
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
    
    def _validate_uploaded_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate uploaded configuration structure and content.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not isinstance(config, dict):
            errors.append("Configuration must be a dictionary")
            return errors
        
        # Validate required top-level sections
        required_sections = ['location', 'devices']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        # Validate location section
        if 'location' in config:
            location = config['location']
            if not isinstance(location, dict):
                errors.append("location section must be a dictionary")
            else:
                # Validate latitude
                if 'latitude' in location:
                    lat = location['latitude']
                    if not isinstance(lat, (int, float)):
                        errors.append(f"location.latitude must be a number, got {type(lat).__name__}")
                    elif lat < -90 or lat > 90:
                        errors.append(f"location.latitude must be between -90 and 90, got {lat}")
                else:
                    errors.append("Missing required field: location.latitude")
                
                # Validate longitude
                if 'longitude' in location:
                    lon = location['longitude']
                    if not isinstance(lon, (int, float)):
                        errors.append(f"location.longitude must be a number, got {type(lon).__name__}")
                    elif lon < -180 or lon > 180:
                        errors.append(f"location.longitude must be between -180 and 180, got {lon}")
                else:
                    errors.append("Missing required field: location.longitude")
                
                # Validate timezone
                if 'timezone' in location:
                    tz = location['timezone']
                    if not isinstance(tz, str):
                        errors.append(f"location.timezone must be a string, got {type(tz).__name__}")
                else:
                    errors.append("Missing required field: location.timezone")
        
        # Validate devices section
        if 'devices' in config:
            devices = config['devices']
            if not isinstance(devices, dict):
                errors.append("devices section must be a dictionary")
            else:
                # Validate credentials
                if 'credentials' in devices:
                    credentials = devices['credentials']
                    if not isinstance(credentials, dict):
                        errors.append("devices.credentials must be a dictionary")
                    else:
                        if 'username' not in credentials:
                            errors.append("Missing required field: devices.credentials.username")
                        elif not isinstance(credentials['username'], str):
                            errors.append("devices.credentials.username must be a string")
                        
                        if 'password' not in credentials:
                            errors.append("Missing required field: devices.credentials.password")
                        elif not isinstance(credentials['password'], str):
                            errors.append("devices.credentials.password must be a string")
                else:
                    errors.append("Missing required section: devices.credentials")
                
                # Validate groups
                if 'groups' in devices:
                    groups = devices['groups']
                    if not isinstance(groups, dict):
                        errors.append("devices.groups must be a dictionary")
                    else:
                        for group_name, group_config in groups.items():
                            if not isinstance(group_config, dict):
                                errors.append(f"devices.groups.{group_name} must be a dictionary")
                                continue
                            
                            # Validate items
                            if 'items' in group_config:
                                items = group_config['items']
                                if not isinstance(items, list):
                                    errors.append(f"devices.groups.{group_name}.items must be a list")
                                else:
                                    for idx, item in enumerate(items):
                                        if not isinstance(item, dict):
                                            errors.append(f"devices.groups.{group_name}.items[{idx}] must be a dictionary")
                                            continue
                                        
                                        # Validate required device fields
                                        if 'name' not in item:
                                            errors.append(f"Missing required field: devices.groups.{group_name}.items[{idx}].name")
                                        elif not isinstance(item['name'], str):
                                            errors.append(f"devices.groups.{group_name}.items[{idx}].name must be a string")
                                        
                                        if 'ip_address' not in item:
                                            errors.append(f"Missing required field: devices.groups.{group_name}.items[{idx}].ip_address")
                                        elif not isinstance(item['ip_address'], str):
                                            errors.append(f"devices.groups.{group_name}.items[{idx}].ip_address must be a string")
                                        else:
                                            # Validate IP address format
                                            ip = item['ip_address']
                                            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
                                            if not re.match(ip_pattern, ip):
                                                errors.append(f"Invalid IP address format for devices.groups.{group_name}.items[{idx}].ip_address: {ip}")
                                            else:
                                                # Validate IP octets are in range and valid decimal format
                                                octets = ip.split('.')
                                                try:
                                                    for octet_str in octets:
                                                        # Check for leading zeros (invalid in IP addresses)
                                                        if len(octet_str) > 1 and octet_str[0] == '0':
                                                            errors.append(f"Invalid IP address for devices.groups.{group_name}.items[{idx}].ip_address: {ip} (leading zeros not allowed)")
                                                            break
                                                        octet = int(octet_str)
                                                        if octet > 255:
                                                            errors.append(f"Invalid IP address for devices.groups.{group_name}.items[{idx}].ip_address: {ip} (octet > 255)")
                                                            break
                                                except ValueError:
                                                    errors.append(f"Invalid IP address for devices.groups.{group_name}.items[{idx}].ip_address: {ip} (non-numeric octet)")

                                        
                                        # Validate outlets field - required for all devices
                                        item_name = item.get('name', f'item {idx}')
                                        if 'outlets' not in item:
                                            errors.append(
                                                f"devices.groups.{group_name}.items[{idx}] ('{item_name}') "
                                                f"missing required 'outlets' field. Add 'outlets: [0]' or 'outlets: [0, 1]'"
                                            )
                                        else:
                                            outlets = item['outlets']
                                            if not isinstance(outlets, list):
                                                errors.append(f"devices.groups.{group_name}.items[{idx}].outlets must be a list")
                                            elif len(outlets) == 0:
                                                errors.append(
                                                    f"devices.groups.{group_name}.items[{idx}].outlets must be a non-empty list. "
                                                    f"Add at least one outlet index (e.g., 'outlets: [0]')"
                                                )
                                            else:
                                                for outlet_idx, outlet in enumerate(outlets):
                                                    if not isinstance(outlet, int):
                                                        errors.append(f"devices.groups.{group_name}.items[{idx}].outlets[{outlet_idx}] must be an integer")
                                                    elif outlet < 0:
                                                        errors.append(f"devices.groups.{group_name}.items[{idx}].outlets[{outlet_idx}] must be non-negative")
                            
                            # Validate automation section if present
                            if 'automation' in group_config:
                                automation = group_config['automation']
                                if not isinstance(automation, dict):
                                    errors.append(f"devices.groups.{group_name}.automation must be a dictionary")
                                else:
                                    # Validate boolean flags (schedule_control removed - use schedules: array)
                                    bool_flags = ['weather_control', 'precipitation_control', 'morning_mode']
                                    for flag in bool_flags:
                                        if flag in automation and not isinstance(automation[flag], bool):
                                            errors.append(f"devices.groups.{group_name}.automation.{flag} must be a boolean")
                            
                            # Note: Legacy schedule: block is still allowed for backwards compatibility
                            # but new configurations should use the schedules: array format
        
        # Validate thresholds section if present
        if 'thresholds' in config:
            thresholds = config['thresholds']
            if not isinstance(thresholds, dict):
                errors.append("thresholds section must be a dictionary")
            else:
                # Validate temperature
                if 'temperature_f' in thresholds:
                    temp = thresholds['temperature_f']
                    if not isinstance(temp, (int, float)):
                        errors.append(f"thresholds.temperature_f must be a number, got {type(temp).__name__}")
                    elif temp < -50 or temp > 150:
                        errors.append(f"thresholds.temperature_f must be between -50 and 150, got {temp}")
                
                # Validate time values
                for time_field in ['lead_time_minutes', 'trailing_time_minutes']:
                    if time_field in thresholds:
                        val = thresholds[time_field]
                        if not isinstance(val, int):
                            errors.append(f"thresholds.{time_field} must be an integer")
                        elif val < 0:
                            errors.append(f"thresholds.{time_field} must be non-negative")
        
        # Validate safety section if present
        if 'safety' in config:
            safety = config['safety']
            if not isinstance(safety, dict):
                errors.append("safety section must be a dictionary")
            else:
                if 'max_runtime_hours' in safety:
                    val = safety['max_runtime_hours']
                    if not isinstance(val, (int, float)):
                        errors.append(f"safety.max_runtime_hours must be a number")
                    elif val < 0:
                        errors.append(f"safety.max_runtime_hours must be non-negative")
        
        # Validate web section if present (for port validation)
        if 'web' in config:
            web = config['web']
            if not isinstance(web, dict):
                errors.append("web section must be a dictionary")
            else:
                # Validate web.port
                if 'port' in web:
                    port = web['port']
                    if not isinstance(port, int):
                        errors.append(f"web.port must be an integer, got {type(port).__name__}")
                    elif port == 0:
                        errors.append("web.port cannot be 0. Use a valid port number (e.g., 4328)")
                    elif port < 1 or port > 65535:
                        errors.append(f"web.port must be between 1 and 65535, got {port}")
                
                # Validate web.bind_host
                if 'bind_host' in web:
                    bind_host = web['bind_host']
                    if not isinstance(bind_host, str):
                        errors.append(f"web.bind_host must be a string, got {type(bind_host).__name__}")
                
                # Validate web.pin
                if 'pin' in web:
                    pin = web['pin']
                    if not isinstance(pin, str):
                        errors.append(f"web.pin must be a string, got {type(pin).__name__}")
        
        # Validate scheduler section if present
        if 'scheduler' in config:
            scheduler = config['scheduler']
            if not isinstance(scheduler, dict):
                errors.append("scheduler section must be a dictionary")
            else:
                # Validate check_interval_minutes
                if 'check_interval_minutes' in scheduler:
                    interval = scheduler['check_interval_minutes']
                    if not isinstance(interval, (int, float)):
                        errors.append(f"scheduler.check_interval_minutes must be a number, got {type(interval).__name__}")
                    elif interval < 1:
                        errors.append(f"scheduler.check_interval_minutes must be >= 1, got {interval}")
        
        return errors
    
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

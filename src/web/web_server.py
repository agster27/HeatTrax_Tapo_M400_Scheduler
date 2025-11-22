"""Flask web server for HeatTrax Scheduler UI and API."""

import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, send_from_directory, render_template, abort
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
        # Static and template folders are relative to this module's location
        module_dir = Path(__file__).parent
        self.app = Flask(__name__, 
                         static_folder=str(module_dir / 'static'),
                         template_folder=str(module_dir / 'templates'))
        
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
                from credential_validator import is_valid_credential
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
            import threading
            def delayed_exit():
                import time
                time.sleep(0.5)  # Give time for response to be sent
                os._exit(0)
            
            threading.Thread(target=delayed_exit, daemon=True).start()
            
            return response
        
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
                
                # Get schedule info
                schedule = group_config.get('schedule', {})
                schedule_valid, on_time, off_time = self.scheduler.validate_schedule(schedule)
                
                schedule_info = {
                    'on_time': on_time,
                    'off_time': off_time,
                    'valid': schedule_valid
                }
                
                return jsonify({
                    'group': group_name,
                    'base': base_automation,
                    'overrides': overrides,
                    'effective': effective,
                    'schedule': schedule_info
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
                    "morning_mode": true/false/null,
                    "schedule_control": true/false/null
                }
            
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
                
                # Valid automation flags
                valid_flags = [
                    'weather_control',
                    'precipitation_control',
                    'morning_mode',
                    'schedule_control'
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
                
                schedule = group_config.get('schedule', {})
                schedule_valid, on_time, off_time = self.scheduler.validate_schedule(schedule)
                
                schedule_info = {
                    'on_time': on_time,
                    'off_time': off_time,
                    'valid': schedule_valid
                }
                
                return jsonify({
                    'group': group_name,
                    'base': base_automation,
                    'overrides': overrides,
                    'effective': effective,
                    'schedule': schedule_info
                })
                
            except Exception as e:
                logger.error(f"Failed to update group automation: {e}", exc_info=True)
                return jsonify({
                    'error': 'Failed to update group automation',
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
                
                for entry in forecast_list:
                    hour_data = {
                        'time': entry.get('timestamp'),
                        'temp_f': entry.get('temperature_f'),
                        'temp_c': round((entry.get('temperature_f', 32) - 32) * 5/9, 1) if entry.get('temperature_f') else None,
                        'precip_prob': None,  # Not stored in current cache format
                        'precip_intensity': entry.get('precipitation_mm'),
                        'precip_type': 'snow' if entry.get('temperature_f', 32) <= 32 and entry.get('precipitation_mm', 0) > 0 else ('rain' if entry.get('precipitation_mm', 0) > 0 else None),
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
                
                return jsonify({
                    'status': 'ok',
                    'last_updated': last_updated,
                    'provider': provider,
                    'timezone': timezone,
                    'cache_age_hours': cache_age_hours,
                    'cache_valid_hours': cache_valid_hours,
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

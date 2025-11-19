"""Thread-safe configuration manager with validation and atomic updates."""

import os
import yaml
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import copy

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Configuration validation error."""
    pass


class ConfigManager:
    """
    Thread-safe configuration manager that handles:
    - Loading config from YAML
    - Auto-generating config from defaults/env when missing
    - Validating config changes
    - Atomic config updates
    - Secret field handling
    """
    
    # Fields that are considered secrets (should not be returned in API responses)
    SECRET_FIELDS = {
        ('devices', 'credentials', 'password'),
        ('weather_api', 'openweathermap', 'api_key'),
        ('notifications', 'email', 'smtp_password'),
        ('notifications', 'webhook', 'url'),  # May contain tokens
        ('web', 'auth', 'password_hash'),
    }
    
    # Default configuration template
    DEFAULT_CONFIG = {
        'location': {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York'
        },
        'devices': {
            'credentials': {
                'username': '',
                'password': ''
            },
            'groups': {}
        },
        'weather_api': {
            'enabled': True,
            'provider': 'open-meteo',
            'openweathermap': {
                'api_key': ''
            },
            'open_meteo': {},
            'resilience': {
                'cache_file': 'state/weather_cache.json',
                'cache_valid_hours': 6.0,
                'forecast_horizon_hours': 12,
                'refresh_interval_minutes': 10,
                'retry_interval_minutes': 5,
                'max_retry_interval_minutes': 60,
                'outage_alert_after_minutes': 30
            }
        },
        'thresholds': {
            'temperature_f': 34,
            'lead_time_minutes': 60,
            'trailing_time_minutes': 60
        },
        'morning_mode': {
            'enabled': True,
            'start_hour': 6,
            'end_hour': 8,
            'temperature_f': 32
        },
        'safety': {
            'max_runtime_hours': 6,
            'cooldown_minutes': 30
        },
        'scheduler': {
            'check_interval_minutes': 10,
            'forecast_hours': 12
        },
        'logging': {
            'level': 'INFO',
            'max_file_size_mb': 10,
            'backup_count': 5
        },
        'health_check': {
            'interval_hours': 24,
            'max_consecutive_failures': 3
        },
        'notifications': {
            'required': False,
            'test_on_startup': False,
            'email': {
                'enabled': False,
                'smtp_host': '',
                'smtp_port': 587,
                'smtp_username': '',
                'smtp_password': '',
                'from_email': '',
                'to_emails': [],
                'use_tls': True
            },
            'webhook': {
                'enabled': False,
                'url': ''
            },
            'forecast': {
                'enabled': False,
                'notify_mode': 'always',
                'temp_change_threshold_f': 5.0,
                'precip_change_threshold_mm': 2.0,
                'state_file': 'state/forecast_notification_state.json'
            }
        },
        'reboot': {
            'pause_seconds': 60
        },
        'health_server': {
            'enabled': True,
            'host': '0.0.0.0',
            'port': 4329
        },
        'web': {
            'enabled': True,
            'bind_host': '127.0.0.1',
            'port': 4328,
            'auth': {
                'enabled': False,
                'username': '',
                'password_hash': ''
            }
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file (defaults to HEATTRAX_CONFIG_PATH or config.yaml)
        """
        self._lock = threading.RLock()
        
        # Resolve config path
        if config_path is None:
            config_path = os.environ.get('HEATTRAX_CONFIG_PATH', '/app/config.yaml')
        
        self.config_path = Path(config_path)
        logger.info(f"Configuration path: {self.config_path}")
        
        # Load or create initial configuration
        self._config, self._env_overridden_paths = self._load_or_create_config()
        self._config_last_modified = datetime.now()
        
        logger.info("ConfigManager initialized successfully")
    
    def _load_or_create_config(self) -> tuple[Dict[str, Any], Dict[str, str]]:
        """
        Load configuration from file or create from defaults.
        
        Returns:
            Tuple of (configuration dictionary, env overridden paths mapping)
        """
        if not self.config_path.exists():
            logger.warning(f"Configuration file not found: {self.config_path}")
            logger.info("Generating config.yaml from defaults and environment variables")
            logger.info("Future changes via web UI will be written to config.yaml and may differ from environment variable values")
            
            # Start with defaults
            config = copy.deepcopy(self.DEFAULT_CONFIG)
            
            # Apply environment variable overrides
            config, env_overridden_paths = self._apply_env_overrides(config)
            
            # Create parent directory if needed
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write initial config
            self._write_config_to_disk(config)
            logger.info(f"Generated initial configuration file: {self.config_path}")
            
            return config, env_overridden_paths
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if config is None or not isinstance(config, dict):
                logger.error(f"Invalid configuration file format: {self.config_path}")
                logger.warning("Falling back to default configuration with environment overrides")
                config = copy.deepcopy(self.DEFAULT_CONFIG)
                config, env_overridden_paths = self._apply_env_overrides(config)
                return config, env_overridden_paths
            
            logger.info(f"Loaded configuration from: {self.config_path}")
            
            # Apply environment variable overrides
            config, env_overridden_paths = self._apply_env_overrides(config)
            
            # Validate loaded config
            self._validate_config(config)
            
            return config, env_overridden_paths
            
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            logger.warning("Falling back to default configuration with environment overrides")
            config = copy.deepcopy(self.DEFAULT_CONFIG)
            config, env_overridden_paths = self._apply_env_overrides(config)
            return config, env_overridden_paths
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            logger.warning("Falling back to default configuration with environment overrides")
            config = copy.deepcopy(self.DEFAULT_CONFIG)
            config, env_overridden_paths = self._apply_env_overrides(config)
            return config, env_overridden_paths
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, str]]:
        """
        Apply environment variable overrides to configuration and track which fields were overridden.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Tuple of (config with overrides applied, dict mapping config paths to env var names)
        """
        # Import the existing mapping from config_loader
        from config_loader import ENV_VAR_MAPPING, get_env_var
        
        # Track which config paths are overridden by which env vars
        env_overridden_paths = {}
        
        for env_var, mapping_tuple in ENV_VAR_MAPPING.items():
            value = get_env_var(env_var, mapping_tuple[-1])
            
            if value is not None:
                sections = mapping_tuple[:-1]
                current = config
                
                # Navigate/create nested structure
                for section in sections[:-1]:
                    if section not in current:
                        current[section] = {}
                    current = current[section]
                
                # Set the final value
                final_key = sections[-1]
                current[final_key] = value
                
                path = '.'.join(sections)
                env_overridden_paths[path] = env_var
                logger.debug(f"Environment override: {env_var} -> {path}")
        
        # Apply web-specific environment overrides
        if os.environ.get('HEATTRAX_WEB_ENABLED'):
            web_enabled = os.environ['HEATTRAX_WEB_ENABLED'].lower() in ('true', '1', 'yes', 'on')
            config.setdefault('web', {})['enabled'] = web_enabled
            env_overridden_paths['web.enabled'] = 'HEATTRAX_WEB_ENABLED'
            logger.info(f"Environment override: HEATTRAX_WEB_ENABLED -> web.enabled = {web_enabled}")
        
        if os.environ.get('HEATTRAX_WEB_PASSWORD'):
            # For future auth support - hash the password
            import hashlib
            password = os.environ['HEATTRAX_WEB_PASSWORD']
            # Simple hash for now (should use bcrypt in production)
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            config.setdefault('web', {}).setdefault('auth', {})['password_hash'] = password_hash
            env_overridden_paths['web.auth.password_hash'] = 'HEATTRAX_WEB_PASSWORD'
            logger.info("Environment override: HEATTRAX_WEB_PASSWORD -> web.auth.password_hash (hashed)")
        
        return config, env_overridden_paths
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """
        Validate configuration.
        
        Args:
            config: Configuration to validate
            
        Raises:
            ConfigValidationError: If validation fails
        """
        # Required sections
        required_sections = ['location', 'devices', 'thresholds', 'safety', 'scheduler']
        for section in required_sections:
            if section not in config:
                raise ConfigValidationError(f"Missing required section: {section}")
        
        # Validate location
        location = config['location']
        if not isinstance(location, dict):
            raise ConfigValidationError("location must be a dictionary")
        
        if 'latitude' not in location or 'longitude' not in location:
            raise ConfigValidationError("location must include latitude and longitude")
        
        try:
            lat = float(location['latitude'])
            lon = float(location['longitude'])
            if not (-90 <= lat <= 90):
                raise ConfigValidationError(f"Invalid latitude: {lat} (must be -90 to 90)")
            if not (-180 <= lon <= 180):
                raise ConfigValidationError(f"Invalid longitude: {lon} (must be -180 to 180)")
        except (ValueError, TypeError) as e:
            raise ConfigValidationError(f"Invalid latitude/longitude: {e}")
        
        # Validate devices
        devices = config['devices']
        if not isinstance(devices, dict):
            raise ConfigValidationError("devices must be a dictionary")
        
        if 'credentials' not in devices:
            raise ConfigValidationError("devices must include credentials section")
        
        credentials = devices['credentials']
        for field in ['username', 'password']:
            if field not in credentials:
                raise ConfigValidationError(f"devices.credentials must include {field}")
        
        # Validate device groups
        if 'groups' in devices:
            groups = devices['groups']
            if not isinstance(groups, dict):
                raise ConfigValidationError("devices.groups must be a dictionary")
            
            for group_name, group_config in groups.items():
                if not isinstance(group_config, dict):
                    raise ConfigValidationError(f"devices.groups.{group_name} must be a dictionary")
                
                # Validate enabled field if present
                if 'enabled' in group_config:
                    if not isinstance(group_config['enabled'], bool):
                        raise ConfigValidationError(f"devices.groups.{group_name}.enabled must be a boolean")
                
                # Validate items
                if 'items' in group_config:
                    items = group_config['items']
                    if not isinstance(items, list):
                        raise ConfigValidationError(f"devices.groups.{group_name}.items must be a list")
                    
                    for idx, item in enumerate(items):
                        if not isinstance(item, dict):
                            raise ConfigValidationError(f"devices.groups.{group_name}.items[{idx}] must be a dictionary")
                        
                        # Validate required fields
                        if 'name' not in item or not item['name']:
                            raise ConfigValidationError(f"devices.groups.{group_name}.items[{idx}] must include 'name' field")
                        
                        if 'ip_address' not in item or not item['ip_address']:
                            raise ConfigValidationError(f"devices.groups.{group_name}.items[{idx}] must include 'ip_address' field")
                        
                        # Validate outlets if present
                        if 'outlets' in item:
                            outlets = item['outlets']
                            if not isinstance(outlets, list):
                                raise ConfigValidationError(f"devices.groups.{group_name}.items[{idx}].outlets must be a list")
                            
                            for outlet_idx, outlet in enumerate(outlets):
                                if not isinstance(outlet, int) or outlet < 0:
                                    raise ConfigValidationError(
                                        f"devices.groups.{group_name}.items[{idx}].outlets[{outlet_idx}] must be a non-negative integer"
                                    )
        
        # Validate thresholds
        thresholds = config['thresholds']
        if not isinstance(thresholds, dict):
            raise ConfigValidationError("thresholds must be a dictionary")
        
        for field in ['temperature_f', 'lead_time_minutes', 'trailing_time_minutes']:
            if field not in thresholds:
                raise ConfigValidationError(f"thresholds must include {field}")
            try:
                value = float(thresholds[field])
                if field in ['lead_time_minutes', 'trailing_time_minutes'] and value < 0:
                    raise ConfigValidationError(f"{field} must be non-negative")
            except (ValueError, TypeError):
                raise ConfigValidationError(f"Invalid {field} value")
        
        # Validate safety
        safety = config['safety']
        if not isinstance(safety, dict):
            raise ConfigValidationError("safety must be a dictionary")
        
        for field in ['max_runtime_hours', 'cooldown_minutes']:
            if field not in safety:
                raise ConfigValidationError(f"safety must include {field}")
            try:
                value = float(safety[field])
                if value <= 0:
                    raise ConfigValidationError(f"{field} must be positive")
            except (ValueError, TypeError):
                raise ConfigValidationError(f"Invalid {field} value")
        
        # Validate notifications if present
        if 'notifications' in config:
            notifications = config['notifications']
            if not isinstance(notifications, dict):
                raise ConfigValidationError("notifications must be a dictionary")
            
            # Validate email notifications if enabled
            if 'email' in notifications:
                email = notifications['email']
                if not isinstance(email, dict):
                    raise ConfigValidationError("notifications.email must be a dictionary")
                
                # If email is enabled, validate required fields
                if email.get('enabled', False):
                    required_email_fields = ['smtp_host', 'smtp_port', 'smtp_username', 
                                            'smtp_password', 'from_email', 'to_emails']
                    
                    for field in required_email_fields:
                        if field not in email:
                            raise ConfigValidationError(
                                f"notifications.email.{field} is required when email notifications are enabled"
                            )
                        
                        # Validate non-empty values
                        value = email[field]
                        if field == 'to_emails':
                            if not isinstance(value, list) or len(value) == 0:
                                raise ConfigValidationError(
                                    "notifications.email.to_emails must be a non-empty list when email is enabled"
                                )
                        elif not value:
                            raise ConfigValidationError(
                                f"notifications.email.{field} cannot be empty when email notifications are enabled"
                            )
                    
                    # Validate smtp_port is an integer
                    try:
                        port = int(email['smtp_port'])
                        if port < 1 or port > 65535:
                            raise ConfigValidationError(
                                f"notifications.email.smtp_port must be between 1 and 65535, got {port}"
                            )
                    except (ValueError, TypeError):
                        raise ConfigValidationError(
                            f"notifications.email.smtp_port must be an integer"
                        )
                    
                    # Validate use_tls is a boolean if present
                    if 'use_tls' in email and not isinstance(email['use_tls'], bool):
                        raise ConfigValidationError("notifications.email.use_tls must be a boolean")
            
            # Validate webhook notifications if enabled
            if 'webhook' in notifications:
                webhook = notifications['webhook']
                if not isinstance(webhook, dict):
                    raise ConfigValidationError("notifications.webhook must be a dictionary")
                
                # If webhook is enabled, validate URL
                if webhook.get('enabled', False):
                    if 'url' not in webhook or not webhook['url']:
                        raise ConfigValidationError(
                            "notifications.webhook.url is required when webhook notifications are enabled"
                        )
    
    def _write_config_to_disk(self, config: Dict[str, Any]) -> None:
        """
        Write configuration to disk atomically.
        
        Args:
            config: Configuration to write
        """
        # Write to temporary file first
        temp_path = self.config_path.with_suffix('.tmp')
        
        try:
            with open(temp_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            # Atomic rename
            temp_path.replace(self.config_path)
            logger.info(f"Configuration written to: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to write configuration: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def get_config(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Get current configuration.
        
        Args:
            include_secrets: Whether to include secret values (default: False)
            
        Returns:
            Configuration dictionary (deep copy)
        """
        with self._lock:
            config = copy.deepcopy(self._config)
            
            if not include_secrets:
                config = self._filter_secrets(config)
            
            return config
    
    def _filter_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter out secret values from configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configuration with secrets masked
        """
        config = copy.deepcopy(config)
        
        for secret_path in self.SECRET_FIELDS:
            current = config
            for key in secret_path[:-1]:
                if key not in current or not isinstance(current[key], dict):
                    break
                current = current[key]
            else:
                final_key = secret_path[-1]
                if final_key in current:
                    # Mask secrets, even if empty (to be consistent)
                    current[final_key] = '********'
        
        return config
    
    def update_config(self, new_config: Dict[str, Any], preserve_secrets: bool = True) -> Dict[str, str]:
        """
        Update configuration with validation and atomic write.
        
        Args:
            new_config: New configuration dictionary
            preserve_secrets: If True, preserve existing secret values when new value is empty/masked
            
        Returns:
            Dictionary with keys: 'status' ('ok' or 'error'), 'message', 'restart_required'
        """
        with self._lock:
            try:
                # Log notification settings for debugging
                logger.debug("update_config received notifications: %s", new_config.get("notifications"))
                
                # Deep copy to avoid modifying input
                config_to_validate = copy.deepcopy(new_config)
                
                # If preserving secrets, merge with existing values
                if preserve_secrets:
                    config_to_validate = self._merge_secrets(config_to_validate, self._config)
                
                # Validate new configuration
                self._validate_config(config_to_validate)
                
                # Check if restart is required (structural changes)
                restart_required = self._requires_restart(self._config, config_to_validate)
                
                # Write to disk
                self._write_config_to_disk(config_to_validate)
                
                # Update in-memory config
                self._config = config_to_validate
                self._config_last_modified = datetime.now()
                
                logger.info("Configuration updated successfully")
                
                return {
                    'status': 'ok',
                    'message': 'Configuration updated successfully',
                    'restart_required': str(restart_required).lower()
                }
                
            except ConfigValidationError as e:
                logger.error(f"Configuration validation failed: {e}")
                return {
                    'status': 'error',
                    'message': f"Validation error: {str(e)}",
                    'restart_required': 'false'
                }
            except Exception as e:
                logger.error(f"Failed to update configuration: {e}", exc_info=True)
                return {
                    'status': 'error',
                    'message': f"Failed to update configuration: {str(e)}",
                    'restart_required': 'false'
                }
    
    def _merge_secrets(self, new_config: Dict[str, Any], old_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge secret values from old config when new values are empty or masked.
        
        Args:
            new_config: New configuration with potentially empty/masked secrets
            old_config: Current configuration with actual secret values
            
        Returns:
            Configuration with secrets properly merged
        """
        result = copy.deepcopy(new_config)
        
        for secret_path in self.SECRET_FIELDS:
            # Get old value
            old_current = old_config
            for key in secret_path:
                if key not in old_current or not isinstance(old_current.get(key), (dict, str)):
                    break
                old_current = old_current[key]
            else:
                old_value = old_current if isinstance(old_current, str) else None
                
                # Get new value
                new_current = result
                for key in secret_path[:-1]:
                    if key not in new_current:
                        new_current[key] = {}
                    new_current = new_current[key]
                
                final_key = secret_path[-1]
                new_value = new_current.get(final_key, '')
                
                # If new value is empty or masked, use old value
                if not new_value or new_value == '********':
                    if old_value:
                        new_current[final_key] = old_value
        
        return result
    
    def _requires_restart(self, old_config: Dict[str, Any], new_config: Dict[str, Any]) -> bool:
        """
        Determine if configuration change requires restart.
        
        Args:
            old_config: Current configuration
            new_config: New configuration
            
        Returns:
            True if restart is recommended
        """
        # Changes that require restart
        restart_keys = [
            ('devices', 'groups'),  # Device group structure changes
            ('weather_api', 'provider'),  # Weather provider change
            ('web', 'port'),  # Web server port change
            ('health_server', 'port'),  # Health server port change
        ]
        
        for key_path in restart_keys:
            old_val = old_config
            new_val = new_config
            
            for key in key_path:
                old_val = old_val.get(key) if isinstance(old_val, dict) else None
                new_val = new_val.get(key) if isinstance(new_val, dict) else None
            
            if old_val != new_val:
                logger.info(f"Configuration change requires restart: {'.'.join(key_path)}")
                return True
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get configuration status metadata.
        
        Returns:
            Dictionary with config metadata
        """
        with self._lock:
            return {
                'config_path': str(self.config_path),
                'config_last_modified': self._config_last_modified.isoformat(),
                'config_exists': self.config_path.exists()
            }
    
    def get_env_overridden_paths(self) -> Dict[str, str]:
        """
        Get mapping of config paths to environment variable names that override them.
        
        Returns:
            Dictionary mapping config paths (e.g., 'location.latitude') to env var names (e.g., 'HEATTRAX_LATITUDE')
        """
        with self._lock:
            return copy.deepcopy(self._env_overridden_paths)

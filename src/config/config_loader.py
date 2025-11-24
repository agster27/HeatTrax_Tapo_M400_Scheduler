"""Configuration loader and validator for HeatTrax Scheduler."""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration error exception."""
    pass


# Environment variable to config key mapping
# All environment variables must use the HEATTRAX_ prefix
ENV_VAR_MAPPING = {
    # Location settings
    'HEATTRAX_LATITUDE': ('location', 'latitude', float),
    'HEATTRAX_LONGITUDE': ('location', 'longitude', float),
    'HEATTRAX_TIMEZONE': ('location', 'timezone', str),
    
    # Weather API settings
    'HEATTRAX_WEATHER_ENABLED': ('weather_api', 'enabled', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    'HEATTRAX_WEATHER_PROVIDER': ('weather_api', 'provider', str),
    'HEATTRAX_OPENWEATHERMAP_API_KEY': ('weather_api', 'openweathermap', 'api_key', str),
    
    # Weather resilience settings
    'HEATTRAX_WEATHER_CACHE_FILE': ('weather_api', 'resilience', 'cache_file', str),
    'HEATTRAX_WEATHER_CACHE_VALID_HOURS': ('weather_api', 'resilience', 'cache_valid_hours', float),
    'HEATTRAX_WEATHER_FORECAST_HORIZON_HOURS': ('weather_api', 'resilience', 'forecast_horizon_hours', int),
    'HEATTRAX_WEATHER_REFRESH_INTERVAL_MINUTES': ('weather_api', 'resilience', 'refresh_interval_minutes', int),
    'HEATTRAX_WEATHER_RETRY_INTERVAL_MINUTES': ('weather_api', 'resilience', 'retry_interval_minutes', int),
    'HEATTRAX_WEATHER_MAX_RETRY_INTERVAL_MINUTES': ('weather_api', 'resilience', 'max_retry_interval_minutes', int),
    'HEATTRAX_WEATHER_OUTAGE_ALERT_AFTER_MINUTES': ('weather_api', 'resilience', 'outage_alert_after_minutes', int),
    
    # Device settings (multi-device mode)
    'HEATTRAX_TAPO_USERNAME': ('devices', 'credentials', 'username', str),
    'HEATTRAX_TAPO_PASSWORD': ('devices', 'credentials', 'password', str),
    
    # Threshold settings
    'HEATTRAX_THRESHOLD_TEMP_F': ('thresholds', 'temperature_f', float),
    'HEATTRAX_LEAD_TIME_MINUTES': ('thresholds', 'lead_time_minutes', int),
    'HEATTRAX_TRAILING_TIME_MINUTES': ('thresholds', 'trailing_time_minutes', int),
    
    # Scheduler settings
    'HEATTRAX_CHECK_INTERVAL_MINUTES': ('scheduler', 'check_interval_minutes', int),
    'HEATTRAX_FORECAST_HOURS': ('scheduler', 'forecast_hours', int),
    
    # Safety settings
    'HEATTRAX_MAX_RUNTIME_HOURS': ('safety', 'max_runtime_hours', float),
    'HEATTRAX_COOLDOWN_MINUTES': ('safety', 'cooldown_minutes', int),
    
    # Vacation mode
    'HEATTRAX_VACATION_MODE': ('vacation_mode', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    
    # Logging settings
    'HEATTRAX_LOG_LEVEL': ('logging', 'level', str),
    
    # Health check settings
    'HEATTRAX_HEALTH_CHECK_INTERVAL_HOURS': ('health_check', 'interval_hours', float),
    'HEATTRAX_HEALTH_CHECK_MAX_FAILURES': ('health_check', 'max_consecutive_failures', int),
    
    # Notification settings - Global
    'HEATTRAX_NOTIFICATIONS_REQUIRED': ('notifications', 'required', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    'HEATTRAX_NOTIFICATIONS_TEST_ON_STARTUP': ('notifications', 'test_on_startup', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    
    # Notification settings - Email
    'HEATTRAX_NOTIFICATION_EMAIL_ENABLED': ('notifications', 'email', 'enabled', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    'HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST': ('notifications', 'email', 'smtp_host', str),
    'HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT': ('notifications', 'email', 'smtp_port', int),
    'HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME': ('notifications', 'email', 'smtp_username', str),
    'HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD': ('notifications', 'email', 'smtp_password', str),
    'HEATTRAX_NOTIFICATION_EMAIL_FROM': ('notifications', 'email', 'from_email', str),
    'HEATTRAX_NOTIFICATION_EMAIL_TO': ('notifications', 'email', 'to_emails', lambda x: [e.strip() for e in x.split(',')]),
    'HEATTRAX_NOTIFICATION_EMAIL_USE_TLS': ('notifications', 'email', 'use_tls', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    
    # Notification settings - Webhook
    'HEATTRAX_NOTIFICATION_WEBHOOK_ENABLED': ('notifications', 'webhook', 'enabled', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    'HEATTRAX_NOTIFICATION_WEBHOOK_URL': ('notifications', 'webhook', 'url', str),
    
    # Notification settings - Forecast Summaries
    'HEATTRAX_NOTIFICATION_FORECAST_ENABLED': ('notifications', 'forecast', 'enabled', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    'HEATTRAX_NOTIFICATION_FORECAST_NOTIFY_MODE': ('notifications', 'forecast', 'notify_mode', str),
    
    # Reboot settings
    'HEATTRAX_REBOOT_PAUSE_SECONDS': ('reboot', 'pause_seconds', int),
    
    # Health server settings
    'HEATTRAX_HEALTH_SERVER_ENABLED': ('health_server', 'enabled', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    'HEATTRAX_HEALTH_SERVER_HOST': ('health_server', 'host', str),
    'HEATTRAX_HEALTH_SERVER_PORT': ('health_server', 'port', int),
    
    # Web UI settings
    'HEATTRAX_WEB_HOST': ('web', 'bind_host', str),
    'HEATTRAX_WEB_PORT': ('web', 'port', int),
}


def get_env_var(env_var: str, convert_type: type) -> Optional[Any]:
    """
    Get environment variable and convert to specified type.
    
    Args:
        env_var: Environment variable name
        convert_type: Type conversion function (int, float, str, or callable)
        
    Returns:
        Converted value or None if not set
    """
    value = os.environ.get(env_var)
    if value is None:
        return None
    
    try:
        if callable(convert_type):
            return convert_type(value)
        return value
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to convert environment variable {env_var}={value}: {e}")
        return None


def apply_env_overrides(config: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, str]]:
    """
    Apply environment variable overrides to configuration and track which fields were overridden.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Tuple of (config with overrides applied, dict mapping config paths to env var names)
    """
    logger.debug("Checking for environment variable overrides...")
    
    # Track which config paths are overridden by which env vars
    env_overridden_paths = {}
    
    for env_var, mapping_tuple in ENV_VAR_MAPPING.items():
        value = get_env_var(env_var, mapping_tuple[-1])  # Last element is the convert function
        
        if value is not None:
            # Handle nested configuration (e.g., notifications.email.enabled)
            sections = mapping_tuple[:-1]  # All but the last element are path components
            
            # Navigate/create nested structure
            current = config
            for i, section in enumerate(sections[:-1]):
                if section not in current:
                    current[section] = {}
                current = current[section]
            
            # Set the final value
            final_key = sections[-1]
            current[final_key] = value
            
            # Build path string for logging and tracking
            path = '.'.join(sections)
            env_overridden_paths[path] = env_var
            logger.info(f"Environment variable override: {env_var} -> {path} = {value}")
    
    return config, env_overridden_paths


class Config:
    """Configuration manager for the application."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize configuration from YAML file with environment variable overrides.
        
        Args:
            config_path: Path to the configuration file (defaults to HEATTRAX_CONFIG_PATH env var or "config.yaml")
        """
        # Check for HEATTRAX_CONFIG_PATH environment variable if no path provided
        if config_path is None:
            config_path = os.environ.get('HEATTRAX_CONFIG_PATH', 'config.yaml')
        
        logger.info(f"Loading configuration from: {config_path}")
        self.config_path = Path(config_path)
        self._config = self._load_config()
        
        # Apply environment variable overrides and track which fields were overridden
        self._config, self._env_overridden_paths = apply_env_overrides(self._config)
        
        self._validate_config()
        logger.info("Configuration loaded and validated successfully")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file or create minimal config if file doesn't exist but env vars are set."""
        logger.debug(f"Checking if configuration file exists: {self.config_path}")
        
        if not self.config_path.exists():
            # Use print() here since logging may not be initialized yet when Config() is instantiated
            # This provides clear, formatted messaging before the logging system is configured
            print(f"INFO: Configuration file not found: {self.config_path}")
            print("INFO: Attempting to load configuration from environment variables...")
            print("INFO: This is normal when using environment-based configuration (Docker/Portainer deployments)")
            
            # Also log for when logging is configured (these may not appear until logging is set up)
            logger.warning(f"Configuration file not found: {self.config_path}")
            logger.info("Will attempt to use environment variables for configuration")
            
            # Create minimal config structure that will be populated by env vars
            config = {
                'vacation_mode': False,
                'location': {},
                'devices': {'credentials': {}, 'groups': {}},
                'weather_api': {},
                'scheduler': {},
                'safety': {},
                'logging': {},
                'health_check': {},
                'notifications': {'email': {}, 'webhook': {}},
                'reboot': {},
                'health_server': {},
                'web': {}
            }
            return config
        
        try:
            logger.debug(f"Reading configuration file: {self.config_path}")
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if config is None:
                logger.warning("Configuration file is empty, using empty config structure")
                config = {
                    'vacation_mode': False,
                    'location': {},
                    'devices': {'credentials': {}, 'groups': {}},
                    'weather_api': {},
                    'scheduler': {},
                    'safety': {},
                    'logging': {},
                    'health_check': {},
                    'notifications': {'email': {}, 'webhook': {}},
                    'reboot': {},
                    'health_server': {},
                    'web': {}
                }
            
            if not isinstance(config, dict):
                logger.error(f"Configuration must be a dictionary, got: {type(config)}")
                raise ConfigError(f"Invalid configuration format: expected dictionary, got {type(config)}")
            
            logger.info(f"Successfully parsed configuration with {len(config)} top-level sections")
            logger.debug(f"Configuration sections: {list(config.keys())}")
            return config
            
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration file: {e}")
            logger.exception("Full traceback:")
            raise ConfigError(f"Error parsing configuration file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise ConfigError(f"Error loading configuration: {e}")
    
    def _validate_config(self):
        """Validate required configuration fields."""
        logger.info("Validating configuration...")
        
        # Required sections for multi-device configuration
        required_sections = ['location', 'devices', 'safety', 'scheduler']
        
        logger.debug(f"Checking for required sections: {required_sections}")
        for section in required_sections:
            if section not in self._config:
                logger.error(f"Missing required configuration section: {section}")
                logger.error(f"Available sections: {list(self._config.keys())}")
                raise ConfigError(f"Missing required configuration section: {section}")
        
        # Validate location
        logger.debug("Validating location configuration")
        location = self._config['location']
        
        if not isinstance(location, dict):
            logger.error(f"Location must be a dictionary, got: {type(location)}")
            raise ConfigError(f"Location configuration must be a dictionary")
        
        if 'latitude' not in location or 'longitude' not in location:
            logger.error(f"Location missing required fields. Has: {list(location.keys())}")
            raise ConfigError("Location must include latitude and longitude")
        
        # Validate latitude/longitude values
        try:
            lat = float(location['latitude'])
            lon = float(location['longitude'])
            if not (-90 <= lat <= 90):
                logger.error(f"Invalid latitude value: {lat} (must be between -90 and 90)")
                raise ConfigError(f"Invalid latitude: {lat} (must be between -90 and 90)")
            if not (-180 <= lon <= 180):
                logger.error(f"Invalid longitude value: {lon} (must be between -180 and 180)")
                raise ConfigError(f"Invalid longitude: {lon} (must be between -180 and 180)")
            logger.debug(f"Location validated: lat={lat}, lon={lon}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid latitude/longitude values: {e}")
            raise ConfigError(f"Latitude and longitude must be valid numbers: {e}")
        
        # Validate devices section
        logger.debug("Validating devices configuration")
        devices = self._config['devices']
        
        if not isinstance(devices, dict):
            logger.error(f"Devices must be a dictionary, got: {type(devices)}")
            raise ConfigError(f"Devices configuration must be a dictionary")
        
        # Validate credentials section exists (but allow empty/placeholder values)
        if 'credentials' not in devices:
            logger.warning("Devices configuration missing 'credentials' section - creating empty credentials")
            devices['credentials'] = {'username': '', 'password': ''}
        
        credentials = devices['credentials']
        
        # Ensure username and password keys exist (but allow empty values)
        if 'username' not in credentials:
            logger.warning("Devices credentials missing 'username' field - using empty string")
            credentials['username'] = ''
        if 'password' not in credentials:
            logger.warning("Devices credentials missing 'password' field - using empty string")
            credentials['password'] = ''
        
        # Log credential state (will be checked for setup mode later)
        from .credential_validator import log_credential_state, is_valid_credential
        log_credential_state(credentials.get('username'), credentials.get('password'), source="config")
        
        is_valid, reason = is_valid_credential(credentials.get('username'), credentials.get('password'))
        if not is_valid:
            logger.warning(f"Tapo credentials validation: {reason}")
            logger.warning("Device control will be DISABLED until valid credentials are provided")
        else:
            logger.info(f"Tapo credentials validation: {reason}")
        
        # Validate groups
        if 'groups' not in devices or not devices['groups']:
            logger.warning("No device groups configured - this is unusual but allowed")
        else:
            groups = devices['groups']
            if not isinstance(groups, dict):
                logger.error(f"Device groups must be a dictionary, got: {type(groups)}")
                raise ConfigError(f"Device groups must be a dictionary")
            
            logger.debug(f"Validating {len(groups)} device groups")
            for group_name, group_config in groups.items():
                if not isinstance(group_config, dict):
                    logger.error(f"Group '{group_name}' must be a dictionary")
                    raise ConfigError(f"Group '{group_name}' configuration must be a dictionary")
                
                if 'items' in group_config:
                    items = group_config['items']
                    if not isinstance(items, list):
                        logger.error(f"Group '{group_name}' items must be a list")
                        raise ConfigError(f"Group '{group_name}' items must be a list")
                    
                    for i, item in enumerate(items):
                        if not isinstance(item, dict):
                            logger.error(f"Group '{group_name}' item {i} must be a dictionary")
                            raise ConfigError(f"Group '{group_name}' item {i} must be a dictionary")
                        if 'ip_address' not in item or not item['ip_address']:
                            logger.error(f"Device in group '{group_name}' item {i} missing or empty ip_address")
                            raise ConfigError(f"All devices must have non-empty 'ip_address'")
        
        # Validate thresholds (optional, deprecated but supported for backward compatibility)
        if 'thresholds' in self._config:
            logger.debug("Validating thresholds configuration (deprecated)")
            thresholds = self._config['thresholds']
            
            if not isinstance(thresholds, dict):
                logger.error(f"Thresholds must be a dictionary, got: {type(thresholds)}")
                raise ConfigError(f"Thresholds configuration must be a dictionary")
            
            threshold_fields = ['temperature_f', 'lead_time_minutes', 'trailing_time_minutes']
            for field in threshold_fields:
                if field not in thresholds:
                    logger.warning(f"Thresholds configuration missing field: {field} (field is deprecated)")
                    continue
                
                # Validate numeric values
                try:
                    value = float(thresholds[field])
                    if field in ['lead_time_minutes', 'trailing_time_minutes'] and value < 0:
                        logger.error(f"Invalid {field}: {value} (must be non-negative)")
                        raise ConfigError(f"{field} must be non-negative, got: {value}")
                    logger.debug(f"Threshold {field}={value}")
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid value for {field}: {thresholds[field]}")
                    raise ConfigError(f"{field} must be a valid number: {e}")
        else:
            logger.debug("Thresholds section not present (using new schedule-based system)")
        
        # Validate safety
        logger.debug("Validating safety configuration")
        safety = self._config['safety']
        
        if not isinstance(safety, dict):
            logger.error(f"Safety must be a dictionary, got: {type(safety)}")
            raise ConfigError(f"Safety configuration must be a dictionary")
        
        safety_fields = ['max_runtime_hours', 'cooldown_minutes']
        for field in safety_fields:
            if field not in safety:
                logger.error(f"Safety configuration missing required field: {field}")
                logger.error(f"Available safety fields: {list(safety.keys())}")
                raise ConfigError(f"Safety configuration missing required field: {field}")
            
            # Validate numeric values
            try:
                value = float(safety[field])
                if value <= 0:
                    logger.error(f"Invalid {field}: {value} (must be positive)")
                    raise ConfigError(f"{field} must be positive, got: {value}")
                logger.debug(f"Safety {field}={value}")
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid value for {field}: {safety[field]}")
                raise ConfigError(f"{field} must be a valid positive number: {e}")
        
        logger.info("Configuration validation completed successfully")
    
    @property
    def location(self) -> Dict[str, Any]:
        """Get location configuration."""
        return self._config['location']
    
    @property
    def devices(self) -> Dict[str, Any]:
        """Get devices configuration."""
        return self._config.get('devices', {})
    
    @property
    def weather_api(self) -> Dict[str, Any]:
        """Get weather API configuration."""
        return self._config.get('weather_api', {
            'provider': 'open-meteo'
        })
    
    @property
    def thresholds(self) -> Dict[str, Any]:
        """Get threshold configuration (deprecated, returns defaults if not present)."""
        return self._config.get('thresholds', {
            'temperature_f': 32,
            'lead_time_minutes': 60,
            'trailing_time_minutes': 60
        })
    
    @property
    def morning_mode(self) -> Dict[str, Any]:
        """Get morning mode configuration (deprecated, returns defaults if not present)."""
        return self._config.get('morning_mode', {
            'enabled': False,
            'start_hour': 6,
            'end_hour': 8
        })
    
    @property
    def vacation_mode(self) -> bool:
        """Get vacation mode status."""
        return self._config.get('vacation_mode', False)
    
    @property
    def safety(self) -> Dict[str, Any]:
        """Get safety configuration."""
        return self._config['safety']
    
    @property
    def scheduler(self) -> Dict[str, Any]:
        """Get scheduler configuration."""
        return self._config['scheduler']
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config.get('logging', {
            'level': 'INFO',
            'max_file_size_mb': 10,
            'backup_count': 5
        })
    
    @property
    def health_check(self) -> Dict[str, Any]:
        """Get health check configuration."""
        return self._config.get('health_check', {
            'interval_hours': 24,
            'max_consecutive_failures': 3
        })
    
    @property
    def notifications(self) -> Dict[str, Any]:
        """Get notifications configuration."""
        return self._config.get('notifications', {
            'email': {'enabled': False},
            'webhook': {'enabled': False}
        })
    
    @property
    def reboot(self) -> Dict[str, Any]:
        """Get reboot configuration."""
        return self._config.get('reboot', {
            'pause_seconds': 60
        })
    
    @property
    def health_server(self) -> Dict[str, Any]:
        """Get health server configuration."""
        return self._config.get('health_server', {
            'enabled': False,
            'host': '0.0.0.0',
            'port': 4329
        })
    
    @property
    def web(self) -> Dict[str, Any]:
        """Get web UI configuration."""
        return self._config.get('web', {
            'enabled': True,
            'bind_host': '0.0.0.0',
            'port': 4328
        })
    
    @property
    def env_overridden_paths(self) -> Dict[str, str]:
        """
        Get mapping of config paths to environment variable names that override them.
        
        Returns:
            Dictionary mapping config paths (e.g., 'location.latitude') to env var names (e.g., 'HEATTRAX_LATITUDE')
        """
        return self._env_overridden_paths

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
ENV_VAR_MAPPING = {
    # Location settings
    'LATITUDE': ('location', 'latitude', float),
    'LONGITUDE': ('location', 'longitude', float),
    'TIMEZONE': ('location', 'timezone', str),
    
    # Device settings
    'TAPO_IP_ADDRESS': ('device', 'ip_address', str),
    'TAPO_USERNAME': ('device', 'username', str),
    'TAPO_PASSWORD': ('device', 'password', str),
    
    # Threshold settings
    'THRESHOLD_TEMP_F': ('thresholds', 'temperature_f', float),
    'LEAD_TIME_MINUTES': ('thresholds', 'lead_time_minutes', int),
    'TRAILING_TIME_MINUTES': ('thresholds', 'trailing_time_minutes', int),
    
    # Scheduler settings
    'CHECK_INTERVAL_MINUTES': ('scheduler', 'check_interval_minutes', int),
    'FORECAST_HOURS': ('scheduler', 'forecast_hours', int),
    
    # Safety settings
    'MAX_RUNTIME_HOURS': ('safety', 'max_runtime_hours', float),
    'COOLDOWN_MINUTES': ('safety', 'cooldown_minutes', int),
    
    # Morning mode settings
    'MORNING_MODE_ENABLED': ('morning_mode', 'enabled', lambda x: x.lower() in ('true', '1', 'yes', 'on')),
    'MORNING_MODE_START_HOUR': ('morning_mode', 'start_hour', int),
    'MORNING_MODE_END_HOUR': ('morning_mode', 'end_hour', int),
    
    # Logging settings
    'LOG_LEVEL': ('logging', 'level', str),
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


def apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment variable overrides to configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configuration with environment variable overrides applied
    """
    logger.debug("Checking for environment variable overrides...")
    
    for env_var, (section, key, convert_type) in ENV_VAR_MAPPING.items():
        value = get_env_var(env_var, convert_type)
        
        if value is not None:
            # Ensure section exists in config
            if section not in config:
                config[section] = {}
            
            # Apply override
            config[section][key] = value
            logger.info(f"Environment variable override: {env_var} -> {section}.{key} = {value}")
    
    return config


class Config:
    """Configuration manager for the application."""
    
    def __init__(self, config_path: str = None):
        """
        Initialize configuration from YAML file with environment variable overrides.
        
        Args:
            config_path: Path to the configuration file (defaults to CONFIG_PATH env var or "config.yaml")
        """
        # Check for CONFIG_PATH environment variable if no path provided
        if config_path is None:
            config_path = os.environ.get('CONFIG_PATH', 'config.yaml')
        
        logger.info(f"Loading configuration from: {config_path}")
        self.config_path = Path(config_path)
        self._config = self._load_config()
        
        # Apply environment variable overrides
        self._config = apply_env_overrides(self._config)
        
        self._validate_config()
        logger.info("Configuration loaded and validated successfully")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file or create minimal config if file doesn't exist but env vars are set."""
        logger.debug(f"Checking if configuration file exists: {self.config_path}")
        
        if not self.config_path.exists():
            logger.warning(f"Configuration file not found: {self.config_path}")
            logger.info("Will attempt to use environment variables for configuration")
            
            # Create minimal config structure that will be populated by env vars
            config = {
                'location': {},
                'device': {},
                'thresholds': {},
                'scheduler': {},
                'safety': {},
                'morning_mode': {},
                'logging': {}
            }
            return config
        
        try:
            logger.debug(f"Reading configuration file: {self.config_path}")
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if config is None:
                logger.warning("Configuration file is empty, using empty config structure")
                config = {
                    'location': {},
                    'device': {},
                    'thresholds': {},
                    'scheduler': {},
                    'safety': {},
                    'morning_mode': {},
                    'logging': {}
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
        
        required_sections = ['location', 'device', 'thresholds', 'safety', 'scheduler']
        
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
        
        # Validate device
        logger.debug("Validating device configuration")
        device = self._config['device']
        
        if not isinstance(device, dict):
            logger.error(f"Device must be a dictionary, got: {type(device)}")
            raise ConfigError(f"Device configuration must be a dictionary")
        
        device_fields = ['ip_address', 'username', 'password']
        for field in device_fields:
            if field not in device:
                logger.error(f"Device configuration missing required field: {field}")
                logger.error(f"Available device fields: {list(device.keys())}")
                raise ConfigError(f"Device configuration missing required field: {field}")
            if not device[field]:
                logger.error(f"Device field '{field}' is empty")
                raise ConfigError(f"Device field '{field}' cannot be empty")
        
        logger.debug(f"Device validated: IP={device['ip_address']}, Username={device['username']}")
        
        # Validate thresholds
        logger.debug("Validating thresholds configuration")
        thresholds = self._config['thresholds']
        
        if not isinstance(thresholds, dict):
            logger.error(f"Thresholds must be a dictionary, got: {type(thresholds)}")
            raise ConfigError(f"Thresholds configuration must be a dictionary")
        
        threshold_fields = ['temperature_f', 'lead_time_minutes', 'trailing_time_minutes']
        for field in threshold_fields:
            if field not in thresholds:
                logger.error(f"Thresholds configuration missing required field: {field}")
                logger.error(f"Available threshold fields: {list(thresholds.keys())}")
                raise ConfigError(f"Thresholds configuration missing required field: {field}")
            
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
    def device(self) -> Dict[str, Any]:
        """Get device configuration."""
        return self._config['device']
    
    @property
    def thresholds(self) -> Dict[str, Any]:
        """Get threshold configuration."""
        return self._config['thresholds']
    
    @property
    def morning_mode(self) -> Dict[str, Any]:
        """Get morning mode configuration."""
        return self._config.get('morning_mode', {'enabled': False})
    
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

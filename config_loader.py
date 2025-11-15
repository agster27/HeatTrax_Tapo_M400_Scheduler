"""Configuration loader and validator for HeatTrax Scheduler."""

import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigError(Exception):
    """Configuration error exception."""
    pass


class Config:
    """Configuration manager for the application."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration from YAML file.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = Path(config_path)
        self._config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise ConfigError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing configuration file: {e}")
    
    def _validate_config(self):
        """Validate required configuration fields."""
        required_sections = ['location', 'device', 'thresholds', 'safety', 'scheduler']
        
        for section in required_sections:
            if section not in self._config:
                raise ConfigError(f"Missing required configuration section: {section}")
        
        # Validate location
        if 'latitude' not in self._config['location'] or 'longitude' not in self._config['location']:
            raise ConfigError("Location must include latitude and longitude")
        
        # Validate device
        device_fields = ['ip_address', 'username', 'password']
        for field in device_fields:
            if field not in self._config['device']:
                raise ConfigError(f"Device configuration missing required field: {field}")
        
        # Validate thresholds
        threshold_fields = ['temperature_f', 'lead_time_minutes', 'trailing_time_minutes']
        for field in threshold_fields:
            if field not in self._config['thresholds']:
                raise ConfigError(f"Thresholds configuration missing required field: {field}")
        
        # Validate safety
        safety_fields = ['max_runtime_hours', 'cooldown_minutes']
        for field in safety_fields:
            if field not in self._config['safety']:
                raise ConfigError(f"Safety configuration missing required field: {field}")
    
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

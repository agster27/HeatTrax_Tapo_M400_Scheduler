#!/usr/bin/env python3
"""
Test weather enabled/disabled toggle functionality.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_loader import Config, ConfigError


class TestWeatherToggle(unittest.TestCase):
    """Test weather enabled/disabled configuration toggle."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear any existing environment variables
        self.original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                self.original_env[key] = os.environ.pop(key)
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                os.environ.pop(key)
        for key, value in self.original_env.items():
            os.environ[key] = value
    
    def test_weather_enabled_default_true(self):
        """Test that weather is enabled by default in config."""
        # Create minimal config with required fields
        os.environ['HEATTRAX_LATITUDE'] = '40.0'
        os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
        os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
        os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
        os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
        os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
        
        # Don't set HEATTRAX_WEATHER_ENABLED - should default to true
        config = Config('nonexistent.yaml')
        
        # Weather API should be enabled by default
        weather_api = config.weather_api
        self.assertTrue(weather_api.get('enabled', True))
    
    def test_weather_enabled_explicit_true(self):
        """Test weather enabled when explicitly set to true."""
        os.environ['HEATTRAX_LATITUDE'] = '40.0'
        os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
        os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
        os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
        os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
        os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
        os.environ['HEATTRAX_WEATHER_ENABLED'] = 'true'
        
        config = Config('nonexistent.yaml')
        
        weather_api = config.weather_api
        self.assertTrue(weather_api.get('enabled'))
    
    def test_weather_disabled(self):
        """Test weather disabled when set to false."""
        os.environ['HEATTRAX_LATITUDE'] = '40.0'
        os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
        os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
        os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
        os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
        os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
        os.environ['HEATTRAX_WEATHER_ENABLED'] = 'false'
        
        config = Config('nonexistent.yaml')
        
        weather_api = config.weather_api
        self.assertFalse(weather_api.get('enabled'))
    
    def test_weather_enabled_various_true_values(self):
        """Test various true value representations."""
        true_values = ['true', 'True', 'TRUE', '1', 'yes', 'YES', 'on', 'ON']
        
        for true_val in true_values:
            with self.subTest(value=true_val):
                # Clear env
                for key in list(os.environ.keys()):
                    if key.startswith('HEATTRAX_'):
                        os.environ.pop(key)
                
                # Set required env vars
                os.environ['HEATTRAX_LATITUDE'] = '40.0'
                os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
                os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
                os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
                os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
                os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
                os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
                os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
                os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
                os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
                os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
                os.environ['HEATTRAX_WEATHER_ENABLED'] = true_val
                
                config = Config('nonexistent.yaml')
                weather_api = config.weather_api
                self.assertTrue(weather_api.get('enabled'), 
                              f"Weather should be enabled for value: {true_val}")
    
    def test_weather_disabled_various_false_values(self):
        """Test various false value representations."""
        false_values = ['false', 'False', 'FALSE', '0', 'no', 'NO', 'off', 'OFF']
        
        for false_val in false_values:
            with self.subTest(value=false_val):
                # Clear env
                for key in list(os.environ.keys()):
                    if key.startswith('HEATTRAX_'):
                        os.environ.pop(key)
                
                # Set required env vars
                os.environ['HEATTRAX_LATITUDE'] = '40.0'
                os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
                os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
                os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
                os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
                os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
                os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
                os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
                os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
                os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
                os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
                os.environ['HEATTRAX_WEATHER_ENABLED'] = false_val
                
                config = Config('nonexistent.yaml')
                weather_api = config.weather_api
                self.assertFalse(weather_api.get('enabled'), 
                               f"Weather should be disabled for value: {false_val}")


class TestHealthServerConfig(unittest.TestCase):
    """Test health server configuration."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = {}
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                self.original_env[key] = os.environ.pop(key)
    
    def tearDown(self):
        """Clean up test environment."""
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                os.environ.pop(key)
        for key, value in self.original_env.items():
            os.environ[key] = value
    
    def test_health_server_default_enabled(self):
        """Test that health server is enabled by default."""
        # Set minimal required env vars
        os.environ['HEATTRAX_LATITUDE'] = '40.0'
        os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
        os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
        os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
        os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
        os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
        
        config = Config('nonexistent.yaml')
        
        health_server = config.health_server
        self.assertTrue(health_server.get('enabled', True))
        self.assertEqual(health_server.get('host', '0.0.0.0'), '0.0.0.0')
        self.assertEqual(health_server.get('port', 8080), 8080)
    
    def test_health_server_custom_config(self):
        """Test custom health server configuration."""
        os.environ['HEATTRAX_LATITUDE'] = '40.0'
        os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
        os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
        os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
        os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
        os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
        os.environ['HEATTRAX_HEALTH_SERVER_ENABLED'] = 'false'
        os.environ['HEATTRAX_HEALTH_SERVER_HOST'] = '127.0.0.1'
        os.environ['HEATTRAX_HEALTH_SERVER_PORT'] = '9090'
        
        config = Config('nonexistent.yaml')
        
        health_server = config.health_server
        self.assertFalse(health_server.get('enabled'))
        self.assertEqual(health_server.get('host'), '127.0.0.1')
        self.assertEqual(health_server.get('port'), 9090)


if __name__ == '__main__':
    unittest.main()

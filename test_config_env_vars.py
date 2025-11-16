#!/usr/bin/env python3
"""
Test environment variable overrides for HeatTrax Scheduler configuration.
"""

import os
import sys
import unittest
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import Config, ConfigError


class TestConfigEnvVarOverrides(unittest.TestCase):
    """Test configuration environment variable overrides."""
    
    def setUp(self):
        """Set up test environment."""
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear any existing config-related env vars
        env_vars_to_clear = [
            'HEATTRAX_LATITUDE', 'HEATTRAX_LONGITUDE', 'HEATTRAX_TIMEZONE',
            'HEATTRAX_TAPO_IP_ADDRESS', 'HEATTRAX_TAPO_USERNAME', 'HEATTRAX_TAPO_PASSWORD',
            'HEATTRAX_THRESHOLD_TEMP_F', 'HEATTRAX_LEAD_TIME_MINUTES', 'HEATTRAX_TRAILING_TIME_MINUTES',
            'HEATTRAX_CHECK_INTERVAL_MINUTES', 'HEATTRAX_FORECAST_HOURS',
            'HEATTRAX_MAX_RUNTIME_HOURS', 'HEATTRAX_COOLDOWN_MINUTES',
            'HEATTRAX_MORNING_MODE_ENABLED', 'HEATTRAX_MORNING_MODE_START_HOUR', 'HEATTRAX_MORNING_MODE_END_HOUR',
            'HEATTRAX_LOG_LEVEL', 'HEATTRAX_CONFIG_PATH'
        ]
        for var in env_vars_to_clear:
            os.environ.pop(var, None)
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_config_loads_from_example_yaml(self):
        """Test that config loads from example YAML without env vars."""
        # Use multi-device config (config.example.yaml now uses multi-device format)
        config = Config('config.example.yaml')
        self.assertEqual(config.location['latitude'], 40.7128)
        # Multi-device config uses devices.credentials instead of device
        self.assertIn('credentials', config.devices)
        self.assertEqual(config.thresholds['temperature_f'], 34)
    
    def test_env_var_overrides_location(self):
        """Test location settings can be overridden with env vars."""
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'
        os.environ['HEATTRAX_LONGITUDE'] = '-0.1278'
        os.environ['HEATTRAX_TIMEZONE'] = 'Europe/London'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.location['latitude'], 51.5074)
        self.assertEqual(config.location['longitude'], -0.1278)
        self.assertEqual(config.location['timezone'], 'Europe/London')
    
    def test_env_var_overrides_device(self):
        """Test device settings can be overridden with env vars."""
        os.environ['HEATTRAX_TAPO_USERNAME'] = 'test@example.com'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'secret123'
        
        config = Config('config.example.yaml')
        # Multi-device mode uses devices.credentials
        self.assertEqual(config.devices['credentials']['username'], 'test@example.com')
        self.assertEqual(config.devices['credentials']['password'], 'secret123')
    
    def test_env_var_overrides_thresholds(self):
        """Test threshold settings can be overridden with env vars."""
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '32'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '90'
        os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '45'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.thresholds['temperature_f'], 32.0)
        self.assertEqual(config.thresholds['lead_time_minutes'], 90)
        self.assertEqual(config.thresholds['trailing_time_minutes'], 45)
    
    def test_env_var_overrides_safety(self):
        """Test safety settings can be overridden with env vars."""
        os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '8'
        os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '45'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.safety['max_runtime_hours'], 8.0)
        self.assertEqual(config.safety['cooldown_minutes'], 45)
    
    def test_env_var_overrides_scheduler(self):
        """Test scheduler settings can be overridden with env vars."""
        os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '15'
        os.environ['HEATTRAX_FORECAST_HOURS'] = '24'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.scheduler['check_interval_minutes'], 15)
        self.assertEqual(config.scheduler['forecast_hours'], 24)
    
    def test_env_var_overrides_morning_mode(self):
        """Test morning mode settings can be overridden with env vars."""
        os.environ['HEATTRAX_MORNING_MODE_ENABLED'] = 'false'
        os.environ['HEATTRAX_MORNING_MODE_START_HOUR'] = '7'
        os.environ['HEATTRAX_MORNING_MODE_END_HOUR'] = '9'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.morning_mode['enabled'], False)
        self.assertEqual(config.morning_mode['start_hour'], 7)
        self.assertEqual(config.morning_mode['end_hour'], 9)
    
    def test_env_var_boolean_values(self):
        """Test boolean environment variable conversion."""
        # Test true values
        for true_val in ['true', 'TRUE', '1', 'yes', 'YES', 'on', 'ON']:
            os.environ['HEATTRAX_MORNING_MODE_ENABLED'] = true_val
            config = Config('config.example.yaml')
            self.assertTrue(config.morning_mode['enabled'], f"Failed for value: {true_val}")
        
        # Test false values
        for false_val in ['false', 'FALSE', '0', 'no', 'NO', 'off', 'OFF']:
            os.environ['HEATTRAX_MORNING_MODE_ENABLED'] = false_val
            config = Config('config.example.yaml')
            self.assertFalse(config.morning_mode['enabled'], f"Failed for value: {false_val}")
    
    def test_env_var_overrides_logging(self):
        """Test logging settings can be overridden with env vars."""
        os.environ['HEATTRAX_LOG_LEVEL'] = 'DEBUG'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.logging_config['level'], 'DEBUG')
    
    def test_type_conversions(self):
        """Test that environment variables are converted to correct types."""
        os.environ['HEATTRAX_LATITUDE'] = '40.5'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '35.5'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '120'
        
        config = Config('config.example.yaml')
        
        # Float conversions
        self.assertIsInstance(config.location['latitude'], float)
        self.assertIsInstance(config.thresholds['temperature_f'], float)
        
        # Int conversions
        self.assertIsInstance(config.thresholds['lead_time_minutes'], int)
    
    def test_config_path_env_var(self):
        """Test HEATTRAX_CONFIG_PATH environment variable."""
        os.environ['HEATTRAX_CONFIG_PATH'] = 'config.example.yaml'
        
        # Should load from config.example.yaml via env var
        config = Config()
        self.assertEqual(config.location['latitude'], 40.7128)


def run_tests():
    """Run all tests."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestConfigEnvVarOverrides)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

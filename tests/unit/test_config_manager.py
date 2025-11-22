#!/usr/bin/env python3
"""
Unit tests for ConfigManager.
"""

import os
import sys
import unittest
import tempfile
import yaml
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager, ConfigValidationError


class TestConfigManager(unittest.TestCase):
    """Test ConfigManager functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_auto_generate_config_when_missing(self):
        """Test that config is auto-generated when file doesn't exist."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Config file should have been created
        self.assertTrue(self.config_path.exists())
        
        # Config should be valid and have default values
        config = config_manager.get_config(include_secrets=True)
        self.assertIn('location', config)
        self.assertIn('devices', config)
        self.assertIn('web', config)
        self.assertEqual(config['web']['enabled'], True)
        self.assertEqual(config['web']['port'], 4328)
    
    def test_load_existing_config(self):
        """Test loading an existing valid config file."""
        # Create a minimal valid config
        test_config = {
            'location': {
                'latitude': 51.5074,
                'longitude': -0.1278,
                'timezone': 'Europe/London'
            },
            'devices': {
                'credentials': {
                    'username': 'test_user',
                    'password': 'test_pass'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 32,
                'lead_time_minutes': 30,
                'trailing_time_minutes': 30
            },
            'safety': {
                'max_runtime_hours': 4,
                'cooldown_minutes': 20
            },
            'scheduler': {
                'check_interval_minutes': 5,
                'forecast_hours': 6
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        self.assertEqual(config['location']['latitude'], 51.5074)
        self.assertEqual(config['devices']['credentials']['username'], 'test_user')
    
    def test_validation_missing_required_section(self):
        """Test that validation fails with missing required section."""
        # Create invalid config missing 'devices'
        invalid_config = {
            'location': {
                'latitude': 40.0,
                'longitude': -74.0
            },
            'thresholds': {
                'temperature_f': 32,
                'lead_time_minutes': 30,
                'trailing_time_minutes': 30
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(invalid_config, f)
        
        # Should fall back to defaults
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config()
        
        # Should have devices section from defaults
        self.assertIn('devices', config)
    
    def test_validation_invalid_latitude(self):
        """Test that validation fails with invalid latitude."""
        config = {
            'location': {
                'latitude': 999,  # Invalid
                'longitude': -74.0
            },
            'devices': {
                'credentials': {'username': 'test', 'password': 'test'},
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 32,
                'lead_time_minutes': 30,
                'trailing_time_minutes': 30
            },
            'safety': {
                'max_runtime_hours': 4,
                'cooldown_minutes': 20
            },
            'scheduler': {
                'check_interval_minutes': 5,
                'forecast_hours': 6
            }
        }
        
        with self.assertRaises(ConfigValidationError):
            ConfigManager._validate_config(None, config)
    
    def test_get_config_filters_secrets(self):
        """Test that get_config filters out secrets by default."""
        # Create config with secrets
        test_config = {
            'location': {
                'latitude': 40.0,
                'longitude': -74.0,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test_user',
                    'password': 'secret_password'
                },
                'groups': {}
            },
            'weather_api': {
                'openweathermap': {
                    'api_key': 'secret_api_key'
                }
            },
            'thresholds': {
                'temperature_f': 32,
                'lead_time_minutes': 30,
                'trailing_time_minutes': 30
            },
            'safety': {
                'max_runtime_hours': 4,
                'cooldown_minutes': 20
            },
            'scheduler': {
                'check_interval_minutes': 5,
                'forecast_hours': 6
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Get config without secrets
        config = config_manager.get_config(include_secrets=False)
        self.assertEqual(config['devices']['credentials']['password'], '********')
        self.assertEqual(config['weather_api']['openweathermap']['api_key'], '********')
        
        # Get config with secrets
        config_with_secrets = config_manager.get_config(include_secrets=True)
        self.assertEqual(config_with_secrets['devices']['credentials']['password'], 'secret_password')
        self.assertEqual(config_with_secrets['weather_api']['openweathermap']['api_key'], 'secret_api_key')
    
    def test_update_config_success(self):
        """Test successful config update."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=True)
        
        # Modify config
        config['thresholds']['temperature_f'] = 30
        config['location']['latitude'] = 42.0
        
        # Update config
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'ok')
        
        # Verify changes persisted
        updated_config = config_manager.get_config(include_secrets=True)
        self.assertEqual(updated_config['thresholds']['temperature_f'], 30)
        self.assertEqual(updated_config['location']['latitude'], 42.0)
    
    def test_update_config_validation_error(self):
        """Test that update fails with invalid config."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=True)
        
        # Make config invalid
        config['location']['latitude'] = 999  # Invalid latitude
        
        # Update should fail
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('validation', result['message'].lower())
        
        # Original config should be unchanged
        current_config = config_manager.get_config(include_secrets=True)
        self.assertNotEqual(current_config['location']['latitude'], 999)
    
    def test_preserve_secrets_on_update(self):
        """Test that secrets are preserved when updating config."""
        # Create config with secret
        test_config = {
            'location': {
                'latitude': 40.0,
                'longitude': -74.0,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test_user',
                    'password': 'secret_password'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 32,
                'lead_time_minutes': 30,
                'trailing_time_minutes': 30
            },
            'safety': {
                'max_runtime_hours': 4,
                'cooldown_minutes': 20
            },
            'scheduler': {
                'check_interval_minutes': 5,
                'forecast_hours': 6
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Get config without secrets (password will be masked)
        config = config_manager.get_config(include_secrets=False)
        self.assertEqual(config['devices']['credentials']['password'], '********')
        
        # Update with masked password
        config['thresholds']['temperature_f'] = 30
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'ok')
        
        # Verify password was preserved
        updated_config = config_manager.get_config(include_secrets=True)
        self.assertEqual(updated_config['devices']['credentials']['password'], 'secret_password')
    
    def test_requires_restart_detection(self):
        """Test detection of changes that require restart."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=True)
        
        # Change web port (requires restart)
        config['web']['port'] = 5000
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['restart_required'], 'true')
    
    def test_env_overrides_applied(self):
        """Test that environment variables override config values."""
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'
        os.environ['HEATTRAX_LONGITUDE'] = '-0.1278'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '30'
        
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        self.assertEqual(config['location']['latitude'], 51.5074)
        self.assertEqual(config['location']['longitude'], -0.1278)
        self.assertEqual(config['thresholds']['temperature_f'], 30)


if __name__ == '__main__':
    unittest.main()

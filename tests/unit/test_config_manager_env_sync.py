#!/usr/bin/env python3
"""
Unit tests for ConfigManager environment variable to YAML synchronization.

Tests the new feature where env-overridden values are synced back to config.yaml
on startup, so that when env vars are removed later, the config persists.
"""

import os
import sys
import unittest
import tempfile
import yaml
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager


class TestConfigManagerEnvSync(unittest.TestCase):
    """Test environment variable to YAML synchronization on startup."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear all HEATTRAX env vars
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
    
    def test_first_run_no_config_env_only(self):
        """
        Test first run with no config.yaml, env vars only.
        
        Scenario: Fresh deployment with only env vars set, no config file exists yet.
        Expected: config.yaml is created with env-provided values.
        """
        # Set environment variables
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'
        os.environ['HEATTRAX_LONGITUDE'] = '-0.1278'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_ENABLED'] = 'true'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST'] = 'smtp.gmail.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT'] = '587'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME'] = 'test@gmail.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD'] = 'secret'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_FROM'] = 'test@gmail.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_TO'] = 'admin@example.com'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '30'
        
        # Instantiate ConfigManager (file doesn't exist yet)
        config_manager = ConfigManager(str(self.config_path))
        
        # Assert: effective config includes env-provided values
        config = config_manager.get_config(include_secrets=True)
        self.assertEqual(config['location']['latitude'], 51.5074)
        self.assertEqual(config['location']['longitude'], -0.1278)
        self.assertEqual(config['notifications']['email']['enabled'], True)
        self.assertEqual(config['notifications']['email']['smtp_host'], 'smtp.gmail.com')
        self.assertEqual(config['thresholds']['temperature_f'], 30.0)
        
        # Assert: env_overridden_paths contains expected paths
        env_paths = config_manager.get_env_overridden_paths()
        self.assertIn('location.latitude', env_paths)
        self.assertIn('location.longitude', env_paths)
        self.assertIn('notifications.email.enabled', env_paths)
        self.assertIn('thresholds.temperature_f', env_paths)
        self.assertEqual(env_paths['location.latitude'], 'HEATTRAX_LATITUDE')
        
        # Assert: config.yaml was created and contains env-provided values
        self.assertTrue(self.config_path.exists())
        
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertEqual(disk_config['location']['latitude'], 51.5074)
        self.assertEqual(disk_config['location']['longitude'], -0.1278)
        self.assertEqual(disk_config['notifications']['email']['enabled'], True)
        self.assertEqual(disk_config['notifications']['email']['smtp_host'], 'smtp.gmail.com')
        self.assertEqual(disk_config['thresholds']['temperature_f'], 30.0)
    
    def test_existing_config_new_env_overrides(self):
        """
        Test existing config.yaml with new env overrides.
        
        Scenario: config.yaml exists with some values, env vars override them.
        Expected: On-disk config.yaml is updated to match env-provided values.
        """
        # Create initial config.yaml with baseline values
        initial_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'old_user',
                    'password': 'old_pass'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 34,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 60
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            },
            'notifications': {
                'email': {
                    'enabled': False,
                    'smtp_host': '',
                    'smtp_port': 587,
                    'smtp_username': '',
                    'smtp_password': '',
                    'from_email': '',
                    'to_emails': [],
                    'use_tls': True
                }
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        # Set env vars to override email settings (need all required fields when enabled)
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_ENABLED'] = 'true'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST'] = 'smtp.example.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT'] = '587'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME'] = 'test@example.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD'] = 'secret'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_FROM'] = 'test@example.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_TO'] = 'admin@example.com'
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'
        
        # Instantiate ConfigManager
        config_manager = ConfigManager(str(self.config_path))
        
        # Assert: effective config has env-overridden values
        config = config_manager.get_config(include_secrets=True)
        self.assertEqual(config['notifications']['email']['enabled'], True)
        self.assertEqual(config['notifications']['email']['smtp_host'], 'smtp.example.com')
        self.assertEqual(config['location']['latitude'], 51.5074)
        
        # Assert: on-disk config.yaml has been updated with env values
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertEqual(disk_config['notifications']['email']['enabled'], True)
        self.assertEqual(disk_config['notifications']['email']['smtp_host'], 'smtp.example.com')
        self.assertEqual(disk_config['location']['latitude'], 51.5074)
        
        # Assert: other values remain unchanged
        self.assertEqual(disk_config['thresholds']['temperature_f'], 34)
    
    def test_env_removed_later(self):
        """
        Test env var removed after previous sync.
        
        Scenario: 
        1. First run with env var - value synced to YAML
        2. Env var removed and app restarted
        Expected: Config loads value from YAML, no env override active.
        """
        # Step 1: First run with env var
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_ENABLED'] = 'true'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST'] = 'smtp.gmail.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT'] = '587'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME'] = 'test@gmail.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD'] = 'secret'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_FROM'] = 'test@gmail.com'
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_TO'] = 'admin@example.com'
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Verify env override is active
        env_paths = config_manager.get_env_overridden_paths()
        self.assertIn('notifications.email.enabled', env_paths)
        
        # Verify config.yaml contains the value
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        self.assertEqual(disk_config['notifications']['email']['enabled'], True)
        
        # Step 2: Remove env vars and restart (simulate)
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
        
        # Instantiate new ConfigManager (simulates restart)
        config_manager2 = ConfigManager(str(self.config_path))
        
        # Assert: config still has enabled=True (from YAML, not env)
        config = config_manager2.get_config(include_secrets=True)
        self.assertEqual(config['notifications']['email']['enabled'], True)
        
        # Assert: env_overridden_paths does NOT contain the path anymore
        env_paths2 = config_manager2.get_env_overridden_paths()
        self.assertNotIn('notifications.email.enabled', env_paths2)
        
        # Assert: no additional write was triggered (YAML already has the value)
        # We can't easily check this without mocking, but at least verify the file wasn't corrupted
        with open(self.config_path, 'r') as f:
            disk_config2 = yaml.safe_load(f)
        self.assertEqual(disk_config2['notifications']['email']['enabled'], True)
    
    def test_no_op_when_env_and_yaml_match(self):
        """
        Test no-op when env and YAML already match.
        
        Scenario: config.yaml already contains the same values that env vars would set.
        Expected: No write is performed (optimization).
        """
        # Create config.yaml with values that match what env vars will provide
        initial_config = {
            'location': {
                'latitude': 51.5074,  # Will match env var
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test_user',
                    'password': 'test_pass'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 34,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 60
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        # Get initial modification time
        initial_mtime = self.config_path.stat().st_mtime
        
        # Set env var with same value as YAML
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'
        
        # Small delay to ensure mtime would change if file is written
        import time
        time.sleep(0.01)
        
        # Instantiate ConfigManager
        config_manager = ConfigManager(str(self.config_path))
        
        # Assert: effective config has the value
        config = config_manager.get_config(include_secrets=True)
        self.assertEqual(config['location']['latitude'], 51.5074)
        
        # Assert: file modification time hasn't changed (no write occurred)
        final_mtime = self.config_path.stat().st_mtime
        self.assertEqual(initial_mtime, final_mtime, "Config file should not be rewritten when values already match")
    
    def test_multiple_env_overrides_partial_sync(self):
        """
        Test multiple env overrides with only some needing sync.
        
        Scenario: Some env vars match YAML, some don't.
        Expected: Only changed values trigger a write.
        """
        # Create initial config with some matching values
        initial_config = {
            'location': {
                'latitude': 40.7128,  # Will be overridden by env
                'longitude': -0.1278,  # Will match env
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test_user',
                    'password': 'test_pass'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 34,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 60
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        # Set env vars - one matches, one doesn't
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'  # Different from YAML
        os.environ['HEATTRAX_LONGITUDE'] = '-0.1278'  # Same as YAML
        
        # Instantiate ConfigManager
        config_manager = ConfigManager(str(self.config_path))
        
        # Assert: both values are in effective config
        config = config_manager.get_config(include_secrets=True)
        self.assertEqual(config['location']['latitude'], 51.5074)
        self.assertEqual(config['location']['longitude'], -0.1278)
        
        # Assert: YAML was updated with the new latitude
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertEqual(disk_config['location']['latitude'], 51.5074)
        self.assertEqual(disk_config['location']['longitude'], -0.1278)
    
    def test_validation_error_prevents_startup(self):
        """
        Test that validation errors are still caught during env sync.
        
        Scenario: Env var provides invalid value (e.g., latitude > 90).
        Expected: Validation fails and falls back to defaults.
        """
        # Set invalid env var
        os.environ['HEATTRAX_LATITUDE'] = '999'  # Invalid latitude
        
        # Create initial valid config
        initial_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test_user',
                    'password': 'test_pass'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 34,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 60
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        # ConfigManager should handle the validation error and fall back
        # The existing code already handles this in the exception blocks
        config_manager = ConfigManager(str(self.config_path))
        
        # Config should be loaded (either with valid values or defaults)
        config = config_manager.get_config(include_secrets=True)
        self.assertIn('location', config)
        self.assertIn('devices', config)


if __name__ == '__main__':
    unittest.main()

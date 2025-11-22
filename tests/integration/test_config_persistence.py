#!/usr/bin/env python3
"""
Unit tests for configuration persistence and validation.
Tests for the bug fix where Web UI config changes don't persist.
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


class TestConfigPersistence(unittest.TestCase):
    """Test configuration persistence to disk."""
    
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
    
    def test_email_enabled_persistence(self):
        """Test that notifications.email.enabled persists to disk."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=True)
        
        # Initially should be disabled
        self.assertFalse(config['notifications']['email']['enabled'])
        
        # Enable email notifications with valid SMTP settings
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user@example.com'
        config['notifications']['email']['smtp_password'] = 'password123'
        config['notifications']['email']['from_email'] = 'user@example.com'
        config['notifications']['email']['to_emails'] = ['recipient@example.com']
        config['notifications']['email']['use_tls'] = True
        
        # Update config
        result = config_manager.update_config(config, preserve_secrets=True)
        
        # Should succeed
        self.assertEqual(result['status'], 'ok', f"Update failed: {result.get('message')}")
        
        # Verify in-memory config updated
        updated_config = config_manager.get_config(include_secrets=True)
        self.assertTrue(updated_config['notifications']['email']['enabled'])
        self.assertEqual(updated_config['notifications']['email']['smtp_host'], 'smtp.example.com')
        
        # Verify on-disk config persisted
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertTrue(disk_config['notifications']['email']['enabled'])
        self.assertEqual(disk_config['notifications']['email']['smtp_host'], 'smtp.example.com')
    
    def test_email_enabled_toggle_false_to_true(self):
        """Test toggling email from false to true."""
        # Create initial config with email disabled
        initial_config = {
            'location': {
                'latitude': 40.0,
                'longitude': -74.0,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test',
                    'password': 'test'
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
            },
            'notifications': {
                'email': {
                    'enabled': False,
                    'smtp_host': '',
                    'smtp_port': 587,
                    'smtp_username': '',
                    'smtp_password': '',
                    'from_email': '',
                    'to_emails': []
                }
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Get config and enable email with valid settings
        config = config_manager.get_config(include_secrets=True)
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.gmail.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'test@gmail.com'
        config['notifications']['email']['smtp_password'] = 'app_password'
        config['notifications']['email']['from_email'] = 'test@gmail.com'
        config['notifications']['email']['to_emails'] = ['admin@example.com']
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'ok')
        
        # Reload config from disk and verify
        with open(self.config_path, 'r') as f:
            reloaded = yaml.safe_load(f)
        
        self.assertTrue(reloaded['notifications']['email']['enabled'])
    
    def test_email_enabled_survives_restart(self):
        """Test that email enabled setting survives a simulated restart."""
        # First session: enable email
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user@example.com'
        config['notifications']['email']['smtp_password'] = 'password123'
        config['notifications']['email']['from_email'] = 'user@example.com'
        config['notifications']['email']['to_emails'] = ['recipient@example.com']
        
        result = config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # Simulate restart by creating new ConfigManager instance
        del config_manager
        config_manager_new = ConfigManager(str(self.config_path))
        
        # Verify email is still enabled
        reloaded_config = config_manager_new.get_config(include_secrets=True)
        self.assertTrue(reloaded_config['notifications']['email']['enabled'])
        self.assertEqual(reloaded_config['notifications']['email']['smtp_host'], 'smtp.example.com')


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_email_enabled_without_smtp_host_fails(self):
        """Test that enabling email without smtp_host fails validation."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        # Enable email but don't set smtp_host
        config['notifications']['email']['enabled'] = True
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('smtp_host', result['message'].lower())
    
    def test_email_enabled_without_smtp_port_fails(self):
        """Test that enabling email without valid smtp_port fails validation."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        # Don't set smtp_port or set invalid port
        config['notifications']['email']['smtp_port'] = 0
        config['notifications']['email']['smtp_username'] = 'user'
        config['notifications']['email']['smtp_password'] = 'pass'
        config['notifications']['email']['from_email'] = 'from@example.com'
        config['notifications']['email']['to_emails'] = ['to@example.com']
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('smtp_port', result['message'].lower())
    
    def test_email_enabled_with_invalid_port_type_fails(self):
        """Test that enabling email with non-integer port fails validation."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 'not_a_number'
        config['notifications']['email']['smtp_username'] = 'user'
        config['notifications']['email']['smtp_password'] = 'pass'
        config['notifications']['email']['from_email'] = 'from@example.com'
        config['notifications']['email']['to_emails'] = ['to@example.com']
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'error')
    
    def test_email_enabled_without_to_emails_fails(self):
        """Test that enabling email without to_emails fails validation."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user'
        config['notifications']['email']['smtp_password'] = 'pass'
        config['notifications']['email']['from_email'] = 'from@example.com'
        config['notifications']['email']['to_emails'] = []  # Empty list
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('to_emails', result['message'].lower())
    
    def test_email_disabled_with_incomplete_settings_succeeds(self):
        """Test that email can be disabled even with incomplete settings."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        # Disable email with incomplete settings
        config['notifications']['email']['enabled'] = False
        config['notifications']['email']['smtp_host'] = ''
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = ''
        config['notifications']['email']['smtp_password'] = ''
        config['notifications']['email']['from_email'] = ''
        config['notifications']['email']['to_emails'] = []
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        # Should succeed because email is disabled
        self.assertEqual(result['status'], 'ok')
    
    def test_webhook_enabled_without_url_fails(self):
        """Test that enabling webhook without URL fails validation."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        config['notifications']['webhook']['enabled'] = True
        config['notifications']['webhook']['url'] = ''
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('url', result['message'].lower())


class TestSecretPreservation(unittest.TestCase):
    """Test that secrets are preserved during config updates."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.original_env = os.environ.copy()
        
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_smtp_password_preserved_when_masked(self):
        """Test that SMTP password is preserved when submitted as masked."""
        # Create config with actual password
        initial_config = {
            'location': {
                'latitude': 40.0,
                'longitude': -74.0,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test',
                    'password': 'device_pass'
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
            },
            'notifications': {
                'email': {
                    'enabled': True,
                    'smtp_host': 'smtp.example.com',
                    'smtp_port': 587,
                    'smtp_username': 'user@example.com',
                    'smtp_password': 'real_smtp_password',
                    'from_email': 'user@example.com',
                    'to_emails': ['admin@example.com']
                }
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(initial_config, f)
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Get config without secrets (password will be masked)
        config = config_manager.get_config(include_secrets=False)
        self.assertEqual(config['notifications']['email']['smtp_password'], '********')
        self.assertEqual(config['devices']['credentials']['password'], '********')
        
        # Make a different change (temperature)
        config['thresholds']['temperature_f'] = 30
        
        # Update with preserve_secrets=True
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'ok')
        
        # Verify password was preserved
        updated_config = config_manager.get_config(include_secrets=True)
        self.assertEqual(updated_config['notifications']['email']['smtp_password'], 'real_smtp_password')
        self.assertEqual(updated_config['devices']['credentials']['password'], 'device_pass')
        
        # Verify on disk
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertEqual(disk_config['notifications']['email']['smtp_password'], 'real_smtp_password')
    
    def test_multiple_secrets_preserved(self):
        """Test that all secrets are preserved simultaneously."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get config with secrets and set them
        config = config_manager.get_config(include_secrets=True)
        config['devices']['credentials']['password'] = 'device_secret'
        config['weather_api']['openweathermap']['api_key'] = 'weather_api_key'
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user'
        config['notifications']['email']['smtp_password'] = 'smtp_secret'
        config['notifications']['email']['from_email'] = 'from@example.com'
        config['notifications']['email']['to_emails'] = ['to@example.com']
        config['notifications']['webhook']['enabled'] = True
        config['notifications']['webhook']['url'] = 'https://webhook.example.com/secret_token'
        
        # Save
        result = config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # Get config without secrets
        masked_config = config_manager.get_config(include_secrets=False)
        
        # All secrets should be masked
        self.assertEqual(masked_config['devices']['credentials']['password'], '********')
        self.assertEqual(masked_config['weather_api']['openweathermap']['api_key'], '********')
        self.assertEqual(masked_config['notifications']['email']['smtp_password'], '********')
        self.assertEqual(masked_config['notifications']['webhook']['url'], '********')
        
        # Update with a non-secret change
        masked_config['thresholds']['temperature_f'] = 28
        result = config_manager.update_config(masked_config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # All secrets should still be preserved
        final_config = config_manager.get_config(include_secrets=True)
        self.assertEqual(final_config['devices']['credentials']['password'], 'device_secret')
        self.assertEqual(final_config['weather_api']['openweathermap']['api_key'], 'weather_api_key')
        self.assertEqual(final_config['notifications']['email']['smtp_password'], 'smtp_secret')
        self.assertEqual(final_config['notifications']['webhook']['url'], 'https://webhook.example.com/secret_token')


class TestEnvVarReadOnly(unittest.TestCase):
    """Test that env-var-overridden fields remain read-only."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.original_env = os.environ.copy()
        
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_env_overridden_field_tracked(self):
        """Test that env-overridden fields are tracked."""
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_ENABLED'] = 'true'
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Get env overridden paths
        env_overrides = config_manager.get_env_overridden_paths()
        
        self.assertIn('notifications.email.enabled', env_overrides)
        self.assertEqual(env_overrides['notifications.email.enabled'], 'HEATTRAX_NOTIFICATION_EMAIL_ENABLED')
        self.assertIn('location.latitude', env_overrides)
        self.assertEqual(env_overrides['location.latitude'], 'HEATTRAX_LATITUDE')
    
    def test_env_override_not_changed_by_config_update(self):
        """Test that env-overridden values persist even if config update tries to change them."""
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_ENABLED'] = 'false'
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Verify email is disabled by env
        config = config_manager.get_config(include_secrets=True)
        self.assertFalse(config['notifications']['email']['enabled'])
        
        # Try to enable via config update
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user'
        config['notifications']['email']['smtp_password'] = 'pass'
        config['notifications']['email']['from_email'] = 'from@example.com'
        config['notifications']['email']['to_emails'] = ['to@example.com']
        
        result = config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # After update, env override should still apply
        # Create new instance to simulate restart
        del config_manager
        config_manager_new = ConfigManager(str(self.config_path))
        
        # Email should still be disabled (env override)
        reloaded_config = config_manager_new.get_config(include_secrets=True)
        self.assertFalse(reloaded_config['notifications']['email']['enabled'])


if __name__ == '__main__':
    unittest.main()

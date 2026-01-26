#!/usr/bin/env python3
"""
Unit tests for ConfigManager notification settings persistence.
Tests specifically target the bug where notification checkboxes in the Web UI
don't persist to config.yaml.
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


class TestConfigManagerNotifications(unittest.TestCase):
    """Test notification settings persistence through ConfigManager."""
    
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
        
        # Create initial config with notifications disabled and valid SMTP settings
        initial_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'test_password'
                },
                'groups': {}
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo',
                'openweathermap': {'api_key': ''},
                'open_meteo': {}
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
                'test_on_startup': False,
                'email': {
                    'enabled': False,
                    'smtp_host': 'smtp.example.com',
                    'smtp_port': 587,
                    'smtp_username': 'notifications@example.com',
                    'smtp_password': 'smtp_password',
                    'from_email': 'notifications@example.com',
                    'to_emails': ['admin@example.com'],
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
        
        # Write initial config
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(initial_config, f, default_flow_style=False)
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_toggle_notification_flags_to_true(self):
        """
        Test toggling notification flags from False to True.
        Simulates a Web UI-like full config update where notification
        flags are toggled to True.
        """
        # Get current config with secrets (simulating what the backend sees)
        config = self.config_manager.get_config(include_secrets=True)
        
        # Verify initial state (all disabled)
        self.assertFalse(config['notifications']['test_on_startup'])
        self.assertFalse(config['notifications']['email']['enabled'])
        
        # Toggle the flags to True
        config['notifications']['test_on_startup'] = True
        config['notifications']['email']['enabled'] = True
        
        # Update config (simulating the POST /api/config behavior)
        result = self.config_manager.update_config(config, preserve_secrets=True)
        
        # Assert update was successful
        self.assertEqual(result['status'], 'ok')
        
        # Verify in-memory config shows the flags as True
        updated_config = self.config_manager.get_config(include_secrets=False)
        self.assertTrue(updated_config['notifications']['test_on_startup'])
        self.assertTrue(updated_config['notifications']['email']['enabled'])
        
        # Verify on-disk config has the flags as True
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertTrue(disk_config['notifications']['test_on_startup'])
        self.assertTrue(disk_config['notifications']['email']['enabled'])
    
    def test_toggle_notification_flags_to_false(self):
        """
        Test toggling notification flags from True to False.
        """
        # First enable flags
        config = self.config_manager.get_config(include_secrets=True)
        config['notifications']['test_on_startup'] = True
        config['notifications']['email']['enabled'] = True
        
        result = self.config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # Now toggle them back to False
        config = self.config_manager.get_config(include_secrets=True)
        config['notifications']['test_on_startup'] = False
        config['notifications']['email']['enabled'] = False
        
        result = self.config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # Verify in-memory config
        updated_config = self.config_manager.get_config(include_secrets=False)
        self.assertFalse(updated_config['notifications']['test_on_startup'])
        self.assertFalse(updated_config['notifications']['email']['enabled'])
        
        # Verify on-disk config
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertFalse(disk_config['notifications']['test_on_startup'])
        self.assertFalse(disk_config['notifications']['email']['enabled'])
    
    def test_partial_notification_flag_updates(self):
        """
        Test updating only some notification flags while leaving others unchanged.
        """
        # Start with all disabled
        config = self.config_manager.get_config(include_secrets=True)
        
        # Only enable email.enabled, leave others as False
        config['notifications']['email']['enabled'] = True
        
        result = self.config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # Verify mixed state
        updated_config = self.config_manager.get_config(include_secrets=False)
        self.assertFalse(updated_config['notifications']['required'])
        self.assertFalse(updated_config['notifications']['test_on_startup'])
        self.assertTrue(updated_config['notifications']['email']['enabled'])
        
        # Verify on disk
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertFalse(disk_config['notifications']['required'])
        self.assertFalse(disk_config['notifications']['test_on_startup'])
        self.assertTrue(disk_config['notifications']['email']['enabled'])
    
    def test_notification_flags_persist_across_reload(self):
        """
        Test that notification flags persist correctly after reloading ConfigManager.
        """
        # Enable all flags
        config = self.config_manager.get_config(include_secrets=True)
        config['notifications']['required'] = True
        config['notifications']['test_on_startup'] = True
        config['notifications']['email']['enabled'] = True
        
        result = self.config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # Create a new ConfigManager instance (simulating app restart)
        new_config_manager = ConfigManager(str(self.config_path))
        
        # Verify the flags are still True
        reloaded_config = new_config_manager.get_config(include_secrets=False)
        self.assertTrue(reloaded_config['notifications']['required'])
        self.assertTrue(reloaded_config['notifications']['test_on_startup'])
        self.assertTrue(reloaded_config['notifications']['email']['enabled'])


if __name__ == '__main__':
    unittest.main()

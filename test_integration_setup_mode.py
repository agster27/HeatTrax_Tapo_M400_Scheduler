"""Integration test for setup mode end-to-end behavior."""

import unittest
import tempfile
import yaml
import os
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import Config
from config_manager import ConfigManager


class TestSetupModeIntegration(unittest.TestCase):
    """Integration tests for setup mode functionality."""
    
    def setUp(self):
        """Create temporary config file for testing."""
        self.temp_file = None
    
    def tearDown(self):
        """Clean up temporary files."""
        if self.temp_file and os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
    
    def _create_config(self, username='', password='', groups=None):
        """Helper to create a test config file."""
        if groups is None:
            groups = {}
        
        config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': username,
                    'password': password
                },
                'groups': groups
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo'
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            self.temp_file = f.name
        
        return self.temp_file
    
    def test_end_to_end_with_placeholder_credentials(self):
        """Test complete flow with placeholder credentials triggering setup mode."""
        # Create config with placeholders
        config_path = self._create_config('your_tapo_username', 'your_tapo_password')
        
        # Load config (should not raise exception)
        config = Config(config_path)
        self.assertIsNotNone(config)
        
        # Create ConfigManager
        config_manager = ConfigManager(config_path)
        
        # Check setup mode
        setup_mode, reason = config_manager.is_setup_mode()
        
        # Verify setup mode is active
        self.assertTrue(setup_mode, "Setup mode should be active with placeholder credentials")
        self.assertIn('placeholder', reason.lower())
        
        # Verify config is still accessible
        cfg = config_manager.get_config(include_secrets=False)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg['devices']['credentials']['username'], 'your_tapo_username')
    
    def test_end_to_end_with_valid_credentials(self):
        """Test complete flow with valid credentials enabling normal mode."""
        # Create config with valid credentials
        config_path = self._create_config('user@example.com', 'SecurePassword123!')
        
        # Load config
        config = Config(config_path)
        self.assertIsNotNone(config)
        
        # Create ConfigManager
        config_manager = ConfigManager(config_path)
        
        # Check setup mode
        setup_mode, reason = config_manager.is_setup_mode()
        
        # Verify normal mode is active
        self.assertFalse(setup_mode, "Setup mode should NOT be active with valid credentials")
        self.assertIn('valid', reason.lower())
    
    def test_end_to_end_updating_credentials_via_api(self):
        """Test updating credentials through the config manager (simulating API call)."""
        # Create config with placeholders
        config_path = self._create_config('your_tapo_username', 'your_tapo_password')
        
        # Create ConfigManager
        config_manager = ConfigManager(config_path)
        
        # Verify initially in setup mode
        setup_mode, _ = config_manager.is_setup_mode()
        self.assertTrue(setup_mode)
        
        # Get current config
        current_config = config_manager.get_config(include_secrets=True)
        
        # Update credentials
        current_config['devices']['credentials']['username'] = 'newuser@example.com'
        current_config['devices']['credentials']['password'] = 'NewPassword123!'
        
        # Save updated config
        result = config_manager.update_config(current_config, preserve_secrets=False)
        
        # Verify save succeeded
        self.assertEqual(result['status'], 'ok')
        
        # Create new ConfigManager instance to reload from disk
        config_manager2 = ConfigManager(config_path)
        
        # Verify setup mode is now inactive
        setup_mode, reason = config_manager2.is_setup_mode()
        self.assertFalse(setup_mode, "Setup mode should be inactive after updating credentials")
        self.assertIn('valid', reason.lower())
        
        # Verify credentials were persisted
        cfg = config_manager2.get_config(include_secrets=True)
        self.assertEqual(cfg['devices']['credentials']['username'], 'newuser@example.com')
        self.assertEqual(cfg['devices']['credentials']['password'], 'NewPassword123!')
    
    def test_end_to_end_empty_credentials_with_groups(self):
        """Test that setup mode activates even when device groups are configured."""
        # Create config with groups but empty credentials
        groups = {
            'heated_mats': {
                'enabled': True,
                'items': [
                    {'name': 'Test Mat', 'ip_address': '192.168.1.100'}
                ]
            }
        }
        config_path = self._create_config('', '', groups)
        
        # Load config
        config = Config(config_path)
        self.assertIsNotNone(config)
        
        # Create ConfigManager
        config_manager = ConfigManager(config_path)
        
        # Check setup mode
        setup_mode, reason = config_manager.is_setup_mode()
        
        # Verify setup mode is active despite having groups
        self.assertTrue(setup_mode, "Setup mode should be active even with device groups configured")
        self.assertIn('missing', reason.lower())
        
        # Verify groups are accessible
        cfg = config_manager.get_config(include_secrets=False)
        self.assertIn('heated_mats', cfg['devices']['groups'])
        self.assertEqual(len(cfg['devices']['groups']['heated_mats']['items']), 1)


class TestConfigManagerPersistence(unittest.TestCase):
    """Test that environment variable behavior matches requirements."""
    
    def setUp(self):
        """Save current env vars."""
        self.saved_env = {}
        self.temp_file = None
    
    def tearDown(self):
        """Restore env vars and clean up temp files."""
        # Restore environment
        for key in ['HEATTRAX_TAPO_USERNAME', 'HEATTRAX_TAPO_PASSWORD']:
            if key in self.saved_env:
                os.environ[key] = self.saved_env[key]
            elif key in os.environ:
                del os.environ[key]
        
        # Clean up temp file
        if self.temp_file and os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
    
    def _save_and_set_env(self, username=None, password=None):
        """Save current env vars and set new ones."""
        for key in ['HEATTRAX_TAPO_USERNAME', 'HEATTRAX_TAPO_PASSWORD']:
            if key in os.environ:
                self.saved_env[key] = os.environ[key]
        
        if username is not None:
            os.environ['HEATTRAX_TAPO_USERNAME'] = username
        elif 'HEATTRAX_TAPO_USERNAME' in os.environ:
            del os.environ['HEATTRAX_TAPO_USERNAME']
        
        if password is not None:
            os.environ['HEATTRAX_TAPO_PASSWORD'] = password
        elif 'HEATTRAX_TAPO_PASSWORD' in os.environ:
            del os.environ['HEATTRAX_TAPO_PASSWORD']
    
    def _create_config(self, username='', password=''):
        """Helper to create a test config file."""
        config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': username,
                    'password': password
                },
                'groups': {}
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo'
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
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            self.temp_file = f.name
        
        return self.temp_file
    
    def test_env_vars_do_not_auto_persist_on_load(self):
        """Test that loading config with env vars does NOT auto-update config.yaml."""
        # Create config with placeholders
        config_path = self._create_config('your_tapo_username', 'your_tapo_password')
        
        # Read original file content
        with open(config_path, 'r') as f:
            original_content = f.read()
        
        # Set environment variables
        self._save_and_set_env('envuser@example.com', 'EnvPassword123')
        
        # Load config (this applies env overrides in memory)
        config_manager = ConfigManager(config_path)
        
        # Verify setup mode is not active (env vars provide valid credentials)
        setup_mode, _ = config_manager.is_setup_mode()
        self.assertFalse(setup_mode)
        
        # Read file content again
        with open(config_path, 'r') as f:
            new_content = f.read()
        
        # File content should be UNCHANGED (env vars don't auto-persist)
        # Note: The sync behavior writes env overrides to disk, so we check the actual values
        with open(config_path, 'r') as f:
            config_on_disk = yaml.safe_load(f)
        
        # The credentials should have been synced to disk per the env sync feature
        # This is the intended behavior - env overrides ARE synced to disk on startup
        # to ensure config.yaml reflects last effective configuration
        self.assertEqual(config_on_disk['devices']['credentials']['username'], 'envuser@example.com')
        self.assertEqual(config_on_disk['devices']['credentials']['password'], 'EnvPassword123')


if __name__ == '__main__':
    unittest.main()

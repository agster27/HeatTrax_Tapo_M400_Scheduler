"""Unit tests for setup mode behavior."""

import unittest
import tempfile
import yaml
import os
from pathlib import Path
from src.config.config_loader import Config
from src.config.config_manager import ConfigManager


class TestSetupMode(unittest.TestCase):
    """Test cases for setup mode functionality."""
    
    def setUp(self):
        """Create a temporary config file for each test."""
        self.temp_file = None
    
    def tearDown(self):
        """Clean up temporary files."""
        if self.temp_file and os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
    
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
    
    def test_setup_mode_with_empty_credentials(self):
        """Test that setup mode is activated with empty credentials."""
        config_path = self._create_config('', '')
        config_manager = ConfigManager(config_path)
        
        setup_mode, reason = config_manager.is_setup_mode()
        
        self.assertTrue(setup_mode, "Setup mode should be active with empty credentials")
        self.assertIn('missing', reason.lower())
    
    def test_setup_mode_with_placeholder_username(self):
        """Test that setup mode is activated with placeholder username."""
        config_path = self._create_config('your_tapo_username', 'ValidPassword123')
        config_manager = ConfigManager(config_path)
        
        setup_mode, reason = config_manager.is_setup_mode()
        
        self.assertTrue(setup_mode, "Setup mode should be active with placeholder username")
        self.assertIn('placeholder', reason.lower())
    
    def test_setup_mode_with_placeholder_password(self):
        """Test that setup mode is activated with placeholder password."""
        config_path = self._create_config('user@example.com', 'your_tapo_password')
        config_manager = ConfigManager(config_path)
        
        setup_mode, reason = config_manager.is_setup_mode()
        
        self.assertTrue(setup_mode, "Setup mode should be active with placeholder password")
        self.assertIn('placeholder', reason.lower())
    
    def test_normal_mode_with_valid_credentials(self):
        """Test that normal mode is active with valid credentials."""
        config_path = self._create_config('user@example.com', 'SecurePassword123!')
        config_manager = ConfigManager(config_path)
        
        setup_mode, reason = config_manager.is_setup_mode()
        
        self.assertFalse(setup_mode, "Setup mode should NOT be active with valid credentials")
        self.assertIn('valid', reason.lower())
    
    def test_config_loader_no_exception_with_empty_credentials(self):
        """Test that Config can be loaded without exception when credentials are empty."""
        config_path = self._create_config('', '')
        
        # This should not raise an exception
        try:
            config = Config(config_path)
            self.assertIsNotNone(config)
            self.assertEqual(config.devices['credentials']['username'], '')
            self.assertEqual(config.devices['credentials']['password'], '')
        except Exception as e:
            self.fail(f"Config loading raised an exception with empty credentials: {e}")
    
    def test_config_loader_no_exception_with_placeholder_credentials(self):
        """Test that Config can be loaded without exception when credentials are placeholders."""
        config_path = self._create_config('your_tapo_username', 'your_tapo_password')
        
        # This should not raise an exception
        try:
            config = Config(config_path)
            self.assertIsNotNone(config)
            self.assertEqual(config.devices['credentials']['username'], 'your_tapo_username')
            self.assertEqual(config.devices['credentials']['password'], 'your_tapo_password')
        except Exception as e:
            self.fail(f"Config loading raised an exception with placeholder credentials: {e}")
    
    def test_config_manager_missing_credentials_section(self):
        """Test that ConfigManager handles missing credentials section gracefully."""
        # Create config without credentials section
        config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
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
        
        # Should not raise exception, should create empty credentials
        try:
            config_manager = ConfigManager(self.temp_file)
            setup_mode, reason = config_manager.is_setup_mode()
            
            self.assertTrue(setup_mode, "Setup mode should be active with missing credentials")
        except Exception as e:
            self.fail(f"ConfigManager raised an exception with missing credentials section: {e}")


class TestSetupModeEnvOverride(unittest.TestCase):
    """Test setup mode with environment variable overrides."""
    
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
            elif key in self.saved_env:
                del self.saved_env[key]
        
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
    
    def test_env_vars_override_placeholder_config(self):
        """Test that valid env vars override placeholder config values."""
        # Create config with placeholders
        config_path = self._create_config('your_tapo_username', 'your_tapo_password')
        
        # Set valid env vars
        self._save_and_set_env('valid@example.com', 'ValidPassword123')
        
        # Create ConfigManager with env overrides
        config_manager = ConfigManager(config_path)
        
        # Setup mode should NOT be active (env vars provide valid credentials)
        setup_mode, reason = config_manager.is_setup_mode()
        
        self.assertFalse(setup_mode, "Setup mode should NOT be active when env vars provide valid credentials")
    
    def test_placeholder_env_vars_trigger_setup_mode(self):
        """Test that placeholder env vars still trigger setup mode."""
        # Create config with valid credentials
        config_path = self._create_config('valid@example.com', 'ValidPassword123')
        
        # Set placeholder env vars (should override config)
        self._save_and_set_env('your_tapo_username', 'your_tapo_password')
        
        # Create ConfigManager with env overrides
        config_manager = ConfigManager(config_path)
        
        # Setup mode SHOULD be active (env vars override with placeholders)
        setup_mode, reason = config_manager.is_setup_mode()
        
        self.assertTrue(setup_mode, "Setup mode should be active when env vars provide placeholder credentials")


if __name__ == '__main__':
    unittest.main()

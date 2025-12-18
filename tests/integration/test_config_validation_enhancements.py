#!/usr/bin/env python3
"""
Integration tests for enhanced config validation.

Tests the validation improvements for:
1. Upload validation (web.port, outlets field, etc.)
2. Config file creation verification
3. Startup validation
"""

import os
import sys
import unittest
import tempfile
import json
import yaml
import copy
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestConfigValidationEnhancements(unittest.TestCase):
    """Test enhanced config validation."""
    
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
        
        # Create a minimal valid base config
        self.base_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpass123'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'items': [
                            {
                                'name': 'Test Device',
                                'ip_address': '192.168.1.100',
                                'outlets': [0]
                            }
                        ]
                    }
                }
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10
            }
        }
        
        # Write base config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(self.base_config, f)
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up temp directory
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_web_port_zero_rejected(self):
        """Test that web.port: 0 is rejected during upload validation."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Create config with invalid port
        import copy
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['web'] = {'port': 0}
        
        # Validate
        errors = web_server._validate_uploaded_config(invalid_config)
        
        # Check that the specific error is present
        self.assertTrue(
            any('web.port cannot be 0' in err for err in errors),
            f"Expected error about web.port being 0, got: {errors}"
        )
    
    def test_web_port_out_of_range_rejected(self):
        """Test that out-of-range port values are rejected."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Test negative port
        import copy
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['web'] = {'port': -1}
        errors = web_server._validate_uploaded_config(invalid_config)
        self.assertTrue(
            any('web.port must be between 1 and 65535' in err for err in errors),
            f"Expected error about port out of range, got: {errors}"
        )
        
        # Test port > 65535
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['web'] = {'port': 99999}
        errors = web_server._validate_uploaded_config(invalid_config)
        self.assertTrue(
            any('web.port must be between 1 and 65535' in err for err in errors),
            f"Expected error about port out of range, got: {errors}"
        )
    
    def test_web_port_non_integer_rejected(self):
        """Test that non-integer port values are rejected."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['web'] = {'port': '4328'}  # String instead of int
        
        errors = web_server._validate_uploaded_config(invalid_config)
        self.assertTrue(
            any('web.port must be an integer' in err for err in errors),
            f"Expected error about port type, got: {errors}"
        )
    
    def test_missing_outlets_field_rejected(self):
        """Test that missing outlets field is rejected."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Create config with missing outlets
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': '192.168.1.100'
                # Missing outlets field
            }
        ]
        
        errors = web_server._validate_uploaded_config(invalid_config)
        self.assertTrue(
            any('missing required \'outlets\' field' in err for err in errors),
            f"Expected error about missing outlets field, got: {errors}"
        )
    
    def test_empty_outlets_list_rejected(self):
        """Test that empty outlets list is rejected."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Create config with empty outlets list
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': '192.168.1.100',
                'outlets': []  # Empty list
            }
        ]
        
        errors = web_server._validate_uploaded_config(invalid_config)
        self.assertTrue(
            any('must be a non-empty list' in err for err in errors),
            f"Expected error about empty outlets list, got: {errors}"
        )
    
    def test_scheduler_interval_too_low_rejected(self):
        """Test that check_interval_minutes < 1 is rejected."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Test with 0
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['scheduler'] = {'check_interval_minutes': 0}
        
        errors = web_server._validate_uploaded_config(invalid_config)
        self.assertTrue(
            any('check_interval_minutes must be >= 1' in err for err in errors),
            f"Expected error about check_interval_minutes, got: {errors}"
        )
        
        # Test with negative
        invalid_config['scheduler'] = {'check_interval_minutes': -1}
        errors = web_server._validate_uploaded_config(invalid_config)
        self.assertTrue(
            any('check_interval_minutes must be >= 1' in err for err in errors),
            f"Expected error about check_interval_minutes, got: {errors}"
        )
    
    def test_valid_config_accepted(self):
        """Test that a valid config is accepted without errors."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Create fully valid config
        valid_config = copy.deepcopy(self.base_config)
        valid_config['web'] = {
            'port': 4328,
            'bind_host': '0.0.0.0',
            'pin': '1234'
        }
        valid_config['scheduler'] = {
            'check_interval_minutes': 10
        }
        
        errors = web_server._validate_uploaded_config(valid_config)
        self.assertEqual(len(errors), 0, f"Valid config should have no errors, got: {errors}")
    
    def test_upload_error_response_includes_help(self):
        """Test that upload validation errors include helpful context."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Create config with invalid port
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['web'] = {'port': 0}
        
        errors = web_server._validate_uploaded_config(invalid_config)
        
        # Verify we have detailed, helpful error messages
        self.assertTrue(len(errors) > 0, "Should have validation errors")
        self.assertTrue(
            any('Use a valid port number' in err for err in errors),
            "Error message should include helpful guidance"
        )
    
    def test_multiple_validation_errors_reported(self):
        """Test that multiple validation errors are all reported."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        # Create config with multiple issues
        invalid_config = copy.deepcopy(self.base_config)
        invalid_config['web'] = {'port': 0}
        invalid_config['scheduler'] = {'check_interval_minutes': 0}
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': '192.168.1.100'
                # Missing outlets
            }
        ]
        
        errors = web_server._validate_uploaded_config(invalid_config)
        
        # Should have at least 3 errors
        self.assertGreaterEqual(
            len(errors), 3,
            f"Expected at least 3 validation errors, got {len(errors)}: {errors}"
        )
    
    def test_config_file_creation_with_valid_defaults(self):
        """Test that config file creation ensures valid defaults."""
        # Delete existing config
        if self.config_path.exists():
            self.config_path.unlink()
        
        # Create new config manager (should create config file)
        config_manager = ConfigManager(str(self.config_path))
        
        # Verify file was created
        self.assertTrue(
            self.config_path.exists(),
            "Config file should be created if missing"
        )
        
        # Load and check defaults
        with open(self.config_path, 'r') as f:
            created_config = yaml.safe_load(f)
        
        # Verify web.port has a valid default
        self.assertIn('web', created_config, "Config should have web section")
        self.assertIn('port', created_config['web'], "Web section should have port")
        port = created_config['web']['port']
        self.assertIsInstance(port, int, "Port should be an integer")
        self.assertGreater(port, 0, "Port should be > 0")
        self.assertLessEqual(port, 65535, "Port should be <= 65535")


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Test device groups validation in ConfigManager.
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


class TestDeviceGroupsValidation(unittest.TestCase):
    """Test device groups validation in ConfigManager."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Create a minimal valid config
        self.valid_config = {
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
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'items': [
                            {
                                'name': 'Test Device',
                                'ip_address': '192.168.1.100',
                                'outlets': [0, 1]
                            }
                        ]
                    }
                }
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
            },
            'logging': {
                'level': 'INFO'
            }
        }
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def write_config(self, config):
        """Write config to test file."""
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f)
    
    def test_valid_device_groups_config(self):
        """Test that valid device groups configuration passes validation."""
        self.write_config(self.valid_config)
        
        # Should not raise exception
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config()
        
        # Check that groups are present
        self.assertIn('groups', config['devices'])
        self.assertIn('test_group', config['devices']['groups'])
    
    def test_device_groups_not_dict(self):
        """Test that device groups must be a dictionary."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups'] = ['not', 'a', 'dict']
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('groups must be a dictionary', result['message'])
    
    def test_group_not_dict(self):
        """Test that each group must be a dictionary."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['bad_group'] = 'not a dict'
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('bad_group must be a dictionary', result['message'])
    
    def test_group_enabled_must_be_bool(self):
        """Test that group enabled field must be a boolean."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['enabled'] = 'yes'
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('enabled must be a boolean', result['message'])
    
    def test_group_items_not_list(self):
        """Test that group items must be a list."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = {'not': 'a list'}
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('items must be a list', result['message'])
    
    def test_item_not_dict(self):
        """Test that each item must be a dictionary."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = ['not a dict']
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('items[0] must be a dictionary', result['message'])
    
    def test_item_missing_name(self):
        """Test that item must have name field."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'ip_address': '192.168.1.100'
            }
        ]
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn("must include 'name' field", result['message'])
    
    def test_item_empty_name(self):
        """Test that item name cannot be empty."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': '',
                'ip_address': '192.168.1.100'
            }
        ]
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn("must include 'name' field", result['message'])
    
    def test_item_missing_ip_address(self):
        """Test that item must have ip_address field."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device'
            }
        ]
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn("must include 'ip_address' field", result['message'])
    
    def test_item_empty_ip_address(self):
        """Test that item ip_address cannot be empty."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': ''
            }
        ]
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn("must include 'ip_address' field", result['message'])
    
    def test_item_outlets_not_list(self):
        """Test that outlets must be a list."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': '192.168.1.100',
                'outlets': 'not a list'
            }
        ]
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('outlets must be a list', result['message'])
    
    def test_item_outlet_not_integer(self):
        """Test that each outlet must be an integer."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': '192.168.1.100',
                'outlets': [0, 'not an int']
            }
        ]
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('must be a non-negative integer', result['message'])
    
    def test_item_outlet_negative(self):
        """Test that outlets cannot be negative."""
        self.write_config(self.valid_config)
        config_manager = ConfigManager(str(self.config_path))
        
        invalid_config = self.valid_config.copy()
        invalid_config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': '192.168.1.100',
                'outlets': [0, -1]
            }
        ]
        
        result = config_manager.update_config(invalid_config)
        self.assertEqual(result['status'], 'error')
        self.assertIn('must be a non-negative integer', result['message'])
    
    def test_item_without_outlets(self):
        """Test that items without outlets field are valid."""
        config = self.valid_config.copy()
        config['devices']['groups']['test_group']['items'] = [
            {
                'name': 'Test Device',
                'ip_address': '192.168.1.100'
            }
        ]
        self.write_config(config)
        
        # Should not raise exception
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config()
        
        # Check that item exists without outlets
        item = config['devices']['groups']['test_group']['items'][0]
        self.assertEqual(item['name'], 'Test Device')
        self.assertNotIn('outlets', item)
    
    def test_multiple_groups(self):
        """Test that multiple groups can be configured."""
        config = self.valid_config.copy()
        config['devices']['groups']['group2'] = {
            'enabled': False,
            'items': [
                {
                    'name': 'Device 2',
                    'ip_address': '192.168.1.101'
                }
            ]
        }
        self.write_config(config)
        
        # Should not raise exception
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config()
        
        # Check that both groups exist
        self.assertIn('test_group', config['devices']['groups'])
        self.assertIn('group2', config['devices']['groups'])
    
    def test_empty_groups(self):
        """Test that empty groups dictionary is valid."""
        config = self.valid_config.copy()
        config['devices']['groups'] = {}
        self.write_config(config)
        
        # Should not raise exception
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config()
        
        # Check that groups is empty
        self.assertEqual(config['devices']['groups'], {})


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Test that device groups can be saved via the web UI.
"""

import os
import sys
import unittest
import tempfile
import yaml
import time
import threading
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestDeviceGroupsWebUI(unittest.TestCase):
    """Test device groups in web UI."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Create a valid config with device groups
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
                                'name': 'Test Device 1',
                                'ip_address': '192.168.1.100',
                                'outlets': [0, 1]
                            },
                            {
                                'name': 'Test Device 2',
                                'ip_address': '192.168.1.101'
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
        
        # Write config
        with open(self.config_path, 'w') as f:
            yaml.dump(self.valid_config, f)
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_device_groups_preserved_in_update(self):
        """Test that device groups are preserved when updating config."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=True)
        
        # Verify groups exist
        self.assertIn('groups', config['devices'])
        self.assertIn('test_group', config['devices']['groups'])
        
        # Update config with modified groups
        new_config = config.copy()
        new_config['devices']['groups']['test_group']['items'].append({
            'name': 'Test Device 3',
            'ip_address': '192.168.1.102',
            'outlets': [0]
        })
        
        # Update
        result = config_manager.update_config(new_config, preserve_secrets=True)
        
        # Verify success
        self.assertEqual(result['status'], 'ok')
        
        # Reload and verify
        updated_config = config_manager.get_config(include_secrets=True)
        items = updated_config['devices']['groups']['test_group']['items']
        self.assertEqual(len(items), 3)
        self.assertEqual(items[2]['name'], 'Test Device 3')
    
    def test_empty_outlets_handled_correctly(self):
        """Test that items without outlets are handled correctly."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Create config with items that have and don't have outlets
        new_config = self.valid_config.copy()
        new_config['devices']['groups']['test_group'] = {
            'enabled': True,
            'items': [
                {
                    'name': 'Device with outlets',
                    'ip_address': '192.168.1.100',
                    'outlets': [0, 1]
                },
                {
                    'name': 'Device without outlets',
                    'ip_address': '192.168.1.101'
                }
            ]
        }
        
        # Update
        result = config_manager.update_config(new_config, preserve_secrets=True)
        
        # Verify success
        self.assertEqual(result['status'], 'ok')
        
        # Reload and verify
        updated_config = config_manager.get_config(include_secrets=True)
        items = updated_config['devices']['groups']['test_group']['items']
        
        # First item should have outlets
        self.assertIn('outlets', items[0])
        self.assertEqual(items[0]['outlets'], [0, 1])
        
        # Second item should not have outlets key
        self.assertNotIn('outlets', items[1])
    
    def test_add_new_group(self):
        """Test adding a new device group."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=True)
        
        # Add new group
        config['devices']['groups']['new_group'] = {
            'enabled': False,
            'items': [
                {
                    'name': 'New Device',
                    'ip_address': '192.168.1.200'
                }
            ]
        }
        
        # Update
        result = config_manager.update_config(config, preserve_secrets=True)
        
        # Verify success
        self.assertEqual(result['status'], 'ok')
        
        # Reload and verify
        updated_config = config_manager.get_config(include_secrets=True)
        self.assertIn('new_group', updated_config['devices']['groups'])
        self.assertFalse(updated_config['devices']['groups']['new_group']['enabled'])
    
    def test_delete_group(self):
        """Test deleting a device group."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=True)
        
        # Delete group
        del config['devices']['groups']['test_group']
        
        # Update
        result = config_manager.update_config(config, preserve_secrets=True)
        
        # Verify success
        self.assertEqual(result['status'], 'ok')
        
        # Reload and verify
        updated_config = config_manager.get_config(include_secrets=True)
        self.assertNotIn('test_group', updated_config['devices']['groups'])
        self.assertEqual(len(updated_config['devices']['groups']), 0)


if __name__ == '__main__':
    unittest.main()

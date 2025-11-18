#!/usr/bin/env python3
"""
Test that Web UI properly merges partial configuration updates.

This test validates the fix for the issue where saving configuration
from the Device Groups editor would send a partial config (e.g., only
{"devices": {"groups": {...}}}) which would fail backend validation
due to missing required sections like location, thresholds, safety, etc.
"""

import os
import sys
import unittest
import tempfile
import json
import yaml
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager
from web_server import WebServer


class TestWebUIPartialConfig(unittest.TestCase):
    """Test Web UI partial configuration updates."""
    
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
        
        # Create a valid full configuration
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
                    'existing_group': {
                        'enabled': True,
                        'items': [
                            {
                                'name': 'Test Device 1',
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
            },
            'notifications': {
                'required': False,
                'email': {
                    'enabled': False
                }
            },
            'web': {
                'enabled': True,
                'bind_host': '127.0.0.1',
                'port': 4328
            }
        }
        
        # Write initial config
        with open(self.config_path, 'w') as f:
            yaml.dump(self.valid_config, f)
        
        # Create config manager and web server
        self.config_manager = ConfigManager(str(self.config_path))
        self.web_server = WebServer(self.config_manager)
        
        # Get Flask test client
        self.client = self.web_server.app.test_client()
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_partial_config_device_groups_only_should_fail_without_merge(self):
        """
        Test that sending ONLY device groups (partial config) fails validation.
        
        This tests the CURRENT broken behavior. The fix should make the Web UI
        never send such partial configs, but we validate that the backend
        properly rejects them.
        """
        # Simulate what the Web UI currently does when editing only device groups:
        # It sends just the devices.groups section
        partial_config = {
            'devices': {
                'groups': {
                    'new_group': {
                        'enabled': True,
                        'items': [
                            {
                                'name': 'New Device',
                                'ip_address': '192.168.1.200'
                            }
                        ]
                    }
                }
            }
        }
        
        # Try to update with partial config
        response = self.client.post(
            '/api/config',
            data=json.dumps(partial_config),
            content_type='application/json'
        )
        
        # Should fail with 400 due to missing required sections
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Missing required section', data['message'])
    
    def test_full_config_with_device_groups_should_succeed(self):
        """
        Test that sending a FULL configuration with updated device groups succeeds.
        
        This is what the Web UI SHOULD do after our fix.
        """
        # Get the current full config
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        annotated_config = json.loads(response.data)
        
        # Extract plain values from annotated config
        full_config = self._extract_config_values(annotated_config)
        
        # Now modify just the device groups
        full_config['devices']['groups']['new_group'] = {
            'enabled': True,
            'items': [
                {
                    'name': 'New Device',
                    'ip_address': '192.168.1.200'
                }
            ]
        }
        
        # Send the FULL config with the device groups modification
        response = self.client.post(
            '/api/config',
            data=json.dumps(full_config),
            content_type='application/json'
        )
        
        # Should succeed
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        
        # Verify the new group was added
        updated_config = self.config_manager.get_config(include_secrets=True)
        self.assertIn('new_group', updated_config['devices']['groups'])
        self.assertIn('existing_group', updated_config['devices']['groups'])
    
    def test_merge_preserves_all_sections(self):
        """
        Test that when we merge partial config into full config,
        all required sections are preserved.
        """
        # Get the current full config
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        annotated_config = json.loads(response.data)
        
        # Extract plain values
        full_config = self._extract_config_values(annotated_config)
        
        # Simulate a partial update (only modifying one field)
        partial_update = {
            'thresholds': {
                'temperature_f': 32  # Changed from 34
            }
        }
        
        # Merge partial into full (simulating what the Web UI should do)
        merged_config = self._deep_merge(full_config, partial_update)
        
        # Verify all required sections are present
        required_sections = ['location', 'devices', 'thresholds', 'safety', 'scheduler']
        for section in required_sections:
            self.assertIn(section, merged_config, f"Missing section: {section}")
        
        # Verify the update took effect
        self.assertEqual(merged_config['thresholds']['temperature_f'], 32)
        
        # Verify other thresholds fields are preserved
        self.assertEqual(merged_config['thresholds']['lead_time_minutes'], 60)
        self.assertEqual(merged_config['thresholds']['trailing_time_minutes'], 60)
        
        # Verify other sections are unchanged
        self.assertEqual(merged_config['location']['latitude'], 40.7128)
        self.assertEqual(merged_config['safety']['max_runtime_hours'], 6)
    
    def _extract_config_values(self, annotated):
        """
        Extract plain config values from annotated config structure.
        
        This mirrors the extractConfigValues() function in the Web UI JavaScript.
        """
        if not isinstance(annotated, dict):
            return annotated
        
        # Check if this is a field with metadata
        if 'value' in annotated and 'source' in annotated:
            return annotated['value']
        
        # Recursively process nested objects
        result = {}
        for key, value in annotated.items():
            result[key] = self._extract_config_values(value)
        return result
    
    def _deep_merge(self, target, source):
        """
        Deep merge source into target.
        
        This mirrors the deepMerge() function we'll add to the Web UI JavaScript.
        """
        import copy
        result = copy.deepcopy(target)
        
        for key, value in source.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result


if __name__ == '__main__':
    unittest.main()

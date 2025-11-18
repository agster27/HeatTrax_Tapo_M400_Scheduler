#!/usr/bin/env python3
"""
Integration test for Web UI configuration workflow with the merge fix.

This test simulates the complete user workflow:
1. User loads the configuration page
2. User edits only device groups (or any other subset of fields)
3. User saves
4. The Web UI merges the edited fields into the full config
5. Backend receives a complete config and validates successfully
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


class TestWebUIIntegration(unittest.TestCase):
    """Integration test for Web UI configuration workflow."""
    
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
        
        # Create a realistic full configuration
        self.initial_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test_user@example.com',
                    'password': 'secure_password_123'
                },
                'groups': {
                    'driveway': {
                        'enabled': True,
                        'items': [
                            {
                                'name': 'Driveway Mat 1',
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
                    'enabled': False,
                    'smtp_host': '',
                    'smtp_port': 587,
                    'smtp_username': '',
                    'smtp_password': '',
                    'from_email': '',
                    'to_emails': [],
                    'use_tls': True
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
            yaml.dump(self.initial_config, f)
        
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
    
    def test_edit_only_device_groups_workflow(self):
        """
        Test the complete workflow when user edits only device groups.
        
        This simulates:
        1. GET /api/config (loadConfig in UI)
        2. User edits device groups
        3. collectFormValues() returns only the edited sections
        4. saveConfig() merges into full config
        5. POST /api/config with full merged config
        """
        # Step 1: Load config (simulates loadConfig())
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        annotated_config = json.loads(response.data)
        
        # Extract plain config (simulates extractConfigValues())
        full_config = self._extract_config_values(annotated_config)
        
        # Verify we have all sections
        self.assertIn('location', full_config)
        self.assertIn('devices', full_config)
        self.assertIn('thresholds', full_config)
        self.assertIn('safety', full_config)
        self.assertIn('scheduler', full_config)
        
        # Step 2: User edits only device groups (simulates form editing)
        # In the real UI, collectFormValues() would return values from all form fields,
        # but in practice, it might miss sections not in FORM_FIELDS or only partially
        # populate them. The key is that we merge into the full config.
        form_values = {
            'location': full_config['location'],
            'devices': {
                'credentials': full_config['devices']['credentials'],
                'groups': {
                    'driveway': {
                        'enabled': True,
                        'items': [
                            {
                                'name': 'Driveway Mat 1',
                                'ip_address': '192.168.1.100',
                                'outlets': [0, 1]
                            }
                        ]
                    },
                    'walkway': {
                        'enabled': True,
                        'items': [
                            {
                                'name': 'Walkway Mat',
                                'ip_address': '192.168.1.101',
                                'outlets': [0]
                            }
                        ]
                    }
                }
            },
            'thresholds': full_config['thresholds'],
            'safety': full_config['safety'],
            'scheduler': full_config['scheduler'],
            'logging': full_config.get('logging', {'level': 'INFO'}),
            'notifications': full_config.get('notifications', {}),
            'web': full_config.get('web', {})
        }
        
        # Step 3: Merge form values into full config (simulates deepMerge in saveConfig())
        merged_config = self._deep_merge(full_config, form_values)
        
        # Verify merge preserves all sections
        self.assertIn('location', merged_config)
        self.assertIn('devices', merged_config)
        self.assertIn('thresholds', merged_config)
        self.assertIn('safety', merged_config)
        self.assertIn('scheduler', merged_config)
        
        # Verify new device group is present
        self.assertIn('walkway', merged_config['devices']['groups'])
        self.assertIn('driveway', merged_config['devices']['groups'])
        
        # Step 4: Send merged config to API
        response = self.client.post(
            '/api/config',
            data=json.dumps(merged_config),
            content_type='application/json'
        )
        
        # Should succeed
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'ok')
        
        # Verify the config was actually saved
        saved_config = self.config_manager.get_config(include_secrets=True)
        self.assertIn('walkway', saved_config['devices']['groups'])
        self.assertIn('driveway', saved_config['devices']['groups'])
        self.assertEqual(len(saved_config['devices']['groups']), 2)
    
    def test_edit_multiple_sections_workflow(self):
        """
        Test workflow when user edits multiple sections.
        """
        # Load config
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        annotated_config = json.loads(response.data)
        full_config = self._extract_config_values(annotated_config)
        
        # User edits device groups AND thresholds
        form_values = full_config.copy()
        form_values['thresholds']['temperature_f'] = 32  # Changed from 34
        form_values['devices']['groups']['garage'] = {
            'enabled': False,
            'items': []
        }
        
        # Merge
        merged_config = self._deep_merge(full_config, form_values)
        
        # Save
        response = self.client.post(
            '/api/config',
            data=json.dumps(merged_config),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'ok')
        
        # Verify both changes were saved
        saved_config = self.config_manager.get_config(include_secrets=True)
        self.assertEqual(saved_config['thresholds']['temperature_f'], 32)
        self.assertIn('garage', saved_config['devices']['groups'])
        self.assertIn('driveway', saved_config['devices']['groups'])
    
    def test_delete_device_group_workflow(self):
        """
        Test workflow when user deletes a device group.
        """
        # Load config
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        annotated_config = json.loads(response.data)
        full_config = self._extract_config_values(annotated_config)
        
        # User deletes the driveway group
        form_values = full_config.copy()
        form_values['devices']['groups'] = {}  # Empty groups
        
        # Merge
        merged_config = self._deep_merge(full_config, form_values)
        
        # Save
        response = self.client.post(
            '/api/config',
            data=json.dumps(merged_config),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'ok')
        
        # Verify group was deleted
        saved_config = self.config_manager.get_config(include_secrets=True)
        self.assertEqual(len(saved_config['devices']['groups']), 0)
    
    def _extract_config_values(self, annotated):
        """Extract plain config values from annotated config structure."""
        if not isinstance(annotated, dict):
            return annotated
        
        if 'value' in annotated and 'source' in annotated:
            return annotated['value']
        
        result = {}
        for key, value in annotated.items():
            result[key] = self._extract_config_values(value)
        return result
    
    def _deep_merge(self, target, source):
        """Deep merge source into target."""
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

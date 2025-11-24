#!/usr/bin/env python3
"""
Integration tests for schedule UI refresh issue.
Tests that config is properly reloaded after schedule operations.
"""

import os
import sys
import unittest
import tempfile
import yaml
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestScheduleUIRefresh(unittest.TestCase):
    """Test that schedule changes immediately reflect in GET /api/config."""
    
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
        
        # Create initial config with a test group
        initial_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpassword'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'automation': {
                            'weather_control': False,
                            'precipitation_control': False,
                            'morning_mode': False,
                            'schedule_control': True
                        },
                        'schedules': [],
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
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo',
                'openweathermap': {'api_key': ''},
                'open_meteo': {},
                'resilience': {
                    'cache_file': 'state/weather_cache.json',
                    'cache_valid_hours': 6.0,
                    'forecast_horizon_hours': 12,
                    'refresh_interval_minutes': 10,
                    'retry_interval_minutes': 5,
                    'max_retry_interval_minutes': 60,
                    'outage_alert_after_minutes': 30
                }
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
                'required': False,
                'test_on_startup': False,
                'email': {
                    'enabled': False,
                    'smtp_host': '',
                    'smtp_port': 587,
                    'smtp_username': '',
                    'smtp_password': '',
                    'from_email': '',
                    'to_emails': [],
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
                'bind_host': '0.0.0.0',
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
            yaml.dump(initial_config, f)
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))
        
        # Create web server
        self.web_server = WebServer(self.config_manager, scheduler=None)
        self.app = self.web_server.app
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_add_schedule_refreshes_config(self):
        """Test that adding a schedule immediately reflects in GET /api/config."""
        # Get initial config - should have no schedules
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        initial_data = json.loads(response.data)
        
        # Navigate to schedules in the annotated config structure
        groups = initial_data.get('devices', {}).get('groups', {})
        test_group = groups.get('test_group', {})
        
        # The schedules might be wrapped in value/source metadata or be direct
        if isinstance(test_group.get('schedules'), dict):
            initial_schedules = test_group.get('schedules', {}).get('value', [])
        else:
            initial_schedules = test_group.get('schedules', [])
        
        self.assertEqual(len(initial_schedules), 0, "Should start with no schedules")
        
        # Add a new schedule
        new_schedule = {
            'name': 'Test Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5],  # Monday-Friday
            'on': {
                'type': 'time',
                'value': '08:00'
            },
            'off': {
                'type': 'time',
                'value': '17:00'
            }
        }
        
        response = self.client.post(
            '/api/groups/test_group/schedules',
            data=json.dumps(new_schedule),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        result = json.loads(response.data)
        self.assertTrue(result.get('success'))
        
        # Immediately get config again - should now have the schedule
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        updated_data = json.loads(response.data)
        
        groups = updated_data.get('devices', {}).get('groups', {})
        test_group = groups.get('test_group', {})
        
        # The schedules might be wrapped in value/source metadata or be direct
        if isinstance(test_group.get('schedules'), dict):
            updated_schedules = test_group.get('schedules', {}).get('value', [])
        else:
            updated_schedules = test_group.get('schedules', [])
        
        self.assertEqual(len(updated_schedules), 1, "Should have 1 schedule after adding")
        self.assertEqual(updated_schedules[0]['name'], 'Test Schedule')
        self.assertEqual(updated_schedules[0]['on']['value'], '08:00')
    
    def test_update_schedule_refreshes_config(self):
        """Test that updating a schedule immediately reflects in GET /api/config."""
        # First add a schedule
        initial_schedule = {
            'name': 'Initial Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1],  # Monday only
            'on': {
                'type': 'time',
                'value': '08:00'
            },
            'off': {
                'type': 'time',
                'value': '17:00'
            }
        }
        
        response = self.client.post(
            '/api/groups/test_group/schedules',
            data=json.dumps(initial_schedule),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        
        # Update the schedule
        updated_schedule = {
            'name': 'Updated Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2],  # Monday and Tuesday
            'on': {
                'type': 'time',
                'value': '09:00'
            },
            'off': {
                'type': 'time',
                'value': '18:00'
            }
        }
        
        response = self.client.put(
            '/api/groups/test_group/schedules/0',
            data=json.dumps(updated_schedule),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Immediately get config - should have updated schedule
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        groups = data.get('devices', {}).get('groups', {})
        test_group = groups.get('test_group', {})
        
        if isinstance(test_group.get('schedules'), dict):
            schedules = test_group.get('schedules', {}).get('value', [])
        else:
            schedules = test_group.get('schedules', [])
        
        self.assertEqual(len(schedules), 1)
        self.assertEqual(schedules[0]['name'], 'Updated Schedule')
        self.assertEqual(schedules[0]['on']['value'], '09:00')
        self.assertEqual(schedules[0]['off']['value'], '18:00')
    
    def test_delete_schedule_refreshes_config(self):
        """Test that deleting a schedule immediately reflects in GET /api/config."""
        # First add a schedule
        schedule = {
            'name': 'To Be Deleted',
            'enabled': True,
            'priority': 'normal',
            'days': [1],  # Monday only
            'on': {
                'type': 'time',
                'value': '08:00'
            },
            'off': {
                'type': 'time',
                'value': '17:00'
            }
        }
        
        response = self.client.post(
            '/api/groups/test_group/schedules',
            data=json.dumps(schedule),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        
        # Verify it's there
        response = self.client.get('/api/config')
        data = json.loads(response.data)
        groups = data.get('devices', {}).get('groups', {})
        test_group = groups.get('test_group', {})
        
        if isinstance(test_group.get('schedules'), dict):
            schedules = test_group.get('schedules', {}).get('value', [])
        else:
            schedules = test_group.get('schedules', [])
        
        self.assertEqual(len(schedules), 1)
        
        # Delete the schedule
        response = self.client.delete('/api/groups/test_group/schedules/0')
        self.assertEqual(response.status_code, 200)
        
        # Immediately get config - should have no schedules
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        groups = data.get('devices', {}).get('groups', {})
        test_group = groups.get('test_group', {})
        
        if isinstance(test_group.get('schedules'), dict):
            schedules = test_group.get('schedules', {}).get('value', [])
        else:
            schedules = test_group.get('schedules', [])
        
        self.assertEqual(len(schedules), 0, "Should have no schedules after deletion")
    
    def test_toggle_enabled_refreshes_config(self):
        """Test that toggling enabled status immediately reflects in GET /api/config."""
        # First add a schedule
        schedule = {
            'name': 'Toggle Test',
            'enabled': True,
            'priority': 'normal',
            'days': [1],  # Monday only
            'on': {
                'type': 'time',
                'value': '08:00'
            },
            'off': {
                'type': 'time',
                'value': '17:00'
            }
        }
        
        response = self.client.post(
            '/api/groups/test_group/schedules',
            data=json.dumps(schedule),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        
        # Toggle enabled to false
        response = self.client.put(
            '/api/groups/test_group/schedules/0/enabled',
            data=json.dumps({'enabled': False}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Immediately get config - should show enabled=false
        response = self.client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        groups = data.get('devices', {}).get('groups', {})
        test_group = groups.get('test_group', {})
        
        if isinstance(test_group.get('schedules'), dict):
            schedules = test_group.get('schedules', {}).get('value', [])
        else:
            schedules = test_group.get('schedules', [])
        
        self.assertEqual(len(schedules), 1)
        self.assertFalse(schedules[0]['enabled'], "Schedule should be disabled")


if __name__ == '__main__':
    unittest.main()

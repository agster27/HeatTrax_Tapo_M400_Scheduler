#!/usr/bin/env python3
"""
Integration tests for automation override API endpoints.

Note: The schedule_control automation flag has been removed.
All schedule-based automation now uses the unified schedules: array format.
"""

import os
import sys
import unittest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer
from src.scheduler.automation_overrides import AutomationOverrides


class TestAutomationAPI(unittest.TestCase):
    """Test automation override API endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.state_dir = Path(self.test_dir) / "state"
        self.state_dir.mkdir(exist_ok=True)
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
        
        # Create a test config with groups using unified schedules: array
        test_config = {
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
                    'heattrax': {
                        'enabled': True,
                        'automation': {
                            'weather_control': True,
                            'precipitation_control': True,
                            'morning_mode': False
                        },
                        'items': []
                    },
                    'christmas_lights': {
                        'enabled': True,
                        'automation': {
                            'weather_control': False,
                            'precipitation_control': False,
                            'morning_mode': False
                        },
                        'schedules': [
                            {
                                'name': 'Evening Lights',
                                'enabled': True,
                                'priority': 'normal',
                                'days': [1, 2, 3, 4, 5, 6, 7],
                                'on': {'type': 'time', 'value': '17:00'},
                                'off': {'type': 'time', 'value': '23:00'}
                            }
                        ],
                        'items': []
                    }
                }
            },
            'weather_api': {'enabled': True},
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
            'safety': {'max_runtime_hours': 6, 'cooldown_minutes': 30},
            'scheduler': {'check_interval_minutes': 10, 'forecast_hours': 12},
            'logging': {'level': 'INFO'},
            'health_check': {'interval_hours': 24, 'max_consecutive_failures': 3},
            'health_server': {'enabled': False},
            'reboot': {'pause_seconds': 60},
            'notifications': {'required': False, 'test_on_startup': False},
            'web': {'enabled': True, 'port': 4328}
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))
        
        # Create mock scheduler with automation_overrides
        self.mock_scheduler = Mock()
        self.mock_scheduler.automation_overrides = AutomationOverrides(
            state_file=str(self.state_dir / "automation_overrides.json")
        )
        
        # Create web server with mock scheduler
        self.web_server = WebServer(self.config_manager, scheduler=self.mock_scheduler)
        
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
    
    def test_get_automation_no_overrides(self):
        """Test GET /api/groups/{group}/automation without overrides."""
        response = self.client.get('/api/groups/heattrax/automation')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['group'], 'heattrax')
        self.assertEqual(data['base']['weather_control'], True)
        self.assertEqual(data['base']['precipitation_control'], True)
        self.assertEqual(data['base']['morning_mode'], False)
        self.assertEqual(data['overrides'], {})
        self.assertEqual(data['effective'], data['base'])
        self.assertEqual(data['schedules_count'], 0)
    
    def test_get_automation_with_schedules(self):
        """Test GET /api/groups/{group}/automation with unified schedules."""
        response = self.client.get('/api/groups/christmas_lights/automation')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['group'], 'christmas_lights')
        self.assertEqual(data['schedules_count'], 1)
    
    def test_get_automation_nonexistent_group(self):
        """Test GET /api/groups/{group}/automation for nonexistent group."""
        response = self.client.get('/api/groups/nonexistent/automation')
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_patch_automation_set_override(self):
        """Test PATCH /api/groups/{group}/automation to set override."""
        payload = {
            'morning_mode': True,
            'precipitation_control': False
        }
        
        response = self.client.patch(
            '/api/groups/heattrax/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['group'], 'heattrax')
        self.assertEqual(data['overrides']['morning_mode'], True)
        self.assertEqual(data['overrides']['precipitation_control'], False)
        self.assertEqual(data['effective']['morning_mode'], True)
        self.assertEqual(data['effective']['precipitation_control'], False)
        # Base values unchanged
        self.assertEqual(data['base']['morning_mode'], False)
        self.assertEqual(data['base']['precipitation_control'], True)
    
    def test_patch_automation_clear_override(self):
        """Test PATCH /api/groups/{group}/automation to clear override."""
        # First set an override
        payload = {'morning_mode': True}
        self.client.patch(
            '/api/groups/heattrax/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Now clear it
        payload = {'morning_mode': None}
        response = self.client.patch(
            '/api/groups/heattrax/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertNotIn('morning_mode', data['overrides'])
        # Should fall back to base value
        self.assertEqual(data['effective']['morning_mode'], False)
    
    def test_patch_automation_invalid_value(self):
        """Test PATCH /api/groups/{group}/automation with invalid value."""
        payload = {'morning_mode': 'invalid'}
        
        response = self.client.patch(
            '/api/groups/heattrax/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_patch_automation_nonexistent_group(self):
        """Test PATCH /api/groups/{group}/automation for nonexistent group."""
        payload = {'morning_mode': True}
        
        response = self.client.patch(
            '/api/groups/nonexistent/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_patch_automation_not_json(self):
        """Test PATCH /api/groups/{group}/automation without JSON."""
        response = self.client.patch('/api/groups/heattrax/automation')
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_patch_automation_multiple_flags(self):
        """Test PATCH /api/groups/{group}/automation with multiple flags."""
        payload = {
            'weather_control': False,
            'precipitation_control': False,
            'morning_mode': True
        }
        
        response = self.client.patch(
            '/api/groups/heattrax/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['effective']['weather_control'], False)
        self.assertEqual(data['effective']['precipitation_control'], False)
        self.assertEqual(data['effective']['morning_mode'], True)
    
    def test_patch_automation_persists(self):
        """Test that PATCH overrides persist across requests."""
        # Set override
        payload = {'morning_mode': True}
        self.client.patch(
            '/api/groups/heattrax/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        # Get automation to verify persistence
        response = self.client.get('/api/groups/heattrax/automation')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['overrides']['morning_mode'], True)
        self.assertEqual(data['effective']['morning_mode'], True)
    
    def test_patch_automation_ignores_unknown_flags(self):
        """Test PATCH /api/groups/{group}/automation ignores unknown flags."""
        payload = {
            'morning_mode': True,
            'unknown_flag': True,
            'schedule_control': True  # Legacy flag, should be ignored
        }
        
        response = self.client.patch(
            '/api/groups/heattrax/automation',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('morning_mode', data['overrides'])
        self.assertNotIn('unknown_flag', data['overrides'])
        self.assertNotIn('schedule_control', data['overrides'])


if __name__ == "__main__":
    unittest.main()

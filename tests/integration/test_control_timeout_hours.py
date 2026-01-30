#!/usr/bin/env python3
"""
Integration tests for /api/mat/control endpoint with timeout_hours parameter.
Tests the manual override duration selection feature.
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestControlTimeoutHours(unittest.TestCase):
    """Test /api/mat/control endpoint with timeout_hours parameter."""
    
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
        
        # Create minimal config with a test group
        config_data = {
            'location': {
                'latitude': 40.0,
                'longitude': -105.0,
                'timezone': 'America/Denver'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'test_password'
                },
                'groups': {
                    'test_group': {
                        'items': [
                            {
                                'name': 'test_device',
                                'ip_address': '192.168.1.100'
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
            },
            'web': {
                'port': 8080,
                'host': '0.0.0.0',
                'manual_override_timeout_hours': 3.0
            }
        }
        
        # Write config file
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))
        
        # Create web server
        self.web_server = WebServer(self.config_manager)
        
        # Mock scheduler and device manager
        mock_scheduler = Mock()
        mock_device_manager = Mock()
        mock_device_manager.control_device_outlet = Mock(return_value=None)
        mock_scheduler.device_manager = mock_device_manager
        mock_scheduler.run_coro_in_loop = Mock(side_effect=lambda coro: None)
        mock_scheduler.weather = None
        
        self.web_server.scheduler = mock_scheduler
        
        # Mock manual override manager
        self.mock_override_manager = Mock()
        self.web_server.manual_override = self.mock_override_manager
        
        # Get Flask test client
        self.client = self.web_server.app.test_client()
        
        # Set up session for authentication
        with self.client.session_transaction() as sess:
            sess['authenticated'] = True
            sess['authenticated_at'] = datetime.now().isoformat()
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_control_with_timeout_hours_3(self):
        """Test control endpoint with 3-hour timeout."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'on',
                                       'timeout_hours': 3
                                   })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify set_override was called with 3 hours
        self.mock_override_manager.set_override.assert_called_once()
        call_args = self.mock_override_manager.set_override.call_args
        self.assertEqual(call_args[0][0], 'test_group')
        self.assertEqual(call_args[0][1], 'on')
        self.assertEqual(call_args[0][2], 3)
    
    def test_control_with_timeout_hours_6(self):
        """Test control endpoint with 6-hour timeout."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'off',
                                       'timeout_hours': 6
                                   })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify set_override was called with 6 hours
        self.mock_override_manager.set_override.assert_called_once()
        call_args = self.mock_override_manager.set_override.call_args
        self.assertEqual(call_args[0][0], 'test_group')
        self.assertEqual(call_args[0][1], 'off')
        self.assertEqual(call_args[0][2], 6)
    
    def test_control_with_timeout_hours_9(self):
        """Test control endpoint with 9-hour timeout."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'on',
                                       'timeout_hours': 9
                                   })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify set_override was called with 9 hours
        self.mock_override_manager.set_override.assert_called_once()
        call_args = self.mock_override_manager.set_override.call_args
        self.assertEqual(call_args[0][0], 'test_group')
        self.assertEqual(call_args[0][1], 'on')
        self.assertEqual(call_args[0][2], 9)
    
    def test_control_without_timeout_hours_uses_default(self):
        """Test control endpoint without timeout_hours uses configured default."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'on'
                                   })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify set_override was called with default (3.0)
        self.mock_override_manager.set_override.assert_called_once()
        call_args = self.mock_override_manager.set_override.call_args
        self.assertEqual(call_args[0][0], 'test_group')
        self.assertEqual(call_args[0][1], 'on')
        self.assertEqual(call_args[0][2], 3.0)  # Default from config
    
    def test_control_with_invalid_timeout_hours_too_low(self):
        """Test control endpoint rejects timeout_hours <= 0."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'on',
                                       'timeout_hours': 0
                                   })
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('timeout_hours must be between 0 and 24', data['error'])
    
    def test_control_with_invalid_timeout_hours_too_high(self):
        """Test control endpoint rejects timeout_hours > 24."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'on',
                                       'timeout_hours': 25
                                   })
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('timeout_hours must be between 0 and 24', data['error'])
    
    def test_control_with_invalid_timeout_hours_not_a_number(self):
        """Test control endpoint rejects non-numeric timeout_hours."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'on',
                                       'timeout_hours': 'invalid'
                                   })
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('timeout_hours must be a number', data['error'])
    
    def test_control_with_float_timeout_hours(self):
        """Test control endpoint accepts float timeout_hours."""
        response = self.client.post('/api/mat/control',
                                   json={
                                       'group': 'test_group',
                                       'action': 'on',
                                       'timeout_hours': 4.5
                                   })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify set_override was called with 4.5 hours
        self.mock_override_manager.set_override.assert_called_once()
        call_args = self.mock_override_manager.set_override.call_args
        self.assertEqual(call_args[0][2], 4.5)


if __name__ == '__main__':
    unittest.main()

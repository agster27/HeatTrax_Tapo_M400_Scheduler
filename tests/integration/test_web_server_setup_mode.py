"""Test web server API endpoints in setup mode."""

import unittest
import tempfile
import yaml
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config.config_loader import Config
from src.config.config_manager import ConfigManager
from src.scheduler.scheduler_enhanced import EnhancedScheduler
from src.web.web_server import WebServer


class TestWebServerSetupMode(unittest.TestCase):
    """Test cases for web server API endpoints in setup mode."""
    
    def setUp(self):
        """Create a temporary config file for each test."""
        self.temp_file = None
        self.app = None
    
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
                'enabled': False,
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
            'web': {
                'enabled': True,
                'bind_host': '127.0.0.1',
                'port': 4328
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            self.temp_file = f.name
        
        return self.temp_file
    
    def test_api_devices_status_in_setup_mode(self):
        """Test /api/devices/status endpoint in setup mode."""
        config_path = self._create_config('', '')
        config_manager = ConfigManager(config_path)
        config = Config(config_path)
        
        # Create scheduler in setup mode
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Create web server
        web_server = WebServer(config_manager, scheduler)
        self.app = web_server.app.test_client()
        
        # Test the devices status endpoint
        response = self.app.get('/api/devices/status')
        
        # Should return 503 with setup mode information
        self.assertEqual(response.status_code, 503)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('setup_mode', data)
        self.assertTrue(data['setup_mode'])
        self.assertIn('message', data)
    
    def test_api_control_device_in_setup_mode(self):
        """Test /api/devices/control endpoint in setup mode."""
        config_path = self._create_config('', '')
        config_manager = ConfigManager(config_path)
        config = Config(config_path)
        
        # Create scheduler in setup mode
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Create web server
        web_server = WebServer(config_manager, scheduler)
        self.app = web_server.app.test_client()
        
        # Test the control device endpoint
        response = self.app.post('/api/devices/control',
                                json={
                                    'group': 'test_group',
                                    'device': 'test_device',
                                    'action': 'on'
                                },
                                content_type='application/json')
        
        # Should return 503 with setup mode information
        self.assertEqual(response.status_code, 503)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('setup_mode', data)
        self.assertTrue(data['setup_mode'])
        self.assertIn('message', data)
        self.assertFalse(data['success'])
    
    def test_api_devices_status_normal_mode(self):
        """Test /api/devices/status endpoint in normal mode with mocked device manager."""
        config_path = self._create_config('user@example.com', 'ValidPassword123!')
        config_manager = ConfigManager(config_path)
        config = Config(config_path)
        
        # Mock DeviceGroupManager to avoid actual device connections
        with patch('scheduler_enhanced.DeviceGroupManager') as mock_dgm:
            mock_instance = MagicMock()
            mock_instance.get_all_groups.return_value = []
            mock_instance.get_all_devices_status = MagicMock(return_value=[])
            mock_instance.get_initialization_summary = MagicMock(return_value={})
            mock_dgm.return_value = mock_instance
            
            # Create scheduler in normal mode
            scheduler = EnhancedScheduler(config, setup_mode=False)
            
            # Mock the run_coro_in_loop method
            scheduler.run_coro_in_loop = MagicMock(return_value=[])
            
            # Create web server
            web_server = WebServer(config_manager, scheduler)
            self.app = web_server.app.test_client()
            
            # Test the devices status endpoint
            response = self.app.get('/api/devices/status')
            
            # Should return 200 in normal mode
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'ok')
            self.assertIn('devices', data)


if __name__ == '__main__':
    unittest.main()

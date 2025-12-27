#!/usr/bin/env python3
"""
Integration test for mat status temperature retrieval.
Tests the fix for get_current_weather() -> get_current_conditions() bug.
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestMatStatusTemperature(unittest.TestCase):
    """Test mat status endpoint temperature retrieval."""
    
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
        
        # Create minimal config
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
                        'items': []
                    }
                }
            },
            'web': {
                'port': 8080,
                'host': '0.0.0.0'
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
    
    def test_mat_status_with_weather_temperature(self):
        """Test that mat status endpoint correctly retrieves temperature from weather service."""
        # Mock scheduler with weather service
        mock_scheduler = Mock()
        mock_weather = Mock()
        
        # Mock get_current_conditions to return (temp_f, precip_mm)
        async def mock_get_current_conditions():
            return (68.0, 0.0)  # 68°F, 0mm precipitation
        
        mock_weather.get_current_conditions = mock_get_current_conditions
        mock_scheduler.weather = mock_weather
        
        # Mock run_coro_in_loop to execute the coroutine
        def mock_run_coro(coro):
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        
        mock_scheduler.run_coro_in_loop = mock_run_coro
        
        # Mock device manager
        async def mock_get_all_devices_status():
            return []
        
        mock_device_manager = Mock()
        mock_device_manager.get_all_devices_status = mock_get_all_devices_status
        mock_scheduler.device_manager = mock_device_manager
        
        # Set the mock scheduler
        self.web_server.scheduler = mock_scheduler
        
        # Call the endpoint
        response = self.client.get('/api/mat/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('groups', data)
        
        # Check that at least one group exists (could be default groups)
        self.assertGreater(len(data['groups']), 0)
        
        # Verify temperature was retrieved and converted to Celsius for any group
        first_group_name = list(data['groups'].keys())[0]
        group_status = data['groups'][first_group_name]
        self.assertIn('temperature', group_status)
        
        # 68°F should convert to 20°C
        expected_temp_c = round((68.0 - 32) * 5/9, 1)
        self.assertEqual(group_status['temperature'], expected_temp_c)
    
    def test_mat_status_without_weather_service(self):
        """Test that mat status endpoint handles missing weather service gracefully."""
        # Mock scheduler without weather service
        mock_scheduler = Mock()
        mock_scheduler.weather = None
        
        # Mock device manager
        async def mock_get_all_devices_status():
            return []
        
        mock_device_manager = Mock()
        mock_device_manager.get_all_devices_status = mock_get_all_devices_status
        mock_scheduler.device_manager = mock_device_manager
        
        def mock_run_coro(coro):
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        
        mock_scheduler.run_coro_in_loop = mock_run_coro
        
        # Set the mock scheduler
        self.web_server.scheduler = mock_scheduler
        
        # Call the endpoint
        response = self.client.get('/api/mat/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Check that at least one group exists
        self.assertGreater(len(data['groups']), 0)
        
        # Temperature should be None when weather service is not available
        first_group_name = list(data['groups'].keys())[0]
        group_status = data['groups'][first_group_name]
        self.assertIsNone(group_status['temperature'])
    
    def test_mat_status_weather_service_error(self):
        """Test that mat status endpoint handles weather service errors gracefully."""
        # Mock scheduler with weather service that throws an error
        mock_scheduler = Mock()
        mock_weather = Mock()
        
        # Mock get_current_conditions to raise an exception
        async def mock_get_current_conditions_error():
            raise Exception("Weather service unavailable")
        
        mock_weather.get_current_conditions = mock_get_current_conditions_error
        mock_scheduler.weather = mock_weather
        
        def mock_run_coro(coro):
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        
        mock_scheduler.run_coro_in_loop = mock_run_coro
        
        # Mock device manager
        async def mock_get_all_devices_status():
            return []
        
        mock_device_manager = Mock()
        mock_device_manager.get_all_devices_status = mock_get_all_devices_status
        mock_scheduler.device_manager = mock_device_manager
        
        # Set the mock scheduler
        self.web_server.scheduler = mock_scheduler
        
        # Call the endpoint
        response = self.client.get('/api/mat/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Check that at least one group exists
        self.assertGreater(len(data['groups']), 0)
        
        # Temperature should be None when weather service errors
        first_group_name = list(data['groups'].keys())[0]
        group_status = data['groups'][first_group_name]
        self.assertIsNone(group_status['temperature'])


if __name__ == '__main__':
    unittest.main()

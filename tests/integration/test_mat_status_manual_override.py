#!/usr/bin/env python3
"""
Integration test for mat status manual override behavior.
Tests that the /api/mat/status endpoint correctly reports status based on
manual override action, not actual device states.
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestMatStatusManualOverride(unittest.TestCase):
    """Test mat status endpoint with manual override behavior."""
    
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
        
        # Create minimal config with two groups
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
                    'christmas_lights': {
                        'items': []
                    },
                    'heated_mats': {
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
    
    def test_manual_override_on_shows_on_despite_devices_off(self):
        """Test that manual override ON shows status as ON even if devices are physically OFF."""
        # Mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.weather = None
        
        # Mock device manager - all devices are OFF
        async def mock_get_all_devices_status():
            return [
                {
                    'group': 'christmas_lights',
                    'name': 'device1',
                    'outlets': [
                        {'is_on': False},  # All outlets OFF
                        {'is_on': False}
                    ]
                }
            ]
        
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
        
        # Set up manual override - ON action
        mock_override_manager = Mock()
        mock_override_manager.is_active.return_value = True
        mock_override_manager.get_status.return_value = {
            'active': True,
            'action': 'on',  # Override is set to ON
            'timeout_hours': 2.0,
            'expires_at': '2026-01-20T12:00:00+00:00'
        }
        
        self.web_server.scheduler = mock_scheduler
        self.web_server.manual_override = mock_override_manager
        
        # Call the endpoint
        response = self.client.get('/api/mat/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('groups', data)
        
        # Check christmas_lights group
        self.assertIn('christmas_lights', data['groups'])
        group_status = data['groups']['christmas_lights']
        
        # The status should be ON because of the manual override action
        # even though all devices are OFF
        self.assertTrue(group_status['is_on'], 
                       "Manual override ON should show status as ON regardless of device states")
        self.assertEqual(group_status['mode'], 'manual')
    
    def test_manual_override_off_shows_off_despite_devices_on(self):
        """Test that manual override OFF shows status as OFF even if devices are physically ON."""
        # Mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.weather = None
        
        # Mock device manager - some devices are ON
        async def mock_get_all_devices_status():
            return [
                {
                    'group': 'heated_mats',
                    'name': 'mat1',
                    'outlets': [
                        {'is_on': True},  # Some outlets are ON
                        {'is_on': False}
                    ]
                },
                {
                    'group': 'heated_mats',
                    'name': 'mat2',
                    'outlets': [
                        {'is_on': True},  # Another ON outlet
                        {'is_on': False}
                    ]
                }
            ]
        
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
        
        # Set up manual override manager - different groups have different overrides
        def mock_is_active(group_name):
            return group_name == 'heated_mats'
        
        def mock_get_status(group_name):
            if group_name == 'heated_mats':
                return {
                    'active': True,
                    'action': 'off',  # Override is set to OFF
                    'timeout_hours': 2.0,
                    'expires_at': '2026-01-20T12:00:00+00:00'
                }
            return None
        
        mock_override_manager = Mock()
        mock_override_manager.is_active = mock_is_active
        mock_override_manager.get_status = mock_get_status
        
        self.web_server.scheduler = mock_scheduler
        self.web_server.manual_override = mock_override_manager
        
        # Call the endpoint
        response = self.client.get('/api/mat/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('groups', data)
        
        # Check heated_mats group
        self.assertIn('heated_mats', data['groups'])
        group_status = data['groups']['heated_mats']
        
        # The status should be OFF because of the manual override action
        # even though some devices are ON
        self.assertFalse(group_status['is_on'], 
                        "Manual override OFF should show status as OFF regardless of device states")
        self.assertEqual(group_status['mode'], 'manual')
    
    def test_auto_mode_always_shows_off(self):
        """Test that AUTO mode (no override) always shows OFF regardless of device states.
        
        Mobile control interface is for manual overrides only, not for displaying
        schedule-driven state. When in AUTO mode, the UI should show OFF so users
        can manually override if desired.
        """
        # Mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.weather = None
        
        # Mock device manager - some devices ON, some OFF
        # (physical state should NOT affect the mobile UI in AUTO mode)
        async def mock_get_all_devices_status():
            return [
                {
                    'group': 'christmas_lights',
                    'name': 'lights1',
                    'outlets': [
                        {'is_on': True},  # Physically ON (from schedule)
                        {'is_on': True}
                    ]
                },
                {
                    'group': 'heated_mats',
                    'name': 'mat1',
                    'outlets': [
                        {'is_on': False},  # Physically OFF
                        {'is_on': False}
                    ]
                }
            ]
        
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
        
        # No manual overrides active
        mock_override_manager = Mock()
        mock_override_manager.is_active.return_value = False
        mock_override_manager.get_status.return_value = None
        
        self.web_server.scheduler = mock_scheduler
        self.web_server.manual_override = mock_override_manager
        
        # Call the endpoint
        response = self.client.get('/api/mat/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Both groups should show OFF in AUTO mode, regardless of physical state
        # This is because the mobile UI is for manual control only
        self.assertFalse(data['groups']['christmas_lights']['is_on'],
                       "AUTO mode should always show OFF (mobile UI is for manual control)")
        self.assertEqual(data['groups']['christmas_lights']['mode'], 'auto')
        
        self.assertFalse(data['groups']['heated_mats']['is_on'],
                        "AUTO mode should always show OFF (mobile UI is for manual control)")
        self.assertEqual(data['groups']['heated_mats']['mode'], 'auto')
    
    def test_independent_group_overrides(self):
        """Test that different groups can have independent manual overrides."""
        # Mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.weather = None
        
        # Mock device manager - all devices OFF
        async def mock_get_all_devices_status():
            return [
                {
                    'group': 'christmas_lights',
                    'name': 'lights1',
                    'outlets': [{'is_on': False}, {'is_on': False}]
                },
                {
                    'group': 'heated_mats',
                    'name': 'mat1',
                    'outlets': [{'is_on': False}, {'is_on': False}]
                }
            ]
        
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
        
        # Different overrides for different groups
        def mock_is_active(group_name):
            return group_name in ['christmas_lights', 'heated_mats']
        
        def mock_get_status(group_name):
            if group_name == 'christmas_lights':
                return {
                    'active': True,
                    'action': 'on',  # Christmas lights: override ON
                    'timeout_hours': 2.0,
                    'expires_at': '2026-01-20T12:00:00+00:00'
                }
            elif group_name == 'heated_mats':
                return {
                    'active': True,
                    'action': 'off',  # Heated mats: override OFF
                    'timeout_hours': 2.0,
                    'expires_at': '2026-01-20T12:00:00+00:00'
                }
            return None
        
        mock_override_manager = Mock()
        mock_override_manager.is_active = mock_is_active
        mock_override_manager.get_status = mock_get_status
        
        self.web_server.scheduler = mock_scheduler
        self.web_server.manual_override = mock_override_manager
        
        # Call the endpoint
        response = self.client.get('/api/mat/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Christmas lights should be ON (override ON)
        self.assertTrue(data['groups']['christmas_lights']['is_on'],
                       "Christmas lights should be ON from manual override")
        self.assertEqual(data['groups']['christmas_lights']['mode'], 'manual')
        
        # Heated mats should be OFF (override OFF)
        self.assertFalse(data['groups']['heated_mats']['is_on'],
                        "Heated mats should be OFF from manual override")
        self.assertEqual(data['groups']['heated_mats']['mode'], 'manual')


if __name__ == '__main__':
    unittest.main()

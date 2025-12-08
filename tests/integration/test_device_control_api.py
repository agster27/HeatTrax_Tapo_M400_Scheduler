#!/usr/bin/env python3
"""
Unit tests for device control API endpoints and device status functionality.
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer
from src.devices.device_group_manager import DeviceGroupManager, DeviceGroup, ManagedDevice


class TestDeviceStatusAPI(unittest.TestCase):
    """Test device status and control API endpoints."""
    
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
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))
        
        # Create mock scheduler with device manager
        self.mock_scheduler = Mock()
        self.mock_device_manager = Mock()
        self.mock_scheduler.device_manager = self.mock_device_manager
        
        # Mock run_coro_in_loop to execute coroutines synchronously
        def mock_run_coro_in_loop(coro):
            """Mock that executes coroutines synchronously for testing."""
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        
        self.mock_scheduler.run_coro_in_loop = mock_run_coro_in_loop
        
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
    
    def test_devices_status_endpoint_no_scheduler(self):
        """Test /api/devices/status endpoint when scheduler is not available."""
        # Create web server without scheduler
        web_server = WebServer(self.config_manager, scheduler=None)
        client = web_server.app.test_client()
        
        response = client.get('/api/devices/status')
        
        self.assertEqual(response.status_code, 503)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_devices_status_endpoint_success(self):
        """Test /api/devices/status endpoint with successful device status retrieval."""
        # Mock device status data
        mock_devices = [
            {
                'name': 'Test Device 1',
                'ip_address': '192.168.1.100',
                'group': 'test_group',
                'reachable': True,
                'has_outlets': True,
                'model': 'EP40M',
                'outlets': [
                    {'index': 0, 'is_on': True, 'alias': 'Outlet 0', 'controlled': True},
                    {'index': 1, 'is_on': False, 'alias': 'Outlet 1', 'controlled': True}
                ],
                'error': None
            },
            {
                'name': 'Test Device 2',
                'ip_address': '192.168.1.101',
                'group': 'test_group',
                'reachable': False,
                'has_outlets': False,
                'model': 'Unknown',
                'outlets': [],
                'error': 'Connection timeout'
            }
        ]
        
        # Mock initialization summary
        mock_init_summary = {
            'total_groups': 1,
            'groups': {},
            'overall': {
                'configured_devices': 2,
                'initialized_devices': 1,
                'failed_devices': 1
            }
        }
        
        # Mock the async method
        async def mock_get_status():
            return mock_devices
        
        self.mock_device_manager.get_all_devices_status = mock_get_status
        self.mock_device_manager.get_initialization_summary = Mock(return_value=mock_init_summary)
        
        response = self.client.get('/api/devices/status')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertEqual(data['status'], 'ok')
        self.assertIn('devices', data)
        self.assertEqual(len(data['devices']), 2)
        self.assertIn('timestamp', data)
        
        # Check first device details
        device1 = data['devices'][0]
        self.assertEqual(device1['name'], 'Test Device 1')
        self.assertTrue(device1['reachable'])
        self.assertEqual(device1['model'], 'EP40M')
        self.assertEqual(len(device1['outlets']), 2)
        self.assertTrue(device1['outlets'][0]['is_on'])
        self.assertFalse(device1['outlets'][1]['is_on'])
        
        # Check second device details
        device2 = data['devices'][1]
        self.assertEqual(device2['name'], 'Test Device 2')
        self.assertFalse(device2['reachable'])
        self.assertEqual(device2['model'], 'Unknown')
        self.assertEqual(device2['error'], 'Connection timeout')
    
    def test_devices_control_endpoint_missing_fields(self):
        """Test /api/devices/control endpoint with missing required fields."""
        # Test with missing 'action' field
        response = self.client.post('/api/devices/control',
                                    json={'group': 'test_group', 'device': 'test_device'})
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Missing required field', data['error'])
    
    def test_devices_control_endpoint_invalid_action(self):
        """Test /api/devices/control endpoint with invalid action."""
        response = self.client.post('/api/devices/control',
                                    json={
                                        'group': 'test_group',
                                        'device': 'test_device',
                                        'outlet': 0,
                                        'action': 'toggle'  # Invalid action
                                    })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('Invalid action', data['error'])
    
    def test_devices_control_endpoint_success(self):
        """Test /api/devices/control endpoint with successful control operation."""
        # Mock control result
        mock_result = {
            'success': True,
            'device': 'test_device',
            'outlet': 0,
            'action': 'on',
            'error': None
        }
        
        # Mock the async method
        async def mock_control(group, device, outlet, action):
            return mock_result
        
        self.mock_device_manager.control_device_outlet = mock_control
        
        response = self.client.post('/api/devices/control',
                                    json={
                                        'group': 'test_group',
                                        'device': 'test_device',
                                        'outlet': 0,
                                        'action': 'on'
                                    })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data['success'])
        self.assertEqual(data['device'], 'test_device')
        self.assertEqual(data['outlet'], 0)
        self.assertEqual(data['action'], 'on')
    
    def test_devices_control_endpoint_failure(self):
        """Test /api/devices/control endpoint with failed control operation."""
        # Mock control result with error
        mock_result = {
            'success': False,
            'device': 'test_device',
            'outlet': 0,
            'action': 'on',
            'error': 'Device not reachable'
        }
        
        # Mock the async method
        async def mock_control(group, device, outlet, action):
            return mock_result
        
        self.mock_device_manager.control_device_outlet = mock_control
        
        response = self.client.post('/api/devices/control',
                                    json={
                                        'group': 'test_group',
                                        'device': 'test_device',
                                        'outlet': 0,
                                        'action': 'on'
                                    })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Device not reachable')


class TestManagedDeviceDetailedStatus(unittest.TestCase):
    """Test ManagedDevice get_detailed_status method."""
    
    def test_get_detailed_status_single_device(self):
        """Test get_detailed_status for a single device (no outlets)."""
        import asyncio
        
        # Create mock device
        mock_device = Mock()
        mock_device.is_on = True
        mock_device.alias = 'Test Single Device'
        mock_device.children = None
        
        managed_device = ManagedDevice(
            config={'name': 'Test Device', 'ip_address': '192.168.1.100'},
            username='test',
            password='test'
        )
        managed_device.device = mock_device
        managed_device._initialized = True
        
        # Mock the update method
        async def mock_update():
            pass
        mock_device.update = mock_update
        
        # Get detailed status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(managed_device.get_detailed_status())
        finally:
            loop.close()
        
        # Verify status
        self.assertEqual(status['name'], 'Test Device')
        self.assertEqual(status['ip_address'], '192.168.1.100')
        self.assertTrue(status['reachable'])
        self.assertFalse(status['has_outlets'])
        self.assertEqual(len(status['outlets']), 1)
        self.assertTrue(status['outlets'][0]['is_on'])
        self.assertIsNone(status['outlets'][0]['index'])
    
    def test_get_detailed_status_multi_outlet_device(self):
        """Test get_detailed_status for a device with multiple outlets."""
        import asyncio
        
        # Create mock outlets
        mock_outlet_0 = Mock()
        mock_outlet_0.is_on = True
        mock_outlet_0.alias = 'Outlet 0'
        
        mock_outlet_1 = Mock()
        mock_outlet_1.is_on = False
        mock_outlet_1.alias = 'Outlet 1'
        
        # Create mock device
        mock_device = Mock()
        mock_device.children = [mock_outlet_0, mock_outlet_1]
        
        managed_device = ManagedDevice(
            config={
                'name': 'Test Multi-Outlet Device',
                'ip_address': '192.168.1.101',
                'outlets': [0, 1]
            },
            username='test',
            password='test'
        )
        managed_device.device = mock_device
        managed_device._initialized = True
        
        # Mock the update method
        async def mock_update():
            pass
        mock_device.update = mock_update
        
        # Get detailed status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(managed_device.get_detailed_status())
        finally:
            loop.close()
        
        # Verify status
        self.assertEqual(status['name'], 'Test Multi-Outlet Device')
        self.assertTrue(status['reachable'])
        self.assertTrue(status['has_outlets'])
        self.assertEqual(len(status['outlets']), 2)
        
        # Check outlet 0
        self.assertEqual(status['outlets'][0]['index'], 0)
        self.assertTrue(status['outlets'][0]['is_on'])
        self.assertEqual(status['outlets'][0]['alias'], 'Outlet 0')
        
        # Check outlet 1
        self.assertEqual(status['outlets'][1]['index'], 1)
        self.assertFalse(status['outlets'][1]['is_on'])
        self.assertEqual(status['outlets'][1]['alias'], 'Outlet 1')
    
    def test_get_detailed_status_unreachable_device(self):
        """Test get_detailed_status for an unreachable device."""
        import asyncio
        
        managed_device = ManagedDevice(
            config={'name': 'Unreachable Device', 'ip_address': '192.168.1.200'},
            username='test',
            password='test'
        )
        managed_device._initialized = False
        
        # Mock initialize to raise an exception
        async def mock_initialize():
            raise Exception('Connection timeout')
        
        managed_device.initialize = mock_initialize
        
        # Get detailed status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            status = loop.run_until_complete(managed_device.get_detailed_status())
        finally:
            loop.close()
        
        # Verify status
        self.assertEqual(status['name'], 'Unreachable Device')
        self.assertFalse(status['reachable'])
        self.assertIsNotNone(status['error'])
        self.assertIn('Connection timeout', status['error'])


class TestManagedDeviceControlOutlet(unittest.TestCase):
    """Test ManagedDevice control_outlet method."""
    
    def test_control_outlet_invalid_action(self):
        """Test control_outlet with invalid action."""
        import asyncio
        
        mock_device = Mock()
        mock_device.is_on = False
        
        managed_device = ManagedDevice(
            config={'name': 'Test Device', 'ip_address': '192.168.1.100'},
            username='test',
            password='test'
        )
        managed_device.device = mock_device
        managed_device._initialized = True
        
        # Mock the update method
        async def mock_update():
            pass
        mock_device.update = mock_update
        
        # Try to control with invalid action
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(managed_device.control_outlet(None, 'toggle'))
        finally:
            loop.close()
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertIn('Invalid action', result['error'])
    
    def test_control_outlet_turn_on_device(self):
        """Test control_outlet to turn on entire device."""
        import asyncio
        
        mock_device = Mock()
        mock_device.is_on = False
        
        # Mock turn_on method
        async def mock_turn_on():
            mock_device.is_on = True
        mock_device.turn_on = mock_turn_on
        
        managed_device = ManagedDevice(
            config={'name': 'Test Device', 'ip_address': '192.168.1.100'},
            username='test',
            password='test'
        )
        managed_device.device = mock_device
        managed_device._initialized = True
        
        # Mock the update method
        async def mock_update():
            pass
        mock_device.update = mock_update
        
        # Control the device
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(managed_device.control_outlet(None, 'on'))
        finally:
            loop.close()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'on')
        self.assertIsNone(result['outlet'])
    
    def test_control_outlet_turn_off_specific_outlet(self):
        """Test control_outlet to turn off a specific outlet."""
        import asyncio
        
        # Create mock outlet
        mock_outlet = Mock()
        mock_outlet.is_on = True
        
        # Mock turn_off method
        async def mock_turn_off():
            mock_outlet.is_on = False
        mock_outlet.turn_off = mock_turn_off
        
        # Create mock device with children
        mock_device = Mock()
        mock_device.children = [mock_outlet]
        
        managed_device = ManagedDevice(
            config={'name': 'Test Device', 'ip_address': '192.168.1.100'},
            username='test',
            password='test'
        )
        managed_device.device = mock_device
        managed_device._initialized = True
        
        # Mock the update method
        async def mock_update():
            pass
        mock_device.update = mock_update
        
        # Control the outlet
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(managed_device.control_outlet(0, 'off'))
        finally:
            loop.close()
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertEqual(result['action'], 'off')
        self.assertEqual(result['outlet'], 0)
    
    def test_control_outlet_invalid_outlet_index(self):
        """Test control_outlet with invalid outlet index."""
        import asyncio
        
        # Create mock device with one outlet
        mock_outlet = Mock()
        mock_outlet.is_on = False
        
        mock_device = Mock()
        mock_device.children = [mock_outlet]
        
        managed_device = ManagedDevice(
            config={'name': 'Test Device', 'ip_address': '192.168.1.100'},
            username='test',
            password='test'
        )
        managed_device.device = mock_device
        managed_device._initialized = True
        
        # Mock the update method
        async def mock_update():
            pass
        mock_device.update = mock_update
        
        # Try to control non-existent outlet
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(managed_device.control_outlet(5, 'on'))
        finally:
            loop.close()
        
        # Verify result
        self.assertFalse(result['success'])
        self.assertIn('out of range', result['error'])


if __name__ == '__main__':
    unittest.main()

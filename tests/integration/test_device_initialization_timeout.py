#!/usr/bin/env python3
"""
Test device initialization timeout handling and error reporting.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.devices.device_group_manager import ManagedDevice, DeviceGroup, DeviceGroupManager
from src.devices.device_controller import DeviceControllerError


class TestDeviceInitializationTimeout(unittest.TestCase):
    """Test device initialization timeout handling."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_config = {
            'name': 'test_device',
            'ip_address': '192.168.1.100',
            'outlets': [0, 1]
        }
        self.username = 'test_user@example.com'
        self.password = 'test_password'
    
    def test_default_timeout_is_30_seconds(self):
        """Test that default timeout is 30 seconds."""
        device = ManagedDevice(self.test_config, self.username, self.password)
        self.assertEqual(device.discovery_timeout, 30)
    
    def test_custom_timeout_from_config(self):
        """Test that custom timeout can be set from config."""
        config = self.test_config.copy()
        config['discovery_timeout_seconds'] = 60
        device = ManagedDevice(config, self.username, self.password)
        self.assertEqual(device.discovery_timeout, 60)
    
    def test_initialization_error_is_tracked(self):
        """Test that initialization errors are tracked on the device."""
        device = ManagedDevice(self.test_config, self.username, self.password)
        
        # Initially no error
        self.assertIsNone(device._initialization_error)
        
        # Simulate initialization failure
        device._initialization_error = "Timeout after 30s"
        
        # Verify error is tracked
        self.assertEqual(device._initialization_error, "Timeout after 30s")
        self.assertFalse(device._initialized)
    
    @patch('device_group_manager.Discover')
    async def test_timeout_error_handling(self, mock_discover):
        """Test that timeout errors are properly handled and logged."""
        # Mock discover_single to simulate timeout
        mock_discover.discover_single = AsyncMock(side_effect=asyncio.TimeoutError())
        
        device = ManagedDevice(self.test_config, self.username, self.password)
        
        with self.assertRaises(DeviceControllerError) as context:
            await device.initialize()
        
        # Verify error message includes timeout duration
        error_msg = str(context.exception)
        self.assertIn("Timeout after", error_msg)
        self.assertIn("30s", error_msg)
        self.assertIn("192.168.1.100", error_msg)
        
        # Verify device tracks the error
        self.assertIsNotNone(device._initialization_error)
        self.assertFalse(device._initialized)
    
    @patch('device_group_manager.Discover')
    async def test_successful_initialization_clears_error(self, mock_discover):
        """Test that successful initialization clears any previous error."""
        # Create a mock device
        mock_device = Mock()
        mock_device.model = 'EP40M'
        mock_device.alias = 'Test Device'
        mock_device.is_on = False
        mock_device.children = []
        mock_device.update = AsyncMock()
        
        # Mock discover_single to return the device
        mock_discover.discover_single = AsyncMock(return_value=mock_device)
        
        device = ManagedDevice(self.test_config, self.username, self.password)
        
        # Set an error first
        device._initialization_error = "Previous error"
        
        # Initialize successfully
        await device.initialize()
        
        # Verify error is cleared
        self.assertIsNone(device._initialization_error)
        self.assertTrue(device._initialized)
    
    async def test_get_detailed_status_includes_initialization_error(self):
        """Test that get_detailed_status includes initialization error."""
        device = ManagedDevice(self.test_config, self.username, self.password)
        device._initialization_error = "Timeout after 30s"
        
        status = await device.get_detailed_status()
        
        # Verify status includes error info
        self.assertFalse(status['initialized'])
        self.assertEqual(status['initialization_error'], "Timeout after 30s")
        self.assertIsNotNone(status['error'])
        self.assertIn("not initialized", status['error'])
        self.assertFalse(status['reachable'])
    
    async def test_device_group_tracks_failed_devices(self):
        """Test that DeviceGroup tracks devices that fail to initialize."""
        group_config = {
            'enabled': True,
            'items': [
                {
                    'name': 'device1',
                    'ip_address': '192.168.1.100',
                    'outlets': [0]
                },
                {
                    'name': 'device2',
                    'ip_address': '192.168.1.101',
                    'outlets': [0]
                }
            ]
        }
        
        group = DeviceGroup('test_group', group_config, self.username, self.password)
        
        # Mock initialization to fail for both devices
        with patch('device_group_manager.Discover') as mock_discover:
            mock_discover.discover_single = AsyncMock(side_effect=asyncio.TimeoutError())
            await group.initialize()
        
        # Verify group tracked the failures
        self.assertEqual(group._configured_device_count, 2)
        self.assertEqual(len(group.devices), 0)
        self.assertEqual(len(group._failed_devices), 2)
        
        # Check failed device details
        self.assertEqual(group._failed_devices[0]['name'], 'device1')
        self.assertEqual(group._failed_devices[0]['ip_address'], '192.168.1.100')
        self.assertIn('Timeout', group._failed_devices[0]['error'])
    
    async def test_device_group_initialization_info(self):
        """Test that DeviceGroup provides initialization info."""
        group_config = {
            'enabled': True,
            'items': [
                {'name': 'device1', 'ip_address': '192.168.1.100', 'outlets': [0]}
            ]
        }
        
        group = DeviceGroup('test_group', group_config, self.username, self.password)
        
        with patch('device_group_manager.Discover') as mock_discover:
            mock_discover.discover_single = AsyncMock(side_effect=asyncio.TimeoutError())
            await group.initialize()
        
        info = group.get_initialization_info()
        
        # Verify initialization info structure
        self.assertEqual(info['group_name'], 'test_group')
        self.assertEqual(info['configured_count'], 1)
        self.assertEqual(info['initialized_count'], 0)
        self.assertEqual(info['failed_count'], 1)
        self.assertTrue(info['initialization_complete'])
        self.assertEqual(len(info['failed_devices']), 1)
    
    async def test_device_group_manager_initialization_summary(self):
        """Test that DeviceGroupManager provides initialization summary."""
        devices_config = {
            'credentials': {
                'username': self.username,
                'password': self.password
            },
            'groups': {
                'group1': {
                    'enabled': True,
                    'items': [
                        {'name': 'device1', 'ip_address': '192.168.1.100', 'outlets': [0]},
                        {'name': 'device2', 'ip_address': '192.168.1.101', 'outlets': [0]}
                    ]
                },
                'group2': {
                    'enabled': True,
                    'items': [
                        {'name': 'device3', 'ip_address': '192.168.1.102', 'outlets': [0]}
                    ]
                }
            }
        }
        
        manager = DeviceGroupManager(devices_config)
        
        # Mock all devices to fail
        with patch('device_group_manager.Discover') as mock_discover:
            mock_discover.discover_single = AsyncMock(side_effect=asyncio.TimeoutError())
            await manager.initialize()
        
        summary = manager.get_initialization_summary()
        
        # Verify overall summary
        self.assertEqual(summary['total_groups'], 2)
        self.assertEqual(summary['overall']['configured_devices'], 3)
        self.assertEqual(summary['overall']['initialized_devices'], 0)
        self.assertEqual(summary['overall']['failed_devices'], 3)
        
        # Verify per-group info
        self.assertIn('group1', summary['groups'])
        self.assertIn('group2', summary['groups'])
        self.assertEqual(summary['groups']['group1']['configured_count'], 2)
        self.assertEqual(summary['groups']['group2']['configured_count'], 1)


def run_async_test(coro):
    """Helper to run async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Make async tests work with unittest
for name in dir(TestDeviceInitializationTimeout):
    if name.startswith('test_') and asyncio.iscoroutinefunction(getattr(TestDeviceInitializationTimeout, name)):
        test_method = getattr(TestDeviceInitializationTimeout, name)
        setattr(
            TestDeviceInitializationTimeout,
            name,
            lambda self, method=test_method: run_async_test(method(self))
        )


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Integration test for device status retrieval.

This test verifies that get_all_devices_status() correctly returns
all configured and initialized devices, addressing the issue where
the API was returning an empty device list.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent))

from src.devices.device_group_manager import DeviceGroupManager, DeviceGroup, ManagedDevice


class TestDeviceStatusIntegration(unittest.TestCase):
    """Integration tests for device status retrieval."""
    
    def test_get_all_devices_status_after_initialization(self):
        """
        Test that get_all_devices_status returns devices after manager initialization.
        
        This test reproduces the scenario from the issue:
        - Create a DeviceGroupManager with a configured device group
        - Initialize the manager (simulating what happens in scheduler.run())
        - Call get_all_devices_status() and verify it returns devices
        
        This addresses the bug where two separate scheduler instances were created,
        and the web server was referencing an uninitialized instance.
        """
        
        # Create a devices config with a single group and device
        devices_config = {
            'credentials': {
                'username': 'test@example.com',
                'password': 'testpassword'
            },
            'groups': {
                'heattrax': {
                    'enabled': True,
                    'automation': {
                        'weather_control': True,
                        'precipitation_control': True,
                        'morning_mode': True
                    },
                    'items': [
                        {
                            'name': 'kitchen',
                            'ip_address': '10.0.50.74',
                            'outlets': [0, 1]
                        }
                    ]
                }
            }
        }
        
        # Mock ManagedDevice.initialize to avoid network calls
        original_init = ManagedDevice.initialize
        
        async def mock_initialize(self):
            """Mock initialize that simulates successful device init."""
            # Create a mock device with children (outlets)
            self.device = Mock()
            self.device.model = 'EP40M'
            self.device.alias = 'Kitchen Device'
            self.device.children = [Mock(), Mock()]
            
            # Configure mock outlets
            self.device.children[0].is_on = True
            self.device.children[0].alias = 'Outlet 0'
            self.device.children[1].is_on = False
            self.device.children[1].alias = 'Outlet 1'
            
            # Mock update method
            async def mock_update():
                pass
            self.device.update = mock_update
            
            self._initialized = True
        
        ManagedDevice.initialize = mock_initialize
        
        try:
            # Run the async test
            async def run_test():
                # Create and initialize the manager
                manager = DeviceGroupManager(devices_config)
                await manager.initialize()
                
                # Verify the manager was initialized
                self.assertEqual(len(manager.groups), 1, "Manager should have 1 group")
                self.assertIn('heattrax', manager.groups, "Group 'heattrax' should exist")
                
                # Verify the group has devices
                group = manager.groups['heattrax']
                self.assertEqual(len(group.devices), 1, "Group should have 1 device")
                self.assertEqual(group.devices[0].name, 'kitchen', "Device name should be 'kitchen'")
                
                # Get all devices status
                devices_status = await manager.get_all_devices_status()
                
                # Verify we got device status
                self.assertEqual(len(devices_status), 1, 
                               "Should return status for 1 device")
                
                # Verify device status structure
                device_status = devices_status[0]
                self.assertEqual(device_status['name'], 'kitchen', 
                               "Device name should match")
                self.assertEqual(device_status['ip_address'], '10.0.50.74', 
                               "IP address should match")
                self.assertEqual(device_status['group'], 'heattrax', 
                               "Group name should be included")
                self.assertTrue(device_status['reachable'], 
                              "Device should be reachable after successful init")
                self.assertTrue(device_status['has_outlets'], 
                              "Device should have outlets")
                self.assertEqual(len(device_status['outlets']), 2, 
                               "Device should have 2 outlets")
                
                # Verify outlet information
                self.assertEqual(device_status['outlets'][0]['index'], 0)
                self.assertTrue(device_status['outlets'][0]['is_on'])
                self.assertEqual(device_status['outlets'][1]['index'], 1)
                self.assertFalse(device_status['outlets'][1]['is_on'])
            
            # Run the async test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_test())
            finally:
                loop.close()
        
        finally:
            # Restore original method
            ManagedDevice.initialize = original_init
    
    def test_get_all_devices_status_multiple_groups(self):
        """
        Test get_all_devices_status with multiple groups.
        
        Verifies that devices from all enabled groups are returned.
        """
        
        devices_config = {
            'credentials': {
                'username': 'test@example.com',
                'password': 'testpassword'
            },
            'groups': {
                'group1': {
                    'enabled': True,
                    'items': [
                        {'name': 'device1', 'ip_address': '10.0.0.1'}
                    ]
                },
                'group2': {
                    'enabled': True,
                    'items': [
                        {'name': 'device2', 'ip_address': '10.0.0.2'},
                        {'name': 'device3', 'ip_address': '10.0.0.3'}
                    ]
                },
                'group3': {
                    'enabled': False,  # Disabled group
                    'items': [
                        {'name': 'device4', 'ip_address': '10.0.0.4'}
                    ]
                }
            }
        }
        
        # Mock ManagedDevice.initialize
        original_init = ManagedDevice.initialize
        
        async def mock_initialize(self):
            self.device = Mock()
            self.device.is_on = False
            self.device.alias = f"{self.name} Device"
            self.device.children = None
            
            async def mock_update():
                pass
            self.device.update = mock_update
            
            self._initialized = True
        
        ManagedDevice.initialize = mock_initialize
        
        try:
            async def run_test():
                manager = DeviceGroupManager(devices_config)
                await manager.initialize()
                
                # Should have 2 enabled groups
                self.assertEqual(len(manager.groups), 2)
                
                # Get all devices status
                devices_status = await manager.get_all_devices_status()
                
                # Should return 3 devices (group1: 1, group2: 2, group3: 0 (disabled))
                self.assertEqual(len(devices_status), 3)
                
                # Verify device names and groups
                device_names = {d['name'] for d in devices_status}
                self.assertEqual(device_names, {'device1', 'device2', 'device3'})
                
                # Verify groups are correctly assigned
                group1_devices = [d for d in devices_status if d['group'] == 'group1']
                group2_devices = [d for d in devices_status if d['group'] == 'group2']
                
                self.assertEqual(len(group1_devices), 1)
                self.assertEqual(len(group2_devices), 2)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_test())
            finally:
                loop.close()
        
        finally:
            ManagedDevice.initialize = original_init
    
    def test_get_all_devices_status_empty_when_uninitialized(self):
        """
        Test that get_all_devices_status returns empty list when manager is not initialized.
        
        This test demonstrates the bug that was occurring: when the DeviceGroupManager
        is not initialized, it has no groups and returns an empty list.
        """
        
        devices_config = {
            'credentials': {
                'username': 'test@example.com',
                'password': 'testpassword'
            },
            'groups': {
                'heattrax': {
                    'enabled': True,
                    'items': [
                        {'name': 'kitchen', 'ip_address': '10.0.50.74'}
                    ]
                }
            }
        }
        
        async def run_test():
            # Create manager but DO NOT initialize it
            manager = DeviceGroupManager(devices_config)
            
            # The manager should have no groups yet
            self.assertEqual(len(manager.groups), 0, 
                           "Uninitialized manager should have no groups")
            
            # Get all devices status without initialization
            devices_status = await manager.get_all_devices_status()
            
            # Should return empty list (this was the bug!)
            self.assertEqual(len(devices_status), 0,
                           "Uninitialized manager should return empty device list")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_test())
        finally:
            loop.close()


if __name__ == '__main__':
    unittest.main()

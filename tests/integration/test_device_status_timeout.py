#!/usr/bin/env python3
"""
Integration test for device status timeout handling.
Tests that get_detailed_status() properly handles slow/unresponsive devices with timeout.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.devices.device_group_manager import DeviceGroupManager, ManagedDevice


class TestDeviceStatusTimeout(unittest.TestCase):
    """Integration tests for device status timeout handling."""
    
    def test_get_detailed_status_with_timeout(self):
        """
        Test that get_detailed_status handles slow device.update() with timeout.
        
        This test verifies:
        - Slow device.update() calls are caught by timeout
        - Timeout results in reachable=False and appropriate error message
        - The method returns gracefully without hanging
        """
        
        # Create a device config
        device_config = {
            'name': 'slow_device',
            'ip_address': '10.0.50.100',
            'outlets': [0, 1]
        }
        
        # Mock ManagedDevice.initialize to avoid network calls
        original_init = ManagedDevice.initialize
        
        async def mock_initialize(self):
            """Mock initialize that simulates successful device init."""
            # Create a mock device
            self.device = Mock()
            self.device.model = 'EP40M'
            self.device.alias = 'Slow Device'
            
            # Mock update method that hangs (simulating slow network)
            async def slow_update():
                await asyncio.sleep(20)  # Sleep longer than timeout
            
            self.device.update = slow_update
            self._initialized = True
        
        ManagedDevice.initialize = mock_initialize
        
        try:
            # Run the async test
            async def run_test():
                # Create a managed device
                managed_device = ManagedDevice(
                    config=device_config,
                    username='test@example.com',
                    password='testpassword'
                )
                
                # Initialize the device
                await managed_device.initialize()
                
                # Get detailed status (should timeout)
                status = await managed_device.get_detailed_status()
                
                # Verify timeout was handled properly
                self.assertFalse(status['reachable'], 
                               "Device should not be reachable after timeout")
                self.assertIsNotNone(status['error'], 
                                    "Error message should be set after timeout")
                self.assertIn('Timeout', status['error'], 
                             "Error message should mention timeout")
                self.assertIn('10s', status['error'], 
                             "Error message should mention timeout duration")
                self.assertEqual(status['name'], 'slow_device')
                self.assertEqual(status['ip_address'], '10.0.50.100')
            
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
    
    def test_get_detailed_status_success_within_timeout(self):
        """
        Test that get_detailed_status succeeds when device responds within timeout.
        
        This test verifies:
        - Fast device.update() calls complete successfully
        - Device state is properly returned
        - Timeout doesn't interfere with normal operation
        """
        
        # Create a device config
        device_config = {
            'name': 'fast_device',
            'ip_address': '10.0.50.101',
            'outlets': [0]
        }
        
        # Mock ManagedDevice.initialize
        original_init = ManagedDevice.initialize
        
        async def mock_initialize(self):
            """Mock initialize with fast device."""
            # Create a mock device with children (outlets)
            self.device = Mock()
            self.device.model = 'EP40M'
            self.device.alias = 'Fast Device'
            self.device.children = [Mock()]
            
            # Configure mock outlet
            self.device.children[0].is_on = True
            self.device.children[0].alias = 'Outlet 0'
            
            # Mock update method that completes quickly
            async def fast_update():
                await asyncio.sleep(0.1)  # Quick response
            
            self.device.update = fast_update
            self._initialized = True
        
        ManagedDevice.initialize = mock_initialize
        
        try:
            # Run the async test
            async def run_test():
                # Create a managed device
                managed_device = ManagedDevice(
                    config=device_config,
                    username='test@example.com',
                    password='testpassword'
                )
                
                # Initialize the device
                await managed_device.initialize()
                
                # Get detailed status (should succeed)
                status = await managed_device.get_detailed_status()
                
                # Verify status was retrieved successfully
                self.assertTrue(status['reachable'], 
                              "Device should be reachable")
                self.assertIsNone(status.get('error'), 
                                "No error should be set")
                self.assertTrue(status['has_outlets'], 
                              "Device should have outlets")
                self.assertEqual(len(status['outlets']), 1)
                self.assertTrue(status['outlets'][0]['is_on'])
                self.assertEqual(status['name'], 'fast_device')
                self.assertEqual(status['model'], 'EP40M')
            
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
    
    def test_get_all_devices_status_with_mixed_responses(self):
        """
        Test that get_all_devices_status returns partial results.
        
        This test verifies:
        - Some devices timeout while others succeed
        - All device statuses are returned (both working and failed)
        - The method doesn't fail completely due to one slow device
        """
        
        # Create a devices config with two devices
        devices_config = {
            'credentials': {
                'username': 'test@example.com',
                'password': 'testpassword'
            },
            'groups': {
                'mixed_group': {
                    'enabled': True,
                    'items': [
                        {
                            'name': 'fast_device',
                            'ip_address': '10.0.50.101',
                            'outlets': [0]
                        },
                        {
                            'name': 'slow_device',
                            'ip_address': '10.0.50.102',
                            'outlets': [0]
                        }
                    ]
                }
            }
        }
        
        # Mock ManagedDevice.initialize
        original_init = ManagedDevice.initialize
        
        async def mock_initialize(self):
            """Mock initialize with different behaviors based on device name."""
            self.device = Mock()
            self.device.model = 'EP40M'
            self.device.alias = self.name
            self.device.children = [Mock()]
            self.device.children[0].is_on = True
            self.device.children[0].alias = 'Outlet 0'
            
            # Fast device responds quickly, slow device hangs
            if self.name == 'fast_device':
                async def fast_update():
                    await asyncio.sleep(0.1)
                self.device.update = fast_update
            else:
                async def slow_update():
                    await asyncio.sleep(20)
                self.device.update = slow_update
            
            self._initialized = True
        
        ManagedDevice.initialize = mock_initialize
        
        try:
            # Run the async test
            async def run_test():
                # Create and initialize the manager
                manager = DeviceGroupManager(devices_config)
                await manager.initialize()
                
                # Get all devices status
                devices_status = await manager.get_all_devices_status()
                
                # Verify we got status for both devices
                self.assertEqual(len(devices_status), 2, 
                               "Should return status for both devices")
                
                # Find each device in results
                fast_device_status = next(
                    (d for d in devices_status if d['name'] == 'fast_device'), 
                    None
                )
                slow_device_status = next(
                    (d for d in devices_status if d['name'] == 'slow_device'), 
                    None
                )
                
                # Verify fast device succeeded
                self.assertIsNotNone(fast_device_status)
                self.assertTrue(fast_device_status['reachable'], 
                              "Fast device should be reachable")
                self.assertIsNone(fast_device_status.get('error'))
                
                # Verify slow device timed out but still returned status
                self.assertIsNotNone(slow_device_status)
                self.assertFalse(slow_device_status['reachable'], 
                               "Slow device should not be reachable")
                self.assertIsNotNone(slow_device_status['error'])
                self.assertIn('Timeout', slow_device_status['error'])
            
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


if __name__ == '__main__':
    unittest.main()
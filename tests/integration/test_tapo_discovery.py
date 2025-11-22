#!/usr/bin/env python3
"""Tests for Tapo-authenticated discovery in device controllers."""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.devices.device_controller import TapoController, DeviceControllerError
from src.devices.device_group_manager import ManagedDevice


class TestTapoControllerDiscovery(unittest.TestCase):
    """Test TapoController uses Discover.discover_single for Tapo authentication."""
    
    def test_initialize_with_valid_credentials(self):
        """Test that TapoController.initialize calls Discover.discover_single with credentials."""
        async def run_test():
            # Create mock device
            mock_device = Mock()
            mock_device.model = "EP40M"
            mock_device.alias = "Test Device"
            mock_device.children = []
            mock_device.is_on = False
            
            # Mock the update method
            async def mock_update():
                pass
            mock_device.update = mock_update
            
            with patch('device_controller.Discover.discover_single', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = mock_device
                
                # Create controller
                controller = TapoController(
                    ip_address="10.0.50.74",
                    username="test_user@example.com",
                    password="test_password"
                )
                
                # Initialize
                await controller.initialize()
                
                # Verify Discover.discover_single was called with correct parameters
                mock_discover.assert_called_once_with(
                    "10.0.50.74",
                    username="test_user@example.com",
                    password="test_password"
                )
                
                # Verify controller is initialized
                self.assertTrue(controller._initialized)
                self.assertEqual(controller.device, mock_device)
        
        asyncio.run(run_test())
    
    def test_initialize_missing_username(self):
        """Test that initialize raises DeviceControllerError when username is missing."""
        async def run_test():
            controller = TapoController(
                ip_address="10.0.50.74",
                username="",
                password="test_password"
            )
            
            with self.assertRaises(DeviceControllerError) as context:
                await controller.initialize()
            
            self.assertIn("HEATTRAX_TAPO_USERNAME", str(context.exception))
            self.assertIn("HEATTRAX_TAPO_PASSWORD", str(context.exception))
        
        asyncio.run(run_test())
    
    def test_initialize_missing_password(self):
        """Test that initialize raises DeviceControllerError when password is missing."""
        async def run_test():
            controller = TapoController(
                ip_address="10.0.50.74",
                username="test_user@example.com",
                password=""
            )
            
            with self.assertRaises(DeviceControllerError) as context:
                await controller.initialize()
            
            self.assertIn("HEATTRAX_TAPO_USERNAME", str(context.exception))
            self.assertIn("HEATTRAX_TAPO_PASSWORD", str(context.exception))
        
        asyncio.run(run_test())
    
    def test_initialize_missing_ip_address(self):
        """Test that initialize raises DeviceControllerError when IP is missing."""
        async def run_test():
            controller = TapoController(
                ip_address="",
                username="test_user@example.com",
                password="test_password"
            )
            
            with self.assertRaises(DeviceControllerError) as context:
                await controller.initialize()
            
            self.assertIn("IP address cannot be empty", str(context.exception))
        
        asyncio.run(run_test())
    
    def test_initialize_logs_device_info(self):
        """Test that initialize logs device model, alias, and children count."""
        async def run_test():
            # Create mock device with children (outlets)
            mock_device = Mock()
            mock_device.model = "EP40M"
            mock_device.alias = "Test Outlet Strip"
            mock_device.children = [Mock(), Mock()]  # 2 outlets
            mock_device.hw_info = {"hw_ver": "1.0"}
            
            # Mock the update method
            async def mock_update():
                pass
            mock_device.update = mock_update
            
            with patch('device_controller.Discover.discover_single', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = mock_device
                
                controller = TapoController(
                    ip_address="10.0.50.74",
                    username="test_user@example.com",
                    password="test_password"
                )
                
                # Initialize - this should log device info
                with patch('device_controller.logger') as mock_logger:
                    await controller.initialize()
                    
                    # Verify logging includes device information
                    info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                    debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
                    
                    # Check that device info was logged
                    self.assertTrue(any("model=EP40M" in str(call) for call in info_calls))
                    self.assertTrue(any("alias=Test Outlet Strip" in str(call) for call in info_calls))
                    self.assertTrue(any("outlets=2" in str(call) for call in info_calls))
        
        asyncio.run(run_test())


class TestManagedDeviceDiscovery(unittest.TestCase):
    """Test ManagedDevice uses Discover.discover_single for Tapo authentication."""
    
    def test_initialize_with_valid_credentials(self):
        """Test that ManagedDevice.initialize calls Discover.discover_single with credentials."""
        async def run_test():
            # Create mock device
            mock_device = Mock()
            mock_device.model = "EP40M"
            mock_device.alias = "Test Device"
            mock_device.children = []
            
            # Mock the update method
            async def mock_update():
                pass
            mock_device.update = mock_update
            
            with patch('device_group_manager.Discover.discover_single', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = mock_device
                
                # Create managed device
                device = ManagedDevice(
                    config={
                        'name': 'Test Mat',
                        'ip_address': '10.0.50.74',
                        'outlets': [0, 1]
                    },
                    username="test_user@example.com",
                    password="test_password"
                )
                
                # Initialize
                await device.initialize()
                
                # Verify Discover.discover_single was called with correct parameters
                mock_discover.assert_called_once_with(
                    "10.0.50.74",
                    username="test_user@example.com",
                    password="test_password"
                )
                
                # Verify device is initialized
                self.assertTrue(device._initialized)
                self.assertEqual(device.device, mock_device)
        
        asyncio.run(run_test())
    
    def test_initialize_missing_credentials(self):
        """Test that initialize raises DeviceControllerError when credentials are missing."""
        async def run_test():
            device = ManagedDevice(
                config={
                    'name': 'Test Mat',
                    'ip_address': '10.0.50.74'
                },
                username="",
                password=""
            )
            
            with self.assertRaises(DeviceControllerError) as context:
                await device.initialize()
            
            self.assertIn("Missing Tapo credentials", str(context.exception))
            self.assertIn("HEATTRAX_TAPO_USERNAME", str(context.exception))
            self.assertIn("HEATTRAX_TAPO_PASSWORD", str(context.exception))
        
        asyncio.run(run_test())
    
    def test_initialize_missing_ip_address(self):
        """Test that ManagedDevice raises error when IP is missing in config."""
        with self.assertRaises(DeviceControllerError) as context:
            device = ManagedDevice(
                config={
                    'name': 'Test Mat'
                    # No ip_address
                },
                username="test_user@example.com",
                password="test_password"
            )
        
        self.assertIn("IP address is required", str(context.exception))
    
    def test_initialize_with_outlets(self):
        """Test that device with outlets (children) is initialized correctly."""
        async def run_test():
            # Create mock device with children
            mock_child1 = Mock()
            mock_child1.is_on = False
            mock_child2 = Mock()
            mock_child2.is_on = False
            
            mock_device = Mock()
            mock_device.model = "EP40M"
            mock_device.alias = "Test Outlet Strip"
            mock_device.children = [mock_child1, mock_child2]
            
            # Mock the update method
            async def mock_update():
                pass
            mock_device.update = mock_update
            
            with patch('device_group_manager.Discover.discover_single', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = mock_device
                
                device = ManagedDevice(
                    config={
                        'name': 'Test Mat',
                        'ip_address': '10.0.50.74',
                        'outlets': [0, 1]
                    },
                    username="test_user@example.com",
                    password="test_password"
                )
                
                await device.initialize()
                
                # Verify device has outlets configured
                self.assertEqual(device.outlets, [0, 1])
                self.assertEqual(len(device.device.children), 2)
        
        asyncio.run(run_test())


class TestTapoAuthenticationErrors(unittest.TestCase):
    """Test error handling for Tapo authentication failures."""
    
    def test_connection_error(self):
        """Test handling of connection errors during discovery."""
        async def run_test():
            with patch('device_controller.Discover.discover_single', new_callable=AsyncMock) as mock_discover:
                mock_discover.side_effect = ConnectionError("Unable to connect to device")
                
                controller = TapoController(
                    ip_address="10.0.50.74",
                    username="test_user@example.com",
                    password="test_password"
                )
                
                with self.assertRaises(DeviceControllerError) as context:
                    await controller.initialize()
                
                self.assertIn("Failed to connect to device", str(context.exception))
        
        asyncio.run(run_test())
    
    def test_timeout_error(self):
        """Test handling of timeout errors during discovery."""
        async def run_test():
            with patch('device_controller.Discover.discover_single', new_callable=AsyncMock) as mock_discover:
                mock_discover.side_effect = TimeoutError("Connection timeout")
                
                controller = TapoController(
                    ip_address="10.0.50.74",
                    username="test_user@example.com",
                    password="test_password"
                )
                
                with self.assertRaises(DeviceControllerError) as context:
                    await controller.initialize()
                
                self.assertIn("Connection timeout", str(context.exception))
        
        asyncio.run(run_test())
    
    def test_authentication_error(self):
        """Test handling of authentication errors (invalid credentials)."""
        async def run_test():
            with patch('device_controller.Discover.discover_single', new_callable=AsyncMock) as mock_discover:
                # Simulate authentication failure
                mock_discover.side_effect = Exception("Invalid credentials")
                
                controller = TapoController(
                    ip_address="10.0.50.74",
                    username="wrong_user@example.com",
                    password="wrong_password"
                )
                
                with self.assertRaises(DeviceControllerError) as context:
                    await controller.initialize()
                
                self.assertIn("Failed to initialize device", str(context.exception))
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()

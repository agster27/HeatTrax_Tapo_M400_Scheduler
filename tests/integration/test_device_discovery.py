#!/usr/bin/env python3
"""Tests for device discovery module."""

import unittest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.devices.device_discovery import DeviceInfo, discover_devices, run_device_discovery_and_diagnostics


class TestDeviceInfo(unittest.TestCase):
    """Test DeviceInfo class."""
    
    def test_device_info_creation(self):
        """Test creating DeviceInfo from mock device."""
        # Create mock device
        mock_device = Mock()
        mock_device.host = "192.168.1.100"
        mock_device.alias = "Test Device"
        mock_device.model = "Tapo P110"
        mock_device.mac = "AA:BB:CC:DD:EE:FF"
        mock_device.is_on = True
        mock_device.rssi = -45
        mock_device.features = ["energy_monitoring"]
        mock_device.hw_version = "1.0"
        mock_device.sw_version = "1.2.3"
        
        # Create DeviceInfo
        device_info = DeviceInfo(mock_device)
        
        # Verify properties
        self.assertEqual(device_info.ip, "192.168.1.100")
        self.assertEqual(device_info.alias, "Test Device")
        self.assertEqual(device_info.model, "Tapo P110")
        self.assertEqual(device_info.mac, "AA:BB:CC:DD:EE:FF")
        self.assertTrue(device_info.is_on)
        self.assertEqual(device_info.rssi, -45)
        self.assertEqual(device_info.features, ["energy_monitoring"])
    
    def test_device_info_to_dict(self):
        """Test converting DeviceInfo to dictionary."""
        mock_device = Mock()
        mock_device.host = "192.168.1.100"
        mock_device.alias = "Test Device"
        mock_device.model = "Tapo P110"
        mock_device.mac = "AA:BB:CC:DD:EE:FF"
        mock_device.is_on = True
        mock_device.rssi = -45
        mock_device.features = []
        mock_device.hw_version = "1.0"
        mock_device.sw_version = "1.2.3"
        
        device_info = DeviceInfo(mock_device)
        device_dict = device_info.to_dict()
        
        self.assertEqual(device_dict['ip'], "192.168.1.100")
        self.assertEqual(device_dict['alias'], "Test Device")
        self.assertEqual(device_dict['state'], "ON")
    
    def test_device_info_string_representation(self):
        """Test string representation of DeviceInfo."""
        mock_device = Mock()
        mock_device.host = "192.168.1.100"
        mock_device.alias = "Test Device"
        mock_device.model = "Tapo P110"
        mock_device.mac = "AA:BB:CC:DD:EE:FF"
        mock_device.is_on = False
        mock_device.rssi = None
        mock_device.features = []
        mock_device.hw_version = "1.0"
        mock_device.sw_version = "1.2.3"
        
        device_info = DeviceInfo(mock_device)
        device_str = str(device_info)
        
        self.assertIn("Test Device", device_str)
        self.assertIn("192.168.1.100", device_str)
        self.assertIn("OFF", device_str)


class TestDeviceDiscovery(unittest.TestCase):
    """Test device discovery functions."""
    
    def test_discover_devices_no_devices(self):
        """Test discovery when no devices found."""
        async def run_test():
            with patch('device_discovery.Discover.discover', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = {}
                
                devices = await discover_devices(timeout=1)
                
                self.assertEqual(len(devices), 0)
                mock_discover.assert_called_once()
        
        asyncio.run(run_test())
    
    def test_discover_devices_with_devices(self):
        """Test discovery with devices found."""
        async def run_test():
            # Create mock device
            mock_device = Mock()
            mock_device.host = "192.168.1.100"
            mock_device.alias = "Test Device"
            mock_device.model = "Tapo P110"
            mock_device.mac = "AA:BB:CC:DD:EE:FF"
            mock_device.is_on = True
            mock_device.rssi = -45
            mock_device.features = []
            mock_device.hw_version = "1.0"
            mock_device.sw_version = "1.2.3"
            mock_device.update = AsyncMock()
            
            mock_devices = {"192.168.1.100": mock_device}
            
            with patch('device_discovery.Discover.discover', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = mock_devices
                
                devices = await discover_devices(timeout=1)
                
                self.assertEqual(len(devices), 1)
                self.assertEqual(devices[0].ip, "192.168.1.100")
                self.assertEqual(devices[0].alias, "Test Device")
                mock_device.update.assert_called_once()
        
        asyncio.run(run_test())
    
    def test_discover_devices_with_exception(self):
        """Test discovery when exception occurs."""
        async def run_test():
            with patch('device_discovery.Discover.discover', new_callable=AsyncMock) as mock_discover:
                mock_discover.side_effect = Exception("Discovery failed")
                
                devices = await discover_devices(timeout=1)
                
                self.assertEqual(len(devices), 0)
        
        asyncio.run(run_test())
    
    def test_run_device_discovery_no_configured_ip(self):
        """Test running discovery without configured IP."""
        async def run_test():
            # Mock single device
            mock_device = Mock()
            mock_device.host = "192.168.1.100"
            mock_device.alias = "Test Device"
            mock_device.model = "Tapo P110"
            mock_device.mac = "AA:BB:CC:DD:EE:FF"
            mock_device.is_on = True
            mock_device.features = []
            mock_device.hw_version = "1.0"
            mock_device.sw_version = "1.2.3"
            mock_device.update = AsyncMock()
            
            with patch('device_discovery.discover_devices', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = [DeviceInfo(mock_device)]
                
                result = await run_device_discovery_and_diagnostics(configured_ip=None)
                
                self.assertIsNotNone(result)
                self.assertEqual(result.ip, "192.168.1.100")
        
        asyncio.run(run_test())
    
    def test_run_device_discovery_with_matching_ip(self):
        """Test running discovery with matching configured IP."""
        async def run_test():
            # Mock device
            mock_device = Mock()
            mock_device.host = "192.168.1.100"
            mock_device.alias = "Test Device"
            mock_device.model = "Tapo P110"
            mock_device.mac = "AA:BB:CC:DD:EE:FF"
            mock_device.is_on = True
            mock_device.features = []
            mock_device.hw_version = "1.0"
            mock_device.sw_version = "1.2.3"
            mock_device.update = AsyncMock()
            
            with patch('device_discovery.discover_devices', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = [DeviceInfo(mock_device)]
                
                result = await run_device_discovery_and_diagnostics(
                    configured_ip="192.168.1.100",
                    connection_successful=True
                )
                
                self.assertIsNotNone(result)
                self.assertEqual(result.ip, "192.168.1.100")
        
        asyncio.run(run_test())
    
    def test_run_device_discovery_ip_not_found_connection_failed(self):
        """Test discovery when configured IP not found and connection failed."""
        async def run_test():
            # Mock device at different IP
            mock_device = Mock()
            mock_device.host = "192.168.1.101"
            mock_device.alias = "Alternative Device"
            mock_device.model = "Tapo P110"
            mock_device.mac = "AA:BB:CC:DD:EE:FF"
            mock_device.is_on = True
            mock_device.features = []
            mock_device.hw_version = "1.0"
            mock_device.sw_version = "1.2.3"
            mock_device.update = AsyncMock()
            
            with patch('device_discovery.discover_devices', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = [DeviceInfo(mock_device)]
                
                # Configured IP is 192.168.1.100, but only 192.168.1.101 found
                result = await run_device_discovery_and_diagnostics(
                    configured_ip="192.168.1.100",
                    connection_successful=False
                )
                
                # Should suggest the alternative device
                self.assertIsNotNone(result)
                self.assertEqual(result.ip, "192.168.1.101")
        
        asyncio.run(run_test())
    
    def test_run_device_discovery_ip_not_found_connection_succeeded(self):
        """Test discovery when configured IP not found but connection succeeded."""
        async def run_test():
            # Mock device at different IP
            mock_device = Mock()
            mock_device.host = "192.168.1.101"
            mock_device.alias = "Other Device"
            mock_device.model = "Tapo P110"
            mock_device.mac = "BB:BB:CC:DD:EE:FF"
            mock_device.is_on = True
            mock_device.features = []
            mock_device.hw_version = "1.0"
            mock_device.sw_version = "1.2.3"
            mock_device.update = AsyncMock()
            
            with patch('device_discovery.discover_devices', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = [DeviceInfo(mock_device)]
                
                # Connection succeeded to 192.168.1.100 but only 192.168.1.101 discovered
                result = await run_device_discovery_and_diagnostics(
                    configured_ip="192.168.1.100",
                    connection_successful=True
                )
                
                # Should not return a device since connection succeeded to configured IP
                # but it wasn't discovered (might be blocking broadcast)
                self.assertIsNone(result)
        
        asyncio.run(run_test())
    
    def test_run_device_discovery_multiple_devices_no_config(self):
        """Test discovery with multiple devices and no configured IP."""
        async def run_test():
            # Mock two devices
            mock_device1 = Mock()
            mock_device1.host = "192.168.1.100"
            mock_device1.alias = "Device 1"
            mock_device1.model = "Tapo P110"
            mock_device1.mac = "AA:BB:CC:DD:EE:FF"
            mock_device1.is_on = True
            mock_device1.features = []
            mock_device1.hw_version = "1.0"
            mock_device1.sw_version = "1.2.3"
            mock_device1.update = AsyncMock()
            
            mock_device2 = Mock()
            mock_device2.host = "192.168.1.101"
            mock_device2.alias = "Device 2"
            mock_device2.model = "Tapo P110"
            mock_device2.mac = "BB:BB:CC:DD:EE:FF"
            mock_device2.is_on = False
            mock_device2.features = []
            mock_device2.hw_version = "1.0"
            mock_device2.sw_version = "1.2.3"
            mock_device2.update = AsyncMock()
            
            with patch('device_discovery.discover_devices', new_callable=AsyncMock) as mock_discover:
                mock_discover.return_value = [DeviceInfo(mock_device1), DeviceInfo(mock_device2)]
                
                result = await run_device_discovery_and_diagnostics(configured_ip=None)
                
                # Should return None when multiple devices and no config
                self.assertIsNone(result)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()

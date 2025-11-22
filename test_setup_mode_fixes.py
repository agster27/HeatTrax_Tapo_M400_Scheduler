"""Test that setup mode handles device_manager being None gracefully."""

import unittest
import tempfile
import yaml
import os
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from config_loader import Config
from scheduler_enhanced import EnhancedScheduler


class TestSetupModeFixes(unittest.TestCase):
    """Test cases for setup mode AttributeError fixes."""
    
    def setUp(self):
        """Create a temporary config file for each test."""
        self.temp_file = None
    
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
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            self.temp_file = f.name
        
        return self.temp_file
    
    def test_get_device_expectations_in_setup_mode(self):
        """Test that get_device_expectations returns empty list in setup mode."""
        config_path = self._create_config('', '')
        config = Config(config_path)
        
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Verify setup mode is active
        self.assertTrue(scheduler.setup_mode)
        self.assertIsNone(scheduler.device_manager)
        
        # Test that get_device_expectations doesn't crash
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            expectations = loop.run_until_complete(scheduler.get_device_expectations())
            self.assertEqual(expectations, [], "Should return empty list in setup mode")
        finally:
            loop.close()
    
    def test_run_cycle_multi_device_in_setup_mode(self):
        """Test that run_cycle_multi_device returns early in setup mode."""
        config_path = self._create_config('', '')
        config = Config(config_path)
        
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Verify setup mode is active
        self.assertTrue(scheduler.setup_mode)
        self.assertIsNone(scheduler.device_manager)
        
        # Test that run_cycle_multi_device doesn't crash
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Should not raise AttributeError
            loop.run_until_complete(scheduler.run_cycle_multi_device())
        finally:
            loop.close()
    
    def test_normal_mode_with_valid_credentials(self):
        """Test that operations work normally with valid credentials (mocked)."""
        config_path = self._create_config('user@example.com', 'ValidPassword123!')
        config = Config(config_path)
        
        # Mock DeviceGroupManager to avoid actual device connections
        with patch('scheduler_enhanced.DeviceGroupManager') as mock_dgm:
            mock_instance = MagicMock()
            mock_instance.get_all_groups.return_value = []
            mock_dgm.return_value = mock_instance
            
            scheduler = EnhancedScheduler(config)
            
            # Verify normal mode is active
            self.assertFalse(scheduler.setup_mode)
            self.assertIsNotNone(scheduler.device_manager)
            
            # Test that get_device_expectations works (returns empty list since no groups)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                expectations = loop.run_until_complete(scheduler.get_device_expectations())
                self.assertEqual(expectations, [], "Should return empty list with no groups")
            finally:
                loop.close()


if __name__ == '__main__':
    unittest.main()

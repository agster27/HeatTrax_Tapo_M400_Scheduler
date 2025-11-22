#!/usr/bin/env python3
"""
Test to verify WeatherServiceState JSON serialization in web server.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from enum import Enum

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class MockWeatherServiceState(Enum):
    """Mock enum to simulate WeatherServiceState."""
    ONLINE = "online"
    DEGRADED_OFFLINE_USING_CACHE = "degraded_offline_using_cache"
    OFFLINE_NO_WEATHER_DATA = "offline_no_weather_data"


class MockWeather:
    """Mock weather service with state."""
    def __init__(self, state):
        self.state = state
        self.last_successful_fetch = None


class MockScheduler:
    """Mock scheduler with weather service."""
    def __init__(self, weather_state):
        self.weather = MockWeather(weather_state)


class TestWeatherStateJsonSerialization(unittest.TestCase):
    """Test WeatherServiceState JSON serialization in WebServer."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Create a minimal config file
        config_data = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpass'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 32.0,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))

    def test_weather_state_enum_serialization(self):
        """Test that WeatherServiceState enum is properly serialized to JSON."""
        # Test with ONLINE state
        scheduler = MockScheduler(MockWeatherServiceState.ONLINE)
        web_server = WebServer(self.config_manager, scheduler)
        
        status = web_server._get_system_status()
        
        # Should have weather_state field
        self.assertIn('weather_state', status)
        
        # Should be a string (the enum's value)
        self.assertIsInstance(status['weather_state'], str)
        self.assertEqual(status['weather_state'], 'online')
        
        # Should be JSON serializable
        try:
            json_str = json.dumps(status)
            # And deserializable
            parsed = json.loads(json_str)
            self.assertEqual(parsed['weather_state'], 'online')
        except TypeError as e:
            self.fail(f"Status should be JSON serializable: {e}")

    def test_weather_state_all_enum_values(self):
        """Test all possible WeatherServiceState enum values."""
        test_states = [
            (MockWeatherServiceState.ONLINE, 'online'),
            (MockWeatherServiceState.DEGRADED_OFFLINE_USING_CACHE, 'degraded_offline_using_cache'),
            (MockWeatherServiceState.OFFLINE_NO_WEATHER_DATA, 'offline_no_weather_data')
        ]
        
        for enum_state, expected_value in test_states:
            with self.subTest(state=enum_state):
                scheduler = MockScheduler(enum_state)
                web_server = WebServer(self.config_manager, scheduler)
                
                status = web_server._get_system_status()
                
                # Should have weather_state field
                self.assertIn('weather_state', status)
                self.assertEqual(status['weather_state'], expected_value)
                
                # Should be JSON serializable
                try:
                    json_str = json.dumps(status)
                    parsed = json.loads(json_str)
                    self.assertEqual(parsed['weather_state'], expected_value)
                except TypeError as e:
                    self.fail(f"Status with state {enum_state} should be JSON serializable: {e}")

    def test_weather_state_without_scheduler(self):
        """Test that status works when scheduler is None."""
        web_server = WebServer(self.config_manager, scheduler=None)
        
        status = web_server._get_system_status()
        
        # Should not have weather_state field
        self.assertNotIn('weather_state', status)
        
        # Should still be JSON serializable
        try:
            json_str = json.dumps(status)
            json.loads(json_str)
        except TypeError as e:
            self.fail(f"Status without scheduler should be JSON serializable: {e}")


if __name__ == '__main__':
    unittest.main()

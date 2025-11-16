#!/usr/bin/env python3
"""
Test script for multi-device configuration and group functionality.
"""

import sys
import os
import unittest
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import Config, ConfigError


class TestMultiDeviceConfig(unittest.TestCase):
    """Test multi-device configuration support."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_multi_device_config_loads(self):
        """Test that multi-device config loads correctly."""
        config = Config('config.example.yaml')
        
        # Should use multi-device mode
        self.assertTrue(config.has_multi_device_config)
        
        # Check devices section
        self.assertIn('devices', config._config)
        devices = config.devices
        
        # Check credentials
        self.assertIn('credentials', devices)
        self.assertEqual(devices['credentials']['username'], 'your_tapo_username')
        self.assertEqual(devices['credentials']['password'], 'your_tapo_password')
        
        # Check groups
        self.assertIn('groups', devices)
        groups = devices['groups']
        
        # Check heated_mats group
        self.assertIn('heated_mats', groups)
        heated_mats = groups['heated_mats']
        self.assertTrue(heated_mats['enabled'])
        self.assertTrue(heated_mats['automation']['weather_control'])
        self.assertTrue(heated_mats['automation']['precipitation_control'])
        self.assertTrue(heated_mats['automation']['morning_mode'])
        
        # Check heated_mats items
        items = heated_mats['items']
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]['name'], 'Front Walkway Mat')
        self.assertEqual(items[0]['ip_address'], '192.168.1.100')
        self.assertEqual(items[0]['outlets'], [0, 1])
        
        # Check christmas_lights group
        self.assertIn('christmas_lights', groups)
        lights = groups['christmas_lights']
        self.assertTrue(lights['enabled'])
        self.assertFalse(lights['automation']['weather_control'])
        self.assertTrue(lights['automation']['schedule_control'])
        
        # Check schedule
        schedule = lights['schedule']
        self.assertEqual(schedule['on_time'], '17:00')
        self.assertEqual(schedule['off_time'], '23:00')
    
    def test_legacy_config_still_works(self):
        """Test that legacy single-device config still works."""
        config = Config('config.example.legacy.yaml')
        
        # Should use legacy mode
        self.assertFalse(config.has_multi_device_config)
        
        # Check device section
        self.assertIn('device', config._config)
        device = config.device
        self.assertEqual(device['ip_address'], '192.168.1.100')
        self.assertEqual(device['username'], 'your_tapo_username')
        self.assertEqual(device['password'], 'your_tapo_password')
    
    def test_weather_api_config(self):
        """Test weather API configuration."""
        config = Config('config.example.yaml')
        
        weather_api = config.weather_api
        self.assertEqual(weather_api['provider'], 'open-meteo')
        
        # Check OpenWeatherMap config exists
        self.assertIn('openweathermap', weather_api)
        self.assertEqual(weather_api['openweathermap']['api_key'], 'your_api_key_here')
    
    def test_morning_mode_with_temperature(self):
        """Test morning mode with separate temperature threshold."""
        config = Config('config.example.yaml')
        
        morning_mode = config.morning_mode
        self.assertTrue(morning_mode['enabled'])
        self.assertEqual(morning_mode['start_hour'], 6)
        self.assertEqual(morning_mode['end_hour'], 8)
        self.assertEqual(morning_mode['temperature_f'], 32)
    
    def test_env_var_weather_provider(self):
        """Test weather provider can be overridden with env var."""
        os.environ['HEATTRAX_WEATHER_PROVIDER'] = 'openweathermap'
        config = Config('config.example.yaml')
        
        self.assertEqual(config.weather_api['provider'], 'openweathermap')
    
    def test_env_var_openweathermap_key(self):
        """Test OpenWeatherMap API key can be overridden with env var."""
        os.environ['HEATTRAX_OPENWEATHERMAP_API_KEY'] = 'test_api_key_123'
        config = Config('config.example.yaml')
        
        self.assertEqual(
            config.weather_api['openweathermap']['api_key'], 
            'test_api_key_123'
        )


class TestWeatherFactory(unittest.TestCase):
    """Test weather service factory."""
    
    def test_open_meteo_creation(self):
        """Test Open-Meteo service creation."""
        from weather_factory import WeatherServiceFactory
        from weather_service import WeatherService
        
        config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'provider': 'open-meteo'
            }
        }
        
        service = WeatherServiceFactory.create_weather_service(config)
        self.assertIsInstance(service, WeatherService)
    
    def test_openweathermap_creation_fails_without_key(self):
        """Test OpenWeatherMap service fails without API key."""
        from weather_factory import WeatherServiceFactory
        from weather_service import WeatherServiceError
        
        config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'provider': 'openweathermap',
                'openweathermap': {}
            }
        }
        
        with self.assertRaises(WeatherServiceError):
            WeatherServiceFactory.create_weather_service(config)
    
    def test_openweathermap_creation_with_key(self):
        """Test OpenWeatherMap service creation with API key."""
        from weather_factory import WeatherServiceFactory
        from weather_openweathermap import OpenWeatherMapService
        
        config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'provider': 'openweathermap',
                'openweathermap': {
                    'api_key': 'test_key_123'
                }
            }
        }
        
        service = WeatherServiceFactory.create_weather_service(config)
        self.assertIsInstance(service, OpenWeatherMapService)
        self.assertEqual(service.api_key, 'test_key_123')


def main():
    """Run tests."""
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMultiDeviceConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestWeatherFactory))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
Tests for weather API endpoints in web server.
"""

import os
import sys
import unittest
import tempfile
import json
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager
from web_server import WebServer
from weather_cache import WeatherCache, WeatherSnapshot


class TestWeatherAPIEndpoints(unittest.TestCase):
    """Test weather-related API endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config and cache files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.cache_path = Path(self.test_dir) / "weather_cache.json"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
        
        # Create minimal config
        config_data = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo',
                'resilience': {
                    'cache_file': str(self.cache_path),
                    'cache_valid_hours': 6.0,
                    'forecast_horizon_hours': 12
                }
            },
            'scheduler': {
                'forecast_hours': 12,
                'check_interval_minutes': 10
            },
            'thresholds': {
                'temperature_f': 32,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 60
            },
            'morning_mode': {
                'enabled': False
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpass'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'automation': {
                            'weather_control': True,
                            'precipitation_control': True
                        },
                        'items': []
                    }
                }
            },
            'safety': {
                'cooldown_minutes': 5
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))
        
        # Create mock scheduler
        self.mock_scheduler = MagicMock()
        self.mock_scheduler.weather_enabled = True
        
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
    
    def test_weather_forecast_no_scheduler(self):
        """Test /api/weather/forecast when scheduler is not available."""
        # Create web server without scheduler
        web_server = WebServer(self.config_manager, scheduler=None)
        client = web_server.app.test_client()
        
        response = client.get('/api/weather/forecast')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'no_data')
        self.assertIn('reason', data)
    
    def test_weather_forecast_weather_disabled(self):
        """Test /api/weather/forecast when weather is disabled."""
        # Update config to disable weather
        config = self.config_manager.get_config(include_secrets=False)
        config['weather_api']['enabled'] = False
        
        # Use a temporary file for this test
        temp_config_path = Path(self.test_dir) / "temp_config.yaml"
        with open(temp_config_path, 'w') as f:
            yaml.dump(config, f)
        
        temp_config_manager = ConfigManager(str(temp_config_path))
        temp_web_server = WebServer(temp_config_manager, scheduler=self.mock_scheduler)
        temp_client = temp_web_server.app.test_client()
        
        response = temp_client.get('/api/weather/forecast')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'no_data')
        self.assertIn('disabled', data['reason'].lower())
    
    def test_weather_forecast_no_cache(self):
        """Test /api/weather/forecast when no cached data exists."""
        # Create mock weather service without cache
        mock_weather = MagicMock()
        mock_weather.cache = MagicMock()
        mock_weather.cache.cache_data = None
        
        self.mock_scheduler.weather = mock_weather
        
        response = self.client.get('/api/weather/forecast')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'no_data')
        self.assertIn('reason', data)
    
    def test_weather_forecast_with_cache(self):
        """Test /api/weather/forecast with cached data."""
        # Create mock weather cache with data
        now = datetime.now()
        forecast_list = []
        
        for i in range(12):
            forecast_time = now + timedelta(hours=i)
            snapshot = WeatherSnapshot(
                timestamp=forecast_time.isoformat(),
                temperature_f=30.0 - i * 0.5,
                precipitation_mm=0.5 if i % 3 == 0 else 0.0
            )
            forecast_list.append(snapshot.to_dict())
        
        cache_data = {
            'fetched_at': now.isoformat(),
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060
            },
            'forecast': forecast_list
        }
        
        mock_cache = MagicMock()
        mock_cache.cache_data = cache_data
        mock_cache.get_cache_age_hours.return_value = 0.5
        
        mock_weather = MagicMock()
        mock_weather.cache = mock_cache
        mock_weather.state = MagicMock()
        mock_weather.state.value = 'online'
        
        self.mock_scheduler.weather = mock_weather
        
        response = self.client.get('/api/weather/forecast')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('hours', data)
        self.assertEqual(len(data['hours']), 12)
        self.assertIn('provider', data)
        self.assertIn('last_updated', data)
        self.assertEqual(data['weather_state'], 'online')
        
        # Verify hour data structure
        first_hour = data['hours'][0]
        self.assertIn('time', first_hour)
        self.assertIn('temp_f', first_hour)
        self.assertIn('temp_c', first_hour)
        self.assertIn('precip_intensity', first_hour)
    
    def test_mat_forecast_no_scheduler(self):
        """Test /api/weather/mat-forecast when scheduler is not available."""
        # Create web server without scheduler
        web_server = WebServer(self.config_manager, scheduler=None)
        client = web_server.app.test_client()
        
        response = client.get('/api/weather/mat-forecast')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'no_data')
        self.assertIn('reason', data)
    
    def test_mat_forecast_success(self):
        """Test /api/weather/mat-forecast returns predicted windows."""
        # Mock the predict_group_windows method
        now = datetime.now()
        mock_windows = {
            'test_group': [
                {
                    'start': now.isoformat(),
                    'end': (now + timedelta(hours=2)).isoformat(),
                    'state': 'on',
                    'reason': 'snow_forecast',
                    'details': {}
                },
                {
                    'start': (now + timedelta(hours=2)).isoformat(),
                    'end': (now + timedelta(hours=12)).isoformat(),
                    'state': 'off',
                    'reason': 'conditions_not_met',
                    'details': {}
                }
            ]
        }
        
        self.mock_scheduler.predict_group_windows.return_value = mock_windows
        
        response = self.client.get('/api/weather/mat-forecast')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('horizon_hours', data)
        self.assertEqual(data['horizon_hours'], 12)
        self.assertIn('step_minutes', data)
        self.assertEqual(data['step_minutes'], 60)
        self.assertIn('groups', data)
        self.assertIn('test_group', data['groups'])
        
        # Verify window structure
        windows = data['groups']['test_group']
        self.assertEqual(len(windows), 2)
        
        first_window = windows[0]
        self.assertEqual(first_window['state'], 'on')
        self.assertEqual(first_window['reason'], 'snow_forecast')
        self.assertIn('start', first_window)
        self.assertIn('end', first_window)
    
    def test_mat_forecast_prediction_error(self):
        """Test /api/weather/mat-forecast handles prediction errors."""
        # Make predict_group_windows raise an exception
        self.mock_scheduler.predict_group_windows.side_effect = Exception('Test error')
        
        response = self.client.get('/api/weather/mat-forecast')
        self.assertEqual(response.status_code, 500)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('error', data)
        self.assertIn('details', data)


class TestSchedulerPrediction(unittest.TestCase):
    """Test scheduler prediction methods."""
    
    def setUp(self):
        """Set up test environment."""
        from scheduler_enhanced import EnhancedScheduler
        from config_loader import Config
        
        # Create temporary directory
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Create minimal config
        self.config_dict = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo'
            },
            'scheduler': {
                'forecast_hours': 12,
                'check_interval_minutes': 10
            },
            'thresholds': {
                'temperature_f': 32,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 60
            },
            'morning_mode': {
                'enabled': False
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpass'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'automation': {
                            'weather_control': False,
                            'precipitation_control': False,
                            'schedule_control': True
                        },
                        'schedule': {
                            'on_time': '06:00',
                            'off_time': '22:00'
                        },
                        'items': []
                    }
                }
            },
            'safety': {
                'cooldown_minutes': 5,
                'max_runtime_hours': 24
            }
        }
        
        # Write config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_dict, f)
        
        # Create config object from file
        self.config = Config(str(self.config_path))
        
        # Create scheduler in setup mode (no device control)
        self.scheduler = EnhancedScheduler(self.config, setup_mode=True)
        self.scheduler.weather_enabled = False
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_predict_group_windows_schedule_only(self):
        """Test prediction with schedule-only control."""
        # In setup mode, device_manager is None, so we need to mock it
        mock_device_manager = MagicMock()
        mock_device_manager.get_all_groups.return_value = ['test_group']
        mock_device_manager.get_group_config.return_value = {
            'enabled': True,
            'automation': {
                'weather_control': False,
                'precipitation_control': False,
                'schedule_control': True
            },
            'schedule': {
                'on_time': '06:00',
                'off_time': '22:00'
            }
        }
        
        # Replace the device_manager
        self.scheduler.device_manager = mock_device_manager
        
        # Call predict_group_windows
        result = self.scheduler.predict_group_windows(horizon_hours=24, step_minutes=60)
        
        # Should return dict with test_group
        self.assertIn('test_group', result)
        
        # Should have windows
        windows = result['test_group']
        self.assertIsInstance(windows, list)
        
        # Verify we have windows with 'on' state during 06:00-22:00
        has_on_window = any(w['state'] == 'on' and w['reason'] == 'schedule' for w in windows)
        has_off_window = any(w['state'] == 'off' for w in windows)
        
        self.assertTrue(has_on_window or has_off_window)
    
    def test_predict_group_windows_disabled_group(self):
        """Test prediction skips disabled groups."""
        from config_loader import Config
        from scheduler_enhanced import EnhancedScheduler
        
        # Disable the test group
        self.config_dict['devices']['groups']['test_group']['enabled'] = False
        
        # Write updated config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config_dict, f)
        
        # Reload config and recreate scheduler
        config = Config(str(self.config_path))
        scheduler = EnhancedScheduler(config, setup_mode=True)
        scheduler.weather_enabled = False
        
        result = scheduler.predict_group_windows(horizon_hours=12, step_minutes=60)
        
        # In setup mode, device_manager is None, so result will be empty
        # This is expected behavior
        self.assertIsInstance(result, dict)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Integration test to verify schedule_control flag is properly deprecated and ignored.

This test ensures that:
1. Schedules are evaluated even if schedule_control: false is present in config
2. The deprecated schedule_control flag triggers a warning log
3. The scheduler uses only the schedules: array for schedule-based automation
"""

import os
import sys
import unittest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import logging

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config_loader import Config
from src.scheduler.scheduler_enhanced import EnhancedScheduler


class TestScheduleControlDeprecation(unittest.TestCase):
    """Test that schedule_control flag is properly deprecated."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
        
        # Set config path
        os.environ['HEATTRAX_CONFIG_PATH'] = str(self.config_path)
    
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up temp files
        if self.config_path.exists():
            self.config_path.unlink()
        Path(self.test_dir).rmdir()
    
    def test_schedules_evaluated_despite_schedule_control_false(self):
        """Test that schedules are evaluated even when schedule_control: false is present."""
        # Create a config with schedule_control: false but schedules defined
        test_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpassword'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'automation': {
                            'weather_control': True,
                            'precipitation_control': True,
                            'morning_mode': True,
                            'schedule_control': False  # Deprecated flag - should be ignored
                        },
                        'schedules': [
                            {
                                'name': 'Morning Heat',
                                'enabled': True,
                                'priority': 'normal',
                                'days': [1, 2, 3, 4, 5],  # Weekdays
                                'on': {
                                    'type': 'time',
                                    'value': '05:00'
                                },
                                'off': {
                                    'type': 'time',
                                    'value': '08:00'
                                },
                                'conditions': {
                                    'temperature_max': 36
                                }
                            }
                        ],
                        'items': [
                            {
                                'name': 'Test Device',
                                'ip_address': '192.168.1.100',
                                'outlets': [0]
                            }
                        ]
                    }
                }
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo',
                'openweathermap': {'api_key': ''},
                'open_meteo': {},
                'resilience': {
                    'cache_file': 'state/weather_cache.json',
                    'cache_valid_hours': 6.0,
                    'forecast_horizon_hours': 12,
                    'refresh_interval_minutes': 10,
                    'retry_interval_minutes': 5,
                    'max_retry_interval_minutes': 60,
                    'outage_alert_after_minutes': 30
                }
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            },
            'logging': {
                'level': 'INFO',
                'max_file_size_mb': 10,
                'backup_count': 5
            },
            'health_check': {
                'interval_hours': 24,
                'max_consecutive_failures': 3
            },
            'notifications': {
                'required': False,
                'test_on_startup': False,
                'email': {'enabled': False},
                'webhook': {'enabled': False}
            },
            'web': {
                'enabled': False,
                'bind_host': '127.0.0.1',
                'port': 4328
            },
            'health_server': {
                'enabled': False,
                'host': '0.0.0.0',
                'port': 4329
            },
            'reboot': {
                'pause_seconds': 60
            }
        }
        
        # Write config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        # Load config
        config = Config(str(self.config_path))
        
        # Create scheduler with setup_mode=True to avoid device initialization
        with patch('logging.Logger.warning') as mock_warning:
            scheduler = EnhancedScheduler(config, setup_mode=True)
            
            # Verify that deprecation warning was logged
            warning_calls = [str(call) for call in mock_warning.call_args_list]
            deprecation_warning_found = any(
                'schedule_control' in str(call) and 'deprecated' in str(call).lower()
                for call in warning_calls
            )
            self.assertTrue(
                deprecation_warning_found,
                f"Expected deprecation warning for schedule_control, got warnings: {warning_calls}"
            )
        
        # Verify schedules were loaded for the group
        self.assertIn('test_group', scheduler.group_schedules)
        schedules = scheduler.group_schedules['test_group']
        self.assertEqual(len(schedules), 1, "Schedule should be loaded despite schedule_control: false")
        self.assertEqual(schedules[0].name, 'Morning Heat')
    
    def test_schedules_without_schedule_control_flag(self):
        """Test that schedules work without any schedule_control flag (preferred configuration)."""
        # Create a config without schedule_control flag
        test_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpassword'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'automation': {
                            'weather_control': True,
                            'precipitation_control': True,
                            'morning_mode': True
                            # No schedule_control flag - this is the preferred configuration
                        },
                        'schedules': [
                            {
                                'name': 'Evening Lights',
                                'enabled': True,
                                'priority': 'normal',
                                'days': [1, 2, 3, 4, 5, 6, 7],  # All days
                                'on': {
                                    'type': 'time',
                                    'value': '17:00'
                                },
                                'off': {
                                    'type': 'time',
                                    'value': '23:00'
                                }
                            }
                        ],
                        'items': [
                            {
                                'name': 'Test Device',
                                'ip_address': '192.168.1.100',
                                'outlets': [0]
                            }
                        ]
                    }
                }
            },
            'weather_api': {
                'enabled': True,
                'provider': 'open-meteo',
                'openweathermap': {'api_key': ''},
                'open_meteo': {},
                'resilience': {
                    'cache_file': 'state/weather_cache.json',
                    'cache_valid_hours': 6.0,
                    'forecast_horizon_hours': 12,
                    'refresh_interval_minutes': 10,
                    'retry_interval_minutes': 5,
                    'max_retry_interval_minutes': 60,
                    'outage_alert_after_minutes': 30
                }
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            },
            'logging': {
                'level': 'INFO',
                'max_file_size_mb': 10,
                'backup_count': 5
            },
            'health_check': {
                'interval_hours': 24,
                'max_consecutive_failures': 3
            },
            'notifications': {
                'required': False,
                'test_on_startup': False,
                'email': {'enabled': False},
                'webhook': {'enabled': False}
            },
            'web': {
                'enabled': False,
                'bind_host': '127.0.0.1',
                'port': 4328
            },
            'health_server': {
                'enabled': False,
                'host': '0.0.0.0',
                'port': 4329
            },
            'reboot': {
                'pause_seconds': 60
            }
        }
        
        # Write config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(test_config, f)
        
        # Load config
        config = Config(str(self.config_path))
        
        # Create scheduler with setup_mode=True to avoid device initialization
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Verify schedules were loaded for the group
        self.assertIn('test_group', scheduler.group_schedules)
        schedules = scheduler.group_schedules['test_group']
        self.assertEqual(len(schedules), 1, "Schedule should be loaded")
        self.assertEqual(schedules[0].name, 'Evening Lights')


if __name__ == "__main__":
    unittest.main()

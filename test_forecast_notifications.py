#!/usr/bin/env python3
"""Tests for forecast notifier and weather state change enhancements."""

import unittest
import asyncio
import json
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from forecast_notifier import ForecastNotifier
from resilient_weather_service import ResilientWeatherService, WeatherServiceState


class TestForecastNotifier(unittest.TestCase):
    """Test ForecastNotifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / "forecast_state.json"
        self.mock_notification_service = Mock()
        self.mock_notification_service.is_enabled.return_value = True
        self.mock_notification_service.notify = AsyncMock()
    
    def test_notifier_initialization_always_mode(self):
        """Test notifier initialization in 'always' mode."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            notify_mode="always",
            state_file=str(self.state_file)
        )
        
        self.assertEqual(notifier.notify_mode, "always")
        self.assertEqual(notifier.temp_change_threshold_f, 5.0)
        self.assertIsNone(notifier.last_forecast_hash)
    
    def test_notifier_initialization_on_change_mode(self):
        """Test notifier initialization in 'on_change' mode."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            notify_mode="on_change",
            temp_change_threshold_f=10.0,
            precip_change_threshold_mm=5.0,
            state_file=str(self.state_file)
        )
        
        self.assertEqual(notifier.notify_mode, "on_change")
        self.assertEqual(notifier.temp_change_threshold_f, 10.0)
        self.assertEqual(notifier.precip_change_threshold_mm, 5.0)
    
    def test_format_forecast_summary_basic(self):
        """Test basic forecast summary formatting."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            state_file=str(self.state_file)
        )
        
        now = datetime.now()
        forecast_data = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 32.0,
                'feels_like_f': 28.0,
                'precipitation_mm': 2.5,
                'precipitation_probability': 80,
                'wind_speed_mph': 10.0,
                'condition_text': 'Light Snow'
            },
            {
                'timestamp': (now + timedelta(hours=2)).isoformat(),
                'temperature_f': 30.0,
                'feels_like_f': 25.0,
                'precipitation_mm': 5.0,
                'precipitation_probability': 90,
                'wind_speed_mph': 12.0,
                'condition_text': 'Snow'
            }
        ]
        
        summary = notifier.format_forecast_summary(
            forecast_data=forecast_data,
            temperature_threshold_f=34.0,
            planned_actions=["Turn on heated mats at 10:00 AM"],
            hours_to_show=12
        )
        
        # Verify summary contains key elements
        self.assertIn("WEATHER FORECAST SUMMARY", summary)
        self.assertIn("Temperature threshold: 34.0°F", summary)
        self.assertIn("Light Snow", summary)
        self.assertIn("Snow", summary)
        self.assertIn("Turn on heated mats at 10:00 AM", summary)
        self.assertIn("***", summary)  # Marker for precip + low temp
    
    def test_format_forecast_summary_no_actions(self):
        """Test forecast summary with no planned actions."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            state_file=str(self.state_file)
        )
        
        now = datetime.now()
        forecast_data = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 40.0,
                'feels_like_f': 38.0,
                'precipitation_mm': 0.0,
                'precipitation_probability': 0,
                'wind_speed_mph': 5.0,
                'condition_text': 'Clear'
            }
        ]
        
        summary = notifier.format_forecast_summary(
            forecast_data=forecast_data,
            temperature_threshold_f=34.0,
            planned_actions=None,
            hours_to_show=12
        )
        
        self.assertIn("No specific actions planned", summary)
        # Check that no data rows have the *** marker (only the legend has it)
        lines = summary.split('\n')
        data_rows = [line for line in lines if '°F' in line and 'mph' in line]
        for row in data_rows:
            # If temp is above threshold or no precip, should not have marker
            if '40.0°F' in row:
                self.assertNotIn('*** ', row)  # Space after *** to distinguish from legend
    
    def test_compute_forecast_hash(self):
        """Test forecast hash computation."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            state_file=str(self.state_file)
        )
        
        now = datetime.now()
        forecast_data = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 32.5,
                'precipitation_mm': 2.3,
                'precipitation_probability': 80
            },
            {
                'timestamp': (now + timedelta(hours=2)).isoformat(),
                'temperature_f': 30.1,
                'precipitation_mm': 5.8,
                'precipitation_probability': 90
            }
        ]
        
        hash1 = notifier._compute_forecast_hash(forecast_data)
        self.assertTrue(len(hash1) > 0)
        
        # Same forecast should produce same hash
        hash2 = notifier._compute_forecast_hash(forecast_data)
        self.assertEqual(hash1, hash2)
        
        # Different forecast should produce different hash
        forecast_data[0]['temperature_f'] = 35.0
        hash3 = notifier._compute_forecast_hash(forecast_data)
        self.assertNotEqual(hash1, hash3)
    
    def test_detect_meaningful_change_first_forecast(self):
        """Test change detection for first forecast (no previous)."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            state_file=str(self.state_file)
        )
        
        now = datetime.now()
        forecast_data = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 32.0,
                'precipitation_mm': 2.0,
                'precipitation_probability': 80
            }
        ]
        
        current_hash = notifier._compute_forecast_hash(forecast_data)
        has_changed = notifier._detect_meaningful_change(forecast_data, current_hash)
        
        self.assertTrue(has_changed)  # First forecast is always a change
    
    def test_detect_meaningful_change_same_forecast(self):
        """Test change detection with unchanged forecast."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            state_file=str(self.state_file)
        )
        
        now = datetime.now()
        forecast_data = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 32.0,
                'precipitation_mm': 2.0,
                'precipitation_probability': 80
            }
        ]
        
        # First call
        hash1 = notifier._compute_forecast_hash(forecast_data)
        notifier.last_forecast_hash = hash1
        
        # Second call with same data
        hash2 = notifier._compute_forecast_hash(forecast_data)
        has_changed = notifier._detect_meaningful_change(forecast_data, hash2)
        
        self.assertFalse(has_changed)  # Should detect no change
    
    def test_detect_meaningful_change_different_forecast(self):
        """Test change detection with changed forecast."""
        notifier = ForecastNotifier(
            notification_service=self.mock_notification_service,
            state_file=str(self.state_file)
        )
        
        now = datetime.now()
        forecast_data1 = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 32.0,
                'precipitation_mm': 2.0,
                'precipitation_probability': 80
            }
        ]
        
        # First call
        hash1 = notifier._compute_forecast_hash(forecast_data1)
        notifier.last_forecast_hash = hash1
        
        # Second call with different data
        forecast_data2 = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 40.0,  # Changed temperature
                'precipitation_mm': 0.0,  # Changed precipitation
                'precipitation_probability': 0
            }
        ]
        
        hash2 = notifier._compute_forecast_hash(forecast_data2)
        has_changed = notifier._detect_meaningful_change(forecast_data2, hash2)
        
        self.assertTrue(has_changed)  # Should detect change
    
    def test_notify_always_mode(self):
        """Test notification in 'always' mode."""
        async def run_test():
            notifier = ForecastNotifier(
                notification_service=self.mock_notification_service,
                notify_mode="always",
                state_file=str(self.state_file)
            )
            
            now = datetime.now()
            forecast_data = [
                {
                    'timestamp': (now + timedelta(hours=1)).isoformat(),
                    'temperature_f': 32.0,
                    'precipitation_mm': 2.0,
                    'precipitation_probability': 80,
                    'feels_like_f': 28.0,
                    'wind_speed_mph': 10.0,
                    'condition_text': 'Snow'
                }
            ]
            
            # First notification
            result1 = await notifier.notify_new_forecast(
                forecast_data=forecast_data,
                temperature_threshold_f=34.0,
                planned_actions=None,
                hours_to_show=12
            )
            
            self.assertTrue(result1)
            self.assertEqual(self.mock_notification_service.notify.call_count, 1)
            
            # Second notification with same data (should still send in 'always' mode)
            result2 = await notifier.notify_new_forecast(
                forecast_data=forecast_data,
                temperature_threshold_f=34.0,
                planned_actions=None,
                hours_to_show=12
            )
            
            self.assertTrue(result2)
            self.assertEqual(self.mock_notification_service.notify.call_count, 2)
        
        asyncio.run(run_test())
    
    def test_notify_on_change_mode_no_change(self):
        """Test notification in 'on_change' mode with no change."""
        async def run_test():
            notifier = ForecastNotifier(
                notification_service=self.mock_notification_service,
                notify_mode="on_change",
                state_file=str(self.state_file)
            )
            
            now = datetime.now()
            forecast_data = [
                {
                    'timestamp': (now + timedelta(hours=1)).isoformat(),
                    'temperature_f': 32.0,
                    'precipitation_mm': 2.0,
                    'precipitation_probability': 80,
                    'feels_like_f': 28.0,
                    'wind_speed_mph': 10.0,
                    'condition_text': 'Snow'
                }
            ]
            
            # First notification (always sent - no previous)
            result1 = await notifier.notify_new_forecast(
                forecast_data=forecast_data,
                temperature_threshold_f=34.0,
                planned_actions=None,
                hours_to_show=12
            )
            
            self.assertTrue(result1)
            self.assertEqual(self.mock_notification_service.notify.call_count, 1)
            
            # Second notification with same data (should NOT send)
            result2 = await notifier.notify_new_forecast(
                forecast_data=forecast_data,
                temperature_threshold_f=34.0,
                planned_actions=None,
                hours_to_show=12
            )
            
            self.assertFalse(result2)
            self.assertEqual(self.mock_notification_service.notify.call_count, 1)
        
        asyncio.run(run_test())
    
    def test_notify_on_change_mode_with_change(self):
        """Test notification in 'on_change' mode with forecast change."""
        async def run_test():
            notifier = ForecastNotifier(
                notification_service=self.mock_notification_service,
                notify_mode="on_change",
                state_file=str(self.state_file)
            )
            
            now = datetime.now()
            forecast_data1 = [
                {
                    'timestamp': (now + timedelta(hours=1)).isoformat(),
                    'temperature_f': 32.0,
                    'precipitation_mm': 2.0,
                    'precipitation_probability': 80,
                    'feels_like_f': 28.0,
                    'wind_speed_mph': 10.0,
                    'condition_text': 'Snow'
                }
            ]
            
            # First notification
            result1 = await notifier.notify_new_forecast(
                forecast_data=forecast_data1,
                temperature_threshold_f=34.0,
                planned_actions=None,
                hours_to_show=12
            )
            
            self.assertTrue(result1)
            self.assertEqual(self.mock_notification_service.notify.call_count, 1)
            
            # Second notification with changed data (should send)
            forecast_data2 = [
                {
                    'timestamp': (now + timedelta(hours=1)).isoformat(),
                    'temperature_f': 40.0,  # Changed
                    'precipitation_mm': 0.0,  # Changed
                    'precipitation_probability': 0,
                    'feels_like_f': 38.0,
                    'wind_speed_mph': 5.0,
                    'condition_text': 'Clear'
                }
            ]
            
            result2 = await notifier.notify_new_forecast(
                forecast_data=forecast_data2,
                temperature_threshold_f=34.0,
                planned_actions=None,
                hours_to_show=12
            )
            
            self.assertTrue(result2)
            self.assertEqual(self.mock_notification_service.notify.call_count, 2)
        
        asyncio.run(run_test())
    
    def test_state_persistence(self):
        """Test that forecast state persists across instances."""
        async def run_test():
            # First instance
            notifier1 = ForecastNotifier(
                notification_service=self.mock_notification_service,
                notify_mode="on_change",
                state_file=str(self.state_file)
            )
            
            now = datetime.now()
            forecast_data = [
                {
                    'timestamp': (now + timedelta(hours=1)).isoformat(),
                    'temperature_f': 32.0,
                    'precipitation_mm': 2.0,
                    'precipitation_probability': 80,
                    'feels_like_f': 28.0,
                    'wind_speed_mph': 10.0,
                    'condition_text': 'Snow'
                }
            ]
            
            await notifier1.notify_new_forecast(
                forecast_data=forecast_data,
                temperature_threshold_f=34.0,
                planned_actions=None,
                hours_to_show=12
            )
            
            # Second instance (should load previous state)
            notifier2 = ForecastNotifier(
                notification_service=self.mock_notification_service,
                notify_mode="on_change",
                state_file=str(self.state_file)
            )
            
            self.assertIsNotNone(notifier2.last_forecast_hash)
            self.assertEqual(notifier2.last_forecast_hash, notifier1.last_forecast_hash)
        
        asyncio.run(run_test())


class TestWeatherStateChangeEnhancements(unittest.TestCase):
    """Test enhanced weather state change notification features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_weather_service = Mock()
        self.mock_weather_service.latitude = 40.7128
        self.mock_weather_service.longitude = -74.0060
        self.mock_notification_service = Mock()
        self.mock_notification_service.is_enabled.return_value = True
        self.mock_notification_service.notify = AsyncMock()
    
    def test_no_notification_on_initial_startup(self):
        """Test that state change notification is suppressed on initial startup."""
        from weather_cache import WeatherCache
        
        # Create a cache with valid data
        temp_dir = tempfile.mkdtemp()
        cache_file = Path(temp_dir) / "weather_cache.json"
        cache = WeatherCache(str(cache_file))
        
        now = datetime.now()
        forecast_data = [
            {
                'timestamp': (now + timedelta(hours=1)).isoformat(),
                'temperature_f': 32.0,
                'precipitation_mm': 0.0,
                'precipitation_probability': 0
            }
        ]
        
        cache.save_forecast(40.7128, -74.0060, forecast_data, 12)
        
        # Create resilient service (will start with DEGRADED state due to valid cache)
        resilient = ResilientWeatherService(
            weather_service=self.mock_weather_service,
            cache_file=str(cache_file),
            notification_service=self.mock_notification_service
        )
        
        # The _update_state should have been called during init, but no notification
        # should have been sent because previous_state is None (initial startup)
        self.assertIsNone(resilient.previous_state)
        self.mock_notification_service.notify.assert_not_called()
    
    def test_rate_limiting_prevents_spam(self):
        """Test that rate limiting state tracking works correctly."""
        # Create resilient service
        resilient = ResilientWeatherService(
            weather_service=self.mock_weather_service,
            notification_service=self.mock_notification_service
        )
        
        # Start with OFFLINE state and mark that we had a previous state
        # (so we're not in initial startup)
        resilient.state = WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        resilient.previous_state = WeatherServiceState.ONLINE  # Had been online before
        resilient.offline_since = datetime.now() - timedelta(hours=1)
        
        # Set up so first state change is allowed (no recent notification)
        resilient.last_state_change_notification_at = None
        
        # Simulate coming back online (first transition)
        resilient.offline_since = None  # Now online
        resilient._update_state()  # Should transition to ONLINE
        
        # Verify state changed
        self.assertEqual(resilient.state, WeatherServiceState.ONLINE)
        
        # Verify that notification timestamp was recorded
        self.assertIsNotNone(resilient.last_state_change_notification_at)
        first_notification_time = resilient.last_state_change_notification_at
        
        # Immediately go offline again (within rate limit - should be suppressed)
        resilient.offline_since = datetime.now()
        resilient._update_state()  # Should transition back to OFFLINE
        
        # Verify state changed
        self.assertEqual(resilient.state, WeatherServiceState.OFFLINE_NO_WEATHER_DATA)
        
        # Notification timestamp should not have changed (rate limited)
        self.assertEqual(
            resilient.last_state_change_notification_at,
            first_notification_time
        )


if __name__ == '__main__':
    unittest.main()

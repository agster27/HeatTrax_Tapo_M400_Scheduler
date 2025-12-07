#!/usr/bin/env python3
"""
Unit test for black ice risk detection.

Tests the black ice detection logic in weather services to ensure
proper identification of conditions that can lead to black ice formation.
"""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.weather.weather_service import WeatherService
from src.weather.weather_openweathermap import OpenWeatherMapService


class TestBlackIceDetection(unittest.TestCase):
    """Test black ice risk detection in weather services."""
    
    def setUp(self):
        """Set up test environment."""
        self.service = WeatherService(
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York"
        )
        
        self.owm_service = OpenWeatherMapService(
            api_key="test_key",
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York"
        )
    
    def _create_mock_forecast_response(self, temp_f, dewpoint_f, humidity_percent):
        """Create a mock forecast response with specified weather conditions."""
        # Create forecast data for 30 minutes from now to ensure it's in the future
        from datetime import timedelta
        future_time = datetime.now() + timedelta(minutes=30)
        # Format as ISO without timezone info (Open-Meteo format)
        time_str = future_time.strftime('%Y-%m-%dT%H:%M')
        
        return {
            'hourly': {
                'time': [time_str],
                'temperature_2m': [temp_f],
                'precipitation': [0.0],
                'dewpoint_2m': [dewpoint_f],
                'relative_humidity_2m': [humidity_percent]
            }
        }
    
    def test_black_ice_risk_detected_perfect_conditions(self):
        """Test that black ice risk is detected with ideal conditions."""
        # Temperature at 34°F, dewpoint at 32°F (2°F spread), humidity at 85%
        # These conditions should trigger black ice detection
        mock_data = self._create_mock_forecast_response(34.0, 32.0, 85.0)
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=36.0,
                dew_point_spread_f=4.0,
                humidity_min_percent=80.0
            ))
            
            risk_detected, risk_time, temp, dewpoint = result
            
            self.assertTrue(risk_detected, "Black ice risk should be detected")
            self.assertIsNotNone(risk_time, "Risk time should be set")
            self.assertEqual(temp, 34.0, "Temperature should match")
            self.assertEqual(dewpoint, 32.0, "Dewpoint should match")
    
    def test_black_ice_risk_not_detected_temp_too_high(self):
        """Test that black ice risk is not detected when temperature is too high."""
        # Temperature at 40°F, dewpoint at 38°F, humidity at 85%
        # Temperature exceeds threshold
        mock_data = self._create_mock_forecast_response(40.0, 38.0, 85.0)
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=36.0,
                dew_point_spread_f=4.0,
                humidity_min_percent=80.0
            ))
            
            risk_detected, _, _, _ = result
            self.assertFalse(risk_detected, "Black ice risk should NOT be detected (temp too high)")
    
    def test_black_ice_risk_not_detected_dew_spread_too_large(self):
        """Test that black ice risk is not detected when dew point spread is too large."""
        # Temperature at 34°F, dewpoint at 25°F (9°F spread), humidity at 85%
        # Dew point spread exceeds threshold
        mock_data = self._create_mock_forecast_response(34.0, 25.0, 85.0)
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=36.0,
                dew_point_spread_f=4.0,
                humidity_min_percent=80.0
            ))
            
            risk_detected, _, _, _ = result
            self.assertFalse(risk_detected, "Black ice risk should NOT be detected (dew spread too large)")
    
    def test_black_ice_risk_not_detected_humidity_too_low(self):
        """Test that black ice risk is not detected when humidity is too low."""
        # Temperature at 34°F, dewpoint at 32°F, humidity at 60%
        # Humidity below threshold
        mock_data = self._create_mock_forecast_response(34.0, 32.0, 60.0)
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=36.0,
                dew_point_spread_f=4.0,
                humidity_min_percent=80.0
            ))
            
            risk_detected, _, _, _ = result
            self.assertFalse(risk_detected, "Black ice risk should NOT be detected (humidity too low)")
    
    def test_black_ice_risk_edge_case_exact_thresholds(self):
        """Test black ice detection with values exactly at thresholds."""
        # Temperature at 36°F, dewpoint at 32°F (4°F spread), humidity at 80%
        # All values exactly at thresholds
        mock_data = self._create_mock_forecast_response(36.0, 32.0, 80.0)
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=36.0,
                dew_point_spread_f=4.0,
                humidity_min_percent=80.0
            ))
            
            risk_detected, _, _, _ = result
            self.assertTrue(risk_detected, "Black ice risk should be detected at exact thresholds")
    
    def test_black_ice_risk_freezing_conditions(self):
        """Test black ice detection at freezing point."""
        # Temperature at 32°F, dewpoint at 31°F (1°F spread), humidity at 90%
        # Classic black ice conditions at freezing point
        mock_data = self._create_mock_forecast_response(32.0, 31.0, 90.0)
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=36.0,
                dew_point_spread_f=4.0,
                humidity_min_percent=80.0
            ))
            
            risk_detected, _, _, _ = result
            self.assertTrue(risk_detected, "Black ice risk should be detected at freezing point")
    
    def test_openweathermap_black_ice_detection(self):
        """Test black ice detection with OpenWeatherMap service."""
        # Create mock forecast response for OWM format
        # Use a timestamp well in the future to avoid timing issues
        from datetime import timedelta
        future_time = datetime.now() + timedelta(hours=2)
        current_time = int(future_time.timestamp())
        
        mock_data = {
            'list': [{
                'dt': current_time,  # 2 hours from now
                'main': {
                    'temp': 34.0,
                    'humidity': 85.0
                }
            }]
        }
        
        with patch.object(self.owm_service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.owm_service.check_black_ice_risk(
                hours_ahead=3,  # Check 3 hours ahead to include our test data
                temperature_max_f=36.0,
                dew_point_spread_f=4.5,  # Slightly higher to account for precision
                humidity_min_percent=80.0
            ))
            
            risk_detected, risk_time, temp, dewpoint = result
            
            # With 85% humidity and 34°F, dew point should be around 30°F (Magnus formula)
            # which gives a spread of about 4.0°F - should trigger detection
            self.assertTrue(risk_detected, "Black ice risk should be detected in OWM service")
            self.assertIsNotNone(risk_time, "Risk time should be set")
            self.assertEqual(temp, 34.0, "Temperature should match")
            self.assertIsNotNone(dewpoint, "Dewpoint should be calculated")
    
    def test_custom_thresholds(self):
        """Test black ice detection with custom threshold values."""
        # Test with more conservative thresholds
        mock_data = self._create_mock_forecast_response(38.0, 36.0, 75.0)
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=40.0,  # Higher temp threshold
                dew_point_spread_f=3.0,   # Smaller spread threshold
                humidity_min_percent=70.0  # Lower humidity threshold
            ))
            
            risk_detected, _, _, _ = result
            self.assertTrue(risk_detected, "Black ice risk should be detected with custom thresholds")
    
    def test_empty_forecast_data(self):
        """Test handling of empty forecast data."""
        mock_data = {
            'hourly': {
                'time': [],
                'temperature_2m': [],
                'precipitation': [],
                'dewpoint_2m': [],
                'relative_humidity_2m': []
            }
        }
        
        with patch.object(self.service, 'get_forecast', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_data
            
            result = asyncio.run(self.service.check_black_ice_risk(
                hours_ahead=1,
                temperature_max_f=36.0,
                dew_point_spread_f=4.0,
                humidity_min_percent=80.0
            ))
            
            risk_detected, _, _, _ = result
            self.assertFalse(risk_detected, "Should return False with empty forecast")


if __name__ == '__main__':
    unittest.main()

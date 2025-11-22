#!/usr/bin/env python3
"""
Unit test for forecast_days calculation fix.

Tests that the forecast_days parameter is calculated correctly to ensure
sufficient API data is returned, especially for late-day requests.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from weather_service import WeatherService


class TestForecastDaysCalculation(unittest.TestCase):
    """Test the forecast_days calculation in WeatherService.get_forecast()."""
    
    def setUp(self):
        """Set up test environment."""
        self.service = WeatherService(
            latitude=40.7128,
            longitude=-74.0060,
            timezone="America/New_York"
        )
    
    def test_forecast_days_calculation_12_hours(self):
        """Test forecast_days calculation for 12 hours ahead."""
        # For 12 hours: max(2, ((12 + 23) // 24)) = max(2, 35 // 24) = max(2, 1) = 2
        hours_ahead = 12
        expected_days = 2
        
        with patch('aiohttp.ClientSession') as mock_session:
            # Mock the HTTP response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'hourly': {'time': [], 'temperature_2m': [], 'precipitation': []}})
            
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = MagicMock(return_value=mock_context)
            
            mock_session_instance = MagicMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            # Run the async function
            import asyncio
            asyncio.run(self.service.get_forecast(hours_ahead))
            
            # Verify the API was called with correct forecast_days
            call_args = mock_get.call_args
            params = call_args[1]['params']
            
            self.assertEqual(params['forecast_days'], expected_days,
                           f"For {hours_ahead} hours, forecast_days should be {expected_days}")
    
    def test_forecast_days_calculation_24_hours(self):
        """Test forecast_days calculation for 24 hours ahead."""
        # For 24 hours: max(2, ((24 + 23) // 24)) = max(2, 47 // 24) = max(2, 1) = 2
        hours_ahead = 24
        expected_days = 2
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'hourly': {'time': [], 'temperature_2m': [], 'precipitation': []}})
            
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = MagicMock(return_value=mock_context)
            
            mock_session_instance = MagicMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            import asyncio
            asyncio.run(self.service.get_forecast(hours_ahead))
            
            call_args = mock_get.call_args
            params = call_args[1]['params']
            
            self.assertEqual(params['forecast_days'], expected_days,
                           f"For {hours_ahead} hours, forecast_days should be {expected_days}")
    
    def test_forecast_days_calculation_36_hours(self):
        """Test forecast_days calculation for 36 hours ahead."""
        # For 36 hours: max(2, ((36 + 23) // 24)) = max(2, 59 // 24) = max(2, 2) = 2
        hours_ahead = 36
        expected_days = 2
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'hourly': {'time': [], 'temperature_2m': [], 'precipitation': []}})
            
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = MagicMock(return_value=mock_context)
            
            mock_session_instance = MagicMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            import asyncio
            asyncio.run(self.service.get_forecast(hours_ahead))
            
            call_args = mock_get.call_args
            params = call_args[1]['params']
            
            self.assertEqual(params['forecast_days'], expected_days,
                           f"For {hours_ahead} hours, forecast_days should be {expected_days}")
    
    def test_forecast_days_calculation_48_hours(self):
        """Test forecast_days calculation for 48 hours ahead."""
        # For 48 hours: max(2, ((48 + 23) // 24)) = max(2, 71 // 24) = max(2, 2) = 2
        hours_ahead = 48
        expected_days = 2
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'hourly': {'time': [], 'temperature_2m': [], 'precipitation': []}})
            
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = MagicMock(return_value=mock_context)
            
            mock_session_instance = MagicMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            import asyncio
            asyncio.run(self.service.get_forecast(hours_ahead))
            
            call_args = mock_get.call_args
            params = call_args[1]['params']
            
            self.assertEqual(params['forecast_days'], expected_days,
                           f"For {hours_ahead} hours, forecast_days should be {expected_days}")
    
    def test_forecast_days_calculation_49_hours(self):
        """Test forecast_days calculation for 49 hours ahead (crosses into 3rd day)."""
        # For 49 hours: max(2, ((49 + 23) // 24)) = max(2, 72 // 24) = max(2, 3) = 3
        hours_ahead = 49
        expected_days = 3
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'hourly': {'time': [], 'temperature_2m': [], 'precipitation': []}})
            
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = MagicMock(return_value=mock_context)
            
            mock_session_instance = MagicMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            import asyncio
            asyncio.run(self.service.get_forecast(hours_ahead))
            
            call_args = mock_get.call_args
            params = call_args[1]['params']
            
            self.assertEqual(params['forecast_days'], expected_days,
                           f"For {hours_ahead} hours, forecast_days should be {expected_days}")
    
    def test_forecast_days_minimum_is_two(self):
        """Test that forecast_days has a minimum of 2 days."""
        # Even for very small hours_ahead values, we should get at least 2 days
        # For 1 hour: max(2, ((1 + 23) // 24)) = max(2, 24 // 24) = max(2, 1) = 2
        hours_ahead = 1
        expected_days = 2
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'hourly': {'time': [], 'temperature_2m': [], 'precipitation': []}})
            
            mock_context = MagicMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_response)
            mock_context.__aexit__ = AsyncMock(return_value=None)
            
            mock_get = MagicMock(return_value=mock_context)
            
            mock_session_instance = MagicMock()
            mock_session_instance.get = mock_get
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            import asyncio
            asyncio.run(self.service.get_forecast(hours_ahead))
            
            call_args = mock_get.call_args
            params = call_args[1]['params']
            
            self.assertEqual(params['forecast_days'], expected_days,
                           f"Minimum forecast_days should be {expected_days}")


if __name__ == '__main__':
    unittest.main()

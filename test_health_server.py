#!/usr/bin/env python3
"""
Test health check HTTP server endpoints.
"""

import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

# Import the health server
from health_server import HealthCheckServer


class TestHealthServerEndpoints(unittest.TestCase):
    """Test health check HTTP server endpoints."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock scheduler
        self.mock_scheduler = Mock()
        self.mock_scheduler.weather_enabled = True
        self.mock_scheduler.config = Mock()
        self.mock_scheduler.config.weather_api = {'provider': 'open-meteo'}
        self.mock_scheduler.config.scheduler = {'forecast_hours': 12}
        self.mock_scheduler.config.thresholds = {'temperature_f': 34}
        
        # Create mock weather service
        self.mock_weather = AsyncMock()
        self.mock_scheduler.weather = self.mock_weather
        
        # Create health server
        self.server = HealthCheckServer(
            scheduler=self.mock_scheduler,
            host='127.0.0.1',
            port=8888
        )
    
    def test_health_server_initialization(self):
        """Test health server is initialized correctly."""
        self.assertIsNotNone(self.server)
        self.assertEqual(self.server.host, '127.0.0.1')
        self.assertEqual(self.server.port, 8888)
        self.assertIsNotNone(self.server.app)
    
    def test_handle_health_basic(self):
        """Test basic health endpoint."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Create mock request
        mock_request = Mock()
        
        # Call handler
        response = loop.run_until_complete(self.server.handle_health(mock_request))
        
        # Verify response
        self.assertEqual(response.status, 200)
        self.assertIn(b'status', response.body)
        
        loop.close()
    
    def test_handle_weather_health_disabled(self):
        """Test weather health endpoint when weather is disabled."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Disable weather
        self.mock_scheduler.weather_enabled = False
        
        # Create mock request
        mock_request = Mock()
        
        # Call handler
        response = loop.run_until_complete(self.server.handle_weather_health(mock_request))
        
        # Verify response
        self.assertEqual(response.status, 200)
        body = response.body
        self.assertIn(b'disabled', body)
        self.assertIn(b'"weather_enabled": false', body)
        
        loop.close()
    
    def test_handle_weather_health_enabled_success(self):
        """Test weather health endpoint when weather is enabled and working."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Enable weather
        self.mock_scheduler.weather_enabled = True
        
        # Mock weather service responses
        self.mock_weather.get_current_conditions = AsyncMock(return_value=(35.5, 'Clear'))
        self.mock_weather.check_precipitation_forecast = AsyncMock(
            return_value=(True, datetime(2024, 1, 1, 10, 0), 33.0)
        )
        
        # Create mock request
        mock_request = Mock()
        
        # Call handler
        response = loop.run_until_complete(self.server.handle_weather_health(mock_request))
        
        # Verify response
        self.assertEqual(response.status, 200)
        body = response.body
        self.assertIn(b'"status": "ok"', body)
        self.assertIn(b'"weather_enabled": true', body)
        self.assertIn(b'open-meteo', body)
        
        loop.close()
    
    def test_handle_weather_health_enabled_timeout(self):
        """Test weather health endpoint when weather API times out."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Enable weather
        self.mock_scheduler.weather_enabled = True
        
        # Mock weather service to timeout
        async def slow_response():
            await asyncio.sleep(10)
            return (35.5, 'Clear')
        
        self.mock_weather.get_current_conditions = slow_response
        
        # Create mock request
        mock_request = Mock()
        
        # Call handler
        response = loop.run_until_complete(self.server.handle_weather_health(mock_request))
        
        # Verify response - should be 503 due to timeout
        self.assertEqual(response.status, 503)
        body = response.body
        self.assertIn(b'timeout', body)
        
        loop.close()
    
    def test_handle_weather_health_enabled_error(self):
        """Test weather health endpoint when weather API returns an error."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Enable weather
        self.mock_scheduler.weather_enabled = True
        
        # Mock weather service to raise error
        self.mock_weather.get_current_conditions = AsyncMock(
            side_effect=Exception("Weather API error")
        )
        
        # Create mock request
        mock_request = Mock()
        
        # Call handler
        response = loop.run_until_complete(self.server.handle_weather_health(mock_request))
        
        # Verify response - should be 503 due to error
        self.assertEqual(response.status, 503)
        body = response.body
        self.assertIn(b'error', body)
        
        loop.close()


if __name__ == '__main__':
    unittest.main()

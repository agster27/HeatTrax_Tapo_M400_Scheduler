#!/usr/bin/env python3
"""
Unit tests for weather resilience features.
Tests WeatherCache, ResilientWeatherService, and fail-safe behavior.
"""

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from weather_cache import WeatherCache, WeatherSnapshot
from resilient_weather_service import ResilientWeatherService, WeatherServiceState
from weather_service import WeatherServiceError
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_weather_cache_save_and_load():
    """Test saving and loading weather cache."""
    logger.info("Testing weather cache save and load...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        cache = WeatherCache(str(cache_file))
        
        # Create mock forecast data
        now = datetime.now()
        forecast_data = {
            'hourly': {
                'time': [
                    (now + timedelta(hours=i)).isoformat() for i in range(12)
                ],
                'temperature_2m': [30.0 + i for i in range(12)],
                'precipitation': [0.0 if i < 6 else 1.5 for i in range(12)]
            }
        }
        
        # Save forecast
        success = cache.save_forecast(
            latitude=40.7128,
            longitude=-74.006,
            forecast_data=forecast_data,
            forecast_hours=12
        )
        
        assert success, "Failed to save forecast"
        assert cache_file.exists(), "Cache file not created"
        
        # Load cache
        cache2 = WeatherCache(str(cache_file))
        assert cache2.cache_data is not None, "Failed to load cache"
        
        # Validate cache age
        age = cache2.get_cache_age_hours()
        assert age is not None, "Failed to get cache age"
        assert age < 0.1, f"Cache age too old: {age} hours"
        
        # Validate cache is valid
        assert cache2.is_valid(6.0), "Cache should be valid"
        
        # Validate location matches
        assert cache2.location_matches(40.7128, -74.006), "Location should match"
        assert not cache2.location_matches(50.0, -100.0), "Wrong location should not match"
        
        logger.info("✓ Weather cache save and load tests passed")
        return True


def test_weather_cache_get_weather():
    """Test retrieving weather from cache."""
    logger.info("Testing weather cache retrieval...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        cache = WeatherCache(str(cache_file))
        
        # Create forecast with specific times
        now = datetime.now()
        forecast_data = {
            'hourly': {
                'time': [
                    (now + timedelta(hours=i)).isoformat() for i in range(12)
                ],
                'temperature_2m': [30.0 + i for i in range(12)],
                'precipitation': [0.0 if i < 6 else 1.5 for i in range(12)]
            }
        }
        
        cache.save_forecast(40.7128, -74.006, forecast_data, 12)
        
        # Get current conditions
        conditions = cache.get_current_conditions()
        assert conditions is not None, "Failed to get current conditions"
        temp, precip = conditions
        assert temp >= 30.0, f"Unexpected temperature: {temp}"
        
        # Get weather at specific time
        future_time = now + timedelta(hours=8)
        snapshot = cache.get_weather_at(future_time)
        assert snapshot is not None, "Failed to get weather snapshot"
        assert snapshot.precipitation_mm > 0, "Expected precipitation at hour 8"
        
        logger.info("✓ Weather cache retrieval tests passed")
        return True


def test_weather_cache_validation():
    """Test cache validation and error handling."""
    logger.info("Testing weather cache validation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        
        # Test with invalid JSON
        cache_file.write_text("{ invalid json ")
        cache = WeatherCache(str(cache_file))
        assert cache.cache_data is None, "Should reject invalid JSON"
        
        # Test with missing required keys
        cache_file.write_text(json.dumps({'foo': 'bar'}))
        cache = WeatherCache(str(cache_file))
        assert cache.cache_data is None, "Should reject invalid structure"
        
        # Test cache expiration
        valid_cache = {
            'fetched_at': (datetime.now() - timedelta(hours=10)).isoformat(),
            'location': {'latitude': 40.0, 'longitude': -74.0},
            'forecast': [
                {
                    'timestamp': datetime.now().isoformat(),
                    'temperature_f': 32.0,
                    'precipitation_mm': 0.0
                }
            ]
        }
        cache_file.write_text(json.dumps(valid_cache))
        cache = WeatherCache(str(cache_file))
        
        assert cache.cache_data is not None, "Should load valid cache"
        assert not cache.is_valid(6.0), "Cache should be expired (10 hours old)"
        assert cache.is_valid(12.0), "Cache should be valid within 12 hours"
        
        logger.info("✓ Weather cache validation tests passed")
        return True


async def test_resilient_weather_service_states():
    """Test state transitions in ResilientWeatherService."""
    logger.info("Testing resilient weather service states...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        
        # Create mock weather service
        mock_weather = Mock()
        mock_weather.latitude = 40.7128
        mock_weather.longitude = -74.006
        
        # Successful forecast
        now = datetime.now()
        mock_forecast = {
            'hourly': {
                'time': [(now + timedelta(hours=i)).isoformat() for i in range(12)],
                'temperature_2m': [32.0] * 12,
                'precipitation': [0.0] * 12
            }
        }
        mock_weather.get_forecast = AsyncMock(return_value=mock_forecast)
        
        # Create resilient service
        service = ResilientWeatherService(
            weather_service=mock_weather,
            cache_file=str(cache_file),
            cache_valid_hours=6.0,
            forecast_horizon_hours=12,
            refresh_interval_minutes=10,
            retry_interval_minutes=5,
            max_retry_interval_minutes=60,
            outage_alert_after_minutes=30
        )
        
        # Initial state should be OFFLINE_NO_WEATHER_DATA
        assert service.state == WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        
        # Fetch should succeed and transition to ONLINE
        success = await service.fetch_and_cache_forecast()
        assert success, "Fetch should succeed"
        assert service.state == WeatherServiceState.ONLINE, f"Should be ONLINE, got {service.state}"
        assert service.offline_since is None, "Should not be marked offline"
        
        # Simulate failure
        mock_weather.get_forecast = AsyncMock(side_effect=Exception("Network error"))
        success = await service.fetch_and_cache_forecast()
        assert not success, "Fetch should fail"
        assert service.offline_since is not None, "Should be marked offline"
        
        # Should be in DEGRADED state (using cache)
        assert service.state == WeatherServiceState.DEGRADED_OFFLINE_USING_CACHE
        
        # Verify can still get data from cache
        conditions = await service.get_current_conditions()
        assert conditions is not None, "Should get data from cache"
        
        logger.info("✓ Resilient weather service state tests passed")
        return True


async def test_resilient_weather_service_fail_safe():
    """Test fail-safe behavior when cache expires."""
    logger.info("Testing fail-safe behavior...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        
        # Create expired cache
        expired_cache = {
            'fetched_at': (datetime.now() - timedelta(hours=10)).isoformat(),
            'location': {'latitude': 40.7128, 'longitude': -74.006},
            'forecast': [
                {
                    'timestamp': (datetime.now() - timedelta(hours=9)).isoformat(),
                    'temperature_f': 32.0,
                    'precipitation_mm': 0.0
                }
            ]
        }
        Path(cache_file).write_text(json.dumps(expired_cache))
        
        # Create mock weather service that always fails
        mock_weather = Mock()
        mock_weather.latitude = 40.7128
        mock_weather.longitude = -74.006
        mock_weather.get_forecast = AsyncMock(side_effect=Exception("Service unavailable"))
        
        # Create resilient service with short cache validity
        service = ResilientWeatherService(
            weather_service=mock_weather,
            cache_file=str(cache_file),
            cache_valid_hours=6.0,  # Cache is 10 hours old, so invalid
            forecast_horizon_hours=12,
            refresh_interval_minutes=10,
            retry_interval_minutes=5,
            max_retry_interval_minutes=60,
            outage_alert_after_minutes=30
        )
        
        # Should start in OFFLINE_NO_WEATHER_DATA (cache expired)
        assert service.state == WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        
        # Try to fetch (will fail)
        success = await service.fetch_and_cache_forecast()
        assert not success, "Fetch should fail"
        
        # Should remain in OFFLINE_NO_WEATHER_DATA
        assert service.state == WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        
        # get_current_conditions should return None (fail-safe)
        conditions = await service.get_current_conditions()
        assert conditions is None, "Should return None in fail-safe mode"
        
        # check_precipitation_forecast should return (False, None, None)
        result = await service.check_precipitation_forecast()
        assert result == (False, None, None), "Should return no precipitation in fail-safe mode"
        
        logger.info("✓ Fail-safe behavior tests passed")
        return True


async def test_resilient_weather_service_retry_backoff():
    """Test exponential backoff retry logic."""
    logger.info("Testing retry backoff...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        
        mock_weather = Mock()
        mock_weather.latitude = 40.7128
        mock_weather.longitude = -74.006
        mock_weather.get_forecast = AsyncMock(side_effect=Exception("Network error"))
        
        service = ResilientWeatherService(
            weather_service=mock_weather,
            cache_file=str(cache_file),
            cache_valid_hours=6.0,
            forecast_horizon_hours=12,
            refresh_interval_minutes=10,
            retry_interval_minutes=5,
            max_retry_interval_minutes=60,
            outage_alert_after_minutes=30
        )
        
        # Initial retry interval should be 5
        assert service.current_retry_interval == 5
        
        # After failure, interval should be 10
        await service.fetch_and_cache_forecast()
        service.update_retry_interval()
        assert service.current_retry_interval == 10, f"Expected 10, got {service.current_retry_interval}"
        
        # After another failure, interval should be 20
        service.update_retry_interval()
        assert service.current_retry_interval == 20
        
        # Keep doubling until max
        service.update_retry_interval()
        assert service.current_retry_interval == 40
        
        service.update_retry_interval()
        assert service.current_retry_interval == 60, "Should cap at max_retry_interval"
        
        service.update_retry_interval()
        assert service.current_retry_interval == 60, "Should stay at max"
        
        logger.info("✓ Retry backoff tests passed")
        return True


def main_test():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Weather Resilience Test Suite")
    logger.info("=" * 60)
    
    results = []
    
    # Sync tests
    results.append(("Weather Cache Save/Load", test_weather_cache_save_and_load()))
    results.append(("Weather Cache Retrieval", test_weather_cache_get_weather()))
    results.append(("Weather Cache Validation", test_weather_cache_validation()))
    
    # Async tests
    loop = asyncio.get_event_loop()
    results.append(("Resilient Service States", loop.run_until_complete(test_resilient_weather_service_states())))
    results.append(("Fail-Safe Behavior", loop.run_until_complete(test_resilient_weather_service_fail_safe())))
    results.append(("Retry Backoff", loop.run_until_complete(test_resilient_weather_service_retry_backoff())))
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("=" * 60)
    logger.info(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")
    logger.info("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main_test()
    sys.exit(0 if success else 1)

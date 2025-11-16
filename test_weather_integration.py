#!/usr/bin/env python3
"""
Integration test for weather resilience features.
Tests end-to-end behavior with real-ish scenarios.
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

from weather_factory import WeatherServiceFactory
from weather_service import WeatherServiceError
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_weather_factory_integration():
    """Test that weather factory creates resilient wrapper correctly."""
    logger.info("Testing weather factory integration...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create minimal config
        config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.006,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'provider': 'open-meteo',
                'resilience': {
                    'cache_file': str(Path(tmpdir) / 'weather_cache.json'),
                    'cache_valid_hours': 6.0,
                    'forecast_horizon_hours': 12,
                    'refresh_interval_minutes': 10,
                    'retry_interval_minutes': 5,
                    'max_retry_interval_minutes': 60,
                    'outage_alert_after_minutes': 30
                }
            }
        }
        
        # Create weather service via factory
        service = WeatherServiceFactory.create_weather_service(config)
        
        # Verify it's a resilient service
        assert hasattr(service, 'weather_service'), "Should be ResilientWeatherService"
        assert hasattr(service, 'state'), "Should have state"
        assert hasattr(service, 'cache'), "Should have cache"
        
        # Verify underlying service
        assert hasattr(service.weather_service, 'latitude'), "Should wrap base service"
        assert service.weather_service.latitude == 40.7128
        
        logger.info("✓ Weather factory integration test passed")
        return True


async def test_full_outage_recovery_cycle():
    """Test complete cycle: online → degraded → offline → recovery."""
    logger.info("Testing full outage recovery cycle...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "weather_cache.json"
        
        # Create mock weather service
        mock_weather = Mock()
        mock_weather.latitude = 40.7128
        mock_weather.longitude = -74.006
        
        now = datetime.now()
        mock_forecast = {
            'hourly': {
                'time': [(now + timedelta(hours=i)).isoformat() for i in range(12)],
                'temperature_2m': [32.0] * 12,
                'precipitation': [0.0] * 12
            }
        }
        
        # Import after mocking to avoid circular imports
        from resilient_weather_service import ResilientWeatherService, WeatherServiceState
        
        # Start with working service
        mock_weather.get_forecast = AsyncMock(return_value=mock_forecast)
        
        service = ResilientWeatherService(
            weather_service=mock_weather,
            cache_file=str(cache_file),
            cache_valid_hours=0.001,  # 0.001 hours = 3.6 seconds (fast expiry for testing)
            forecast_horizon_hours=12,
            refresh_interval_minutes=10,
            retry_interval_minutes=5,
            max_retry_interval_minutes=60,
            outage_alert_after_minutes=30
        )
        
        # Step 1: Online - successful fetch
        logger.info("Step 1: Testing ONLINE state...")
        success = await service.fetch_and_cache_forecast()
        assert success, "Initial fetch should succeed"
        assert service.state == WeatherServiceState.ONLINE
        conditions = await service.get_current_conditions()
        assert conditions is not None, "Should get conditions when ONLINE"
        
        # Step 2: Degraded - service fails but cache valid
        logger.info("Step 2: Testing DEGRADED state...")
        mock_weather.get_forecast = AsyncMock(side_effect=Exception("Network error"))
        success = await service.fetch_and_cache_forecast()
        assert not success, "Fetch should fail"
        assert service.state == WeatherServiceState.DEGRADED_OFFLINE_USING_CACHE
        conditions = await service.get_current_conditions()
        assert conditions is not None, "Should get conditions from cache when DEGRADED"
        
        # Step 3: Offline - wait for cache to expire
        logger.info("Step 3: Testing OFFLINE state (waiting for cache expiry)...")
        await asyncio.sleep(4)  # Wait for cache to expire (>3.6 seconds)
        
        # Update state to reflect expired cache
        service._update_state()
        assert service.state == WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        conditions = await service.get_current_conditions()
        assert conditions is None, "Should return None when OFFLINE (fail-safe)"
        
        # Step 4: Recovery - service comes back online
        logger.info("Step 4: Testing RECOVERY...")
        mock_weather.get_forecast = AsyncMock(return_value=mock_forecast)
        success = await service.fetch_and_cache_forecast()
        assert success, "Recovery fetch should succeed"
        assert service.state == WeatherServiceState.ONLINE
        assert service.offline_since is None, "Should clear offline tracking"
        conditions = await service.get_current_conditions()
        assert conditions is not None, "Should get conditions after recovery"
        
        logger.info("✓ Full outage recovery cycle test passed")
        return True


async def test_precipitation_check_with_failsafe():
    """Test precipitation checking with fail-safe fallback."""
    logger.info("Testing precipitation check with fail-safe...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "weather_cache.json"
        
        # Create mock weather service
        mock_weather = Mock()
        mock_weather.latitude = 40.7128
        mock_weather.longitude = -74.006
        
        # Create forecast with precipitation
        now = datetime.now()
        mock_forecast = {
            'hourly': {
                'time': [(now + timedelta(hours=i)).isoformat() for i in range(12)],
                'temperature_2m': [30.0] * 12,  # Below 34°F
                'precipitation': [0.0 if i < 4 else 2.0 for i in range(12)]  # Precip at hour 4+
            }
        }
        
        from resilient_weather_service import ResilientWeatherService
        
        mock_weather.get_forecast = AsyncMock(return_value=mock_forecast)
        
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
        
        # Fetch and cache
        await service.fetch_and_cache_forecast()
        
        # Check precipitation - should detect it
        has_precip, precip_time, temp = await service.check_precipitation_forecast(
            hours_ahead=12,
            temperature_threshold_f=34.0
        )
        assert has_precip, "Should detect precipitation"
        assert precip_time is not None, "Should have precipitation time"
        assert temp < 34.0, "Temperature should be below threshold"
        
        # Simulate service failure
        mock_weather.get_forecast = AsyncMock(side_effect=Exception("Network error"))
        await service.fetch_and_cache_forecast()
        
        # Should still detect precipitation from cache
        has_precip, precip_time, temp = await service.check_precipitation_forecast(
            hours_ahead=12,
            temperature_threshold_f=34.0
        )
        assert has_precip, "Should still detect precipitation from cache"
        
        # Now expire the cache by setting invalid state
        from resilient_weather_service import WeatherServiceState
        service.state = WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        
        # Should return fail-safe response
        result = await service.check_precipitation_forecast()
        assert result == (False, None, None), "Should return fail-safe response when offline"
        
        logger.info("✓ Precipitation check with fail-safe test passed")
        return True


def main_test():
    """Run all integration tests."""
    logger.info("=" * 60)
    logger.info("Weather Resilience Integration Test Suite")
    logger.info("=" * 60)
    
    results = []
    
    # Run async tests
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    results.append(("Weather Factory Integration", loop.run_until_complete(test_weather_factory_integration())))
    results.append(("Full Outage Recovery Cycle", loop.run_until_complete(test_full_outage_recovery_cycle())))
    results.append(("Precipitation Check with Fail-Safe", loop.run_until_complete(test_precipitation_check_with_failsafe())))
    
    loop.close()
    
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

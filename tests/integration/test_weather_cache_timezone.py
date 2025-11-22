#!/usr/bin/env python3
"""
Test timezone-aware datetime handling in weather cache.

This test verifies the fix for the issue where forecast timestamps from the Open-Meteo API
(in local time) were incorrectly compared against system UTC time, causing all forecast
entries to be filtered out as "in the past".
"""

import json
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.weather.weather_cache import WeatherCache
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_timezone_aware_forecast_filtering():
    """
    Test that forecast entries are correctly filtered with timezone-aware datetime comparisons.
    
    This simulates the production scenario where:
    - API returns times like "2025-11-20T23:00" (local time, no timezone info)
    - System time is UTC (e.g., "2025-11-21 03:10:19 UTC")
    - The cache should interpret API times as being in the configured timezone
    """
    logger.info("Testing timezone-aware forecast filtering...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        
        # Use America/New_York timezone (EST/EDT)
        timezone = "America/New_York"
        cache = WeatherCache(str(cache_file), timezone=timezone)
        
        # Create mock forecast data with times in local timezone (no timezone info)
        # Simulate the scenario from the bug report:
        # System time: 2025-11-21 03:10:19 UTC (which equals 2025-11-20 22:10:19 EST)
        # API returns: 2025-11-20T23:00 (local time, meaning 23:00 EST)
        # This should be considered a future time (in ~50 minutes from system perspective)
        
        ny_tz = ZoneInfo(timezone)
        utc_tz = ZoneInfo("UTC")
        
        # Simulate system time in UTC (Nov 21, 03:10 UTC = Nov 20, 22:10 EST)
        # For testing, we'll use the current time but the concept is the same
        system_time_utc = datetime.now(utc_tz)
        system_time_local = system_time_utc.astimezone(ny_tz)
        
        logger.info(f"System time (UTC): {system_time_utc}")
        logger.info(f"System time (local): {system_time_local}")
        
        # Create forecast times in local timezone (as API would return them - without tzinfo)
        # These are future times relative to the current local time
        forecast_times = []
        for i in range(1, 13):  # 12 hours ahead
            future_local = system_time_local + timedelta(hours=i)
            # Convert to naive datetime (no timezone info) as API returns them
            forecast_times.append(future_local.replace(tzinfo=None).isoformat())
        
        logger.info(f"First forecast time (naive, local): {forecast_times[0]}")
        logger.info(f"Last forecast time (naive, local): {forecast_times[-1]}")
        
        forecast_data = {
            'hourly': {
                'time': forecast_times,
                'temperature_2m': [32.0 + i for i in range(12)],
                'precipitation': [0.0 if i < 6 else 1.5 for i in range(12)]
            }
        }
        
        # Save forecast with timezone-aware cache
        success = cache.save_forecast(
            latitude=40.7128,  # New York coordinates
            longitude=-74.006,
            forecast_data=forecast_data,
            forecast_hours=12
        )
        
        # Verify the forecast was saved successfully
        assert success, "Failed to save forecast - timezone handling may be broken"
        assert cache.cache_data is not None, "Cache data should not be None"
        
        forecast_list = cache.cache_data['forecast']
        logger.info(f"Successfully saved {len(forecast_list)} forecast entries")
        
        # With the fix, we should have entries in the forecast
        # Without the fix, all entries would be filtered out
        assert len(forecast_list) > 0, (
            "No forecast entries saved! This indicates the timezone fix is not working. "
            "The forecast times should be interpreted as local time and compared correctly."
        )
        
        # Ideally, we should have most of the 12 hours saved (some may be filtered if too close to cutoff)
        assert len(forecast_list) >= 10, (
            f"Expected at least 10 forecast entries, got {len(forecast_list)}. "
            "Some entries may be incorrectly filtered due to timezone handling."
        )
        
        logger.info("✓ Timezone-aware forecast filtering test passed")
        return True


def test_timezone_aware_retrieval():
    """Test that forecast retrieval uses timezone-aware comparisons."""
    logger.info("Testing timezone-aware forecast retrieval...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        
        # Use America/Los_Angeles timezone (PST/PDT)
        timezone = "America/Los_Angeles"
        cache = WeatherCache(str(cache_file), timezone=timezone)
        
        la_tz = ZoneInfo(timezone)
        current_local = datetime.now(la_tz)
        
        # Create forecast data
        forecast_times = []
        for i in range(1, 13):
            future_local = current_local + timedelta(hours=i)
            forecast_times.append(future_local.replace(tzinfo=None).isoformat())
        
        forecast_data = {
            'hourly': {
                'time': forecast_times,
                'temperature_2m': [30.0 + i for i in range(12)],
                'precipitation': [0.0] * 12
            }
        }
        
        # Save forecast
        success = cache.save_forecast(
            latitude=34.0522,  # Los Angeles coordinates
            longitude=-118.2437,
            forecast_data=forecast_data,
            forecast_hours=12
        )
        
        assert success, "Failed to save forecast"
        
        # Test get_current_conditions - should work with timezone-aware comparisons
        conditions = cache.get_current_conditions()
        assert conditions is not None, "Failed to get current conditions"
        temp, precip = conditions
        assert temp >= 30.0, f"Unexpected temperature: {temp}"
        logger.info(f"Current conditions: {temp}°F, {precip}mm")
        
        # Test get_weather_at with a future time
        future_time = current_local + timedelta(hours=6)
        snapshot = cache.get_weather_at(future_time)
        assert snapshot is not None, "Failed to get weather snapshot for future time"
        logger.info(f"Weather at +6 hours: {snapshot.temperature_f}°F, {snapshot.precipitation_mm}mm")
        
        logger.info("✓ Timezone-aware retrieval test passed")
        return True


def test_different_timezones():
    """Test that the cache works correctly with different timezones."""
    logger.info("Testing different timezones...")
    
    timezones = [
        "America/New_York",      # EST/EDT
        "America/Chicago",       # CST/CDT
        "America/Denver",        # MST/MDT
        "America/Los_Angeles",   # PST/PDT
        "Europe/London",         # GMT/BST
        "Asia/Tokyo",            # JST
        "Australia/Sydney",      # AEST/AEDT
    ]
    
    for timezone in timezones:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = WeatherCache(str(cache_file), timezone=timezone)
            
            tz = ZoneInfo(timezone)
            current_local = datetime.now(tz)
            
            # Create forecast data
            forecast_times = []
            for i in range(1, 7):  # 6 hours for faster testing
                future_local = current_local + timedelta(hours=i)
                forecast_times.append(future_local.replace(tzinfo=None).isoformat())
            
            forecast_data = {
                'hourly': {
                    'time': forecast_times,
                    'temperature_2m': [25.0 + i for i in range(6)],
                    'precipitation': [0.0] * 6
                }
            }
            
            # Save forecast
            success = cache.save_forecast(
                latitude=0.0,
                longitude=0.0,
                forecast_data=forecast_data,
                forecast_hours=6
            )
            
            assert success, f"Failed to save forecast for timezone {timezone}"
            
            forecast_list = cache.cache_data['forecast']
            assert len(forecast_list) >= 5, (
                f"Timezone {timezone}: Expected at least 5 entries, got {len(forecast_list)}"
            )
            
            logger.info(f"  ✓ {timezone}: {len(forecast_list)} entries saved")
    
    logger.info("✓ Different timezones test passed")
    return True


def test_invalid_timezone_fallback():
    """Test that invalid timezone falls back to UTC."""
    logger.info("Testing invalid timezone fallback...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        
        # Use an invalid timezone
        cache = WeatherCache(str(cache_file), timezone="Invalid/Timezone")
        
        # Should fall back to UTC
        assert cache.timezone == "UTC", f"Expected UTC, got {cache.timezone}"
        assert cache.tz == ZoneInfo("UTC"), "Timezone should be UTC"
        
        # Cache should still work
        utc_now = datetime.now(ZoneInfo("UTC"))
        forecast_times = []
        for i in range(1, 7):
            future = utc_now + timedelta(hours=i)
            forecast_times.append(future.replace(tzinfo=None).isoformat())
        
        forecast_data = {
            'hourly': {
                'time': forecast_times,
                'temperature_2m': [20.0] * 6,
                'precipitation': [0.0] * 6
            }
        }
        
        success = cache.save_forecast(0.0, 0.0, forecast_data, 6)
        assert success, "Cache should work with UTC fallback"
        
        logger.info("✓ Invalid timezone fallback test passed")
        return True


def main_test():
    """Run all timezone tests."""
    logger.info("=" * 60)
    logger.info("Weather Cache Timezone Test Suite")
    logger.info("=" * 60)
    
    results = []
    results.append(("Timezone-aware forecast filtering", test_timezone_aware_forecast_filtering()))
    results.append(("Timezone-aware retrieval", test_timezone_aware_retrieval()))
    results.append(("Different timezones", test_different_timezones()))
    results.append(("Invalid timezone fallback", test_invalid_timezone_fallback()))
    
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

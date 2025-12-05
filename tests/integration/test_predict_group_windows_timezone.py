"""
Test to validate the timezone-aware datetime fix for predict_group_windows method.
This test specifically addresses the bug where datetime.now() was timezone-naive
in predict_group_windows while precip_time was timezone-aware, causing comparison errors.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo
import tempfile
from pathlib import Path

from src.scheduler.scheduler_enhanced import EnhancedScheduler
from src.config.config_loader import Config


def test_predict_group_windows_precipitation_timezone_aware():
    """
    Test that predict_group_windows properly handles timezone-aware datetime comparisons
    when precipitation control is enabled.
    
    This test verifies:
    1. predict_group_windows uses timezone-aware datetime for the 'now' variable
    2. check_time passed to _predict_group_state_at_time is timezone-aware
    3. No TypeError is raised when comparing offset-naive and offset-aware datetimes
    4. Mats are predicted to be ON when precipitation is forecasted
    """
    
    # Create config file with precipitation control enabled
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
location:
  latitude: 42.1456
  longitude: -71.5072
  timezone: "America/New_York"

weather_api:
  enabled: true
  provider: "open-meteo"

devices:
  credentials:
    username: "test_user"
    password: "test_password"
  groups:
    test_group:
      enabled: true
      automation:
        weather_control: true
        precipitation_control: true
      items:
        - name: "test_device"
          ip_address: "10.0.0.1"
          outlets: [0]

thresholds:
  temperature_f: 45
  lead_time_minutes: 60
  trailing_time_minutes: 60

safety:
  max_runtime_hours: 6
  cooldown_minutes: 30

scheduler:
  check_interval_minutes: 10
  forecast_hours: 12

logging:
  level: "DEBUG"
""")
        config_path = f.name
    
    try:
        # Load config
        config = Config(config_path)
        
        # Create scheduler but don't initialize (to avoid device connection attempts)
        scheduler = EnhancedScheduler(config, setup_mode=False)
        
        # Mock the device manager to avoid actual connections
        scheduler.device_manager = MagicMock()
        scheduler.device_manager.get_all_groups.return_value = ['test_group']
        scheduler.device_manager.get_group_config.return_value = {
            'enabled': True,
            'automation': {
                'weather_control': True,
                'precipitation_control': True
            }
        }
        
        # Mock automation_overrides to return the base automation
        scheduler.automation_overrides.get_effective_automation = MagicMock(
            side_effect=lambda group_name, base_automation: base_automation
        )
        
        # Create a mock weather cache with timezone-aware precipitation data
        eastern_tz = ZoneInfo("America/New_York")
        now_eastern = datetime.now(eastern_tz)
        
        # Create precipitation forecast 1 hour from now with temperature below threshold
        precip_time = now_eastern + timedelta(hours=1)
        
        # Mock weather snapshot
        mock_snapshot = MagicMock()
        mock_snapshot.timestamp = precip_time.isoformat()
        mock_snapshot.precipitation_mm = 5.0  # Rain/snow
        mock_snapshot.temperature_f = 40.0  # Below threshold of 45°F
        
        # Mock weather cache
        scheduler.weather = MagicMock()
        scheduler.weather.cache = MagicMock()
        scheduler.weather.cache.cache_data = True
        scheduler.weather.cache.get_weather_at = MagicMock(return_value=mock_snapshot)
        
        # Call predict_group_windows - this should NOT raise TypeError
        try:
            result = scheduler.predict_group_windows(horizon_hours=2, step_minutes=30)
            
            # Verify that we got results
            assert 'test_group' in result, "Should have results for test_group"
            windows = result['test_group']
            assert isinstance(windows, list), "Windows should be a list"
            
            # Check that at least one window shows the mats should be ON due to precipitation
            # The precipitation is 1 hour from now, with 60 minute lead time, so mats should be ON now
            has_on_window = any(w['state'] == 'on' for w in windows)
            assert has_on_window, "Should have at least one ON window due to precipitation forecast"
            
            # Verify reason for ON state
            on_windows = [w for w in windows if w['state'] == 'on']
            assert any(w['reason'] == 'snow_forecast' for w in on_windows), \
                "At least one ON window should be due to snow_forecast (precipitation control)"
            
            print("✓ predict_group_windows handles timezone-aware precipitation comparisons correctly")
            print(f"✓ Found {len(on_windows)} ON window(s) in prediction")
            
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail(f"Timezone comparison error still occurs: {e}")
            else:
                raise
        
    finally:
        # Cleanup
        Path(config_path).unlink(missing_ok=True)


def test_predict_group_windows_check_time_timezone():
    """
    Test that check_time parameter in _predict_group_state_at_time is properly
    handled even if it's timezone-naive (defensive check).
    """
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
location:
  latitude: 40.7128
  longitude: -74.0060
  timezone: "America/New_York"

weather_api:
  enabled: true
  provider: "open-meteo"

devices:
  credentials:
    username: "test_user"
    password: "test_password"
  groups:
    test_group:
      enabled: true
      automation:
        precipitation_control: true
      items:
        - name: "test_device"
          ip_address: "10.0.0.1"
          outlets: [0]

thresholds:
  temperature_f: 45
  lead_time_minutes: 60
  trailing_time_minutes: 60

safety:
  max_runtime_hours: 6
  cooldown_minutes: 30

scheduler:
  check_interval_minutes: 10
  forecast_hours: 12

logging:
  level: "DEBUG"
""")
        config_path = f.name
    
    try:
        config = Config(config_path)
        scheduler = EnhancedScheduler(config, setup_mode=False)
        
        # Setup mocks
        scheduler.device_manager = MagicMock()
        scheduler.automation_overrides.get_effective_automation = MagicMock(
            side_effect=lambda group_name, base_automation: base_automation
        )
        
        group_config = {
            'enabled': True,
            'automation': {
                'weather_control': True,
                'precipitation_control': True
            }
        }
        
        # Create timezone-aware precipitation time
        eastern_tz = ZoneInfo("America/New_York")
        precip_time = datetime.now(eastern_tz) + timedelta(minutes=30)
        
        # Mock weather snapshot
        mock_snapshot = MagicMock()
        mock_snapshot.timestamp = precip_time.isoformat()
        mock_snapshot.precipitation_mm = 3.0
        mock_snapshot.temperature_f = 40.0
        
        scheduler.weather = MagicMock()
        scheduler.weather.cache = MagicMock()
        scheduler.weather.cache.cache_data = True
        scheduler.weather.cache.get_weather_at = MagicMock(return_value=mock_snapshot)
        
        # Test with timezone-aware check_time (normal case after our fix)
        check_time_aware = datetime.now(eastern_tz)
        try:
            result, reason = scheduler._predict_group_state_at_time(
                'test_group', group_config, check_time_aware
            )
            assert isinstance(result, bool), "Should return boolean"
            assert isinstance(reason, str), "Should return reason string"
            print("✓ _predict_group_state_at_time handles timezone-aware check_time correctly")
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail(f"Timezone comparison error with timezone-aware check_time: {e}")
            else:
                raise
        
        # Test defensive check: even if check_time is somehow naive, it should be handled
        # (this tests the additional defensive code we added)
        check_time_naive = datetime.now()  # Intentionally naive
        try:
            result, reason = scheduler._predict_group_state_at_time(
                'test_group', group_config, check_time_naive
            )
            assert isinstance(result, bool), "Should return boolean even with naive check_time"
            print("✓ _predict_group_state_at_time handles timezone-naive check_time defensively")
        except TypeError as e:
            if "can't compare offset-naive and offset-aware datetimes" in str(e):
                pytest.fail(f"Defensive check failed for naive check_time: {e}")
            else:
                raise
        
    finally:
        Path(config_path).unlink(missing_ok=True)


if __name__ == '__main__':
    # Run tests
    test_predict_group_windows_precipitation_timezone_aware()
    test_predict_group_windows_check_time_timezone()
    print("\n✓ All predict_group_windows timezone tests passed!")

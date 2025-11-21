"""
Integration test demonstrating the timezone fix works correctly.
This simulates the exact scenario from the bug report.
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo
import tempfile
from pathlib import Path

from scheduler_enhanced import EnhancedScheduler
from config_loader import Config
from state_manager import StateManager

@pytest.mark.asyncio
async def test_bug_scenario():
    """
    Reproduce the exact bug scenario:
    - Container is in UTC (datetime.now() returns UTC)
    - Config has timezone: America/New_York
    - Morning mode: start_hour: 6, end_hour: 11
    - Current time: 07:48 AM Eastern (12:48 PM UTC)
    - Expected: Morning mode should be ACTIVE
    - Before fix: Was INACTIVE (checked 12 UTC against 6-11 range)
    - After fix: Should be ACTIVE (checks 7 Eastern against 6-11 range)
    """
    
    # Create config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
location:
  latitude: 42.1456
  longitude: -71.5072
  timezone: "America/New_York"

weather_api:
  enabled: true
  provider: "open-meteo"
  resilience:
    cache_file: "/tmp/test_weather_cache.json"

devices:
  credentials:
    username: "test_user"
    password: "test_password"
  groups:
    heattrax:
      enabled: true
      automation:
        weather_control: true
        precipitation_control: true
        morning_mode: true
      items:
        - name: "kitchen"
          ip_address: "10.0.50.74"
          outlets: [0, 1]

morning_mode:
  enabled: true
  start_hour: 6
  end_hour: 11
  temperature_f: 32

thresholds:
  temperature_f: 34
  lead_time_minutes: 60
  trailing_time_minutes: 60

safety:
  max_runtime_hours: 6
  cooldown_minutes: 30

scheduler:
  check_interval_minutes: 10
  forecast_hours: 12

logging:
  level: "INFO"

health_check:
  interval_hours: 24
  max_consecutive_failures: 3

notifications:
  required: false
  email:
    enabled: false
  webhook:
    enabled: false

web:
  enabled: false

health_server:
  enabled: false
""")
        config_path = f.name
    
    try:
        # Load config and create scheduler
        config = Config(config_path)
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Verify timezone was set correctly
        assert scheduler.timezone == ZoneInfo("America/New_York"), \
            f"Expected America/New_York, got {scheduler.timezone}"
        
        # Simulate 07:48 AM Eastern (12:48 PM UTC)
        # This is the time from the bug report
        eastern_748am = datetime(2025, 11, 20, 7, 48, 0, tzinfo=ZoneInfo("America/New_York"))
        
        print(f"\n{'='*70}")
        print(f"TIMEZONE FIX INTEGRATION TEST")
        print(f"{'='*70}")
        print(f"Simulating time: {eastern_748am.isoformat()}")
        print(f"Eastern Time: {eastern_748am.strftime('%I:%M %p %Z')}")
        print(f"UTC equivalent: {eastern_748am.astimezone(ZoneInfo('UTC')).strftime('%I:%M %p %Z')}")
        print(f"Morning mode window: 6:00 AM - 11:00 AM Eastern")
        print(f"Temperature: 30°F (below threshold of 32°F)")
        print(f"{'='*70}\n")
        
        with patch.object(scheduler, '_get_local_now', return_value=eastern_748am):
            # Mock weather service
            scheduler.weather = AsyncMock()
            scheduler.weather.get_current_conditions = AsyncMock(return_value=(30.0, 0.0))
            
            # Mock device manager
            scheduler.device_manager = MagicMock()
            scheduler.device_manager.get_group_config = MagicMock(return_value={
                'automation': {
                    'weather_control': True,
                    'morning_mode': True,
                    'precipitation_control': True
                }
            })
            
            # Create state manager
            with tempfile.NamedTemporaryFile(delete=False) as f:
                state_file = f.name
            state = StateManager(state_file=state_file)
            scheduler.states['heattrax'] = state
            
            # Test should_turn_on_group
            result = await scheduler.should_turn_on_group('heattrax')
            
            print(f"Result: should_turn_on_group('heattrax') = {result}")
            print(f"{'='*70}\n")
            
            if result:
                print("✅ SUCCESS: Morning mode is correctly ACTIVE at 7:48 AM Eastern")
                print("   The timezone fix is working as expected!")
            else:
                print("❌ FAILURE: Morning mode should be ACTIVE but is not")
                print("   The bug may not be fixed correctly")
            
            # Cleanup
            Path(state_file).unlink(missing_ok=True)
            
            assert result is True, \
                "Morning mode should be ACTIVE at 7:48 AM Eastern with temp below threshold"
    
    finally:
        Path(config_path).unlink(missing_ok=True)

if __name__ == '__main__':
    asyncio.run(test_bug_scenario())
    print("\n✅ All integration tests PASSED!\n")

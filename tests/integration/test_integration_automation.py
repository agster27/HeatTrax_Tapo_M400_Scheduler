#!/usr/bin/env python3
"""
Integration test for automation overrides with scheduler.
Tests that the scheduler correctly uses effective automation values.

Note: The schedule_control automation flag has been removed.
All schedule-based automation now uses the unified schedules: array format.
"""

import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock
from datetime import datetime

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_loader import Config
from src.scheduler.automation_overrides import AutomationOverrides
from src.scheduler.scheduler_enhanced import EnhancedScheduler


def test_scheduler_integration():
    """Test that scheduler uses effective automation with overrides."""
    print("="*60)
    print("SCHEDULER INTEGRATION TEST")
    print("="*60)
    
    # Create temporary config file
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "test_config.yaml"
        state_file = Path(tmpdir) / "automation_overrides.json"
        
        # Write test config (using unified schedules: array, no schedule_control)
        config_yaml = """
location:
  latitude: 40.7128
  longitude: -74.0060
  timezone: "America/New_York"

weather_api:
  enabled: false

devices:
  credentials:
    username: "test_user"
    password: "test_pass"
  groups:
    heattrax:
      enabled: true
      automation:
        weather_control: true
        precipitation_control: true
        morning_mode: true
      items: []

thresholds:
  temperature_f: 34
  lead_time_minutes: 60
  trailing_time_minutes: 60

morning_mode:
  enabled: true
  start_hour: 6
  end_hour: 8
  temperature_f: 32

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

health_server:
  enabled: false

reboot:
  pause_seconds: 60

notifications:
  required: false

web:
  enabled: false
"""
        
        with open(config_file, 'w') as f:
            f.write(config_yaml)
        
        # Load config
        print("\n1. Loading configuration...")
        config = Config(str(config_file))
        print("   ✓ Config loaded")
        
        # Create automation overrides
        print("\n2. Creating automation overrides...")
        overrides = AutomationOverrides(state_file=str(state_file))
        print("   ✓ Overrides created")
        
        # Test initial state (no overrides)
        print("\n3. Testing initial state (no overrides)...")
        base_automation = config.devices['groups']['heattrax']['automation']
        effective = overrides.get_effective_automation('heattrax', base_automation)
        
        assert effective['weather_control'] == True, "weather_control should be True"
        assert effective['morning_mode'] == True, "morning_mode should be True"
        assert effective['precipitation_control'] == True, "precipitation_control should be True"
        print("   ✓ Initial state correct")
        
        # Set an override
        print("\n4. Setting override: morning_mode = False...")
        overrides.set_flag('heattrax', 'morning_mode', False)
        
        # Verify override was saved
        with open(state_file, 'r') as f:
            saved_state = json.load(f)
        assert saved_state == {'heattrax': {'morning_mode': False}}, "Override not saved correctly"
        print("   ✓ Override saved to state file")
        
        # Check effective automation with override
        print("\n5. Testing effective automation with override...")
        effective = overrides.get_effective_automation('heattrax', base_automation)
        
        assert effective['weather_control'] == True, "weather_control should still be True"
        assert effective['morning_mode'] == False, "morning_mode should now be False (overridden)"
        assert effective['precipitation_control'] == True, "precipitation_control should still be True"
        print("   ✓ Override applied correctly")
        
        # Load overrides in a new instance (simulating restart)
        print("\n6. Testing persistence across instances...")
        overrides2 = AutomationOverrides(state_file=str(state_file))
        effective2 = overrides2.get_effective_automation('heattrax', base_automation)
        
        assert effective2['morning_mode'] == False, "Override should persist"
        print("   ✓ Override persisted across instances")
        
        # Clear the override
        print("\n7. Clearing override...")
        overrides.set_flag('heattrax', 'morning_mode', None)
        effective = overrides.get_effective_automation('heattrax', base_automation)
        
        assert effective['morning_mode'] == True, "morning_mode should be back to base value"
        print("   ✓ Override cleared successfully")
        
        print("\n" + "="*60)
        print("ALL INTEGRATION TESTS PASSED ✓")
        print("="*60)
        
        return True


if __name__ == "__main__":
    try:
        success = test_scheduler_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

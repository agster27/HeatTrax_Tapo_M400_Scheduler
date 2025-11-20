"""
Unit tests for timezone-aware morning mode and schedule control.

These tests verify that:
1. Morning mode times are evaluated in the configured timezone (not UTC)
2. Schedule control times are evaluated in the configured timezone
3. The scheduler works correctly regardless of container timezone
"""

import asyncio
import pytest
import tempfile
from datetime import datetime, time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from scheduler_enhanced import EnhancedScheduler
from config_loader import Config


class TestTimezoneMorningMode:
    """Test morning mode with timezone-aware time handling."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
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
        - name: "test_mat"
          ip_address: "192.168.1.100"
          outlets: [0]

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
  test_on_startup: false
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
        
        yield config_path
        
        # Cleanup
        Path(config_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def config(self, temp_config_file):
        """Load configuration from temp file."""
        return Config(temp_config_file)
    
    @pytest.mark.asyncio
    async def test_morning_mode_uses_local_timezone(self, config):
        """Test that morning mode hours are evaluated in configured timezone."""
        # Setup scheduler in setup mode (no device init)
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Verify timezone is set correctly
        assert scheduler.timezone == ZoneInfo("America/New_York")
        
        # Mock _get_local_now to return specific times
        # Test case: 7:00 AM Eastern (12:00 UTC)
        eastern_7am = datetime(2025, 11, 20, 7, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        
        with patch.object(scheduler, '_get_local_now', return_value=eastern_7am):
            # Mock weather service
            scheduler.weather = AsyncMock()
            scheduler.weather.get_current_conditions = AsyncMock(return_value=(30.0, 0.0))
            
            # Mock device manager and state
            scheduler.device_manager = MagicMock()
            scheduler.device_manager.get_group_config = MagicMock(return_value={
                'automation': {
                    'weather_control': True,
                    'morning_mode': True,
                    'precipitation_control': False
                }
            })
            
            # Mock state manager
            from state_manager import StateManager
            with tempfile.NamedTemporaryFile(delete=False) as f:
                state_file = f.name
            
            state = StateManager(state_file=state_file)
            scheduler.states['heattrax'] = state
            
            # Test should_turn_on_group at 7 AM Eastern (within 6-11 window)
            result = await scheduler.should_turn_on_group('heattrax')
            
            # Should be True because:
            # - Local time is 7 AM (within 6-11 window)
            # - Temperature (30°F) is below threshold (32°F)
            assert result is True, "Morning mode should be active at 7 AM Eastern when temp is below threshold"
            
            # Cleanup
            Path(state_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_morning_mode_outside_window(self, config):
        """Test that morning mode is NOT active outside the configured window."""
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Test case: 2:00 PM Eastern (outside 6-11 AM window)
        eastern_2pm = datetime(2025, 11, 20, 14, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        
        with patch.object(scheduler, '_get_local_now', return_value=eastern_2pm):
            # Mock weather service
            scheduler.weather = AsyncMock()
            scheduler.weather.get_current_conditions = AsyncMock(return_value=(30.0, 0.0))
            scheduler.weather.check_precipitation_forecast = AsyncMock(
                return_value=(False, None, None)
            )
            
            # Mock device manager and state
            scheduler.device_manager = MagicMock()
            scheduler.device_manager.get_group_config = MagicMock(return_value={
                'automation': {
                    'weather_control': True,
                    'morning_mode': True,
                    'precipitation_control': True
                }
            })
            
            # Mock state manager
            from state_manager import StateManager
            with tempfile.NamedTemporaryFile(delete=False) as f:
                state_file = f.name
            
            state = StateManager(state_file=state_file)
            scheduler.states['heattrax'] = state
            
            # Test should_turn_on_group at 2 PM Eastern (outside 6-11 window)
            result = await scheduler.should_turn_on_group('heattrax')
            
            # Should be False because:
            # - Local time is 2 PM (outside 6-11 window)
            # - No precipitation forecast
            assert result is False, "Morning mode should NOT be active at 2 PM Eastern"
            
            # Cleanup
            Path(state_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_morning_mode_at_window_boundary(self, config):
        """Test morning mode at exact boundary hours."""
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Mock weather service
        scheduler.weather = AsyncMock()
        scheduler.weather.get_current_conditions = AsyncMock(return_value=(30.0, 0.0))
        
        # Mock device manager
        scheduler.device_manager = MagicMock()
        scheduler.device_manager.get_group_config = MagicMock(return_value={
            'automation': {
                'weather_control': True,
                'morning_mode': True,
                'precipitation_control': False
            }
        })
        
        # Mock state manager
        from state_manager import StateManager
        with tempfile.NamedTemporaryFile(delete=False) as f:
            state_file = f.name
        state = StateManager(state_file=state_file)
        scheduler.states['heattrax'] = state
        
        # Test at start hour (6 AM) - should be active
        eastern_6am = datetime(2025, 11, 20, 6, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch.object(scheduler, '_get_local_now', return_value=eastern_6am):
            result = await scheduler.should_turn_on_group('heattrax')
            assert result is True, "Morning mode should be active at start hour (6 AM)"
        
        # Test at end hour (11 AM) - should NOT be active (exclusive)
        eastern_11am = datetime(2025, 11, 20, 11, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch.object(scheduler, '_get_local_now', return_value=eastern_11am):
            scheduler.weather.check_precipitation_forecast = AsyncMock(
                return_value=(False, None, None)
            )
            result = await scheduler.should_turn_on_group('heattrax')
            assert result is False, "Morning mode should NOT be active at end hour (11 AM, exclusive)"
        
        # Test just before end hour (10:59 AM) - should be active
        eastern_1059am = datetime(2025, 11, 20, 10, 59, 0, tzinfo=ZoneInfo("America/New_York"))
        with patch.object(scheduler, '_get_local_now', return_value=eastern_1059am):
            result = await scheduler.should_turn_on_group('heattrax')
            assert result is True, "Morning mode should be active at 10:59 AM"
        
        # Cleanup
        Path(state_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_morning_mode_temp_above_threshold(self, config):
        """Test morning mode when temperature is above threshold."""
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Test case: 7:00 AM Eastern but temp is above threshold
        eastern_7am = datetime(2025, 11, 20, 7, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        
        with patch.object(scheduler, '_get_local_now', return_value=eastern_7am):
            # Mock weather service with temp ABOVE threshold
            scheduler.weather = AsyncMock()
            scheduler.weather.get_current_conditions = AsyncMock(return_value=(35.0, 0.0))
            scheduler.weather.check_precipitation_forecast = AsyncMock(
                return_value=(False, None, None)
            )
            
            # Mock device manager and state
            scheduler.device_manager = MagicMock()
            scheduler.device_manager.get_group_config = MagicMock(return_value={
                'automation': {
                    'weather_control': True,
                    'morning_mode': True,
                    'precipitation_control': True
                }
            })
            
            from state_manager import StateManager
            with tempfile.NamedTemporaryFile(delete=False) as f:
                state_file = f.name
            state = StateManager(state_file=state_file)
            scheduler.states['heattrax'] = state
            
            # Test should_turn_on_group
            result = await scheduler.should_turn_on_group('heattrax')
            
            # Should be False because temp (35°F) is above threshold (32°F)
            assert result is False, "Morning mode should NOT activate when temp is above threshold"
            
            # Cleanup
            Path(state_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_schedule_control_uses_local_timezone(self):
        """Test that schedule control uses configured timezone."""
        # Create a new config file with schedule control
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
location:
  latitude: 42.1456
  longitude: -71.5072
  timezone: "America/New_York"

weather_api:
  enabled: false

devices:
  credentials:
    username: "test_user"
    password: "test_password"
  groups:
    christmas_lights:
      enabled: true
      automation:
        weather_control: false
        schedule_control: true
      schedule:
        on_time: "17:00"
        off_time: "23:00"
      items:
        - name: "test_lights"
          ip_address: "192.168.1.110"

morning_mode:
  enabled: false

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
"""
            )
            temp_config_file = f.name
        
        try:
            config = Config(temp_config_file)
            scheduler = EnhancedScheduler(config, setup_mode=True)
            
            # Test case: 6:00 PM Eastern (should be ON, within 17:00-23:00)
            eastern_6pm = datetime(2025, 11, 20, 18, 0, 0, tzinfo=ZoneInfo("America/New_York"))
            
            with patch.object(scheduler, '_get_local_now', return_value=eastern_6pm):
                # Mock device manager and state
                scheduler.device_manager = MagicMock()
                scheduler.device_manager.get_group_config = MagicMock(return_value={
                    'automation': {
                        'weather_control': False,
                        'schedule_control': True
                    },
                    'schedule': {
                        'on_time': '17:00',
                        'off_time': '23:00'
                    }
                })
                
                from state_manager import StateManager
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    state_file = f.name
                state = StateManager(state_file=state_file)
                scheduler.states['christmas_lights'] = state
                
                # Test should_turn_on_group at 6 PM Eastern (within 17:00-23:00)
                result = await scheduler.should_turn_on_group('christmas_lights')
                
                assert result is True, "Schedule control should be active at 6 PM (within 17:00-23:00)"
                
                # Cleanup
                Path(state_file).unlink(missing_ok=True)
        finally:
            Path(temp_config_file).unlink(missing_ok=True)
    
    def test_timezone_initialization_fallback(self):
        """Test that invalid timezone falls back to UTC."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
location:
  latitude: 40.0
  longitude: -74.0
  timezone: "Invalid/Timezone"

devices:
  credentials:
    username: "test"
    password: "test"
  groups: {}

morning_mode:
  enabled: false

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

weather_api:
  enabled: true
  provider: "open-meteo"

logging:
  level: "INFO"

health_check:
  interval_hours: 24

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
            config = Config(config_path)
            scheduler = EnhancedScheduler(config, setup_mode=True)
            
            # Should fall back to UTC
            assert scheduler.timezone == ZoneInfo('UTC'), "Should fall back to UTC for invalid timezone"
        finally:
            Path(config_path).unlink(missing_ok=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

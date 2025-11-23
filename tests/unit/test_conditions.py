"""Unit tests for condition evaluation logic."""

import pytest
from datetime import datetime

from src.scheduler.schedule_evaluator import ScheduleEvaluator
from src.scheduler.schedule_types import Schedule


class TestTemperatureConditions:
    """Test temperature-based condition evaluation."""
    
    def test_temperature_below_threshold(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule activates when temperature is below threshold."""
        # Schedule requires temp <= 32
        weather = {
            'temperature_f': 25.0,
            'precipitation_active': True
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is True
    
    def test_temperature_at_threshold(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule activates when temperature equals threshold."""
        # Schedule requires temp <= 32
        weather = {
            'temperature_f': 32.0,
            'precipitation_active': True
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is True
    
    def test_temperature_above_threshold(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule does not activate when temperature is above threshold."""
        # Schedule requires temp <= 32
        weather = {
            'temperature_f': 33.0,
            'precipitation_active': True
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is False
    
    def test_temperature_missing_data(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule does not activate when temperature data is missing."""
        weather = {
            'precipitation_active': True
            # temperature_f is missing
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is False


class TestPrecipitationConditions:
    """Test precipitation-based condition evaluation."""
    
    def test_precipitation_required_and_active(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule activates when precipitation is required and active."""
        weather = {
            'temperature_f': 30.0,
            'precipitation_active': True
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is True
    
    def test_precipitation_required_but_not_active(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule does not activate when precipitation required but not active."""
        weather = {
            'temperature_f': 30.0,
            'precipitation_active': False
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is False
    
    def test_precipitation_not_wanted_but_active(
        self, schedule_evaluator, timezone_ny
    ):
        """Test schedule does not activate when precipitation not wanted but is active."""
        config = {
            'name': 'No Rain Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'precipitation_active': False},
            'safety': {}
        }
        schedule = Schedule(config)
        
        weather = {
            'temperature_f': 50.0,
            'precipitation_active': True
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, _, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is False
    
    def test_precipitation_not_wanted_and_not_active(
        self, schedule_evaluator, timezone_ny
    ):
        """Test schedule activates when precipitation not wanted and not active."""
        config = {
            'name': 'No Rain Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'precipitation_active': False},
            'safety': {}
        }
        schedule = Schedule(config)
        
        weather = {
            'temperature_f': 50.0,
            'precipitation_active': False
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is True


class TestMultipleConditions:
    """Test evaluation of multiple conditions together (AND logic)."""
    
    def test_all_conditions_met(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule activates when all conditions are met."""
        weather = {
            'temperature_f': 25.0,
            'precipitation_active': True
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is True
        assert active_schedule == schedule_with_conditions
    
    def test_one_condition_not_met(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule does not activate when one condition is not met."""
        # Temperature OK, but no precipitation
        weather = {
            'temperature_f': 25.0,
            'precipitation_active': False
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is False
    
    def test_both_conditions_not_met(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule does not activate when both conditions are not met."""
        weather = {
            'temperature_f': 50.0,
            'precipitation_active': False
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is False


class TestNoConditions:
    """Test schedules without conditions."""
    
    def test_no_conditions_always_evaluates_true(
        self, schedule_evaluator, schedule_basic, timezone_ny
    ):
        """Test schedule without conditions always evaluates to true (no weather check)."""
        # Even with no weather data
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time,
            weather_conditions=None
        )
        
        assert should_on is True
        assert active_schedule == schedule_basic
    
    def test_no_conditions_with_weather_data(
        self, schedule_evaluator, schedule_basic, timezone_ny
    ):
        """Test schedule without conditions ignores weather data."""
        weather = {
            'temperature_f': 100.0,  # Extreme values
            'precipitation_active': True
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is True


class TestWeatherOfflineHandling:
    """Test handling when weather service is offline."""
    
    def test_schedule_without_conditions_weather_offline(
        self, schedule_evaluator, schedule_basic, timezone_ny
    ):
        """Test schedule without conditions works when weather is offline."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time,
            weather_conditions=None,
            weather_offline=True
        )
        
        assert should_on is True
        assert active_schedule == schedule_basic
    
    def test_schedule_with_conditions_weather_offline_skipped(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule with conditions is skipped when weather is offline."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=None,
            weather_offline=True
        )
        
        assert should_on is False
        assert schedule is None
    
    def test_mixed_schedules_weather_offline(
        self, schedule_evaluator, schedule_basic, schedule_with_conditions, timezone_ny
    ):
        """Test that only schedules without conditions activate when weather is offline."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions, schedule_basic],
            current_time=test_time,
            weather_conditions=None,
            weather_offline=True
        )
        
        # Should activate the schedule without conditions
        assert should_on is True
        assert active_schedule == schedule_basic


class TestEdgeCaseConditions:
    """Test edge cases in condition evaluation."""
    
    def test_temperature_exactly_freezing(
        self, schedule_evaluator, timezone_ny
    ):
        """Test behavior at exactly freezing point."""
        config = {
            'name': 'Freezing Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'temperature_max': 32},
            'safety': {}
        }
        schedule = Schedule(config)
        
        weather = {
            'temperature_f': 32.0,
            'precipitation_active': False
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time,
            weather_conditions=weather
        )
        
        # At exactly 32°F, should activate (temperature_max is inclusive)
        assert should_on is True
    
    def test_temperature_very_cold(
        self, schedule_evaluator, timezone_ny
    ):
        """Test behavior with very cold temperatures."""
        config = {
            'name': 'Cold Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'temperature_max': 0},
            'safety': {}
        }
        schedule = Schedule(config)
        
        weather = {
            'temperature_f': -20.0,
            'precipitation_active': False
        }
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time,
            weather_conditions=weather
        )
        
        assert should_on is True
    
    def test_no_weather_data_with_conditions(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule with conditions when weather data is None."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=None,
            weather_offline=False
        )
        
        # Should not activate without weather data
        assert should_on is False


class TestConditionValidation:
    """Test validation of condition configurations."""
    
    def test_invalid_temperature_type(self):
        """Test that non-numeric temperature raises error."""
        config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'temperature_max': 'cold'}
        }
        
        with pytest.raises(ValueError, match="temperature_max must be a number"):
            Schedule(config)
    
    def test_invalid_precipitation_type(self):
        """Test that non-boolean precipitation raises error."""
        config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'precipitation_active': 'yes'}
        }
        
        with pytest.raises(ValueError, match="precipitation_active must be true or false"):
            Schedule(config)
    
    def test_temperature_out_of_reasonable_range(self):
        """Test that temperature outside reasonable range raises error."""
        config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'temperature_max': 200}  # Too high
        }
        
        with pytest.raises(ValueError, match="temperature_max must be between"):
            Schedule(config)

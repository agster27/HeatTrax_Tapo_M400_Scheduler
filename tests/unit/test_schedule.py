"""Unit tests for Schedule class."""

import pytest
from src.scheduler.schedule_types import (
    Schedule,
    ScheduleTimeType,
    SchedulePriority,
    validate_schedules,
    parse_schedules
)


class TestScheduleCreation:
    """Test Schedule object creation and validation."""
    
    def test_schedule_creation_clock_time(self, schedule_config_basic):
        """Test creating a schedule with clock-based times."""
        schedule = Schedule(schedule_config_basic)
        
        assert schedule.name == 'Morning Schedule'
        assert schedule.enabled is True
        assert schedule.priority == SchedulePriority.NORMAL
        assert schedule.days == [1, 2, 3, 4, 5]
        assert schedule.on_config['type'] == 'time'
        assert schedule.on_config['value'] == '06:00'
        assert schedule.off_config['type'] == 'time'
        assert schedule.off_config['value'] == '08:00'
    
    def test_schedule_creation_solar_time(self, schedule_config_solar):
        """Test creating a schedule with solar-based times."""
        schedule = Schedule(schedule_config_solar)
        
        assert schedule.name == 'Solar Schedule'
        assert schedule.on_config['type'] == 'sunset'
        assert schedule.on_config['offset'] == -30
        assert schedule.on_config['fallback'] == '18:00'
        assert schedule.off_config['type'] == 'sunrise'
        assert schedule.off_config['offset'] == 30
        assert schedule.off_config['fallback'] == '07:00'
    
    def test_schedule_creation_with_conditions(self, schedule_config_with_conditions):
        """Test creating a schedule with weather conditions."""
        schedule = Schedule(schedule_config_with_conditions)
        
        assert schedule.name == 'Cold Weather Schedule'
        assert schedule.priority == SchedulePriority.CRITICAL
        assert schedule.has_conditions() is True
        assert schedule.conditions['temperature_max'] == 32
        assert schedule.conditions['precipitation_active'] is True
    
    def test_schedule_creation_duration(self, schedule_config_duration):
        """Test creating a schedule with duration-based off time."""
        schedule = Schedule(schedule_config_duration)
        
        assert schedule.off_config['type'] == 'duration'
        assert schedule.off_config['value'] == 2.5
    
    def test_schedule_defaults(self):
        """Test schedule with minimal configuration uses defaults."""
        config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        schedule = Schedule(config)
        
        assert schedule.name == 'Unnamed Schedule'
        assert schedule.enabled is True
        assert schedule.priority == SchedulePriority.NORMAL
        assert schedule.days == [1, 2, 3, 4, 5, 6, 7]
        assert schedule.has_conditions() is False


class TestScheduleValidation:
    """Test schedule validation logic."""
    
    def test_invalid_missing_on_time(self):
        """Test that missing 'on' time raises ValueError."""
        config = {
            'name': 'Invalid',
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError, match="must have 'on' time"):
            Schedule(config)
    
    def test_invalid_missing_off_time(self):
        """Test that missing 'off' time raises ValueError."""
        config = {
            'name': 'Invalid',
            'on': {'type': 'time', 'value': '06:00'}
        }
        
        with pytest.raises(ValueError, match="must have 'off' time"):
            Schedule(config)
    
    def test_invalid_time_type(self):
        """Test that invalid time type raises ValueError."""
        config = {
            'on': {'type': 'invalid_type', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError, match="Invalid time type"):
            Schedule(config)
    
    def test_invalid_time_format(self):
        """Test that invalid time format raises ValueError."""
        config = {
            'on': {'type': 'time', 'value': '25:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError, match="Invalid time format"):
            Schedule(config)
    
    def test_invalid_solar_missing_fallback(self):
        """Test that solar time without fallback raises ValueError."""
        config = {
            'on': {'type': 'sunrise', 'offset': 30},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError, match="must have 'fallback'"):
            Schedule(config)
    
    def test_invalid_solar_offset_out_of_range(self):
        """Test that solar offset out of valid range raises ValueError."""
        config = {
            'on': {'type': 'sunrise', 'offset': 200, 'fallback': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError, match="offset must be between"):
            Schedule(config)
    
    def test_invalid_duration_for_on_time(self):
        """Test that duration type for 'on' time raises ValueError."""
        config = {
            'on': {'type': 'duration', 'value': 2},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError, match="Duration type only valid for 'off' time"):
            Schedule(config)
    
    def test_invalid_duration_negative(self):
        """Test that negative duration raises ValueError."""
        config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'duration', 'value': -1}
        }
        
        with pytest.raises(ValueError, match="Duration value must be a positive number"):
            Schedule(config)
    
    def test_invalid_days(self):
        """Test that invalid days specification raises ValueError."""
        config = {
            'days': [0, 8, 9],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError, match="Invalid days specification"):
            Schedule(config)
    
    def test_invalid_temperature_condition(self):
        """Test that invalid temperature condition raises ValueError."""
        config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {'temperature_max': 'not_a_number'}
        }
        
        with pytest.raises(ValueError, match="temperature_max must be a number"):
            Schedule(config)
    
    def test_invalid_precipitation_condition(self):
        """Test that invalid precipitation condition raises ValueError."""
        config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {'precipitation_active': 'yes'}
        }
        
        with pytest.raises(ValueError, match="precipitation_active must be true or false"):
            Schedule(config)


class TestScheduleMethods:
    """Test Schedule object methods."""
    
    def test_has_conditions_true(self, schedule_with_conditions):
        """Test has_conditions returns True when conditions exist."""
        assert schedule_with_conditions.has_conditions() is True
    
    def test_has_conditions_false(self, schedule_basic):
        """Test has_conditions returns False when no conditions."""
        assert schedule_basic.has_conditions() is False
    
    def test_get_max_runtime_hours_custom(self, schedule_with_conditions):
        """Test getting custom max runtime hours."""
        assert schedule_with_conditions.get_max_runtime_hours(default=10) == 6
    
    def test_get_max_runtime_hours_default(self, schedule_basic):
        """Test getting default max runtime hours."""
        assert schedule_basic.get_max_runtime_hours(default=10) == 10
    
    def test_get_cooldown_minutes_custom(self, schedule_with_conditions):
        """Test getting custom cooldown minutes."""
        assert schedule_with_conditions.get_cooldown_minutes(default=15) == 60
    
    def test_get_cooldown_minutes_default(self, schedule_basic):
        """Test getting default cooldown minutes."""
        assert schedule_basic.get_cooldown_minutes(default=15) == 15
    
    def test_to_dict(self, schedule_basic):
        """Test converting schedule to dictionary."""
        schedule_dict = schedule_basic.to_dict()
        
        assert schedule_dict['name'] == 'Morning Schedule'
        assert schedule_dict['enabled'] is True
        assert schedule_dict['priority'] == 'normal'
        assert schedule_dict['days'] == [1, 2, 3, 4, 5]
        assert 'on' in schedule_dict
        assert 'off' in schedule_dict
    
    def test_repr(self, schedule_basic):
        """Test string representation of schedule."""
        repr_str = repr(schedule_basic)
        
        assert 'Schedule' in repr_str
        assert 'Morning Schedule' in repr_str
        assert 'enabled=True' in repr_str


class TestScheduleValidationFunctions:
    """Test module-level validation functions."""
    
    def test_validate_schedules_valid(self, schedule_config_basic, schedule_config_solar):
        """Test validation passes for valid schedules."""
        schedules = [schedule_config_basic, schedule_config_solar]
        
        is_valid, errors = validate_schedules(schedules)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_schedules_invalid(self):
        """Test validation fails for invalid schedules."""
        schedules = [
            {'on': {'type': 'time', 'value': '06:00'}},  # Missing off
            {'off': {'type': 'time', 'value': '08:00'}}   # Missing on
        ]
        
        is_valid, errors = validate_schedules(schedules)
        
        assert is_valid is False
        assert len(errors) > 0
    
    def test_validate_schedules_not_list(self):
        """Test validation fails when schedules is not a list."""
        is_valid, errors = validate_schedules("not a list")
        
        assert is_valid is False
        assert len(errors) == 1
        assert "must be a list" in errors[0]
    
    def test_parse_schedules_valid(self, schedule_config_basic, schedule_config_solar):
        """Test parsing valid schedule configurations."""
        configs = [schedule_config_basic, schedule_config_solar]
        
        schedules = parse_schedules(configs)
        
        assert len(schedules) == 2
        assert all(isinstance(s, Schedule) for s in schedules)
        assert schedules[0].name == 'Morning Schedule'
        assert schedules[1].name == 'Solar Schedule'
    
    def test_parse_schedules_invalid_raises(self):
        """Test parsing invalid schedules raises ValueError."""
        configs = [
            {'on': {'type': 'time', 'value': '06:00'}}  # Missing off
        ]
        
        with pytest.raises(ValueError, match="Invalid schedule"):
            parse_schedules(configs)


class TestSchedulePriority:
    """Test priority handling."""
    
    def test_priority_critical(self):
        """Test critical priority schedule."""
        config = {
            'priority': 'critical',
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        schedule = Schedule(config)
        
        assert schedule.priority == SchedulePriority.CRITICAL
    
    def test_priority_normal(self):
        """Test normal priority schedule."""
        config = {
            'priority': 'normal',
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        schedule = Schedule(config)
        
        assert schedule.priority == SchedulePriority.NORMAL
    
    def test_priority_low(self):
        """Test low priority schedule."""
        config = {
            'priority': 'low',
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        schedule = Schedule(config)
        
        assert schedule.priority == SchedulePriority.LOW
    
    def test_priority_invalid_defaults_to_normal(self):
        """Test invalid priority defaults to normal with warning."""
        config = {
            'priority': 'super_important',
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        schedule = Schedule(config)
        
        # Should default to normal without raising error
        assert schedule.priority == SchedulePriority.NORMAL

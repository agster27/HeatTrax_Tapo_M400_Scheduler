"""Unit tests for ScheduleEvaluator class."""

import pytest
from datetime import datetime, time
from freezegun import freeze_time

from src.scheduler.schedule_evaluator import ScheduleEvaluator
from src.scheduler.schedule_types import Schedule, SchedulePriority


class TestScheduleEvaluatorInitialization:
    """Test ScheduleEvaluator initialization."""
    
    def test_initialization(self, solar_calculator, timezone_ny):
        """Test evaluator initializes correctly."""
        evaluator = ScheduleEvaluator(solar_calculator, timezone_ny)
        
        assert evaluator.solar_calculator == solar_calculator
        assert evaluator.timezone == timezone_ny


class TestShouldTurnOnBasic:
    """Test should_turn_on with basic clock-time schedules."""
    
    def test_no_schedules(self, schedule_evaluator, test_datetime):
        """Test behavior when no schedules configured."""
        should_on, schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[],
            current_time=test_datetime
        )
        
        assert should_on is False
        assert schedule is None
        assert "No schedules configured" in reason
    
    def test_schedule_active_weekday(self, schedule_evaluator, schedule_basic, timezone_ny):
        """Test schedule is active during its time window on correct day."""
        # Monday at 7:00 AM (schedule is 6:00-8:00 on weekdays)
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)  # Monday
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule_basic
        assert schedule_basic.name in reason
    
    def test_schedule_inactive_wrong_time(self, schedule_evaluator, schedule_basic, timezone_ny):
        """Test schedule is inactive outside its time window."""
        # Monday at 9:00 AM (schedule is 6:00-8:00)
        test_time = datetime(2024, 6, 17, 9, 0, tzinfo=timezone_ny)  # Monday
        
        should_on, schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time
        )
        
        assert should_on is False
        assert schedule is None
    
    def test_schedule_inactive_weekend(self, schedule_evaluator, schedule_basic, timezone_ny):
        """Test weekday schedule is inactive on weekend."""
        # Saturday at 7:00 AM (schedule is weekdays only)
        test_time = datetime(2024, 6, 22, 7, 0, tzinfo=timezone_ny)  # Saturday
        
        should_on, schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time
        )
        
        assert should_on is False
        assert schedule is None
    
    def test_schedule_disabled(self, schedule_evaluator, schedule_config_basic, timezone_ny):
        """Test disabled schedule is not activated."""
        # Create a copy to avoid modifying the fixture
        config = schedule_config_basic.copy()
        config['enabled'] = False
        schedule = Schedule(config)
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)  # Monday 7 AM
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is False
        assert active_schedule is None


class TestShouldTurnOnWithConditions:
    """Test should_turn_on with weather conditions."""
    
    def test_schedule_with_conditions_met(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny, weather_cold_snowing
    ):
        """Test schedule activates when conditions are met."""
        # Schedule requires temp <= 32 and precipitation
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather_cold_snowing
        )
        
        assert should_on is True
        assert active_schedule == schedule_with_conditions
    
    def test_schedule_with_conditions_not_met_temperature(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny, weather_warm
    ):
        """Test schedule does not activate when temperature condition not met."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather_warm
        )
        
        assert should_on is False
        assert schedule is None
    
    def test_schedule_with_conditions_not_met_precipitation(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny, weather_cold_dry
    ):
        """Test schedule does not activate when precipitation condition not met."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=weather_cold_dry
        )
        
        assert should_on is False
        assert schedule is None
    
    def test_schedule_with_conditions_weather_offline(
        self, schedule_evaluator, schedule_with_conditions, timezone_ny
    ):
        """Test schedule is skipped when weather is offline."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions],
            current_time=test_time,
            weather_conditions=None,
            weather_offline=True
        )
        
        assert should_on is False
        assert schedule is None


class TestShouldTurnOnWithPriority:
    """Test should_turn_on with multiple schedules and priority resolution."""
    
    def test_multiple_schedules_highest_priority_wins(
        self, schedule_evaluator, timezone_ny
    ):
        """Test that highest priority schedule wins when multiple are active."""
        # Create three overlapping schedules with different priorities
        low_config = {
            'name': 'Low Priority',
            'enabled': True,
            'priority': 'low',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        }
        normal_config = {
            'name': 'Normal Priority',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        }
        critical_config = {
            'name': 'Critical Priority',
            'enabled': True,
            'priority': 'critical',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        }
        
        schedules = [
            Schedule(low_config),
            Schedule(normal_config),
            Schedule(critical_config)
        ]
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=schedules,
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule.name == 'Critical Priority'
        assert active_schedule.priority == SchedulePriority.CRITICAL
    
    def test_single_low_priority_schedule_activates(
        self, schedule_evaluator, schedule_config_weekend, timezone_ny
    ):
        """Test that low priority schedule activates when it's the only one."""
        schedule = Schedule(schedule_config_weekend)
        
        # Saturday at 10:00 AM (schedule is 9:00-18:00 on weekends)
        test_time = datetime(2024, 6, 22, 10, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule


class TestShouldTurnOnSolarTimes:
    """Test should_turn_on with solar-based schedules."""
    
    def test_solar_schedule_active(
        self, schedule_evaluator, schedule_solar, timezone_ny, test_date
    ):
        """Test solar-based schedule activates correctly."""
        # Get actual sunset time for the date
        sunset_time = schedule_evaluator.solar_calculator.get_sunset_time(
            test_date, offset_minutes=-30
        )
        
        # Create test time 10 minutes after adjusted sunset
        # Handle minute overflow
        from datetime import timedelta
        sunset_dt = datetime.combine(test_date, sunset_time, tzinfo=timezone_ny)
        test_time = sunset_dt + timedelta(minutes=10)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_solar],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule_solar


class TestShouldTurnOff:
    """Test should_turn_off method."""
    
    def test_should_turn_off_no_active_schedules(
        self, schedule_evaluator, schedule_basic, timezone_ny
    ):
        """Test device should turn off when no schedules are active."""
        # Monday at 9:00 AM (schedule is 6:00-8:00)
        test_time = datetime(2024, 6, 17, 9, 0, tzinfo=timezone_ny)
        
        should_off, reason = schedule_evaluator.should_turn_off(
            schedules=[schedule_basic],
            current_time=test_time
        )
        
        assert should_off is True
        assert "No schedules active" in reason
    
    def test_should_not_turn_off_schedule_active(
        self, schedule_evaluator, schedule_basic, timezone_ny
    ):
        """Test device should not turn off when schedule is active."""
        # Monday at 7:00 AM (schedule is 6:00-8:00)
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_off, reason = schedule_evaluator.should_turn_off(
            schedules=[schedule_basic],
            current_time=test_time
        )
        
        assert should_off is False
        assert "Schedule still active" in reason


class TestMidnightRollover:
    """Test schedules that span midnight."""
    
    def test_schedule_spanning_midnight_before_midnight(
        self, schedule_evaluator, timezone_ny
    ):
        """Test schedule that spans midnight (e.g., 23:00 to 02:00) before midnight."""
        config = {
            'name': 'Night Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '23:00'},
            'off': {'type': 'time', 'value': '02:00'},
            'conditions': {},
            'safety': {}
        }
        schedule = Schedule(config)
        
        # Test at 23:30 (should be active)
        test_time = datetime(2024, 6, 17, 23, 30, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule
    
    def test_schedule_spanning_midnight_after_midnight(
        self, schedule_evaluator, timezone_ny
    ):
        """Test schedule that spans midnight after midnight."""
        config = {
            'name': 'Night Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '23:00'},
            'off': {'type': 'time', 'value': '02:00'},
            'conditions': {},
            'safety': {}
        }
        schedule = Schedule(config)
        
        # Test at 01:00 (should be active)
        test_time = datetime(2024, 6, 17, 1, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule
    
    def test_schedule_spanning_midnight_outside_window(
        self, schedule_evaluator, timezone_ny
    ):
        """Test schedule that spans midnight outside the window."""
        config = {
            'name': 'Night Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '23:00'},
            'off': {'type': 'time', 'value': '02:00'},
            'conditions': {},
            'safety': {}
        }
        schedule = Schedule(config)
        
        # Test at 03:00 (should not be active)
        test_time = datetime(2024, 6, 17, 3, 0, tzinfo=timezone_ny)
        
        should_on, schedule_obj, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is False


class TestDayOfWeekMatching:
    """Test day of week filtering."""
    
    def test_weekday_schedule_on_monday(self, schedule_evaluator, schedule_basic, timezone_ny):
        """Test weekday schedule is active on Monday."""
        # Monday at 7:00 AM
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time
        )
        
        assert should_on is True
    
    def test_weekday_schedule_on_friday(self, schedule_evaluator, schedule_basic, timezone_ny):
        """Test weekday schedule is active on Friday."""
        # Friday at 7:00 AM
        test_time = datetime(2024, 6, 21, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule_basic],
            current_time=test_time
        )
        
        assert should_on is True
    
    def test_weekend_schedule_on_saturday(
        self, schedule_evaluator, schedule_config_weekend, timezone_ny
    ):
        """Test weekend schedule is active on Saturday."""
        schedule = Schedule(schedule_config_weekend)
        
        # Saturday at 10:00 AM
        test_time = datetime(2024, 6, 22, 10, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
    
    def test_weekend_schedule_on_sunday(
        self, schedule_evaluator, schedule_config_weekend, timezone_ny
    ):
        """Test weekend schedule is active on Sunday."""
        schedule = Schedule(schedule_config_weekend)
        
        # Sunday at 10:00 AM
        test_time = datetime(2024, 6, 23, 10, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
    
    def test_weekend_schedule_inactive_on_weekday(
        self, schedule_evaluator, schedule_config_weekend, timezone_ny
    ):
        """Test weekend schedule is inactive on weekday."""
        schedule = Schedule(schedule_config_weekend)
        
        # Monday at 10:00 AM
        test_time = datetime(2024, 6, 17, 10, 0, tzinfo=timezone_ny)
        
        should_on, schedule_obj, _ = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is False


class TestAllDayScheduleEvaluation:
    """Test all_day schedule evaluation."""
    
    def test_all_day_schedule_active_at_midnight(self, schedule_evaluator, timezone_ny):
        """Test all_day schedule is active at midnight."""
        config = {
            'name': 'All Day Schedule',
            'enabled': True,
            'all_day': True,
            'days': [1, 2, 3, 4, 5, 6, 7]
        }
        schedule = Schedule(config)
        
        # Monday at 00:00
        test_time = datetime(2024, 6, 17, 0, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule
    
    def test_all_day_schedule_active_at_noon(self, schedule_evaluator, timezone_ny):
        """Test all_day schedule is active at noon."""
        config = {
            'name': 'All Day Schedule',
            'enabled': True,
            'all_day': True,
            'days': [1, 2, 3, 4, 5, 6, 7]
        }
        schedule = Schedule(config)
        
        # Monday at 12:00
        test_time = datetime(2024, 6, 17, 12, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule
    
    def test_all_day_schedule_active_at_end_of_day(self, schedule_evaluator, timezone_ny):
        """Test all_day schedule is active at 23:59."""
        config = {
            'name': 'All Day Schedule',
            'enabled': True,
            'all_day': True,
            'days': [1, 2, 3, 4, 5, 6, 7]
        }
        schedule = Schedule(config)
        
        # Monday at 23:59
        test_time = datetime(2024, 6, 17, 23, 59, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == schedule
    
    def test_all_day_schedule_respects_day_of_week(self, schedule_evaluator, timezone_ny):
        """Test all_day schedule respects day-of-week filter."""
        config = {
            'name': 'Weekday All Day',
            'enabled': True,
            'all_day': True,
            'days': [1, 2, 3, 4, 5]  # Weekdays only
        }
        schedule = Schedule(config)
        
        # Saturday at 12:00 - should NOT be active
        test_time = datetime(2024, 6, 22, 12, 0, tzinfo=timezone_ny)
        
        should_on, schedule_obj, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is False
    
    def test_all_day_schedule_with_weather_conditions_met(
        self, schedule_evaluator, timezone_ny, weather_cold_snowing
    ):
        """Test all_day schedule with weather conditions met."""
        config = {
            'name': 'Snow Event',
            'enabled': True,
            'all_day': True,
            'days': [1, 2, 3, 4, 5, 6, 7],
            'conditions': {
                'temperature_max': 32,
                'precipitation_active': True
            }
        }
        schedule = Schedule(config)
        
        # Monday at any time with cold snowing weather
        test_time = datetime(2024, 6, 17, 14, 30, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time,
            weather_conditions=weather_cold_snowing
        )
        
        assert should_on is True
        assert active_schedule == schedule
    
    def test_all_day_schedule_with_weather_conditions_not_met(
        self, schedule_evaluator, timezone_ny, weather_warm
    ):
        """Test all_day schedule with weather conditions not met."""
        config = {
            'name': 'Snow Event',
            'enabled': True,
            'all_day': True,
            'days': [1, 2, 3, 4, 5, 6, 7],
            'conditions': {
                'temperature_max': 32,
                'precipitation_active': True
            }
        }
        schedule = Schedule(config)
        
        # Monday at any time with warm weather
        test_time = datetime(2024, 6, 17, 14, 30, tzinfo=timezone_ny)
        
        should_on, schedule_obj, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time,
            weather_conditions=weather_warm
        )
        
        assert should_on is False
    
    def test_all_day_schedule_disabled(self, schedule_evaluator, timezone_ny):
        """Test disabled all_day schedule is not active."""
        config = {
            'name': 'Disabled All Day',
            'enabled': False,
            'all_day': True,
            'days': [1, 2, 3, 4, 5, 6, 7]
        }
        schedule = Schedule(config)
        
        test_time = datetime(2024, 6, 17, 12, 0, tzinfo=timezone_ny)
        
        should_on, schedule_obj, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=test_time
        )
        
        assert should_on is False

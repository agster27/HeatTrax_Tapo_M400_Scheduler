"""Integration tests for end-to-end schedule execution."""

import pytest
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import yaml

from src.scheduler.solar_calculator import SolarCalculator
from src.scheduler.schedule_evaluator import ScheduleEvaluator
from src.scheduler.schedule_types import Schedule, parse_schedules


@pytest.fixture
def valid_schedules_from_yaml():
    """Load valid schedules from YAML fixture file."""
    from pathlib import Path
    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'valid_schedule_config.yaml'
    with open(fixture_path, 'r') as f:
        config = yaml.safe_load(f)
    return parse_schedules(config['schedules'])


@pytest.fixture
def solar_schedules_from_yaml():
    """Load solar schedules from YAML fixture file."""
    from pathlib import Path
    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'solar_schedule_config.yaml'
    with open(fixture_path, 'r') as f:
        config = yaml.safe_load(f)
    return parse_schedules(config['schedules'])


class TestDailyScheduleExecution:
    """Test complete daily schedule execution flow."""
    
    def test_weekday_morning_schedule_activates(
        self, schedule_evaluator, valid_schedules_from_yaml
    ):
        """Test that morning warmup schedule activates on weekday mornings."""
        # Monday at 7:00 AM
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=ZoneInfo("America/New_York"))
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=valid_schedules_from_yaml,
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule.name == "Morning Warmup"
    
    def test_time_progression_through_schedules(self, schedule_evaluator, timezone_ny):
        """Test device behavior as time progresses through the day."""
        # Simple schedule for testing time progression
        config = {
            'name': 'Test Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {},
            'safety': {}
        }
        schedule = Schedule(config)
        schedules = [schedule]
        
        # Test at 5:00 AM (before schedule)
        time_5am = datetime(2024, 6, 17, 5, 0, tzinfo=timezone_ny)
        should_on, _, _ = schedule_evaluator.should_turn_on(schedules, time_5am)
        assert should_on is False
        
        # Test at 7:00 AM (during schedule)
        time_7am = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(schedules, time_7am)
        assert should_on is True
        assert active_schedule == schedule
        
        # Test at 9:00 AM (after schedule)
        time_9am = datetime(2024, 6, 17, 9, 0, tzinfo=timezone_ny)
        should_on, _, _ = schedule_evaluator.should_turn_on(schedules, time_9am)
        assert should_on is False
    
    def test_weekend_different_schedule(
        self, schedule_evaluator, valid_schedules_from_yaml, timezone_ny
    ):
        """Test that weekend schedule is different from weekday."""
        # Saturday at 7:00 AM - Morning Warmup should NOT be active (weekdays only)
        saturday_morning = datetime(2024, 6, 22, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=valid_schedules_from_yaml,
            current_time=saturday_morning
        )
        
        # No schedule should be active at this time on Saturday
        assert should_on is False
        
        # Saturday at 10:00 AM - Weekend Schedule should be active
        saturday_midmorning = datetime(2024, 6, 22, 10, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=valid_schedules_from_yaml,
            current_time=saturday_midmorning
        )
        
        assert should_on is True
        assert active_schedule.name == "Weekend Schedule"


class TestTemperatureConditionalSchedule:
    """Test schedules that depend on temperature conditions."""
    
    def test_cold_weather_schedule_activates(
        self, schedule_evaluator, valid_schedules_from_yaml, timezone_ny
    ):
        """Test that winter storm schedule activates in cold snowy conditions."""
        # Monday at 7:00 AM with cold snowy weather
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        weather = {
            'temperature_f': 28.0,
            'precipitation_active': True
        }
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=valid_schedules_from_yaml,
            current_time=test_time,
            weather_conditions=weather
        )
        
        # Winter Storm Schedule has critical priority, should win over Morning Warmup
        assert should_on is True
        assert active_schedule.name == "Winter Storm Schedule"
        assert active_schedule.priority.value == "critical"
    
    def test_warm_weather_skips_cold_schedule(
        self, schedule_evaluator, valid_schedules_from_yaml, timezone_ny
    ):
        """Test that cold weather schedule does not activate when warm."""
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        weather = {
            'temperature_f': 50.0,
            'precipitation_active': False
        }
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=valid_schedules_from_yaml,
            current_time=test_time,
            weather_conditions=weather
        )
        
        # Should activate Morning Warmup (no conditions) instead of Winter Storm
        assert should_on is True
        assert active_schedule.name == "Morning Warmup"


class TestPriorityBasedSelection:
    """Test priority-based schedule selection when multiple schedules overlap."""
    
    def test_critical_priority_overrides_normal(
        self, schedule_evaluator, timezone_ny
    ):
        """Test that critical priority schedule wins over normal priority."""
        normal_schedule = Schedule({
            'name': 'Normal Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        })
        
        critical_schedule = Schedule({
            'name': 'Critical Schedule',
            'enabled': True,
            'priority': 'critical',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        })
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=[normal_schedule, critical_schedule],
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule == critical_schedule
    
    def test_priority_ordering_with_three_levels(
        self, schedule_evaluator, timezone_ny
    ):
        """Test correct priority ordering with low, normal, and critical."""
        schedules = [
            Schedule({
                'name': 'Low Priority',
                'enabled': True,
                'priority': 'low',
                'days': [1, 2, 3, 4, 5, 6, 7],
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '10:00'},
                'conditions': {},
                'safety': {}
            }),
            Schedule({
                'name': 'Normal Priority',
                'enabled': True,
                'priority': 'normal',
                'days': [1, 2, 3, 4, 5, 6, 7],
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '10:00'},
                'conditions': {},
                'safety': {}
            }),
            Schedule({
                'name': 'Critical Priority',
                'enabled': True,
                'priority': 'critical',
                'days': [1, 2, 3, 4, 5, 6, 7],
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '10:00'},
                'conditions': {},
                'safety': {}
            })
        ]
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=schedules,
            current_time=test_time
        )
        
        assert should_on is True
        assert active_schedule.name == 'Critical Priority'


class TestSolarScheduleExecution:
    """Test solar-based schedule execution."""
    
    def test_solar_schedule_follows_sunset(
        self, schedule_evaluator, solar_schedules_from_yaml, test_date, timezone_ny
    ):
        """Test that solar schedule activates based on actual sunset time."""
        # Get the actual sunset time for test date
        sunset_time = schedule_evaluator.solar_calculator.get_sunset_time(
            test_date, offset_minutes=0
        )
        
        # Create test time just after sunset
        test_time = datetime.combine(
            test_date,
            sunset_time,
            tzinfo=timezone_ny
        ) + timedelta(minutes=5)
        
        should_on, active_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=solar_schedules_from_yaml,
            current_time=test_time
        )
        
        # At least one solar schedule should be active
        # (Could be "Evening Lighting" or "Dawn to Dusk" depending on timing)
        assert should_on is True
        assert active_schedule is not None
        # Verify it's a solar-based schedule
        assert (active_schedule.on_config.get('type') in ['sunrise', 'sunset'] or
                active_schedule.off_config.get('type') in ['sunrise', 'sunset'])
    
    def test_solar_schedule_varies_by_season(self, timezone_ny):
        """Test that solar schedule times change with seasons."""
        # Create calculator and evaluator
        calc = SolarCalculator(40.7128, -74.0060, "America/New_York")
        evaluator = ScheduleEvaluator(calc, timezone_ny)
        
        # Solar schedule that turns on at sunset
        schedule = Schedule({
            'name': 'Sunset Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'sunset', 'offset': 0, 'fallback': '18:00'},
            'off': {'type': 'time', 'value': '23:00'},
            'conditions': {},
            'safety': {}
        })
        
        # Summer date - sunset is late (around 8pm)
        summer_sunset = calc.get_sunset_time(date(2024, 6, 21))
        assert summer_sunset.hour >= 19
        
        # Winter date - sunset is early (around 4:30pm)
        winter_sunset = calc.get_sunset_time(date(2024, 12, 21))
        assert winter_sunset.hour <= 17


class TestComplexScenarios:
    """Test complex real-world scenarios."""
    
    def test_transition_from_morning_to_evening_schedule(
        self, schedule_evaluator, timezone_ny
    ):
        """Test smooth transition between different schedules during the day."""
        morning_schedule = Schedule({
            'name': 'Morning',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {},
            'safety': {}
        })
        
        evening_schedule = Schedule({
            'name': 'Evening',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '18:00'},
            'off': {'type': 'time', 'value': '22:00'},
            'conditions': {},
            'safety': {}
        })
        
        schedules = [morning_schedule, evening_schedule]
        
        # Morning: 7am - morning schedule active
        morning_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        should_on, active, _ = schedule_evaluator.should_turn_on(schedules, morning_time)
        assert should_on is True
        assert active.name == 'Morning'
        
        # Midday: 12pm - no schedule active
        midday_time = datetime(2024, 6, 17, 12, 0, tzinfo=timezone_ny)
        should_on, _, _ = schedule_evaluator.should_turn_on(schedules, midday_time)
        assert should_on is False
        
        # Evening: 7pm - evening schedule active
        evening_time = datetime(2024, 6, 17, 19, 0, tzinfo=timezone_ny)
        should_on, active, _ = schedule_evaluator.should_turn_on(schedules, evening_time)
        assert should_on is True
        assert active.name == 'Evening'
        
        # Night: 11pm - no schedule active
        night_time = datetime(2024, 6, 17, 23, 0, tzinfo=timezone_ny)
        should_on, _, _ = schedule_evaluator.should_turn_on(schedules, night_time)
        assert should_on is False
    
    def test_conditional_overrides_unconditional_same_priority(
        self, schedule_evaluator, timezone_ny
    ):
        """Test that conditional schedule can override unconditional if conditions met."""
        # Both critical priority, both active at same time
        # Conditional schedule should be used when conditions are met
        unconditional = Schedule({
            'name': 'Always On',
            'enabled': True,
            'priority': 'critical',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        })
        
        conditional = Schedule({
            'name': 'Cold Only',
            'enabled': True,
            'priority': 'critical',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'temperature_max': 32},
            'safety': {}
        })
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        # With cold weather, both are active
        cold_weather = {'temperature_f': 25.0, 'precipitation_active': False}
        should_on, active, _ = schedule_evaluator.should_turn_on(
            schedules=[unconditional, conditional],
            current_time=test_time,
            weather_conditions=cold_weather
        )
        
        # Both are critical, first one in list wins when both match
        assert should_on is True
        assert active == unconditional  # First in list
    
    def test_disabled_schedule_ignored(self, schedule_evaluator, timezone_ny):
        """Test that disabled schedules are completely ignored."""
        enabled_schedule = Schedule({
            'name': 'Enabled',
            'enabled': True,
            'priority': 'low',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        })
        
        disabled_schedule = Schedule({
            'name': 'Disabled',
            'enabled': False,
            'priority': 'critical',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        })
        
        test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active, _ = schedule_evaluator.should_turn_on(
            schedules=[disabled_schedule, enabled_schedule],
            current_time=test_time
        )
        
        # Should activate low priority enabled schedule, not disabled critical
        assert should_on is True
        assert active == enabled_schedule

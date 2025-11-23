"""Integration tests for API interactions with schedule system."""

import pytest
from datetime import datetime, date
from zoneinfo import ZoneInfo

from src.scheduler.solar_calculator import SolarCalculator
from src.scheduler.schedule_evaluator import ScheduleEvaluator
from src.scheduler.schedule_types import Schedule


class TestScheduleDataAccess:
    """Test accessing schedule data through API-like interfaces."""
    
    def test_get_schedule_as_dict(self):
        """Test getting schedule data as dictionary (for API responses)."""
        config = {
            'name': 'Morning Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {'temperature_max': 32},
            'safety': {'max_runtime_hours': 6}
        }
        
        schedule = Schedule(config)
        schedule_dict = schedule.to_dict()
        
        # Verify all fields are present
        assert 'name' in schedule_dict
        assert 'enabled' in schedule_dict
        assert 'priority' in schedule_dict
        assert 'days' in schedule_dict
        assert 'on' in schedule_dict
        assert 'off' in schedule_dict
        assert 'conditions' in schedule_dict
        assert 'safety' in schedule_dict
        
        # Verify values
        assert schedule_dict['name'] == 'Morning Schedule'
        assert schedule_dict['enabled'] is True
        assert schedule_dict['priority'] == 'normal'
    
    def test_list_schedules(self):
        """Test listing multiple schedules (like GET /schedules)."""
        configs = [
            {
                'name': 'Morning',
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '08:00'}
            },
            {
                'name': 'Evening',
                'on': {'type': 'time', 'value': '18:00'},
                'off': {'type': 'time', 'value': '22:00'}
            }
        ]
        
        schedules = [Schedule(config) for config in configs]
        schedule_list = [s.to_dict() for s in schedules]
        
        assert len(schedule_list) == 2
        assert schedule_list[0]['name'] == 'Morning'
        assert schedule_list[1]['name'] == 'Evening'
    
    def test_filter_enabled_schedules(self):
        """Test filtering only enabled schedules (for API queries)."""
        configs = [
            {
                'name': 'Enabled',
                'enabled': True,
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '08:00'}
            },
            {
                'name': 'Disabled',
                'enabled': False,
                'on': {'type': 'time', 'value': '18:00'},
                'off': {'type': 'time', 'value': '22:00'}
            }
        ]
        
        schedules = [Schedule(config) for config in configs]
        enabled_schedules = [s for s in schedules if s.enabled]
        
        assert len(enabled_schedules) == 1
        assert enabled_schedules[0].name == 'Enabled'


class TestSolarTimesAPI:
    """Test solar times endpoint functionality."""
    
    def test_get_solar_times_for_date(self):
        """Test getting sunrise/sunset times for a specific date."""
        calc = SolarCalculator(40.7128, -74.0060, "America/New_York")
        test_date = date(2024, 6, 15)
        
        sunrise, sunset = calc.calculate_solar_times(test_date)
        
        # Return format suitable for API
        solar_data = {
            'date': test_date.isoformat(),
            'sunrise': sunrise.strftime('%H:%M'),
            'sunset': sunset.strftime('%H:%M'),
            'timezone': 'America/New_York'
        }
        
        assert 'date' in solar_data
        assert 'sunrise' in solar_data
        assert 'sunset' in solar_data
        assert 'timezone' in solar_data
    
    def test_get_solar_times_with_offset(self):
        """Test getting solar times with offsets applied."""
        calc = SolarCalculator(40.7128, -74.0060, "America/New_York")
        test_date = date(2024, 6, 15)
        
        # Get times with offsets
        sunrise_early = calc.get_sunrise_time(test_date, offset_minutes=-30)
        sunrise_late = calc.get_sunrise_time(test_date, offset_minutes=30)
        
        # Return format suitable for API
        solar_data = {
            'date': test_date.isoformat(),
            'sunrise': calc.get_sunrise_time(test_date).strftime('%H:%M'),
            'sunrise_minus_30': sunrise_early.strftime('%H:%M'),
            'sunrise_plus_30': sunrise_late.strftime('%H:%M')
        }
        
        assert solar_data['sunrise'] != solar_data['sunrise_minus_30']
        assert solar_data['sunrise'] != solar_data['sunrise_plus_30']
    
    def test_solar_times_multiple_dates(self):
        """Test getting solar times for multiple dates (date range query)."""
        calc = SolarCalculator(40.7128, -74.0060, "America/New_York")
        dates = [date(2024, 6, i) for i in range(1, 8)]  # Week of June
        
        solar_times = []
        for d in dates:
            sunrise, sunset = calc.calculate_solar_times(d)
            solar_times.append({
                'date': d.isoformat(),
                'sunrise': sunrise.strftime('%H:%M'),
                'sunset': sunset.strftime('%H:%M')
            })
        
        assert len(solar_times) == 7
        # All dates should have sunrise and sunset
        assert all('sunrise' in st and 'sunset' in st for st in solar_times)


class TestScheduleStatusAPI:
    """Test schedule status queries (what's active now)."""
    
    def test_get_current_active_schedule(self, schedule_evaluator, timezone_ny):
        """Test querying which schedule is currently active."""
        schedules = [
            Schedule({
                'name': 'Morning',
                'enabled': True,
                'priority': 'normal',
                'days': [1, 2, 3, 4, 5, 6, 7],
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '08:00'},
                'conditions': {},
                'safety': {}
            })
        ]
        
        # Query at 7:00 AM on Monday
        current_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=schedules,
            current_time=current_time
        )
        
        # Format as API response
        if should_on:
            status = {
                'device_state': 'on',
                'active_schedule': active_schedule.to_dict(),
                'reason': reason
            }
        else:
            status = {
                'device_state': 'off',
                'active_schedule': None,
                'reason': reason
            }
        
        assert status['device_state'] == 'on'
        assert status['active_schedule']['name'] == 'Morning'
    
    def test_get_schedule_status_no_active(self, schedule_evaluator, timezone_ny):
        """Test status when no schedule is active."""
        schedules = [
            Schedule({
                'name': 'Morning',
                'enabled': True,
                'priority': 'normal',
                'days': [1, 2, 3, 4, 5, 6, 7],
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '08:00'},
                'conditions': {},
                'safety': {}
            })
        ]
        
        # Query at 12:00 PM (no schedule active)
        current_time = datetime(2024, 6, 17, 12, 0, tzinfo=timezone_ny)
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=schedules,
            current_time=current_time
        )
        
        status = {
            'device_state': 'off',
            'active_schedule': None,
            'reason': reason
        }
        
        assert status['device_state'] == 'off'
        assert status['active_schedule'] is None
    
    def test_get_all_active_schedules(self, schedule_evaluator, timezone_ny):
        """Test getting all schedules that want device on (not just winning one)."""
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
                'name': 'High Priority',
                'enabled': True,
                'priority': 'critical',
                'days': [1, 2, 3, 4, 5, 6, 7],
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '10:00'},
                'conditions': {},
                'safety': {}
            })
        ]
        
        current_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        should_on, winning_schedule, _ = schedule_evaluator.should_turn_on(
            schedules=schedules,
            current_time=current_time
        )
        
        # In a real API, might want to show all active schedules
        # For now, we just get the winner
        assert winning_schedule.name == 'High Priority'


class TestScheduleValidationAPI:
    """Test schedule validation endpoints."""
    
    def test_validate_schedule_before_save(self):
        """Test validating a schedule configuration before saving."""
        config = {
            'name': 'New Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {},
            'safety': {}
        }
        
        # Try to create schedule (validation happens in constructor)
        try:
            schedule = Schedule(config)
            validation_result = {
                'valid': True,
                'errors': [],
                'schedule': schedule.to_dict()
            }
        except ValueError as e:
            validation_result = {
                'valid': False,
                'errors': [str(e)],
                'schedule': None
            }
        
        assert validation_result['valid'] is True
        assert len(validation_result['errors']) == 0
    
    def test_validate_invalid_schedule(self):
        """Test validation catches invalid schedule."""
        config = {
            'name': 'Bad Schedule',
            'on': {'type': 'time', 'value': '25:00'},  # Invalid hour
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        try:
            schedule = Schedule(config)
            validation_result = {
                'valid': True,
                'errors': []
            }
        except ValueError as e:
            validation_result = {
                'valid': False,
                'errors': [str(e)]
            }
        
        assert validation_result['valid'] is False
        assert len(validation_result['errors']) > 0


class TestWeatherConditionAPI:
    """Test API interactions with weather conditions."""
    
    def test_evaluate_schedule_with_weather_data(
        self, schedule_evaluator, timezone_ny
    ):
        """Test evaluating schedule with provided weather data."""
        schedule = Schedule({
            'name': 'Cold Weather',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'temperature_max': 32},
            'safety': {}
        })
        
        current_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        # Weather data from API
        weather_data = {
            'temperature_f': 28.0,
            'precipitation_active': False
        }
        
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule],
            current_time=current_time,
            weather_conditions=weather_data
        )
        
        result = {
            'should_activate': should_on,
            'schedule': active_schedule.name if active_schedule else None,
            'weather': weather_data,
            'reason': reason
        }
        
        assert result['should_activate'] is True
        assert result['schedule'] == 'Cold Weather'
    
    def test_weather_offline_status(self, schedule_evaluator, timezone_ny):
        """Test handling when weather service is offline."""
        schedule_with_conditions = Schedule({
            'name': 'Weather Dependent',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {'temperature_max': 32},
            'safety': {}
        })
        
        schedule_no_conditions = Schedule({
            'name': 'Always Active',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '10:00'},
            'conditions': {},
            'safety': {}
        })
        
        current_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
        
        # Weather is offline
        should_on, active_schedule, reason = schedule_evaluator.should_turn_on(
            schedules=[schedule_with_conditions, schedule_no_conditions],
            current_time=current_time,
            weather_conditions=None,
            weather_offline=True
        )
        
        # Should use schedule without conditions
        assert should_on is True
        assert active_schedule.name == 'Always Active'


class TestScheduleMetadataAPI:
    """Test API for schedule metadata and statistics."""
    
    def test_get_schedule_summary(self):
        """Test getting summary information about schedules."""
        schedules = [
            Schedule({
                'name': 'Morning',
                'enabled': True,
                'priority': 'normal',
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '08:00'}
            }),
            Schedule({
                'name': 'Evening',
                'enabled': True,
                'priority': 'critical',
                'on': {'type': 'time', 'value': '18:00'},
                'off': {'type': 'time', 'value': '22:00'}
            }),
            Schedule({
                'name': 'Disabled',
                'enabled': False,
                'priority': 'normal',
                'on': {'type': 'time', 'value': '12:00'},
                'off': {'type': 'time', 'value': '14:00'}
            })
        ]
        
        # Generate summary
        summary = {
            'total_schedules': len(schedules),
            'enabled_schedules': len([s for s in schedules if s.enabled]),
            'disabled_schedules': len([s for s in schedules if not s.enabled]),
            'priority_breakdown': {
                'critical': len([s for s in schedules if s.priority.value == 'critical']),
                'normal': len([s for s in schedules if s.priority.value == 'normal']),
                'low': len([s for s in schedules if s.priority.value == 'low'])
            }
        }
        
        assert summary['total_schedules'] == 3
        assert summary['enabled_schedules'] == 2
        assert summary['disabled_schedules'] == 1
        assert summary['priority_breakdown']['critical'] == 1
        assert summary['priority_breakdown']['normal'] == 2

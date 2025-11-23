"""Pytest fixtures and configuration for testing the scheduler system."""

import pytest
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
from typing import Dict, Any

from src.scheduler.solar_calculator import SolarCalculator
from src.scheduler.schedule_evaluator import ScheduleEvaluator
from src.scheduler.schedule_types import Schedule


# ============================================================================
# Time and Location Fixtures
# ============================================================================

@pytest.fixture
def timezone_ny():
    """New York timezone."""
    return ZoneInfo("America/New_York")


@pytest.fixture
def timezone_utc():
    """UTC timezone."""
    return ZoneInfo("UTC")


@pytest.fixture
def test_date():
    """A fixed test date for deterministic testing."""
    return date(2024, 6, 15)  # Summer date


@pytest.fixture
def test_date_winter():
    """A winter test date."""
    return date(2024, 12, 15)


@pytest.fixture
def test_datetime(timezone_ny, test_date):
    """A fixed test datetime for deterministic testing."""
    return datetime.combine(test_date, time(14, 30), tzinfo=timezone_ny)


@pytest.fixture
def location_ny():
    """New York location coordinates."""
    return {
        'latitude': 40.7128,
        'longitude': -74.0060,
        'timezone': 'America/New_York'
    }


@pytest.fixture
def location_alaska():
    """Alaska location (edge case for solar times)."""
    return {
        'latitude': 64.2008,
        'longitude': -149.4937,
        'timezone': 'America/Anchorage'
    }


# ============================================================================
# Solar Calculator Fixtures
# ============================================================================

@pytest.fixture
def solar_calculator(location_ny):
    """Create a solar calculator with NY location."""
    return SolarCalculator(
        latitude=location_ny['latitude'],
        longitude=location_ny['longitude'],
        timezone=location_ny['timezone']
    )


@pytest.fixture
def solar_calculator_alaska(location_alaska):
    """Create a solar calculator with Alaska location (edge cases)."""
    return SolarCalculator(
        latitude=location_alaska['latitude'],
        longitude=location_alaska['longitude'],
        timezone=location_alaska['timezone']
    )


# ============================================================================
# Schedule Evaluator Fixtures
# ============================================================================

@pytest.fixture
def schedule_evaluator(solar_calculator, timezone_ny):
    """Create a schedule evaluator."""
    return ScheduleEvaluator(
        solar_calculator=solar_calculator,
        timezone=timezone_ny
    )


# ============================================================================
# Schedule Configuration Fixtures
# ============================================================================

@pytest.fixture
def schedule_config_basic():
    """Basic clock-time schedule configuration."""
    return {
        'name': 'Morning Schedule',
        'enabled': True,
        'priority': 'normal',
        'days': [1, 2, 3, 4, 5],  # Weekdays
        'on': {
            'type': 'time',
            'value': '06:00'
        },
        'off': {
            'type': 'time',
            'value': '08:00'
        },
        'conditions': {},
        'safety': {}
    }


@pytest.fixture
def schedule_config_solar():
    """Solar-time based schedule configuration."""
    return {
        'name': 'Solar Schedule',
        'enabled': True,
        'priority': 'normal',
        'days': [1, 2, 3, 4, 5, 6, 7],
        'on': {
            'type': 'sunset',
            'offset': -30,  # 30 minutes before sunset
            'fallback': '18:00'
        },
        'off': {
            'type': 'sunrise',
            'offset': 30,  # 30 minutes after sunrise
            'fallback': '07:00'
        },
        'conditions': {},
        'safety': {}
    }


@pytest.fixture
def schedule_config_with_conditions():
    """Schedule with weather conditions."""
    return {
        'name': 'Cold Weather Schedule',
        'enabled': True,
        'priority': 'critical',
        'days': [1, 2, 3, 4, 5, 6, 7],
        'on': {
            'type': 'time',
            'value': '05:00'
        },
        'off': {
            'type': 'time',
            'value': '10:00'
        },
        'conditions': {
            'temperature_max': 32,
            'precipitation_active': True
        },
        'safety': {
            'max_runtime_hours': 6,
            'cooldown_minutes': 60
        }
    }


@pytest.fixture
def schedule_config_duration():
    """Schedule with duration-based off time."""
    return {
        'name': 'Duration Schedule',
        'enabled': True,
        'priority': 'normal',
        'days': [1, 2, 3, 4, 5, 6, 7],
        'on': {
            'type': 'time',
            'value': '06:00'
        },
        'off': {
            'type': 'duration',
            'value': 2.5  # 2.5 hours
        },
        'conditions': {},
        'safety': {}
    }


@pytest.fixture
def schedule_config_weekend():
    """Weekend-only schedule."""
    return {
        'name': 'Weekend Schedule',
        'enabled': True,
        'priority': 'low',
        'days': [6, 7],  # Saturday, Sunday
        'on': {
            'type': 'time',
            'value': '09:00'
        },
        'off': {
            'type': 'time',
            'value': '18:00'
        },
        'conditions': {},
        'safety': {}
    }


# ============================================================================
# Schedule Object Fixtures
# ============================================================================

@pytest.fixture
def schedule_basic(schedule_config_basic):
    """Create a basic Schedule object."""
    return Schedule(schedule_config_basic)


@pytest.fixture
def schedule_solar(schedule_config_solar):
    """Create a solar Schedule object."""
    return Schedule(schedule_config_solar)


@pytest.fixture
def schedule_with_conditions(schedule_config_with_conditions):
    """Create a Schedule object with conditions."""
    return Schedule(schedule_config_with_conditions)


# ============================================================================
# Weather Condition Fixtures
# ============================================================================

@pytest.fixture
def weather_cold_dry():
    """Weather conditions: cold and dry."""
    return {
        'temperature_f': 28.0,
        'precipitation_active': False
    }


@pytest.fixture
def weather_cold_snowing():
    """Weather conditions: cold with snow."""
    return {
        'temperature_f': 25.0,
        'precipitation_active': True
    }


@pytest.fixture
def weather_warm():
    """Weather conditions: warm."""
    return {
        'temperature_f': 55.0,
        'precipitation_active': False
    }


@pytest.fixture
def weather_freezing_rain():
    """Weather conditions: freezing rain."""
    return {
        'temperature_f': 32.0,
        'precipitation_active': True
    }


# ============================================================================
# Mock Time Provider
# ============================================================================

class MockTimeProvider:
    """Mock time provider for testing time-dependent code."""
    
    def __init__(self, current_time: datetime):
        self._current_time = current_time
    
    def now(self) -> datetime:
        """Get current mock time."""
        return self._current_time
    
    def set_time(self, new_time: datetime):
        """Set new mock time."""
        self._current_time = new_time
    
    def advance(self, **kwargs):
        """Advance time by timedelta kwargs."""
        from datetime import timedelta
        self._current_time += timedelta(**kwargs)


@pytest.fixture
def mock_time_provider(test_datetime):
    """Create a mock time provider."""
    return MockTimeProvider(test_datetime)


# ============================================================================
# Utility Functions
# ============================================================================

def create_schedule_list(schedule_configs):
    """Helper to create list of Schedule objects from configs."""
    return [Schedule(config) for config in schedule_configs]

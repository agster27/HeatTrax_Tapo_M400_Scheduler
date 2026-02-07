# Testing Guide

This document describes the comprehensive testing suite for the HeatTrax Tapo M400 Scheduler.

## Overview

The project includes a comprehensive test suite covering unit tests and integration tests for the scheduler system:
- **Unit tests** for core components (Schedule, ScheduleEvaluator, SolarCalculator, Conditions)
- **Integration tests** for end-to-end behavior and API interactions

## Quick Start

### Install Testing Dependencies

```bash
pip install pytest pytest-cov pytest-mock pytest-asyncio freezegun
```

### Run All Tests

```bash
# Run all tests with coverage
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

### Run Specific Test Suites

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_schedule.py

# Specific test class
pytest tests/unit/test_schedule.py::TestScheduleCreation

# Specific test
pytest tests/unit/test_schedule.py::TestScheduleCreation::test_schedule_creation_clock_time
```

## Test Organization

### Unit Tests (`tests/unit/`)

#### `test_schedule.py` (44 tests)
Tests for the Schedule class:
- Schedule creation with various time types (clock, solar, duration)
- Configuration validation (time formats, priorities, days, conditions)
- Schedule methods (has_conditions, get_runtime, to_dict)
- Priority handling (critical, normal, low)
- Edge cases and error handling

#### `test_schedule_evaluator.py` (27 tests)
Tests for schedule evaluation logic:
- Basic schedule activation/deactivation
- Weather condition evaluation
- Priority-based conflict resolution
- Solar time-based schedules
- Day-of-week matching
- Midnight rollover scenarios

#### `test_solar_calculator.py` (18 tests)
Tests for solar time calculations:
- Sunrise/sunset calculation for different dates
- Offset handling (before/after sunrise/sunset)
- Caching behavior
- Edge cases (extreme latitudes, seasonal variations)
- Fallback time handling

#### `test_conditions.py` (13 tests)
Tests for weather condition evaluation:
- Temperature threshold conditions
- Precipitation conditions
- Multiple condition combinations (AND logic)
- Weather offline handling
- Edge cases and validation

#### `test_black_ice_detection.py`
Tests for black ice risk detection:
- Perfect conditions detection (temperature, dew point spread, humidity)
- Temperature too high scenarios
- Dew point spread too large scenarios
- Humidity too low scenarios
- Edge case threshold testing
- Custom threshold configuration
- Weather service integration

#### `test_notification_graceful_failure.py`
Tests for notification failure handling:
- Scheduler continues operating when notification services fail
- System status endpoint data integrity during failures

#### `test_notification_service.py`
Tests for notification service:
- Provider registration and routing
- Event notification delivery
- Disabled service behavior

#### `test_auth.py`
Tests for PIN authentication and session management:
- Authentication flow and session tokens
- Invalid PIN handling
- Session expiration and cleanup

#### `test_manual_override.py`
Tests for manual override functionality:
- Manual control overriding automated schedules
- Override duration and expiration
- Manual override state persistence

#### `test_device_expectations_actual_state.py`
Tests for device state expectation logic:
- Expected vs actual state comparison
- State mismatch detection
- Device state validation

#### `test_config_env_vars.py`
Tests for environment variable overrides:
- Environment variable parsing and application
- Config file and environment variable precedence
- Type conversion and validation

#### `test_credential_validator.py`
Tests for credential validation and placeholder detection:
- Placeholder credential detection
- Invalid credential format handling
- Credential validation rules

#### `test_health_server_config.py`
Tests for health server configuration:
- Default configuration values
- Environment variable overrides
- Health server settings validation

### Integration Tests (`tests/integration/`)

#### `test_schedule_execution.py` (17 tests)
End-to-end schedule execution tests:
- Daily schedule progression
- Temperature-conditional schedules
- Priority-based schedule selection
- Solar schedule execution
- Complex real-world scenarios
- Weekend vs weekday behavior

#### `test_configuration.py` (17 tests)
Configuration loading and validation:
- Loading schedules from YAML files
- Validation of valid/invalid configurations
- Default value handling
- Configuration round-trip (save/load)
- Edge cases and error messages

#### `test_api.py` (14 tests)
API-like interface tests:
- Schedule data access (list, filter, get details)
- Solar times queries
- Schedule status queries
- Validation endpoints
- Weather condition integration
- Metadata and statistics

#### `test_weather_resilience.py`
Weather resilience integration tests:
- Weather cache save, load, and validation
- Cache expiration and age tracking
- Resilient service state transitions (ONLINE → DEGRADED → OFFLINE)
- Fail-safe behavior when cache expires
- Recovery from offline state

#### `test_web_server.py`
Tests for web server routes and functionality:
- Route handlers and responses
- Web server initialization
- HTTP request handling

#### `test_web_config.py`
Tests for web configuration management:
- Web UI configuration loading
- Configuration update endpoints
- Configuration validation

#### `test_web_defaults.py`
Tests for web default configuration values:
- Default bind host (0.0.0.0)
- Default port (4328)
- Default web UI settings

#### `test_web_form.py`
Tests for web form handling:
- Form data parsing and validation
- Form submission processing
- Error handling for invalid inputs

#### `test_web_ui_integration.py`
Tests for web UI integration:
- Full web UI workflow testing
- UI component interaction
- End-to-end UI scenarios

#### `test_automation_api.py`
Tests for automation API endpoints:
- API endpoint functionality
- Request/response validation
- API error handling

#### `test_weather_api.py`
Tests for weather API integration:
- Weather data fetching
- API response parsing
- Weather provider integration

#### `test_weather_toggle.py`
Tests for weather enable/disable functionality:
- Weather toggle state management
- Behavior when weather is disabled
- Weather configuration changes

#### `test_weather_integration.py`
Tests for weather system integration:
- End-to-end weather integration
- Weather-based decision making
- Weather service interaction

#### `test_setup_mode.py`
Tests for setup mode functionality:
- Setup mode activation and detection
- Setup wizard workflow
- Initial configuration setup

#### `test_integration_setup_mode.py`
Integration tests for setup mode:
- Complete setup mode flow
- Device discovery in setup mode
- Configuration persistence from setup

#### `test_startup_checks.py`
Tests for startup diagnostic checks:
- System health validation on startup
- Configuration verification
- Dependency checks

#### `test_config_upload_download.py`
Tests for configuration upload and download:
- Config file export functionality
- Config file import and validation
- Backup and restore operations

#### `test_connection.py`
Tests for device connection handling:
- Device connectivity verification
- Connection timeout handling
- Network error scenarios

#### `test_scheduler.py`
Tests for scheduler core functionality:
- Schedule execution engine
- Timing and scheduling logic
- Schedule state management

#### `test_multi_device.py`
Tests for multi-device group management:
- Device group operations
- Group-level scheduling
- Multi-device coordination

#### `test_multi_outlet_expectations.py`
Tests for multi-outlet device expectations:
- Individual outlet state expectations
- Multi-outlet coordination
- Outlet-specific scheduling

#### `test_device_status_timeout.py`
Tests for device status timeout handling:
- Status query timeouts
- Retry logic
- Timeout error handling

#### `test_health_server.py`
Tests for health server HTTP endpoints:
- Health check endpoint responses
- Weather health endpoint
- Server startup and shutdown

#### `test_notification_enhancements.py`
Tests for notification system enhancements:
- Enhanced notification features
- Notification formatting
- Multi-channel notifications

#### `test_shared_event_loop.py`
Tests for shared asyncio event loop:
- Event loop sharing between components
- Async task coordination
- Event loop lifecycle management

#### `test_control_timeout_hours.py`
Tests for control timeout in hours:
- Timeout configuration
- Long-running control operations
- Timeout expiration handling

## Test Fixtures

### Location Fixtures
- `timezone_ny`: New York timezone
- `location_ny`: NYC coordinates
- `location_alaska`: Alaska coordinates (for edge cases)

### Time Fixtures
- `test_date`: Fixed summer date (2024-06-15)
- `test_date_winter`: Winter date (2024-12-15)
- `test_datetime`: Fixed datetime for deterministic tests

### Schedule Configuration Fixtures
- `schedule_config_basic`: Simple clock-time schedule
- `schedule_config_solar`: Solar-based schedule (sunset/sunrise)
- `schedule_config_with_conditions`: Weather-conditional schedule
- `schedule_config_duration`: Duration-based off time
- `schedule_config_weekend`: Weekend-only schedule

### Weather Fixtures
- `weather_cold_dry`: 28°F, no precipitation
- `weather_cold_snowing`: 25°F with snow
- `weather_warm`: 55°F, no precipitation
- `weather_freezing_rain`: 32°F with precipitation

### YAML Configuration Files
Located in `tests/fixtures/`:
- `valid_schedule_config.yaml`: Valid schedule examples
- `invalid_schedule_config.yaml`: Invalid schedules for error testing
- `solar_schedule_config.yaml`: Solar-based schedule examples

## Coverage Goals

Current coverage for scheduler components:
- **ScheduleEvaluator**: 92% coverage
- **Schedule types**: 95% coverage
- **SolarCalculator**: 80% coverage

Coverage reports are generated in:
- Terminal: Shows coverage summary
- HTML: `htmlcov/index.html` (detailed line-by-line coverage)
- XML: `coverage.xml` (for CI/CD integration)

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Every push to `main` or `develop` branches
- Every pull request

The CI pipeline:
1. Tests on Python 3.11 and 3.12
2. Runs unit tests with coverage
3. Runs integration tests
4. Uploads coverage to Codecov
5. Runs advisory linting checks (flake8, black) — non-blocking

**Note:** Currently, only a subset of the test suite runs in CI (7 original test files):
- Unit tests: `test_schedule.py`, `test_solar_calculator.py`, `test_schedule_evaluator.py`, `test_conditions.py`
- Integration tests: `test_schedule_execution.py`, `test_configuration.py`, `test_api.py`

The remaining tests exist in the repository but are not yet integrated into the CI workflow. Future improvements will expand CI coverage to include all test files.

## Writing New Tests

### Test Structure

```python
def test_descriptive_name(fixture1, fixture2):
    """Clear description of what this test validates."""
    # Arrange: Set up test data
    config = {...}
    
    # Act: Perform the operation
    result = function_under_test(config)
    
    # Assert: Verify expected behavior
    assert result.some_property == expected_value
```

### Using Fixtures

```python
def test_with_schedule(schedule_basic, timezone_ny):
    """Tests can use fixtures defined in conftest.py."""
    test_time = datetime(2024, 6, 17, 7, 0, tzinfo=timezone_ny)
    # ... test logic
```

### Mocking Time

Use `freezegun` for time-dependent tests:

```python
from freezegun import freeze_time

@freeze_time("2024-06-17 07:00:00")
def test_at_specific_time():
    now = datetime.now()
    # ... test logic with fixed time
```

## Common Testing Patterns

### Testing Schedule Activation

```python
should_on, active_schedule, reason = evaluator.should_turn_on(
    schedules=[schedule],
    current_time=test_time,
    weather_conditions=weather_data
)

assert should_on is True
assert active_schedule.name == "Expected Schedule"
```

### Testing Configuration Validation

```python
is_valid, errors = validate_schedules(schedule_configs)

assert is_valid is False
assert len(errors) > 0
assert "expected error message" in errors[0]
```

### Testing Exception Handling

```python
with pytest.raises(ValueError, match="expected message"):
    Schedule(invalid_config)
```

## Troubleshooting

### Test Failures

If tests fail:
1. Check the test output for specific error messages
2. Run failed test in verbose mode: `pytest path/to/test.py::test_name -v`
3. Check if fixtures are correctly loaded
4. Verify YAML configuration files are valid

### Import Errors

If you see import errors:
```bash
# Ensure you're in the project root
cd /path/to/HeatTrax_Tapo_M400_Scheduler

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock pytest-asyncio freezegun
```

### Coverage Issues

To see which lines aren't covered:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View in browser
```

## Best Practices

1. **Keep tests independent**: Each test should be able to run in isolation
2. **Use descriptive names**: Test names should clearly indicate what they're testing
3. **Test one thing**: Each test should verify one specific behavior
4. **Use fixtures**: Reuse common test data through fixtures
5. **Test edge cases**: Don't just test the happy path
6. **Keep tests fast**: Unit tests should complete in milliseconds
7. **Mock external dependencies**: Avoid real network calls or file I/O when possible

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [freezegun documentation](https://github.com/spulec/freezegun)
- [Testing best practices](https://docs.pytest.org/en/latest/goodpractices.html)

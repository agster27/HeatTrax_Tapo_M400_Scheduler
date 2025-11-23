"""Integration tests for configuration loading and validation."""

import pytest
import yaml
import tempfile
from pathlib import Path

from src.scheduler.schedule_types import (
    Schedule,
    parse_schedules,
    validate_schedules
)


class TestConfigurationLoading:
    """Test loading schedules from configuration files."""
    
    def test_load_valid_yaml_config(self):
        """Test loading valid schedule configuration from YAML."""
        yaml_path = 'tests/fixtures/valid_schedule_config.yaml'
        
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        
        assert 'schedules' in config
        assert isinstance(config['schedules'], list)
        assert len(config['schedules']) == 4
        
        # Parse schedules
        schedules = parse_schedules(config['schedules'])
        
        assert len(schedules) == 4
        assert all(isinstance(s, Schedule) for s in schedules)
    
    def test_load_solar_yaml_config(self):
        """Test loading solar schedule configuration from YAML."""
        yaml_path = 'tests/fixtures/solar_schedule_config.yaml'
        
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        
        schedules = parse_schedules(config['schedules'])
        
        assert len(schedules) == 3
        
        # Check that schedules have solar times
        for schedule in schedules:
            has_solar = (
                schedule.on_config.get('type') in ['sunrise', 'sunset'] or
                schedule.off_config.get('type') in ['sunrise', 'sunset']
            )
            assert has_solar, f"Schedule {schedule.name} should have solar times"
    
    def test_detect_invalid_yaml_config(self):
        """Test detection of invalid schedule configuration."""
        yaml_path = 'tests/fixtures/invalid_schedule_config.yaml'
        
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Validation should fail
        is_valid, errors = validate_schedules(config['schedules'])
        
        assert is_valid is False
        assert len(errors) > 0
    
    def test_parse_invalid_config_raises_error(self):
        """Test that parsing invalid config raises ValueError."""
        yaml_path = 'tests/fixtures/invalid_schedule_config.yaml'
        
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        
        with pytest.raises(ValueError):
            parse_schedules(config['schedules'])


class TestConfigurationValidation:
    """Test validation of various configuration scenarios."""
    
    def test_validate_empty_schedule_list(self):
        """Test validation of empty schedule list."""
        is_valid, errors = validate_schedules([])
        
        # Empty list is valid (no errors)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_single_valid_schedule(self):
        """Test validation of single valid schedule."""
        config = [{
            'name': 'Test Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {},
            'safety': {}
        }]
        
        is_valid, errors = validate_schedules(config)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_multiple_schedules_one_invalid(self):
        """Test validation catches invalid schedule among valid ones."""
        configs = [
            {
                'name': 'Valid Schedule',
                'on': {'type': 'time', 'value': '06:00'},
                'off': {'type': 'time', 'value': '08:00'}
            },
            {
                'name': 'Invalid Schedule',
                'on': {'type': 'invalid_type', 'value': '06:00'},
                'off': {'type': 'time', 'value': '08:00'}
            },
            {
                'name': 'Another Valid',
                'on': {'type': 'time', 'value': '18:00'},
                'off': {'type': 'time', 'value': '20:00'}
            }
        ]
        
        is_valid, errors = validate_schedules(configs)
        
        assert is_valid is False
        assert len(errors) >= 1
        assert 'Invalid Schedule' in str(errors)
    
    def test_validate_not_a_list(self):
        """Test validation rejects non-list input."""
        is_valid, errors = validate_schedules("not a list")
        
        assert is_valid is False
        assert len(errors) == 1
        assert "must be a list" in errors[0]
    
    def test_validate_schedule_dict_not_dict(self):
        """Test validation rejects non-dict schedule items."""
        is_valid, errors = validate_schedules([
            "not a dict",
            {'on': {'type': 'time', 'value': '06:00'}, 'off': {'type': 'time', 'value': '08:00'}}
        ])
        
        assert is_valid is False
        assert len(errors) >= 1


class TestConfigurationDefaultValues:
    """Test that default values are applied correctly."""
    
    def test_minimal_config_uses_defaults(self):
        """Test that minimal config gets default values."""
        minimal_config = {
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        schedule = Schedule(minimal_config)
        
        # Check defaults
        assert schedule.name == 'Unnamed Schedule'
        assert schedule.enabled is True
        assert schedule.priority.value == 'normal'
        assert schedule.days == [1, 2, 3, 4, 5, 6, 7]
        assert schedule.conditions == {}
        assert schedule.safety == {}
    
    def test_explicit_values_override_defaults(self):
        """Test that explicit values override defaults."""
        config = {
            'name': 'Custom Name',
            'enabled': False,
            'priority': 'critical',
            'days': [6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {'temperature_max': 32},
            'safety': {'max_runtime_hours': 8}
        }
        
        schedule = Schedule(config)
        
        assert schedule.name == 'Custom Name'
        assert schedule.enabled is False
        assert schedule.priority.value == 'critical'
        assert schedule.days == [6, 7]
        assert schedule.conditions == {'temperature_max': 32}
        assert schedule.safety == {'max_runtime_hours': 8}


class TestConfigurationRoundTrip:
    """Test that configurations can be serialized and deserialized."""
    
    def test_schedule_to_dict_and_back(self):
        """Test converting schedule to dict and back."""
        original_config = {
            'name': 'Test Schedule',
            'enabled': True,
            'priority': 'normal',
            'days': [1, 2, 3, 4, 5],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'},
            'conditions': {'temperature_max': 32},
            'safety': {'max_runtime_hours': 6}
        }
        
        schedule = Schedule(original_config)
        dict_repr = schedule.to_dict()
        
        # Should be able to create new schedule from dict
        new_schedule = Schedule(dict_repr)
        
        assert new_schedule.name == schedule.name
        assert new_schedule.enabled == schedule.enabled
        assert new_schedule.priority == schedule.priority
        assert new_schedule.days == schedule.days
        assert new_schedule.conditions == schedule.conditions
    
    def test_save_and_load_config(self):
        """Test saving configuration to file and loading it back."""
        config = {
            'schedules': [
                {
                    'name': 'Morning Schedule',
                    'enabled': True,
                    'priority': 'normal',
                    'days': [1, 2, 3, 4, 5],
                    'on': {'type': 'time', 'value': '06:00'},
                    'off': {'type': 'time', 'value': '08:00'},
                    'conditions': {},
                    'safety': {}
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            # Load it back
            with open(temp_path, 'r') as f:
                loaded_config = yaml.safe_load(f)
            
            # Parse schedules
            schedules = parse_schedules(loaded_config['schedules'])
            
            assert len(schedules) == 1
            assert schedules[0].name == 'Morning Schedule'
        finally:
            Path(temp_path).unlink()


class TestConfigurationEdgeCases:
    """Test edge cases in configuration handling."""
    
    def test_schedule_with_all_days(self):
        """Test schedule configured for all days of week."""
        config = {
            'days': [1, 2, 3, 4, 5, 6, 7],
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        schedule = Schedule(config)
        assert len(schedule.days) == 7
    
    def test_schedule_with_single_day(self):
        """Test schedule configured for single day."""
        config = {
            'days': [1],  # Monday only
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        schedule = Schedule(config)
        assert schedule.days == [1]
    
    def test_schedule_midnight_times(self):
        """Test schedule with midnight times."""
        config = {
            'on': {'type': 'time', 'value': '00:00'},
            'off': {'type': 'time', 'value': '23:59'}
        }
        
        schedule = Schedule(config)
        assert schedule.on_config['value'] == '00:00'
        assert schedule.off_config['value'] == '23:59'
    
    def test_schedule_with_zero_offset(self):
        """Test solar schedule with zero offset."""
        config = {
            'on': {'type': 'sunrise', 'offset': 0, 'fallback': '06:00'},
            'off': {'type': 'sunset', 'offset': 0, 'fallback': '18:00'}
        }
        
        schedule = Schedule(config)
        assert schedule.on_config['offset'] == 0
        assert schedule.off_config['offset'] == 0
    
    def test_schedule_with_extreme_offsets(self):
        """Test solar schedule with maximum allowed offsets."""
        config = {
            'on': {'type': 'sunrise', 'offset': -180, 'fallback': '03:00'},
            'off': {'type': 'sunset', 'offset': 180, 'fallback': '22:00'}
        }
        
        schedule = Schedule(config)
        assert schedule.on_config['offset'] == -180
        assert schedule.off_config['offset'] == 180


class TestConfigurationErrorMessages:
    """Test that error messages are helpful."""
    
    def test_missing_on_time_error_message(self):
        """Test error message for missing on time."""
        config = {
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError) as exc_info:
            Schedule(config)
        
        assert "must have 'on' time" in str(exc_info.value)
    
    def test_invalid_time_format_error_message(self):
        """Test error message for invalid time format."""
        config = {
            'on': {'type': 'time', 'value': '25:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        with pytest.raises(ValueError) as exc_info:
            Schedule(config)
        
        assert "Invalid time format" in str(exc_info.value)
        assert "25:00" in str(exc_info.value)
    
    def test_invalid_priority_warning_uses_default(self):
        """Test that invalid priority logs warning but uses default."""
        config = {
            'priority': 'super_critical',
            'on': {'type': 'time', 'value': '06:00'},
            'off': {'type': 'time', 'value': '08:00'}
        }
        
        # Should not raise error, just use default
        schedule = Schedule(config)
        assert schedule.priority.value == 'normal'
    
    def test_validation_error_includes_schedule_name(self):
        """Test that validation errors include schedule name."""
        configs = [
            {
                'name': 'Problem Schedule',
                'on': {'type': 'time', 'value': '06:00'}
                # Missing off time
            }
        ]
        
        is_valid, errors = validate_schedules(configs)
        
        assert is_valid is False
        assert any('Problem Schedule' in err for err in errors)

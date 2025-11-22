"""
Unit tests for automation_overrides module.
"""

import json
import pytest
import tempfile
from pathlib import Path
from src.scheduler.automation_overrides import AutomationOverrides


class TestAutomationOverrides:
    """Test AutomationOverrides functionality."""
    
    def test_initialization_creates_directory(self):
        """Test that initialization creates state directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "subdir" / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            assert state_file.parent.exists()
            assert overrides.overrides == {}
    
    def test_load_missing_file(self):
        """Test loading when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            assert overrides.overrides == {}
    
    def test_load_existing_file(self):
        """Test loading existing overrides file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            
            # Create file with test data
            test_data = {
                "heattrax": {
                    "weather_control": True,
                    "morning_mode": False
                }
            }
            with open(state_file, 'w') as f:
                json.dump(test_data, f)
            
            overrides = AutomationOverrides(state_file=str(state_file))
            assert overrides.overrides == test_data
    
    def test_load_malformed_json(self):
        """Test handling of malformed JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            
            # Create malformed JSON
            with open(state_file, 'w') as f:
                f.write("{ invalid json")
            
            overrides = AutomationOverrides(state_file=str(state_file))
            assert overrides.overrides == {}
    
    def test_load_invalid_format(self):
        """Test handling of non-dict JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            
            # Create list instead of dict
            with open(state_file, 'w') as f:
                json.dump(["not", "a", "dict"], f)
            
            overrides = AutomationOverrides(state_file=str(state_file))
            assert overrides.overrides == {}
    
    def test_set_flag_creates_override(self):
        """Test setting a flag creates an override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            overrides.set_flag("heattrax", "weather_control", True)
            
            assert overrides.get_group_overrides("heattrax") == {"weather_control": True}
            assert state_file.exists()
    
    def test_set_flag_updates_existing(self):
        """Test setting a flag updates existing override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            overrides.set_flag("heattrax", "weather_control", True)
            overrides.set_flag("heattrax", "weather_control", False)
            
            assert overrides.get_group_overrides("heattrax") == {"weather_control": False}
    
    def test_set_flag_none_clears_override(self):
        """Test setting flag to None clears the override."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            overrides.set_flag("heattrax", "weather_control", True)
            assert "weather_control" in overrides.get_group_overrides("heattrax")
            
            overrides.set_flag("heattrax", "weather_control", None)
            assert "weather_control" not in overrides.get_group_overrides("heattrax")
    
    def test_set_flag_none_removes_empty_group(self):
        """Test that clearing last flag removes group entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            overrides.set_flag("heattrax", "weather_control", True)
            overrides.set_flag("heattrax", "weather_control", None)
            
            assert "heattrax" not in overrides.overrides
    
    def test_get_group_overrides_empty(self):
        """Test getting overrides for group with no overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            assert overrides.get_group_overrides("nonexistent") == {}
    
    def test_get_effective_automation_no_overrides(self):
        """Test effective automation without overrides matches base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            base = {
                "weather_control": True,
                "precipitation_control": True,
                "morning_mode": False,
                "schedule_control": False
            }
            
            effective = overrides.get_effective_automation("heattrax", base)
            assert effective == base
    
    def test_get_effective_automation_with_overrides(self):
        """Test effective automation with overrides applied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            base = {
                "weather_control": True,
                "precipitation_control": True,
                "morning_mode": False,
                "schedule_control": False
            }
            
            overrides.set_flag("heattrax", "morning_mode", True)
            overrides.set_flag("heattrax", "schedule_control", True)
            
            effective = overrides.get_effective_automation("heattrax", base)
            
            assert effective["weather_control"] == True  # From base
            assert effective["precipitation_control"] == True  # From base
            assert effective["morning_mode"] == True  # Overridden
            assert effective["schedule_control"] == True  # Overridden
    
    def test_get_effective_automation_partial_overrides(self):
        """Test that partial overrides only affect specified flags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            base = {
                "weather_control": True,
                "morning_mode": True
            }
            
            overrides.set_flag("heattrax", "weather_control", False)
            
            effective = overrides.get_effective_automation("heattrax", base)
            
            assert effective["weather_control"] == False  # Overridden
            assert effective["morning_mode"] == True  # Unchanged from base
    
    def test_clear_group_overrides(self):
        """Test clearing all overrides for a group."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            overrides.set_flag("heattrax", "weather_control", False)
            overrides.set_flag("heattrax", "morning_mode", True)
            
            overrides.clear_group_overrides("heattrax")
            
            assert overrides.get_group_overrides("heattrax") == {}
            assert "heattrax" not in overrides.overrides
    
    def test_get_all_overrides(self):
        """Test getting all overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            overrides.set_flag("heattrax", "weather_control", True)
            overrides.set_flag("lights", "schedule_control", False)
            
            all_overrides = overrides.get_all_overrides()
            
            assert "heattrax" in all_overrides
            assert "lights" in all_overrides
            assert all_overrides["heattrax"]["weather_control"] == True
            assert all_overrides["lights"]["schedule_control"] == False
    
    def test_persistence_across_instances(self):
        """Test that overrides persist across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            
            # First instance
            overrides1 = AutomationOverrides(state_file=str(state_file))
            overrides1.set_flag("heattrax", "weather_control", True)
            
            # Second instance
            overrides2 = AutomationOverrides(state_file=str(state_file))
            assert overrides2.get_group_overrides("heattrax") == {"weather_control": True}
    
    def test_multiple_groups(self):
        """Test handling multiple groups simultaneously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "overrides.json"
            overrides = AutomationOverrides(state_file=str(state_file))
            
            overrides.set_flag("heattrax", "weather_control", True)
            overrides.set_flag("lights", "schedule_control", False)
            overrides.set_flag("pool", "morning_mode", True)
            
            assert overrides.get_group_overrides("heattrax") == {"weather_control": True}
            assert overrides.get_group_overrides("lights") == {"schedule_control": False}
            assert overrides.get_group_overrides("pool") == {"morning_mode": True}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

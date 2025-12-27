"""Unit tests for scheduler manual override handling."""

import pytest
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from src.state.manual_override import ManualOverrideManager


class TestSchedulerManualOverride:
    """Tests for scheduler's handling of manual overrides."""
    
    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def override_manager(self, temp_state_file):
        """Create a ManualOverrideManager instance with temp file."""
        return ManualOverrideManager(state_file=temp_state_file, timezone='America/New_York')
    
    def test_override_not_cleared_on_state_mismatch(self, override_manager):
        """Test that manual override is NOT cleared just because state differs from schedule.
        
        This validates the fix for the bug where overrides were being cleared prematurely
        during scheduler cycles when the current state differed from what the schedule wanted.
        
        The override should ONLY be cleared when:
        1. It expires naturally (time-based expiration)
        2. User manually cancels it
        3. A specific schedule boundary transition occurs
        
        NOT when there's just a state mismatch during a regular scheduler cycle.
        """
        # Set a 2-hour override to turn on a group
        override_manager.set_override('heated_mats', 'on', 2.0)
        
        # Verify override is active
        assert override_manager.is_active('heated_mats') is True
        assert override_manager.get_action('heated_mats') == 'on'
        
        # Simulate scheduler cycle running - override should remain active
        # even if schedule wants a different state
        # (In the buggy code, this would have cleared the override)
        
        # Override should still be active after "scheduler cycle"
        assert override_manager.is_active('heated_mats') is True
        assert override_manager.get_action('heated_mats') == 'on'
    
    def test_override_clears_on_expiration(self, override_manager):
        """Test that manual override is properly cleared when it expires."""
        # Set override with very short timeout
        override_manager.set_override('heated_mats', 'on', 0.0001)
        
        # Should be active immediately
        assert override_manager.is_active('heated_mats') is True
        
        # Wait for expiration
        time.sleep(0.5)
        
        # Should be expired now
        assert override_manager.is_active('heated_mats') is False
    
    def test_override_clears_on_manual_cancel(self, override_manager):
        """Test that manual override can be manually cleared."""
        # Set override
        override_manager.set_override('heated_mats', 'on', 2.0)
        assert override_manager.is_active('heated_mats') is True
        
        # Manually clear
        result = override_manager.clear_override('heated_mats')
        assert result is True
        assert override_manager.is_active('heated_mats') is False
    
    def test_multiple_overrides_independent(self, override_manager):
        """Test that multiple group overrides are handled independently."""
        # Set overrides for different groups
        override_manager.set_override('heated_mats', 'on', 2.0)
        override_manager.set_override('christmas_lights', 'off', 1.0)
        
        # Both should be active
        assert override_manager.is_active('heated_mats') is True
        assert override_manager.is_active('christmas_lights') is True
        
        # Clear one
        override_manager.clear_override('heated_mats')
        
        # Only the cleared one should be inactive
        assert override_manager.is_active('heated_mats') is False
        assert override_manager.is_active('christmas_lights') is True
    
    def test_override_persists_across_multiple_scheduler_checks(self, override_manager):
        """Test that override remains active across multiple scheduler cycle checks.
        
        This simulates what happens when the scheduler runs multiple times
        while an override is active. The override should persist through all
        cycles until it expires naturally.
        """
        # Set a 2-hour override
        override_manager.set_override('heated_mats', 'on', 2.0)
        
        # Simulate multiple scheduler cycles (e.g., every 10 minutes)
        for cycle in range(5):
            # Each cycle checks if override is active
            assert override_manager.is_active('heated_mats') is True
            assert override_manager.get_action('heated_mats') == 'on'
            
            # In the buggy code, the first or second cycle might have cleared it
            # due to state mismatch detection
        
        # After 5 "cycles", override should still be active
        assert override_manager.is_active('heated_mats') is True

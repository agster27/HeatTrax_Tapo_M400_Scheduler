"""Unit tests for manual override state management."""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.state.manual_override import ManualOverrideManager


@pytest.fixture
def temp_state_file():
    """Create a temporary state file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def override_manager(temp_state_file):
    """Create a ManualOverrideManager instance with temp file."""
    return ManualOverrideManager(state_file=temp_state_file, timezone='America/New_York')


class TestManualOverrideManager:
    """Tests for ManualOverrideManager class."""
    
    def test_initialization(self, override_manager):
        """Test manager initialization."""
        assert override_manager.state == {}
        assert override_manager.timezone == ZoneInfo('America/New_York')
    
    def test_set_override(self, override_manager):
        """Test setting a manual override."""
        result = override_manager.set_override('test_group', 'on', 2.0)
        
        assert result['active'] is True
        assert result['action'] == 'on'
        assert result['timeout_hours'] == 2.0
        assert 'timestamp' in result
        assert 'expires_at' in result
        
        # Verify it was saved
        assert 'test_group' in override_manager.state
    
    def test_set_override_invalid_action(self, override_manager):
        """Test setting override with invalid action."""
        with pytest.raises(ValueError, match="Invalid action"):
            override_manager.set_override('test_group', 'invalid', 2.0)
    
    def test_is_active(self, override_manager):
        """Test checking if override is active."""
        # No override initially
        assert override_manager.is_active('test_group') is False
        
        # Set override
        override_manager.set_override('test_group', 'on', 1.0)
        assert override_manager.is_active('test_group') is True
        
        # Different group
        assert override_manager.is_active('other_group') is False
    
    def test_is_active_expired(self, override_manager):
        """Test that expired overrides return False."""
        # Set override with very short timeout
        override_manager.set_override('test_group', 'on', 0.0001)
        
        # Should be active immediately
        assert override_manager.is_active('test_group') is True
        
        # Wait a bit and check again
        import time
        time.sleep(0.5)
        
        # Should be expired now
        assert override_manager.is_active('test_group') is False
        
        # Should have been auto-cleared
        assert 'test_group' not in override_manager.state
    
    def test_clear_override(self, override_manager):
        """Test clearing an override."""
        override_manager.set_override('test_group', 'on', 1.0)
        assert override_manager.is_active('test_group') is True
        
        result = override_manager.clear_override('test_group')
        assert result is True
        assert override_manager.is_active('test_group') is False
        
        # Clearing non-existent override
        result = override_manager.clear_override('nonexistent')
        assert result is False
    
    def test_get_status(self, override_manager):
        """Test getting override status."""
        # No override
        status = override_manager.get_status('test_group')
        assert status is None
        
        # Set override
        override_manager.set_override('test_group', 'off', 3.0)
        status = override_manager.get_status('test_group')
        
        assert status is not None
        assert status['active'] is True
        assert status['action'] == 'off'
        assert status['timeout_hours'] == 3.0
    
    def test_get_all_status(self, override_manager):
        """Test getting status for all groups."""
        # Set multiple overrides
        override_manager.set_override('group1', 'on', 1.0)
        override_manager.set_override('group2', 'off', 2.0)
        
        all_status = override_manager.get_all_status()
        
        assert len(all_status) == 2
        assert 'group1' in all_status
        assert 'group2' in all_status
        assert all_status['group1']['action'] == 'on'
        assert all_status['group2']['action'] == 'off'
    
    def test_get_action(self, override_manager):
        """Test getting override action."""
        # No override
        assert override_manager.get_action('test_group') is None
        
        # Set override
        override_manager.set_override('test_group', 'on', 1.0)
        assert override_manager.get_action('test_group') == 'on'
    
    def test_should_clear_on_schedule(self, override_manager):
        """Test should_clear_on_schedule method."""
        # Default should return True
        assert override_manager.should_clear_on_schedule() is True
    
    def test_state_persistence(self, temp_state_file):
        """Test that state persists across instances."""
        # Create manager and set override
        manager1 = ManualOverrideManager(state_file=temp_state_file, timezone='America/New_York')
        manager1.set_override('test_group', 'on', 5.0)
        
        # Create new manager with same file
        manager2 = ManualOverrideManager(state_file=temp_state_file, timezone='America/New_York')
        
        # Should have loaded the state
        assert manager2.is_active('test_group') is True
        assert manager2.get_action('test_group') == 'on'
    
    def test_multiple_groups_independent(self, override_manager):
        """Test that multiple groups are handled independently."""
        # Set different overrides for different groups
        override_manager.set_override('group1', 'on', 1.0)
        override_manager.set_override('group2', 'off', 2.0)
        override_manager.set_override('group3', 'on', 3.0)
        
        # Each should have its own state
        assert override_manager.get_action('group1') == 'on'
        assert override_manager.get_action('group2') == 'off'
        assert override_manager.get_action('group3') == 'on'
        
        # Clear one should not affect others
        override_manager.clear_override('group2')
        
        assert override_manager.is_active('group1') is True
        assert override_manager.is_active('group2') is False
        assert override_manager.is_active('group3') is True
    
    def test_timezone_aware_expiration(self, override_manager):
        """Test that override expiration times are timezone-aware and correct."""
        # Set override with 2 hour timeout
        result = override_manager.set_override('test_group', 'on', 2.0)
        
        # Parse the expires_at timestamp
        expires_at = datetime.fromisoformat(result['expires_at'])
        timestamp = datetime.fromisoformat(result['timestamp'])
        
        # Verify both timestamps are timezone-aware
        assert expires_at.tzinfo is not None, "expires_at should be timezone-aware"
        assert timestamp.tzinfo is not None, "timestamp should be timezone-aware"
        
        # Verify expires_at is in the future
        now = datetime.now(override_manager.timezone)
        assert expires_at > now, "expires_at should be in the future"
        
        # Verify the timeout is approximately 2 hours
        delta = expires_at - timestamp
        delta_hours = delta.total_seconds() / 3600
        assert abs(delta_hours - 2.0) < 0.01, f"Timeout should be ~2 hours, got {delta_hours}"
        
        # Verify ISO format includes timezone offset
        assert '+' in result['expires_at'] or '-' in result['expires_at'] or result['expires_at'].endswith('Z'), \
            "ISO format should include timezone offset"

#!/usr/bin/env python3
"""
Unit test for device expectations showing actual device state vs state manager memory.

This test validates that get_device_expectations() queries the actual physical device state
instead of using the state manager's memory, ensuring the Health tab accurately displays
device state and can detect mismatches.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.scheduler.scheduler_enhanced import EnhancedScheduler
from src.config.config_loader import Config
from src.scheduler.state_manager import StateManager


@pytest.mark.unit
class TestDeviceExpectationsActualState:
    """Test that device expectations query actual device state."""
    
    @pytest.mark.asyncio
    async def test_current_state_from_actual_device(self):
        """Test that current_state comes from actual device query, not state manager."""
        # Load actual config file
        config = Config('config.example.yaml')
        
        # Create scheduler in setup mode
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Test group configuration
        test_group_config = {
            'enabled': True,
            'items': [
                {
                    'name': 'Test Device',
                    'ip_address': '192.168.1.100'
                }
            ]
        }
        
        # Mock the device manager
        mock_device_manager = MagicMock()
        mock_device_manager.get_all_groups.return_value = ['test_group']
        mock_device_manager.get_group_config.return_value = test_group_config
        
        # Key test: Mock get_group_state to return True (device is ON)
        # while state manager thinks device is OFF
        mock_device_manager.get_group_state = AsyncMock(return_value=True)
        
        scheduler.device_manager = mock_device_manager
        
        # Create state manager that thinks device is OFF
        mock_state = StateManager(state_file='/tmp/test_device_expectations_state.json')
        mock_state.device_on = False  # State manager memory says OFF
        scheduler.states = {'test_group': mock_state}
        
        # Mock should_turn_on_group and should_turn_off_group
        scheduler.should_turn_on_group = AsyncMock(return_value=True)
        scheduler.should_turn_off_group = AsyncMock(return_value=False)
        
        # Get device expectations
        expectations = await scheduler.get_device_expectations()
        
        # Verify we got an expectation
        assert len(expectations) == 1
        
        # CRITICAL: Current state should be "on" (from actual device query)
        # NOT "off" (from state manager memory)
        assert expectations[0]['current_state'] == 'on', \
            "Current state should come from actual device query (on), not state manager memory (off)"
        
        # Expected state should be "on" based on should_turn_on_group
        assert expectations[0]['expected_state'] == 'on'
        
        # Verify get_group_state was called
        mock_device_manager.get_group_state.assert_called_once_with('test_group')
    
    @pytest.mark.asyncio
    async def test_fallback_to_state_manager_on_device_query_error(self):
        """Test that we fallback to state manager if device query fails."""
        # Load actual config file
        config = Config('config.example.yaml')
        
        # Create scheduler in setup mode
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Test group configuration
        test_group_config = {
            'enabled': True,
            'items': [
                {
                    'name': 'Test Device',
                    'ip_address': '192.168.1.100'
                }
            ]
        }
        
        # Mock the device manager
        mock_device_manager = MagicMock()
        mock_device_manager.get_all_groups.return_value = ['test_group']
        mock_device_manager.get_group_config.return_value = test_group_config
        
        # Mock get_group_state to raise an exception (network error, device unreachable, etc.)
        mock_device_manager.get_group_state = AsyncMock(side_effect=Exception("Network error"))
        
        scheduler.device_manager = mock_device_manager
        
        # Create state manager that thinks device is ON
        mock_state = StateManager(state_file='/tmp/test_device_expectations_fallback_state.json')
        mock_state.device_on = True  # State manager memory says ON
        scheduler.states = {'test_group': mock_state}
        
        # Mock should_turn_on_group and should_turn_off_group
        scheduler.should_turn_on_group = AsyncMock(return_value=False)
        scheduler.should_turn_off_group = AsyncMock(return_value=True)
        
        # Get device expectations
        expectations = await scheduler.get_device_expectations()
        
        # Verify we got an expectation
        assert len(expectations) == 1
        
        # Should fallback to state manager when device query fails
        assert expectations[0]['current_state'] == 'on', \
            "Current state should fallback to state manager (on) when device query fails"
        
        # Expected state should be "off" based on should_turn_off_group
        assert expectations[0]['expected_state'] == 'off'
        
        # Verify get_group_state was called and failed
        mock_device_manager.get_group_state.assert_called_once_with('test_group')
    
    @pytest.mark.asyncio
    async def test_mismatch_detection_with_actual_state(self):
        """Test that mismatches are detected when actual device state differs from expected."""
        # Load actual config file
        config = Config('config.example.yaml')
        
        # Create scheduler in setup mode
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Test group configuration
        test_group_config = {
            'enabled': True,
            'items': [
                {
                    'name': 'Test Device',
                    'ip_address': '192.168.1.100'
                }
            ]
        }
        
        # Mock the device manager
        mock_device_manager = MagicMock()
        mock_device_manager.get_all_groups.return_value = ['test_group']
        mock_device_manager.get_group_config.return_value = test_group_config
        
        # Actual device is OFF (manual override turned it off)
        mock_device_manager.get_group_state = AsyncMock(return_value=False)
        
        scheduler.device_manager = mock_device_manager
        
        # State manager might think it's ON or OFF, but we're not using it for current_state anymore
        mock_state = StateManager(state_file='/tmp/test_device_expectations_mismatch_state.json')
        mock_state.device_on = True  # State manager memory is out of sync
        scheduler.states = {'test_group': mock_state}
        
        # Schedule says device should be ON
        scheduler.should_turn_on_group = AsyncMock(return_value=True)
        scheduler.should_turn_off_group = AsyncMock(return_value=False)
        
        # Get device expectations
        expectations = await scheduler.get_device_expectations()
        
        # Verify we got an expectation
        assert len(expectations) == 1
        
        # Current state should be "off" (from actual device)
        assert expectations[0]['current_state'] == 'off', \
            "Current state should reflect actual device state (off)"
        
        # Expected state should be "on" (from schedule)
        assert expectations[0]['expected_state'] == 'on', \
            "Expected state should reflect what schedule wants (on)"
        
        # This mismatch should trigger the warning indicator in the UI
        # (current_state != expected_state)
        assert expectations[0]['current_state'] != expectations[0]['expected_state'], \
            "Mismatch should be detected between current and expected state"
        
        # Verify get_group_state was called
        mock_device_manager.get_group_state.assert_called_once_with('test_group')


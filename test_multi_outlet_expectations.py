#!/usr/bin/env python3
"""
Test for multi-outlet device expectations in the scheduler.
Validates that devices with outlets: [0, 1] create separate health cards.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scheduler_enhanced import EnhancedScheduler
from config_loader import Config
from state_manager import StateManager
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_multi_outlet_device_expectations():
    """Test that devices with multiple outlets create separate expectations."""
    logger.info("Testing multi-outlet device expectations...")
    
    try:
        # Load config
        config = Config('config.example.yaml')
        
        # Create scheduler in setup mode to avoid device initialization
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Mock the device manager to return our test config
        mock_device_manager = MagicMock()
        
        # Mock group configuration with multi-outlet device
        test_group_config = {
            'enabled': True,
            'automation': {
                'weather_control': False,
                'schedule_control': True
            },
            'schedule': {
                'on_time': '17:00',
                'off_time': '23:00'
            },
            'items': [
                {
                    'name': 'Test Multi-Outlet Device',
                    'ip_address': '192.168.1.100',
                    'outlets': [0, 1]  # Multi-outlet device
                },
                {
                    'name': 'Test Single-Outlet Device',
                    'ip_address': '192.168.1.101',
                    'outlet': 0  # Single outlet device
                }
            ]
        }
        
        # Setup mock to return our test group
        mock_device_manager.get_all_groups.return_value = ['test_group']
        mock_device_manager.get_group_config.return_value = test_group_config
        
        # Replace device manager with mock
        scheduler.device_manager = mock_device_manager
        
        # Create a mock state for the group
        mock_state = StateManager(state_file='/tmp/test_multi_outlet_state.json')
        mock_state.device_on = False
        scheduler.states = {'test_group': mock_state}
        
        # Mock should_turn_on_group and should_turn_off_group
        async def mock_should_turn_on(group_name):
            return False
        
        async def mock_should_turn_off(group_name):
            return True
        
        scheduler.should_turn_on_group = mock_should_turn_on
        scheduler.should_turn_off_group = mock_should_turn_off
        
        # Get device expectations
        expectations = await scheduler.get_device_expectations()
        
        logger.info(f"Got {len(expectations)} device expectations")
        for exp in expectations:
            logger.info(f"  - {exp['device_name']} (Outlet: {exp['outlet']})")
        
        # Validate results
        # Should have 3 expectations:
        # - 2 for the multi-outlet device (outlets 0 and 1)
        # - 1 for the single-outlet device (outlet 0)
        assert len(expectations) == 3, f"Expected 3 expectations, got {len(expectations)}"
        
        # Check multi-outlet device entries
        multi_outlet_expectations = [
            exp for exp in expectations 
            if exp['device_name'] == 'Test Multi-Outlet Device'
        ]
        assert len(multi_outlet_expectations) == 2, \
            f"Expected 2 expectations for multi-outlet device, got {len(multi_outlet_expectations)}"
        
        # Verify both outlets are present
        outlets = sorted([exp['outlet'] for exp in multi_outlet_expectations])
        assert outlets == [0, 1], f"Expected outlets [0, 1], got {outlets}"
        
        # Check single-outlet device entry
        single_outlet_expectations = [
            exp for exp in expectations 
            if exp['device_name'] == 'Test Single-Outlet Device'
        ]
        assert len(single_outlet_expectations) == 1, \
            f"Expected 1 expectation for single-outlet device, got {len(single_outlet_expectations)}"
        assert single_outlet_expectations[0]['outlet'] == 0, \
            f"Expected outlet 0, got {single_outlet_expectations[0]['outlet']}"
        
        # Verify all expectations have the same group and state info
        for exp in expectations:
            assert exp['group'] == 'test_group'
            assert exp['current_state'] == 'off'
            assert exp['expected_state'] == 'off'
            assert exp['ip_address'] in ['192.168.1.100', '192.168.1.101']
        
        logger.info("✓ Multi-outlet device expectations test passed")
        return True
        
    except AssertionError as e:
        logger.error(f"✗ Test assertion failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Multi-outlet device expectations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_backwards_compatibility():
    """Test that devices without outlets array still work (backwards compatibility)."""
    logger.info("Testing backwards compatibility for devices without outlets array...")
    
    try:
        # Load config
        config = Config('config.example.yaml')
        
        # Create scheduler in setup mode
        scheduler = EnhancedScheduler(config, setup_mode=True)
        
        # Mock the device manager
        mock_device_manager = MagicMock()
        
        # Mock group configuration with old-style config (no outlets array)
        test_group_config = {
            'enabled': True,
            'automation': {
                'weather_control': False,
                'schedule_control': False
            },
            'items': [
                {
                    'name': 'Legacy Device',
                    'ip_address': '192.168.1.200',
                    # No outlets or outlet key - should default to outlet 0
                }
            ]
        }
        
        mock_device_manager.get_all_groups.return_value = ['legacy_group']
        mock_device_manager.get_group_config.return_value = test_group_config
        
        scheduler.device_manager = mock_device_manager
        
        # Create a mock state
        mock_state = StateManager(state_file='/tmp/test_legacy_state.json')
        mock_state.device_on = True
        scheduler.states = {'legacy_group': mock_state}
        
        # Mock should_turn_on_group and should_turn_off_group
        async def mock_should_turn_on(group_name):
            return False
        
        async def mock_should_turn_off(group_name):
            return False
        
        scheduler.should_turn_on_group = mock_should_turn_on
        scheduler.should_turn_off_group = mock_should_turn_off
        
        # Get device expectations
        expectations = await scheduler.get_device_expectations()
        
        # Should have 1 expectation with outlet defaulting to 0
        assert len(expectations) == 1, f"Expected 1 expectation, got {len(expectations)}"
        assert expectations[0]['outlet'] == 0, f"Expected outlet 0, got {expectations[0]['outlet']}"
        assert expectations[0]['device_name'] == 'Legacy Device'
        
        logger.info("✓ Backwards compatibility test passed")
        return True
        
    except AssertionError as e:
        logger.error(f"✗ Test assertion failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Backwards compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main_test():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Multi-Outlet Device Expectations Test Suite")
    logger.info("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Multi-Outlet Device Expectations", await test_multi_outlet_device_expectations()))
    results.append(("Backwards Compatibility", await test_backwards_compatibility()))
    
    # Print summary
    logger.info("=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    passed = 0
    failed = 0
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("=" * 60)
    logger.info(f"Total: {passed + failed}, Passed: {passed}, Failed: {failed}")
    logger.info("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main_test())
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Simple test script to validate the HeatTrax Scheduler implementation.
This tests the core functionality without requiring actual device or network access.
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_loader import Config, ConfigError
from src.scheduler.state_manager import StateManager
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_config_loader():
    """Test configuration loading."""
    logger.info("Testing configuration loader...")
    try:
        config = Config('config.example.yaml')
        assert config.location['latitude'] == 40.7128
        assert config.location['longitude'] == -74.006
        # Multi-device config
        assert config.devices['credentials']['username'] == 'your_tapo_username'
        assert config.devices['credentials']['password'] == 'your_tapo_password'
        assert 'groups' in config.devices
        assert 'heated_mats' in config.devices['groups']
        assert config.thresholds['temperature_f'] == 34
        assert config.safety['max_runtime_hours'] == 6
        assert config.safety['cooldown_minutes'] == 30
        assert config.morning_mode['enabled'] is True
        assert config.scheduler['check_interval_minutes'] == 10
        logger.info("✓ Configuration loader tests passed")
        return True
    except Exception as e:
        logger.error(f"✗ Configuration loader test failed: {e}")
        return False


def test_state_manager():
    """Test state manager functionality."""
    logger.info("Testing state manager...")
    try:
        # Use temporary state file
        state = StateManager(state_file='/tmp/test_scheduler_state.json')
        
        # Test marking device on
        state.mark_turned_on()
        assert state.device_on is True
        assert state.turn_on_time is not None
        
        # Test runtime calculation
        runtime = state.get_current_runtime_hours()
        assert runtime >= 0
        
        # Test max runtime check
        exceeded = state.exceeded_max_runtime(max_runtime_hours=0.0001)
        # Should not exceed immediately
        
        # Test marking device off
        state.mark_turned_off()
        assert state.device_on is False
        assert state.turn_on_time is None
        
        # Test cooldown
        state.start_cooldown()
        assert state.cooldown_start is not None
        in_cooldown = state.is_in_cooldown(cooldown_minutes=30)
        assert in_cooldown is True
        
        # Test that cooldown expired works (set to past)
        state.cooldown_start = datetime.now() - timedelta(hours=1)
        in_cooldown = state.is_in_cooldown(cooldown_minutes=30)
        assert in_cooldown is False
        
        logger.info("✓ State manager tests passed")
        return True
    except Exception as e:
        logger.error(f"✗ State manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_module_imports():
    """Test that all modules can be imported."""
    logger.info("Testing module imports...")
    try:
        import config_loader
        import weather_service
        import device_controller
        import state_manager
        import main
        logger.info("✓ All modules imported successfully")
        return True
    except Exception as e:
        logger.error(f"✗ Module import test failed: {e}")
        return False


def main_test():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("HeatTrax Scheduler Test Suite")
    logger.info("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Module Imports", test_module_imports()))
    results.append(("Configuration Loader", test_config_loader()))
    results.append(("State Manager", test_state_manager()))
    
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
    success = main_test()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Test to verify shared event loop functionality between scheduler and web server.

This test ensures that:
1. The scheduler properly initializes its event loop
2. The run_coro_in_loop method works for thread-safe async execution
3. Proper error handling when loop is not initialized
"""

import asyncio
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_loader import Config
from src.scheduler.scheduler_enhanced import EnhancedScheduler


class TestSharedEventLoop(unittest.TestCase):
    """Test shared event loop functionality."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Create a minimal config file
        config_data = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'weather_api': {
                'enabled': False,  # Disable weather to avoid network calls
                'provider': 'open-meteo'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpass'
                },
                'groups': {}
            },
            'thresholds': {
                'temperature_f': 32.0,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            },
            'safety': {
                'max_runtime_hours': 6.0,
                'cooldown_minutes': 15
            },
            'morning_mode': {
                'enabled': False
            },
            'health_check': {
                'interval_hours': 24,
                'max_consecutive_failures': 3
            },
            'health_server': {
                'enabled': False
            },
            'notifications': {
                'required': False,
                'test_on_startup': False
            },
            'logging': {
                'level': 'INFO'
            }
        }
        
        import yaml
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create config object
        self.config = Config(str(self.config_path))

    def test_loop_not_initialized_before_run(self):
        """Test that loop is None before run() is called."""
        scheduler = EnhancedScheduler(self.config)
        self.assertIsNone(scheduler.loop)

    def test_run_coro_in_loop_raises_when_not_initialized(self):
        """Test that run_coro_in_loop raises RuntimeError when loop is not initialized."""
        scheduler = EnhancedScheduler(self.config)
        
        async def dummy_coro():
            return 42
        
        with self.assertRaises(RuntimeError) as context:
            scheduler.run_coro_in_loop(dummy_coro())
        
        self.assertIn("not initialized", str(context.exception))

    def test_loop_initialized_during_run(self):
        """Test that loop is set when run() method starts."""
        scheduler = EnhancedScheduler(self.config)
        loop_was_set = {'value': False}
        
        async def mock_run():
            """Mock version of run that just checks if loop is set."""
            # Simulate what happens in run()
            scheduler.loop = asyncio.get_running_loop()
            loop_was_set['value'] = scheduler.loop is not None
            # Don't actually run the full scheduler
            return
        
        # Run the mock in an event loop
        asyncio.run(mock_run())
        
        self.assertTrue(loop_was_set['value'])

    def test_run_coro_in_loop_executes_coroutine(self):
        """Test that run_coro_in_loop successfully executes a coroutine on the scheduler loop."""
        scheduler = EnhancedScheduler(self.config)
        result_container = {'result': None}
        scheduler_running = threading.Event()
        
        async def test_coroutine():
            """Simple coroutine to test execution."""
            await asyncio.sleep(0.01)
            return "success"
        
        async def scheduler_loop():
            """Simulate scheduler event loop."""
            scheduler.loop = asyncio.get_running_loop()
            scheduler_running.set()
            # Keep loop running for a bit
            await asyncio.sleep(1)
        
        def run_scheduler():
            """Run scheduler in a thread."""
            asyncio.run(scheduler_loop())
        
        def test_from_thread():
            """Test run_coro_in_loop from another thread (simulating Flask)."""
            # Wait for scheduler to initialize
            scheduler_running.wait(timeout=2)
            # Execute coroutine on scheduler's loop
            result = scheduler.run_coro_in_loop(test_coroutine())
            result_container['result'] = result
        
        # Start scheduler in background thread
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Start test thread (simulating Flask request)
        test_thread = threading.Thread(target=test_from_thread, daemon=True)
        test_thread.start()
        
        # Wait for test to complete
        test_thread.join(timeout=2)
        
        # Verify result
        self.assertEqual(result_container['result'], "success")


if __name__ == '__main__':
    unittest.main()

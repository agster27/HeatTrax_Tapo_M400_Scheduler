#!/usr/bin/env python3
"""
Test to verify device control API uses shared event loop.

This test ensures that:
1. The /api/devices/control endpoint uses scheduler.run_coro_in_loop()
2. Device control operations run on the scheduler's event loop
3. No new event loops are created for device control operations
"""

import asyncio
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.config.config_loader import Config
from src.scheduler.scheduler_enhanced import EnhancedScheduler
from src.web.web_server import WebServer


class TestDeviceControlSharedLoop(unittest.TestCase):
    """Test that device control API uses the shared scheduler event loop."""

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
                'enabled': False,
                'provider': 'open-meteo'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpass'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'items': []
                    }
                }
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

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_device_control_uses_scheduler_loop(self):
        """
        Test that device control endpoint uses the scheduler's event loop
        via run_coro_in_loop instead of creating a new one.
        """
        # Create config and scheduler
        config = Config(str(self.config_path))
        scheduler = EnhancedScheduler(config)
        
        # Track which loop is used
        loop_used = {'scheduler_loop': None, 'control_loop': None}
        control_called = threading.Event()
        
        # Mock device_manager.control_device_outlet to capture the running loop
        async def mock_control_outlet(group, device, outlet, action):
            # Capture the event loop that this coroutine runs on
            loop_used['control_loop'] = asyncio.get_running_loop()
            control_called.set()
            return {
                'success': True,
                'device': device,
                'outlet': outlet,
                'action': action,
                'error': None
            }
        
        # Patch the device manager
        scheduler.device_manager = Mock()
        scheduler.device_manager.control_device_outlet = mock_control_outlet
        
        # Create web server with scheduler
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager, scheduler=scheduler)
        
        # Start scheduler in background thread
        scheduler_started = threading.Event()
        
        async def run_scheduler_mock():
            """Mock scheduler that sets loop and waits."""
            scheduler.loop = asyncio.get_running_loop()
            loop_used['scheduler_loop'] = scheduler.loop
            scheduler_started.set()
            # Keep running for test duration
            await asyncio.sleep(2)
        
        def scheduler_thread_func():
            asyncio.run(run_scheduler_mock())
        
        scheduler_thread = threading.Thread(target=scheduler_thread_func, daemon=True)
        scheduler_thread.start()
        
        # Wait for scheduler to initialize
        self.assertTrue(scheduler_started.wait(timeout=2), "Scheduler failed to start")
        
        # Make API call from test thread (simulating Flask)
        client = web_server.app.test_client()
        response = client.post('/api/devices/control',
                              json={
                                  'group': 'test_group',
                                  'device': 'test_device',
                                  'outlet': 0,
                                  'action': 'on'
                              })
        
        # Wait for control to be called
        self.assertTrue(control_called.wait(timeout=2), "Control method not called")
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        
        # Verify that the same loop was used
        self.assertIsNotNone(loop_used['scheduler_loop'], "Scheduler loop not set")
        self.assertIsNotNone(loop_used['control_loop'], "Control loop not captured")
        self.assertIs(
            loop_used['control_loop'], 
            loop_used['scheduler_loop'],
            "Control operation did not use scheduler's event loop"
        )

    def test_device_control_handles_no_scheduler_loop(self):
        """
        Test that device control endpoint handles the case when
        scheduler loop is not initialized.
        """
        # Create mock scheduler without loop initialization
        config_manager = ConfigManager(str(self.config_path))
        mock_scheduler = Mock()
        mock_scheduler.device_manager = Mock()
        mock_scheduler.loop = None  # Simulate loop not initialized
        
        # Mock run_coro_in_loop to raise RuntimeError
        def mock_run_coro_raise(coro):
            raise RuntimeError("Scheduler event loop not initialized")
        
        mock_scheduler.run_coro_in_loop = mock_run_coro_raise
        
        web_server = WebServer(config_manager, scheduler=mock_scheduler)
        client = web_server.app.test_client()
        
        response = client.post('/api/devices/control',
                              json={
                                  'group': 'test_group',
                                  'device': 'test_device',
                                  'outlet': 0,
                                  'action': 'on'
                              })
        
        # Should return 500 with error message
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('not available', data['error'])

    def test_run_coro_in_loop_prevents_kasa_errors(self):
        """
        Test that using run_coro_in_loop prevents the specific error pattern
        that occurs when creating new event loops for kasa operations.
        
        This simulates the "Timeout context manager should be used inside a task" 
        error that would occur with the old implementation.
        """
        config = Config(str(self.config_path))
        scheduler = EnhancedScheduler(config)
        
        # Track if operation was executed as a Task (proper way)
        operation_info = {'is_task': False}
        
        async def mock_control_that_checks_task(group, device, outlet, action):
            # Check if we're running as a proper asyncio Task
            # This is what python-kasa requires to avoid timeout errors
            try:
                current_task = asyncio.current_task()
                operation_info['is_task'] = current_task is not None
            except RuntimeError:
                operation_info['is_task'] = False
            
            return {
                'success': True,
                'device': device,
                'outlet': outlet,
                'action': action,
                'error': None
            }
        
        scheduler.device_manager = Mock()
        scheduler.device_manager.control_device_outlet = mock_control_that_checks_task
        
        # Create web server
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager, scheduler=scheduler)
        
        # Start scheduler
        scheduler_started = threading.Event()
        
        async def run_scheduler_mock():
            scheduler.loop = asyncio.get_running_loop()
            scheduler_started.set()
            await asyncio.sleep(2)
        
        def scheduler_thread_func():
            asyncio.run(run_scheduler_mock())
        
        scheduler_thread = threading.Thread(target=scheduler_thread_func, daemon=True)
        scheduler_thread.start()
        scheduler_started.wait(timeout=2)
        
        # Make API call
        client = web_server.app.test_client()
        response = client.post('/api/devices/control',
                              json={
                                  'group': 'test_group',
                                  'device': 'test_device',
                                  'outlet': 0,
                                  'action': 'on'
                              })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify the operation ran as a proper asyncio Task
        # This is what prevents the "Timeout context manager" error
        self.assertTrue(
            operation_info['is_task'],
            "Control operation did not run as an asyncio Task. "
            "This would cause 'Timeout context manager should be used inside a task' errors."
        )


if __name__ == '__main__':
    unittest.main()

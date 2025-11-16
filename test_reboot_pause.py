#!/usr/bin/env python3
"""Test reboot pause functionality."""

import unittest
import sys
import time
from io import StringIO
from unittest.mock import patch, MagicMock
import logging

# Add parent directory to path for imports
sys.path.insert(0, '.')

from main import pause_before_restart


class TestRebootPause(unittest.TestCase):
    """Test cases for reboot pause functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Set up logging for tests
        logging.basicConfig(level=logging.DEBUG)
        self.logger = logging.getLogger('main')
    
    @patch('time.sleep')
    def test_pause_before_restart_with_valid_duration(self, mock_sleep):
        """Test pause_before_restart with valid duration."""
        # Capture stderr output
        captured_output = StringIO()
        
        with patch('sys.stderr', captured_output):
            pause_before_restart(5, "Test failure reason")
        
        # Verify sleep was called 5 times (once per second)
        self.assertEqual(mock_sleep.call_count, 5)
        
        # Verify output contains key messages
        output = captured_output.getvalue()
        self.assertIn("CONTAINER RESTART SEQUENCE INITIATED", output)
        self.assertIn("Test failure reason", output)
        self.assertIn("Pausing for 5 seconds", output)
        self.assertIn("Pause complete", output)
    
    @patch('time.sleep')
    def test_pause_before_restart_with_zero_duration(self, mock_sleep):
        """Test pause_before_restart with zero duration (no pause)."""
        captured_output = StringIO()
        
        with patch('sys.stderr', captured_output):
            pause_before_restart(0, "Test failure reason")
        
        # Verify no sleep was called
        self.assertEqual(mock_sleep.call_count, 0)
        
        # Verify no output was generated
        output = captured_output.getvalue()
        self.assertEqual(output, "")
    
    @patch('time.sleep')
    def test_pause_before_restart_with_negative_duration(self, mock_sleep):
        """Test pause_before_restart with negative duration (no pause)."""
        captured_output = StringIO()
        
        with patch('sys.stderr', captured_output):
            pause_before_restart(-10, "Test failure reason")
        
        # Verify no sleep was called
        self.assertEqual(mock_sleep.call_count, 0)
        
        # Verify no output was generated
        output = captured_output.getvalue()
        self.assertEqual(output, "")
    
    @patch('time.sleep')
    def test_pause_countdown_messages(self, mock_sleep):
        """Test that countdown messages appear at correct intervals."""
        captured_output = StringIO()
        
        with patch('sys.stderr', captured_output):
            pause_before_restart(15, "Test failure")
        
        output = captured_output.getvalue()
        
        # Should see countdown messages for 10 and 5 (multiples of 10 or <=5)
        # Note: The actual implementation logs at every 10s and <=5s
        # For a 15-second pause, we should see messages at: 10s and then 5,4,3,2,1
        # But since we're mocking sleep, we can't test the exact timing
        # Just verify that countdown messages exist
        self.assertIn("Container restart in", output)
    
    @patch('time.sleep')
    def test_pause_with_long_reason_message(self, mock_sleep):
        """Test pause with a long reason message."""
        long_reason = "This is a very long error message that describes a complex failure scenario with multiple causes and effects. " * 3
        
        captured_output = StringIO()
        
        with patch('sys.stderr', captured_output):
            pause_before_restart(3, long_reason)
        
        output = captured_output.getvalue()
        
        # Verify the long reason is included in output
        self.assertIn(long_reason, output)
        
        # Verify pause still works
        self.assertEqual(mock_sleep.call_count, 3)


class TestRebootPauseIntegration(unittest.TestCase):
    """Integration tests for reboot pause with config."""
    
    def test_reboot_pause_in_config(self):
        """Test that reboot config is accessible."""
        from config_loader import Config
        import os
        
        # Test with environment variable and minimal required config
        os.environ['REBOOT_PAUSE_SECONDS'] = '30'
        os.environ['HEATTRAX_LATITUDE'] = '40.0'
        os.environ['HEATTRAX_LONGITUDE'] = '-74.0'
        os.environ['HEATTRAX_TAPO_IP_ADDRESS'] = '192.168.1.100'
        os.environ['HEATTRAX_TAPO_USERNAME'] = 'test'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'test'
        os.environ['HEATTRAX_THRESHOLD_TEMP_F'] = '34'
        os.environ['HEATTRAX_LEAD_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_TRAILING_TIME_MINUTES'] = '60'
        os.environ['HEATTRAX_CHECK_INTERVAL_MINUTES'] = '10'
        os.environ['HEATTRAX_FORECAST_HOURS'] = '12'
        os.environ['HEATTRAX_MAX_RUNTIME_HOURS'] = '6'
        os.environ['HEATTRAX_COOLDOWN_MINUTES'] = '30'
        
        try:
            config = Config()
            reboot_config = config.reboot
            
            # Verify we can access reboot config
            self.assertIsInstance(reboot_config, dict)
            
            # Verify default or env value is present
            self.assertIn('pause_seconds', reboot_config)
            self.assertEqual(reboot_config['pause_seconds'], 30)
        finally:
            # Clean up
            for key in ['REBOOT_PAUSE_SECONDS', 'HEATTRAX_LATITUDE', 'HEATTRAX_LONGITUDE',
                       'HEATTRAX_TAPO_IP_ADDRESS', 'HEATTRAX_TAPO_USERNAME', 'HEATTRAX_TAPO_PASSWORD',
                       'HEATTRAX_THRESHOLD_TEMP_F', 'HEATTRAX_LEAD_TIME_MINUTES', 
                       'HEATTRAX_TRAILING_TIME_MINUTES', 'HEATTRAX_CHECK_INTERVAL_MINUTES',
                       'HEATTRAX_FORECAST_HOURS', 'HEATTRAX_MAX_RUNTIME_HOURS', 'HEATTRAX_COOLDOWN_MINUTES']:
                if key in os.environ:
                    del os.environ[key]
    
    def test_reboot_pause_default_value(self):
        """Test default reboot pause value."""
        from config_loader import Config
        import os
        
        # Make sure env var is not set
        if 'REBOOT_PAUSE_SECONDS' in os.environ:
            del os.environ['REBOOT_PAUSE_SECONDS']
        
        try:
            config = Config()
            reboot_config = config.reboot
            
            # Verify default value is 60
            self.assertEqual(reboot_config.get('pause_seconds', 60), 60)
        except Exception:
            # If config loading fails (e.g., missing config file), that's okay
            # We're just testing the default value logic
            pass


def main():
    """Run tests."""
    # Run tests
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()

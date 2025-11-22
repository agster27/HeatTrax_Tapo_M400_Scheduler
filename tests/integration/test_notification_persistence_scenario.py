#!/usr/bin/env python3
"""
End-to-end scenario test for notification configuration persistence.
Demonstrates the fix for the bug where email notification toggle doesn't persist.
"""

import os
import sys
import unittest
import tempfile
import yaml
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager


class TestNotificationPersistenceScenario(unittest.TestCase):
    """
    End-to-end scenario test demonstrating the notification persistence fix.
    
    This test simulates the exact scenario described in the bug report:
    1. User has email notifications disabled
    2. User enables email via Web UI and provides SMTP settings
    3. User saves configuration
    4. Container/application restarts
    5. Email notifications should remain enabled
    """
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_end_to_end_notification_persistence(self):
        """
        Full end-to-end test of notification configuration persistence.
        
        Scenario:
        1. Application starts with default config (email disabled)
        2. User opens Web UI Configuration tab
        3. User enables "Email Enabled" checkbox
        4. User fills in SMTP settings
        5. User clicks "Save Configuration"
        6. Configuration is validated and saved
        7. Application restarts (simulated)
        8. Email notifications are loaded as enabled
        9. Notification service is initialized with email provider
        """
        print("\n=== Starting End-to-End Notification Persistence Test ===\n")
        
        # Step 1: Initial startup with default config
        print("Step 1: Initial startup - email notifications disabled by default")
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        # Verify initial state
        self.assertFalse(config['notifications']['email']['enabled'])
        print(f"  ✓ Email enabled: {config['notifications']['email']['enabled']}")
        
        # Step 2: User opens Web UI and gets config (simulated)
        print("\nStep 2: User opens Web UI Configuration tab")
        ui_config = config_manager.get_config(include_secrets=False)
        print(f"  ✓ UI loads config with email enabled: {ui_config['notifications']['email']['enabled']}")
        self.assertFalse(ui_config['notifications']['email']['enabled'])
        
        # Step 3: User enables email and fills in settings
        print("\nStep 3: User enables email and fills in SMTP settings")
        ui_config['notifications']['email']['enabled'] = True
        ui_config['notifications']['email']['smtp_host'] = 'smtp.gmail.com'
        ui_config['notifications']['email']['smtp_port'] = 587
        ui_config['notifications']['email']['smtp_username'] = 'heattrax@gmail.com'
        ui_config['notifications']['email']['smtp_password'] = 'app_specific_password'
        ui_config['notifications']['email']['from_email'] = 'heattrax@gmail.com'
        ui_config['notifications']['email']['to_emails'] = ['admin@example.com']
        ui_config['notifications']['email']['use_tls'] = True
        
        print("  ✓ Email enabled checkbox: checked")
        print("  ✓ SMTP Host: smtp.gmail.com")
        print("  ✓ SMTP Port: 587")
        print("  ✓ From Email: heattrax@gmail.com")
        print("  ✓ To Emails: admin@example.com")
        
        # Step 4: User clicks "Save Configuration"
        print("\nStep 4: User clicks 'Save Configuration'")
        
        # Merge with full config (as the Web UI does)
        full_config = config_manager.get_config(include_secrets=True)
        for key in ['enabled', 'smtp_host', 'smtp_port', 'smtp_username', 
                    'smtp_password', 'from_email', 'to_emails', 'use_tls']:
            full_config['notifications']['email'][key] = ui_config['notifications']['email'][key]
        
        # Save via config manager
        result = config_manager.update_config(full_config, preserve_secrets=True)
        
        print(f"  ✓ Validation: {result['status']}")
        self.assertEqual(result['status'], 'ok', f"Save failed: {result.get('message')}")
        print(f"  ✓ Config written to disk: {self.config_path}")
        
        # Step 5: Verify in-memory config updated
        print("\nStep 5: Verify in-memory configuration updated")
        updated_config = config_manager.get_config(include_secrets=True)
        self.assertTrue(updated_config['notifications']['email']['enabled'])
        self.assertEqual(updated_config['notifications']['email']['smtp_host'], 'smtp.gmail.com')
        print(f"  ✓ In-memory email enabled: {updated_config['notifications']['email']['enabled']}")
        
        # Step 6: Verify on-disk config persisted
        print("\nStep 6: Verify configuration persisted to disk")
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertTrue(disk_config['notifications']['email']['enabled'])
        self.assertEqual(disk_config['notifications']['email']['smtp_host'], 'smtp.gmail.com')
        print(f"  ✓ On-disk email enabled: {disk_config['notifications']['email']['enabled']}")
        print(f"  ✓ On-disk SMTP host: {disk_config['notifications']['email']['smtp_host']}")
        
        # Step 7: Simulate application restart
        print("\nStep 7: Simulating application restart (container restart)")
        del config_manager
        del updated_config
        
        # Create new config manager (simulates fresh startup)
        config_manager_restart = ConfigManager(str(self.config_path))
        
        # Step 8: Verify email still enabled after restart
        print("\nStep 8: Verify email notifications remain enabled after restart")
        restarted_config = config_manager_restart.get_config(include_secrets=True)
        
        self.assertTrue(restarted_config['notifications']['email']['enabled'])
        self.assertEqual(restarted_config['notifications']['email']['smtp_host'], 'smtp.gmail.com')
        self.assertEqual(restarted_config['notifications']['email']['smtp_port'], 587)
        self.assertEqual(restarted_config['notifications']['email']['to_emails'], ['admin@example.com'])
        
        print(f"  ✓ Email enabled after restart: {restarted_config['notifications']['email']['enabled']}")
        print(f"  ✓ SMTP configuration preserved: {restarted_config['notifications']['email']['smtp_host']}")
        
        # Step 9: Verify notification service would be initialized
        print("\nStep 9: Verify notification service would initialize with email provider")
        
        # Simulate what the scheduler would do
        notifications_config = restarted_config.get('notifications', {})
        email_config = notifications_config.get('email', {})
        
        if email_config.get('enabled', False):
            print("  ✓ Notification service would initialize EmailNotificationProvider")
            print(f"    - SMTP Host: {email_config['smtp_host']}")
            print(f"    - Recipients: {', '.join(email_config['to_emails'])}")
            
            # The scheduler log line mentioned in the requirements would NOT appear
            print("  ✓ Scheduler log would NOT show: 'Notifications not enabled, skipping...'")
        else:
            self.fail("Email should be enabled but was not!")
        
        print("\n=== Test Passed: Email notifications persist correctly! ===\n")
    
    def test_validation_prevents_invalid_config(self):
        """
        Test that validation prevents saving invalid notification config.
        
        This ensures users get immediate feedback if they enable email
        without providing complete SMTP settings.
        """
        print("\n=== Testing Validation Prevents Invalid Configuration ===\n")
        
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=True)
        
        # Try to enable email without providing SMTP settings
        print("Attempting to enable email without SMTP host...")
        config['notifications']['email']['enabled'] = True
        # Leave smtp_host empty
        
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'error')
        print(f"  ✓ Validation failed as expected: {result['message']}")
        
        # Verify config was NOT written to disk
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        # Should still be disabled (unchanged)
        self.assertFalse(disk_config['notifications']['email']['enabled'])
        print("  ✓ Invalid config NOT written to disk")
        
        # Verify in-memory config unchanged
        current_config = config_manager.get_config(include_secrets=True)
        self.assertFalse(current_config['notifications']['email']['enabled'])
        print("  ✓ In-memory config unchanged")
        
        print("\n=== Test Passed: Validation works correctly! ===\n")


if __name__ == '__main__':
    # Run with verbose output to show the scenario steps
    unittest.main(verbosity=2)

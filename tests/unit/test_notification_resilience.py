#!/usr/bin/env python3
"""Tests for notification resilience in scheduler."""

import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.notifications.notification_service import validate_and_test_notifications


class TestNotificationResilience(unittest.TestCase):
    """Test notification resilience - scheduler should not crash on notification failures."""
    
    def test_validate_notifications_returns_false_on_failure(self):
        """Test that validate_and_test_notifications returns (False, None) on failure."""
        async def run_test():
            # Simulate email auth failure
            config = {
                'required': True,
                'test_on_startup': True,
                'email': {
                    'enabled': True,
                    'smtp_host': 'smtp.gmail.com',
                    'smtp_port': 587,
                    'smtp_username': 'test@example.com',
                    'smtp_password': 'wrong_password',
                    'from_email': 'test@example.com',
                    'to_emails': ['recipient@example.com']
                }
            }
            
            success, service = await validate_and_test_notifications(
                config,
                test_connectivity=True,
                send_test=False
            )
            
            # Should return False but not raise exception
            self.assertFalse(success)
            self.assertIsNone(service)
        
        asyncio.run(run_test())
    
    def test_validate_notifications_succeeds_with_disabled_providers(self):
        """Test that validate_and_test_notifications succeeds when all providers disabled."""
        async def run_test():
            config = {
                'required': False,
                'test_on_startup': False,
                'email': {
                    'enabled': False
                },
                'webhook': {
                    'enabled': False
                }
            }
            
            success, service = await validate_and_test_notifications(
                config,
                test_connectivity=False,
                send_test=False
            )
            
            # Should succeed with disabled service
            self.assertTrue(success)
            self.assertIsNotNone(service)
            self.assertFalse(service.is_enabled())
        
        asyncio.run(run_test())
    
    def test_validate_notifications_handles_missing_config(self):
        """Test that validate_and_test_notifications handles missing email config fields."""
        async def run_test():
            # Missing required fields
            config = {
                'required': False,
                'email': {
                    'enabled': True,
                    'smtp_host': 'smtp.gmail.com',
                    # Missing other required fields
                }
            }
            
            success, service = await validate_and_test_notifications(
                config,
                test_connectivity=False,
                send_test=False
            )
            
            # Should return False but not raise exception
            self.assertFalse(success)
            self.assertIsNone(service)
        
        asyncio.run(run_test())
    
    def test_validate_notifications_with_connectivity_test_failure(self):
        """Test that validate_and_test_notifications handles connectivity test failures gracefully."""
        async def run_test():
            # Valid config but connectivity will fail
            with patch('src.notifications.notification_service.EmailNotificationProvider.test_connectivity',
                      new_callable=AsyncMock) as mock_test:
                mock_test.return_value = (False, "Connection refused")
                
                config = {
                    'required': True,
                    'test_on_startup': False,
                    'email': {
                        'enabled': True,
                        'smtp_host': 'smtp.gmail.com',
                        'smtp_port': 587,
                        'smtp_username': 'test@example.com',
                        'smtp_password': 'test_password',
                        'from_email': 'test@example.com',
                        'to_emails': ['recipient@example.com']
                    }
                }
                
                success, service = await validate_and_test_notifications(
                    config,
                    test_connectivity=True,
                    send_test=False
                )
                
                # Should return False but not raise exception
                self.assertFalse(success)
                self.assertIsNone(service)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()

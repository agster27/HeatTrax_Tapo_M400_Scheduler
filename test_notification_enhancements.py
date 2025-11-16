#!/usr/bin/env python3
"""Tests for notification service enhancements."""

import unittest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from notification_service import (
    NotificationService,
    EmailNotificationProvider,
    WebhookNotificationProvider,
    create_notification_service_from_config,
    validate_and_test_notifications,
    NotificationValidationError
)


class TestProviderValidation(unittest.TestCase):
    """Test provider validation methods."""
    
    def test_email_validate_config_success(self):
        """Test email config validation with valid config."""
        provider = EmailNotificationProvider(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails=["to@example.com"]
        )
        
        is_valid, error_msg = provider.validate_config()
        self.assertTrue(is_valid)
        self.assertIsNone(error_msg)
    
    def test_email_validate_config_missing_host(self):
        """Test email config validation with missing host."""
        provider = EmailNotificationProvider(
            smtp_host="",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails=["to@example.com"]
        )
        
        is_valid, error_msg = provider.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("smtp_host", error_msg)
    
    def test_email_validate_config_empty_recipients(self):
        """Test email config validation with empty recipients."""
        provider = EmailNotificationProvider(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails=[]
        )
        
        is_valid, error_msg = provider.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("to_emails", error_msg)
    
    def test_webhook_validate_config_success(self):
        """Test webhook config validation with valid config."""
        provider = WebhookNotificationProvider(
            webhook_url="https://example.com/webhook"
        )
        
        is_valid, error_msg = provider.validate_config()
        self.assertTrue(is_valid)
        self.assertIsNone(error_msg)
    
    def test_webhook_validate_config_missing_url(self):
        """Test webhook config validation with missing URL."""
        provider = WebhookNotificationProvider(webhook_url="")
        
        is_valid, error_msg = provider.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("url", error_msg)
    
    def test_webhook_validate_config_invalid_url(self):
        """Test webhook config validation with invalid URL."""
        provider = WebhookNotificationProvider(webhook_url="not-a-url")
        
        is_valid, error_msg = provider.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("invalid", error_msg.lower())
    
    def test_webhook_validate_config_invalid_scheme(self):
        """Test webhook config validation with invalid scheme."""
        provider = WebhookNotificationProvider(webhook_url="ftp://example.com")
        
        is_valid, error_msg = provider.validate_config()
        self.assertFalse(is_valid)
        self.assertIn("http", error_msg.lower())


class TestProviderConnectivity(unittest.TestCase):
    """Test provider connectivity methods."""
    
    def test_email_connectivity_success(self):
        """Test email connectivity check success."""
        async def run_test():
            provider = EmailNotificationProvider(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user",
                smtp_password="pass",
                from_email="from@example.com",
                to_emails=["to@example.com"]
            )
            
            with patch.object(provider, '_test_smtp_connection'):
                is_connected, error_msg = await provider.test_connectivity()
                self.assertTrue(is_connected)
                self.assertIsNone(error_msg)
        
        asyncio.run(run_test())
    
    def test_email_connectivity_failure(self):
        """Test email connectivity check failure."""
        async def run_test():
            provider = EmailNotificationProvider(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user",
                smtp_password="pass",
                from_email="from@example.com",
                to_emails=["to@example.com"]
            )
            
            with patch.object(provider, '_test_smtp_connection', side_effect=Exception("Connection failed")):
                is_connected, error_msg = await provider.test_connectivity()
                self.assertFalse(is_connected)
                self.assertIsNotNone(error_msg)
                self.assertIn("Connection failed", error_msg)
        
        asyncio.run(run_test())
    
    def test_webhook_connectivity_success(self):
        """Test webhook connectivity check success."""
        async def run_test():
            provider = WebhookNotificationProvider(
                webhook_url="https://example.com/webhook"
            )
            
            # Mock aiohttp session
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            mock_session = AsyncMock()
            mock_session.head = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            with patch('notification_service.aiohttp.ClientSession', return_value=mock_session):
                is_connected, error_msg = await provider.test_connectivity()
                self.assertTrue(is_connected)
                self.assertIsNone(error_msg)
        
        asyncio.run(run_test())
    
    def test_webhook_connectivity_server_error(self):
        """Test webhook connectivity check with server error."""
        async def run_test():
            provider = WebhookNotificationProvider(
                webhook_url="https://example.com/webhook"
            )
            
            # Mock aiohttp session with 500 error
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            mock_session = AsyncMock()
            mock_session.head = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            with patch('notification_service.aiohttp.ClientSession', return_value=mock_session):
                is_connected, error_msg = await provider.test_connectivity()
                self.assertFalse(is_connected)
                self.assertIn("500", error_msg)
        
        asyncio.run(run_test())


class TestNotificationRouting(unittest.TestCase):
    """Test per-event notification routing."""
    
    def test_routing_no_config(self):
        """Test routing with no routing config (all events to all providers)."""
        service = NotificationService(routing=None)
        
        provider1 = Mock()
        provider2 = Mock()
        service.add_provider('email', provider1)
        service.add_provider('webhook', provider2)
        
        providers = service.get_providers_for_event('device_lost')
        self.assertEqual(len(providers), 2)
        self.assertIn(('email', provider1), providers)
        self.assertIn(('webhook', provider2), providers)
    
    def test_routing_event_not_configured(self):
        """Test routing for event not in routing config (send to all)."""
        routing = {
            'device_lost': {'email': True, 'webhook': False}
        }
        service = NotificationService(routing=routing)
        
        provider1 = Mock()
        provider2 = Mock()
        service.add_provider('email', provider1)
        service.add_provider('webhook', provider2)
        
        # Event not in routing config
        providers = service.get_providers_for_event('device_found')
        self.assertEqual(len(providers), 2)
    
    def test_routing_email_only(self):
        """Test routing that sends to email only."""
        routing = {
            'device_lost': {'email': True, 'webhook': False}
        }
        service = NotificationService(routing=routing)
        
        provider1 = Mock()
        provider2 = Mock()
        service.add_provider('email', provider1)
        service.add_provider('webhook', provider2)
        
        providers = service.get_providers_for_event('device_lost')
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0][0], 'email')
    
    def test_routing_webhook_only(self):
        """Test routing that sends to webhook only."""
        routing = {
            'device_ip_changed': {'email': False, 'webhook': True}
        }
        service = NotificationService(routing=routing)
        
        provider1 = Mock()
        provider2 = Mock()
        service.add_provider('email', provider1)
        service.add_provider('webhook', provider2)
        
        providers = service.get_providers_for_event('device_ip_changed')
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0][0], 'webhook')
    
    def test_routing_none(self):
        """Test routing that sends to no providers."""
        routing = {
            'test_event': {'email': False, 'webhook': False}
        }
        service = NotificationService(routing=routing)
        
        provider1 = Mock()
        provider2 = Mock()
        service.add_provider('email', provider1)
        service.add_provider('webhook', provider2)
        
        providers = service.get_providers_for_event('test_event')
        self.assertEqual(len(providers), 0)


class TestNotificationServiceWithRouting(unittest.TestCase):
    """Test notification service notify method with routing."""
    
    def test_notify_with_routing(self):
        """Test notify respects routing configuration."""
        async def run_test():
            routing = {
                'device_lost': {'email': True, 'webhook': False}
            }
            service = NotificationService(routing=routing)
            
            # Create mock providers
            mock_email = Mock()
            mock_email.send = AsyncMock(return_value=True)
            mock_webhook = Mock()
            mock_webhook.send = AsyncMock(return_value=True)
            
            service.add_provider('email', mock_email)
            service.add_provider('webhook', mock_webhook)
            
            await service.notify('device_lost', 'Test message', {})
            
            # Email should be called, webhook should not
            mock_email.send.assert_called_once()
            mock_webhook.send.assert_not_called()
        
        asyncio.run(run_test())


class TestTestNotification(unittest.TestCase):
    """Test sending test notifications."""
    
    def test_send_test_notification_success(self):
        """Test sending test notification successfully."""
        async def run_test():
            service = NotificationService()
            
            mock_provider = Mock()
            mock_provider.send = AsyncMock(return_value=True)
            service.add_provider('email', mock_provider)
            
            result = await service.send_test_notification()
            
            self.assertTrue(result)
            mock_provider.send.assert_called_once()
            call_args = mock_provider.send.call_args
            self.assertEqual(call_args[0][0], 'startup_test')
        
        asyncio.run(run_test())
    
    def test_send_test_notification_failure(self):
        """Test sending test notification with failure."""
        async def run_test():
            service = NotificationService()
            
            mock_provider = Mock()
            mock_provider.send = AsyncMock(return_value=False)
            service.add_provider('email', mock_provider)
            
            result = await service.send_test_notification()
            
            self.assertFalse(result)
        
        asyncio.run(run_test())


class TestCreateServiceFromConfig(unittest.TestCase):
    """Test creating notification service from configuration."""
    
    def test_create_service_email_missing_fields(self):
        """Test creating service with email enabled but missing fields."""
        config = {
            'email': {
                'enabled': True,
                'smtp_host': 'smtp.example.com'
                # Missing other required fields
            }
        }
        
        with self.assertRaises(NotificationValidationError):
            create_notification_service_from_config(config)
    
    def test_create_service_webhook_missing_url(self):
        """Test creating service with webhook enabled but missing URL."""
        config = {
            'webhook': {
                'enabled': True
                # Missing url
            }
        }
        
        with self.assertRaises(NotificationValidationError):
            create_notification_service_from_config(config)
    
    def test_create_service_with_routing(self):
        """Test creating service with routing configuration."""
        config = {
            'routing': {
                'device_lost': {'email': True, 'webhook': False}
            },
            'email': {
                'enabled': True,
                'smtp_host': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'user',
                'smtp_password': 'pass',
                'from_email': 'from@example.com',
                'to_emails': ['to@example.com']
            }
        }
        
        service = create_notification_service_from_config(config)
        self.assertTrue(service.is_enabled())
        self.assertIsNotNone(service.routing)
        self.assertEqual(len(service.routing), 1)


class TestValidateAndTestNotifications(unittest.TestCase):
    """Test validate_and_test_notifications function."""
    
    def test_validate_success_no_tests(self):
        """Test validation succeeds without connectivity/test."""
        async def run_test():
            config = {
                'email': {
                    'enabled': True,
                    'smtp_host': 'smtp.example.com',
                    'smtp_port': 587,
                    'smtp_username': 'user',
                    'smtp_password': 'pass',
                    'from_email': 'from@example.com',
                    'to_emails': ['to@example.com']
                }
            }
            
            success, service = await validate_and_test_notifications(
                config,
                test_connectivity=False,
                send_test=False
            )
            
            self.assertTrue(success)
            self.assertIsNotNone(service)
            self.assertTrue(service.is_enabled())
        
        asyncio.run(run_test())
    
    def test_validate_with_connectivity_test(self):
        """Test validation with connectivity test."""
        async def run_test():
            config = {
                'email': {
                    'enabled': True,
                    'smtp_host': 'smtp.example.com',
                    'smtp_port': 587,
                    'smtp_username': 'user',
                    'smtp_password': 'pass',
                    'from_email': 'from@example.com',
                    'to_emails': ['to@example.com']
                }
            }
            
            # Mock connectivity test to succeed
            with patch('notification_service.EmailNotificationProvider.test_connectivity',
                      new_callable=AsyncMock, return_value=(True, None)):
                success, service = await validate_and_test_notifications(
                    config,
                    test_connectivity=True,
                    send_test=False
                )
                
                self.assertTrue(success)
                self.assertIsNotNone(service)
        
        asyncio.run(run_test())
    
    def test_validate_connectivity_failure(self):
        """Test validation fails on connectivity test failure."""
        async def run_test():
            config = {
                'email': {
                    'enabled': True,
                    'smtp_host': 'smtp.example.com',
                    'smtp_port': 587,
                    'smtp_username': 'user',
                    'smtp_password': 'pass',
                    'from_email': 'from@example.com',
                    'to_emails': ['to@example.com']
                }
            }
            
            # Mock connectivity test to fail
            with patch('notification_service.EmailNotificationProvider.test_connectivity',
                      new_callable=AsyncMock, return_value=(False, "Connection failed")):
                success, service = await validate_and_test_notifications(
                    config,
                    test_connectivity=True,
                    send_test=False
                )
                
                self.assertFalse(success)
                self.assertIsNone(service)
        
        asyncio.run(run_test())
    
    def test_validate_with_test_notification(self):
        """Test validation with test notification."""
        async def run_test():
            config = {
                'webhook': {
                    'enabled': True,
                    'url': 'https://example.com/webhook'
                }
            }
            
            # Mock connectivity and send
            with patch('notification_service.WebhookNotificationProvider.test_connectivity',
                      new_callable=AsyncMock, return_value=(True, None)):
                with patch('notification_service.WebhookNotificationProvider.send',
                          new_callable=AsyncMock, return_value=True):
                    success, service = await validate_and_test_notifications(
                        config,
                        test_connectivity=True,
                        send_test=True
                    )
                    
                    self.assertTrue(success)
                    self.assertIsNotNone(service)
        
        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()

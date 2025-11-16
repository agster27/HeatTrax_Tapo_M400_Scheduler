#!/usr/bin/env python3
"""Tests for notification service module."""

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
    create_notification_service_from_config
)


class TestNotificationService(unittest.TestCase):
    """Test NotificationService class."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        service = NotificationService()
        self.assertFalse(service.is_enabled())
        self.assertEqual(len(service.providers), 0)
    
    def test_add_provider(self):
        """Test adding a provider."""
        service = NotificationService()
        provider = Mock()
        
        service.add_provider('test', provider)
        
        self.assertTrue(service.is_enabled())
        self.assertEqual(len(service.providers), 1)
    
    def test_notify_disabled(self):
        """Test notification when disabled."""
        async def run_test():
            service = NotificationService()
            
            # Should not raise exception
            await service.notify("test_event", "Test message")
        
        asyncio.run(run_test())
    
    def test_notify_enabled(self):
        """Test notification when enabled."""
        async def run_test():
            service = NotificationService()
            
            # Create mock provider
            mock_provider = Mock()
            mock_provider.send = AsyncMock(return_value=True)
            
            service.add_provider('test', mock_provider)
            
            await service.notify("test_event", "Test message", {"key": "value"})
            
            mock_provider.send.assert_called_once()
            call_args = mock_provider.send.call_args
            self.assertEqual(call_args[0][0], "test_event")
            self.assertEqual(call_args[0][1], "Test message")
            self.assertEqual(call_args[0][2], {"key": "value"})
        
        asyncio.run(run_test())


class TestEmailNotificationProvider(unittest.TestCase):
    """Test EmailNotificationProvider class."""
    
    def test_provider_initialization(self):
        """Test provider initialization."""
        provider = EmailNotificationProvider(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails=["to@example.com"],
            use_tls=True
        )
        
        self.assertEqual(provider.smtp_host, "smtp.example.com")
        self.assertEqual(provider.smtp_port, 587)
        self.assertEqual(provider.to_emails, ["to@example.com"])
    
    def test_email_send_success(self):
        """Test sending email successfully."""
        async def run_test():
            provider = EmailNotificationProvider(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user",
                smtp_password="pass",
                from_email="from@example.com",
                to_emails=["to@example.com"]
            )
            
            with patch.object(provider, '_send_smtp') as mock_send:
                result = await provider.send(
                    "test_event",
                    "Test message",
                    {"key": "value"}
                )
                
                self.assertTrue(result)
                mock_send.assert_called_once()
        
        asyncio.run(run_test())
    
    def test_email_send_failure(self):
        """Test email send failure."""
        async def run_test():
            provider = EmailNotificationProvider(
                smtp_host="smtp.example.com",
                smtp_port=587,
                smtp_username="user",
                smtp_password="pass",
                from_email="from@example.com",
                to_emails=["to@example.com"]
            )
            
            with patch.object(provider, '_send_smtp', side_effect=Exception("SMTP error")):
                result = await provider.send(
                    "test_event",
                    "Test message",
                    {}
                )
                
                self.assertFalse(result)
        
        asyncio.run(run_test())


class TestWebhookNotificationProvider(unittest.TestCase):
    """Test WebhookNotificationProvider class."""
    
    def test_provider_initialization(self):
        """Test provider initialization."""
        provider = WebhookNotificationProvider(
            webhook_url="https://example.com/webhook"
        )
        
        self.assertEqual(provider.webhook_url, "https://example.com/webhook")
        self.assertIn('Content-Type', provider.headers)
    
    def test_webhook_send_success(self):
        """Test sending webhook successfully."""
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
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            with patch('notification_service.aiohttp.ClientSession', return_value=mock_session):
                result = await provider.send(
                    "test_event",
                    "Test message",
                    {"key": "value"}
                )
                
                self.assertTrue(result)
        
        asyncio.run(run_test())
    
    def test_webhook_send_failure(self):
        """Test webhook send failure."""
        async def run_test():
            provider = WebhookNotificationProvider(
                webhook_url="https://example.com/webhook"
            )
            
            # Mock failed response
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Server error")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            mock_session = AsyncMock()
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            with patch('notification_service.aiohttp.ClientSession', return_value=mock_session):
                result = await provider.send(
                    "test_event",
                    "Test message",
                    {}
                )
                
                self.assertFalse(result)
        
        asyncio.run(run_test())


class TestCreateNotificationService(unittest.TestCase):
    """Test creating notification service from config."""
    
    def test_create_service_empty_config(self):
        """Test creating service with empty config."""
        service = create_notification_service_from_config({})
        self.assertFalse(service.is_enabled())
    
    def test_create_service_email_disabled(self):
        """Test creating service with email disabled."""
        config = {
            'email': {'enabled': False}
        }
        service = create_notification_service_from_config(config)
        self.assertFalse(service.is_enabled())
    
    def test_create_service_email_enabled(self):
        """Test creating service with email enabled."""
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
        service = create_notification_service_from_config(config)
        self.assertTrue(service.is_enabled())
        self.assertEqual(len(service.providers), 1)
    
    def test_create_service_webhook_enabled(self):
        """Test creating service with webhook enabled."""
        config = {
            'webhook': {
                'enabled': True,
                'url': 'https://example.com/webhook'
            }
        }
        service = create_notification_service_from_config(config)
        self.assertTrue(service.is_enabled())
        self.assertEqual(len(service.providers), 1)
    
    def test_create_service_both_enabled(self):
        """Test creating service with both providers enabled."""
        config = {
            'email': {
                'enabled': True,
                'smtp_host': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_username': 'user',
                'smtp_password': 'pass',
                'from_email': 'from@example.com',
                'to_emails': ['to@example.com']
            },
            'webhook': {
                'enabled': True,
                'url': 'https://example.com/webhook'
            }
        }
        service = create_notification_service_from_config(config)
        self.assertTrue(service.is_enabled())
        self.assertEqual(len(service.providers), 2)


if __name__ == '__main__':
    unittest.main()

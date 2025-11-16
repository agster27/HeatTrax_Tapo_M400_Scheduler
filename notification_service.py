"""Notification service for health check events."""

import asyncio
import logging
import smtplib
import aiohttp
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Notification error exception."""
    pass


class NotificationProvider(ABC):
    """Abstract base class for notification providers."""
    
    @abstractmethod
    async def send(self, event_type: str, message: str, details: Dict[str, Any]) -> bool:
        """
        Send a notification.
        
        Args:
            event_type: Type of event (e.g., "device_lost", "device_ip_changed")
            message: Human-readable message
            details: Additional details about the event
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        pass


class EmailNotificationProvider(NotificationProvider):
    """Email notification provider using SMTP."""
    
    def __init__(self, smtp_host: str, smtp_port: int, smtp_username: str, 
                 smtp_password: str, from_email: str, to_emails: List[str],
                 use_tls: bool = True):
        """
        Initialize email notification provider.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP authentication username
            smtp_password: SMTP authentication password
            from_email: From email address
            to_emails: List of recipient email addresses
            use_tls: Whether to use TLS (default True)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = to_emails
        self.use_tls = use_tls
        
        logger.info(f"Email notifications configured: {smtp_host}:{smtp_port} -> {', '.join(to_emails)}")
    
    async def send(self, event_type: str, message: str, details: Dict[str, Any]) -> bool:
        """
        Send email notification.
        
        Args:
            event_type: Type of event
            message: Human-readable message
            details: Additional details about the event
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Format subject line
            subject = f"HeatTrax Alert: {event_type.replace('_', ' ').title()}"
            
            # Create email body
            body_parts = [
                f"HeatTrax Scheduler Alert",
                f"",
                f"Event: {event_type}",
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"",
                f"Message:",
                f"{message}",
                f"",
            ]
            
            if details:
                body_parts.append("Details:")
                for key, value in details.items():
                    body_parts.append(f"  {key}: {value}")
                body_parts.append("")
            
            body_parts.append("---")
            body_parts.append("This is an automated message from HeatTrax Scheduler")
            
            body = "\n".join(body_parts)
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email in thread pool (SMTP is blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg)
            
            logger.info(f"Email notification sent: {event_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            return False
    
    def _send_smtp(self, msg: MIMEMultipart):
        """
        Send SMTP email (blocking operation).
        
        Args:
            msg: Email message to send
        """
        if self.use_tls:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)


class WebhookNotificationProvider(NotificationProvider):
    """Webhook notification provider using HTTP POST."""
    
    def __init__(self, webhook_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize webhook notification provider.
        
        Args:
            webhook_url: Webhook URL to POST to
            headers: Optional custom headers to include in request
        """
        self.webhook_url = webhook_url
        self.headers = headers or {}
        
        # Set default content type if not specified
        if 'Content-Type' not in self.headers:
            self.headers['Content-Type'] = 'application/json'
        
        logger.info(f"Webhook notifications configured: {webhook_url}")
    
    async def send(self, event_type: str, message: str, details: Dict[str, Any]) -> bool:
        """
        Send webhook notification.
        
        Args:
            event_type: Type of event
            message: Human-readable message
            details: Additional details about the event
            
        Returns:
            True if webhook sent successfully, False otherwise
        """
        try:
            # Create payload
            payload = {
                'event_type': event_type,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'details': details,
                'source': 'heattrax_scheduler'
            }
            
            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status < 400:
                        logger.info(f"Webhook notification sent: {event_type} (status: {response.status})")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(
                            f"Webhook notification failed: {event_type} "
                            f"(status: {response.status}, response: {response_text[:200]})"
                        )
                        return False
                        
        except asyncio.TimeoutError:
            logger.error(f"Webhook notification timeout: {event_type}")
            return False
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            return False


class NotificationService:
    """Service for sending notifications about health check events."""
    
    def __init__(self):
        """Initialize notification service."""
        self.providers: List[NotificationProvider] = []
        self._enabled = False
        logger.info("Notification service initialized")
    
    def add_provider(self, provider: NotificationProvider):
        """
        Add a notification provider.
        
        Args:
            provider: Notification provider to add
        """
        self.providers.append(provider)
        self._enabled = True
        logger.info(f"Added notification provider: {type(provider).__name__}")
    
    def is_enabled(self) -> bool:
        """
        Check if notifications are enabled.
        
        Returns:
            True if at least one provider is configured
        """
        return self._enabled and len(self.providers) > 0
    
    async def notify(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Send notification to all configured providers.
        
        Args:
            event_type: Type of event (e.g., "device_lost", "device_ip_changed", "connectivity_lost")
            message: Human-readable message
            details: Optional additional details about the event
        """
        if not self.is_enabled():
            logger.debug(f"Notifications disabled, skipping: {event_type}")
            return
        
        if details is None:
            details = {}
        
        logger.info(f"Sending notification: {event_type}")
        logger.debug(f"Message: {message}")
        logger.debug(f"Details: {details}")
        
        # Send to all providers concurrently
        tasks = [
            provider.send(event_type, message, details)
            for provider in self.providers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        success_count = sum(1 for r in results if r is True)
        logger.info(f"Notification sent to {success_count}/{len(self.providers)} provider(s)")
        
        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Provider {i} raised exception: {result}")


def create_notification_service_from_config(config: Dict[str, Any]) -> NotificationService:
    """
    Create notification service from configuration.
    
    Args:
        config: Configuration dictionary with notification settings
        
    Returns:
        Configured NotificationService instance
    """
    service = NotificationService()
    
    # Email notifications
    email_config = config.get('email', {})
    if email_config.get('enabled', False):
        try:
            provider = EmailNotificationProvider(
                smtp_host=email_config['smtp_host'],
                smtp_port=email_config['smtp_port'],
                smtp_username=email_config['smtp_username'],
                smtp_password=email_config['smtp_password'],
                from_email=email_config['from_email'],
                to_emails=email_config['to_emails'],
                use_tls=email_config.get('use_tls', True)
            )
            service.add_provider(provider)
            logger.info("Email notifications enabled")
        except KeyError as e:
            logger.error(f"Email notification configuration missing required field: {e}")
        except Exception as e:
            logger.error(f"Failed to configure email notifications: {e}")
    
    # Webhook notifications
    webhook_config = config.get('webhook', {})
    if webhook_config.get('enabled', False):
        try:
            headers = webhook_config.get('headers', {})
            provider = WebhookNotificationProvider(
                webhook_url=webhook_config['url'],
                headers=headers
            )
            service.add_provider(provider)
            logger.info("Webhook notifications enabled")
        except KeyError as e:
            logger.error(f"Webhook notification configuration missing required field: {e}")
        except Exception as e:
            logger.error(f"Failed to configure webhook notifications: {e}")
    
    if not service.is_enabled():
        logger.info("No notification providers configured (notifications disabled)")
    
    return service

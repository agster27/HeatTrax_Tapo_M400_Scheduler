"""Notification service for health check events."""

import asyncio
import logging
import smtplib
import socket
import aiohttp
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Notification error exception."""
    pass


class NotificationValidationError(Exception):
    """Notification validation error exception."""
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
    
    @abstractmethod
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        Validate provider configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    async def test_connectivity(self, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        """
        Test connectivity to provider.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            Tuple of (is_connected, error_message)
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
    
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        Validate email configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.smtp_host:
            return False, "smtp_host is required"
        if not self.smtp_port:
            return False, "smtp_port is required"
        if not self.smtp_username:
            return False, "smtp_username is required"
        if not self.smtp_password:
            return False, "smtp_password is required"
        if not self.from_email:
            return False, "from_email is required"
        if not self.to_emails or len(self.to_emails) == 0:
            return False, "at least one recipient in to_emails is required"
        
        return True, None
    
    async def test_connectivity(self, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        """
        Test SMTP connectivity.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            Tuple of (is_connected, error_message)
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._test_smtp_connection, timeout)
            return True, None
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)}"
    
    def _test_smtp_connection(self, timeout: float):
        """
        Test SMTP connection (blocking operation).
        
        Args:
            timeout: Connection timeout in seconds
        """
        # Set socket timeout for all operations
        old_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(timeout)
            
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=timeout)
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.quit()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=timeout)
                server.login(self.smtp_username, self.smtp_password)
                server.quit()
        finally:
            socket.setdefaulttimeout(old_timeout)
    
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
            
            logger.info(f"Email notification sent successfully: {event_type}")
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to send email notification for {event_type}: "
                f"{type(e).__name__}: {e}"
            )
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
    
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        """
        Validate webhook configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.webhook_url:
            return False, "webhook url is required"
        
        # Validate URL format
        try:
            parsed = urlparse(self.webhook_url)
            if not parsed.scheme or not parsed.netloc:
                return False, f"invalid webhook URL format: {self.webhook_url}"
            if parsed.scheme not in ['http', 'https']:
                return False, f"webhook URL must use http or https, got: {parsed.scheme}"
        except Exception as e:
            return False, f"invalid webhook URL: {e}"
        
        return True, None
    
    async def test_connectivity(self, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        """
        Test webhook connectivity.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            Tuple of (is_connected, error_message)
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Try a HEAD or GET request to test connectivity
                async with session.head(
                    self.webhook_url,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    # Accept any response that indicates the server is reachable
                    # (even 404 or 405 means we can reach it)
                    if response.status < 500:
                        return True, None
                    else:
                        return False, f"HTTP {response.status}"
        except asyncio.TimeoutError:
            return False, "connection timeout"
        except aiohttp.ClientError as e:
            return False, f"{type(e).__name__}: {str(e)}"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)}"
    
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
                        logger.info(f"Webhook notification sent successfully: {event_type} (status: {response.status})")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(
                            f"Webhook notification failed for {event_type}: "
                            f"HTTP {response.status}, response: {response_text[:200]}"
                        )
                        return False
                        
        except asyncio.TimeoutError:
            logger.error(f"Webhook notification timeout for {event_type}")
            return False
        except Exception as e:
            logger.error(
                f"Failed to send webhook notification for {event_type}: "
                f"{type(e).__name__}: {e}"
            )
            return False


class NotificationService:
    """Service for sending notifications about health check events."""
    
    def __init__(self, routing: Optional[Dict[str, Dict[str, bool]]] = None):
        """
        Initialize notification service.
        
        Args:
            routing: Optional per-event routing configuration
        """
        self.providers: Dict[str, NotificationProvider] = {}
        self._enabled = False
        self.routing = routing or {}
        logger.info("Notification service initialized")
    
    def add_provider(self, name: str, provider: NotificationProvider):
        """
        Add a notification provider.
        
        Args:
            name: Provider name (e.g., 'email', 'webhook')
            provider: Notification provider to add
        """
        self.providers[name] = provider
        self._enabled = True
        logger.info(f"Added notification provider: {name} ({type(provider).__name__})")
    
    def is_enabled(self) -> bool:
        """
        Check if notifications are enabled.
        
        Returns:
            True if at least one provider is configured
        """
        return self._enabled and len(self.providers) > 0
    
    def get_providers_for_event(self, event_type: str) -> List[Tuple[str, NotificationProvider]]:
        """
        Get providers that should receive this event based on routing configuration.
        
        Args:
            event_type: Type of event
            
        Returns:
            List of (provider_name, provider) tuples
        """
        # If no routing config, send to all providers (default behavior)
        if not self.routing:
            return list(self.providers.items())
        
        # If event not in routing config, send to all providers
        if event_type not in self.routing:
            return list(self.providers.items())
        
        # Use routing configuration for this event
        event_routing = self.routing[event_type]
        result = []
        
        for name, provider in self.providers.items():
            # Default to True if provider not specified in routing
            if event_routing.get(name, True):
                result.append((name, provider))
        
        return result
    
    async def notify(self, event_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Send notification to configured providers based on routing.
        
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
        
        # Get providers for this event based on routing
        providers_for_event = self.get_providers_for_event(event_type)
        
        if not providers_for_event:
            logger.debug(f"No providers configured for event: {event_type}")
            return
        
        logger.info(f"Sending notification: {event_type} to {len(providers_for_event)} provider(s)")
        logger.debug(f"Message: {message}")
        logger.debug(f"Details: {details}")
        
        # Send to selected providers concurrently
        tasks = [
            provider.send(event_type, message, details)
            for name, provider in providers_for_event
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results with detailed error information
        success_count = 0
        for i, result in enumerate(results):
            provider_name = providers_for_event[i][0]
            if isinstance(result, Exception):
                logger.error(
                    f"Notification provider '{provider_name}' raised exception for {event_type}: "
                    f"{type(result).__name__}: {result}"
                )
            elif result is True:
                success_count += 1
            else:
                logger.error(
                    f"Notification provider '{provider_name}' failed for {event_type}"
                )
        
        logger.info(f"Notification sent to {success_count}/{len(providers_for_event)} provider(s)")
    
    async def send_test_notification(self) -> bool:
        """
        Send test notification to all providers.
        
        Returns:
            True if all providers succeeded, False otherwise
        """
        if not self.is_enabled():
            logger.info("No providers configured for test notification")
            return True
        
        logger.info(f"Sending test notification to {len(self.providers)} provider(s)...")
        
        message = "HeatTrax scheduler startup test notification"
        details = {
            "test": True,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to all providers concurrently
        tasks = [
            provider.send("startup_test", message, details)
            for provider in self.providers.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        all_success = True
        for i, (name, provider) in enumerate(self.providers.items()):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Test notification failed for {name}: {result}")
                all_success = False
            elif not result:
                logger.warning(f"Test notification failed for {name}")
                all_success = False
            else:
                logger.info(f"Test notification succeeded for {name}")
        
        return all_success


def create_notification_service_from_config(config: Dict[str, Any]) -> NotificationService:
    """
    Create notification service from configuration.
    
    Args:
        config: Configuration dictionary with notification settings
        
    Returns:
        Configured NotificationService instance
    """
    # Get routing configuration if present
    routing = config.get('routing', {})
    service = NotificationService(routing=routing)
    
    # Email notifications
    email_config = config.get('email', {})
    email_enabled = email_config.get('enabled', False)
    
    if email_enabled:
        # Provider is enabled, validate configuration
        try:
            # Check for required fields
            required_fields = ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'from_email', 'to_emails']
            missing_fields = [field for field in required_fields if not email_config.get(field)]
            
            if missing_fields:
                logger.error(
                    f"Email notifications enabled but missing required fields: {', '.join(missing_fields)}. "
                    f"Disable email notifications or fix the configuration. See HEALTH_CHECK.md for details."
                )
                raise NotificationValidationError(f"Email configuration missing: {', '.join(missing_fields)}")
            
            # Validate to_emails is not empty
            to_emails = email_config.get('to_emails', [])
            if not to_emails or len(to_emails) == 0:
                logger.error(
                    f"Email notifications enabled but to_emails is empty. "
                    f"Disable email notifications or add at least one recipient."
                )
                raise NotificationValidationError("Email configuration missing recipients in to_emails")
            
            provider = EmailNotificationProvider(
                smtp_host=email_config['smtp_host'],
                smtp_port=email_config['smtp_port'],
                smtp_username=email_config['smtp_username'],
                smtp_password=email_config['smtp_password'],
                from_email=email_config['from_email'],
                to_emails=email_config['to_emails'],
                use_tls=email_config.get('use_tls', True)
            )
            
            # Validate configuration
            is_valid, error_msg = provider.validate_config()
            if not is_valid:
                logger.error(f"Email notification configuration invalid: {error_msg}")
                raise NotificationValidationError(f"Email configuration invalid: {error_msg}")
            
            service.add_provider('email', provider)
            logger.info("Email notifications enabled")
            
        except NotificationValidationError:
            raise  # Re-raise validation errors
        except KeyError as e:
            logger.error(f"Email notification configuration missing required field: {e}")
            raise NotificationValidationError(f"Email configuration missing field: {e}")
        except Exception as e:
            logger.error(f"Failed to configure email notifications: {e}")
            raise NotificationValidationError(f"Failed to configure email: {e}")
    else:
        # Check if disabled via env var or config
        logger.info("Email notifications disabled (notifications.email.enabled=false)")
    
    # Webhook notifications
    webhook_config = config.get('webhook', {})
    webhook_enabled = webhook_config.get('enabled', False)
    
    if webhook_enabled:
        # Provider is enabled, validate configuration
        try:
            # Check for required fields
            if not webhook_config.get('url'):
                logger.error(
                    f"Webhook notifications enabled but url is missing. "
                    f"Disable webhook notifications or fix the configuration. See HEALTH_CHECK.md for details."
                )
                raise NotificationValidationError("Webhook configuration missing url")
            
            headers = webhook_config.get('headers', {})
            provider = WebhookNotificationProvider(
                webhook_url=webhook_config['url'],
                headers=headers
            )
            
            # Validate configuration
            is_valid, error_msg = provider.validate_config()
            if not is_valid:
                logger.error(f"Webhook notification configuration invalid: {error_msg}")
                raise NotificationValidationError(f"Webhook configuration invalid: {error_msg}")
            
            service.add_provider('webhook', provider)
            logger.info("Webhook notifications enabled")
            
        except NotificationValidationError:
            raise  # Re-raise validation errors
        except KeyError as e:
            logger.error(f"Webhook notification configuration missing required field: {e}")
            raise NotificationValidationError(f"Webhook configuration missing field: {e}")
        except Exception as e:
            logger.error(f"Failed to configure webhook notifications: {e}")
            raise NotificationValidationError(f"Failed to configure webhook: {e}")
    else:
        logger.info("Webhook notifications disabled (notifications.webhook.enabled=false)")
    
    if not service.is_enabled():
        logger.info("No notification providers configured (all notifications disabled)")
    
    return service


async def validate_and_test_notifications(
    config: Dict[str, Any],
    test_connectivity: bool = True,
    send_test: bool = False
) -> Tuple[bool, NotificationService]:
    """
    Validate notification configuration and optionally test connectivity and send test notifications.
    
    Args:
        config: Notification configuration dictionary
        test_connectivity: If True, test connectivity to each enabled provider
        send_test: If True, send test notification to each provider
        
    Returns:
        Tuple of (success, NotificationService)
    """
    try:
        # Create service from config (will validate configuration)
        service = create_notification_service_from_config(config)
        
        # Test connectivity if requested
        if test_connectivity and service.is_enabled():
            logger.info("Testing notification provider connectivity...")
            
            all_connected = True
            for name, provider in service.providers.items():
                logger.info(f"Testing connectivity for {name}...")
                is_connected, error_msg = await provider.test_connectivity(timeout=5.0)
                
                if is_connected:
                    logger.info(f"✓ {name} connectivity test passed")
                else:
                    logger.error(f"✗ {name} connectivity test failed: {error_msg}")
                    all_connected = False
            
            if not all_connected:
                raise NotificationValidationError("One or more notification providers failed connectivity test")
        
        # Send test notification if requested
        if send_test and service.is_enabled():
            logger.info("Sending test notifications...")
            test_success = await service.send_test_notification()
            
            if not test_success:
                raise NotificationValidationError("One or more test notifications failed")
        
        return True, service
        
    except NotificationValidationError as e:
        logger.error(f"Notification validation failed: {e}")
        return False, None
    except Exception as e:
        logger.error(f"Unexpected error during notification validation: {e}")
        return False, None

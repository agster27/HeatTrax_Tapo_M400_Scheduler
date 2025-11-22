"""Background notification validation and testing infrastructure.

This module provides a NotificationManager that monitors notification providers
(email and webhook) in a non-fatal background thread and exposes status for the Web UI.
"""

import logging
import threading
import time
import smtplib
import socket
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
import requests

logger = logging.getLogger(__name__)


class ProviderHealth(Enum):
    """Health status for notification providers."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class ProviderStatus:
    """Status information for a notification provider."""
    name: str
    enabled: bool
    health: ProviderHealth = ProviderHealth.UNKNOWN
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'health': self.health.value,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'last_success': self.last_success.isoformat() if self.last_success else None,
            'last_error': self.last_error,
            'consecutive_failures': self.consecutive_failures
        }


class NotificationManager:
    """
    Manages background validation and monitoring of notification providers.
    
    This manager runs in a background thread and periodically checks the health
    of configured notification providers (email and webhook). It provides status
    information for the Web UI and supports non-blocking test sends.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize notification manager.
        
        Args:
            config: Notifications configuration dictionary
        """
        self.config = config
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status_lock = threading.Lock()
        
        # Provider status tracking
        self._provider_status: Dict[str, ProviderStatus] = {}
        
        # Test queue for non-blocking test sends
        self._test_queue: List[Dict[str, str]] = []
        self._test_queue_lock = threading.Lock()
        
        # Parse configuration
        self.check_interval = config.get('check_interval_seconds', 60)
        
        # Initialize provider status
        self._init_provider_status()
        
        logger.info(f"NotificationManager initialized (check_interval={self.check_interval}s)")
    
    def _init_provider_status(self):
        """Initialize provider status from config."""
        email_config = self.config.get('email', {})
        webhook_config = self.config.get('webhook', {})
        
        with self._status_lock:
            self._provider_status['email'] = ProviderStatus(
                name='email',
                enabled=email_config.get('enabled', False)
            )
            self._provider_status['webhook'] = ProviderStatus(
                name='webhook',
                enabled=webhook_config.get('enabled', False)
            )
    
    def start(self):
        """Start the background validation thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("NotificationManager already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._background_loop,
            name="NotificationManager",
            daemon=True
        )
        self._thread.start()
        logger.info("NotificationManager background thread started")
    
    def stop(self, timeout: float = 5.0):
        """
        Stop the background validation thread.
        
        Args:
            timeout: Maximum time to wait for thread to stop
        """
        if not self._thread or not self._thread.is_alive():
            return
        
        logger.info("Stopping NotificationManager...")
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        
        if self._thread.is_alive():
            logger.warning("NotificationManager thread did not stop gracefully")
        else:
            logger.info("NotificationManager stopped")
    
    def _background_loop(self):
        """Background validation loop."""
        logger.info("NotificationManager background loop started")
        
        # Initial quick validation
        self._validate_all_providers()
        
        # Periodic checks
        while not self._stop_event.is_set():
            # Process test queue
            self._process_test_queue()
            
            # Wait for check interval or stop signal
            if self._stop_event.wait(timeout=self.check_interval):
                break
            
            # Periodic validation
            self._validate_all_providers()
        
        logger.info("NotificationManager background loop exiting")
    
    def _validate_all_providers(self):
        """Validate all enabled providers."""
        email_config = self.config.get('email', {})
        webhook_config = self.config.get('webhook', {})
        
        if email_config.get('enabled', False):
            self._validate_email_provider(email_config)
        
        if webhook_config.get('enabled', False):
            self._validate_webhook_provider(webhook_config)
    
    def _validate_email_provider(self, config: Dict[str, Any]):
        """
        Validate email provider.
        
        Args:
            config: Email provider configuration
        """
        with self._status_lock:
            status = self._provider_status['email']
            status.last_check = datetime.now()
        
        try:
            # Basic config validation
            required_fields = ['smtp_host', 'smtp_port', 'smtp_username', 
                             'smtp_password', 'from_email', 'to_emails']
            for field in required_fields:
                if not config.get(field):
                    raise ValueError(f"Missing required field: {field}")
            
            # Test SMTP connection
            smtp_host = config['smtp_host']
            smtp_port = config['smtp_port']
            smtp_username = config['smtp_username']
            smtp_password = config['smtp_password']
            use_tls = config.get('use_tls', True)
            
            # Set a timeout for the connection test
            old_timeout = socket.getdefaulttimeout()
            try:
                socket.setdefaulttimeout(5.0)
                
                if use_tls:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=5.0)
                    server.starttls()
                    server.login(smtp_username, smtp_password)
                    server.quit()
                else:
                    server = smtplib.SMTP(smtp_host, smtp_port, timeout=5.0)
                    server.login(smtp_username, smtp_password)
                    server.quit()
            finally:
                socket.setdefaulttimeout(old_timeout)
            
            # Success
            with self._status_lock:
                status.health = ProviderHealth.HEALTHY
                status.last_success = datetime.now()
                status.last_error = None
                status.consecutive_failures = 0
            
            logger.debug("Email provider validation successful")
            
        except Exception as e:
            with self._status_lock:
                status.health = ProviderHealth.DEGRADED
                status.last_error = f"{type(e).__name__}: {str(e)}"
                status.consecutive_failures += 1
            
            logger.warning(f"Email provider validation failed: {e}")
    
    def _validate_webhook_provider(self, config: Dict[str, Any]):
        """
        Validate webhook provider.
        
        Args:
            config: Webhook provider configuration
        """
        with self._status_lock:
            status = self._provider_status['webhook']
            status.last_check = datetime.now()
        
        try:
            # Basic config validation
            webhook_url = config.get('url')
            if not webhook_url:
                raise ValueError("Missing required field: url")
            
            # Test webhook connectivity with a HEAD request
            response = requests.head(webhook_url, timeout=5.0, allow_redirects=True)
            
            # Accept 2xx, 3xx, and 405 (Method Not Allowed - endpoint exists but doesn't support HEAD)
            if response.status_code < 400 or response.status_code == 405:
                # Success
                with self._status_lock:
                    status.health = ProviderHealth.HEALTHY
                    status.last_success = datetime.now()
                    status.last_error = None
                    status.consecutive_failures = 0
                
                logger.debug("Webhook provider validation successful")
            else:
                raise ValueError(f"Unexpected status code: {response.status_code}")
            
        except Exception as e:
            with self._status_lock:
                status.health = ProviderHealth.DEGRADED
                status.last_error = f"{type(e).__name__}: {str(e)}"
                status.consecutive_failures += 1
            
            logger.warning(f"Webhook provider validation failed: {e}")
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all providers.
        
        Returns:
            Dictionary mapping provider name to status dict
        """
        with self._status_lock:
            return {
                name: status.to_dict()
                for name, status in self._provider_status.items()
            }
    
    def send_test_notification(self, subject: str, body: str):
        """
        Queue a test notification (non-blocking).
        
        This method queues a test notification to be sent by the background
        thread. It returns immediately without blocking.
        
        Args:
            subject: Test notification subject
            body: Test notification body
        """
        with self._test_queue_lock:
            self._test_queue.append({
                'subject': subject,
                'body': body,
                'queued_at': datetime.now().isoformat()
            })
        
        logger.info(f"Test notification queued: {subject}")
    
    def _process_test_queue(self):
        """Process queued test notifications."""
        # Get all pending tests
        with self._test_queue_lock:
            if not self._test_queue:
                return
            
            tests = self._test_queue[:]
            self._test_queue.clear()
        
        # Process each test
        for test in tests:
            subject = test['subject']
            body = test['body']
            
            logger.info(f"Processing test notification: {subject}")
            
            # Send to email if enabled
            email_config = self.config.get('email', {})
            if email_config.get('enabled', False):
                self._send_test_email(email_config, subject, body)
            
            # Send to webhook if enabled
            webhook_config = self.config.get('webhook', {})
            if webhook_config.get('enabled', False):
                self._send_test_webhook(webhook_config, subject, body)
    
    def _send_test_email(self, config: Dict[str, Any], subject: str, body: str, 
                        max_retries: int = 3):
        """
        Send test email with retries and exponential backoff.
        
        Args:
            config: Email configuration
            subject: Email subject
            body: Email body
            max_retries: Maximum number of retry attempts
        """
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        attempt = 0
        while attempt < max_retries:
            try:
                # Create message
                msg = MIMEMultipart()
                msg['From'] = config['from_email']
                msg['To'] = ', '.join(config['to_emails'])
                msg['Subject'] = subject
                
                # Add timestamp to body
                full_body = f"{body}\n\nSent at: {datetime.now().isoformat()}"
                msg.attach(MIMEText(full_body, 'plain'))
                
                # Send
                smtp_host = config['smtp_host']
                smtp_port = config['smtp_port']
                smtp_username = config['smtp_username']
                smtp_password = config['smtp_password']
                use_tls = config.get('use_tls', True)
                
                if use_tls:
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
                        server.starttls()
                        server.login(smtp_username, smtp_password)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
                        server.login(smtp_username, smtp_password)
                        server.send_message(msg)
                
                logger.info(f"Test email sent successfully: {subject}")
                return
                
            except Exception as e:
                attempt += 1
                logger.warning(f"Test email send attempt {attempt}/{max_retries} failed: {e}")
                
                if attempt < max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    backoff = 2 ** (attempt - 1)
                    time.sleep(backoff)
        
        logger.error(f"Failed to send test email after {max_retries} attempts")
    
    def _send_test_webhook(self, config: Dict[str, Any], subject: str, body: str,
                          max_retries: int = 3):
        """
        Send test webhook with retries and exponential backoff.
        
        Args:
            config: Webhook configuration
            subject: Notification subject
            body: Notification body
            max_retries: Maximum number of retry attempts
        """
        attempt = 0
        while attempt < max_retries:
            try:
                webhook_url = config['url']
                
                # Prepare payload
                payload = {
                    'subject': subject,
                    'body': body,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'HeatTrax Scheduler Test'
                }
                
                # Send request
                response = requests.post(
                    webhook_url,
                    json=payload,
                    timeout=10.0,
                    headers={'Content-Type': 'application/json'}
                )
                
                # Check response
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"Test webhook sent successfully: {subject}")
                    return
                else:
                    raise ValueError(f"Unexpected status code: {response.status_code}")
                
            except Exception as e:
                attempt += 1
                logger.warning(f"Test webhook send attempt {attempt}/{max_retries} failed: {e}")
                
                if attempt < max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    backoff = 2 ** (attempt - 1)
                    time.sleep(backoff)
        
        logger.error(f"Failed to send test webhook after {max_retries} attempts")

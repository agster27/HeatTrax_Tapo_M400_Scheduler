"""Flask routes for notification management API.

This module provides minimal Flask route registrations to expose notification
status and testing endpoints. It's designed to be registered with the WebServer
Flask app in main.py.
"""

import logging
from flask import jsonify, request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.notifications import NotificationManager

logger = logging.getLogger(__name__)


def register_notification_routes(app, notification_manager):
    """
    Register notification routes with Flask app.
    
    This function registers two endpoints:
    - GET /api/notifications/status - Returns per-provider status JSON
    - POST /api/notifications/test - Queues a test send (non-blocking, returns 202)
    
    Args:
        app: Flask application instance
        notification_manager: NotificationManager instance
    """
    
    @app.route('/api/notifications/status', methods=['GET'])
    def api_notifications_status():
        """
        Get notification provider status.
        
        Returns per-provider health status including last check time,
        last success time, error messages, and consecutive failure counts.
        
        Returns:
            JSON: {
                "status": "ok",
                "providers": {
                    "email": {
                        "name": "email",
                        "enabled": true/false,
                        "health": "healthy"|"degraded"|"failed"|"unknown",
                        "last_check": "ISO timestamp",
                        "last_success": "ISO timestamp",
                        "last_error": "error message or null",
                        "consecutive_failures": number
                    },
                    "webhook": { ... }
                }
            }
        """
        try:
            provider_status = notification_manager.get_status()
            
            return jsonify({
                'status': 'ok',
                'providers': provider_status
            })
        except Exception as e:
            logger.error(f"Failed to get notification status: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'error': 'Failed to get notification status',
                'details': str(e)
            }), 500
    
    @app.route('/api/notifications/test', methods=['POST'])
    def api_notifications_test():
        """
        Queue a test notification (non-blocking).
        
        Accepts an optional JSON body with custom subject and body text.
        If not provided, uses default test message.
        
        The test notification is queued and processed asynchronously by the
        NotificationManager background thread. This endpoint returns immediately
        with 202 Accepted.
        
        Expects JSON (optional):
            {
                "subject": "Custom test subject",
                "body": "Custom test body"
            }
        
        Returns:
            JSON: {
                "status": "queued",
                "message": "Test notification queued for processing"
            }
        """
        try:
            # Get custom subject and body if provided
            data = request.get_json() if request.is_json else {}
            subject = data.get('subject', 'HeatTrax Test Notification')
            body = data.get('body', 'This is a test notification from HeatTrax Scheduler.')
            
            # Queue the test (non-blocking)
            notification_manager.send_test_notification(subject, body)
            
            return jsonify({
                'status': 'queued',
                'message': 'Test notification queued for processing'
            }), 202
            
        except Exception as e:
            logger.error(f"Failed to queue test notification: {e}", exc_info=True)
            return jsonify({
                'status': 'error',
                'error': 'Failed to queue test notification',
                'details': str(e)
            }), 500
    
    logger.info("Notification routes registered: GET /api/notifications/status, POST /api/notifications/test")

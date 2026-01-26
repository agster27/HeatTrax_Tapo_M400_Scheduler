"""Authentication middleware for web interface."""

import logging
from functools import wraps
from datetime import datetime, timedelta
from typing import Tuple, Optional
from flask import session, request, jsonify, redirect, url_for

logger = logging.getLogger(__name__)


def init_auth(app, pin: str):
    """
    Initialize authentication for Flask app.
    
    Args:
        app: Flask application instance
        pin: PIN for authentication (can be empty string if not configured)
    """
    # Set a secret key for session management
    if not app.secret_key:
        import secrets
        app.secret_key = secrets.token_hex(32)
        logger.info("Generated secret key for session management")
    
    # Store PIN in app config
    # Use HEATTRAX_PIN for consistency with check_pin
    app.config['HEATTRAX_PIN'] = pin
    # Keep AUTH_PIN for backward compatibility
    app.config['AUTH_PIN'] = pin
    
    # Session lifetime (24 hours)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    if pin:
        logger.info("Authentication initialized with PIN")
    else:
        logger.warning("Authentication initialized without PIN - PIN not configured")


def require_auth(f):
    """
    Decorator to require authentication for a route.
    
    Checks if user is authenticated via session.
    If not authenticated, returns 401 error for API routes
    or redirects to login for page routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if authenticated
        if not session.get('authenticated'):
            # Check if this is an API route
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': 'Authentication required',
                    'redirect': '/control/login'
                }), 401
            else:
                # Redirect to login page
                return redirect(url_for('control_login'))
        
        # Check session expiration
        auth_time = session.get('authenticated_at')
        if auth_time:
            try:
                auth_datetime = datetime.fromisoformat(auth_time)
                now = datetime.now()
                
                # Session expires after 24 hours
                if now - auth_datetime > timedelta(hours=24):
                    logger.info("Session expired")
                    session.clear()
                    
                    if request.path.startswith('/api/'):
                        return jsonify({
                            'success': False,
                            'error': 'Session expired',
                            'redirect': '/control/login'
                        }), 401
                    else:
                        return redirect(url_for('control_login'))
            except Exception as e:
                logger.error(f"Failed to check session expiration: {e}")
        
        return f(*args, **kwargs)
    
    return decorated_function


def check_pin(app, provided_pin: str) -> Tuple[bool, Optional[str]]:
    """
    Check if provided PIN is valid.
    
    Args:
        app: Flask application instance
        provided_pin: PIN provided by user
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None): PIN is correct
        - (False, "error message"): PIN is incorrect or not configured
    """
    configured_pin = app.config.get('HEATTRAX_PIN') or app.config.get('AUTH_PIN', '')
    
    # Check if PIN is configured at all
    if not configured_pin:
        logger.error("No PIN configured for mobile control. Set web.pin in config or HEATTRAX_WEB_PIN environment variable.")
        return False, "No PIN configured. Contact your administrator."
    
    # Check if provided PIN matches
    if provided_pin == configured_pin:
        return True, None
    else:
        return False, "Invalid PIN"


def create_session():
    """
    Create an authenticated session.
    
    Sets session variables for authenticated state.
    """
    session.permanent = True
    session['authenticated'] = True
    session['authenticated_at'] = datetime.now().isoformat()
    logger.info("Created authenticated session")


def clear_session():
    """Clear the current session."""
    session.clear()
    logger.info("Cleared session")

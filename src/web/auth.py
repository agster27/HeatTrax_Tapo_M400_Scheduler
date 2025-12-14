"""Authentication middleware for web interface."""

import logging
from functools import wraps
from datetime import datetime, timedelta
from flask import session, request, jsonify, redirect, url_for

logger = logging.getLogger(__name__)


def init_auth(app, pin: str):
    """
    Initialize authentication for Flask app.
    
    Args:
        app: Flask application instance
        pin: PIN for authentication
    """
    # Set a secret key for session management
    if not app.secret_key:
        import secrets
        app.secret_key = secrets.token_hex(32)
        logger.info("Generated secret key for session management")
    
    # Store PIN in app config
    app.config['AUTH_PIN'] = pin
    
    # Session lifetime (24 hours)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    logger.info("Authentication initialized")


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


def check_pin(app, provided_pin: str) -> bool:
    """
    Check if provided PIN matches configured PIN.
    
    Args:
        app: Flask application instance
        provided_pin: PIN provided by user
        
    Returns:
        True if PIN matches, False otherwise
    """
    configured_pin = app.config.get('AUTH_PIN', '')
    return provided_pin == configured_pin


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

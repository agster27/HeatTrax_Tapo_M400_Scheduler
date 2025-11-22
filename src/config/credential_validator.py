"""Credential validation for Tapo device control."""

import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


# Known placeholder values that should be treated as invalid credentials
PLACEHOLDER_USERNAMES = {
    'your_tapo_email@example.com',
    'your_tapo_username',
    'your_username',
    'your_email@example.com',
}

PLACEHOLDER_PASSWORDS = {
    'your_tapo_password',
    'password',
}


def is_valid_credential(username: Optional[str], password: Optional[str]) -> Tuple[bool, str]:
    """
    Validate Tapo credentials to determine if device control should be enabled.
    
    Credentials are considered invalid if:
    - Either username or password is None, empty, or whitespace-only
    - Username matches a known placeholder pattern
    - Password matches a known placeholder pattern
    
    Args:
        username: Tapo account username/email
        password: Tapo account password
        
    Returns:
        Tuple of (is_valid, reason):
            - is_valid: True if credentials are valid for device control
            - reason: Human-readable explanation of the credential state
    """
    # Check for None or empty values
    if not username or not username.strip():
        return False, "Username is missing or empty"
    
    if not password or not password.strip():
        return False, "Password is missing or empty"
    
    # Check for placeholder usernames (case-insensitive)
    username_lower = username.strip().lower()
    if username_lower in {p.lower() for p in PLACEHOLDER_USERNAMES}:
        return False, f"Username '{username}' is a placeholder value"
    
    # Check for placeholder passwords
    password_stripped = password.strip()
    if password_stripped in PLACEHOLDER_PASSWORDS:
        return False, f"Password is a placeholder value"
    
    # Credentials appear valid
    return True, "Credentials present and valid"


def check_credentials_for_setup_mode(username: Optional[str], password: Optional[str]) -> Tuple[bool, str]:
    """
    Check if credentials require setup mode (missing or placeholder).
    
    This is a convenience wrapper around is_valid_credential that returns
    the inverse - whether setup mode should be activated.
    
    Args:
        username: Tapo account username/email
        password: Tapo account password
        
    Returns:
        Tuple of (needs_setup, reason):
            - needs_setup: True if credentials are missing/invalid and setup mode required
            - reason: Human-readable explanation
    """
    is_valid, reason = is_valid_credential(username, password)
    
    if is_valid:
        return False, "Credentials are valid, setup mode not required"
    else:
        return True, f"Setup mode required: {reason}"


def log_credential_state(username: Optional[str], password: Optional[str], 
                         source: str = "config") -> None:
    """
    Log the current credential state with appropriate level and detail.
    
    Args:
        username: Tapo account username/email
        password: Tapo account password
        source: Source of credentials (e.g., "config", "environment")
    """
    is_valid, reason = is_valid_credential(username, password)
    
    if is_valid:
        logger.info(f"Tapo credentials ({source}): {reason}")
        logger.info(f"  Username: {username}")
        logger.info(f"  Password: {'*' * len(password) if password else '(empty)'}")
    else:
        logger.warning(f"Tapo credentials ({source}): {reason}")
        logger.warning(f"  Username: {username or '(empty)'}")
        logger.warning(f"  Password: {'(placeholder)' if password in PLACEHOLDER_PASSWORDS else ('*' * len(password) if password else '(empty)')}")

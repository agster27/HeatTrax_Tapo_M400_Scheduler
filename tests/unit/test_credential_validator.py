"""Unit tests for credential validation."""

import unittest
from src.config.credential_validator import (
    is_valid_credential,
    check_credentials_for_setup_mode,
    PLACEHOLDER_USERNAMES,
    PLACEHOLDER_PASSWORDS
)


class TestCredentialValidator(unittest.TestCase):
    """Test cases for credential validation logic."""
    
    def test_empty_username(self):
        """Test that empty username is invalid."""
        is_valid, reason = is_valid_credential('', 'password123')
        self.assertFalse(is_valid)
        self.assertIn('Username is missing or empty', reason)
    
    def test_empty_password(self):
        """Test that empty password is invalid."""
        is_valid, reason = is_valid_credential('user@example.com', '')
        self.assertFalse(is_valid)
        self.assertIn('Password is missing or empty', reason)
    
    def test_none_username(self):
        """Test that None username is invalid."""
        is_valid, reason = is_valid_credential(None, 'password123')
        self.assertFalse(is_valid)
        self.assertIn('Username is missing or empty', reason)
    
    def test_none_password(self):
        """Test that None password is invalid."""
        is_valid, reason = is_valid_credential('user@example.com', None)
        self.assertFalse(is_valid)
        self.assertIn('Password is missing or empty', reason)
    
    def test_whitespace_only_username(self):
        """Test that whitespace-only username is invalid."""
        is_valid, reason = is_valid_credential('   ', 'password123')
        self.assertFalse(is_valid)
        self.assertIn('Username is missing or empty', reason)
    
    def test_whitespace_only_password(self):
        """Test that whitespace-only password is invalid."""
        is_valid, reason = is_valid_credential('user@example.com', '   ')
        self.assertFalse(is_valid)
        self.assertIn('Password is missing or empty', reason)
    
    def test_placeholder_username_exact_match(self):
        """Test that exact placeholder usernames are detected."""
        for placeholder in PLACEHOLDER_USERNAMES:
            is_valid, reason = is_valid_credential(placeholder, 'ValidPassword123')
            self.assertFalse(is_valid, f"Placeholder '{placeholder}' should be invalid")
            self.assertIn('placeholder', reason.lower())
    
    def test_placeholder_username_case_insensitive(self):
        """Test that placeholder detection is case-insensitive."""
        is_valid, reason = is_valid_credential('YOUR_TAPO_USERNAME', 'ValidPassword123')
        self.assertFalse(is_valid)
        self.assertIn('placeholder', reason.lower())
    
    def test_placeholder_password(self):
        """Test that placeholder passwords are detected."""
        for placeholder in PLACEHOLDER_PASSWORDS:
            is_valid, reason = is_valid_credential('user@example.com', placeholder)
            self.assertFalse(is_valid, f"Placeholder password '{placeholder}' should be invalid")
            self.assertIn('placeholder', reason.lower())
    
    def test_valid_credentials(self):
        """Test that valid credentials pass validation."""
        is_valid, reason = is_valid_credential('user@example.com', 'SecurePassword123!')
        self.assertTrue(is_valid)
        self.assertIn('valid', reason.lower())
    
    def test_valid_credentials_with_special_chars(self):
        """Test valid credentials with special characters."""
        is_valid, reason = is_valid_credential('user+tag@example.com', 'P@ssw0rd!#$%')
        self.assertTrue(is_valid)
        self.assertIn('valid', reason.lower())
    
    def test_check_setup_mode_with_invalid_credentials(self):
        """Test that check_setup_mode returns True for invalid credentials."""
        needs_setup, reason = check_credentials_for_setup_mode('', '')
        self.assertTrue(needs_setup)
        self.assertIn('Setup mode required', reason)
    
    def test_check_setup_mode_with_valid_credentials(self):
        """Test that check_setup_mode returns False for valid credentials."""
        needs_setup, reason = check_credentials_for_setup_mode('user@example.com', 'ValidPass123')
        self.assertFalse(needs_setup)
        self.assertIn('not required', reason)
    
    def test_check_setup_mode_with_placeholder(self):
        """Test that check_setup_mode returns True for placeholder credentials."""
        needs_setup, reason = check_credentials_for_setup_mode('your_tapo_username', 'password')
        self.assertTrue(needs_setup)
        self.assertIn('Setup mode required', reason)


if __name__ == '__main__':
    unittest.main()

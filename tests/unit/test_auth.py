#!/usr/bin/env python3
"""Tests for authentication module."""

import unittest
from unittest.mock import Mock
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.web.auth import check_pin, init_auth, create_session, clear_session


class TestCheckPin(unittest.TestCase):
    """Test check_pin function."""
    
    def test_pin_configured_and_correct(self):
        """Test PIN check when PIN is configured and correct."""
        app = Mock()
        app.config = {'HEATTRAX_PIN': '1234'}
        
        is_valid, error_message = check_pin(app, '1234')
        
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)
    
    def test_pin_configured_but_incorrect(self):
        """Test PIN check when PIN is configured but incorrect."""
        app = Mock()
        app.config = {'HEATTRAX_PIN': '1234'}
        
        is_valid, error_message = check_pin(app, '9999')
        
        self.assertFalse(is_valid)
        self.assertEqual(error_message, 'Invalid PIN')
    
    def test_pin_not_configured(self):
        """Test PIN check when PIN is not configured."""
        app = Mock()
        app.config = {}
        
        is_valid, error_message = check_pin(app, '1234')
        
        self.assertFalse(is_valid)
        self.assertEqual(error_message, 'No PIN configured. Contact your administrator.')
    
    def test_pin_configured_as_empty_string(self):
        """Test PIN check when PIN is empty string."""
        app = Mock()
        app.config = {'HEATTRAX_PIN': ''}
        
        is_valid, error_message = check_pin(app, '1234')
        
        self.assertFalse(is_valid)
        self.assertEqual(error_message, 'No PIN configured. Contact your administrator.')
    
    def test_pin_fallback_to_auth_pin(self):
        """Test PIN check falls back to AUTH_PIN if HEATTRAX_PIN not set."""
        app = Mock()
        app.config = {'AUTH_PIN': '5678'}
        
        is_valid, error_message = check_pin(app, '5678')
        
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)


class TestInitAuth(unittest.TestCase):
    """Test init_auth function."""
    
    def test_init_with_pin(self):
        """Test authentication initialization with PIN."""
        app = Mock()
        app.config = {}
        app.secret_key = None
        
        init_auth(app, '1234')
        
        self.assertEqual(app.config['HEATTRAX_PIN'], '1234')
        self.assertEqual(app.config['AUTH_PIN'], '1234')
        self.assertIsNotNone(app.secret_key)
    
    def test_init_without_pin(self):
        """Test authentication initialization without PIN."""
        app = Mock()
        app.config = {}
        app.secret_key = None
        
        init_auth(app, '')
        
        self.assertEqual(app.config['HEATTRAX_PIN'], '')
        self.assertEqual(app.config['AUTH_PIN'], '')
        self.assertIsNotNone(app.secret_key)
    
    def test_init_preserves_existing_secret_key(self):
        """Test authentication initialization preserves existing secret key."""
        app = Mock()
        app.config = {}
        app.secret_key = 'existing-secret'
        
        init_auth(app, '1234')
        
        self.assertEqual(app.secret_key, 'existing-secret')


if __name__ == '__main__':
    unittest.main()

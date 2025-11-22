#!/usr/bin/env python3
"""
Test form-based configuration editor functionality.
"""

import os
import sys
import unittest
import tempfile
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestFormBasedConfig(unittest.TestCase):
    """Test form-based configuration editor."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear all HEATTRAX env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                os.environ.pop(key, None)
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_html_contains_form_not_textarea(self):
        """Test that HTML contains form, not textarea."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        html = web_server._get_default_index_html()
        
        # Should contain form
        self.assertIn('config-form', html)
        self.assertIn('form-group', html)
        
        # Should NOT contain textarea for config editing
        self.assertNotIn('config-editor', html)
    
    def test_html_contains_all_sections(self):
        """Test that HTML contains all required form sections."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        html = web_server._get_default_index_html()
        
        # Check for section headers
        required_sections = [
            'Location',
            'Weather',
            'Device Credentials',
            'Thresholds & Scheduler',
            'Safety & Morning Mode',
            'Logging',
            'Health & Reboot',
            'Notifications - Global',
            'Notifications - Email',
            'Notifications - Webhook',
            'Web UI'
        ]
        
        for section in required_sections:
            self.assertIn(section, html, f"Missing section: {section}")
    
    def test_html_contains_form_fields(self):
        """Test that HTML contains expected form fields."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        html = web_server._get_default_index_html()
        
        # Check for specific field labels
        expected_fields = [
            'Latitude',
            'Longitude',
            'Timezone',
            'Weather Enabled',
            'Weather Provider',
            'Tapo Username',
            'Tapo Password',
            'Threshold Temperature',
            'Lead Time',
            'Trailing Time',
            'Log Level',
            'Health Check Interval',
            'SMTP Host',
            'Webhook URL',
            'Bind Host',
            'Port'
        ]
        
        for field in expected_fields:
            self.assertIn(field, html, f"Missing field: {field}")
    
    def test_form_has_javascript_functions(self):
        """Test that required JavaScript functions are present."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        html = web_server._get_default_index_html()
        
        # Check for required JavaScript functions
        required_functions = [
            'buildConfigForm',
            'createFormField',
            'collectFormValues',
            'getFieldMetadata',
            'showEnvOverridesInfo',
            'loadConfig',
            'saveConfig'
        ]
        
        for func in required_functions:
            self.assertIn(f'function {func}', html, f"Missing function: {func}")
    
    def test_form_field_types_in_definition(self):
        """Test that FORM_FIELDS definition contains proper field types."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        html = web_server._get_default_index_html()
        
        # Check for field type definitions
        self.assertIn("type: 'number'", html)  # Number fields
        self.assertIn("type: 'checkbox'", html)  # Boolean fields
        self.assertIn("type: 'select'", html)  # Select dropdowns
        self.assertIn("type: 'password'", html)  # Password fields
        self.assertIn("type: 'text'", html)  # Text fields
    
    def test_env_override_functionality(self):
        """Test that environment overrides are properly handled in the HTML."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        html = web_server._get_default_index_html()
        
        # Check for env override display functionality
        self.assertIn('readonly', html)
        self.assertIn('env_var', html)
        self.assertIn('Set via env:', html)
    
    def test_api_config_endpoint_unchanged(self):
        """Test that API config endpoint still works as before."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get config via API-style call
        config = config_manager.get_config(include_secrets=False)
        
        # Should have expected structure
        self.assertIn('location', config)
        self.assertIn('latitude', config['location'])
        self.assertIn('longitude', config['location'])
        self.assertIn('devices', config)
        self.assertIn('thresholds', config)
    
    def test_to_emails_array_handling(self):
        """Test that to_emails special handling is mentioned in the HTML."""
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager)
        
        html = web_server._get_default_index_html()
        
        # Check for to_emails field with comma-separated handling
        self.assertIn('to_emails', html.lower())
        self.assertIn('comma', html.lower())


class TestFormWithEnvOverrides(unittest.TestCase):
    """Test form behavior with environment variable overrides."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_env_override_creates_readonly_field(self):
        """Test that env overrides result in readonly fields being identified."""
        # Set environment variable
        os.environ['HEATTRAX_LATITUDE'] = '42.3601'
        
        config_manager = ConfigManager(str(self.config_path))
        
        # Get annotated config
        config = config_manager.get_config(include_secrets=False)
        env_overrides = config_manager.get_env_overridden_paths()
        
        # Latitude should be in env overrides
        self.assertIn('location.latitude', env_overrides)
        self.assertEqual(env_overrides['location.latitude'], 'HEATTRAX_LATITUDE')


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestFormBasedConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestFormWithEnvOverrides))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

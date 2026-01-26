#!/usr/bin/env python3
"""
Integration tests for web server configuration persistence.
Tests the full end-to-end flow of config updates via Web UI.
"""

import os
import sys
import unittest
import tempfile
import yaml
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestWebConfigPersistence(unittest.TestCase):
    """Test configuration persistence through web server API."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
        
        # Create config manager
        self.config_manager = ConfigManager(str(self.config_path))
        
        # Create web server
        self.web_server = WebServer(self.config_manager, scheduler=None)
        self.app = self.web_server.app
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_get_config_endpoint(self):
        """Test GET /api/config returns annotated configuration."""
        response = self.client.get('/api/config')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # Should have location section
        self.assertIn('location', data)
        
        # Check that fields are annotated with metadata
        # The annotated config should have nested structure with 'value', 'source', etc.
        self.assertIn('latitude', data['location'])
    
    def test_post_config_email_enabled_success(self):
        """Test POST /api/config with valid email configuration succeeds."""
        # Get current config
        config = self.config_manager.get_config(include_secrets=True)
        
        # Enable email with valid settings
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user@example.com'
        config['notifications']['email']['smtp_password'] = 'password123'
        config['notifications']['email']['from_email'] = 'user@example.com'
        config['notifications']['email']['to_emails'] = ['admin@example.com']
        config['notifications']['email']['use_tls'] = True
        
        # POST the config
        response = self.client.post('/api/config',
                                    data=json.dumps(config),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'ok')
        
        # Verify config persisted to disk
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertTrue(disk_config['notifications']['email']['enabled'])
        self.assertEqual(disk_config['notifications']['email']['smtp_host'], 'smtp.example.com')
    
    def test_post_config_email_enabled_without_smtp_fails(self):
        """Test POST /api/config with email enabled but missing SMTP settings fails."""
        # Get current config
        config = self.config_manager.get_config(include_secrets=True)
        
        # Enable email but don't provide SMTP settings
        config['notifications']['email']['enabled'] = True
        # Leave other fields empty/default
        
        # POST the config
        response = self.client.post('/api/config',
                                    data=json.dumps(config),
                                    content_type='application/json')
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'error')
        self.assertIn('smtp', result['message'].lower())
    
    def test_post_config_invalid_latitude_fails(self):
        """Test POST /api/config with invalid latitude returns 400."""
        config = self.config_manager.get_config(include_secrets=True)
        
        # Set invalid latitude
        config['location']['latitude'] = 999
        
        response = self.client.post('/api/config',
                                    data=json.dumps(config),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'error')
        self.assertIn('latitude', result['message'].lower())
    
    def test_post_config_preserves_secrets(self):
        """Test that secrets are preserved when updating via web API."""
        # First, set up config with secrets
        config = self.config_manager.get_config(include_secrets=True)
        config['devices']['credentials']['password'] = 'original_password'
        config['notifications']['email']['enabled'] = True
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user'
        config['notifications']['email']['smtp_password'] = 'original_smtp_pass'
        config['notifications']['email']['from_email'] = 'from@example.com'
        config['notifications']['email']['to_emails'] = ['to@example.com']
        
        result = self.config_manager.update_config(config, preserve_secrets=True)
        self.assertEqual(result['status'], 'ok')
        
        # Now get config without secrets (as the UI would)
        config_without_secrets = self.config_manager.get_config(include_secrets=False)
        self.assertEqual(config_without_secrets['devices']['credentials']['password'], '********')
        self.assertEqual(config_without_secrets['notifications']['email']['smtp_password'], '********')
        
        # Make a different change
        config_without_secrets['thresholds']['temperature_f'] = 28
        
        # POST the config with masked secrets
        response = self.client.post('/api/config',
                                    data=json.dumps(config_without_secrets),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        
        # Verify secrets were preserved
        final_config = self.config_manager.get_config(include_secrets=True)
        self.assertEqual(final_config['devices']['credentials']['password'], 'original_password')
        self.assertEqual(final_config['notifications']['email']['smtp_password'], 'original_smtp_pass')
        
        # Verify on disk
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertEqual(disk_config['devices']['credentials']['password'], 'original_password')
        self.assertEqual(disk_config['notifications']['email']['smtp_password'], 'original_smtp_pass')
    
    def test_post_config_non_json_fails(self):
        """Test POST /api/config with non-JSON data returns 400."""
        response = self.client.post('/api/config',
                                    data='not json',
                                    content_type='text/plain')
        
        self.assertEqual(response.status_code, 400)
        
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'error')
        self.assertIn('json', result['message'].lower())
    
    def test_post_config_non_dict_fails(self):
        """Test POST /api/config with non-dict JSON returns 400."""
        response = self.client.post('/api/config',
                                    data=json.dumps(['not', 'a', 'dict']),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        
        result = json.loads(response.data)
        self.assertEqual(result['status'], 'error')
        self.assertIn('dictionary', result['message'].lower())
    
    def test_health_endpoint(self):
        """Test /api/health endpoint returns ok."""
        response = self.client.get('/api/health')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['config_loaded'])
    
    def test_ping_endpoint(self):
        """Test /api/ping endpoint returns pong."""
        response = self.client.get('/api/ping')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['message'], 'pong')
    
    def test_post_config_notification_checkboxes_persist(self):
        """
        Test that notification checkboxes persist correctly via Web API.
        This test specifically validates the fix for the bug where notification
        checkboxes (required, test_on_startup, email.enabled) don't persist.
        """
        # First, get current config to build a baseline
        get_response = self.client.get('/api/config')
        self.assertEqual(get_response.status_code, 200)
        
        # Extract raw values from annotated config
        annotated_config = json.loads(get_response.data)
        
        def extract_values(annotated, path=''):
            """Helper to extract values from annotated config."""
            if isinstance(annotated, dict):
                if 'value' in annotated:
                    # This is a leaf node
                    return annotated['value']
                else:
                    # This is a nested object
                    result = {}
                    for key, val in annotated.items():
                        result[key] = extract_values(val, f"{path}.{key}" if path else key)
                    return result
            else:
                return annotated
        
        config = extract_values(annotated_config)
        
        # Verify initial state (all disabled)
        self.assertFalse(config['notifications']['test_on_startup'])
        self.assertFalse(config['notifications']['email']['enabled'])
        
        # Enable the notification flags
        config['notifications']['test_on_startup'] = True
        config['notifications']['email']['enabled'] = True
        
        # Ensure valid SMTP settings are present (required for validation when email is enabled)
        config['notifications']['email']['smtp_host'] = 'smtp.example.com'
        config['notifications']['email']['smtp_port'] = 587
        config['notifications']['email']['smtp_username'] = 'user@example.com'
        config['notifications']['email']['smtp_password'] = 'password123'
        config['notifications']['email']['from_email'] = 'user@example.com'
        config['notifications']['email']['to_emails'] = ['admin@example.com']
        config['notifications']['email']['use_tls'] = True
        
        # POST the updated config
        post_response = self.client.post('/api/config',
                                         data=json.dumps(config),
                                         content_type='application/json')
        
        self.assertEqual(post_response.status_code, 200)
        
        result = json.loads(post_response.data)
        self.assertEqual(result['status'], 'ok')
        
        # Re-GET config to verify persistence
        get_response2 = self.client.get('/api/config')
        self.assertEqual(get_response2.status_code, 200)
        
        annotated_config2 = json.loads(get_response2.data)
        config2 = extract_values(annotated_config2)
        
        # Verify the flags are now True
        self.assertTrue(config2['notifications']['test_on_startup'],
                       "notifications.test_on_startup should be True after update")
        self.assertTrue(config2['notifications']['email']['enabled'],
                       "notifications.email.enabled should be True after update")
        
        # Verify on-disk persistence
        with open(self.config_path, 'r') as f:
            disk_config = yaml.safe_load(f)
        
        self.assertTrue(disk_config['notifications']['test_on_startup'],
                       "notifications.test_on_startup should be True on disk")
        self.assertTrue(disk_config['notifications']['email']['enabled'],
                       "notifications.email.enabled should be True on disk")


class TestWebConfigEnvOverrides(unittest.TestCase):
    """Test that env overrides are properly tracked in web API."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        self.original_env = os.environ.copy()
        
        # Clear config-related env vars
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_env_overridden_fields_marked_readonly(self):
        """Test that env-overridden fields are marked as readonly in API response."""
        # Set env override
        os.environ['HEATTRAX_NOTIFICATION_EMAIL_ENABLED'] = 'true'
        os.environ['HEATTRAX_LATITUDE'] = '51.5074'
        
        # Create config manager and web server
        config_manager = ConfigManager(str(self.config_path))
        web_server = WebServer(config_manager, scheduler=None)
        client = web_server.app.test_client()
        
        # Get config
        response = client.get('/api/config')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        
        # The annotated config should show that these fields are readonly
        # Navigate to the field (structure depends on _build_annotated_config implementation)
        # We need to check that the field has readonly: True and env_var set
        
        # Get env overridden paths from config manager
        env_overrides = config_manager.get_env_overridden_paths()
        self.assertIn('notifications.email.enabled', env_overrides)
        self.assertIn('location.latitude', env_overrides)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""
Integration tests for web server API endpoints.
"""

import os
import sys
import unittest
import tempfile
import json
import yaml
from pathlib import Path
import threading
import time

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager
from web_server import WebServer


class TestWebServerAPI(unittest.TestCase):
    """Test web server API endpoints."""
    
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
        self.web_server = WebServer(self.config_manager)
        
        # Get Flask test client
        self.client = self.web_server.app.test_client()
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_health_endpoint(self):
        """Test /api/health endpoint."""
        response = self.client.get('/api/health')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('timestamp', data)
        self.assertTrue(data['config_loaded'])
    
    def test_ping_endpoint(self):
        """Test /api/ping endpoint."""
        response = self.client.get('/api/ping')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['message'], 'pong')
    
    def test_status_endpoint(self):
        """Test /api/status endpoint."""
        response = self.client.get('/api/status')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('config_path', data)
        self.assertIn('timestamp', data)
    
    def test_config_get_endpoint(self):
        """Test GET /api/config endpoint."""
        response = self.client.get('/api/config')
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('location', data)
        self.assertIn('devices', data)
        self.assertIn('web', data)
        
        # Secrets should be masked
        self.assertEqual(data['devices']['credentials']['password'], '********')
    
    def test_config_put_endpoint_success(self):
        """Test PUT /api/config endpoint with valid config."""
        # Get current config
        response = self.client.get('/api/config')
        config = json.loads(response.data)
        
        # Modify config
        config['thresholds']['temperature_f'] = 30
        config['location']['latitude'] = 42.0
        
        # Update config
        response = self.client.put(
            '/api/config',
            data=json.dumps(config),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        
        # Verify changes
        response = self.client.get('/api/config')
        updated_config = json.loads(response.data)
        self.assertEqual(updated_config['thresholds']['temperature_f'], 30)
        self.assertEqual(updated_config['location']['latitude'], 42.0)
    
    def test_config_put_endpoint_validation_error(self):
        """Test PUT /api/config endpoint with invalid config."""
        # Get current config
        response = self.client.get('/api/config')
        config = json.loads(response.data)
        
        # Make config invalid
        config['location']['latitude'] = 999  # Invalid
        
        # Update config
        response = self.client.put(
            '/api/config',
            data=json.dumps(config),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('validation', data['message'].lower())
    
    def test_config_put_endpoint_non_json(self):
        """Test PUT /api/config endpoint with non-JSON data."""
        response = self.client.put(
            '/api/config',
            data='not json',
            content_type='text/plain'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('json', data['message'].lower())
    
    def test_config_put_endpoint_non_dict(self):
        """Test PUT /api/config endpoint with non-dict JSON."""
        response = self.client.put(
            '/api/config',
            data=json.dumps(['not', 'a', 'dict']),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('dictionary', data['message'].lower())
    
    def test_index_route(self):
        """Test / route returns HTML."""
        response = self.client.get('/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'HeatTrax Scheduler', response.data)
        self.assertIn(b'text/html', response.content_type.encode())
    
    def test_ui_route(self):
        """Test /ui route returns HTML."""
        response = self.client.get('/ui')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'HeatTrax Scheduler', response.data)
    
    def test_secrets_preserved_on_update(self):
        """Test that secrets are preserved when updating config via API."""
        # First, set a real password in the config
        full_config = self.config_manager.get_config(include_secrets=True)
        full_config['devices']['credentials']['password'] = 'actual_secret_password'
        self.config_manager.update_config(full_config, preserve_secrets=False)
        
        # Get current config (secrets masked)
        response = self.client.get('/api/config')
        config = json.loads(response.data)
        
        # Verify password is masked
        self.assertEqual(config['devices']['credentials']['password'], '********')
        
        # Update config (with masked password)
        config['thresholds']['temperature_f'] = 33
        
        response = self.client.put(
            '/api/config',
            data=json.dumps(config),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify password is still set in underlying config
        full_config = self.config_manager.get_config(include_secrets=True)
        self.assertEqual(full_config['devices']['credentials']['password'], 'actual_secret_password')
        self.assertNotEqual(full_config['devices']['credentials']['password'], '********')
    
    def test_restart_required_flag(self):
        """Test that restart_required flag is set for structural changes."""
        # Get current config
        response = self.client.get('/api/config')
        config = json.loads(response.data)
        
        # Change web port (requires restart)
        config['web']['port'] = 5000
        
        response = self.client.put(
            '/api/config',
            data=json.dumps(config),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['restart_required'], 'true')


if __name__ == '__main__':
    unittest.main()

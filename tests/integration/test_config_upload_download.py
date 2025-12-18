#!/usr/bin/env python3
"""
Integration tests for config upload and download endpoints.
"""

import copy
import json
import os
import sys
import tempfile
import time
import unittest
import unittest.mock as mock
import yaml
from io import BytesIO
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config_manager import ConfigManager
from src.web.web_server import WebServer


class TestConfigUploadDownload(unittest.TestCase):
    """Test config upload and download endpoints."""
    
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
        
        # Create a valid test config
        self.valid_config = {
            'location': {
                'latitude': 40.7128,
                'longitude': -74.0060,
                'timezone': 'America/New_York'
            },
            'devices': {
                'credentials': {
                    'username': 'test@example.com',
                    'password': 'testpass123'
                },
                'groups': {
                    'test_group': {
                        'enabled': True,
                        'automation': {
                            'weather_control': True,
                            'precipitation_control': True,
                            'morning_mode': True,
                            'schedule_control': False
                        },
                        'items': [
                            {
                                'name': 'Test Device',
                                'ip_address': '192.168.1.100',
                                'outlets': [0, 1]
                            }
                        ]
                    }
                }
            },
            'thresholds': {
                'temperature_f': 34,
                'lead_time_minutes': 60,
                'trailing_time_minutes': 60
            },
            'safety': {
                'max_runtime_hours': 6,
                'cooldown_minutes': 30
            },
            'scheduler': {
                'check_interval_minutes': 10,
                'forecast_hours': 12
            },
            'web': {
                'enabled': True,
                'port': 4328
            }
        }
        
        # Write initial config
        with open(self.config_path, 'w') as f:
            yaml.safe_dump(self.valid_config, f)
        
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
    
    def test_download_config(self):
        """Test downloading config.yaml file."""
        response = self.client.get('/api/config/download')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/x-yaml')
        
        # Verify content-disposition header
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        self.assertIn('config.yaml', response.headers.get('Content-Disposition', ''))
        
        # Parse downloaded content
        downloaded_config = yaml.safe_load(response.data)
        
        # Verify key sections exist
        self.assertIn('location', downloaded_config)
        self.assertIn('devices', downloaded_config)
        self.assertEqual(downloaded_config['location']['latitude'], 40.7128)
    
    def test_upload_valid_config(self):
        """Test uploading a valid config file."""
        # Create a valid config file
        import copy
        new_config = copy.deepcopy(self.valid_config)
        new_config['location']['latitude'] = 41.0
        new_config['location']['longitude'] = -75.0
        
        config_bytes = yaml.safe_dump(new_config).encode('utf-8')
        
        response = self.client.post(
            '/api/config/upload',
            data={'config_file': (BytesIO(config_bytes), 'config.yaml')},
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'ok')
        self.assertIn('message', data)
        self.assertTrue(data.get('backup_created', False))
        
        # Verify backup was created
        backup_files = list(Path(self.test_dir).glob('config.yaml.backup.*'))
        self.assertTrue(len(backup_files) > 0)
        
        # Verify new config was written
        with open(self.config_path, 'r') as f:
            saved_config = yaml.safe_load(f)
        
        self.assertEqual(saved_config['location']['latitude'], 41.0)
        self.assertEqual(saved_config['location']['longitude'], -75.0)
    
    def test_upload_invalid_yaml(self):
        """Test uploading an invalid YAML file."""
        invalid_yaml = b"this is not: valid: yaml: [[[unclosed"
        
        response = self.client.post(
            '/api/config/upload',
            data={'config_file': (BytesIO(invalid_yaml), 'config.yaml')},
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('YAML', data['message'])
    
    def test_upload_missing_required_fields(self):
        """Test uploading config with missing required fields."""
        # Missing location section
        invalid_config = {
            'devices': {
                'credentials': {
                    'username': 'test',
                    'password': 'test'
                },
                'groups': {}
            }
        }
        
        config_bytes = yaml.safe_dump(invalid_config).encode('utf-8')
        
        response = self.client.post(
            '/api/config/upload',
            data={'config_file': (BytesIO(config_bytes), 'config.yaml')},
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('validation_errors', data)
        self.assertTrue(any('location' in err.lower() for err in data['validation_errors']))
    
    def test_upload_invalid_latitude(self):
        """Test uploading config with invalid latitude."""
        import copy
        invalid_config = copy.deepcopy(self.valid_config)
        invalid_config['location']['latitude'] = 95  # Out of range
        
        config_bytes = yaml.safe_dump(invalid_config).encode('utf-8')
        
        response = self.client.post(
            '/api/config/upload',
            data={'config_file': (BytesIO(config_bytes), 'config.yaml')},
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('validation_errors', data)
        self.assertTrue(any('latitude' in err.lower() and '90' in err for err in data['validation_errors']))
    
    def test_upload_invalid_ip_address(self):
        """Test uploading config with invalid IP address."""
        import copy
        invalid_config = copy.deepcopy(self.valid_config)
        invalid_config['devices']['groups']['test_group']['items'][0]['ip_address'] = '999.999.999.999'
        
        config_bytes = yaml.safe_dump(invalid_config).encode('utf-8')
        
        response = self.client.post(
            '/api/config/upload',
            data={'config_file': (BytesIO(config_bytes), 'config.yaml')},
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('validation_errors', data)
        self.assertTrue(any('ip address' in err.lower() for err in data['validation_errors']))
    
    def test_upload_wrong_file_extension(self):
        """Test uploading file with wrong extension."""
        response = self.client.post(
            '/api/config/upload',
            data={'config_file': (BytesIO(b'content'), 'config.txt')},
            content_type='multipart/form-data'
        )
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        # Check for file type or extension message
        msg = (data.get('message') or data.get('error', '')).lower()
        self.assertTrue('extension' in msg or 'file type' in msg)
    
    def test_upload_no_file(self):
        """Test upload endpoint with no file."""
        response = self.client.post('/api/config/upload')
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
    
    def test_download_nonexistent_config(self):
        """Test downloading when config file doesn't exist."""
        # Remove config file
        os.remove(self.config_path)
        
        response = self.client.get('/api/config/download')
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_upload_triggers_automatic_restart(self):
        """Test that successful config upload triggers automatic restart."""
        # Create a valid config file
        new_config = copy.deepcopy(self.valid_config)
        new_config['location']['latitude'] = 41.0
        new_config['location']['longitude'] = -75.0
        
        config_bytes = yaml.safe_dump(new_config).encode('utf-8')
        
        # Mock os._exit to prevent actual process termination
        with mock.patch('os._exit') as mock_exit:
            response = self.client.post(
                '/api/config/upload',
                data={'config_file': (BytesIO(config_bytes), 'config.yaml')},
                content_type='multipart/form-data'
            )
            
            self.assertEqual(response.status_code, 200)
            
            data = json.loads(response.data)
            self.assertEqual(data['status'], 'ok')
            self.assertTrue(data.get('restart_required', False))
            
            # Give the delayed thread time to execute
            time.sleep(1)
            
            # Verify os._exit was called (automatic restart)
            mock_exit.assert_called_once_with(0)


if __name__ == '__main__':
    unittest.main()

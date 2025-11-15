#!/usr/bin/env python3
"""Tests for startup_checks module."""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from startup_checks import (
    check_python_version,
    check_package_versions,
    check_working_directory,
    check_directory_access,
    check_config_file,
    dump_environment_variables,
    check_device_connectivity,
    run_startup_checks
)


class TestStartupChecks(unittest.TestCase):
    """Test startup check functions."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
    
    def tearDown(self):
        """Clean up test environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        os.chdir(self.original_cwd)
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_check_python_version(self):
        """Test Python version check."""
        # Capture output
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_python_version()
            output = mock_stdout.getvalue()
        
        self.assertTrue(result)
        self.assertIn('Python version:', output)
        self.assertIn(f"{sys.version_info.major}.{sys.version_info.minor}", output)
    
    def test_check_package_versions_missing_file(self):
        """Test package version check with missing requirements file."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_package_versions('/nonexistent/requirements.txt')
            output = mock_stdout.getvalue()
        
        self.assertFalse(result)
        self.assertIn('not found', output.lower())
    
    def test_check_package_versions_success(self):
        """Test package version check with valid requirements file."""
        # Create a temporary requirements file
        req_file = Path(self.test_dir) / 'requirements.txt'
        with open(req_file, 'w') as f:
            f.write('PyYAML>=6.0.1\n')
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_package_versions(str(req_file))
            output = mock_stdout.getvalue()
        
        self.assertTrue(result)
        self.assertIn('PyYAML', output)
    
    def test_check_working_directory(self):
        """Test working directory check."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_working_directory()
            output = mock_stdout.getvalue()
        
        self.assertTrue(result)
        self.assertIn('Current working directory:', output)
    
    def test_check_directory_access_nonexistent(self):
        """Test directory access check with non-existent directory."""
        test_dir = os.path.join(self.test_dir, 'logs')
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_directory_access([test_dir])
            output = mock_stdout.getvalue()
        
        self.assertTrue(result)  # Should succeed after creating
        self.assertIn('Successfully created', output)
        self.assertTrue(os.path.exists(test_dir))
    
    def test_check_directory_access_existing(self):
        """Test directory access check with existing directory."""
        test_dir = os.path.join(self.test_dir, 'existing')
        os.makedirs(test_dir)
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_directory_access([test_dir])
            output = mock_stdout.getvalue()
        
        self.assertTrue(result)
        self.assertIn('readable', output)
        self.assertIn('writable', output)
    
    def test_check_config_file_missing(self):
        """Test config file check when file is missing."""
        nonexistent_config = os.path.join(self.test_dir, 'config.yaml')
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result, config = check_config_file(nonexistent_config)
            output = mock_stdout.getvalue()
        
        self.assertTrue(result)  # Should be True (acceptable if using env vars)
        self.assertIsNone(config)
        self.assertIn('not found', output.lower())
    
    def test_check_config_file_valid(self):
        """Test config file check with valid YAML."""
        config_file = os.path.join(self.test_dir, 'config.yaml')
        with open(config_file, 'w') as f:
            f.write('location:\n  latitude: 40.7128\n  longitude: -74.0060\n')
            f.write('device:\n  ip_address: "192.168.1.100"\n')
            f.write('thresholds:\n  temperature_f: 34\n')
            f.write('safety:\n  max_runtime_hours: 6\n')
            f.write('scheduler:\n  check_interval_minutes: 10\n')
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result, config = check_config_file(config_file)
            output = mock_stdout.getvalue()
        
        self.assertTrue(result)
        self.assertIsNotNone(config)
        self.assertIn('location', config)
        self.assertIn('parsed successfully', output.lower())
    
    def test_check_config_file_invalid_yaml(self):
        """Test config file check with invalid YAML."""
        config_file = os.path.join(self.test_dir, 'config.yaml')
        with open(config_file, 'w') as f:
            f.write('invalid: yaml: content: [\n')
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result, config = check_config_file(config_file)
            output = mock_stdout.getvalue()
        
        self.assertFalse(result)
        self.assertIsNone(config)
        self.assertIn('failed', output.lower())
    
    def test_dump_environment_variables_no_heattrax_vars(self):
        """Test environment variable dump with no HEATTRAX_ variables."""
        os.environ.clear()
        os.environ['PATH'] = '/usr/bin'
        os.environ['HOME'] = '/home/test'
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            dump_environment_variables()
            output = mock_stdout.getvalue()
        
        self.assertIn('Environment variables:', output)
        self.assertIn('No HEATTRAX_', output)
        self.assertIn('PATH', output)
        self.assertIn('HOME', output)
    
    def test_dump_environment_variables_with_heattrax_vars(self):
        """Test environment variable dump with HEATTRAX_ variables."""
        os.environ['HEATTRAX_LATITUDE'] = '40.7128'
        os.environ['HEATTRAX_TAPO_PASSWORD'] = 'secret123'
        os.environ['HEATTRAX_LOG_LEVEL'] = 'INFO'
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            dump_environment_variables()
            output = mock_stdout.getvalue()
        
        self.assertIn('HEATTRAX_LATITUDE=40.7128', output)
        self.assertIn('HEATTRAX_TAPO_PASSWORD=***REDACTED***', output)
        self.assertIn('HEATTRAX_LOG_LEVEL=INFO', output)
        self.assertNotIn('secret123', output)  # Sensitive value should be redacted
    
    def test_dump_environment_variables_custom_sensitive_patterns(self):
        """Test environment variable dump with custom sensitive patterns."""
        os.environ['HEATTRAX_API_KEY'] = 'myapikey123'
        os.environ['HEATTRAX_USERNAME'] = 'testuser'
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            dump_environment_variables(sensitive_patterns=['key'])
            output = mock_stdout.getvalue()
        
        self.assertIn('HEATTRAX_API_KEY=***REDACTED***', output)
        self.assertIn('HEATTRAX_USERNAME=testuser', output)  # Not redacted
        self.assertNotIn('myapikey123', output)
    
    def test_check_device_connectivity_invalid_ip(self):
        """Test device connectivity check with invalid IP."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_device_connectivity('invalid.ip.address', timeout=1.0)
            output = mock_stdout.getvalue()
        
        self.assertFalse(result)
        self.assertIn('failed', output.lower())
    
    def test_check_device_connectivity_unreachable(self):
        """Test device connectivity check with unreachable IP."""
        # Use a non-routable IP address
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = check_device_connectivity('192.0.2.1', port=9999, timeout=1.0)
            output = mock_stdout.getvalue()
        
        self.assertFalse(result)
        self.assertIn('192.0.2.1', output)
    
    def test_run_startup_checks_integration(self):
        """Test run_startup_checks integration."""
        # Set up a test environment
        os.chdir(self.test_dir)
        
        # Create requirements.txt
        req_file = Path(self.test_dir) / 'requirements.txt'
        with open(req_file, 'w') as f:
            f.write('PyYAML>=6.0.1\n')
        
        # Create config.yaml
        config_file = Path(self.test_dir) / 'config.yaml'
        with open(config_file, 'w') as f:
            f.write('location:\n  latitude: 40.7128\n  longitude: -74.0060\n')
            f.write('device:\n  ip_address: "192.168.1.100"\n')
            f.write('thresholds:\n  temperature_f: 34\n')
            f.write('safety:\n  max_runtime_hours: 6\n')
            f.write('scheduler:\n  check_interval_minutes: 10\n')
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = run_startup_checks(config_path='config.yaml')
            output = mock_stdout.getvalue()
        
        # Should succeed
        self.assertTrue(result)
        
        # Check that all sections are present
        self.assertIn('STARTUP SANITY CHECKS', output)
        self.assertIn('Python version:', output)
        self.assertIn('Installed package versions:', output)
        self.assertIn('Current working directory:', output)
        self.assertIn('Directory access checks:', output)
        self.assertIn('Configuration file check:', output)
        self.assertIn('Environment variables:', output)
        self.assertIn('Outbound IP address check:', output)


if __name__ == '__main__':
    unittest.main()

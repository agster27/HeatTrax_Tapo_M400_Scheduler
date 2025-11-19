#!/usr/bin/env python3
"""
Test web UI configuration including environment variable overrides.
"""

import os
import sys
import unittest
import tempfile
import yaml
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import Config, ConfigError
from config_manager import ConfigManager


class TestWebUIConfig(unittest.TestCase):
    """Test web UI configuration."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear web-related env vars
        for key in ['HEATTRAX_WEB_HOST', 'HEATTRAX_WEB_PORT', 'HEATTRAX_WEB_ENABLED']:
            os.environ.pop(key, None)
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_default_web_config_values(self):
        """Test default web UI configuration values."""
        config = Config('config.example.yaml')
        web_config = config.web
        
        # Check defaults are present
        self.assertIn('enabled', web_config)
        self.assertIn('bind_host', web_config)
        self.assertIn('port', web_config)
        
        # Default should be localhost for safety
        self.assertEqual(web_config.get('bind_host', '127.0.0.1'), '127.0.0.1')
        self.assertEqual(web_config.get('port', 4328), 4328)
    
    def test_web_host_env_override(self):
        """Test HEATTRAX_WEB_HOST environment variable override."""
        os.environ['HEATTRAX_WEB_HOST'] = '0.0.0.0'
        
        config = Config('config.example.yaml')
        web_config = config.web
        
        self.assertEqual(web_config['bind_host'], '0.0.0.0')
    
    def test_web_port_env_override(self):
        """Test HEATTRAX_WEB_PORT environment variable override."""
        os.environ['HEATTRAX_WEB_PORT'] = '8080'
        
        config = Config('config.example.yaml')
        web_config = config.web
        
        self.assertEqual(web_config['port'], 8080)
    
    def test_web_host_and_port_env_override(self):
        """Test both web host and port can be overridden."""
        os.environ['HEATTRAX_WEB_HOST'] = '0.0.0.0'
        os.environ['HEATTRAX_WEB_PORT'] = '5000'
        
        config = Config('config.example.yaml')
        web_config = config.web
        
        self.assertEqual(web_config['bind_host'], '0.0.0.0')
        self.assertEqual(web_config['port'], 5000)
    
    def test_web_port_type_conversion(self):
        """Test that web port is converted to integer."""
        os.environ['HEATTRAX_WEB_PORT'] = '9999'
        
        config = Config('config.example.yaml')
        web_config = config.web
        
        self.assertIsInstance(web_config['port'], int)
        self.assertEqual(web_config['port'], 9999)
    
    def test_web_config_in_config_manager(self):
        """Test web configuration in ConfigManager."""
        # Create a config manager
        config_manager = ConfigManager(str(self.config_path))
        
        # Get config (without secrets)
        config = config_manager.get_config(include_secrets=False)
        
        # Check web section exists
        self.assertIn('web', config)
        self.assertIn('bind_host', config['web'])
        self.assertIn('port', config['web'])
        
        # Check defaults (updated to 0.0.0.0 for network accessibility)
        self.assertEqual(config['web']['bind_host'], '0.0.0.0')
        self.assertEqual(config['web']['port'], 4328)
    
    def test_web_config_manager_env_override(self):
        """Test ConfigManager respects environment variables for web config."""
        os.environ['HEATTRAX_WEB_HOST'] = '0.0.0.0'
        os.environ['HEATTRAX_WEB_PORT'] = '3000'
        
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=False)
        
        self.assertEqual(config['web']['bind_host'], '0.0.0.0')
        self.assertEqual(config['web']['port'], 3000)
    
    def test_web_config_update_via_config_manager(self):
        """Test updating web configuration through ConfigManager."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=False)
        
        # Update web config
        config['web']['bind_host'] = '0.0.0.0'
        config['web']['port'] = 8888
        
        # Save
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'ok')
        
        # Verify changes
        updated_config = config_manager.get_config(include_secrets=False)
        self.assertEqual(updated_config['web']['bind_host'], '0.0.0.0')
        self.assertEqual(updated_config['web']['port'], 8888)
    
    def test_web_port_change_requires_restart(self):
        """Test that changing web port sets restart_required flag."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Get current config
        config = config_manager.get_config(include_secrets=False)
        
        # Change web port
        config['web']['port'] = 5555
        
        # Update
        result = config_manager.update_config(config, preserve_secrets=True)
        
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['restart_required'], 'true')
    
    def test_docker_defaults_with_env_vars(self):
        """Test typical Docker deployment with 0.0.0.0 binding."""
        # This simulates a Docker deployment where user sets host to 0.0.0.0
        os.environ['HEATTRAX_WEB_HOST'] = '0.0.0.0'
        os.environ['HEATTRAX_WEB_PORT'] = '4328'
        
        config = Config('config.example.yaml')
        web_config = config.web
        
        # Should be accessible from network
        self.assertEqual(web_config['bind_host'], '0.0.0.0')
        self.assertEqual(web_config['port'], 4328)
    
    def test_local_dev_defaults_without_env_vars(self):
        """Test local development defaults without env vars."""
        # No env vars set - should default to localhost
        config = Config('config.example.yaml')
        web_config = config.web
        
        # Should be localhost only for security
        bind_host = web_config.get('bind_host', '127.0.0.1')
        self.assertIn(bind_host, ['127.0.0.1', 'localhost'])


class TestWebUIConfigValidation(unittest.TestCase):
    """Test web UI configuration validation."""
    
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
    
    def test_web_port_range_validation(self):
        """Test that valid port ranges are accepted."""
        config_manager = ConfigManager(str(self.config_path))
        
        # Test valid ports
        for port in [80, 443, 4328, 8080, 65535]:
            config = config_manager.get_config(include_secrets=False)
            config['web']['port'] = port
            result = config_manager.update_config(config, preserve_secrets=True)
            self.assertEqual(result['status'], 'ok', f"Port {port} should be valid")
    
    def test_web_host_string_type(self):
        """Test that web host must be a string."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=False)
        
        # Valid strings
        for host in ['127.0.0.1', '0.0.0.0', 'localhost', '192.168.1.100']:
            config['web']['bind_host'] = host
            result = config_manager.update_config(config, preserve_secrets=True)
            self.assertEqual(result['status'], 'ok', f"Host '{host}' should be valid")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestWebUIConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestWebUIConfigValidation))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

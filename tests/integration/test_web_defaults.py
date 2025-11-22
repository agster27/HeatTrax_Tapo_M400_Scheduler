#!/usr/bin/env python3
"""
Test Web UI default configuration and environment variable overrides.

Tests specifically for the new default bind configuration (0.0.0.0:4328)
and ensures env variable overrides (HEATTRAX_WEB_HOST, HEATTRAX_WEB_PORT) work correctly.
"""

import os
import sys
import unittest
import tempfile
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_manager import ConfigManager


class TestWebDefaults(unittest.TestCase):
    """Test Web UI default configuration."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "test_config.yaml"
        
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear all HEATTRAX_ env vars to test pure defaults
        for key in list(os.environ.keys()):
            if key.startswith('HEATTRAX_'):
                del os.environ[key]
    
    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Clean up test files
        import shutil
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
    
    def test_default_bind_host_is_all_interfaces(self):
        """Test that default bind_host is 0.0.0.0 (all interfaces)."""
        # Create ConfigManager without any config file or env vars
        config_manager = ConfigManager(str(self.config_path))
        
        # Get the config
        config = config_manager.get_config(include_secrets=False)
        
        # Verify web section has correct defaults
        self.assertIn('web', config)
        self.assertEqual(config['web']['bind_host'], '0.0.0.0')
        self.assertEqual(config['web']['port'], 4328)
        self.assertEqual(config['web']['enabled'], True)
        
        # Verify no env overrides are tracked
        env_overrides = config_manager.get_env_overridden_paths()
        self.assertNotIn('web.bind_host', env_overrides)
        self.assertNotIn('web.port', env_overrides)
    
    def test_default_port_is_4328(self):
        """Test that default port is 4328."""
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=False)
        
        self.assertEqual(config['web']['port'], 4328)
    
    def test_env_override_bind_host(self):
        """Test that HEATTRAX_WEB_HOST overrides default bind_host."""
        # Set environment variable
        os.environ['HEATTRAX_WEB_HOST'] = '127.0.0.1'
        
        # Create ConfigManager
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=False)
        
        # Verify env override took effect
        self.assertEqual(config['web']['bind_host'], '127.0.0.1')
        
        # Verify env override is tracked
        env_overrides = config_manager.get_env_overridden_paths()
        self.assertIn('web.bind_host', env_overrides)
        self.assertEqual(env_overrides['web.bind_host'], 'HEATTRAX_WEB_HOST')
    
    def test_env_override_port(self):
        """Test that HEATTRAX_WEB_PORT overrides default port."""
        # Set environment variable
        os.environ['HEATTRAX_WEB_PORT'] = '9999'
        
        # Create ConfigManager
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=False)
        
        # Verify env override took effect
        self.assertEqual(config['web']['port'], 9999)
        
        # Verify env override is tracked
        env_overrides = config_manager.get_env_overridden_paths()
        self.assertIn('web.port', env_overrides)
        self.assertEqual(env_overrides['web.port'], 'HEATTRAX_WEB_PORT')
    
    def test_env_override_both_host_and_port(self):
        """Test that both HEATTRAX_WEB_HOST and HEATTRAX_WEB_PORT can override simultaneously."""
        # Set environment variables
        os.environ['HEATTRAX_WEB_HOST'] = '192.168.1.100'
        os.environ['HEATTRAX_WEB_PORT'] = '8080'
        
        # Create ConfigManager
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=False)
        
        # Verify both env overrides took effect
        self.assertEqual(config['web']['bind_host'], '192.168.1.100')
        self.assertEqual(config['web']['port'], 8080)
        
        # Verify both env overrides are tracked
        env_overrides = config_manager.get_env_overridden_paths()
        self.assertIn('web.bind_host', env_overrides)
        self.assertIn('web.port', env_overrides)
        self.assertEqual(env_overrides['web.bind_host'], 'HEATTRAX_WEB_HOST')
        self.assertEqual(env_overrides['web.port'], 'HEATTRAX_WEB_PORT')
    
    def test_localhost_override_for_security(self):
        """Test that users can override to localhost for enhanced security."""
        # Set environment variable to restrict to localhost
        os.environ['HEATTRAX_WEB_HOST'] = 'localhost'
        
        # Create ConfigManager
        config_manager = ConfigManager(str(self.config_path))
        config = config_manager.get_config(include_secrets=False)
        
        # Verify override to localhost works
        self.assertEqual(config['web']['bind_host'], 'localhost')
        
        # Verify it's tracked as env override
        env_overrides = config_manager.get_env_overridden_paths()
        self.assertIn('web.bind_host', env_overrides)


if __name__ == '__main__':
    unittest.main()

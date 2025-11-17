#!/usr/bin/env python3
"""
Test health server configuration and defaults.
"""

import os
import sys
import unittest
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config_loader import Config, ConfigError
from scheduler_enhanced import EnhancedScheduler


class TestHealthServerConfig(unittest.TestCase):
    """Test health server configuration."""
    
    def setUp(self):
        """Set up test environment."""
        # Store original environment
        self.original_env = os.environ.copy()
        
        # Clear any existing health server env vars
        for var in ['HEATTRAX_HEALTH_SERVER_ENABLED', 
                    'HEATTRAX_HEALTH_SERVER_HOST', 
                    'HEATTRAX_HEALTH_SERVER_PORT']:
            os.environ.pop(var, None)
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_default_health_server_disabled(self):
        """Test that health server is disabled by default."""
        config = Config('config.example.yaml')
        
        # Check defaults
        self.assertEqual(config.health_server.get('enabled'), False)
        self.assertEqual(config.health_server.get('port'), 4329)
        self.assertEqual(config.health_server.get('host'), '0.0.0.0')
    
    def test_default_port_4329(self):
        """Test that default port is 4329, not 8080."""
        config = Config('config.example.yaml')
        
        # Port should be 4329 by default
        self.assertEqual(config.health_server.get('port'), 4329)
        self.assertNotEqual(config.health_server.get('port'), 8080)
    
    def test_env_var_override_enabled(self):
        """Test that HEATTRAX_HEALTH_SERVER_ENABLED overrides config."""
        os.environ['HEATTRAX_HEALTH_SERVER_ENABLED'] = 'true'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.health_server.get('enabled'), True)
        
        # Test false value
        os.environ['HEATTRAX_HEALTH_SERVER_ENABLED'] = 'false'
        config = Config('config.example.yaml')
        self.assertEqual(config.health_server.get('enabled'), False)
    
    def test_env_var_override_port(self):
        """Test that HEATTRAX_HEALTH_SERVER_PORT overrides config."""
        os.environ['HEATTRAX_HEALTH_SERVER_PORT'] = '9999'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.health_server.get('port'), 9999)
    
    def test_env_var_override_host(self):
        """Test that HEATTRAX_HEALTH_SERVER_HOST overrides config."""
        os.environ['HEATTRAX_HEALTH_SERVER_HOST'] = '127.0.0.1'
        
        config = Config('config.example.yaml')
        self.assertEqual(config.health_server.get('host'), '127.0.0.1')
    
    def test_scheduler_no_health_server_when_disabled(self):
        """Test that scheduler doesn't create health server when disabled."""
        config = Config('config.example.yaml')
        scheduler = EnhancedScheduler(config)
        
        self.assertIsNone(scheduler.health_server)
    
    def test_scheduler_creates_health_server_when_enabled(self):
        """Test that scheduler creates health server when enabled."""
        os.environ['HEATTRAX_HEALTH_SERVER_ENABLED'] = 'true'
        
        config = Config('config.example.yaml')
        scheduler = EnhancedScheduler(config)
        
        self.assertIsNotNone(scheduler.health_server)
        self.assertEqual(scheduler.health_server.port, 4329)
        self.assertEqual(scheduler.health_server.host, '0.0.0.0')
    
    def test_scheduler_uses_custom_port(self):
        """Test that scheduler uses custom port from config."""
        os.environ['HEATTRAX_HEALTH_SERVER_ENABLED'] = 'true'
        os.environ['HEATTRAX_HEALTH_SERVER_PORT'] = '7777'
        
        config = Config('config.example.yaml')
        scheduler = EnhancedScheduler(config)
        
        self.assertIsNotNone(scheduler.health_server)
        self.assertEqual(scheduler.health_server.port, 7777)


if __name__ == '__main__':
    unittest.main()

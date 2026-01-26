#!/usr/bin/env python3
"""Tests for graceful notification failure handling."""

import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestNotificationGracefulFailure(unittest.IsolatedAsyncioTestCase):
    """Test that scheduler continues when notifications fail."""
    
    async def test_scheduler_tracks_notification_availability(self):
        """Test that scheduler tracks notification_service_available flag."""
        from src.scheduler.scheduler_enhanced import EnhancedScheduler
        
        # Create a minimal mock config
        mock_config = Mock()
        mock_config.location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York'
        }
        mock_config.weather_api = {'enabled': False}
        mock_config.notifications = {
            'required': True,
            'test_on_startup': False,
            'email': {'enabled': True}
        }
        mock_config.devices = {'groups': {}}
        mock_config.health_check = {'interval_hours': 24}
        mock_config.health_server = {'enabled': False}
        mock_config._config = {}
        
        # Create scheduler in setup mode
        scheduler = EnhancedScheduler(mock_config, setup_mode=True)
        
        # Verify the flag is initialized
        self.assertFalse(scheduler.notification_service_available)
        
        # Mock notification validation to fail
        with patch('src.scheduler.scheduler_enhanced.validate_and_test_notifications',
                   return_value=(False, None)):
            await scheduler.initialize()
            
            # Verify flag remains False after failed initialization
            self.assertFalse(scheduler.notification_service_available)
            print("✓ Scheduler tracks notification availability correctly")
    
    async def test_notification_service_available_flag_when_working(self):
        """Test that notification_service_available flag is set correctly when notifications work."""
        from src.scheduler.scheduler_enhanced import EnhancedScheduler
        
        # Create a minimal mock config
        mock_config = Mock()
        mock_config.location = {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York'
        }
        mock_config.weather_api = {'enabled': False}
        mock_config.notifications = {
            'required': False,
            'test_on_startup': False,
            'email': {'enabled': True}
        }
        mock_config.devices = {'groups': {}}
        mock_config.health_check = {'interval_hours': 24}
        mock_config.health_server = {'enabled': False}
        mock_config._config = {}
        
        scheduler = EnhancedScheduler(mock_config, setup_mode=True)
        
        # Mock notification service to be enabled
        mock_notification_service = Mock()
        mock_notification_service.is_enabled.return_value = True
        mock_notification_service.providers = {'email': Mock()}
        
        with patch('src.scheduler.scheduler_enhanced.validate_and_test_notifications',
                   return_value=(True, mock_notification_service)):
            await scheduler.initialize()
            
            # Verify flag is set to True when notifications work
            self.assertTrue(scheduler.notification_service_available)
            print("✓ notification_service_available flag correctly set to True")


class TestSystemStatusEndpoint(unittest.TestCase):
    """Test the /api/system/status endpoint."""
    
    def test_system_status_with_scheduler(self):
        """Test system status endpoint returns correct data."""
        from src.web.web_server import WebServer
        
        # Create mock config manager
        config_manager = MagicMock()
        config_manager.get_config.return_value = {
            'notifications': {
                'email': {
                    'enabled': True
                }
            },
            'web': {}
        }
        config_manager.get_web_pin.return_value = '1234'
        
        # Create mock scheduler
        mock_scheduler = Mock()
        mock_scheduler.notification_service_available = False
        mock_scheduler.manual_override = Mock()
        
        # Create web server
        web_server = WebServer(config_manager, scheduler=mock_scheduler)
        
        # Test the endpoint
        with web_server.app.test_client() as client:
            response = client.get('/api/system/status')
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            
            self.assertTrue(data['success'])
            self.assertIn('status', data)
            
            status = data['status']
            self.assertTrue(status['scheduler_running'])
            self.assertFalse(status['notifications_available'])
            self.assertTrue(status['pin_configured'])
            self.assertIsNotNone(status['notifications_error'])
            
            print("✓ System status endpoint returns correct data")
    
    def test_system_status_without_scheduler(self):
        """Test system status endpoint when scheduler is not running."""
        from src.web.web_server import WebServer
        
        # Create mock config manager
        config_manager = MagicMock()
        config_manager.get_config.return_value = {'web': {}}
        config_manager.get_web_pin.return_value = None
        
        # Create web server without scheduler
        web_server = WebServer(config_manager, scheduler=None)
        
        # Test the endpoint
        with web_server.app.test_client() as client:
            response = client.get('/api/system/status')
            
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            
            self.assertTrue(data['success'])
            self.assertIn('status', data)
            
            status = data['status']
            self.assertFalse(status['scheduler_running'])
            self.assertFalse(status['notifications_available'])
            self.assertFalse(status['pin_configured'])
            
            print("✓ System status endpoint works without scheduler")


if __name__ == '__main__':
    unittest.main()

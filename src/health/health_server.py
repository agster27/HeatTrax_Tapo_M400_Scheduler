"""HTTP server for health check endpoints."""

import asyncio
import logging
from typing import Optional, Dict, Any
from aiohttp import web
from datetime import datetime

logger = logging.getLogger(__name__)


class HealthCheckServer:
    """HTTP server providing health check endpoints."""
    
    def __init__(self, scheduler, host: str = '0.0.0.0', port: int = 4329):
        """
        Initialize health check server.
        
        Args:
            scheduler: Reference to EnhancedScheduler instance
            host: Host to bind to (default: 0.0.0.0)
            port: Port to bind to (default: 4329)
        """
        self.scheduler = scheduler
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        # Setup routes
        self.app.router.add_get('/health', self.handle_health)
        self.app.router.add_get('/health/weather', self.handle_weather_health)
        
        logger.info(f"Health check server initialized on {host}:{port}")
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """
        Basic application health endpoint.
        Returns 200 OK if application is running.
        
        Args:
            request: HTTP request
            
        Returns:
            JSON response with health status
        """
        try:
            response_data = {
                'status': 'ok',
                'timestamp': datetime.now().isoformat(),
                'service': 'heattrax_scheduler'
            }
            
            logger.debug("Health check request: /health -> OK")
            return web.json_response(response_data, status=200)
            
        except Exception as e:
            logger.error(f"Error in health check endpoint: {e}")
            return web.json_response(
                {'status': 'error', 'message': str(e)},
                status=500
            )
    
    async def handle_weather_health(self, request: web.Request) -> web.Response:
        """
        Weather-specific health endpoint.
        
        If weather is disabled:
            Returns 200 with status='disabled'
        
        If weather is enabled:
            Performs minimal weather check and returns status with forecast snapshot
        
        Args:
            request: HTTP request
            
        Returns:
            JSON response with weather health status
        """
        try:
            if not self.scheduler.weather_enabled:
                # Weather is disabled
                response_data = {
                    'status': 'disabled',
                    'weather_enabled': False,
                    'timestamp': datetime.now().isoformat()
                }
                logger.debug("Weather health check: weather disabled")
                return web.json_response(response_data, status=200)
            
            # Weather is enabled - perform health check
            response_data = {
                'status': 'ok',
                'weather_enabled': True,
                'timestamp': datetime.now().isoformat()
            }
            
            # Add provider info
            provider = self.scheduler.config.weather_api.get('provider', 'open-meteo')
            response_data['provider'] = provider
            
            # Try to get current conditions (with short timeout)
            try:
                # Get current conditions
                temp, conditions = await asyncio.wait_for(
                    self.scheduler.weather.get_current_conditions(),
                    timeout=5.0
                )
                
                response_data['current_conditions'] = {
                    'temperature_f': round(temp, 1),
                    'description': conditions
                }
                
                # Get precipitation forecast
                has_precip, precip_time, precip_temp = await asyncio.wait_for(
                    self.scheduler.weather.check_precipitation_forecast(
                        hours_ahead=self.scheduler.config.scheduler['forecast_hours'],
                        temperature_threshold_f=self.scheduler.config.thresholds['temperature_f']
                    ),
                    timeout=5.0
                )
                
                if has_precip and precip_time:
                    response_data['precipitation_forecast'] = {
                        'expected': True,
                        'time': precip_time.isoformat(),
                        'temperature_f': round(precip_temp, 1)
                    }
                else:
                    response_data['precipitation_forecast'] = {
                        'expected': False
                    }
                
                logger.debug(f"Weather health check: OK (provider={provider}, temp={temp}°F)")
                return web.json_response(response_data, status=200)
                
            except asyncio.TimeoutError:
                response_data['status'] = 'timeout'
                response_data['message'] = 'Weather API request timed out'
                logger.warning("Weather health check: timeout")
                return web.json_response(response_data, status=503)
                
            except Exception as e:
                response_data['status'] = 'error'
                response_data['message'] = str(e)
                logger.warning(f"Weather health check: error - {e}")
                return web.json_response(response_data, status=503)
                
        except Exception as e:
            logger.error(f"Error in weather health check endpoint: {e}")
            return web.json_response(
                {'status': 'error', 'message': str(e)},
                status=500
            )
    
    async def start(self):
        """Start the health check server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            logger.info(f"Health check server started on http://{self.host}:{self.port}")
            logger.info(f"  - Basic health: http://{self.host}:{self.port}/health")
            logger.info(f"  - Weather health: http://{self.host}:{self.port}/health/weather")
        except Exception as e:
            logger.error(f"Failed to start health check server: {e}")
            raise
    
    async def stop(self):
        """Stop the health check server."""
        try:
            if self.site:
                await self.site.stop()
            if self.runner:
                await self.runner.cleanup()
            logger.info("Health check server stopped")
        except Exception as e:
            logger.error(f"Error stopping health check server: {e}")

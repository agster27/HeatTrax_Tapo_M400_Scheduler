"""Weather service factory - creates weather service based on configuration."""

import logging
from typing import Dict, Any

from weather_service import WeatherService, WeatherServiceError
from weather_openweathermap import OpenWeatherMapService, OpenWeatherMapError


logger = logging.getLogger(__name__)


class WeatherServiceFactory:
    """Factory for creating weather service instances based on configuration."""
    
    @staticmethod
    def create_weather_service(config: Dict[str, Any]):
        """
        Create a weather service instance based on configuration.
        
        Args:
            config: Configuration dictionary with location and weather_api sections
            
        Returns:
            Weather service instance (WeatherService or OpenWeatherMapService)
            
        Raises:
            WeatherServiceError: If configuration is invalid or service creation fails
        """
        # Extract location
        location = config.get('location', {})
        latitude = location.get('latitude')
        longitude = location.get('longitude')
        timezone = location.get('timezone', 'auto')
        
        if latitude is None or longitude is None:
            raise WeatherServiceError("Location latitude and longitude are required")
        
        # Get weather API configuration
        weather_api = config.get('weather_api', {})
        provider = weather_api.get('provider', 'open-meteo').lower()
        
        logger.info(f"Creating weather service with provider: {provider}")
        
        if provider == 'openweathermap':
            # Create OpenWeatherMap service
            owm_config = weather_api.get('openweathermap', {})
            api_key = owm_config.get('api_key')
            
            if not api_key:
                logger.error("OpenWeatherMap API key is required but not provided")
                raise WeatherServiceError(
                    "OpenWeatherMap API key is required. "
                    "Add weather_api.openweathermap.api_key to config or set HEATTRAX_OPENWEATHERMAP_API_KEY"
                )
            
            api_url = owm_config.get('api_url')
            
            logger.info(f"Creating OpenWeatherMap service for lat={latitude}, lon={longitude}")
            return OpenWeatherMapService(
                api_key=api_key,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                api_url=api_url
            )
        
        elif provider == 'open-meteo':
            # Create Open-Meteo service (default, no API key required)
            logger.info(f"Creating Open-Meteo service for lat={latitude}, lon={longitude}")
            return WeatherService(
                latitude=latitude,
                longitude=longitude,
                timezone=timezone
            )
        
        else:
            logger.error(f"Unknown weather provider: {provider}")
            raise WeatherServiceError(
                f"Unknown weather provider: {provider}. "
                f"Supported providers: 'openweathermap', 'open-meteo'"
            )

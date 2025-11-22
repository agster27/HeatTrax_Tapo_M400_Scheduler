"""Weather service factory - creates weather service based on configuration."""

import logging
from typing import Dict, Any, Optional

from src.weather.weather_service import WeatherService, WeatherServiceError
from src.weather.weather_openweathermap import OpenWeatherMapService, OpenWeatherMapError
from src.weather.resilient_weather_service import ResilientWeatherService
from src.notifications.forecast_notifier import ForecastNotifier


logger = logging.getLogger(__name__)


class WeatherServiceFactory:
    """Factory for creating weather service instances based on configuration."""
    
    @staticmethod
    def create_weather_service(config: Dict[str, Any], notification_service: Optional[Any] = None):
        """
        Create a weather service instance based on configuration.
        
        Creates a base weather service (Open-Meteo or OpenWeatherMap) and wraps it
        with ResilientWeatherService for caching and outage handling.
        
        Args:
            config: Configuration dictionary with location and weather_api sections
            notification_service: Optional notification service for alerts
            
        Returns:
            ResilientWeatherService instance wrapping the base weather service
            
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
        
        # Create base weather service
        base_service = None
        
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
            base_service = OpenWeatherMapService(
                api_key=api_key,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                api_url=api_url
            )
        
        elif provider == 'open-meteo':
            # Create Open-Meteo service (default, no API key required)
            logger.info(f"Creating Open-Meteo service for lat={latitude}, lon={longitude}")
            base_service = WeatherService(
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
        
        # Get resilience configuration
        weather_config = weather_api.get('resilience', {})
        cache_file = weather_config.get('cache_file', 'state/weather_cache.json')
        cache_valid_hours = weather_config.get('cache_valid_hours', 6.0)
        forecast_horizon_hours = weather_config.get('forecast_horizon_hours', 12)
        refresh_interval_minutes = weather_config.get('refresh_interval_minutes', 10)
        retry_interval_minutes = weather_config.get('retry_interval_minutes', 5)
        max_retry_interval_minutes = weather_config.get('max_retry_interval_minutes', 60)
        outage_alert_after_minutes = weather_config.get('outage_alert_after_minutes', 30)
        
        logger.info(f"Wrapping with resilient weather service (cache_valid_hours={cache_valid_hours})")
        
        # Create forecast notifier if configured
        forecast_notifier = None
        notifications_config = config.get('notifications', {})
        forecast_config = notifications_config.get('forecast', {})
        
        if forecast_config.get('enabled', False) and notification_service:
            notify_mode = forecast_config.get('notify_mode', 'always')
            temp_threshold = forecast_config.get('temp_change_threshold_f', 5.0)
            precip_threshold = forecast_config.get('precip_change_threshold_mm', 2.0)
            state_file = forecast_config.get('state_file', 'state/forecast_notification_state.json')
            
            logger.info(f"Creating forecast notifier (mode={notify_mode})")
            forecast_notifier = ForecastNotifier(
                notification_service=notification_service,
                notify_mode=notify_mode,
                temp_change_threshold_f=temp_threshold,
                precip_change_threshold_mm=precip_threshold,
                state_file=state_file
            )
        
        # Wrap with resilient service
        return ResilientWeatherService(
            weather_service=base_service,
            cache_file=cache_file,
            cache_valid_hours=cache_valid_hours,
            forecast_horizon_hours=forecast_horizon_hours,
            refresh_interval_minutes=refresh_interval_minutes,
            retry_interval_minutes=retry_interval_minutes,
            max_retry_interval_minutes=max_retry_interval_minutes,
            outage_alert_after_minutes=outage_alert_after_minutes,
            notification_service=notification_service,
            forecast_notifier=forecast_notifier
        )

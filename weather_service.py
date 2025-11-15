"""Weather service using Open-Meteo API."""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging


logger = logging.getLogger(__name__)


class WeatherServiceError(Exception):
    """Weather service error exception."""
    pass


class WeatherService:
    """Weather service for fetching weather data from Open-Meteo API."""
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, latitude: float, longitude: float, timezone: str = "auto"):
        """
        Initialize weather service.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            timezone: Timezone for the location
        """
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
    
    async def get_forecast(self, hours_ahead: int = 12) -> Dict:
        """
        Get weather forecast from Open-Meteo API.
        
        Args:
            hours_ahead: Number of hours to forecast ahead
            
        Returns:
            Dictionary containing forecast data
        """
        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'hourly': 'temperature_2m,precipitation',
            'temperature_unit': 'fahrenheit',
            'timezone': self.timezone,
            'forecast_days': max(1, (hours_ahead // 24) + 1)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL, params=params) as response:
                    if response.status != 200:
                        raise WeatherServiceError(f"API request failed with status {response.status}")
                    
                    data = await response.json()
                    logger.debug(f"Received weather data: {data}")
                    return data
        except aiohttp.ClientError as e:
            raise WeatherServiceError(f"Failed to fetch weather data: {e}")
        except Exception as e:
            raise WeatherServiceError(f"Unexpected error fetching weather: {e}")
    
    async def check_precipitation_forecast(
        self,
        hours_ahead: int = 12,
        temperature_threshold_f: float = 34.0
    ) -> Tuple[bool, Optional[datetime], Optional[float]]:
        """
        Check if precipitation is forecasted with temperature below threshold.
        
        Args:
            hours_ahead: Number of hours to look ahead
            temperature_threshold_f: Temperature threshold in Fahrenheit
            
        Returns:
            Tuple of (precipitation_expected, first_precipitation_time, temperature)
        """
        try:
            forecast = await self.get_forecast(hours_ahead)
            
            if 'hourly' not in forecast:
                logger.error("No hourly data in forecast response")
                return False, None, None
            
            hourly = forecast['hourly']
            times = hourly.get('time', [])
            temperatures = hourly.get('temperature_2m', [])
            precipitations = hourly.get('precipitation', [])
            
            if not times or not temperatures or not precipitations:
                logger.error("Missing data in forecast response")
                return False, None, None
            
            now = datetime.now()
            cutoff_time = now + timedelta(hours=hours_ahead)
            
            for i, time_str in enumerate(times):
                try:
                    forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    # Convert to naive datetime for comparison
                    forecast_time = forecast_time.replace(tzinfo=None)
                    
                    if forecast_time > cutoff_time:
                        break
                    
                    if forecast_time < now:
                        continue
                    
                    temp = temperatures[i]
                    precip = precipitations[i]
                    
                    # Check if there's precipitation and temperature is below threshold
                    if precip > 0 and temp < temperature_threshold_f:
                        logger.info(
                            f"Precipitation expected at {forecast_time}: "
                            f"{precip}mm, temp: {temp}°F"
                        )
                        return True, forecast_time, temp
                
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing forecast data at index {i}: {e}")
                    continue
            
            logger.info("No precipitation expected below temperature threshold")
            return False, None, None
            
        except WeatherServiceError as e:
            logger.error(f"Weather service error: {e}")
            raise
    
    async def get_current_conditions(self) -> Tuple[float, float]:
        """
        Get current temperature and precipitation.
        
        Returns:
            Tuple of (temperature_f, precipitation_mm)
        """
        try:
            forecast = await self.get_forecast(hours_ahead=1)
            
            if 'hourly' not in forecast:
                raise WeatherServiceError("No hourly data in forecast response")
            
            hourly = forecast['hourly']
            temperatures = hourly.get('temperature_2m', [])
            precipitations = hourly.get('precipitation', [])
            
            if not temperatures or not precipitations:
                raise WeatherServiceError("Missing current conditions data")
            
            # Get the first forecast hour (closest to current time)
            current_temp = temperatures[0]
            current_precip = precipitations[0]
            
            logger.debug(f"Current conditions: {current_temp}°F, {current_precip}mm precip")
            return current_temp, current_precip
            
        except WeatherServiceError as e:
            logger.error(f"Failed to get current conditions: {e}")
            raise

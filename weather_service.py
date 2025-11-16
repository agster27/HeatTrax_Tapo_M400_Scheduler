"""Weather service using Open-Meteo API."""

import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
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
        # Validate input parameters
        if not isinstance(hours_ahead, (int, float)) or hours_ahead <= 0:
            logger.error(f"Invalid hours_ahead parameter: {hours_ahead}")
            raise WeatherServiceError(f"hours_ahead must be a positive number, got: {hours_ahead}")
        
        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'hourly': 'temperature_2m,precipitation',
            'temperature_unit': 'fahrenheit',
            'timezone': self.timezone,
            'forecast_days': max(1, (hours_ahead // 24) + 1)
        }
        
        logger.info(f"Requesting weather forecast for {hours_ahead} hours ahead")
        logger.debug(f"API request URL: {self.BASE_URL}")
        logger.debug(f"API request parameters: {params}")
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"Opening HTTP session to {self.BASE_URL}")
                async with session.get(self.BASE_URL, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    logger.debug(f"Received HTTP response with status: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API request failed with status {response.status}")
                        logger.error(f"Error response body: {error_text}")
                        raise WeatherServiceError(
                            f"API request failed with status {response.status}: {error_text}"
                        )
                    
                    data = await response.json()
                    logger.info("Successfully retrieved weather data from API")
                    logger.debug(f"Response data keys: {data.keys() if data else 'None'}")
                    
                    # Validate response structure
                    if not data:
                        logger.error("Received empty response from weather API")
                        raise WeatherServiceError("Empty response from weather API")
                    
                    logger.debug(f"Full weather data: {data}")
                    return data
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error while fetching weather data: {type(e).__name__}: {e}")
            raise WeatherServiceError(f"Failed to fetch weather data: {e}")
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout while connecting to weather API: {e}")
            raise WeatherServiceError(f"Weather API request timed out after 30 seconds")
        except Exception as e:
            logger.error(f"Unexpected error fetching weather: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
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
        logger.info(f"Checking precipitation forecast: hours_ahead={hours_ahead}, temp_threshold={temperature_threshold_f}°F")
        
        # Validate input parameters
        if not isinstance(temperature_threshold_f, (int, float)):
            logger.error(f"Invalid temperature_threshold_f: {temperature_threshold_f}")
            raise WeatherServiceError(f"temperature_threshold_f must be a number, got: {temperature_threshold_f}")
        
        try:
            forecast = await self.get_forecast(hours_ahead)
            
            if 'hourly' not in forecast:
                logger.error("No hourly data in forecast response")
                logger.error(f"Available keys in response: {list(forecast.keys())}")
                return False, None, None
            
            hourly = forecast['hourly']
            times = hourly.get('time', [])
            temperatures = hourly.get('temperature_2m', [])
            precipitations = hourly.get('precipitation', [])
            
            logger.debug(f"Received {len(times)} hourly forecast entries")
            
            if not times or not temperatures or not precipitations:
                logger.error("Missing data in forecast response")
                logger.error(f"Times count: {len(times)}, Temps count: {len(temperatures)}, Precip count: {len(precipitations)}")
                return False, None, None
            
            # Validate data consistency
            if not (len(times) == len(temperatures) == len(precipitations)):
                logger.error(
                    f"Data length mismatch: times={len(times)}, "
                    f"temperatures={len(temperatures)}, precipitations={len(precipitations)}"
                )
                return False, None, None
            
            now = datetime.now()
            cutoff_time = now + timedelta(hours=hours_ahead)
            logger.debug(f"Checking forecast from {now} to {cutoff_time}")
            
            for i, time_str in enumerate(times):
                try:
                    # Validate time string
                    if not time_str:
                        logger.warning(f"Empty time string at index {i}, skipping")
                        continue
                    
                    forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    # Convert to naive datetime for comparison
                    forecast_time = forecast_time.replace(tzinfo=None)
                    
                    if forecast_time > cutoff_time:
                        logger.debug(f"Reached cutoff time at index {i}")
                        break
                    
                    if forecast_time < now:
                        continue
                    
                    # Validate temperature and precipitation values
                    temp = temperatures[i]
                    precip = precipitations[i]
                    
                    if temp is None or precip is None:
                        logger.warning(f"Null values at index {i}, skipping")
                        continue
                    
                    if not isinstance(temp, (int, float)) or not isinstance(precip, (int, float)):
                        logger.warning(f"Invalid data types at index {i}: temp={type(temp)}, precip={type(precip)}")
                        continue
                    
                    logger.debug(f"Forecast at {forecast_time}: temp={temp}°F, precip={precip}mm")
                    
                    # Check if there's precipitation and temperature is below threshold
                    if precip > 0 and temp < temperature_threshold_f:
                        logger.info(
                            f"PRECIPITATION DETECTED: Expected at {forecast_time}: "
                            f"{precip}mm precipitation, temp: {temp}°F (threshold: {temperature_threshold_f}°F)"
                        )
                        return True, forecast_time, temp
                
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing forecast data at index {i}: {type(e).__name__}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing forecast at index {i}: {type(e).__name__}: {e}")
                    continue
            
            logger.info(f"No precipitation expected below {temperature_threshold_f}°F threshold in next {hours_ahead} hours")
            return False, None, None
            
        except WeatherServiceError as e:
            logger.error(f"Weather service error in check_precipitation_forecast: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in check_precipitation_forecast: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise WeatherServiceError(f"Error checking precipitation forecast: {e}")
    
    async def get_current_conditions(self) -> Tuple[float, float]:
        """
        Get current temperature and precipitation.
        
        Returns:
            Tuple of (temperature_f, precipitation_mm)
        """
        logger.info("Fetching current weather conditions")
        
        try:
            forecast = await self.get_forecast(hours_ahead=1)
            
            if 'hourly' not in forecast:
                logger.error("No hourly data in forecast response for current conditions")
                raise WeatherServiceError("No hourly data in forecast response")
            
            hourly = forecast['hourly']
            temperatures = hourly.get('temperature_2m', [])
            precipitations = hourly.get('precipitation', [])
            
            if not temperatures or not precipitations:
                logger.error("Missing current conditions data in response")
                logger.error(f"Temperatures available: {bool(temperatures)}, Precipitations available: {bool(precipitations)}")
                raise WeatherServiceError("Missing current conditions data")
            
            # Validate data types
            if len(temperatures) == 0 or len(precipitations) == 0:
                logger.error("Empty temperature or precipitation arrays")
                raise WeatherServiceError("Empty weather data arrays")
            
            # Get the first forecast hour (closest to current time)
            current_temp = temperatures[0]
            current_precip = precipitations[0]
            
            # Validate values
            if current_temp is None or current_precip is None:
                logger.error("Null values in current conditions")
                raise WeatherServiceError("Null values in current conditions")
            
            if not isinstance(current_temp, (int, float)) or not isinstance(current_precip, (int, float)):
                logger.error(f"Invalid data types: temp={type(current_temp)}, precip={type(current_precip)}")
                raise WeatherServiceError("Invalid data types in current conditions")
            
            logger.info(f"Current conditions: {current_temp}°F, {current_precip}mm precipitation")
            return current_temp, current_precip
            
        except WeatherServiceError as e:
            logger.error(f"Failed to get current conditions: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting current conditions: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise WeatherServiceError(f"Error getting current conditions: {e}")

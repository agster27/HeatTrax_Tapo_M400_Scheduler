"""Weather service using OpenWeatherMap API."""

import aiohttp
import asyncio
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging


logger = logging.getLogger(__name__)


class OpenWeatherMapError(Exception):
    """OpenWeatherMap API error exception."""
    pass


class OpenWeatherMapService:
    """Weather service for fetching weather data from OpenWeatherMap API."""
    
    DEFAULT_API_URL = "https://api.openweathermap.org/data/2.5"
    
    def __init__(self, api_key: str, latitude: float, longitude: float, 
                 timezone: str = "auto", api_url: str = None):
        """
        Initialize OpenWeatherMap weather service.
        
        Args:
            api_key: OpenWeatherMap API key
            latitude: Location latitude
            longitude: Location longitude
            timezone: Timezone for the location
            api_url: Optional custom API URL (defaults to official API)
        """
        if not api_key:
            raise OpenWeatherMapError("API key is required for OpenWeatherMap")
        
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.api_url = api_url or self.DEFAULT_API_URL
    
    async def get_forecast(self, hours_ahead: int = 12) -> Dict:
        """
        Get weather forecast from OpenWeatherMap API.
        
        Args:
            hours_ahead: Number of hours to forecast ahead
            
        Returns:
            Dictionary containing forecast data
        """
        # Validate input parameters
        if not isinstance(hours_ahead, (int, float)) or hours_ahead <= 0:
            logger.error(f"Invalid hours_ahead parameter: {hours_ahead}")
            raise OpenWeatherMapError(f"hours_ahead must be a positive number, got: {hours_ahead}")
        
        # Use 5-day/3-hour forecast endpoint
        endpoint = f"{self.api_url}/forecast"
        params = {
            'lat': self.latitude,
            'lon': self.longitude,
            'appid': self.api_key,
            'units': 'imperial',  # Fahrenheit
            'cnt': min(40, (hours_ahead // 3) + 2)  # 3-hour intervals, max 40 entries (5 days)
        }
        
        logger.info(f"Requesting OpenWeatherMap forecast for {hours_ahead} hours ahead")
        logger.debug(f"API request URL: {endpoint}")
        logger.debug(f"API request parameters (without key): lat={params['lat']}, lon={params['lon']}, units={params['units']}")
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.debug(f"Opening HTTP session to {endpoint}")
                async with session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    logger.debug(f"Received HTTP response with status: {response.status}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API request failed with status {response.status}")
                        logger.error(f"Error response body: {error_text}")
                        raise OpenWeatherMapError(
                            f"API request failed with status {response.status}: {error_text}"
                        )
                    
                    data = await response.json()
                    logger.info("Successfully retrieved weather data from OpenWeatherMap API")
                    logger.debug(f"Response data keys: {data.keys() if data else 'None'}")
                    
                    # Validate response structure
                    if not data:
                        logger.error("Received empty response from OpenWeatherMap API")
                        raise OpenWeatherMapError("Empty response from weather API")
                    
                    if 'list' not in data:
                        logger.error("No forecast list in OpenWeatherMap response")
                        raise OpenWeatherMapError("Invalid response format from OpenWeatherMap")
                    
                    logger.debug(f"Received {len(data.get('list', []))} forecast entries")
                    return data
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error while fetching weather data: {type(e).__name__}: {e}")
            raise OpenWeatherMapError(f"Failed to fetch weather data: {e}")
        except asyncio.TimeoutError as e:
            logger.error(f"Timeout while connecting to OpenWeatherMap API: {e}")
            raise OpenWeatherMapError(f"Weather API request timed out after 30 seconds")
        except Exception as e:
            logger.error(f"Unexpected error fetching weather: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise OpenWeatherMapError(f"Unexpected error fetching weather: {e}")
    
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
            raise OpenWeatherMapError(f"temperature_threshold_f must be a number, got: {temperature_threshold_f}")
        
        try:
            forecast = await self.get_forecast(hours_ahead)
            
            if 'list' not in forecast:
                logger.error("No forecast list in response")
                return False, None, None
            
            forecast_list = forecast['list']
            
            now = datetime.now()
            cutoff_time = now + timedelta(hours=hours_ahead)
            logger.debug(f"Checking forecast from {now} to {cutoff_time}")
            
            for entry in forecast_list:
                try:
                    # Parse forecast time
                    forecast_time = datetime.fromtimestamp(entry['dt'])
                    
                    if forecast_time > cutoff_time:
                        logger.debug(f"Reached cutoff time at {forecast_time}")
                        break
                    
                    if forecast_time < now:
                        continue
                    
                    # Extract temperature and precipitation
                    temp = entry.get('main', {}).get('temp')
                    
                    # Check for rain or snow
                    rain = entry.get('rain', {}).get('3h', 0)  # Rain in last 3 hours (mm)
                    snow = entry.get('snow', {}).get('3h', 0)  # Snow in last 3 hours (mm)
                    precip = rain + snow
                    
                    if temp is None:
                        logger.warning(f"Missing temperature data at {forecast_time}")
                        continue
                    
                    logger.debug(f"Forecast at {forecast_time}: temp={temp}°F, rain={rain}mm, snow={snow}mm")
                    
                    # Check if there's precipitation and temperature is below threshold
                    if precip > 0 and temp < temperature_threshold_f:
                        logger.info(
                            f"PRECIPITATION DETECTED: Expected at {forecast_time}: "
                            f"{precip}mm precipitation (rain={rain}mm, snow={snow}mm), "
                            f"temp: {temp}°F (threshold: {temperature_threshold_f}°F)"
                        )
                        return True, forecast_time, temp
                
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing forecast entry: {type(e).__name__}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing forecast entry: {type(e).__name__}: {e}")
                    continue
            
            logger.info(f"No precipitation expected below {temperature_threshold_f}°F threshold in next {hours_ahead} hours")
            return False, None, None
            
        except OpenWeatherMapError as e:
            logger.error(f"OpenWeatherMap error in check_precipitation_forecast: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in check_precipitation_forecast: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise OpenWeatherMapError(f"Error checking precipitation forecast: {e}")
    
    async def get_current_conditions(self) -> Tuple[float, float]:
        """
        Get current temperature and precipitation.
        
        Returns:
            Tuple of (temperature_f, precipitation_mm)
        """
        logger.info("Fetching current weather conditions from OpenWeatherMap")
        
        # Use current weather endpoint
        endpoint = f"{self.api_url}/weather"
        params = {
            'lat': self.latitude,
            'lon': self.longitude,
            'appid': self.api_key,
            'units': 'imperial'  # Fahrenheit
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API request failed with status {response.status}: {error_text}")
                        raise OpenWeatherMapError(f"Failed to get current conditions: {error_text}")
                    
                    data = await response.json()
                    
                    # Extract current conditions
                    temp = data.get('main', {}).get('temp')
                    rain = data.get('rain', {}).get('1h', 0)  # Rain in last hour (mm)
                    snow = data.get('snow', {}).get('1h', 0)  # Snow in last hour (mm)
                    precip = rain + snow
                    
                    if temp is None:
                        logger.error("Missing temperature in current conditions")
                        raise OpenWeatherMapError("Missing temperature data")
                    
                    logger.info(f"Current conditions: {temp}°F, {precip}mm precipitation")
                    return temp, precip
                    
        except OpenWeatherMapError as e:
            logger.error(f"Failed to get current conditions: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting current conditions: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise OpenWeatherMapError(f"Error getting current conditions: {e}")
    
    async def check_black_ice_risk(
        self,
        hours_ahead: int = 12,
        temperature_max_f: float = 36.0,
        dew_point_spread_f: float = 4.0,
        humidity_min_percent: float = 80.0
    ) -> Tuple[bool, Optional[datetime], Optional[float], Optional[float]]:
        """
        Check if black ice risk conditions are present in forecast.
        
        Black ice can form when:
        - Temperature is near or below freezing
        - Dew point is close to temperature (small spread indicates high moisture)
        - High relative humidity
        
        Args:
            hours_ahead: Number of hours to look ahead
            temperature_max_f: Maximum temperature to consider risk (default 36°F)
            dew_point_spread_f: Max temp-dewpoint spread for risk (default 4°F)
            humidity_min_percent: Minimum humidity for risk (default 80%)
            
        Returns:
            Tuple of (risk_detected, first_risk_time, temperature, dewpoint)
        """
        logger.info(
            f"Checking black ice risk: hours_ahead={hours_ahead}, "
            f"temp_max={temperature_max_f}°F, dew_spread={dew_point_spread_f}°F, "
            f"humidity_min={humidity_min_percent}%"
        )
        
        # Validate input parameters
        if not isinstance(temperature_max_f, (int, float)):
            logger.error(f"Invalid temperature_max_f: {temperature_max_f}")
            raise OpenWeatherMapError(f"temperature_max_f must be a number, got: {temperature_max_f}")
        
        if not isinstance(dew_point_spread_f, (int, float)):
            logger.error(f"Invalid dew_point_spread_f: {dew_point_spread_f}")
            raise OpenWeatherMapError(f"dew_point_spread_f must be a number, got: {dew_point_spread_f}")
        
        if not isinstance(humidity_min_percent, (int, float)):
            logger.error(f"Invalid humidity_min_percent: {humidity_min_percent}")
            raise OpenWeatherMapError(f"humidity_min_percent must be a number, got: {humidity_min_percent}")
        
        try:
            forecast = await self.get_forecast(hours_ahead)
            
            if 'list' not in forecast:
                logger.error("No forecast list in response")
                return False, None, None, None
            
            forecast_list = forecast['list']
            
            now = datetime.now()
            cutoff_time = now + timedelta(hours=hours_ahead)
            logger.debug(f"Checking forecast from {now} to {cutoff_time}")
            
            for entry in forecast_list:
                try:
                    # Parse forecast time
                    forecast_time = datetime.fromtimestamp(entry['dt'])
                    
                    if forecast_time > cutoff_time:
                        logger.debug(f"Reached cutoff time at {forecast_time}")
                        break
                    
                    if forecast_time < now:
                        continue
                    
                    # Extract weather data
                    main_data = entry.get('main', {})
                    temp = main_data.get('temp')
                    humidity = main_data.get('humidity')
                    
                    # Calculate dew point from temperature and humidity
                    # Using Magnus formula approximation
                    if temp is not None and humidity is not None and humidity > 0:
                        # Convert Fahrenheit to Celsius for dew point calculation
                        temp_c = (temp - 32) * 5/9
                        # Magnus formula constants
                        a = 17.27
                        b = 237.7
                        
                        # Calculate dew point in Celsius using Magnus formula
                        # Formula: Td = (b * alpha) / (a - alpha)
                        # where alpha = ln(RH/100) + (a * T) / (b + T)
                        try:
                            alpha = math.log(humidity / 100.0) + ((a * temp_c) / (b + temp_c))
                            dewpoint_c = (b * alpha) / (a - alpha)
                        except (ValueError, ZeroDivisionError):
                            # Fallback: use simplified approximation
                            dewpoint_c = temp_c - ((100 - humidity) / 5.0)
                        
                        # Convert back to Fahrenheit
                        dewpoint = (dewpoint_c * 9/5) + 32
                    else:
                        logger.warning(f"Missing temperature or humidity data at {forecast_time}")
                        continue
                    
                    logger.debug(
                        f"Forecast at {forecast_time}: temp={temp}°F, dewpoint={dewpoint:.1f}°F, "
                        f"spread={temp-dewpoint:.1f}°F, humidity={humidity}%"
                    )
                    
                    # Check black ice conditions
                    dew_spread = temp - dewpoint
                    
                    if (temp <= temperature_max_f and 
                        dew_spread <= dew_point_spread_f and 
                        humidity >= humidity_min_percent):
                        logger.info(
                            f"BLACK ICE RISK DETECTED at {forecast_time}: "
                            f"temp={temp}°F (≤{temperature_max_f}°F), "
                            f"dewpoint={dewpoint:.1f}°F, spread={dew_spread:.1f}°F (≤{dew_point_spread_f}°F), "
                            f"humidity={humidity}% (≥{humidity_min_percent}%)"
                        )
                        return True, forecast_time, temp, dewpoint
                
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing forecast entry: {type(e).__name__}: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing forecast entry: {type(e).__name__}: {e}")
                    continue
            
            logger.info(
                f"No black ice risk detected in next {hours_ahead} hours "
                f"(temp≤{temperature_max_f}°F, spread≤{dew_point_spread_f}°F, humidity≥{humidity_min_percent}%)"
            )
            return False, None, None, None
            
        except OpenWeatherMapError as e:
            logger.error(f"OpenWeatherMap error in check_black_ice_risk: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in check_black_ice_risk: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise OpenWeatherMapError(f"Error checking black ice risk: {e}")

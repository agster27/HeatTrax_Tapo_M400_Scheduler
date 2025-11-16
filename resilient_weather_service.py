"""Resilient weather service with caching and outage handling."""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Tuple, Any, Dict
from pathlib import Path

from weather_cache import WeatherCache, WeatherSnapshot
from weather_service import WeatherServiceError


logger = logging.getLogger(__name__)


class WeatherServiceState(Enum):
    """States for the weather service."""
    ONLINE = "online"  # Recent successful fetch
    DEGRADED_OFFLINE_USING_CACHE = "degraded_offline_using_cache"  # Fetch failures but cached data valid
    OFFLINE_NO_WEATHER_DATA = "offline_no_weather_data"  # Fetch failures and cache expired/unavailable


class ResilientWeatherService:
    """
    Resilient weather service wrapper that provides caching and outage handling.
    
    This wraps an existing weather service (Open-Meteo or OpenWeatherMap) and adds:
    - Persistent caching of forecasts
    - Automatic retry with exponential backoff
    - State tracking (online/degraded/offline)
    - Fallback to cached data during outages
    - Notification hooks for outage detection and recovery
    """
    
    def __init__(
        self,
        weather_service: Any,
        cache_file: str = "state/weather_cache.json",
        cache_valid_hours: float = 6.0,
        forecast_horizon_hours: int = 12,
        refresh_interval_minutes: int = 10,
        retry_interval_minutes: int = 5,
        max_retry_interval_minutes: int = 60,
        outage_alert_after_minutes: int = 30,
        notification_service: Optional[Any] = None
    ):
        """
        Initialize resilient weather service.
        
        Args:
            weather_service: Underlying weather service (WeatherService or OpenWeatherMapService)
            cache_file: Path to cache file
            cache_valid_hours: How long cached data is trusted for decision-making
            forecast_horizon_hours: How many hours of forecast to store
            refresh_interval_minutes: Normal polling interval
            retry_interval_minutes: Initial retry delay after failure
            max_retry_interval_minutes: Maximum backoff interval
            outage_alert_after_minutes: Alert if offline longer than this
            notification_service: Service for sending alerts (optional)
        """
        self.weather_service = weather_service
        self.cache = WeatherCache(cache_file)
        self.cache_valid_hours = cache_valid_hours
        self.forecast_horizon_hours = forecast_horizon_hours
        self.refresh_interval_minutes = refresh_interval_minutes
        self.retry_interval_minutes = retry_interval_minutes
        self.max_retry_interval_minutes = max_retry_interval_minutes
        self.outage_alert_after_minutes = outage_alert_after_minutes
        self.notification_service = notification_service
        
        # State tracking
        self.state = WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        self.last_successful_fetch_at: Optional[datetime] = None
        self.offline_since: Optional[datetime] = None
        self.alert_sent_for_outage = False
        self.current_retry_interval = retry_interval_minutes
        
        # Check if we have valid cached data on startup
        if self.cache.is_valid(cache_valid_hours):
            self.state = WeatherServiceState.DEGRADED_OFFLINE_USING_CACHE
            logger.info("Starting with valid cached weather data")
            # Mark as if we were online until first fetch attempt
            cache_age = self.cache.get_cache_age_hours()
            if cache_age is not None:
                self.last_successful_fetch_at = datetime.now() - timedelta(hours=cache_age)
        else:
            logger.info("Starting with no valid cached weather data")
    
    def _update_state(self) -> None:
        """Update service state based on current conditions."""
        old_state = self.state
        
        # Check if cache is valid
        cache_valid = self.cache.is_valid(self.cache_valid_hours)
        
        # Determine new state
        if self.offline_since is None:
            # We're online
            self.state = WeatherServiceState.ONLINE
        elif cache_valid:
            # Offline but have valid cache
            self.state = WeatherServiceState.DEGRADED_OFFLINE_USING_CACHE
        else:
            # Offline and no valid cache
            self.state = WeatherServiceState.OFFLINE_NO_WEATHER_DATA
        
        # Log state changes
        if old_state != self.state:
            logger.warning(f"Weather service state changed: {old_state.value} -> {self.state.value}")
            self._send_state_change_notification(old_state, self.state)
        
        # Check for outage alert
        if self.offline_since and not self.alert_sent_for_outage:
            offline_minutes = (datetime.now() - self.offline_since).total_seconds() / 60
            if offline_minutes >= self.outage_alert_after_minutes:
                self._send_outage_alert(offline_minutes)
                self.alert_sent_for_outage = True
    
    def _send_state_change_notification(
        self,
        old_state: WeatherServiceState,
        new_state: WeatherServiceState
    ) -> None:
        """Send notification about state change."""
        if not self.notification_service:
            return
        
        # Map states to notification events
        if new_state == WeatherServiceState.ONLINE and old_state != WeatherServiceState.ONLINE:
            # Recovery
            event_type = "weather_service_recovered"
            message = "Weather service has recovered and is now online"
            if self.offline_since:
                offline_duration = (datetime.now() - self.offline_since).total_seconds() / 60
                message += f" (was offline for {offline_duration:.1f} minutes)"
        elif new_state == WeatherServiceState.DEGRADED_OFFLINE_USING_CACHE:
            event_type = "weather_service_degraded"
            message = "Weather service is offline but using cached data"
        elif new_state == WeatherServiceState.OFFLINE_NO_WEATHER_DATA:
            event_type = "weather_service_offline"
            message = "Weather service is offline and no valid cached data available - using static schedule"
        else:
            return
        
        try:
            asyncio.create_task(
                self.notification_service.send_notification(
                    event_type=event_type,
                    message=message,
                    details={
                        'previous_state': old_state.value,
                        'current_state': new_state.value,
                        'cache_age_hours': self.cache.get_cache_age_hours()
                    }
                )
            )
        except Exception as e:
            logger.warning(f"Failed to send state change notification: {e}")
    
    def _send_outage_alert(self, offline_minutes: float) -> None:
        """Send alert that weather service has been offline too long."""
        if not self.notification_service:
            return
        
        logger.critical(
            f"WEATHER SERVICE OUTAGE ALERT: Service has been offline for {offline_minutes:.1f} minutes "
            f"(threshold: {self.outage_alert_after_minutes} minutes)"
        )
        
        try:
            asyncio.create_task(
                self.notification_service.send_notification(
                    event_type="weather_service_outage_alert",
                    message=f"Weather service has been offline for {offline_minutes:.1f} minutes",
                    details={
                        'offline_since': self.offline_since.isoformat() if self.offline_since else None,
                        'offline_minutes': offline_minutes,
                        'alert_threshold_minutes': self.outage_alert_after_minutes,
                        'state': self.state.value
                    }
                )
            )
        except Exception as e:
            logger.warning(f"Failed to send outage alert: {e}")
    
    async def fetch_and_cache_forecast(self) -> bool:
        """
        Attempt to fetch fresh weather data and cache it.
        
        Returns:
            True if successful, False on failure
        """
        try:
            logger.info("Fetching fresh weather forecast...")
            
            # Get forecast from underlying service
            forecast_data = await self.weather_service.get_forecast(
                hours_ahead=self.forecast_horizon_hours
            )
            
            # Save to cache
            success = self.cache.save_forecast(
                latitude=self.weather_service.latitude,
                longitude=self.weather_service.longitude,
                forecast_data=forecast_data,
                forecast_hours=self.forecast_horizon_hours
            )
            
            if success:
                # Update state tracking
                self.last_successful_fetch_at = datetime.now()
                was_offline = self.offline_since is not None
                self.offline_since = None
                self.alert_sent_for_outage = False
                self.current_retry_interval = self.retry_interval_minutes
                
                # Update state
                self._update_state()
                
                logger.info(f"Successfully fetched and cached weather forecast")
                return True
            else:
                logger.error("Failed to save forecast to cache")
                return False
        
        except WeatherServiceError as e:
            logger.error(f"Weather service error: {e}")
            
            # Mark as offline if this is first failure
            if self.offline_since is None:
                self.offline_since = datetime.now()
                logger.warning("Weather service went offline")
            
            # Update state
            self._update_state()
            
            return False
        
        except Exception as e:
            logger.error(f"Unexpected error fetching forecast: {type(e).__name__}: {e}")
            
            # Mark as offline if this is first failure
            if self.offline_since is None:
                self.offline_since = datetime.now()
                logger.warning("Weather service went offline")
            
            # Update state
            self._update_state()
            
            return False
    
    def get_next_fetch_interval_minutes(self) -> int:
        """
        Get the interval until next fetch attempt.
        
        Returns:
            Minutes to wait before next fetch
        """
        if self.state == WeatherServiceState.ONLINE:
            return self.refresh_interval_minutes
        else:
            # Use exponential backoff for retries
            return self.current_retry_interval
    
    def update_retry_interval(self) -> None:
        """Update retry interval with exponential backoff."""
        if self.state != WeatherServiceState.ONLINE:
            # Double the retry interval, up to max
            self.current_retry_interval = min(
                self.current_retry_interval * 2,
                self.max_retry_interval_minutes
            )
            logger.info(f"Updated retry interval to {self.current_retry_interval} minutes")
    
    async def get_current_conditions(self) -> Optional[Tuple[float, float]]:
        """
        Get current temperature and precipitation.
        
        Returns weather from cache if available, otherwise returns None
        to signal that weather data is unavailable.
        
        Returns:
            Tuple of (temperature_f, precipitation_mm) or None if unavailable
        """
        if self.state == WeatherServiceState.OFFLINE_NO_WEATHER_DATA:
            logger.warning("No weather data available (service offline and cache invalid)")
            return None
        
        # Try to get from cache
        conditions = self.cache.get_current_conditions()
        
        if conditions:
            temp, precip = conditions
            logger.debug(f"Current conditions from cache: {temp}°F, {precip}mm")
            return conditions
        
        logger.warning("Failed to get current conditions from cache")
        return None
    
    async def check_precipitation_forecast(
        self,
        hours_ahead: int = 12,
        temperature_threshold_f: float = 34.0
    ) -> Tuple[bool, Optional[datetime], Optional[float]]:
        """
        Check if precipitation is forecasted with temperature below threshold.
        
        Returns data from cache if available, otherwise returns (False, None, None)
        to signal that weather data is unavailable.
        
        Args:
            hours_ahead: Number of hours to look ahead
            temperature_threshold_f: Temperature threshold in Fahrenheit
            
        Returns:
            Tuple of (precipitation_expected, first_precipitation_time, temperature)
        """
        if self.state == WeatherServiceState.OFFLINE_NO_WEATHER_DATA:
            logger.warning("No weather data available for precipitation check")
            return (False, None, None)
        
        # Check cache for precipitation
        if not self.cache.cache_data:
            logger.warning("No cached forecast data available")
            return (False, None, None)
        
        try:
            forecast = self.cache.cache_data['forecast']
            now = datetime.now()
            cutoff_time = now + timedelta(hours=hours_ahead)
            
            for entry in forecast:
                try:
                    forecast_time = datetime.fromisoformat(entry['timestamp'])
                    
                    if forecast_time > cutoff_time:
                        break
                    
                    if forecast_time < now:
                        continue
                    
                    temp = entry['temperature_f']
                    precip = entry['precipitation_mm']
                    
                    # Check if there's precipitation and temperature is below threshold
                    if precip > 0 and temp < temperature_threshold_f:
                        logger.info(
                            f"PRECIPITATION DETECTED (from cache): Expected at {forecast_time}: "
                            f"{precip}mm precipitation, temp: {temp}°F (threshold: {temperature_threshold_f}°F)"
                        )
                        return (True, forecast_time, temp)
                
                except (KeyError, ValueError) as e:
                    logger.warning(f"Error processing cached forecast entry: {e}")
                    continue
            
            logger.info(
                f"No precipitation expected below {temperature_threshold_f}°F threshold "
                f"in next {hours_ahead} hours (from cache)"
            )
            return (False, None, None)
        
        except Exception as e:
            logger.error(f"Error checking precipitation from cache: {type(e).__name__}: {e}")
            return (False, None, None)
    
    def get_state(self) -> WeatherServiceState:
        """Get current service state."""
        return self.state
    
    def get_state_info(self) -> Dict[str, Any]:
        """
        Get detailed state information.
        
        Returns:
            Dictionary with state details
        """
        cache_age = self.cache.get_cache_age_hours()
        
        info = {
            'state': self.state.value,
            'last_successful_fetch_at': self.last_successful_fetch_at.isoformat() if self.last_successful_fetch_at else None,
            'offline_since': self.offline_since.isoformat() if self.offline_since else None,
            'cache_age_hours': cache_age,
            'cache_valid': self.cache.is_valid(self.cache_valid_hours),
            'cache_valid_hours_threshold': self.cache_valid_hours,
            'next_fetch_interval_minutes': self.get_next_fetch_interval_minutes(),
            'alert_sent_for_outage': self.alert_sent_for_outage
        }
        
        if self.offline_since:
            offline_duration = (datetime.now() - self.offline_since).total_seconds() / 60
            info['offline_duration_minutes'] = offline_duration
        
        return info

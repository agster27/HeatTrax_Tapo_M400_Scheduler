"""Solar time calculations for sunrise/sunset scheduling."""

import logging
from datetime import date, time, datetime, timedelta
from typing import Tuple, Optional
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun


logger = logging.getLogger(__name__)


class SolarCalculator:
    """
    Calculate sunrise and sunset times for scheduling.
    
    Caches daily calculations to avoid redundant computation.
    """
    
    def __init__(self, latitude: float, longitude: float, timezone: str):
        """
        Initialize solar calculator.
        
        Args:
            latitude: Location latitude in degrees
            longitude: Location longitude in degrees
            timezone: IANA timezone string (e.g., "America/New_York")
        """
        self.latitude = latitude
        self.longitude = longitude
        self.timezone_str = timezone
        self.timezone = ZoneInfo(timezone)
        
        # Create LocationInfo for astral
        self.location = LocationInfo(
            name="Location",
            region="",
            timezone=timezone,
            latitude=latitude,
            longitude=longitude
        )
        
        # Cache for daily calculations: date -> (sunrise_time, sunset_time)
        self._cache = {}
        
        logger.info(
            f"Solar calculator initialized: lat={latitude}, lon={longitude}, tz={timezone}"
        )
    
    def calculate_solar_times(self, target_date: date) -> Tuple[time, time]:
        """
        Calculate sunrise and sunset for given date.
        
        Args:
            target_date: Date to calculate solar times for
            
        Returns:
            Tuple of (sunrise_time, sunset_time) as time objects in configured timezone
            
        Raises:
            ValueError: If solar calculation fails (e.g., polar regions)
        """
        # Check cache first
        if target_date in self._cache:
            logger.debug(f"Using cached solar times for {target_date}")
            return self._cache[target_date]
        
        try:
            # Calculate sun times for the date
            s = sun(self.location.observer, date=target_date, tzinfo=self.timezone)
            
            sunrise_dt = s['sunrise']
            sunset_dt = s['sunset']
            
            # Extract time objects
            sunrise_time = sunrise_dt.time()
            sunset_time = sunset_dt.time()
            
            # Cache the result
            self._cache[target_date] = (sunrise_time, sunset_time)
            
            logger.info(
                f"Calculated solar times for {target_date}: "
                f"sunrise={sunrise_time.strftime('%H:%M')}, "
                f"sunset={sunset_time.strftime('%H:%M')}"
            )
            
            return sunrise_time, sunset_time
            
        except Exception as e:
            logger.error(f"Failed to calculate solar times for {target_date}: {e}")
            raise ValueError(f"Solar calculation failed: {e}")
    
    def get_sunrise_time(
        self,
        target_date: date,
        offset_minutes: int = 0,
        fallback: Optional[str] = None
    ) -> time:
        """
        Get sunrise time with optional offset.
        
        Args:
            target_date: Date to get sunrise for
            offset_minutes: Minutes to offset (positive = after, negative = before)
            fallback: Fallback time string (HH:MM) if calculation fails
            
        Returns:
            Sunrise time with offset applied
            
        Raises:
            ValueError: If calculation fails and no fallback provided
        """
        try:
            sunrise_time, _ = self.calculate_solar_times(target_date)
            
            # Apply offset if needed
            if offset_minutes != 0:
                # Convert to datetime to do time math
                dt = datetime.combine(target_date, sunrise_time)
                dt += timedelta(minutes=offset_minutes)
                sunrise_time = dt.time()
                
                logger.debug(
                    f"Applied offset {offset_minutes}min to sunrise: "
                    f"{sunrise_time.strftime('%H:%M')}"
                )
            
            return sunrise_time
            
        except ValueError as e:
            if fallback:
                logger.warning(
                    f"Solar calculation failed, using fallback {fallback}: {e}"
                )
                return datetime.strptime(fallback, "%H:%M").time()
            else:
                raise
    
    def get_sunset_time(
        self,
        target_date: date,
        offset_minutes: int = 0,
        fallback: Optional[str] = None
    ) -> time:
        """
        Get sunset time with optional offset.
        
        Args:
            target_date: Date to get sunset for
            offset_minutes: Minutes to offset (positive = after, negative = before)
            fallback: Fallback time string (HH:MM) if calculation fails
            
        Returns:
            Sunset time with offset applied
            
        Raises:
            ValueError: If calculation fails and no fallback provided
        """
        try:
            _, sunset_time = self.calculate_solar_times(target_date)
            
            # Apply offset if needed
            if offset_minutes != 0:
                # Convert to datetime to do time math
                dt = datetime.combine(target_date, sunset_time)
                dt += timedelta(minutes=offset_minutes)
                sunset_time = dt.time()
                
                logger.debug(
                    f"Applied offset {offset_minutes}min to sunset: "
                    f"{sunset_time.strftime('%H:%M')}"
                )
            
            return sunset_time
            
        except ValueError as e:
            if fallback:
                logger.warning(
                    f"Solar calculation failed, using fallback {fallback}: {e}"
                )
                return datetime.strptime(fallback, "%H:%M").time()
            else:
                raise
    
    def clear_cache(self):
        """Clear the solar time cache."""
        self._cache.clear()
        logger.debug("Solar time cache cleared")
    
    def get_cached_dates(self) -> list:
        """Get list of dates currently cached."""
        return list(self._cache.keys())

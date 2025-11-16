"""Weather cache for storing and retrieving weather forecast data."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class WeatherSnapshot:
    """A snapshot of weather conditions at a specific time."""
    timestamp: str  # ISO format
    temperature_f: float
    precipitation_mm: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeatherSnapshot':
        """Create from dictionary."""
        return cls(**data)


class WeatherCache:
    """
    Cache for weather forecast data with persistence and validation.
    
    Stores the last successful forecast to disk and provides methods
    to retrieve weather snapshots within the cache validity horizon.
    """
    
    def __init__(self, cache_file: str = "weather_cache.json"):
        """
        Initialize weather cache.
        
        Args:
            cache_file: Path to cache file
        """
        self.cache_file = Path(cache_file)
        self.cache_data: Optional[Dict[str, Any]] = None
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from disk if it exists."""
        if not self.cache_file.exists():
            logger.info(f"No existing cache file found at {self.cache_file}")
            self.cache_data = None
            return
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            # Validate cache structure
            if not self._validate_cache_structure(data):
                logger.warning("Invalid cache structure, ignoring cache")
                self.cache_data = None
                return
            
            self.cache_data = data
            logger.info(f"Loaded weather cache from {self.cache_file}")
            
            # Log cache age
            fetched_at = datetime.fromisoformat(data['fetched_at'])
            age_hours = (datetime.now() - fetched_at).total_seconds() / 3600
            logger.info(f"Cache age: {age_hours:.1f} hours")
            
        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.warning(f"Failed to load cache: {type(e).__name__}: {e}")
            self.cache_data = None
    
    def _validate_cache_structure(self, data: Dict[str, Any]) -> bool:
        """
        Validate that cache has required structure.
        
        Args:
            data: Cache data to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_keys = ['fetched_at', 'location', 'forecast']
        if not all(key in data for key in required_keys):
            logger.warning(f"Cache missing required keys. Expected: {required_keys}")
            return False
        
        # Validate location
        location = data['location']
        if not isinstance(location, dict) or 'latitude' not in location or 'longitude' not in location:
            logger.warning("Invalid location in cache")
            return False
        
        # Validate forecast
        forecast = data['forecast']
        if not isinstance(forecast, list) or len(forecast) == 0:
            logger.warning("Invalid or empty forecast in cache")
            return False
        
        # Validate at least one forecast entry
        first_entry = forecast[0]
        if not isinstance(first_entry, dict) or 'timestamp' not in first_entry:
            logger.warning("Invalid forecast entry in cache")
            return False
        
        return True
    
    def save_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_data: Dict[str, Any],
        forecast_hours: int = 12
    ) -> bool:
        """
        Save weather forecast to cache.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            forecast_data: Raw forecast data from weather API
            forecast_hours: Number of hours to store
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Extract hourly data
            if 'hourly' not in forecast_data:
                logger.error("No hourly data in forecast")
                return False
            
            hourly = forecast_data['hourly']
            times = hourly.get('time', [])
            temperatures = hourly.get('temperature_2m', [])
            precipitations = hourly.get('precipitation', [])
            
            if not times or not temperatures or not precipitations:
                logger.error("Missing data in forecast")
                return False
            
            # Build forecast list
            forecast_list = []
            now = datetime.now()
            cutoff = now + timedelta(hours=forecast_hours)
            
            for i, time_str in enumerate(times):
                try:
                    # Parse timestamp
                    forecast_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    forecast_time = forecast_time.replace(tzinfo=None)
                    
                    # Only store future forecasts within horizon
                    if forecast_time < now or forecast_time > cutoff:
                        continue
                    
                    snapshot = WeatherSnapshot(
                        timestamp=forecast_time.isoformat(),
                        temperature_f=temperatures[i],
                        precipitation_mm=precipitations[i]
                    )
                    forecast_list.append(snapshot.to_dict())
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error processing forecast at index {i}: {e}")
                    continue
            
            if not forecast_list:
                logger.error("No valid forecast entries to cache")
                return False
            
            # Build cache structure
            cache_data = {
                'fetched_at': datetime.now().isoformat(),
                'location': {
                    'latitude': latitude,
                    'longitude': longitude
                },
                'forecast': forecast_list
            }
            
            # Save to disk
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            self.cache_data = cache_data
            logger.info(f"Saved weather cache with {len(forecast_list)} entries to {self.cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving forecast to cache: {type(e).__name__}: {e}")
            return False
    
    def get_cache_age_hours(self) -> Optional[float]:
        """
        Get age of cached data in hours.
        
        Returns:
            Age in hours, or None if no cache
        """
        if not self.cache_data:
            return None
        
        try:
            fetched_at = datetime.fromisoformat(self.cache_data['fetched_at'])
            age = datetime.now() - fetched_at
            return age.total_seconds() / 3600
        except (KeyError, ValueError) as e:
            logger.error(f"Error calculating cache age: {e}")
            return None
    
    def is_valid(self, valid_hours: float) -> bool:
        """
        Check if cache is still valid.
        
        Args:
            valid_hours: Maximum age in hours
            
        Returns:
            True if cache exists and is within valid_hours
        """
        age = self.get_cache_age_hours()
        if age is None:
            return False
        
        return age <= valid_hours
    
    def location_matches(self, latitude: float, longitude: float, tolerance: float = 0.01) -> bool:
        """
        Check if cache location matches given coordinates.
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            tolerance: Allowed difference in degrees
            
        Returns:
            True if location matches
        """
        if not self.cache_data:
            return False
        
        try:
            cache_loc = self.cache_data['location']
            cache_lat = cache_loc['latitude']
            cache_lon = cache_loc['longitude']
            
            lat_diff = abs(cache_lat - latitude)
            lon_diff = abs(cache_lon - longitude)
            
            return lat_diff <= tolerance and lon_diff <= tolerance
            
        except (KeyError, TypeError) as e:
            logger.error(f"Error checking location match: {e}")
            return False
    
    def get_weather_at(self, target_time: datetime) -> Optional[WeatherSnapshot]:
        """
        Get weather snapshot for a specific time from cache.
        
        Finds the cached forecast entry closest to the target time.
        
        Args:
            target_time: Time to get weather for
            
        Returns:
            WeatherSnapshot if found, None otherwise
        """
        if not self.cache_data:
            return None
        
        try:
            forecast = self.cache_data['forecast']
            if not forecast:
                return None
            
            # Find closest forecast entry
            closest_entry = None
            min_diff = None
            
            for entry in forecast:
                entry_time = datetime.fromisoformat(entry['timestamp'])
                time_diff = abs((entry_time - target_time).total_seconds())
                
                if min_diff is None or time_diff < min_diff:
                    min_diff = time_diff
                    closest_entry = entry
            
            if closest_entry:
                return WeatherSnapshot.from_dict(closest_entry)
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving weather from cache: {type(e).__name__}: {e}")
            return None
    
    def get_current_conditions(self) -> Optional[Tuple[float, float]]:
        """
        Get current temperature and precipitation from cache.
        
        Returns:
            Tuple of (temperature_f, precipitation_mm) or None
        """
        snapshot = self.get_weather_at(datetime.now())
        if snapshot:
            return (snapshot.temperature_f, snapshot.precipitation_mm)
        return None
    
    def clear(self) -> None:
        """Clear cache data (in memory and on disk)."""
        self.cache_data = None
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                logger.info(f"Cleared cache file: {self.cache_file}")
            except Exception as e:
                logger.warning(f"Error deleting cache file: {e}")

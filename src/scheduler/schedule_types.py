"""Schedule data structures and validation for unified scheduling."""

import logging
from datetime import datetime, time
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum


logger = logging.getLogger(__name__)


class ScheduleTimeType(Enum):
    """Types of schedule time specifications."""
    TIME = "time"  # Absolute time (HH:MM)
    SUNRISE = "sunrise"  # Solar-based (sunrise + offset)
    SUNSET = "sunset"  # Solar-based (sunset + offset)
    DURATION = "duration"  # Duration-based (hours after turn on)


class SchedulePriority(Enum):
    """Priority levels for schedule conflict resolution."""
    CRITICAL = "critical"  # Safety/heating schedules (highest priority)
    NORMAL = "normal"  # Standard automation (default)
    LOW = "low"  # Nice-to-have automation


class Schedule:
    """
    Represents a single schedule with time specification and conditions.
    """
    
    def __init__(self, schedule_dict: Dict[str, Any]):
        """
        Initialize schedule from dictionary.
        
        Args:
            schedule_dict: Schedule configuration dictionary
            
        Raises:
            ValueError: If schedule configuration is invalid
        """
        self.name = schedule_dict.get('name', 'Unnamed Schedule')
        self.enabled = schedule_dict.get('enabled', True)
        
        # Parse priority
        priority_str = schedule_dict.get('priority', 'normal').lower()
        try:
            self.priority = SchedulePriority(priority_str)
        except ValueError:
            logger.warning(
                f"Invalid priority '{priority_str}' for schedule '{self.name}', "
                f"using 'normal'"
            )
            self.priority = SchedulePriority.NORMAL
        
        # Days of week (1=Monday, 7=Sunday)
        self.days = schedule_dict.get('days', [1, 2, 3, 4, 5, 6, 7])
        if not isinstance(self.days, list) or not all(1 <= d <= 7 for d in self.days):
            raise ValueError(f"Invalid days specification: {self.days}")
        
        # All day flag (new feature for 24-hour schedules)
        self.all_day = schedule_dict.get('all_day', False)
        if not isinstance(self.all_day, bool):
            raise ValueError("all_day must be true or false")
        
        # Parse on time (not required if all_day is true)
        self.on_config = schedule_dict.get('on', {})
        if not self.all_day:
            if not self.on_config:
                raise ValueError("Schedule must have 'on' time configuration")
            self._validate_time_config(self.on_config, 'on')
        
        # Parse off time (not required if all_day is true)
        self.off_config = schedule_dict.get('off', {})
        if not self.all_day:
            if not self.off_config:
                raise ValueError("Schedule must have 'off' time configuration")
            self._validate_time_config(self.off_config, 'off')
        
        # Conditions (optional)
        self.conditions = schedule_dict.get('conditions', {})
        self._validate_conditions(self.conditions)
        
        # Safety limits (optional overrides)
        self.safety = schedule_dict.get('safety', {})
        self._validate_safety(self.safety)
    
    def _validate_time_config(self, config: Dict[str, Any], label: str):
        """Validate time configuration."""
        time_type_str = config.get('type', '').lower()
        try:
            time_type = ScheduleTimeType(time_type_str)
        except ValueError:
            raise ValueError(
                f"Invalid time type '{time_type_str}' for {label} time. "
                f"Must be one of: time, sunrise, sunset, duration"
            )
        
        if time_type == ScheduleTimeType.TIME:
            # Must have 'value' in HH:MM format
            value = config.get('value')
            if not value:
                raise ValueError(f"{label} time with type 'time' must have 'value'")
            try:
                datetime.strptime(value, "%H:%M")
            except ValueError:
                raise ValueError(
                    f"Invalid time format '{value}' for {label} time. "
                    f"Must be HH:MM (24-hour)"
                )
        
        elif time_type in (ScheduleTimeType.SUNRISE, ScheduleTimeType.SUNSET):
            # Must have 'offset' and 'fallback'
            offset = config.get('offset', 0)
            if not isinstance(offset, (int, float)):
                raise ValueError(f"{label} time offset must be a number")
            if not (-180 <= offset <= 180):
                raise ValueError(
                    f"{label} time offset must be between -180 and 180 minutes"
                )
            
            fallback = config.get('fallback')
            if not fallback:
                raise ValueError(
                    f"{label} time with type '{time_type_str}' must have 'fallback'"
                )
            try:
                datetime.strptime(fallback, "%H:%M")
            except ValueError:
                raise ValueError(
                    f"Invalid fallback time format '{fallback}' for {label} time. "
                    f"Must be HH:MM (24-hour)"
                )
        
        elif time_type == ScheduleTimeType.DURATION:
            # Only valid for 'off' time
            if label != 'off':
                raise ValueError("Duration type only valid for 'off' time")
            
            # Must have 'value' in hours
            value = config.get('value')
            if not value:
                raise ValueError("Duration type must have 'value' (hours)")
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValueError("Duration value must be a positive number (hours)")
    
    def _validate_conditions(self, conditions: Dict[str, Any]):
        """Validate condition configuration."""
        if not conditions:
            return
        
        # Validate temperature_max if present
        if 'temperature_max' in conditions:
            temp = conditions['temperature_max']
            if not isinstance(temp, (int, float)):
                raise ValueError("temperature_max must be a number")
            if not (-100 <= temp <= 150):  # Reasonable range in Fahrenheit
                raise ValueError("temperature_max must be between -100 and 150°F")
        
        # Validate precipitation_active if present
        if 'precipitation_active' in conditions:
            precip = conditions['precipitation_active']
            if not isinstance(precip, bool):
                raise ValueError("precipitation_active must be true or false")
    
    def _validate_safety(self, safety: Dict[str, Any]):
        """Validate safety limit configuration."""
        if not safety:
            return
        
        # Validate max_runtime_hours if present
        if 'max_runtime_hours' in safety:
            hours = safety['max_runtime_hours']
            if not isinstance(hours, (int, float)) or hours <= 0:
                raise ValueError("max_runtime_hours must be a positive number")
        
        # Validate cooldown_minutes if present
        if 'cooldown_minutes' in safety:
            minutes = safety['cooldown_minutes']
            if not isinstance(minutes, (int, float)) or minutes < 0:
                raise ValueError("cooldown_minutes must be a non-negative number")
    
    def has_conditions(self) -> bool:
        """Check if schedule has weather conditions."""
        return bool(self.conditions)
    
    def is_all_day(self) -> bool:
        """Check if this is an all-day schedule."""
        return self.all_day
    
    def get_max_runtime_hours(self, default: float) -> float:
        """Get max runtime hours (schedule-specific or default)."""
        return self.safety.get('max_runtime_hours', default)
    
    def get_cooldown_minutes(self, default: int) -> int:
        """Get cooldown minutes (schedule-specific or default)."""
        return self.safety.get('cooldown_minutes', default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert schedule to dictionary representation."""
        result = {
            'name': self.name,
            'enabled': self.enabled,
            'priority': self.priority.value,
            'days': self.days,
            'all_day': self.all_day,
            'conditions': self.conditions if self.conditions else {},
            'safety': self.safety if self.safety else {}
        }
        # Only include on/off configs if not an all_day schedule
        if not self.all_day:
            result['on'] = self.on_config
            result['off'] = self.off_config
        return result
    
    def __repr__(self) -> str:
        if self.all_day:
            return (
                f"Schedule(name='{self.name}', enabled={self.enabled}, "
                f"priority={self.priority.value}, days={self.days}, all_day=True)"
            )
        return (
            f"Schedule(name='{self.name}', enabled={self.enabled}, "
            f"priority={self.priority.value}, days={self.days})"
        )


def validate_schedules(schedules: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate a list of schedule configurations.
    
    Args:
        schedules: List of schedule dictionaries
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if not isinstance(schedules, list):
        errors.append("Schedules must be a list")
        return False, errors
    
    for i, schedule_dict in enumerate(schedules):
        if not isinstance(schedule_dict, dict):
            errors.append(f"Schedule {i}: Must be a dictionary")
            continue
        
        try:
            # Try to create Schedule object (validates structure)
            Schedule(schedule_dict)
        except ValueError as e:
            errors.append(f"Schedule {i} ('{schedule_dict.get('name', 'unnamed')}'): {e}")
    
    return len(errors) == 0, errors


def parse_schedules(schedules_config: List[Dict[str, Any]]) -> List[Schedule]:
    """
    Parse schedule configurations into Schedule objects.
    
    Args:
        schedules_config: List of schedule dictionaries
        
    Returns:
        List of Schedule objects
        
    Raises:
        ValueError: If any schedule is invalid
    """
    schedules = []
    
    for i, schedule_dict in enumerate(schedules_config):
        try:
            schedule = Schedule(schedule_dict)
            schedules.append(schedule)
        except ValueError as e:
            raise ValueError(
                f"Invalid schedule at index {i} "
                f"('{schedule_dict.get('name', 'unnamed')}'): {e}"
            )
    
    return schedules

"""Schedule evaluation logic for unified conditional scheduling."""

import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .schedule_types import Schedule, ScheduleTimeType, SchedulePriority
from .solar_calculator import SolarCalculator


logger = logging.getLogger(__name__)


class ScheduleEvaluator:
    """
    Evaluates schedules to determine if devices should be on or off.
    
    Handles:
    - Time-based, sunrise/sunset-based, and duration-based schedules
    - Day-of-week filtering
    - Weather condition evaluation
    - Priority-based conflict resolution
    """
    
    def __init__(self, solar_calculator: SolarCalculator, timezone: ZoneInfo):
        """
        Initialize schedule evaluator.
        
        Args:
            solar_calculator: Solar calculator for sunrise/sunset times
            timezone: Timezone for local time calculations
        """
        self.solar_calculator = solar_calculator
        self.timezone = timezone
        self.logger = logging.getLogger(__name__)
    
    def should_turn_on(
        self,
        schedules: List[Schedule],
        current_time: datetime,
        weather_conditions: Optional[Dict[str, Any]] = None,
        weather_offline: bool = False
    ) -> Tuple[bool, Optional[Schedule], str]:
        """
        Determine if any schedule wants the device ON.
        
        Args:
            schedules: List of schedules to evaluate
            current_time: Current datetime in configured timezone
            weather_conditions: Optional weather data dict with 'temperature_f' and
                              'precipitation_active' keys
            weather_offline: True if weather service is offline
            
        Returns:
            Tuple of (should_turn_on, winning_schedule, reason)
        """
        if not schedules:
            return False, None, "No schedules configured"
        
        current_day = current_time.isoweekday()  # 1=Monday, 7=Sunday
        current_time_only = current_time.time()
        current_date = current_time.date()
        
        # Evaluate all enabled schedules
        active_schedules = []
        
        for schedule in schedules:
            if not schedule.enabled:
                self.logger.debug(f"Schedule '{schedule.name}' is disabled")
                continue
            
            # Check day of week
            if current_day not in schedule.days:
                self.logger.debug(
                    f"Schedule '{schedule.name}' not active on day {current_day}"
                )
                continue
            
            # Handle all_day schedules - skip time range check
            if schedule.is_all_day():
                self.logger.debug(
                    f"Schedule '{schedule.name}' is an all_day schedule, skipping time check"
                )
                in_range = True
            else:
                # Get schedule time range
                try:
                    on_time, off_time = self._get_schedule_times(
                        schedule, current_date, current_time
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to calculate times for schedule '{schedule.name}': {e}"
                    )
                    continue
                
                # Check if current time is within schedule window
                # Handle day-spanning schedules (e.g., 23:00 to 02:00)
                in_range = False
                if off_time and on_time < off_time:
                    # Normal case: on < off (same day)
                    in_range = on_time <= current_time_only < off_time
                elif off_time:
                    # Day-spanning case: on > off (crosses midnight)
                    in_range = current_time_only >= on_time or current_time_only < off_time
                else:
                    # Duration-based: only check if we've passed on_time
                    # (off_time will be None for duration schedules during evaluation)
                    in_range = current_time_only >= on_time
                
                if not in_range:
                    self.logger.debug(
                        f"Schedule '{schedule.name}' not in time range: "
                        f"current={current_time_only.strftime('%H:%M')}, "
                        f"range={on_time.strftime('%H:%M')}-"
                        f"{off_time.strftime('%H:%M') if off_time else 'duration'}"
                    )
                    continue
            
            # Check weather conditions if schedule has them
            if schedule.has_conditions():
                if weather_offline:
                    self.logger.info(
                        f"Schedule '{schedule.name}' has conditions but weather is "
                        f"OFFLINE - skipping schedule"
                    )
                    continue
                
                if not self._evaluate_conditions(
                    schedule.conditions, weather_conditions
                ):
                    self.logger.debug(
                        f"Schedule '{schedule.name}' conditions not met"
                    )
                    continue
            
            # Schedule wants device ON
            self.logger.info(
                f"Schedule '{schedule.name}' is active and wants device ON "
                f"(priority={schedule.priority.value})"
            )
            active_schedules.append(schedule)
        
        # If any schedule wants ON, return the highest priority one
        if active_schedules:
            # Sort by priority (CRITICAL > NORMAL > LOW)
            priority_order = {
                SchedulePriority.CRITICAL: 0,
                SchedulePriority.NORMAL: 1,
                SchedulePriority.LOW: 2
            }
            active_schedules.sort(key=lambda s: priority_order[s.priority])
            
            winning_schedule = active_schedules[0]
            reason = (
                f"Schedule '{winning_schedule.name}' active "
                f"(priority={winning_schedule.priority.value})"
            )
            
            if len(active_schedules) > 1:
                other_names = [s.name for s in active_schedules[1:]]
                reason += f", also active: {', '.join(other_names)}"
            
            return True, winning_schedule, reason
        
        return False, None, "No active schedules want device ON"
    
    def should_turn_off(
        self,
        schedules: List[Schedule],
        current_time: datetime,
        weather_conditions: Optional[Dict[str, Any]] = None,
        weather_offline: bool = False
    ) -> Tuple[bool, str]:
        """
        Determine if device should be turned OFF.
        
        Device should turn off if NO schedules want it ON.
        
        Args:
            schedules: List of schedules to evaluate
            current_time: Current datetime in configured timezone
            weather_conditions: Optional weather data dict
            weather_offline: True if weather service is offline
            
        Returns:
            Tuple of (should_turn_off, reason)
        """
        should_on, _, reason = self.should_turn_on(
            schedules, current_time, weather_conditions, weather_offline
        )
        
        if should_on:
            return False, f"Schedule still active: {reason}"
        else:
            return True, f"No schedules active: {reason}"
    
    def _get_schedule_times(
        self,
        schedule: Schedule,
        current_date,
        current_time: datetime
    ) -> Tuple[time, Optional[time]]:
        """
        Calculate on and off times for a schedule.
        
        Args:
            schedule: Schedule to calculate times for
            current_date: Current date
            current_time: Current datetime
            
        Returns:
            Tuple of (on_time, off_time). off_time may be None for duration-based.
            
        Raises:
            ValueError: If time calculation fails
        """
        # Calculate on_time
        on_config = schedule.on_config
        on_type = ScheduleTimeType(on_config['type'])
        
        if on_type == ScheduleTimeType.TIME:
            on_time = datetime.strptime(on_config['value'], "%H:%M").time()
        
        elif on_type == ScheduleTimeType.SUNRISE:
            on_time = self.solar_calculator.get_sunrise_time(
                current_date,
                offset_minutes=on_config.get('offset', 0),
                fallback=on_config.get('fallback')
            )
        
        elif on_type == ScheduleTimeType.SUNSET:
            on_time = self.solar_calculator.get_sunset_time(
                current_date,
                offset_minutes=on_config.get('offset', 0),
                fallback=on_config.get('fallback')
            )
        
        else:
            raise ValueError(f"Invalid on_time type: {on_type}")
        
        # Calculate off_time
        off_config = schedule.off_config
        off_type = ScheduleTimeType(off_config['type'])
        
        if off_type == ScheduleTimeType.TIME:
            off_time = datetime.strptime(off_config['value'], "%H:%M").time()
        
        elif off_type == ScheduleTimeType.SUNRISE:
            off_time = self.solar_calculator.get_sunrise_time(
                current_date,
                offset_minutes=off_config.get('offset', 0),
                fallback=off_config.get('fallback')
            )
        
        elif off_type == ScheduleTimeType.SUNSET:
            off_time = self.solar_calculator.get_sunset_time(
                current_date,
                offset_minutes=off_config.get('offset', 0),
                fallback=off_config.get('fallback')
            )
        
        elif off_type == ScheduleTimeType.DURATION:
            # Duration-based: return None for off_time (handled by state manager)
            off_time = None
        
        else:
            raise ValueError(f"Invalid off_time type: {off_type}")
        
        return on_time, off_time
    
    def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        weather_conditions: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Evaluate weather conditions.
        
        Args:
            conditions: Condition requirements from schedule
            weather_conditions: Current weather data
            
        Returns:
            True if all conditions are met
        """
        if not weather_conditions:
            self.logger.warning("No weather data available for condition evaluation")
            return False
        
        # Check temperature_max condition
        if 'temperature_max' in conditions:
            temp_max = conditions['temperature_max']
            current_temp = weather_conditions.get('temperature_f')
            
            if current_temp is None:
                self.logger.warning("Temperature data not available")
                return False
            
            if current_temp > temp_max:
                self.logger.debug(
                    f"Temperature condition not met: {current_temp}°F > {temp_max}°F"
                )
                return False
        
        # Check precipitation_active condition
        if 'precipitation_active' in conditions:
            precip_required = conditions['precipitation_active']
            precip_active = weather_conditions.get('precipitation_active', False)
            
            if precip_required and not precip_active:
                self.logger.debug("Precipitation required but not active")
                return False
            
            if not precip_required and precip_active:
                self.logger.debug("Precipitation not wanted but is active")
                return False
        
        # Check black_ice_risk condition
        if 'black_ice_risk' in conditions:
            risk_required = conditions['black_ice_risk']
            risk_active = weather_conditions.get('black_ice_risk', False)
            
            if risk_required and not risk_active:
                self.logger.debug("Black ice risk required but not detected")
                return False
            
            if not risk_required and risk_active:
                self.logger.debug("Black ice risk not wanted but is detected")
                return False
        
        # All conditions met
        return True
    
    def get_next_schedule_change(
        self,
        schedules: List[Schedule],
        current_time: datetime
    ) -> Optional[Tuple[datetime, str]]:
        """
        Calculate the next expected schedule change time.
        
        Args:
            schedules: List of schedules to evaluate
            current_time: Current datetime
            
        Returns:
            Tuple of (next_change_time, description) or None if no changes expected
        """
        # This is a simplified version - could be enhanced to look ahead
        # For now, return None (not critical for initial implementation)
        return None

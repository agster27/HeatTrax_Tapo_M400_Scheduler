"""Enhanced scheduler supporting multi-device group configurations."""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Dict, Any, Tuple, List, Optional

from src.config import Config
from src.weather import WeatherServiceFactory, WeatherServiceError
from src.devices import DeviceGroupManager
from src.scheduler.state_manager import StateManager
from src.health import HealthCheckService, HealthCheckServer
from src.scheduler.automation_overrides import AutomationOverrides
from src.scheduler.solar_calculator import SolarCalculator
from src.scheduler.schedule_types import Schedule, parse_schedules
from src.scheduler.schedule_evaluator import ScheduleEvaluator
from src.notifications.notification_service import (
    NotificationService,
    validate_and_test_notifications,
    NotificationValidationError
)


logger = logging.getLogger(__name__)


class EnhancedScheduler:
    """
    Enhanced scheduler supporting multi-device groups with weather-based
    and schedule-based automation.
    """
    
    def __init__(self, config: Config, setup_mode: bool = False):
        """
        Initialize enhanced scheduler.
        
        Args:
            config: Application configuration
            setup_mode: If True, device control is disabled (credentials missing/invalid)
        """
        self.config = config
        self.setup_mode = setup_mode
        self.logger = logging.getLogger(__name__)
        
        # Check if weather is enabled
        weather_config = config.weather_api
        self.weather_enabled = weather_config.get('enabled', True)
        
        # Weather service will be created after notification service initialization
        self.weather = None
        
        if self.weather_enabled:
            self.logger.info("Weather-based scheduling will be ENABLED")
        else:
            self.logger.info("Weather-based scheduling DISABLED - using fixed schedule behavior")
        
        # Initialize device management (skip in setup mode)
        if self.setup_mode:
            self.logger.warning("Device management DISABLED - running in setup mode")
            self.logger.warning("Configure valid Tapo credentials to enable device control")
            self.device_manager = None
        else:
            self.logger.info("Using multi-device group configuration")
            self.device_manager = DeviceGroupManager(config.devices)
        
        # State management per group
        self.states = {}  # group_name -> StateManager
        
        # Automation overrides management
        self.automation_overrides = AutomationOverrides()
        
        # Manual override management for mobile control
        from src.state.manual_override import ManualOverrideManager
        tz_name = config.location.get('timezone', 'America/New_York')
        self.manual_override = ManualOverrideManager(timezone=tz_name)
        self.logger.info("Manual override manager initialized")
        
        # Initialize notification service (will be set during validation)
        self.notification_service = None
        
        # Collect all configured device IPs with labels for health check
        configured_devices = {}  # IP -> label mapping
        groups = config.devices.get('groups', {})
        for group_name, group_config in groups.items():
            items = group_config.get('items', [])
            for item in items:
                ip = item.get('ip_address')
                if ip:
                    name = item.get('name', 'Unknown')
                    label = f"{group_name}: {name}"
                    configured_devices[ip] = label
        
        # Health check service (will set notification_service later)
        health_check_config = config.health_check
        self.health_check = HealthCheckService(
            check_interval_hours=health_check_config.get('interval_hours', 24),
            configured_devices=configured_devices,
            notification_service=None,  # Set after validation
            max_consecutive_failures=health_check_config.get('max_consecutive_failures', 3)
        )
        
        # Health check HTTP server (optional)
        health_server_config = config.health_server
        if health_server_config.get('enabled', False):
            self.health_server = HealthCheckServer(
                scheduler=self,
                host=health_server_config.get('host', '0.0.0.0'),
                port=health_server_config.get('port', 4329)
            )
        else:
            self.health_server = None
            self.logger.info("Health check HTTP server disabled")
        
        # Event loop reference for thread-safe async operations
        # This will be set in run() and used by web server to avoid creating ad-hoc loops
        # for python-kasa device operations. All kasa device I/O must run on the same loop
        # to prevent "Timeout context manager should be used inside a task" errors.
        self.loop = None
        
        # Timezone for local time calculations
        try:
            tz_name = config.location.get('timezone', 'UTC')
            self.timezone = ZoneInfo(tz_name)
            self.logger.info(f"Using timezone: {tz_name}")
        except Exception as e:
            self.logger.warning(f"Invalid timezone '{config.location.get('timezone')}', defaulting to UTC: {e}")
            self.timezone = ZoneInfo('UTC')
        
        # Solar calculator for sunrise/sunset times
        try:
            latitude = config.location.get('latitude', 0.0)
            longitude = config.location.get('longitude', 0.0)
            self.solar_calculator = SolarCalculator(latitude, longitude, tz_name)
            self.logger.info("Solar calculator initialized for schedule evaluation")
        except Exception as e:
            self.logger.warning(f"Failed to initialize solar calculator: {e}")
            self.solar_calculator = None
        
        # Schedule evaluator for unified scheduling
        if self.solar_calculator:
            self.schedule_evaluator = ScheduleEvaluator(self.solar_calculator, self.timezone)
            self.logger.info("Schedule evaluator initialized")
        else:
            self.schedule_evaluator = None
            self.logger.warning("Schedule evaluator not initialized (solar calculator unavailable)")
        
        # Get vacation mode from config
        self.vacation_mode = config._config.get('vacation_mode', False)
        if self.vacation_mode:
            self.logger.warning("VACATION MODE IS ENABLED - All schedules will be disabled")
        
        # Parse schedules for each group
        self.group_schedules = {}  # group_name -> List[Schedule]
        for group_name, group_config in groups.items():
            schedules_config = group_config.get('schedules', [])
            automation = group_config.get('automation', {})
            
            # Warn if deprecated schedule_control flag is present (regardless of schedules)
            if automation and 'schedule_control' in automation:
                self.logger.warning(
                    f"Group '{group_name}' has deprecated 'schedule_control' flag in automation config. "
                    f"This flag is ignored - use 'schedules:' array instead for schedule-based automation. "
                    f"Remove 'schedule_control' from your config to clear this warning."
                )
            
            if schedules_config:
                try:
                    self.group_schedules[group_name] = parse_schedules(schedules_config)
                    self.logger.info(
                        f"Loaded {len(self.group_schedules[group_name])} schedule(s) "
                        f"for group '{group_name}'"
                    )
                except ValueError as e:
                    self.logger.error(f"Failed to parse schedules for group '{group_name}': {e}")
                    self.group_schedules[group_name] = []
            else:
                self.group_schedules[group_name] = []
                # Check for legacy schedule format (backward compatibility)
                # Only warn if group has the old 'schedule' (singular) format
                if 'schedule' in group_config:
                    self.logger.warning(
                        f"Group '{group_name}' uses legacy 'schedule' format - "
                        f"migration to unified 'schedules:' array recommended"
                    )
    
    def _get_raw_config(self) -> Dict[str, Any]:
        """
        Get the raw configuration dictionary from the config object.
        
        This helper method provides a robust way to access the underlying config dict
        regardless of whether the config object is a Config or ConfigManager instance.
        
        Returns:
            Raw configuration dictionary, or empty dict if not accessible
        """
        # Try known attributes in order of likely availability
        # Check _config first (used by both Config and ConfigManager)
        if hasattr(self.config, '_config') and isinstance(self.config._config, dict):
            return self.config._config
        # Check config_data (legacy/alternative name, if present)
        if hasattr(self.config, 'config_data') and isinstance(self.config.config_data, dict):
            return self.config.config_data
        # Fallback to public API if available (ConfigManager)
        if hasattr(self.config, 'get_config') and callable(self.config.get_config):
            try:
                return self.config.get_config(include_secrets=False)
            except Exception as e:
                self.logger.debug(f"Failed to get config via get_config(): {e}")
        # Last resort: return empty dict
        self.logger.warning("Unable to access raw config data, using empty dict")
        return {}
    
    async def initialize(self):
        """Initialize the scheduler and device connections."""
        self.logger.info("Initializing Enhanced Scheduler...")
        
        # Validate and initialize notification service
        self.logger.info("=" * 80)
        self.logger.info("NOTIFICATION SERVICE INITIALIZATION")
        self.logger.info("=" * 80)
        
        notifications_config = self.config.notifications
        required = notifications_config.get('required', False)
        test_on_startup = notifications_config.get('test_on_startup', False)
        
        self.logger.info(f"Notifications required: {required}")
        self.logger.info(f"Test on startup: {test_on_startup}")
        
        try:
            # Validate notification configuration and test connectivity
            success, notification_service = await validate_and_test_notifications(
                notifications_config,
                test_connectivity=True,
                send_test=test_on_startup
            )
            
            if not success:
                if required:
                    self.logger.error("Notification validation failed and notifications are required")
                    raise RuntimeError("Notification validation failed (notifications.required=true)")
                else:
                    self.logger.warning("Notification validation failed, but notifications are not required - continuing")
                    # Create a disabled service
                    notification_service = None
            
            self.notification_service = notification_service
            
            # Update health check service with validated notification service
            self.health_check.notification_service = notification_service
            
            if notification_service and notification_service.is_enabled():
                self.logger.info(f"✓ Notification service initialized with {len(notification_service.providers)} provider(s)")
            else:
                self.logger.info("Notification service disabled or not configured")
        
        except NotificationValidationError as e:
            if required:
                self.logger.error(f"Notification validation failed: {e}")
                raise RuntimeError(f"Notification validation failed (notifications.required=true): {e}")
            else:
                self.logger.warning(f"Notification validation failed: {e}")
                self.logger.warning("Continuing without notifications (notifications.required=false)")
                self.notification_service = None
                self.health_check.notification_service = None
        
        self.logger.info("=" * 80)
        
        # Create weather service now that we have notification service (skip in setup mode)
        if self.weather_enabled and not self.setup_mode:
            self.logger.info("Creating resilient weather service...")
            self.weather = WeatherServiceFactory.create_weather_service(
                self.config._config, 
                notification_service=self.notification_service
            )
            self.logger.info("Weather-based scheduling ENABLED with resilience layer")
        elif self.setup_mode:
            self.logger.warning("Weather service DISABLED - running in setup mode")
        
        # Skip device initialization in setup mode
        if self.setup_mode:
            self.logger.warning("=" * 80)
            self.logger.warning("SETUP MODE ACTIVE - Device initialization SKIPPED")
            self.logger.warning("=" * 80)
            self.logger.warning("The scheduler will run in a safe no-op state")
            self.logger.warning("Configure valid Tapo credentials via Web UI to enable device control")
            self.logger.info("Scheduler initialization completed (setup mode)")
            return
        
        try:
            await self.device_manager.initialize()
            
            # Initialize state managers for each group with per-group state files
            state_dir = Path('state')
            state_dir.mkdir(exist_ok=True)
            
            for group_name in self.device_manager.get_all_groups():
                state_file = state_dir / f"{group_name}.json"
                self.states[group_name] = StateManager(state_file=str(state_file))
                self.logger.info(f"Initialized state manager for group: {group_name} (file: {state_file})")
            
            # Send weather mode notification after initialization
            await self._send_weather_mode_notification()
            
            self.logger.info("Scheduler initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize scheduler: {e}")
            raise
    
    async def _send_weather_mode_notification(self):
        """Send notification about weather mode status on startup."""
        if not self.notification_service or not self.notification_service.is_enabled():
            self.logger.debug("Notifications not enabled, skipping weather mode notification")
            return
        
        try:
            if self.weather_enabled:
                # Get current weather snapshot
                weather_details = {}
                try:
                    conditions = await self.weather.get_current_conditions()
                    if conditions:
                        temp, precip = conditions
                        weather_details['current_temperature_f'] = round(temp, 1)
                        weather_details['current_precipitation_mm'] = precip
                    else:
                        weather_details['note'] = 'Weather data unavailable at startup'
                    
                    # Get forecast info
                    result = await self.weather.check_precipitation_forecast(
                        hours_ahead=self.config.scheduler['forecast_hours'],
                        temperature_threshold_f=self.config.thresholds['temperature_f']
                    )
                    
                    if result and result != (False, None, None):
                        has_precip, precip_time, precip_temp = result
                        if has_precip and precip_time:
                            weather_details['precipitation_expected'] = True
                            weather_details['precipitation_time'] = precip_time.isoformat()
                            weather_details['precipitation_temp_f'] = round(precip_temp, 1)
                        else:
                            weather_details['precipitation_expected'] = False
                    else:
                        weather_details['precipitation_expected'] = False
                    
                    weather_details['provider'] = self.config.weather_api.get('provider', 'open-meteo')
                    
                    # Add resilience info
                    if hasattr(self.weather, 'get_state_info'):
                        state_info = self.weather.get_state_info()
                        weather_details['resilience_state'] = state_info.get('state', 'unknown')
                        weather_details['cache_age_hours'] = state_info.get('cache_age_hours')
                    
                except WeatherServiceError as e:
                    self.logger.warning(f"Failed to get weather snapshot for notification: {e}")
                    weather_details['error'] = str(e)
                
                await self.notification_service.notify(
                    event_type="weather_mode_enabled",
                    message="Weather-based scheduling ENABLED with resilience layer",
                    details=weather_details
                )
                self.logger.info("Sent weather mode enabled notification")
            else:
                await self.notification_service.notify(
                    event_type="weather_mode_disabled",
                    message="Weather-based scheduling DISABLED - using fixed schedule behavior",
                    details={'weather_enabled': False}
                )
                self.logger.info("Sent weather mode disabled notification")
        except Exception as e:
            self.logger.warning(f"Failed to send weather mode notification: {e}")
    
    def _get_local_now(self) -> datetime:
        """
        Get current time in the configured timezone.
        
        Returns:
            datetime: Current time in the configured timezone
        """
        return datetime.now(self.timezone)
    
    def validate_schedule(self, schedule: dict) -> tuple[bool, str, str]:
        """
        Validate schedule configuration.
        
        Args:
            schedule: Schedule dictionary with on_time and off_time
            
        Returns:
            Tuple of (is_valid, on_time_str, off_time_str)
        """
        if not schedule:
            return (False, None, None)
        
        on_time_str = schedule.get('on_time')
        off_time_str = schedule.get('off_time')
        
        if not on_time_str or not off_time_str:
            return (False, None, None)
        
        try:
            # Validate format by parsing
            datetime.strptime(on_time_str, "%H:%M")
            datetime.strptime(off_time_str, "%H:%M")
            
            # Optionally log warning if on_time >= off_time (crosses midnight or same)
            on_time = datetime.strptime(on_time_str, "%H:%M").time()
            off_time = datetime.strptime(off_time_str, "%H:%M").time()
            
            if on_time >= off_time:
                self.logger.warning(
                    f"Schedule has on_time >= off_time ({on_time_str} >= {off_time_str}). "
                    "This may cross midnight or be invalid."
                )
            
            return (True, on_time_str, off_time_str)
        except ValueError as e:
            self.logger.error(f"Invalid schedule time format: {e}")
            return (False, None, None)
    
    async def should_turn_on_group(self, group_name: str) -> bool:
        """
        Determine if a device group should be turned on using unified scheduling.
        
        Args:
            group_name: Name of the group to check
            
        Returns:
            True if group should be on, False otherwise
        """
        group_config = self.device_manager.get_group_config(group_name)
        if not group_config:
            self.logger.error(f"Group '{group_name}' not found")
            return False
        
        state = self.states.get(group_name)
        if not state:
            self.logger.error(f"State manager not found for group '{group_name}'")
            return False
        
        # Get local time
        now_local = self._get_local_now()
        
        # Check vacation mode first
        if self.vacation_mode:
            self.logger.info(f"Group '{group_name}': Vacation mode enabled - all schedules disabled")
            return False
        
        # Check if in cooldown
        cooldown_minutes = self.config.safety.get('cooldown_minutes', 30)
        if state.is_in_cooldown(cooldown_minutes):
            self.logger.info(f"Group '{group_name}' in cooldown period")
            return False
        
        # Check if group has new unified schedules
        schedules = self.group_schedules.get(group_name, [])
        if schedules and self.schedule_evaluator:
            # Use unified schedule evaluation
            return await self._should_turn_on_unified(group_name, schedules, now_local)
        else:
            # Fall back to old automation logic for backward compatibility
            self.logger.debug(f"Group '{group_name}': Using legacy automation logic")
            return await self._should_turn_on_legacy(group_name, now_local)
    
    async def _should_turn_on_unified(
        self, 
        group_name: str, 
        schedules: List[Schedule], 
        now_local: datetime
    ) -> bool:
        """
        Unified schedule evaluation logic.
        
        Args:
            group_name: Name of the group
            schedules: List of schedules for the group
            now_local: Current local time
            
        Returns:
            True if any schedule wants device ON
        """
        # Get weather conditions if available
        weather_conditions = None
        weather_offline = False
        
        if self.weather_enabled and self.weather:
            # Check if weather service is offline
            weather_offline = self.weather.is_offline()
            
            if not weather_offline:
                try:
                    conditions = await self.weather.get_current_conditions()
                    if conditions:
                        temp_f, precip_mm = conditions
                        # Check for precipitation in forecast
                        forecast_result = await self.weather.check_precipitation_forecast(
                            hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                            temperature_threshold_f=999  # We'll check temp in schedule conditions
                        )
                        
                        precip_active = False
                        if forecast_result and forecast_result != (False, None, None):
                            has_precip, precip_time, _ = forecast_result
                            # Consider precipitation active if expected within next hour
                            if has_precip and precip_time:
                                time_to_precip = (precip_time - now_local).total_seconds() / 60
                                precip_active = time_to_precip <= 60
                        
                        # Check for black ice risk if enabled
                        black_ice_risk = False
                        raw_config = self._get_raw_config()
                        thresholds = raw_config.get('thresholds', {})
                        black_ice_config = thresholds.get('black_ice_detection', {})
                        
                        if black_ice_config.get('enabled', True):
                            try:
                                black_ice_result = await self.weather.check_black_ice_risk(
                                    hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                                    temperature_max_f=black_ice_config.get('temperature_max_f', 36.0),
                                    dew_point_spread_f=black_ice_config.get('dew_point_spread_f', 4.0),
                                    humidity_min_percent=black_ice_config.get('humidity_min_percent', 80.0)
                                )
                                
                                if black_ice_result and black_ice_result != (False, None, None, None):
                                    has_risk, risk_time, risk_temp, risk_dewpoint = black_ice_result
                                    # Consider black ice risk active if expected within next hour
                                    if has_risk and risk_time:
                                        time_to_risk = (risk_time - now_local).total_seconds() / 60
                                        if time_to_risk <= 60:
                                            black_ice_risk = True
                                            self.logger.info(
                                                f"BLACK ICE RISK DETECTED for group '{group_name}': "
                                                f"temp={risk_temp}°F, dewpoint={risk_dewpoint}°F at {risk_time}"
                                            )
                            except Exception as e:
                                self.logger.warning(f"Failed to check black ice risk: {e}")
                        
                        weather_conditions = {
                            'temperature_f': temp_f,
                            'precipitation_active': precip_active,
                            'black_ice_risk': black_ice_risk
                        }
                except Exception as e:
                    self.logger.warning(f"Failed to get weather conditions: {e}")
        
        # Evaluate schedules
        should_on, winning_schedule, reason = self.schedule_evaluator.should_turn_on(
            schedules,
            now_local,
            weather_conditions,
            weather_offline
        )
        
        if should_on:
            self.logger.info(f"Group '{group_name}': {reason}")
        else:
            self.logger.debug(f"Group '{group_name}': {reason}")
        
        return should_on
    
    async def _should_turn_on_legacy(self, group_name: str, now_local: datetime) -> bool:
        """
        Legacy automation logic for backward compatibility.
        
        Args:
            group_name: Name of the group
            now_local: Current local time
            
        Returns:
            True if legacy automation wants device ON
        """
        group_config = self.device_manager.get_group_config(group_name)
        state = self.states.get(group_name)
        
        base_automation = group_config.get('automation', {})
        automation = self.automation_overrides.get_effective_automation(group_name, base_automation)
        
        # Log effective automation
        self.logger.info(
            f"Group '{group_name}': legacy automation={automation}, "
            f"now_local={now_local.isoformat()} ({self.timezone})"
        )
        
        # Check if thresholds config exists (legacy format)
        thresholds = self.config._config.get('thresholds', {})
        morning_mode_config = self.config._config.get('morning_mode', {})
        
        # Weather-based control
        if automation.get('weather_control', False):
            # Skip weather checks if weather is disabled
            if not self.weather_enabled:
                self.logger.debug(f"Group '{group_name}': Weather control requested but weather is disabled")
                return False
            
            # Morning mode (black ice protection)
            if automation.get('morning_mode', False):
                current_hour = now_local.hour
                
                if morning_mode_config.get('enabled', False):
                    start_hour = morning_mode_config.get('start_hour', 6)
                    end_hour = morning_mode_config.get('end_hour', 8)
                    
                    if start_hour <= current_hour < end_hour:
                        self.logger.info(
                            f"Group '{group_name}': Morning mode active "
                            f"(local hour {current_hour} in window {start_hour}-{end_hour})"
                        )
                        try:
                            conditions = await self.weather.get_current_conditions()
                            if conditions is None:
                                self.logger.warning(
                                    f"Group '{group_name}': Weather data unavailable (fail-safe mode) - "
                                    "morning mode check skipped"
                                )
                            else:
                                temp, _ = conditions
                                morning_temp_threshold = morning_mode_config.get('temperature_f', 
                                                                           thresholds.get('temperature_f', 32))
                                if temp < morning_temp_threshold:
                                    self.logger.info(
                                        f"Group '{group_name}': Temperature {temp}°F below "
                                        f"morning threshold {morning_temp_threshold}°F"
                                    )
                                    return True
                        except WeatherServiceError as e:
                            self.logger.error(f"Failed to get current conditions: {e}")
            
            # Precipitation control
            if automation.get('precipitation_control', False):
                try:
                    result = await self.weather.check_precipitation_forecast(
                        hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                        temperature_threshold_f=thresholds.get('temperature_f', 34)
                    )
                    
                    # Check if result is None or valid tuple
                    if result is None or result == (False, None, None):
                        # No precipitation or weather data unavailable (fail-safe mode)
                        if result is None:
                            self.logger.warning(
                                f"Group '{group_name}': Weather data unavailable (fail-safe mode) - "
                                "precipitation check skipped"
                            )
                    else:
                        has_precip, precip_time, temp = result
                        
                        if has_precip and precip_time:
                            lead_time = timedelta(minutes=thresholds.get('lead_time_minutes', 60))
                            turn_on_time = precip_time - lead_time
                            now = datetime.now(self.timezone)
                            
                            if now >= turn_on_time:
                                self.logger.info(
                                    f"Group '{group_name}': Precipitation expected at {precip_time}, "
                                    f"temperature {temp}°F - turning on"
                                )
                                return True
                            else:
                                self.logger.info(
                                    f"Group '{group_name}': Precipitation expected at {precip_time}, "
                                    f"will turn on at {turn_on_time}"
                                )
                except WeatherServiceError as e:
                    self.logger.error(f"Weather service error: {e}")
        
        # Legacy schedule_control has been removed - use unified schedules: array instead
        # (Any group using old schedule_control should migrate to schedules: array)
        
        return False
    
    async def should_turn_off_group(self, group_name: str) -> bool:
        """
        Determine if a device group should be turned off using unified scheduling.
        
        Args:
            group_name: Name of the group to check
            
        Returns:
            True if group should be off, False otherwise
        """
        group_config = self.device_manager.get_group_config(group_name)
        if not group_config:
            return True  # Turn off if config not found
        
        state = self.states.get(group_name)
        if not state:
            return True  # Turn off if state not found
        
        # Get local time
        now_local = self._get_local_now()
        
        # Check vacation mode - turn off if enabled
        if self.vacation_mode:
            self.logger.info(f"Group '{group_name}': Vacation mode enabled - turning OFF")
            return True
        
        # Check if exceeded max runtime (use schedule-specific or global)
        # For unified schedules, we need to check the winning schedule's max runtime
        schedules = self.group_schedules.get(group_name, [])
        if schedules and self.schedule_evaluator:
            # Get weather conditions to determine which schedule is active
            weather_conditions = None
            weather_offline = False
            
            if self.weather_enabled and self.weather:
                weather_offline = self.weather.is_offline()
                if not weather_offline:
                    try:
                        conditions = await self.weather.get_current_conditions()
                        if conditions:
                            temp_f, precip_mm = conditions
                            forecast_result = await self.weather.check_precipitation_forecast(
                                hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                                temperature_threshold_f=999
                            )
                            precip_active = False
                            if forecast_result and forecast_result != (False, None, None):
                                has_precip, precip_time, _ = forecast_result
                                if has_precip and precip_time:
                                    time_to_precip = (precip_time - now_local).total_seconds() / 60
                                    precip_active = time_to_precip <= 60
                            
                            # Check for black ice risk if enabled
                            black_ice_risk = False
                            raw_config = self._get_raw_config()
                            thresholds = raw_config.get('thresholds', {})
                            black_ice_config = thresholds.get('black_ice_detection', {})
                            
                            if black_ice_config.get('enabled', True):
                                try:
                                    black_ice_result = await self.weather.check_black_ice_risk(
                                        hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                                        temperature_max_f=black_ice_config.get('temperature_max_f', 36.0),
                                        dew_point_spread_f=black_ice_config.get('dew_point_spread_f', 4.0),
                                        humidity_min_percent=black_ice_config.get('humidity_min_percent', 80.0)
                                    )
                                    
                                    if black_ice_result and black_ice_result != (False, None, None, None):
                                        has_risk, risk_time, _, _ = black_ice_result
                                        if has_risk and risk_time:
                                            time_to_risk = (risk_time - now_local).total_seconds() / 60
                                            black_ice_risk = time_to_risk <= 60
                                except Exception as e:
                                    self.logger.warning(f"Failed to check black ice risk: {e}")
                            
                            weather_conditions = {
                                'temperature_f': temp_f,
                                'precipitation_active': precip_active,
                                'black_ice_risk': black_ice_risk
                            }
                    except Exception as e:
                        self.logger.warning(f"Failed to get weather conditions: {e}")
            
            # Check if any schedule wants device on
            should_on, winning_schedule, _ = self.schedule_evaluator.should_turn_on(
                schedules,
                now_local,
                weather_conditions,
                weather_offline
            )
            
            if should_on and winning_schedule:
                # Check max runtime for winning schedule
                max_runtime = winning_schedule.get_max_runtime_hours(
                    self.config.safety.get('max_runtime_hours', 6)
                )
                if state.exceeded_max_runtime(max_runtime):
                    self.logger.warning(
                        f"Group '{group_name}': Maximum runtime exceeded "
                        f"({max_runtime} hours for schedule '{winning_schedule.name}')"
                    )
                    state.start_cooldown()
                    return True
                
                # Schedule still wants device on
                return False
            else:
                # No schedules want device on
                return True
        else:
            # Fall back to legacy logic
            return await self._should_turn_off_legacy(group_name, now_local)
    
    async def _should_turn_off_legacy(self, group_name: str, now_local: datetime) -> bool:
        """
        Legacy turn-off logic for backward compatibility.
        
        Args:
            group_name: Name of the group
            now_local: Current local time
            
        Returns:
            True if legacy automation wants device OFF
        """
        group_config = self.device_manager.get_group_config(group_name)
        state = self.states.get(group_name)
        
        base_automation = group_config.get('automation', {})
        automation = self.automation_overrides.get_effective_automation(group_name, base_automation)
        
        # Check if exceeded max runtime
        max_runtime_hours = self.config.safety.get('max_runtime_hours', 6)
        if state.exceeded_max_runtime(max_runtime_hours):
            self.logger.warning(f"Group '{group_name}': Maximum runtime exceeded")
            state.start_cooldown()
            return True
        
        # Check if thresholds config exists (legacy format)
        thresholds = self.config._config.get('thresholds', {})
        morning_mode_config = self.config._config.get('morning_mode', {})
        
        # Weather-based control
        if automation.get('weather_control', False):
            # Skip weather checks if weather is disabled
            if not self.weather_enabled:
                self.logger.debug(f"Group '{group_name}': Weather control requested but weather is disabled")
                return True  # Turn off if weather control requested but weather disabled
            
            # Check if still in morning mode hours
            if automation.get('morning_mode', False):
                current_hour = now_local.hour
                
                if morning_mode_config.get('enabled', False):
                    start_hour = morning_mode_config.get('start_hour', 6)
                    end_hour = morning_mode_config.get('end_hour', 8)
                    
                    if start_hour <= current_hour < end_hour:
                        try:
                            temp, _ = await self.weather.get_current_conditions()
                            morning_temp_threshold = morning_mode_config.get('temperature_f',
                                                                       thresholds.get('temperature_f', 32))
                            if temp < morning_temp_threshold:
                                return False  # Keep on
                        except WeatherServiceError as e:
                            self.logger.error(f"Failed to get current conditions: {e}")
            
            # Check if precipitation has ended
            if automation.get('precipitation_control', False):
                try:
                    has_precip, precip_time, _ = await self.weather.check_precipitation_forecast(
                        hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                        temperature_threshold_f=thresholds.get('temperature_f', 34)
                    )
                    
                    if not has_precip:
                        trailing_time = timedelta(
                            minutes=thresholds.get('trailing_time_minutes', 60)
                        )
                        if state.device_on and state.turn_on_time:
                            # Ensure turn_on_time is timezone-aware for comparison
                            turn_on_time = state.turn_on_time
                            if turn_on_time.tzinfo is None:
                                # Convert naive datetime to timezone-aware using scheduler's timezone
                                turn_on_time = turn_on_time.replace(tzinfo=self.timezone)
                            
                            time_on = datetime.now(self.timezone) - turn_on_time
                            if time_on >= trailing_time:
                                self.logger.info(
                                    f"Group '{group_name}': No precipitation expected and "
                                    f"trailing time passed ({time_on.total_seconds()/60:.1f} minutes)"
                                )
                                return True
                except WeatherServiceError as e:
                    self.logger.error(f"Weather service error: {e}")
        
        # Legacy schedule_control has been removed - use unified schedules: array instead
        # (Any group using old schedule_control should migrate to schedules: array)
        
        return False
    
    async def _should_schedule_clear_override(self, group_name: str, override_action: str) -> bool:
        """
        Check if a schedule boundary should clear the manual override.
        
        Returns True if we're at a schedule boundary (ON->OFF or OFF->ON transition)
        AND the schedule wants the opposite state from the override.
        
        This ensures overrides are cleared when the schedule naturally transitions,
        but NOT just because a schedule is active with a different desired state.
        
        Args:
            group_name: Name of the device group
            override_action: Current override action ('on' or 'off')
        
        Returns:
            True if override should be cleared due to schedule boundary
        """
        # Get schedules for this group
        schedules = self.group_schedules.get(group_name, [])
        if not schedules:
            return False
        
        # Get current time
        current_time = datetime.now(self.timezone)
        
        # Gather weather conditions if needed
        weather_conditions = None
        weather_offline = False
        
        # Check if any schedules have conditions
        has_conditions = any(schedule.has_conditions() for schedule in schedules)
        
        if has_conditions:
            if self.weather_enabled and self.weather:
                try:
                    weather_offline = self.weather.is_offline()
                    if not weather_offline:
                        conditions = await self.weather.get_current_conditions()
                        if conditions:
                            temp_f, _ = conditions
                            
                            # Check for precipitation in forecast
                            forecast_result = await self.weather.check_precipitation_forecast(
                                hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                                temperature_threshold_f=999  # We'll check temp in schedule conditions
                            )
                            
                            precip_active = False
                            if forecast_result and forecast_result != (False, None, None):
                                has_precip, precip_time, _ = forecast_result
                                # Consider precipitation active if expected within next hour
                                if has_precip and precip_time:
                                    time_to_precip = (precip_time - current_time).total_seconds() / 60
                                    precip_active = time_to_precip <= 60
                            
                            # Check for black ice risk if enabled
                            black_ice_risk = False
                            raw_config = self._get_raw_config()
                            thresholds = raw_config.get('thresholds', {})
                            black_ice_config = thresholds.get('black_ice_detection', {})
                            
                            if black_ice_config.get('enabled', True):
                                try:
                                    black_ice_result = await self.weather.check_black_ice_risk(
                                        hours_ahead=self.config.scheduler.get('forecast_hours', 12),
                                        temperature_max_f=black_ice_config.get('temperature_max_f', 36.0),
                                        dew_point_spread_f=black_ice_config.get('dew_point_spread_f', 4.0),
                                        humidity_min_percent=black_ice_config.get('humidity_min_percent', 80.0)
                                    )
                                    
                                    if black_ice_result and black_ice_result != (False, None, None, None):
                                        has_risk, risk_time, _, _ = black_ice_result
                                        # Consider black ice risk active if expected within next hour
                                        if has_risk and risk_time:
                                            time_to_risk = (risk_time - current_time).total_seconds() / 60
                                            black_ice_risk = time_to_risk <= 60
                                except Exception as e:
                                    self.logger.warning(f"Failed to check black ice risk: {e}")
                            
                            weather_conditions = {
                                'temperature_f': temp_f,
                                'precipitation_active': precip_active,
                                'black_ice_risk': black_ice_risk
                            }
                except Exception as e:
                    self.logger.warning(f"Could not get weather conditions for schedule evaluation: {e}")
                    weather_offline = True
        
        # Evaluate schedules
        should_on, active_schedule, reason = self.schedule_evaluator.should_turn_on(
            schedules=schedules,
            current_time=current_time,
            weather_conditions=weather_conditions,
            weather_offline=weather_offline
        )
        
        # Determine what the schedule wants
        schedule_action = 'on' if should_on else 'off'
        
        # Only clear if schedule wants opposite of override
        if schedule_action != override_action:
            # Check if we're at a schedule boundary by seeing if we were in a different
            # state in the recent past (within the last check interval)
            check_interval = self.config.scheduler.get('check_interval_minutes', 15)
            past_time = current_time - timedelta(minutes=check_interval)
            
            past_should_on, _, _ = self.schedule_evaluator.should_turn_on(
                schedules=schedules,
                current_time=past_time,
                weather_conditions=weather_conditions,
                weather_offline=weather_offline
            )
            
            past_schedule_action = 'on' if past_should_on else 'off'
            
            # We're at a boundary if the schedule's desired state changed
            if past_schedule_action != schedule_action:
                self.logger.info(
                    f"Schedule boundary detected for '{group_name}': "
                    f"{past_schedule_action} -> {schedule_action} (override: {override_action})"
                )
                return True
        
        return False
    
    async def run_cycle_multi_device(self):
        """Run one scheduler cycle for multi-device configuration."""
        self.logger.info("=" * 60)
        self.logger.info("Starting multi-device scheduler cycle")
        self.logger.info("=" * 60)
        
        # Skip in setup mode
        if not self.device_manager:
            self.logger.warning("Device manager not available (setup mode) - skipping cycle")
            return
        
        for group_name in self.device_manager.get_all_groups():
            try:
                self.logger.info(f"Processing group: {group_name}")
                state = self.states[group_name]
                
                # Check for manual override first
                if self.manual_override.is_active(group_name):
                    override_action = self.manual_override.get_action(group_name)
                    override_status = self.manual_override.get_status(group_name)
                    expires_at = override_status.get('expires_at', 'unknown')
                    
                    self.logger.info(f"  Manual override active: {override_action} (expires: {expires_at})")
                    
                    # Check if a schedule boundary should clear the override
                    should_clear = await self._should_schedule_clear_override(group_name, override_action)
                    if should_clear:
                        self.logger.info(f"  Schedule boundary detected - clearing manual override")
                        self.manual_override.clear_override(group_name)
                        # Continue with normal scheduling logic below
                    else:
                        self.logger.info(f"  Skipping automatic scheduling for this group")
                        continue
                
                # Get current group state
                group_is_on = await self.device_manager.get_group_state(group_name)
                self.logger.info(f"  Current state: {'ON' if group_is_on else 'OFF'}")
                
                if group_is_on:
                    # Check if should turn off
                    should_off = await self.should_turn_off_group(group_name)
                    
                    if should_off:
                        self.logger.info(f"  DECISION: Turn OFF group '{group_name}'")
                        await self.device_manager.turn_off_group(group_name)
                        state.mark_turned_off()
                        state.start_cooldown()
                        self.logger.info(f"  ✓ Group '{group_name}' turned OFF")
                    else:
                        runtime_hours = state.get_current_runtime_hours()
                        self.logger.info(f"  DECISION: Keep ON (runtime: {runtime_hours:.2f}h)")
                else:
                    # Check if should turn on
                    should_on = await self.should_turn_on_group(group_name)
                    
                    if should_on:
                        self.logger.info(f"  DECISION: Turn ON group '{group_name}'")
                        await self.device_manager.turn_on_group(group_name)
                        state.mark_turned_on()
                        self.logger.info(f"  ✓ Group '{group_name}' turned ON")
                    else:
                        self.logger.info(f"  DECISION: Keep OFF")
            
            except Exception as e:
                self.logger.error(f"Error processing group '{group_name}': {e}")
                self.logger.exception("Full traceback:")
        
        self.logger.info("Multi-device scheduler cycle completed")
    
    async def _weather_fetch_loop(self):
        """Background task to fetch weather data at regular intervals."""
        from main import shutdown_event
        
        self.logger.info("Weather fetch loop started")
        
        # Initial fetch
        await self.weather.fetch_and_cache_forecast()
        
        try:
            while not shutdown_event.is_set():
                # Get next fetch interval from resilient weather service
                interval_minutes = self.weather.get_next_fetch_interval_minutes()
                interval_seconds = interval_minutes * 60
                
                self.logger.info(f"Next weather fetch in {interval_minutes} minutes")
                
                # Wait for interval or shutdown
                try:
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=interval_seconds
                    )
                    # Shutdown was signaled
                    break
                except asyncio.TimeoutError:
                    # Time to fetch weather
                    pass
                
                # Fetch weather forecast
                success = await self.weather.fetch_and_cache_forecast()
                
                if not success:
                    # Update retry interval with exponential backoff
                    self.weather.update_retry_interval()
                
        except asyncio.CancelledError:
            self.logger.info("Weather fetch loop cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Error in weather fetch loop: {type(e).__name__}: {e}")
            raise
    
    async def get_device_expectations(self):
        """
        Get device expectations for all configured device groups.
        
        Returns a list of device expectation dictionaries showing expected vs actual state.
        This is used by the web UI Health tab to display device health information.
        
        Returns:
            List of dicts with device expectation data
        """
        expectations = []
        
        # Return empty list in setup mode
        if not self.device_manager:
            return expectations
        
        try:
            for group_name in self.device_manager.get_all_groups():
                group_config = self.device_manager.get_group_config(group_name)
                if not group_config:
                    continue
                
                # Get current state
                state = self.states.get(group_name)
                if not state:
                    continue
                
                # Determine expected state based on scheduler logic
                try:
                    should_on = await self.should_turn_on_group(group_name)
                    should_off = await self.should_turn_off_group(group_name)
                    
                    if should_on:
                        expected_state = "on"
                    elif should_off:
                        expected_state = "off"
                    else:
                        # Neither turn on nor turn off triggered, maintain current state
                        expected_state = "on" if state.device_on else "off"
                except Exception as e:
                    self.logger.warning(f"Could not determine expected state for group '{group_name}': {e}")
                    expected_state = "unknown"
                
                # Get actual current state from physical devices
                try:
                    actual_group_state = await self.device_manager.get_group_state(group_name)
                    current_state = "on" if actual_group_state else "off"
                except Exception as e:
                    self.logger.warning(f"Could not get actual device state for group '{group_name}': {e}")
                    # Fallback to state manager if device query fails
                    current_state = "on" if state.device_on else "off"
                
                # Get timing information from unified schedules
                expected_on_from = None
                expected_off_at = None
                
                # Use unified schedules system for timing information
                schedules = self.group_schedules.get(group_name, [])
                if schedules and self.schedule_evaluator:
                    now_local = self._get_local_now()
                    today = now_local.date()
                    
                    # Find the currently active or next active schedule
                    for schedule in schedules:
                        if not schedule.enabled:
                            continue
                        
                        # Check if schedule is for today
                        current_day = now_local.isoweekday()
                        if current_day not in schedule.days:
                            continue
                        
                        try:
                            on_time, off_time = self.schedule_evaluator._get_schedule_times(
                                schedule, today, now_local
                            )
                            
                            if on_time and off_time:
                                # Convert to full datetime objects
                                on_dt = datetime.combine(today, on_time)
                                off_dt = datetime.combine(today, off_time)
                                
                                # Handle day-spanning schedules
                                if off_time < on_time:
                                    # Schedule spans midnight
                                    if now_local.time() >= on_time or now_local.time() < off_time:
                                        expected_on_from = on_dt.isoformat()
                                        expected_off_at = datetime.combine(today + timedelta(days=1), off_time).isoformat()
                                        break
                                else:
                                    # Normal schedule (same day)
                                    if on_time <= now_local.time() < off_time:
                                        expected_on_from = on_dt.isoformat()
                                        expected_off_at = off_dt.isoformat()
                                        break
                                    elif now_local.time() < on_time:
                                        # Schedule is upcoming today
                                        expected_on_from = on_dt.isoformat()
                                        expected_off_at = off_dt.isoformat()
                                        break
                        except Exception as e:
                            self.logger.debug(f"Could not calculate schedule times: {e}")
                
                # Get last state change time
                last_state_change = None
                if state.turn_on_time:
                    last_state_change = state.turn_on_time.isoformat()
                
                # Add expectation for each device in the group
                items = group_config.get('items', [])
                for item in items:
                    # Check if device has multiple outlets
                    outlets = item.get('outlets')
                    
                    if outlets and isinstance(outlets, list):
                        # Create an expectation for each outlet
                        for outlet_index in outlets:
                            # Validate outlet index is a non-negative integer
                            if not isinstance(outlet_index, int) or outlet_index < 0:
                                self.logger.warning(
                                    f"Skipping invalid outlet index {outlet_index} for device "
                                    f"{item.get('name', 'Unknown')} in group {group_name}"
                                )
                                continue
                            device_expectation = {
                                'group': group_name,
                                'device_name': item.get('name', 'Unknown'),
                                'ip_address': item.get('ip_address', 'N/A'),
                                'outlet': outlet_index,
                                'current_state': current_state,
                                'expected_state': expected_state,
                                'expected_on_from': expected_on_from,
                                'expected_off_at': expected_off_at,
                                'last_state_change': last_state_change,
                                'last_error': None  # Could be enhanced to track device errors
                            }
                            expectations.append(device_expectation)
                    else:
                        # Single outlet or entire device
                        device_expectation = {
                            'group': group_name,
                            'device_name': item.get('name', 'Unknown'),
                            'ip_address': item.get('ip_address', 'N/A'),
                            'outlet': item.get('outlet', None),
                            'current_state': current_state,
                            'expected_state': expected_state,
                            'expected_on_from': expected_on_from,
                            'expected_off_at': expected_off_at,
                            'last_state_change': last_state_change,
                            'last_error': None  # Could be enhanced to track device errors
                        }
                        expectations.append(device_expectation)
        
        except Exception as e:
            self.logger.error(f"Error getting device expectations: {e}", exc_info=True)
        
        return expectations
    
    def predict_group_windows(self, horizon_hours: int, step_minutes: int) -> Dict[str, Any]:
        """
        Predict per-group ON/OFF windows over the next horizon_hours, stepping in step_minutes increments.
        
        Uses the unified scheduling system (schedules: array) with ScheduleEvaluator to determine
        whether devices should be on or off at a given time, including:
        - Time-based schedules (clock times and solar times)
        - Weather conditions (temperature thresholds, precipitation)
        - Day-of-week filtering
        - Priority-based conflict resolution
        
        Must NOT talk to devices or external systems.
        Only uses current config, current in-memory weather state, and scheduler-internal helper methods.
        
        Args:
            horizon_hours: Number of hours ahead to predict
            step_minutes: Time step in minutes for prediction granularity
            
        Returns:
            Dictionary with per-group windows: {group_name: [window_dict, ...]}
            Each window has: start, end, state (on/off), reason, details
        """
        if not self.device_manager:
            return {}
        
        result = {}
        now = datetime.now(self.timezone)
        
        try:
            groups = self.device_manager.get_all_groups()
            
            for group_name in groups:
                group_config = self.device_manager.get_group_config(group_name)
                if not group_config or not group_config.get('enabled', True):
                    result[group_name] = []
                    continue
                
                windows = []
                current_window = None
                
                # Step through the time horizon
                for step in range(0, int(horizon_hours * 60 / step_minutes) + 1):
                    check_time = now + timedelta(minutes=step * step_minutes)
                    
                    # Determine if group should be ON at this time
                    should_be_on, reason = self._predict_group_state_at_time(
                        group_name, group_config, check_time
                    )
                    
                    state = "on" if should_be_on else "off"
                    
                    # Coalesce adjacent steps with same state into windows
                    if current_window is None:
                        # Start first window
                        current_window = {
                            'start': check_time.isoformat(),
                            'end': check_time.isoformat(),
                            'state': state,
                            'reason': reason,
                            'details': {}
                        }
                    elif current_window['state'] == state and current_window['reason'] == reason:
                        # Extend current window
                        current_window['end'] = check_time.isoformat()
                    else:
                        # State or reason changed, close current window and start new one
                        windows.append(current_window)
                        current_window = {
                            'start': check_time.isoformat(),
                            'end': check_time.isoformat(),
                            'state': state,
                            'reason': reason,
                            'details': {}
                        }
                
                # Add final window
                if current_window is not None:
                    windows.append(current_window)
                
                result[group_name] = windows
        
        except Exception as e:
            self.logger.error(f"Error predicting group windows: {e}", exc_info=True)
        
        return result
    
    def _predict_group_state_at_time(
        self, group_name: str, group_config: Dict[str, Any], check_time: datetime
    ) -> Tuple[bool, str]:
        """
        Predict if a group should be ON at a given time (synchronous helper for predictions).
        
        Uses the unified scheduling system with ScheduleEvaluator to determine if
        any schedule wants the device ON at the given time.
        
        Args:
            group_name: Name of the group
            group_config: Group configuration dictionary
            check_time: Time to check
            
        Returns:
            Tuple of (should_be_on, reason_string)
        """
        # Check vacation mode first
        if self.vacation_mode:
            return (False, "vacation_mode")
        
        # Check if group has unified schedules
        schedules = self.group_schedules.get(group_name, [])
        
        if schedules and self.schedule_evaluator:
            # Use unified schedule evaluation
            # Get weather conditions from cache if available
            weather_conditions = None
            weather_offline = False
            
            if self.weather_enabled and self.weather:
                # Check if weather service is offline
                weather_offline = self.weather.is_offline() if hasattr(self.weather, 'is_offline') else False
                
                if not weather_offline:
                    try:
                        # Get weather conditions at check_time from cache
                        if hasattr(self.weather, 'cache') and self.weather.cache:
                            snapshot = self.weather.cache.get_weather_at(check_time)
                            if snapshot:
                                # Check for precipitation active (precipitation_mm > 0)
                                precip_active = snapshot.precipitation_mm > 0 if hasattr(snapshot, 'precipitation_mm') else False
                                
                                # Check for black ice risk if enabled
                                black_ice_risk = False
                                try:
                                    # Use helper method to safely access config data
                                    raw_config = self._get_raw_config()
                                    thresholds = raw_config.get('thresholds', {})
                                    black_ice_config = thresholds.get('black_ice_detection', {})
                                    
                                    if black_ice_config.get('enabled', True):
                                        temp = snapshot.temperature_f if hasattr(snapshot, 'temperature_f') else None
                                        dewpoint = snapshot.dewpoint_f if hasattr(snapshot, 'dewpoint_f') else None
                                        humidity = snapshot.humidity_percent if hasattr(snapshot, 'humidity_percent') else None
                                        
                                        if temp is not None and dewpoint is not None and humidity is not None:
                                            temp_max = black_ice_config.get('temperature_max_f', 36.0)
                                            dew_spread_max = black_ice_config.get('dew_point_spread_f', 4.0)
                                            humidity_min = black_ice_config.get('humidity_min_percent', 80.0)
                                            
                                            dew_spread = temp - dewpoint
                                            if temp <= temp_max and dew_spread <= dew_spread_max and humidity >= humidity_min:
                                                black_ice_risk = True
                                except Exception as e:
                                    # Log at debug level to avoid noise, treat as no black ice risk
                                    self.logger.debug(f"Failed to check black ice conditions: {e}")
                                    black_ice_risk = False
                                
                                weather_conditions = {
                                    'temperature_f': snapshot.temperature_f if hasattr(snapshot, 'temperature_f') else None,
                                    'precipitation_active': precip_active,
                                    'black_ice_risk': black_ice_risk
                                }
                    except Exception as e:
                        # Log at debug level to avoid spamming logs in tight loops
                        self.logger.debug(f"Could not get weather at time {check_time}: {e}")
            
            # Evaluate schedules using ScheduleEvaluator
            should_on, winning_schedule, reason = self.schedule_evaluator.should_turn_on(
                schedules,
                check_time,
                weather_conditions,
                weather_offline
            )
            
            if should_on and winning_schedule:
                # Return with the schedule name as the reason
                return (True, f"schedule:{winning_schedule.name}")
            else:
                # No active schedule
                return (False, "no_active_schedule")
        
        # No schedules configured for this group
        return (False, "no_schedules_configured")
    
    def run_coro_in_loop(self, coro):
        """
        Execute a coroutine on the scheduler's event loop from another thread.
        
        This method allows the Flask web server (running in a separate thread) to safely
        execute async python-kasa device operations on the scheduler's event loop.
        All kasa device I/O must run on the same asyncio event loop to avoid runtime errors
        such as "Timeout context manager should be used inside a task" and INTERNAL_QUERY_ERROR.
        
        Args:
            coro: Coroutine to execute on the scheduler's event loop
            
        Returns:
            Result of the coroutine execution
            
        Raises:
            RuntimeError: If the scheduler loop is not initialized
        """
        if self.loop is None:
            raise RuntimeError(
                "Scheduler event loop not initialized. "
                "Ensure the scheduler is running before calling this method."
            )
        
        # Use asyncio.run_coroutine_threadsafe to schedule the coroutine on the scheduler's loop
        # and block until it completes
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()
    
    async def run(self):
        """Run the main scheduler loop."""
        # Capture the running event loop for thread-safe access from web server
        # This allows web server threads to execute async kasa operations on this loop
        self.loop = asyncio.get_running_loop()
        self.logger.info(f"Scheduler event loop initialized: {self.loop}")
        
        await self.initialize()
        
        # In setup mode, run a minimal idle loop
        if self.setup_mode:
            self.logger.warning("=" * 80)
            self.logger.warning("SCHEDULER RUNNING IN SETUP MODE")
            self.logger.warning("=" * 80)
            self.logger.warning("Device control is DISABLED - scheduler will idle")
            self.logger.warning("Web UI is available for configuration")
            self.logger.warning("Once credentials are configured, restart the application")
            self.logger.warning("=" * 80)
            
            # Import shutdown event
            from main import shutdown_event
            
            # Idle loop - just wait for shutdown
            try:
                while not shutdown_event.is_set():
                    await asyncio.sleep(10)
                    # Log periodically to show we're still alive
                    if int(asyncio.get_event_loop().time()) % 300 == 0:
                        self.logger.info("Setup mode active - waiting for credential configuration...")
            finally:
                self.logger.info("Scheduler shutdown (setup mode)")
            
            return
        
        # Start health check service
        await self.health_check.start()
        
        # Start health check HTTP server
        if self.health_server:
            await self.health_server.start()
        
        check_interval = self.config.scheduler['check_interval_minutes'] * 60
        self.logger.info(f"Starting scheduler with {check_interval}s check interval")
        
        # Start weather fetch task if weather is enabled
        weather_task = None
        if self.weather_enabled and self.weather:
            self.logger.info("Starting weather fetch background task...")
            weather_task = asyncio.create_task(self._weather_fetch_loop())
        
        # Import shutdown event from main
        from main import shutdown_event
        
        try:
            while not shutdown_event.is_set():
                # Health check - reinitialize if needed
                if self.health_check.needs_reinitialization():
                    self.logger.warning("Health check recommends re-initialization")
                    try:
                        self.logger.info("Attempting to reinitialize device connections...")
                        
                        # Reinitialize device manager
                        await self.device_manager.close()
                        await self.device_manager.initialize()
                        
                        # Reinitialize state managers for each group
                        state_dir = Path('state')
                        for group_name in self.device_manager.get_all_groups():
                            state_file = state_dir / f"{group_name}.json"
                            self.states[group_name] = StateManager(state_file=str(state_file))
                        
                        self.logger.info("✓ Devices re-initialized successfully")
                        self.health_check.state.consecutive_failures = 0
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="connectivity_restored",
                                message="Device connections re-initialized successfully after health check failures",
                                details=self.health_check.get_status()
                            )
                    except Exception as e:
                        self.logger.error(f"Failed to reinitialize devices: {e}")
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="connectivity_lost",
                                message=f"Failed to reinitialize devices after health check failures: {e}",
                                details=self.health_check.get_status()
                            )
                
                # Run scheduler cycle
                await self.run_cycle_multi_device()
                
                # Wait for next cycle or shutdown
                try:
                    await asyncio.wait_for(
                        shutdown_event.wait(),
                        timeout=check_interval
                    )
                except asyncio.TimeoutError:
                    pass  # Continue to next cycle
        
        finally:
            self.logger.info("Shutting down scheduler...")
            
            # Cancel weather fetch task
            if weather_task and not weather_task.done():
                self.logger.info("Cancelling weather fetch task...")
                weather_task.cancel()
                try:
                    await weather_task
                except asyncio.CancelledError:
                    pass
            
            # Stop health check service
            await self.health_check.stop()
            
            # Stop health check HTTP server
            if self.health_server:
                await self.health_server.stop()
            
            # Close connections
            await self.device_manager.close()
            
            self.logger.info("Scheduler shutdown complete")

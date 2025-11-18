"""Enhanced scheduler supporting multi-device group configurations."""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config_loader import Config
from weather_factory import WeatherServiceFactory
from weather_service import WeatherServiceError
from device_group_manager import DeviceGroupManager
from state_manager import StateManager
from health_check import HealthCheckService
from health_server import HealthCheckServer
from notification_service import (
    validate_and_test_notifications,
    NotificationValidationError
)


logger = logging.getLogger(__name__)


class EnhancedScheduler:
    """
    Enhanced scheduler supporting multi-device groups with weather-based
    and schedule-based automation.
    """
    
    def __init__(self, config: Config):
        """
        Initialize enhanced scheduler.
        
        Args:
            config: Application configuration
        """
        self.config = config
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
        
        # Initialize device management (multi-device mode only)
        self.logger.info("Using multi-device group configuration")
        self.device_manager = DeviceGroupManager(config.devices)
        
        # State management per group
        self.states = {}  # group_name -> StateManager
        
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
        
        # Create weather service now that we have notification service
        if self.weather_enabled:
            self.logger.info("Creating resilient weather service...")
            self.weather = WeatherServiceFactory.create_weather_service(
                self.config._config, 
                notification_service=self.notification_service
            )
            self.logger.info("Weather-based scheduling ENABLED with resilience layer")
        
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
    
    async def should_turn_on_group(self, group_name: str) -> bool:
        """
        Determine if a device group should be turned on.
        
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
        
        automation = group_config.get('automation', {})
        
        # Check if in cooldown
        if state.is_in_cooldown(self.config.safety['cooldown_minutes']):
            self.logger.info(f"Group '{group_name}' in cooldown period")
            return False
        
        # Weather-based control
        if automation.get('weather_control', False):
            # Skip weather checks if weather is disabled
            if not self.weather_enabled:
                self.logger.debug(f"Group '{group_name}': Weather control requested but weather is disabled")
                return False
            
            # Morning mode (black ice protection)
            if automation.get('morning_mode', False):
                current_hour = datetime.now().hour
                morning_mode = self.config.morning_mode
                
                if morning_mode.get('enabled', False):
                    start_hour = morning_mode.get('start_hour', 6)
                    end_hour = morning_mode.get('end_hour', 8)
                    
                    if start_hour <= current_hour < end_hour:
                        self.logger.info(f"Group '{group_name}': Morning mode active")
                        try:
                            conditions = await self.weather.get_current_conditions()
                            if conditions is None:
                                self.logger.warning(
                                    f"Group '{group_name}': Weather data unavailable (fail-safe mode) - "
                                    "morning mode check skipped"
                                )
                            else:
                                temp, _ = conditions
                                morning_temp_threshold = morning_mode.get('temperature_f', 
                                                                           self.config.thresholds['temperature_f'])
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
                        hours_ahead=self.config.scheduler['forecast_hours'],
                        temperature_threshold_f=self.config.thresholds['temperature_f']
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
                            lead_time = timedelta(minutes=self.config.thresholds['lead_time_minutes'])
                            turn_on_time = precip_time - lead_time
                            now = datetime.now()
                            
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
        
        # Schedule-based control
        if automation.get('schedule_control', False):
            schedule = group_config.get('schedule', {})
            if schedule:
                current_time = datetime.now().time()
                
                # Parse on_time and off_time
                on_time_str = schedule.get('on_time')
                off_time_str = schedule.get('off_time')
                
                if on_time_str and off_time_str:
                    try:
                        on_time = datetime.strptime(on_time_str, "%H:%M").time()
                        off_time = datetime.strptime(off_time_str, "%H:%M").time()
                        
                        # Check if current time is within schedule
                        if on_time <= current_time < off_time:
                            self.logger.info(
                                f"Group '{group_name}': Within schedule window "
                                f"({on_time_str} - {off_time_str})"
                            )
                            return True
                    except ValueError as e:
                        self.logger.error(f"Invalid time format in schedule: {e}")
        
        return False
    
    async def should_turn_off_group(self, group_name: str) -> bool:
        """
        Determine if a device group should be turned off.
        
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
        
        automation = group_config.get('automation', {})
        
        # Check if exceeded max runtime
        if state.exceeded_max_runtime(self.config.safety['max_runtime_hours']):
            self.logger.warning(f"Group '{group_name}': Maximum runtime exceeded")
            return True
        
        # Weather-based control
        if automation.get('weather_control', False):
            # Skip weather checks if weather is disabled
            if not self.weather_enabled:
                self.logger.debug(f"Group '{group_name}': Weather control requested but weather is disabled")
                return True  # Turn off if weather control requested but weather disabled
            
            # Check if still in morning mode hours
            if automation.get('morning_mode', False):
                current_hour = datetime.now().hour
                morning_mode = self.config.morning_mode
                
                if morning_mode.get('enabled', False):
                    start_hour = morning_mode.get('start_hour', 6)
                    end_hour = morning_mode.get('end_hour', 8)
                    
                    if start_hour <= current_hour < end_hour:
                        try:
                            temp, _ = await self.weather.get_current_conditions()
                            morning_temp_threshold = morning_mode.get('temperature_f',
                                                                       self.config.thresholds['temperature_f'])
                            if temp < morning_temp_threshold:
                                return False  # Keep on
                        except WeatherServiceError as e:
                            self.logger.error(f"Failed to get current conditions: {e}")
            
            # Check if precipitation has ended
            if automation.get('precipitation_control', False):
                try:
                    has_precip, precip_time, _ = await self.weather.check_precipitation_forecast(
                        hours_ahead=self.config.scheduler['forecast_hours'],
                        temperature_threshold_f=self.config.thresholds['temperature_f']
                    )
                    
                    if not has_precip:
                        trailing_time = timedelta(
                            minutes=self.config.thresholds['trailing_time_minutes']
                        )
                        if state.device_on and state.turn_on_time:
                            time_on = datetime.now() - state.turn_on_time
                            if time_on >= trailing_time:
                                self.logger.info(
                                    f"Group '{group_name}': No precipitation expected and "
                                    f"trailing time passed ({time_on.total_seconds()/60:.1f} minutes)"
                                )
                                return True
                except WeatherServiceError as e:
                    self.logger.error(f"Weather service error: {e}")
        
        # Schedule-based control
        if automation.get('schedule_control', False):
            schedule = group_config.get('schedule', {})
            if schedule:
                current_time = datetime.now().time()
                
                # Parse off_time
                off_time_str = schedule.get('off_time')
                on_time_str = schedule.get('on_time')
                
                if off_time_str and on_time_str:
                    try:
                        off_time = datetime.strptime(off_time_str, "%H:%M").time()
                        on_time = datetime.strptime(on_time_str, "%H:%M").time()
                        
                        # Check if current time is outside schedule
                        if not (on_time <= current_time < off_time):
                            self.logger.info(
                                f"Group '{group_name}': Outside schedule window "
                                f"({on_time_str} - {off_time_str})"
                            )
                            return True
                    except ValueError as e:
                        self.logger.error(f"Invalid time format in schedule: {e}")
        
        return False
    
    async def run_cycle_multi_device(self):
        """Run one scheduler cycle for multi-device configuration."""
        self.logger.info("=" * 60)
        self.logger.info("Starting multi-device scheduler cycle")
        self.logger.info("=" * 60)
        
        for group_name in self.device_manager.get_all_groups():
            try:
                self.logger.info(f"Processing group: {group_name}")
                state = self.states[group_name]
                
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
                
                # Get current state from state manager
                current_state = "on" if state.device_on else "off"
                
                # Get timing information
                expected_on_from = None
                expected_off_at = None
                
                # For schedule-based control, calculate expected times
                automation = group_config.get('automation', {})
                if automation.get('schedule_control', False):
                    schedule = group_config.get('schedule', {})
                    if schedule:
                        on_time_str = schedule.get('on_time')
                        off_time_str = schedule.get('off_time')
                        
                        if on_time_str and off_time_str:
                            try:
                                # Build datetime objects for today
                                today = datetime.now().date()
                                on_time = datetime.combine(today, datetime.strptime(on_time_str, "%H:%M").time())
                                off_time = datetime.combine(today, datetime.strptime(off_time_str, "%H:%M").time())
                                
                                # If we're past the on time today, schedule is for today
                                # If we're before the on time, it's also for today
                                now = datetime.now()
                                if now.time() < on_time.time():
                                    expected_on_from = on_time.isoformat()
                                    expected_off_at = off_time.isoformat()
                                elif on_time.time() <= now.time() < off_time.time():
                                    expected_on_from = on_time.isoformat()
                                    expected_off_at = off_time.isoformat()
                                else:
                                    # Past off time, schedule is for tomorrow
                                    tomorrow = today + timedelta(days=1)
                                    expected_on_from = datetime.combine(tomorrow, on_time.time()).isoformat()
                                    expected_off_at = datetime.combine(tomorrow, off_time.time()).isoformat()
                            except ValueError:
                                pass
                
                # For weather-based control with precipitation, try to estimate times
                if automation.get('weather_control', False) and automation.get('precipitation_control', False):
                    if self.weather_enabled and self.weather:
                        try:
                            result = await self.weather.check_precipitation_forecast(
                                hours_ahead=self.config.scheduler['forecast_hours'],
                                temperature_threshold_f=self.config.thresholds['temperature_f']
                            )
                            
                            if result and result != (False, None, None):
                                has_precip, precip_time, temp = result
                                if has_precip and precip_time:
                                    lead_time = timedelta(minutes=self.config.thresholds['lead_time_minutes'])
                                    turn_on_time = precip_time - lead_time
                                    expected_on_from = turn_on_time.isoformat()
                                    
                                    # Expected off time is trailing time after precipitation ends
                                    trailing_time = timedelta(minutes=self.config.thresholds['trailing_time_minutes'])
                                    expected_off_at = (precip_time + trailing_time).isoformat()
                        except Exception as e:
                            self.logger.debug(f"Could not get weather forecast for expectations: {e}")
                
                # Get last state change time
                last_state_change = None
                if state.turn_on_time:
                    last_state_change = state.turn_on_time.isoformat()
                
                # Add expectation for each device in the group
                items = group_config.get('items', [])
                for item in items:
                    device_expectation = {
                        'group': group_name,
                        'device_name': item.get('name', 'Unknown'),
                        'ip_address': item.get('ip_address', 'N/A'),
                        'outlet': item.get('outlet', 0),
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

"""Enhanced scheduler supporting multi-device group configurations."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from pathlib import Path

from config_loader import Config
from weather_factory import WeatherServiceFactory
from weather_service import WeatherServiceError
from device_group_manager import DeviceGroupManager
from state_manager import StateManager
from health_check import HealthCheckService
from health_server import HealthCheckServer
from notification_service import (
    create_notification_service_from_config,
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
        
        if self.weather_enabled:
            # Create weather service using factory
            self.weather = WeatherServiceFactory.create_weather_service(config._config)
            self.logger.info("Weather-based scheduling ENABLED")
        else:
            self.weather = None
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
        if health_server_config.get('enabled', True):
            self.health_server = HealthCheckServer(
                scheduler=self,
                host=health_server_config.get('host', '0.0.0.0'),
                port=health_server_config.get('port', 8080)
            )
        else:
            self.health_server = None
            self.logger.info("Health check HTTP server disabled")
    
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
                    temp, conditions = await self.weather.get_current_conditions()
                    weather_details['current_temperature_f'] = round(temp, 1)
                    weather_details['current_conditions'] = conditions
                    
                    # Get forecast info
                    has_precip, precip_time, precip_temp = await self.weather.check_precipitation_forecast(
                        hours_ahead=self.config.scheduler['forecast_hours'],
                        temperature_threshold_f=self.config.thresholds['temperature_f']
                    )
                    
                    if has_precip and precip_time:
                        weather_details['precipitation_expected'] = True
                        weather_details['precipitation_time'] = precip_time.isoformat()
                        weather_details['precipitation_temp_f'] = round(precip_temp, 1)
                    else:
                        weather_details['precipitation_expected'] = False
                    
                    weather_details['provider'] = self.config.weather_api.get('provider', 'open-meteo')
                except WeatherServiceError as e:
                    self.logger.warning(f"Failed to get weather snapshot for notification: {e}")
                    weather_details['error'] = str(e)
                
                await self.notification_service.notify(
                    event_type="weather_mode_enabled",
                    message="Weather-based scheduling ENABLED",
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
                            temp, _ = await self.weather.get_current_conditions()
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
                    has_precip, precip_time, temp = await self.weather.check_precipitation_forecast(
                        hours_ahead=self.config.scheduler['forecast_hours'],
                        temperature_threshold_f=self.config.thresholds['temperature_f']
                    )
                    
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
    
    
    async def run(self):
        """Run the main scheduler loop."""
        await self.initialize()
        
        # Start health check service
        await self.health_check.start()
        
        # Start health check HTTP server
        if self.health_server:
            await self.health_server.start()
        
        check_interval = self.config.scheduler['check_interval_minutes'] * 60
        self.logger.info(f"Starting scheduler with {check_interval}s check interval")
        
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
            
            # Stop health check service
            await self.health_check.stop()
            
            # Stop health check HTTP server
            if self.health_server:
                await self.health_server.stop()
            
            # Close connections
            await self.device_manager.close()
            
            self.logger.info("Scheduler shutdown complete")

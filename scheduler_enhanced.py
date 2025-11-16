"""Enhanced scheduler supporting both single device and multi-device group configurations."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from config_loader import Config
from weather_factory import WeatherServiceFactory
from weather_service import WeatherServiceError
from device_controller import TapoController, DeviceControllerError
from device_group_manager import DeviceGroupManager
from state_manager import StateManager
from health_check import HealthCheckService
from notification_service import create_notification_service_from_config


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
        
        # Create weather service using factory
        self.weather = WeatherServiceFactory.create_weather_service(config._config)
        
        # Initialize device management
        if config.has_multi_device_config:
            self.logger.info("Using multi-device group configuration")
            self.mode = "multi-device"
            self.device_manager = DeviceGroupManager(config.devices)
            self.legacy_controller = None
        else:
            self.logger.info("Using legacy single-device configuration")
            self.mode = "legacy"
            self.legacy_controller = TapoController(
                ip_address=config.device['ip_address'],
                username=config.device['username'],
                password=config.device['password']
            )
            self.device_manager = None
        
        # State management per group (or single state for legacy)
        self.states = {}  # group_name -> StateManager
        
        # Initialize notification service
        self.notification_service = create_notification_service_from_config(config.notifications)
        
        # Health check service (legacy mode only)
        if self.mode == "legacy":
            health_check_config = config.health_check
            self.health_check = HealthCheckService(
                check_interval_hours=health_check_config.get('interval_hours', 24),
                configured_ip=config.device['ip_address'],
                notification_service=self.notification_service,
                max_consecutive_failures=health_check_config.get('max_consecutive_failures', 3)
            )
        else:
            self.health_check = None
    
    async def initialize(self):
        """Initialize the scheduler and device connections."""
        self.logger.info("Initializing Enhanced Scheduler...")
        
        try:
            if self.mode == "multi-device":
                await self.device_manager.initialize()
                
                # Initialize state managers for each group
                for group_name in self.device_manager.get_all_groups():
                    self.states[group_name] = StateManager()
                    self.logger.info(f"Initialized state manager for group: {group_name}")
            else:
                await self.legacy_controller.initialize()
                self.states['default'] = StateManager()
                self.logger.info("Initialized state manager for legacy device")
            
            self.logger.info("Scheduler initialized successfully")
        except (DeviceControllerError, Exception) as e:
            self.logger.error(f"Failed to initialize scheduler: {e}")
            raise
    
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
    
    async def run_cycle_legacy(self):
        """Run one scheduler cycle for legacy single-device configuration."""
        # Use the same logic as the original HeatTraxScheduler
        from main import HeatTraxScheduler
        
        # Create temporary scheduler for legacy mode
        legacy_scheduler = HeatTraxScheduler(self.config)
        legacy_scheduler.controller = self.legacy_controller
        legacy_scheduler.state = self.states['default']
        legacy_scheduler.weather = self.weather
        
        await legacy_scheduler.run_cycle()
    
    async def run(self):
        """Run the main scheduler loop."""
        await self.initialize()
        
        # Start health check service (legacy mode only)
        if self.health_check:
            await self.health_check.start()
        
        check_interval = self.config.scheduler['check_interval_minutes'] * 60
        self.logger.info(f"Starting scheduler with {check_interval}s check interval")
        
        # Import shutdown event from main
        from main import shutdown_event
        
        try:
            while not shutdown_event.is_set():
                # Health check for legacy mode
                if self.health_check and self.health_check.needs_reinitialization():
                    self.logger.warning("Health check recommends re-initialization")
                    try:
                        await self.legacy_controller.close()
                        await self.legacy_controller.initialize()
                        self.logger.info("✓ Device re-initialized successfully")
                        self.health_check.state.consecutive_failures = 0
                    except Exception as e:
                        self.logger.error(f"Failed to reinitialize device: {e}")
                
                # Run appropriate cycle
                if self.mode == "multi-device":
                    await self.run_cycle_multi_device()
                else:
                    await self.run_cycle_legacy()
                
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
            if self.health_check:
                await self.health_check.stop()
            
            # Close connections
            if self.mode == "multi-device":
                await self.device_manager.close()
            else:
                await self.legacy_controller.close()
            
            self.logger.info("Scheduler shutdown complete")

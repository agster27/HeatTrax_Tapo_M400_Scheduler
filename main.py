"""Main scheduler application for HeatTrax Tapo M400."""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config_loader import Config, ConfigError
from weather_service import WeatherService, WeatherServiceError
from device_controller import TapoController, DeviceControllerError
from state_manager import StateManager
from startup_checks import run_startup_checks
from device_discovery import run_device_discovery_and_diagnostics
from health_check import HealthCheckService
from notification_service import create_notification_service_from_config


# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


def setup_logging(config: Config):
    """Set up rotating file logging."""
    log_config = config.logging_config
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    
    # Create logs directory
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Rotating file handler
    max_bytes = log_config.get('max_file_size_mb', 10) * 1024 * 1024
    backup_count = log_config.get('backup_count', 5)
    
    file_handler = RotatingFileHandler(
        log_dir / 'heattrax_scheduler.log',
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    logging.info("Logging initialized")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


class HeatTraxScheduler:
    """Main scheduler for controlling heated mats based on weather."""
    
    def __init__(self, config: Config):
        """
        Initialize scheduler.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.weather = WeatherService(
            latitude=config.location['latitude'],
            longitude=config.location['longitude'],
            timezone=config.location.get('timezone', 'auto')
        )
        self.controller = TapoController(
            ip_address=config.device['ip_address'],
            username=config.device['username'],
            password=config.device['password']
        )
        self.state = StateManager()
        self.logger = logging.getLogger(__name__)
        
        # Initialize notification service
        self.notification_service = create_notification_service_from_config(config.notifications)
        
        # Initialize health check service
        health_check_config = config.health_check
        self.health_check = HealthCheckService(
            check_interval_hours=health_check_config.get('interval_hours', 24),
            configured_ip=config.device['ip_address'],
            notification_service=self.notification_service,
            max_consecutive_failures=health_check_config.get('max_consecutive_failures', 3)
        )
    
    async def initialize(self):
        """Initialize the scheduler and device connection."""
        self.logger.info("Initializing HeatTrax Scheduler...")
        try:
            await self.controller.initialize()
            self.logger.info("Scheduler initialized successfully")
        except DeviceControllerError as e:
            self.logger.error(f"Failed to initialize device controller: {e}")
            raise
    
    async def should_turn_on(self) -> bool:
        """
        Determine if device should be turned on based on weather and conditions.
        
        Returns:
            True if device should be on, False otherwise
        """
        # Check if in cooldown
        if self.state.is_in_cooldown(self.config.safety['cooldown_minutes']):
            self.logger.info("Device in cooldown period, cannot turn on")
            return False
        
        # Check morning mode
        current_hour = datetime.now().hour
        morning_mode = self.config.morning_mode
        if morning_mode.get('enabled', False):
            start_hour = morning_mode.get('start_hour', 6)
            end_hour = morning_mode.get('end_hour', 8)
            
            if start_hour <= current_hour < end_hour:
                self.logger.info("Morning frost-clearing mode active")
                # Check temperature only
                try:
                    temp, _ = await self.weather.get_current_conditions()
                    if temp < self.config.thresholds['temperature_f']:
                        self.logger.info(
                            f"Morning mode: Temperature {temp}°F below threshold "
                            f"{self.config.thresholds['temperature_f']}°F"
                        )
                        return True
                except WeatherServiceError as e:
                    self.logger.error(f"Failed to get current conditions: {e}")
        
        # Check precipitation forecast
        try:
            has_precip, precip_time, temp = await self.weather.check_precipitation_forecast(
                hours_ahead=self.config.scheduler['forecast_hours'],
                temperature_threshold_f=self.config.thresholds['temperature_f']
            )
            
            if has_precip and precip_time:
                # Check if we should turn on based on lead time
                lead_time = timedelta(minutes=self.config.thresholds['lead_time_minutes'])
                turn_on_time = precip_time - lead_time
                now = datetime.now()
                
                if now >= turn_on_time:
                    self.logger.info(
                        f"Precipitation expected at {precip_time}, "
                        f"temperature {temp}°F - turning on"
                    )
                    return True
                else:
                    self.logger.info(
                        f"Precipitation expected at {precip_time}, "
                        f"will turn on at {turn_on_time}"
                    )
            
        except WeatherServiceError as e:
            self.logger.error(f"Weather service error: {e}")
        
        return False
    
    async def should_turn_off(self) -> bool:
        """
        Determine if device should be turned off.
        
        Returns:
            True if device should be off, False otherwise
        """
        # Check if exceeded max runtime
        if self.state.exceeded_max_runtime(self.config.safety['max_runtime_hours']):
            self.logger.warning("Maximum runtime exceeded, turning off for safety")
            return True
        
        # Check if still in morning mode hours
        current_hour = datetime.now().hour
        morning_mode = self.config.morning_mode
        if morning_mode.get('enabled', False):
            start_hour = morning_mode.get('start_hour', 6)
            end_hour = morning_mode.get('end_hour', 8)
            
            if start_hour <= current_hour < end_hour:
                # Still in morning mode, check temperature
                try:
                    temp, _ = await self.weather.get_current_conditions()
                    if temp < self.config.thresholds['temperature_f']:
                        return False  # Keep on
                except WeatherServiceError as e:
                    self.logger.error(f"Failed to get current conditions: {e}")
        
        # Check if precipitation has ended
        try:
            has_precip, precip_time, _ = await self.weather.check_precipitation_forecast(
                hours_ahead=self.config.scheduler['forecast_hours'],
                temperature_threshold_f=self.config.thresholds['temperature_f']
            )
            
            if not has_precip:
                # No precipitation expected, check trailing time
                trailing_time = timedelta(
                    minutes=self.config.thresholds['trailing_time_minutes']
                )
                # If device has been on for at least the trailing time, turn off
                if self.state.device_on and self.state.turn_on_time:
                    time_on = datetime.now() - self.state.turn_on_time
                    if time_on >= trailing_time:
                        self.logger.info(
                            f"No precipitation expected and trailing time passed "
                            f"({time_on.total_seconds()/60:.1f} minutes), turning off"
                        )
                        return True
        except WeatherServiceError as e:
            self.logger.error(f"Weather service error: {e}")
        
        return False
    
    async def run_cycle(self):
        """Run one scheduler cycle."""
        try:
            self.logger.info("=" * 60)
            self.logger.info("Starting scheduler cycle")
            self.logger.info("=" * 60)
            
            # Get current device state
            self.logger.info("Checking current device state...")
            device_is_on = await self.controller.get_state()
            self.logger.info(f"Current device state: {'ON' if device_is_on else 'OFF'}")
            
            if device_is_on:
                # Device is on, check if it should turn off
                self.logger.info("Device is ON - evaluating if it should turn OFF")
                should_off = await self.should_turn_off()
                
                if should_off:
                    self.logger.info("DECISION: Device should turn OFF")
                    await self.controller.turn_off()
                    self.state.mark_turned_off()
                    self.state.start_cooldown()
                    self.logger.info("Device turned OFF and cooldown started")
                else:
                    runtime_hours = self.state.get_current_runtime_hours()
                    self.logger.info(f"DECISION: Device should stay ON")
                    self.logger.info(f"Current runtime: {runtime_hours:.2f} hours")
            else:
                # Device is off, check if it should turn on
                self.logger.info("Device is OFF - evaluating if it should turn ON")
                should_on = await self.should_turn_on()
                
                if should_on:
                    self.logger.info("DECISION: Device should turn ON")
                    await self.controller.turn_on()
                    self.state.mark_turned_on()
                    self.logger.info("Device turned ON and state recorded")
                else:
                    self.logger.info("DECISION: Device should stay OFF")
            
            self.logger.info("Scheduler cycle completed successfully")
            
        except DeviceControllerError as e:
            self.logger.error(f"Device controller error in scheduler cycle: {e}")
            self.logger.error("Will retry on next cycle")
        except WeatherServiceError as e:
            self.logger.error(f"Weather service error in scheduler cycle: {e}")
            self.logger.error("Will retry on next cycle")
        except Exception as e:
            self.logger.error(f"Unexpected error in scheduler cycle: {type(e).__name__}: {e}")
            self.logger.exception("Full traceback:")
            self.logger.error("Will retry on next cycle")
    
    async def run(self):
        """Run the main scheduler loop."""
        await self.initialize()
        
        # Start health check service
        await self.health_check.start()
        
        check_interval = self.config.scheduler['check_interval_minutes'] * 60
        self.logger.info(f"Starting scheduler with {check_interval}s check interval")
        
        try:
            while not shutdown_event.is_set():
                # Check if health check recommends re-initialization
                if self.health_check.needs_reinitialization():
                    self.logger.warning("Health check recommends re-initialization")
                    
                    # Attempt to reinitialize device connection
                    try:
                        self.logger.info("Attempting to reinitialize device connection...")
                        await self.controller.close()
                        await self.controller.initialize()
                        self.logger.info("✓ Device re-initialized successfully")
                        
                        # Reset health check state
                        self.health_check.state.consecutive_failures = 0
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="connectivity_restored",
                                message="Device connection re-initialized successfully after health check failures",
                                details=self.health_check.get_status()
                            )
                    except Exception as e:
                        self.logger.error(f"Failed to reinitialize device: {e}")
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="connectivity_lost",
                                message=f"Failed to reinitialize device after health check failures: {e}",
                                details=self.health_check.get_status()
                            )
                
                await self.run_cycle()
                
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
            
            # Ensure device is off on shutdown (optional, can be removed if you want device to stay in current state)
            # await self.controller.turn_off()
            await self.controller.close()
            self.logger.info("Scheduler shutdown complete")


async def main():
    """Main entry point for the application."""
    # Run startup sanity checks FIRST (before logging or config)
    # This provides maximum diagnostic value for containerized deployments
    config_path = os.environ.get('HEATTRAX_CONFIG_PATH', 'config.yaml')
    
    # Run checks - get device IP from environment for connectivity test if available
    device_ip = os.environ.get('HEATTRAX_TAPO_IP_ADDRESS')
    
    startup_ok = run_startup_checks(config_path=config_path, device_ip=device_ip)
    if not startup_ok:
        print("\nERROR: Critical startup checks failed. Exiting.", file=sys.stderr)
        sys.exit(1)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Load configuration
        config = Config()
        
        # Set up logging
        setup_logging(config)
        
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info("HeatTrax Tapo M400 Scheduler Starting")
        logger.info("=" * 60)
        
        # Run device discovery and diagnostics
        logger.info("\n" + "=" * 80)
        logger.info("DEVICE AUTO-DISCOVERY AND DIAGNOSTICS")
        logger.info("=" * 80)
        configured_ip = config.device.get('ip_address')
        discovered_device = await run_device_discovery_and_diagnostics(configured_ip)
        logger.info("")  # Blank line for readability
        
        # Create and run scheduler
        scheduler = HeatTraxScheduler(config)
        await scheduler.run()
        
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

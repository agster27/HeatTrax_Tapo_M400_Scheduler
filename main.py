"""Main scheduler application for HeatTrax Tapo M400."""

import asyncio
import logging
import signal
import sys
import os
import time
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config_loader import Config, ConfigError
from config_manager import ConfigManager
from startup_checks import run_startup_checks
from scheduler_enhanced import EnhancedScheduler
from web_server import WebServer
from version import __version__


# Global flag for graceful shutdown
shutdown_event = asyncio.Event()
scheduler_thread = None


def pause_before_restart(pause_seconds: int, reason: str):
    """
    Pause before container restart to allow console troubleshooting.
    
    Args:
        pause_seconds: Number of seconds to pause
        reason: Reason for the restart (for logging)
    """
    if pause_seconds <= 0:
        return
    
    logger = logging.getLogger(__name__)
    logger.critical("=" * 80)
    logger.critical("CONTAINER RESTART SEQUENCE INITIATED")
    logger.critical("=" * 80)
    logger.critical(f"Reason: {reason}")
    logger.critical(f"Pausing for {pause_seconds} seconds to allow console troubleshooting...")
    logger.critical(f"The container will restart automatically after the pause.")
    logger.critical("=" * 80)
    
    # Also print to console to ensure visibility
    print("\n" + "=" * 80, file=sys.stderr)
    print("CONTAINER RESTART SEQUENCE INITIATED", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Reason: {reason}", file=sys.stderr)
    print(f"Pausing for {pause_seconds} seconds to allow console troubleshooting...", file=sys.stderr)
    print(f"The container will restart automatically after the pause.", file=sys.stderr)
    print("=" * 80 + "\n", file=sys.stderr)
    
    # Countdown every 10 seconds for visibility
    remaining = pause_seconds
    while remaining > 0:
        if remaining % 10 == 0 or remaining <= 5:
            logger.warning(f"Container restart in {remaining} seconds...")
            print(f"Container restart in {remaining} seconds...", file=sys.stderr)
        time.sleep(1)
        remaining -= 1
    
    logger.critical("Pause complete. Exiting to trigger container restart.")
    print("Pause complete. Exiting to trigger container restart.\n", file=sys.stderr)


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


def run_scheduler_thread(scheduler: EnhancedScheduler):
    """
    Run scheduler in a separate thread.
    
    Args:
        scheduler: EnhancedScheduler instance to run
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the scheduler
        loop.run_until_complete(scheduler.run())
        
    except Exception as e:
        logger.error(f"Fatal error in scheduler thread: {e}", exc_info=True)
        shutdown_event.set()
    finally:
        logger.info("Scheduler thread exiting")


async def main():
    """Main entry point for the application."""
    # Run startup sanity checks FIRST (before logging or config)
    # This provides maximum diagnostic value for containerized deployments
    config_path = os.environ.get('HEATTRAX_CONFIG_PATH', '/app/config.yaml')
    
    # Get pause seconds from environment variable (for use before config is loaded)
    pause_seconds_env = os.environ.get('HEATTRAX_REBOOT_PAUSE_SECONDS', '60')
    try:
        pause_seconds = int(pause_seconds_env)
    except ValueError:
        pause_seconds = 60  # Default to 60 if invalid
    
    startup_ok = run_startup_checks(config_path=config_path, device_ip=None)
    if not startup_ok:
        print("\nERROR: Critical startup checks failed. Exiting.", file=sys.stderr)
        pause_before_restart(pause_seconds, "Critical startup checks failed")
        sys.exit(1)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize ConfigManager (new approach)
        config_manager = ConfigManager(config_path)
        
        # Also create Config object for compatibility with existing code
        config = Config(config_path)
        
        # Get pause_seconds from config (may override environment variable)
        pause_seconds = config.reboot.get('pause_seconds', pause_seconds)
        
        # Set up logging
        setup_logging(config)
        
        logger = logging.getLogger(__name__)
        logger.info("=" * 60)
        logger.info(f"HeatTrax Tapo M400 Scheduler v{__version__}")
        logger.info("=" * 60)
        logger.info(f"Reboot pause configured: {pause_seconds} seconds")
        
        # Multi-device configuration
        logger.info("\n" + "=" * 80)
        logger.info("MULTI-DEVICE CONFIGURATION")
        logger.info("=" * 80)
        devices_config = config.devices
        groups = devices_config.get('groups', {})
        
        enabled_groups = [name for name, cfg in groups.items() if cfg.get('enabled', True)]
        logger.info(f"Found {len(groups)} groups, {len(enabled_groups)} enabled:")
        
        for group_name in enabled_groups:
            group_cfg = groups[group_name]
            items = group_cfg.get('items', [])
            logger.info(f"  - {group_name}: {len(items)} devices")
        
        logger.info("Device connections will be established during initialization")
        
        # Check if web UI is enabled
        web_config = config_manager.get_config(include_secrets=False).get('web', {})
        web_enabled = web_config.get('enabled', True)
        
        # Check for environment override
        if os.environ.get('HEATTRAX_WEB_ENABLED'):
            web_enabled = os.environ['HEATTRAX_WEB_ENABLED'].lower() in ('true', '1', 'yes', 'on')
        
        if not web_enabled:
            logger.info("=" * 80)
            logger.info("WEB UI DISABLED")
            logger.info("=" * 80)
            logger.info("Running in scheduler-only mode")
            
            # Run scheduler directly without web UI
            scheduler = EnhancedScheduler(config)
            await scheduler.run()
        else:
            logger.info("=" * 80)
            logger.info("STARTING WEB UI AND SCHEDULER")
            logger.info("=" * 80)
            
            # Get web server configuration
            bind_host = web_config.get('bind_host', '127.0.0.1')
            port = web_config.get('port', 4328)
            
            logger.info(f"Web UI will be available at http://{bind_host}:{port}")
            
            # Create scheduler (will run in separate thread)
            scheduler = EnhancedScheduler(config)
            
            # Create web server
            web_server = WebServer(config_manager, scheduler)
            
            # Start scheduler in a separate thread
            global scheduler_thread
            scheduler_thread = threading.Thread(
                target=run_scheduler_thread,
                args=(scheduler,),
                daemon=False,
                name="SchedulerThread"
            )
            scheduler_thread.start()
            logger.info("Scheduler thread started")
            
            # Run web server in main thread (blocking)
            logger.info("Starting web server (main thread)...")
            try:
                web_server.run(host=bind_host, port=port, debug=False)
            except KeyboardInterrupt:
                logger.info("Web server interrupted")
            finally:
                shutdown_event.set()
                logger.info("Waiting for scheduler thread to complete...")
                if scheduler_thread:
                    scheduler_thread.join(timeout=10)
                logger.info("Shutdown complete")
        
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        pause_before_restart(pause_seconds, f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        pause_before_restart(pause_seconds, f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

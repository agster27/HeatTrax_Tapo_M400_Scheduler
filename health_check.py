"""Periodic health check system for device monitoring."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from device_discovery import discover_devices, DeviceInfo, get_local_ip_and_subnet, is_ip_in_same_subnet
from notification_service import NotificationService

logger = logging.getLogger(__name__)


class HealthCheckState:
    """Track health check state."""
    
    def __init__(self):
        """Initialize health check state."""
        self.last_check_time: Optional[datetime] = None
        self.last_known_devices: Dict[str, DeviceInfo] = {}
        self.consecutive_failures: int = 0
        self.configured_ips: Dict[str, str] = {}  # IP -> label/group mapping
        self.configured_device_last_seen: Dict[str, datetime] = {}  # IP -> last seen time


class HealthCheckService:
    """Service for periodic health checks of devices."""
    
    def __init__(self, check_interval_hours: float, configured_ips: list = None,
                 notification_service: Optional[NotificationService] = None,
                 max_consecutive_failures: int = 3):
        """
        Initialize health check service.
        
        Args:
            check_interval_hours: Hours between health checks
            configured_ips: List of configured device IP addresses
            notification_service: Optional notification service for alerts
            max_consecutive_failures: Maximum consecutive failures before triggering re-init
        """
        self.check_interval_hours = check_interval_hours
        self.configured_ips_list = configured_ips or []
        self.notification_service = notification_service
        self.max_consecutive_failures = max_consecutive_failures
        
        self.state = HealthCheckState()
        # Initialize configured IPs mapping (IP -> IP as label for now)
        for ip in self.configured_ips_list:
            self.state.configured_ips[ip] = ip
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        logger.info(f"Health check service initialized: interval={check_interval_hours}h, "
                   f"configured_devices={len(self.configured_ips_list)}, max_failures={max_consecutive_failures}")
        if self.configured_ips_list:
            logger.debug(f"Monitoring devices: {', '.join(self.configured_ips_list)}")
    
    async def start(self):
        """Start the health check background task."""
        if self._running:
            logger.warning("Health check service already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._health_check_loop())
        logger.info("Health check service started")
    
    async def stop(self):
        """Stop the health check background task."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health check service stopped")
    
    async def _health_check_loop(self):
        """Background loop for periodic health checks."""
        logger.info(f"Health check loop started (interval: {self.check_interval_hours} hours)")
        
        # Wait for the first check interval
        await asyncio.sleep(self.check_interval_hours * 3600)
        
        while self._running:
            try:
                await self.run_health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check failed with exception: {type(e).__name__}: {e}")
                logger.exception("Full traceback:")
            
            # Wait for next check
            try:
                await asyncio.sleep(self.check_interval_hours * 3600)
            except asyncio.CancelledError:
                break
    
    async def run_health_check(self) -> bool:
        """
        Run a health check.
        
        Returns:
            True if health check passed, False if issues detected
        """
        logger.info("\n" + "=" * 60)
        logger.info(f"PERIODIC HEALTH CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        self.state.last_check_time = datetime.now()
        
        # Get local network information for subnet diagnostics
        local_info = get_local_ip_and_subnet()
        if local_info:
            local_ip, subnet_cidr = local_info
            logger.debug(f"Local network: {local_ip} (subnet: {subnet_cidr})")
        
        # Discover devices
        devices = await discover_devices(timeout=10)
        
        if not devices:
            logger.warning("⚠ No devices found during health check!")
            
            # Check if any configured IPs are outside subnet
            if self.state.configured_ips and local_info:
                local_ip, subnet_cidr = local_info
                cross_subnet_ips = []
                for ip in self.state.configured_ips.keys():
                    if not is_ip_in_same_subnet(ip, local_ip, subnet_cidr):
                        cross_subnet_ips.append(ip)
                
                if cross_subnet_ips:
                    logger.debug(f"Configured devices outside subnet: {', '.join(cross_subnet_ips)}")
                    logger.debug(f"Cross-subnet discovery limitation - relying on static configuration")
            
            self.state.consecutive_failures += 1
            
            # Notify if configured devices are missing
            for ip, label in self.state.configured_ips.items():
                if self.notification_service:
                    last_seen = self.state.configured_device_last_seen.get(ip)
                    await self.notification_service.notify(
                        event_type="device_lost",
                        message=f"Configured device at {ip} not found during health check",
                        details={
                            'ip': ip,
                            'label': label,
                            'consecutive_failures': self.state.consecutive_failures,
                            'last_seen': last_seen.isoformat() if last_seen else 'Never'
                        }
                    )
            
            # Check if we need to trigger re-initialization
            if self.state.consecutive_failures >= self.max_consecutive_failures:
                logger.error(f"✗ CRITICAL: {self.state.consecutive_failures} consecutive health check failures!")
                logger.error("  Consider restarting the scheduler or checking device connectivity")
                logger.error("\n  RECOVERY SUGGESTIONS:")
                logger.error("    1. Verify devices are powered on and connected to network")
                logger.error("    2. Check firewall settings (UDP port 9999 for discovery)")
                logger.error("    3. Verify device IPs haven't changed (check DHCP assignments)")
                return False
            
            return False
        
        # Reset consecutive failures if we found devices
        if self.state.consecutive_failures > 0:
            logger.info(f"✓ Health check recovered after {self.state.consecutive_failures} failure(s)")
            self.state.consecutive_failures = 0
        
        # Create device map for comparison
        current_devices = {device.ip: device for device in devices}
        
        # Check for new devices
        for ip, device in current_devices.items():
            if ip not in self.state.last_known_devices:
                logger.info(f"✓ New device discovered: {device.alias} at {ip}")
                
                if self.notification_service:
                    await self.notification_service.notify(
                        event_type="device_found",
                        message=f"New device discovered: {device.alias} at {ip}",
                        details=device.to_dict()
                    )
        
        # Check for missing devices
        for ip, device in self.state.last_known_devices.items():
            if ip not in current_devices:
                logger.warning(f"⚠ Device no longer found: {device.alias} at {ip}")
                
                if self.notification_service:
                    await self.notification_service.notify(
                        event_type="device_lost",
                        message=f"Device no longer found: {device.alias} at {ip}",
                        details=device.to_dict()
                    )
        
        # Check configured devices
        for configured_ip, label in self.state.configured_ips.items():
            if configured_ip in current_devices:
                configured_device = current_devices[configured_ip]
                self.state.configured_device_last_seen[configured_ip] = datetime.now()
                
                logger.info(f"✓ Configured device OK: {configured_device.alias} at {configured_ip} ({label})")
                
                # Check if alias changed
                if configured_ip in self.state.last_known_devices:
                    old_device = self.state.last_known_devices[configured_ip]
                    if old_device.alias != configured_device.alias:
                        logger.warning(
                            f"⚠ Device alias changed at {configured_ip}: {old_device.alias} -> {configured_device.alias}"
                        )
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="device_changed",
                                message=f"Device alias changed at {configured_ip} ({label})",
                                details={
                                    'ip': configured_ip,
                                    'label': label,
                                    'old_alias': old_device.alias,
                                    'new_alias': configured_device.alias,
                                }
                            )
                    
                    # Check if MAC changed (IP might have been reassigned)
                    if old_device.mac != configured_device.mac:
                        logger.warning(
                            f"⚠ CRITICAL: MAC address changed at {configured_ip}! "
                            f"IP may have been reassigned to a different device!"
                        )
                        logger.warning(f"  Old MAC: {old_device.mac} ({old_device.alias})")
                        logger.warning(f"  New MAC: {configured_device.mac} ({configured_device.alias})")
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="device_ip_changed",
                                message=f"CRITICAL: MAC address changed at {configured_ip} ({label})! IP may have been reassigned!",
                                details={
                                    'ip': configured_ip,
                                    'label': label,
                                    'old_mac': old_device.mac,
                                    'new_mac': configured_device.mac,
                                    'old_alias': old_device.alias,
                                    'new_alias': configured_device.alias,
                                }
                            )
                
            else:
                logger.warning(f"⚠ Configured device not found at {configured_ip} ({label})")
                
                # Check if this is expected due to subnet limitations
                if local_info:
                    local_ip, subnet_cidr = local_info
                    if not is_ip_in_same_subnet(configured_ip, local_ip, subnet_cidr):
                        logger.debug(f"  Device at {configured_ip} is outside local subnet - this may be expected")
                
                # Check if device moved to a different IP
                configured_mac = None
                if configured_ip in self.state.last_known_devices:
                    configured_mac = self.state.last_known_devices[configured_ip].mac
                
                found_at_different_ip = False
                if configured_mac:
                    for ip, device in current_devices.items():
                        if device.mac == configured_mac:
                            logger.warning(
                                f"  ✓ FOUND: Device from {configured_ip} ({label}) moved to {ip}!"
                            )
                            logger.warning(f"    Device: {device.alias} (MAC: {device.mac})")
                            logger.warning(f"    Update configuration for this device")
                            found_at_different_ip = True
                            
                            if self.notification_service:
                                await self.notification_service.notify(
                                    event_type="device_ip_changed",
                                    message=f"Configured device moved from {configured_ip} to {ip} ({label})",
                                    details={
                                        'old_ip': configured_ip,
                                        'new_ip': ip,
                                        'label': label,
                                        'mac': device.mac,
                                        'alias': device.alias,
                                    }
                                )
                            break

        
        # Update last known devices
        self.state.last_known_devices = current_devices
        
        logger.info("=" * 60)
        logger.info(f"Health check completed - {len(devices)} device(s) found")
        logger.info("=" * 60 + "\n")
        
        return True
    
    def needs_reinitialization(self) -> bool:
        """
        Check if the scheduler needs re-initialization due to health check failures.
        
        Returns:
            True if re-initialization is recommended
        """
        return self.state.consecutive_failures >= self.max_consecutive_failures
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get health check status.
        
        Returns:
            Dictionary with health check status information
        """
        # Build configured device status
        configured_device_status = {}
        for ip, label in self.state.configured_ips.items():
            last_seen = self.state.configured_device_last_seen.get(ip)
            configured_device_status[ip] = {
                'label': label,
                'last_seen': last_seen.isoformat() if last_seen else None
            }
        
        return {
            'last_check_time': self.state.last_check_time.isoformat() if self.state.last_check_time else None,
            'consecutive_failures': self.state.consecutive_failures,
            'known_devices_count': len(self.state.last_known_devices),
            'configured_devices': configured_device_status,
            'needs_reinitialization': self.needs_reinitialization(),
        }

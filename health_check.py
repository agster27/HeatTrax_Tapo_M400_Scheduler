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
        self.configured_ip: Optional[str] = None
        self.configured_device_last_seen: Optional[datetime] = None


class HealthCheckService:
    """Service for periodic health checks of devices."""
    
    def __init__(self, check_interval_hours: float, configured_ip: Optional[str] = None,
                 notification_service: Optional[NotificationService] = None,
                 max_consecutive_failures: int = 3):
        """
        Initialize health check service.
        
        Args:
            check_interval_hours: Hours between health checks
            configured_ip: The configured device IP address
            notification_service: Optional notification service for alerts
            max_consecutive_failures: Maximum consecutive failures before triggering re-init
        """
        self.check_interval_hours = check_interval_hours
        self.configured_ip = configured_ip
        self.notification_service = notification_service
        self.max_consecutive_failures = max_consecutive_failures
        
        self.state = HealthCheckState()
        self.state.configured_ip = configured_ip
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        logger.info(f"Health check service initialized: interval={check_interval_hours}h, "
                   f"configured_ip={configured_ip}, max_failures={max_consecutive_failures}")
    
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
            
            # Check if configured IP is outside subnet
            if self.configured_ip and local_info:
                local_ip, subnet_cidr = local_info
                if not is_ip_in_same_subnet(self.configured_ip, local_ip, subnet_cidr):
                    logger.warning(f"\n⚠ SUBNET LIMITATION: Configured device IP {self.configured_ip} is outside")
                    logger.warning(f"   the container's subnet ({subnet_cidr}).")
                    logger.warning("   python-kasa discovery cannot detect devices across subnet boundaries.")
                    logger.warning("   This is expected - relying on static configuration for cross-subnet devices.")
                    logger.warning("   See README FAQ for more details on subnet/VLAN limitations.")
            
            self.state.consecutive_failures += 1
            
            # Notify if configured device is missing
            if self.configured_ip and self.notification_service:
                await self.notification_service.notify(
                    event_type="device_lost",
                    message=f"Configured device at {self.configured_ip} not found during health check",
                    details={
                        'configured_ip': self.configured_ip,
                        'consecutive_failures': self.state.consecutive_failures,
                        'last_seen': self.state.configured_device_last_seen.isoformat() 
                                    if self.state.configured_device_last_seen else 'Never'
                    }
                )
            
            # Check if we need to trigger re-initialization
            if self.state.consecutive_failures >= self.max_consecutive_failures:
                logger.error(f"✗ CRITICAL: {self.state.consecutive_failures} consecutive health check failures!")
                logger.error("  Consider restarting the scheduler or checking device connectivity")
                logger.error("\n  RECOVERY SUGGESTIONS:")
                logger.error("    1. Verify device is powered on and connected to network")
                logger.error("    2. Check firewall settings (UDP port 9999 for discovery)")
                logger.error("    3. Try running device discovery manually")
                logger.error("    4. Verify device IP hasn't changed (check DHCP assignments)")
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
        
        # Check configured device
        if self.configured_ip:
            if self.configured_ip in current_devices:
                configured_device = current_devices[self.configured_ip]
                self.state.configured_device_last_seen = datetime.now()
                
                logger.info(f"✓ Configured device OK: {configured_device.alias} at {self.configured_ip}")
                
                # Check if alias changed
                if self.configured_ip in self.state.last_known_devices:
                    old_device = self.state.last_known_devices[self.configured_ip]
                    if old_device.alias != configured_device.alias:
                        logger.warning(
                            f"⚠ Device alias changed: {old_device.alias} -> {configured_device.alias}"
                        )
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="device_changed",
                                message=f"Device alias changed at {self.configured_ip}",
                                details={
                                    'ip': self.configured_ip,
                                    'old_alias': old_device.alias,
                                    'new_alias': configured_device.alias,
                                }
                            )
                    
                    # Check if MAC changed (IP might have been reassigned)
                    if old_device.mac != configured_device.mac:
                        logger.warning(
                            f"⚠ CRITICAL: MAC address changed at {self.configured_ip}! "
                            f"IP may have been reassigned to a different device!"
                        )
                        logger.warning(f"  Old MAC: {old_device.mac} ({old_device.alias})")
                        logger.warning(f"  New MAC: {configured_device.mac} ({configured_device.alias})")
                        
                        if self.notification_service:
                            await self.notification_service.notify(
                                event_type="device_ip_changed",
                                message=f"CRITICAL: MAC address changed at {self.configured_ip}! IP may have been reassigned!",
                                details={
                                    'ip': self.configured_ip,
                                    'old_mac': old_device.mac,
                                    'new_mac': configured_device.mac,
                                    'old_alias': old_device.alias,
                                    'new_alias': configured_device.alias,
                                }
                            )
                
            else:
                logger.warning(f"⚠ Configured device not found at {self.configured_ip}")
                
                # Check if this is expected due to subnet limitations
                if local_info:
                    local_ip, subnet_cidr = local_info
                    if not is_ip_in_same_subnet(self.configured_ip, local_ip, subnet_cidr):
                        logger.info(f"  Note: Device is outside local subnet ({subnet_cidr}) - this is expected")
                        logger.info("  Discovery cannot detect cross-subnet devices. Relying on static configuration.")
                
                # Provide recovery suggestions based on discovery
                logger.warning("\n  RECOVERY SUGGESTIONS:")
                
                # Check if device moved to a different IP
                configured_mac = None
                if self.configured_ip in self.state.last_known_devices:
                    configured_mac = self.state.last_known_devices[self.configured_ip].mac
                
                found_at_different_ip = False
                if configured_mac:
                    for ip, device in current_devices.items():
                        if device.mac == configured_mac:
                            logger.warning(
                                f"    ✓ FOUND: Your device moved from {self.configured_ip} to {ip}!"
                            )
                            logger.warning(f"      Device: {device.alias} (MAC: {device.mac})")
                            logger.warning(f"      Update configuration: HEATTRAX_TAPO_IP_ADDRESS={ip}")
                            found_at_different_ip = True
                            
                            if self.notification_service:
                                await self.notification_service.notify(
                                    event_type="device_ip_changed",
                                    message=f"Configured device moved from {self.configured_ip} to {ip}",
                                    details={
                                        'old_ip': self.configured_ip,
                                        'new_ip': ip,
                                        'mac': device.mac,
                                        'alias': device.alias,
                                    }
                                )
                            break
                
                if not found_at_different_ip:
                    # Suggest alternatives from discovered devices
                    if len(current_devices) == 1:
                        single_device = list(current_devices.values())[0]
                        logger.warning(f"    ✓ ALTERNATIVE: Only one device found on network:")
                        logger.warning(f"      IP: {single_device.ip}")
                        logger.warning(f"      Alias: {single_device.alias} ({single_device.model})")
                        logger.warning(f"      MAC: {single_device.mac}")
                        logger.warning(f"      Update configuration: HEATTRAX_TAPO_IP_ADDRESS={single_device.ip}")
                    elif len(current_devices) > 1:
                        logger.warning(f"    ✓ ALTERNATIVES: {len(current_devices)} devices available:")
                        for i, (ip, device) in enumerate(current_devices.items(), 1):
                            logger.warning(
                                f"      {i}. {ip} - {device.alias} ({device.model}) [MAC: {device.mac}]"
                            )
                        logger.warning(f"      Update HEATTRAX_TAPO_IP_ADDRESS to use one of these")
                    else:
                        logger.warning(f"    ✗ No alternative devices discovered on network")
                        logger.warning(f"      Device may be powered off or on different network")
        
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
        return {
            'last_check_time': self.state.last_check_time.isoformat() if self.state.last_check_time else None,
            'consecutive_failures': self.state.consecutive_failures,
            'known_devices_count': len(self.state.last_known_devices),
            'configured_device_last_seen': self.state.configured_device_last_seen.isoformat() 
                                          if self.state.configured_device_last_seen else None,
            'needs_reinitialization': self.needs_reinitialization(),
        }

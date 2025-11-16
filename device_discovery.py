"""Device discovery and diagnostics using python-kasa library."""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from kasa import Discover

logger = logging.getLogger(__name__)


class DeviceInfo:
    """Container for discovered device information."""
    
    def __init__(self, device):
        """Initialize device info from discovered device.
        
        Args:
            device: Discovered device from python-kasa
        """
        self.device = device
        self.ip = device.host
        self.alias = getattr(device, 'alias', 'Unknown')
        self.model = getattr(device, 'model', 'Unknown')
        self.mac = getattr(device, 'mac', 'Unknown')
        self.is_on = getattr(device, 'is_on', None)
        
        # RSSI (signal strength) - may not be available on all devices
        self.rssi = None
        if hasattr(device, 'rssi'):
            self.rssi = device.rssi
        
        # Features
        self.features = []
        if hasattr(device, 'features'):
            self.features = list(device.features)
        
        # Hardware info
        self.hw_version = getattr(device, 'hw_version', 'Unknown')
        self.sw_version = getattr(device, 'sw_version', 'Unknown')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert device info to dictionary.
        
        Returns:
            Dictionary with device information
        """
        return {
            'ip': self.ip,
            'mac': self.mac,
            'alias': self.alias,
            'model': self.model,
            'state': 'ON' if self.is_on else 'OFF' if self.is_on is not None else 'Unknown',
            'rssi': self.rssi,
            'features': self.features,
            'hw_version': self.hw_version,
            'sw_version': self.sw_version,
        }
    
    def __str__(self) -> str:
        """String representation of device info."""
        parts = [
            f"Device: {self.alias}",
            f"  IP: {self.ip}",
            f"  MAC: {self.mac}",
            f"  Model: {self.model}",
            f"  State: {'ON' if self.is_on else 'OFF' if self.is_on is not None else 'Unknown'}",
        ]
        
        if self.rssi is not None:
            parts.append(f"  RSSI: {self.rssi} dBm")
        
        if self.features:
            parts.append(f"  Features: {', '.join(self.features)}")
        
        parts.append(f"  HW Version: {self.hw_version}")
        parts.append(f"  SW Version: {self.sw_version}")
        
        return '\n'.join(parts)


async def discover_devices(timeout: int = 10, target: Optional[str] = None) -> List[DeviceInfo]:
    """
    Discover Kasa/Tapo devices on the network.
    
    Args:
        timeout: Discovery timeout in seconds
        target: Optional target IP address or subnet (e.g., "192.168.1.255")
        
    Returns:
        List of DeviceInfo objects for discovered devices
    """
    logger.info("=" * 60)
    logger.info("Starting device discovery...")
    logger.info("=" * 60)
    
    if target:
        logger.info(f"Target: {target} (timeout: {timeout}s)")
    else:
        logger.info(f"Scanning local network (timeout: {timeout}s)")
    
    try:
        # Discover devices on the network
        logger.debug(f"Calling Discover.discover() with timeout={timeout}")
        
        if target:
            devices = await Discover.discover(target=target, timeout=timeout)
        else:
            devices = await Discover.discover(timeout=timeout)
        
        logger.info(f"Discovery completed - found {len(devices)} device(s)")
        
        # Process discovered devices
        device_infos = []
        for ip, device in devices.items():
            try:
                logger.debug(f"Processing device at {ip}...")
                
                # Update device to get latest information
                await device.update()
                
                device_info = DeviceInfo(device)
                device_infos.append(device_info)
                
                logger.info(f"\n{device_info}")
                logger.info("-" * 60)
                
            except Exception as e:
                logger.warning(f"Failed to get info for device at {ip}: {e}")
                continue
        
        return device_infos
        
    except Exception as e:
        logger.error(f"Device discovery failed: {type(e).__name__}: {e}")
        logger.exception("Full traceback:")
        return []


def print_config_suggestions(devices: List[DeviceInfo]):
    """
    Print configuration suggestions when multiple devices are found.
    
    Args:
        devices: List of discovered devices
    """
    logger.info("\n" + "=" * 60)
    logger.info(f"CONFIGURATION SUGGESTION: {len(devices)} devices found")
    logger.info("=" * 60)
    logger.info("\nPlease specify which device to control using one of these configurations:")
    logger.info("\nOption 1: Set environment variable:")
    
    for i, device in enumerate(devices, 1):
        logger.info(f"  Device {i}: HEATTRAX_TAPO_IP_ADDRESS={device.ip}  # {device.alias} ({device.model})")
    
    logger.info("\nOption 2: Update config.yaml:")
    logger.info("  device:")
    for i, device in enumerate(devices, 1):
        logger.info(f"    # Device {i}: {device.alias} ({device.model})")
        logger.info(f"    ip_address: \"{device.ip}\"")
        if i < len(devices):
            logger.info("")
    
    logger.info("\n" + "=" * 60)


async def run_device_discovery_and_diagnostics(configured_ip: Optional[str] = None, 
                                               connection_successful: bool = False) -> Optional[DeviceInfo]:
    """
    Run device discovery at startup and provide diagnostics.
    
    This function always runs network discovery and:
    1. Discovers all Kasa/Tapo devices on the network
    2. Logs details for each device (IP, MAC, alias, model)
    3. Validates configured IP exists in discovered devices (if provided)
    4. Logs warnings if configured device not found
    5. Suggests alternatives if only one device discovered
    6. Provides configuration suggestions for multiple devices
    
    Args:
        configured_ip: The IP address configured for use (if any)
        connection_successful: Whether connection to configured IP was successful
        
    Returns:
        DeviceInfo for the selected device, or None if no device selected
    """
    logger.info("\n" + "=" * 80)
    logger.info("DEVICE DISCOVERY AND DIAGNOSTICS")
    logger.info("=" * 80)
    
    if configured_ip:
        if connection_successful:
            logger.info(f"✓ Successfully connected to configured device at {configured_ip}")
            logger.info(f"  Running discovery to validate and log network devices...")
        else:
            logger.warning(f"⚠ Failed to connect to configured device at {configured_ip}")
            logger.warning(f"  Running discovery to find alternatives...")
    else:
        logger.info("No device IP configured - discovering devices on network...")
    
    # Always discover all devices on the network
    devices = await discover_devices(timeout=10)
    
    if not devices:
        logger.warning("\n⚠ WARNING: No Kasa/Tapo devices found on the network!")
        logger.warning("Please check:")
        logger.warning("  - Devices are powered on and connected to the network")
        logger.warning("  - This application is on the same network as the devices")
        logger.warning("  - Firewall is not blocking discovery (UDP port 9999)")
        
        if configured_ip:
            logger.warning(f"\nConfigured device at {configured_ip} not discovered.")
            if connection_successful:
                logger.info("However, direct connection succeeded - will continue with configured IP")
            else:
                logger.error("Direct connection also failed - device may be offline or unreachable")
        else:
            logger.error("No devices found and no IP configured - cannot proceed")
        
        logger.info("\n" + "=" * 80)
        logger.info("DEVICE DISCOVERY COMPLETE")
        logger.info("=" * 80 + "\n")
        return None
    
    # Log all discovered devices
    logger.info(f"\n{'=' * 80}")
    logger.info(f"DISCOVERED DEVICES ({len(devices)} found)")
    logger.info(f"{'=' * 80}")
    for i, device in enumerate(devices, 1):
        logger.info(f"\nDevice {i}:")
        logger.info(f"  IP Address: {device.ip}")
        logger.info(f"  MAC Address: {device.mac}")
        logger.info(f"  Alias: {device.alias}")
        logger.info(f"  Model: {device.model}")
        logger.info(f"  State: {'ON' if device.is_on else 'OFF' if device.is_on is not None else 'Unknown'}")
    logger.info(f"{'=' * 80}\n")
    
    # Check if configured IP matches any discovered device
    selected_device = None
    
    if configured_ip:
        logger.info(f"CONFIGURED DEVICE VALIDATION:")
        logger.info(f"  Configured IP: {configured_ip}")
        
        # Find matching device
        for device in devices:
            if device.ip == configured_ip:
                selected_device = device
                logger.info(f"  ✓ VALIDATION SUCCESS: Configured device found in discovery!")
                logger.info(f"    Using: {device.alias} (MAC: {device.mac})")
                break
        
        if not selected_device:
            logger.warning(f"  ⚠ VALIDATION WARNING: Configured IP {configured_ip} NOT found in discovery!")
            logger.warning(f"    The device may be:")
            logger.warning(f"      - On a different network segment")
            logger.warning(f"      - Blocking broadcast discovery")
            logger.warning(f"      - Using a static IP outside DHCP range")
            
            if connection_successful:
                logger.info(f"    However, direct connection succeeded.")
                logger.info(f"    Continuing with configured IP {configured_ip}")
            else:
                logger.error(f"    Direct connection FAILED and device not discovered.")
                logger.error(f"    Device appears to be offline or unreachable!")
                
                # Suggest alternatives
                if len(devices) == 1:
                    logger.info(f"\n  SUGGESTION: Only one device discovered on network:")
                    logger.info(f"    IP: {devices[0].ip}")
                    logger.info(f"    Alias: {devices[0].alias} ({devices[0].model})")
                    logger.info(f"    MAC: {devices[0].mac}")
                    logger.info(f"    Consider updating configuration: HEATTRAX_TAPO_IP_ADDRESS={devices[0].ip}")
                    selected_device = devices[0]
                elif len(devices) > 1:
                    logger.info(f"\n  AVAILABLE ALTERNATIVES ({len(devices)} devices):")
                    for i, device in enumerate(devices, 1):
                        logger.info(f"    {i}. {device.ip} - {device.alias} ({device.model}) [MAC: {device.mac}]")
                    logger.info(f"    Update HEATTRAX_TAPO_IP_ADDRESS to use one of these devices")
        
        # If multiple devices, still provide config suggestions
        if len(devices) > 1:
            logger.info(f"\n  NOTE: Multiple devices detected on network")
            print_config_suggestions(devices)
    
    elif len(devices) == 1:
        # Auto-select the only device found (when no IP configured)
        selected_device = devices[0]
        logger.info(f"✓ AUTO-SELECT: Only one device discovered on network")
        logger.info(f"  IP: {selected_device.ip}")
        logger.info(f"  Alias: {selected_device.alias} ({selected_device.model})")
        logger.info(f"  MAC: {selected_device.mac}")
        logger.info(f"\n  To persist this selection, set:")
        logger.info(f"    HEATTRAX_TAPO_IP_ADDRESS={selected_device.ip}")
    
    else:
        # Multiple devices found - provide configuration suggestions
        logger.warning(f"⚠ No device IP configured and multiple devices found")
        logger.warning(f"  Please specify which device to use")
        print_config_suggestions(devices)
    
    logger.info("\n" + "=" * 80)
    logger.info("DEVICE DISCOVERY COMPLETE")
    logger.info("=" * 80 + "\n")
    
    return selected_device

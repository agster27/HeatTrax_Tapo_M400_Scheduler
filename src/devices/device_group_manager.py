"""Device group manager for controlling multiple Kasa/Tapo devices organized by groups."""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from kasa import Discover
from src.devices.device_controller import DeviceControllerError


logger = logging.getLogger(__name__)


class DeviceGroupManager:
    """Manager for controlling groups of smart devices."""
    
    def __init__(self, devices_config: Dict[str, Any]):
        """
        Initialize device group manager.
        
        Args:
            devices_config: Configuration dictionary with devices section
        """
        self.devices_config = devices_config
        self.credentials = devices_config.get('credentials', {})
        self.username = self.credentials.get('username')
        self.password = self.credentials.get('password')
        self.groups = {}
        self._initialized = False
        
        if not self.username or not self.password:
            raise DeviceControllerError("Username and password are required in devices.credentials")
    
    async def initialize(self):
        """Initialize all device groups."""
        logger.info("Initializing device group manager...")
        
        groups_config = self.devices_config.get('groups', {})
        
        for group_name, group_config in groups_config.items():
            if not group_config.get('enabled', True):
                logger.info(f"Group '{group_name}' is disabled, skipping")
                continue
            
            logger.info(f"Initializing group: {group_name}")
            group = DeviceGroup(
                name=group_name,
                config=group_config,
                username=self.username,
                password=self.password
            )
            await group.initialize()
            self.groups[group_name] = group
        
        self._initialized = True
        logger.info(f"Device group manager initialized with {len(self.groups)} groups")
    
    async def turn_on_group(self, group_name: str):
        """
        Turn on all devices in a group.
        
        Args:
            group_name: Name of the group to turn on
        """
        if group_name not in self.groups:
            logger.error(f"Group '{group_name}' not found")
            raise DeviceControllerError(f"Group '{group_name}' not found")
        
        logger.info(f"Turning ON group: {group_name}")
        await self.groups[group_name].turn_on()
    
    async def turn_off_group(self, group_name: str):
        """
        Turn off all devices in a group.
        
        Args:
            group_name: Name of the group to turn off
        """
        if group_name not in self.groups:
            logger.error(f"Group '{group_name}' not found")
            raise DeviceControllerError(f"Group '{group_name}' not found")
        
        logger.info(f"Turning OFF group: {group_name}")
        await self.groups[group_name].turn_off()
    
    async def get_group_state(self, group_name: str) -> bool:
        """
        Get state of a group (on if any device is on).
        
        Args:
            group_name: Name of the group
            
        Returns:
            True if any device in group is on, False otherwise
        """
        if group_name not in self.groups:
            logger.error(f"Group '{group_name}' not found")
            raise DeviceControllerError(f"Group '{group_name}' not found")
        
        return await self.groups[group_name].get_state()
    
    def get_group_config(self, group_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a group.
        
        Args:
            group_name: Name of the group
            
        Returns:
            Group configuration dictionary or None if not found
        """
        if group_name not in self.groups:
            return None
        return self.groups[group_name].config
    
    def get_all_groups(self) -> List[str]:
        """Get list of all group names."""
        return list(self.groups.keys())
    
    async def get_all_devices_status(self) -> List[Dict[str, Any]]:
        """
        Get detailed status of all devices across all groups.
        
        This method queries each device to get its current state, including:
        - Device reachability (whether the device responds to queries)
        - Individual outlet states (on/off for each outlet)
        - Any error conditions (connection failures, timeouts, etc.)
        
        Unreachable devices are included in the results with reachable=False
        and an error message, rather than raising exceptions.
        
        Returns:
            List of device status dictionaries with device info and outlet states
        """
        all_devices = []
        
        logger.debug(f"Getting status for {len(self.groups)} group(s)")
        
        for group_name, group in self.groups.items():
            devices_status = await group.get_devices_status()
            logger.debug(f"Group '{group_name}': retrieved status for {len(devices_status)} device(s)")
            for device_status in devices_status:
                device_status['group'] = group_name
                all_devices.append(device_status)
        
        logger.info(f"Retrieved status for {len(all_devices)} total device(s) across all groups")
        return all_devices
    
    def get_initialization_summary(self) -> Dict[str, Any]:
        """
        Get summary of device initialization across all groups.
        
        Returns:
            Dictionary with initialization statistics for all groups
        """
        summary = {
            'total_groups': len(self.groups),
            'groups': {},
            'overall': {
                'configured_devices': 0,
                'initialized_devices': 0,
                'failed_devices': 0
            }
        }
        
        for group_name, group in self.groups.items():
            group_info = group.get_initialization_info()
            summary['groups'][group_name] = group_info
            
            # Aggregate totals
            summary['overall']['configured_devices'] += group_info['configured_count']
            summary['overall']['initialized_devices'] += group_info['initialized_count']
            summary['overall']['failed_devices'] += group_info['failed_count']
        
        return summary
    
    async def control_device_outlet(self, group_name: str, device_name: str, 
                                    outlet_index: Optional[int], action: str) -> Dict[str, Any]:
        """
        Control a specific device or outlet.
        
        This method provides manual control of devices and outlets, bypassing
        the scheduler's automated logic. Use cases include:
        - Emergency shutoff of malfunctioning devices
        - Manual override for special circumstances
        - Testing device functionality
        
        Note: Manual control is temporary. The scheduler will reassert control
        on its next evaluation cycle (typically check_interval_minutes).
        The scheduler does not persist or remember manual overrides.
        
        Args:
            group_name: Name of the group containing the device
            device_name: Name of the device
            outlet_index: Outlet index (None for entire device)
            action: 'on' or 'off'
            
        Returns:
            Dictionary with status of the control operation:
            {
                'success': bool,
                'device': str,
                'outlet': int or None,
                'action': str,
                'error': str or None
            }
        """
        if group_name not in self.groups:
            return {
                'success': False,
                'error': f"Group '{group_name}' not found"
            }
        
        return await self.groups[group_name].control_device_outlet(
            device_name, outlet_index, action
        )
    
    async def close(self):
        """Close all device connections."""
        logger.info("Closing all device group connections...")
        for group in self.groups.values():
            await group.close()


class DeviceGroup:
    """Represents a group of devices with common automation rules."""
    
    def __init__(self, name: str, config: Dict[str, Any], username: str, password: str):
        """
        Initialize a device group.
        
        Args:
            name: Group name
            config: Group configuration
            username: Tapo account username
            password: Tapo account password
        """
        self.name = name
        self.config = config
        self.username = username
        self.password = password
        self.devices = []
        self._initialized = False
        self._configured_device_count = 0  # Track how many devices were configured
        self._failed_devices = []  # Track devices that failed to initialize
    
    async def initialize(self):
        """Initialize all devices in the group."""
        items = self.config.get('items', [])
        self._configured_device_count = len(items)
        
        if not items:
            logger.warning(f"Group '{self.name}' has no devices configured")
            return
        
        logger.info(f"Initializing {len(items)} device(s) in group '{self.name}'")
        
        for item_config in items:
            device_name = item_config.get('name', 'unknown')
            device_ip = item_config.get('ip_address', 'unknown')
            
            try:
                device = ManagedDevice(
                    config=item_config,
                    username=self.username,
                    password=self.password
                )
                await device.initialize()
                self.devices.append(device)
                logger.info(f"  ✓ Initialized device: {device.name} at {device.ip_address}")
            except Exception as e:
                # Track failed device for reporting
                self._failed_devices.append({
                    'name': device_name,
                    'ip_address': device_ip,
                    'error': str(e)
                })
                logger.error(f"  ✗ Failed to initialize device '{device_name}' at {device_ip}: {e}")
                # Continue with other devices even if one fails
        
        self._initialized = True
        
        if len(self.devices) == 0:
            logger.warning(f"Group '{self.name}' initialized with 0 devices (all {self._configured_device_count} configured device(s) failed)")
        elif len(self.devices) < self._configured_device_count:
            logger.warning(f"Group '{self.name}' initialized with {len(self.devices)}/{self._configured_device_count} devices ({self._configured_device_count - len(self.devices)} failed)")
        else:
            logger.info(f"Group '{self.name}' initialized successfully with {len(self.devices)} device(s)")
    
    async def turn_on(self):
        """Turn on all devices in the group."""
        logger.info(f"Turning ON all devices in group '{self.name}'")
        tasks = [device.turn_on() for device in self.devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any failures
        for device, result in zip(self.devices, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to turn on device '{device.name}': {result}")
    
    async def turn_off(self):
        """Turn off all devices in the group."""
        logger.info(f"Turning OFF all devices in group '{self.name}'")
        tasks = [device.turn_off() for device in self.devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any failures
        for device, result in zip(self.devices, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to turn off device '{device.name}': {result}")
    
    async def get_state(self) -> bool:
        """
        Get state of the group (on if any device is on).
        
        Returns:
            True if any device is on, False otherwise
        """
        states = await asyncio.gather(
            *[device.get_state() for device in self.devices],
            return_exceptions=True
        )
        
        # Return True if any device is on (and didn't fail)
        return any(state is True for state in states if not isinstance(state, Exception))
    
    async def get_devices_status(self) -> List[Dict[str, Any]]:
        """
        Get detailed status of all devices in the group.
        
        Returns:
            List of device status dictionaries
        """
        devices_status = []
        
        for device in self.devices:
            status = await device.get_detailed_status()
            devices_status.append(status)
        
        return devices_status
    
    def get_initialization_info(self) -> Dict[str, Any]:
        """
        Get information about device initialization for this group.
        
        Returns:
            Dictionary with initialization statistics and failed device details
        """
        return {
            'group_name': self.name,
            'configured_count': self._configured_device_count,
            'initialized_count': len(self.devices),
            'failed_count': len(self._failed_devices),
            'failed_devices': self._failed_devices,
            'initialization_complete': self._initialized
        }
    
    async def control_device_outlet(self, device_name: str, outlet_index: Optional[int], 
                                    action: str) -> Dict[str, Any]:
        """
        Control a specific device or outlet in the group.
        
        Args:
            device_name: Name of the device
            outlet_index: Outlet index (None for entire device)
            action: 'on' or 'off'
            
        Returns:
            Dictionary with status of the control operation
        """
        # Find the device
        target_device = None
        for device in self.devices:
            if device.name == device_name:
                target_device = device
                break
        
        if not target_device:
            return {
                'success': False,
                'error': f"Device '{device_name}' not found in group '{self.name}'"
            }
        
        # Control the device/outlet
        return await target_device.control_outlet(outlet_index, action)
    
    async def close(self):
        """Close all device connections."""
        for device in self.devices:
            await device.close()


class ManagedDevice:
    """Represents a managed smart device with optional outlet control."""
    
    # Default timeout for Tapo device discovery and initialization (in seconds)
    # Increased from default to handle slow Tapo responses
    DEFAULT_DISCOVERY_TIMEOUT = 30
    
    def __init__(self, config: Dict[str, Any], username: str, password: str):
        """
        Initialize a managed device.
        
        Args:
            config: Device configuration
            username: Tapo account username
            password: Tapo account password
        """
        self.name = config.get('name', 'Unknown Device')
        self.ip_address = config.get('ip_address')
        self.outlets = config.get('outlets', [])  # Empty list means control entire device
        self.username = username
        self.password = password
        self.device = None
        self._initialized = False
        self._initialization_error = None  # Track initialization failures
        
        # Allow timeout configuration per device (optional)
        self.discovery_timeout = config.get('discovery_timeout_seconds', self.DEFAULT_DISCOVERY_TIMEOUT)
        
        if not self.ip_address:
            raise DeviceControllerError(f"IP address is required for device '{self.name}'")
    
    async def initialize(self):
        """Initialize connection to the device using Tapo-authenticated discovery."""
        logger.debug(f"Initializing device '{self.name}' at {self.ip_address} (timeout: {self.discovery_timeout}s)")
        
        # Validate credentials
        if not self.username or not self.password:
            error_msg = (
                f"Missing Tapo credentials for device '{self.name}'. "
                "Please set HEATTRAX_TAPO_USERNAME and HEATTRAX_TAPO_PASSWORD environment variables."
            )
            logger.error(error_msg)
            self._initialization_error = error_msg
            raise DeviceControllerError(error_msg)
        
        try:
            # Use Tapo-authenticated discovery with extended timeout
            # Wrap in asyncio.wait_for to control timeout explicitly
            logger.debug(f"Using Discover.discover_single with Tapo credentials for {self.ip_address}")
            
            try:
                # Discovery step with timeout
                self.device = await asyncio.wait_for(
                    Discover.discover_single(
                        self.ip_address,
                        username=self.username,
                        password=self.password,
                    ),
                    timeout=self.discovery_timeout
                )
                logger.debug(f"Device discovered at {self.ip_address}, fetching initial state...")
                
                # Update step with timeout
                await asyncio.wait_for(
                    self.device.update(),
                    timeout=self.discovery_timeout
                )
                
            except asyncio.TimeoutError as te:
                error_msg = (
                    f"Timeout after {self.discovery_timeout}s while initializing device '{self.name}' at {self.ip_address}. "
                    f"Device may be unreachable, overloaded, or slow to respond. "
                    f"Consider increasing 'discovery_timeout_seconds' in device config if device is reachable but slow."
                )
                logger.error(error_msg)
                self._initialization_error = f"Timeout after {self.discovery_timeout}s"
                raise DeviceControllerError(error_msg) from te
            
            self._initialized = True
            self._initialization_error = None
            
            # Log device information
            device_model = getattr(self.device, 'model', 'Unknown')
            device_alias = getattr(self.device, 'alias', 'Unknown')
            num_children = len(self.device.children) if hasattr(self.device, 'children') and self.device.children else 0
            
            logger.info(f"Successfully initialized device '{self.name}': model={device_model}, alias={device_alias}, outlets={num_children}")
            
            # Check if device has children (outlets)
            if num_children > 0:
                logger.debug(f"Device '{self.name}' has {num_children} outlets")
            
        except DeviceControllerError:
            # Re-raise controller errors as-is
            raise
        except Exception as e:
            # Capture detailed error information for any other exceptions
            error_type = type(e).__name__
            error_msg = f"{error_type}: {str(e)}"
            logger.error(f"Failed to initialize device '{self.name}' at {self.ip_address}: {error_msg}")
            logger.debug(f"Full exception for device '{self.name}':", exc_info=True)
            self._initialization_error = error_msg
            raise DeviceControllerError(f"Failed to initialize device '{self.name}': {error_msg}") from e
    
    async def turn_on(self):
        """Turn on the device or specified outlets."""
        if not self._initialized:
            await self.initialize()
        
        try:
            await self.device.update()
            
            # If outlets are specified, control only those outlets
            if self.outlets and hasattr(self.device, 'children') and self.device.children:
                logger.debug(f"Turning ON outlets {self.outlets} on device '{self.name}'")
                for outlet_index in self.outlets:
                    if outlet_index < len(self.device.children):
                        child = self.device.children[outlet_index]
                        if not child.is_on:
                            await child.turn_on()
                            logger.debug(f"  ✓ Outlet {outlet_index} turned ON")
            else:
                # Control entire device
                if not self.device.is_on:
                    logger.debug(f"Turning ON device '{self.name}'")
                    await self.device.turn_on()
                    logger.debug(f"  ✓ Device '{self.name}' turned ON")
            
            # Verify state
            await asyncio.sleep(1)
            await self.device.update()
            
        except Exception as e:
            logger.error(f"Failed to turn on device '{self.name}': {e}")
            raise DeviceControllerError(f"Failed to turn on device '{self.name}': {e}")
    
    async def turn_off(self):
        """Turn off the device or specified outlets."""
        if not self._initialized:
            await self.initialize()
        
        try:
            await self.device.update()
            
            # If outlets are specified, control only those outlets
            if self.outlets and hasattr(self.device, 'children') and self.device.children:
                logger.debug(f"Turning OFF outlets {self.outlets} on device '{self.name}'")
                for outlet_index in self.outlets:
                    if outlet_index < len(self.device.children):
                        child = self.device.children[outlet_index]
                        if child.is_on:
                            await child.turn_off()
                            logger.debug(f"  ✓ Outlet {outlet_index} turned OFF")
            else:
                # Control entire device
                if self.device.is_on:
                    logger.debug(f"Turning OFF device '{self.name}'")
                    await self.device.turn_off()
                    logger.debug(f"  ✓ Device '{self.name}' turned OFF")
            
            # Verify state
            await asyncio.sleep(1)
            await self.device.update()
            
        except Exception as e:
            logger.error(f"Failed to turn off device '{self.name}': {e}")
            raise DeviceControllerError(f"Failed to turn off device '{self.name}': {e}")
    
    async def get_state(self) -> bool:
        """
        Get current state of the device or outlets.
        
        Returns:
            True if device/any outlet is on, False otherwise
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            await self.device.update()
            
            # If outlets are specified, check those outlets
            if self.outlets and hasattr(self.device, 'children') and self.device.children:
                for outlet_index in self.outlets:
                    if outlet_index < len(self.device.children):
                        if self.device.children[outlet_index].is_on:
                            return True
                return False
            else:
                # Check entire device
                return self.device.is_on
                
        except Exception as e:
            logger.error(f"Failed to get state of device '{self.name}': {e}")
            raise DeviceControllerError(f"Failed to get state of device '{self.name}': {e}")
    
    async def get_detailed_status(self) -> Dict[str, Any]:
        """
        Get detailed status of the device including outlet states.
        
        Returns:
            Dictionary with device information and outlet states
        """
        status = {
            'name': self.name,
            'ip_address': self.ip_address,
            'reachable': False,
            'initialized': self._initialized,
            'has_outlets': False,
            'outlets': [],
            'model': 'Unknown',
            'error': None,
            'initialization_error': self._initialization_error
        }
        
        # If device never initialized successfully, return status with initialization error
        if not self._initialized and self._initialization_error:
            status['error'] = f"Device not initialized: {self._initialization_error}"
            return status
        
        try:
            if not self._initialized:
                await self.initialize()
            
            await self.device.update()
            status['reachable'] = True
            status['initialized'] = True
            
            # Get device model
            status['model'] = getattr(self.device, 'model', 'Unknown')
            
            # Check if device has children (outlets)
            if hasattr(self.device, 'children') and self.device.children:
                status['has_outlets'] = True
                num_outlets = len(self.device.children)
                
                for i in range(num_outlets):
                    child = self.device.children[i]
                    outlet_info = {
                        'index': i,
                        'is_on': child.is_on,
                        'alias': getattr(child, 'alias', f'Outlet {i}'),
                        'controlled': i in self.outlets if self.outlets else True
                    }
                    status['outlets'].append(outlet_info)
            else:
                # Single device (no outlets)
                status['outlets'].append({
                    'index': None,
                    'is_on': self.device.is_on,
                    'alias': getattr(self.device, 'alias', self.name),
                    'controlled': True
                })
            
        except Exception as e:
            logger.error(f"Failed to get detailed status for device '{self.name}': {e}")
            status['error'] = str(e)
            status['reachable'] = False
        
        return status
    
    async def control_outlet(self, outlet_index: Optional[int], action: str) -> Dict[str, Any]:
        """
        Control a specific outlet or the entire device.
        
        Args:
            outlet_index: Outlet index (None for entire device)
            action: 'on' or 'off'
            
        Returns:
            Dictionary with status of the control operation
        """
        result = {
            'success': False,
            'device': self.name,
            'outlet': outlet_index,
            'action': action,
            'error': None
        }
        
        try:
            if not self._initialized:
                await self.initialize()
            
            await self.device.update()
            
            # Validate action
            if action not in ['on', 'off']:
                result['error'] = f"Invalid action: {action}. Must be 'on' or 'off'"
                return result
            
            # Control specific outlet
            if outlet_index is not None:
                if not hasattr(self.device, 'children') or not self.device.children:
                    result['error'] = "Device has no outlets"
                    return result
                
                if outlet_index >= len(self.device.children):
                    result['error'] = f"Outlet index {outlet_index} out of range (device has {len(self.device.children)} outlets)"
                    return result
                
                child = self.device.children[outlet_index]
                
                if action == 'on':
                    await child.turn_on()
                    logger.info(f"Manually turned ON outlet {outlet_index} on device '{self.name}'")
                else:
                    await child.turn_off()
                    logger.info(f"Manually turned OFF outlet {outlet_index} on device '{self.name}'")
                
            else:
                # Control entire device
                if action == 'on':
                    await self.device.turn_on()
                    logger.info(f"Manually turned ON device '{self.name}'")
                else:
                    await self.device.turn_off()
                    logger.info(f"Manually turned OFF device '{self.name}'")
            
            # Verify state after action
            await asyncio.sleep(1)
            await self.device.update()
            
            result['success'] = True
            logger.info(f"Successfully {action} device '{self.name}' outlet {outlet_index}")
            
        except Exception as e:
            logger.error(f"Failed to control device '{self.name}' outlet {outlet_index}: {e}")
            result['error'] = str(e)
        
        return result
    
    async def close(self):
        """Close connection to the device."""
        if self.device:
            try:
                # python-kasa doesn't require explicit close for SmartPlug
                logger.debug(f"Closed connection to device '{self.name}'")
            except Exception as e:
                logger.warning(f"Error closing device '{self.name}': {e}")

"""Device group manager for controlling multiple Kasa/Tapo devices organized by groups."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from kasa import SmartPlug, SmartStrip
from device_controller import DeviceControllerError


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
    
    async def initialize(self):
        """Initialize all devices in the group."""
        items = self.config.get('items', [])
        
        if not items:
            logger.warning(f"Group '{self.name}' has no devices configured")
            return
        
        logger.info(f"Initializing {len(items)} devices in group '{self.name}'")
        
        for item_config in items:
            try:
                device = ManagedDevice(
                    config=item_config,
                    username=self.username,
                    password=self.password
                )
                await device.initialize()
                self.devices.append(device)
                logger.info(f"  ✓ Initialized device: {device.name}")
            except Exception as e:
                logger.error(f"  ✗ Failed to initialize device '{item_config.get('name', 'unknown')}': {e}")
                # Continue with other devices even if one fails
        
        self._initialized = True
        logger.info(f"Group '{self.name}' initialized with {len(self.devices)} devices")
    
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
    
    async def close(self):
        """Close all device connections."""
        for device in self.devices:
            await device.close()


class ManagedDevice:
    """Represents a managed smart device with optional outlet control."""
    
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
        
        if not self.ip_address:
            raise DeviceControllerError(f"IP address is required for device '{self.name}'")
    
    async def initialize(self):
        """Initialize connection to the device."""
        logger.debug(f"Initializing device '{self.name}' at {self.ip_address}")
        
        try:
            # Create SmartPlug device
            self.device = SmartPlug(self.ip_address)
            await self.device.update()
            
            self._initialized = True
            logger.debug(f"Successfully initialized device '{self.name}'")
            
            # Check if device has children (outlets)
            if hasattr(self.device, 'children') and self.device.children:
                logger.debug(f"Device '{self.name}' has {len(self.device.children)} outlets")
            
        except Exception as e:
            logger.error(f"Failed to initialize device '{self.name}' at {self.ip_address}: {e}")
            raise DeviceControllerError(f"Failed to initialize device '{self.name}': {e}")
    
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
    
    async def close(self):
        """Close connection to the device."""
        if self.device:
            try:
                # python-kasa doesn't require explicit close for SmartPlug
                logger.debug(f"Closed connection to device '{self.name}'")
            except Exception as e:
                logger.warning(f"Error closing device '{self.name}': {e}")

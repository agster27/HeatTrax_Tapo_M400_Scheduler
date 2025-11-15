"""Device controller for TP-Link Tapo smart plugs using python-kasa."""

import asyncio
import logging
from typing import Optional
from kasa import SmartPlug, Credentials


logger = logging.getLogger(__name__)


class DeviceControllerError(Exception):
    """Device controller error exception."""
    pass


class TapoController:
    """Controller for TP-Link Tapo smart plug."""
    
    def __init__(self, ip_address: str, username: str, password: str):
        """
        Initialize Tapo controller.
        
        Args:
            ip_address: IP address of the Tapo device
            username: Tapo account username
            password: Tapo account password
        """
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.device: Optional[SmartPlug] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize connection to the device."""
        try:
            credentials = Credentials(username=self.username, password=self.password)
            self.device = SmartPlug(self.ip_address, credentials=credentials)
            await self.device.update()
            self._initialized = True
            logger.info(f"Successfully connected to device at {self.ip_address}")
            logger.info(f"Device info: {self.device.alias}")
        except Exception as e:
            raise DeviceControllerError(f"Failed to initialize device: {e}")
    
    async def turn_on(self):
        """Turn on the smart plug."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if not self.device.is_on:
                await self.device.turn_on()
                logger.info(f"Turned ON device at {self.ip_address}")
            else:
                logger.debug(f"Device at {self.ip_address} is already ON")
        except Exception as e:
            raise DeviceControllerError(f"Failed to turn on device: {e}")
    
    async def turn_off(self):
        """Turn off the smart plug."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if self.device.is_on:
                await self.device.turn_off()
                logger.info(f"Turned OFF device at {self.ip_address}")
            else:
                logger.debug(f"Device at {self.ip_address} is already OFF")
        except Exception as e:
            raise DeviceControllerError(f"Failed to turn off device: {e}")
    
    async def get_state(self) -> bool:
        """
        Get current state of the device.
        
        Returns:
            True if device is on, False otherwise
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            await self.device.update()
            return self.device.is_on
        except Exception as e:
            raise DeviceControllerError(f"Failed to get device state: {e}")
    
    async def close(self):
        """Close connection to the device."""
        if self.device:
            try:
                # python-kasa handles cleanup automatically
                logger.info("Closed connection to device")
            except Exception as e:
                logger.warning(f"Error closing device connection: {e}")

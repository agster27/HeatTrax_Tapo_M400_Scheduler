"""Device controller for TP-Link Tapo smart plugs using python-kasa."""

import asyncio
import logging
from typing import Optional
from kasa import Discover


logger = logging.getLogger(__name__)


class DeviceControllerError(Exception):
    """Device controller error exception."""
    pass


class TapoController:
    """Controller for TP-Link Tapo smart plug."""
    
    def __init__(self, ip_address: str, username: str, password: str):
        """Initialize Tapo controller.
        
        Args:
            ip_address: IP address of the Tapo device
            username: Tapo account username
            password: Tapo account password
        """
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.device = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize connection to the device using Tapo-authenticated discovery."""
        logger.info(f"Initializing connection to Tapo device at {self.ip_address}")
        logger.debug(f"Using username: {self.username}")
        
        if not self.ip_address:
            logger.error("IP address is empty")
            raise DeviceControllerError("IP address cannot be empty")
        
        if not self.username or not self.password:
            logger.error("Username or password is empty - Tapo credentials are required")
            error_msg = (
                "Username and password are required for Tapo device control. "
                "Please set HEATTRAX_TAPO_USERNAME and HEATTRAX_TAPO_PASSWORD environment variables."
            )
            raise DeviceControllerError(error_msg)
        
        try:
            logger.debug(f"Using Discover.discover_single with Tapo credentials for {self.ip_address}")
            self.device = await Discover.discover_single(
                self.ip_address,
                username=self.username,
                password=self.password,
            )
            
            logger.info(f"Attempting to update device at {self.ip_address}")
            await self.device.update()
            
            self._initialized = True
            logger.info(f"Successfully connected to device at {self.ip_address}")
            
            # Log device information
            device_model = getattr(self.device, 'model', 'Unknown')
            device_alias = getattr(self.device, 'alias', 'Unknown')
            num_children = len(self.device.children) if hasattr(self.device, 'children') and self.device.children else 0
            
            logger.info(f"Device info: model={device_model}, alias={device_alias}, outlets={num_children}")
            
            if self.device.alias:
                logger.info(f"Device name: {self.device.alias}")
            if hasattr(self.device, 'model'):
                logger.debug(f"Device model: {self.device.model}")
            if hasattr(self.device, 'hw_info'):
                logger.debug(f"Hardware info: {self.device.hw_info}")
                
        except ConnectionError as e:
            logger.error(f"Connection error while initializing device at {self.ip_address}: {e}")
            logger.error("Possible causes: Device is offline, IP address is wrong, network issue")
            raise DeviceControllerError(f"Failed to connect to device at {self.ip_address}: {e}")
        except TimeoutError as e:
            logger.error(f"Timeout while connecting to device at {self.ip_address}: {e}")
            logger.error("Device may be unreachable or not responding")
            raise DeviceControllerError(f"Connection timeout for device at {self.ip_address}: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize device at {self.ip_address}: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            logger.error("Possible causes: Invalid credentials, device not compatible, network issue")
            raise DeviceControllerError(f"Failed to initialize device: {e}")
    
    async def turn_on(self):
        """Turn on the smart plug."""
        logger.info(f"Request to turn ON device at {self.ip_address}")
        
        if not self._initialized:
            logger.warning("Device not initialized, initializing now")
            await self.initialize()
        
        try:
            if not self.device:
                logger.error("Device object is None")
                raise DeviceControllerError("Device object is not initialized")
            
            logger.debug(f"Checking current state of device at {self.ip_address}")
            await self.device.update()
            
            if not self.device.is_on:
                logger.info(f"Turning ON device at {self.ip_address}")
                await self.device.turn_on()
                
                await asyncio.sleep(1)
                await self.device.update()
                
                if self.device.is_on:
                    logger.info(f"Successfully turned ON device at {self.ip_address}")
                else:
                    logger.warning(f"Device reports OFF state after turn_on command")
            else:
                logger.info(f"Device at {self.ip_address} is already ON, no action needed")
                
        except ConnectionError as e:
            logger.error(f"Connection error while turning on device: {e}")
            raise DeviceControllerError(f"Failed to turn on device due to connection error: {e}")
        except TimeoutError as e:
            logger.error(f"Timeout while turning on device: {e}")
            raise DeviceControllerError(f"Timeout while turning on device: {e}")
        except Exception as e:
            logger.error(f"Failed to turn on device: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise DeviceControllerError(f"Failed to turn on device: {e}")
    
    async def turn_off(self):
        """Turn off the smart plug."""
        logger.info(f"Request to turn OFF device at {self.ip_address}")
        
        if not self._initialized:
            logger.warning("Device not initialized, initializing now")
            await self.initialize()
        
        try:
            if not self.device:
                logger.error("Device object is None")
                raise DeviceControllerError("Device object is not initialized")
            
            logger.debug(f"Checking current state of device at {self.ip_address}")
            await self.device.update()
            
            if self.device.is_on:
                logger.info(f"Turning OFF device at {self.ip_address}")
                await self.device.turn_off()
                
                await asyncio.sleep(1)
                await self.device.update()
                
                if not self.device.is_on:
                    logger.info(f"Successfully turned OFF device at {self.ip_address}")
                else:
                    logger.warning(f"Device reports ON state after turn_off command")
            else:
                logger.info(f"Device at {self.ip_address} is already OFF, no action needed")
                
        except ConnectionError as e:
            logger.error(f"Connection error while turning off device: {e}")
            raise DeviceControllerError(f"Failed to turn off device due to connection error: {e}")
        except TimeoutError as e:
            logger.error(f"Timeout while turning off device: {e}")
            raise DeviceControllerError(f"Timeout while turning off device: {e}")
        except Exception as e:
            logger.error(f"Failed to turn off device: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise DeviceControllerError(f"Failed to turn off device: {e}")
    
    async def get_state(self) -> bool:
        """Get current state of the device.
        
        Returns:
            True if device is on, False otherwise
        """
        logger.debug(f"Checking state of device at {self.ip_address}")
        
        if not self._initialized:
            logger.warning("Device not initialized, initializing now")
            await self.initialize()
        
        try:
            if not self.device:
                logger.error("Device object is None")
                raise DeviceControllerError("Device object is not initialized")
            
            logger.debug(f"Updating device state from {self.ip_address}")
            await self.device.update()
            
            state = self.device.is_on
            logger.info(f"Device at {self.ip_address} is currently: {'ON' if state else 'OFF'}")
            
            return state
            
        except ConnectionError as e:
            logger.error(f"Connection error while getting device state: {e}")
            raise DeviceControllerError(f"Failed to get device state due to connection error: {e}")
        except TimeoutError as e:
            logger.error(f"Timeout while getting device state: {e}")
            raise DeviceControllerError(f"Timeout while getting device state: {e}")
        except Exception as e:
            logger.error(f"Failed to get device state: {type(e).__name__}: {e}")
            logger.exception("Full traceback:")
            raise DeviceControllerError(f"Failed to get device state: {e}")
    
    async def close(self):
        """Close connection to the device."""
        if self.device:
            try:
                logger.info("Closed connection to device")
            except Exception as e:
                logger.warning(f"Error closing device connection: {e}")


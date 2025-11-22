"""Device management package."""

from .device_controller import TapoController, DeviceControllerError
from .device_discovery import (
    DeviceInfo,
    discover_devices,
    run_device_discovery_and_diagnostics,
    get_local_ip_and_subnet,
    is_ip_in_same_subnet,
    print_config_suggestions
)
from .device_group_manager import DeviceGroupManager, DeviceGroup, ManagedDevice

__all__ = [
    'TapoController',
    'DeviceControllerError',
    'DeviceInfo',
    'discover_devices',
    'run_device_discovery_and_diagnostics',
    'get_local_ip_and_subnet',
    'is_ip_in_same_subnet',
    'print_config_suggestions',
    'DeviceGroupManager',
    'DeviceGroup',
    'ManagedDevice',
]

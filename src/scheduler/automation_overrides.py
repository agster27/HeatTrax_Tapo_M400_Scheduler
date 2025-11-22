"""
Automation overrides management for group-level automation flags.

This module provides a mechanism to persist automation overrides per group,
allowing Web UI to temporarily override automation flags defined in config.yaml.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any


logger = logging.getLogger(__name__)


class AutomationOverrides:
    """
    Manages automation flag overrides for device groups.
    
    Overrides are stored in a JSON file and merged with base automation
    configuration from config.yaml. When no override is present for a flag,
    the base value from config.yaml is used.
    """
    
    def __init__(self, state_file: str = "state/automation_overrides.json"):
        """
        Initialize automation overrides manager.
        
        Args:
            state_file: Path to JSON file storing overrides
        """
        self.state_file = Path(state_file)
        self.overrides: Dict[str, Dict[str, bool]] = {}
        self._ensure_state_dir()
        self._load_overrides()
    
    def _ensure_state_dir(self):
        """Ensure state directory exists."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load_overrides(self):
        """Load overrides from JSON file."""
        if not self.state_file.exists():
            logger.info(f"No automation overrides file found at {self.state_file}")
            self.overrides = {}
            return
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning(f"Invalid overrides file format (expected dict): {self.state_file}")
                    self.overrides = {}
                else:
                    self.overrides = data
                    logger.info(f"Loaded automation overrides for {len(self.overrides)} group(s)")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse overrides file {self.state_file}: {e}")
            self.overrides = {}
        except Exception as e:
            logger.error(f"Failed to load overrides file {self.state_file}: {e}")
            self.overrides = {}
    
    def _save_overrides(self):
        """Save overrides to JSON file."""
        try:
            self._ensure_state_dir()
            with open(self.state_file, 'w') as f:
                json.dump(self.overrides, f, indent=2)
            logger.debug(f"Saved automation overrides to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save overrides to {self.state_file}: {e}")
    
    def get_group_overrides(self, group_name: str) -> Dict[str, bool]:
        """
        Get automation overrides for a specific group.
        
        Args:
            group_name: Name of the device group
            
        Returns:
            Dictionary of automation flag overrides (empty if none)
        """
        return self.overrides.get(group_name, {})
    
    def set_flag(self, group_name: str, flag_name: str, value: Optional[bool]):
        """
        Set or clear an automation flag override.
        
        Args:
            group_name: Name of the device group
            flag_name: Name of automation flag (e.g., 'weather_control')
            value: Boolean value to set, or None to clear the override
        """
        if value is None:
            # Clear the override
            if group_name in self.overrides:
                if flag_name in self.overrides[group_name]:
                    del self.overrides[group_name][flag_name]
                    logger.info(f"Cleared override for {group_name}.{flag_name}")
                    
                    # Remove group entry if empty
                    if not self.overrides[group_name]:
                        del self.overrides[group_name]
                        logger.debug(f"Removed empty overrides for group {group_name}")
                    
                    self._save_overrides()
        else:
            # Set the override
            if group_name not in self.overrides:
                self.overrides[group_name] = {}
            
            self.overrides[group_name][flag_name] = value
            logger.info(f"Set override for {group_name}.{flag_name} = {value}")
            self._save_overrides()
    
    def get_effective_automation(
        self, 
        group_name: str, 
        base_automation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get effective automation configuration by merging base config with overrides.
        
        Args:
            group_name: Name of the device group
            base_automation: Base automation config from config.yaml
            
        Returns:
            Merged automation configuration with overrides applied
        """
        # Start with base automation
        effective = dict(base_automation)
        
        # Apply overrides for this group
        group_overrides = self.get_group_overrides(group_name)
        for flag_name, override_value in group_overrides.items():
            if override_value is not None:
                effective[flag_name] = override_value
        
        return effective
    
    def clear_group_overrides(self, group_name: str):
        """
        Clear all overrides for a specific group.
        
        Args:
            group_name: Name of the device group
        """
        if group_name in self.overrides:
            del self.overrides[group_name]
            logger.info(f"Cleared all overrides for group {group_name}")
            self._save_overrides()
    
    def get_all_overrides(self) -> Dict[str, Dict[str, bool]]:
        """
        Get all automation overrides.
        
        Returns:
            Dictionary mapping group names to their overrides
        """
        return dict(self.overrides)

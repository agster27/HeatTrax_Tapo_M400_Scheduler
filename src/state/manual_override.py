"""Manual override state management for device groups."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class ManualOverrideManager:
    """Manages manual override state for device groups."""
    
    def __init__(self, state_file: str = "state/manual_overrides.json", timezone: str = "America/New_York"):
        """Initialize the manual override manager.
        
        Args:
            state_file: Path to JSON state file for persistence
            timezone: Timezone string for datetime handling
        """
        self.state_file = Path(state_file)
        self.timezone = ZoneInfo(timezone)
        self.state: Dict[str, dict] = {}
        
        # Create parent directories if they don't exist
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing state
        self._load_state()
        
        logger.info(f"ManualOverrideManager initialized with state file: {self.state_file}")
    
    def _load_state(self):
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.debug(f"Loaded state from {self.state_file}: {len(self.state)} override(s)")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}. Starting with empty state.")
                self.state = {}
        else:
            logger.debug(f"State file {self.state_file} does not exist. Starting with empty state.")
            self.state = {}
    
    def _save_state(self):
        """Save state to JSON file."""
        try:
            # Ensure parent directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            logger.debug(f"Saved state to {self.state_file}")
        except IOError as e:
            logger.error(f"Failed to save state file: {e}")
    
    def set_override(self, group_name: str, action: str, timeout_hours: float) -> dict:
        """Set a manual override for a device group.
        
        Args:
            group_name: Name of the device group
            action: Action to take ('on' or 'off')
            timeout_hours: Number of hours until override expires
            
        Returns:
            Dictionary with override details
            
        Raises:
            ValueError: If action is not 'on' or 'off'
        """
        if action not in ['on', 'off']:
            raise ValueError(f"Invalid action: {action}. Must be 'on' or 'off'")
        
        # Get current time with timezone awareness
        now = datetime.now(self.timezone)
        expires_at = now + timedelta(hours=timeout_hours)
        
        # Create override record
        override = {
            'active': True,
            'action': action,
            'timeout_hours': timeout_hours,
            'timestamp': now.isoformat(),
            'expires_at': expires_at.isoformat()
        }
        
        # Save to state
        self.state[group_name] = override
        self._save_state()
        
        # Log with full ISO timestamp for debugging
        logger.info(f"Set override for '{group_name}': {action} (expires: {expires_at.isoformat()})")
        
        return override.copy()
    
    def is_active(self, group_name: str) -> bool:
        """Check if an override is active for a group.
        
        Auto-clears expired overrides.
        
        Args:
            group_name: Name of the device group
            
        Returns:
            True if an active override exists, False otherwise
        """
        if group_name not in self.state:
            return False
        
        override = self.state[group_name]
        
        # Check if expired
        expires_at = datetime.fromisoformat(override['expires_at'])
        now = datetime.now(self.timezone)
        
        if now >= expires_at:
            # Expired - auto-clear
            logger.info(f"Override for '{group_name}' has expired. Auto-clearing.")
            del self.state[group_name]
            self._save_state()
            return False
        
        return True
    
    def clear_override(self, group_name: str) -> bool:
        """Clear an override for a group.
        
        Args:
            group_name: Name of the device group
            
        Returns:
            True if override was cleared, False if none existed
        """
        if group_name in self.state:
            del self.state[group_name]
            self._save_state()
            logger.info(f"Cleared override for '{group_name}'")
            return True
        
        return False
    
    def get_status(self, group_name: str) -> Optional[dict]:
        """Get the status of an override for a group.
        
        Args:
            group_name: Name of the device group
            
        Returns:
            Dictionary with override status, or None if no override exists
        """
        if not self.is_active(group_name):
            return None
        
        return self.state[group_name].copy()
    
    def get_all_status(self) -> Dict[str, dict]:
        """Get status for all active overrides.
        
        Returns:
            Dictionary mapping group names to their override status
        """
        # Clean up expired overrides
        expired_groups = []
        now = datetime.now(self.timezone)
        
        for group_name, override in self.state.items():
            expires_at = datetime.fromisoformat(override['expires_at'])
            if now >= expires_at:
                expired_groups.append(group_name)
        
        # Remove expired
        for group_name in expired_groups:
            del self.state[group_name]
        
        if expired_groups:
            self._save_state()
        
        return self.state.copy()
    
    def get_action(self, group_name: str) -> Optional[str]:
        """Get the action for an active override.
        
        Args:
            group_name: Name of the device group
            
        Returns:
            Action string ('on' or 'off'), or None if no active override
        """
        if not self.is_active(group_name):
            return None
        
        return self.state[group_name]['action']
    
    def should_clear_on_schedule(self) -> bool:
        """Check if overrides should be cleared on schedule events.
        
        Returns:
            True if overrides should be cleared on schedule events
        """
        return True
    
    def cleanup_expired_overrides(self) -> list:
        """Remove expired overrides and return list of affected groups.
        
        Returns:
            List of group names that had expired overrides removed
        """
        expired_groups = []
        now = datetime.now(self.timezone)
        
        for group_name, override in list(self.state.items()):
            expires_at = datetime.fromisoformat(override['expires_at'])
            if now >= expires_at:
                expired_groups.append(group_name)
                del self.state[group_name]
                logger.info(f"Cleaned up expired override for '{group_name}'")
        
        if expired_groups:
            self._save_state()
        
        return expired_groups

"""State management for tracking runtime and cooldown periods."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


class StateManager:
    """Manages application state for runtime tracking and persistence."""
    
    def __init__(self, state_file: str = "state/state.json"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to the state file
        """
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.device_on = False
        self.turn_on_time: Optional[datetime] = None
        self.cooldown_start: Optional[datetime] = None
        self.total_runtime_seconds = 0
        
        self._load_state()
    
    def _load_state(self):
        """Load state from file."""
        if not self.state_file.exists():
            logger.info("No existing state file found, starting fresh")
            return
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            self.device_on = data.get('device_on', False)
            
            if data.get('turn_on_time'):
                self.turn_on_time = datetime.fromisoformat(data['turn_on_time'])
            
            if data.get('cooldown_start'):
                self.cooldown_start = datetime.fromisoformat(data['cooldown_start'])
            
            self.total_runtime_seconds = data.get('total_runtime_seconds', 0)
            
            logger.info(f"Loaded state from {self.state_file}")
        except Exception as e:
            logger.error(f"Error loading state file: {e}, starting fresh")
    
    def _save_state(self):
        """Save state to file."""
        try:
            data = {
                'device_on': self.device_on,
                'turn_on_time': self.turn_on_time.isoformat() if self.turn_on_time else None,
                'cooldown_start': self.cooldown_start.isoformat() if self.cooldown_start else None,
                'total_runtime_seconds': self.total_runtime_seconds,
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state file: {e}")
    
    def mark_turned_on(self):
        """Mark device as turned on."""
        self.device_on = True
        self.turn_on_time = datetime.now()
        self._save_state()
        logger.info(f"Device marked as ON at {self.turn_on_time}")
    
    def mark_turned_off(self):
        """Mark device as turned off and calculate runtime."""
        if self.device_on and self.turn_on_time:
            runtime = (datetime.now() - self.turn_on_time).total_seconds()
            self.total_runtime_seconds += runtime
            logger.info(f"Device was ON for {runtime:.0f} seconds ({runtime/3600:.2f} hours)")
        
        self.device_on = False
        self.turn_on_time = None
        self._save_state()
        logger.info("Device marked as OFF")
    
    def start_cooldown(self):
        """Start cooldown period."""
        self.cooldown_start = datetime.now()
        self._save_state()
        logger.info(f"Started cooldown at {self.cooldown_start}")
    
    def is_in_cooldown(self, cooldown_minutes: int) -> bool:
        """
        Check if device is in cooldown period.
        
        Args:
            cooldown_minutes: Cooldown duration in minutes
            
        Returns:
            True if in cooldown, False otherwise
        """
        if not self.cooldown_start:
            return False
        
        cooldown_end = self.cooldown_start + timedelta(minutes=cooldown_minutes)
        now = datetime.now()
        
        if now < cooldown_end:
            remaining = (cooldown_end - now).total_seconds() / 60
            logger.info(f"In cooldown: {remaining:.1f} minutes remaining")
            return True
        else:
            logger.info("Cooldown period ended")
            self.cooldown_start = None
            self._save_state()
            return False
    
    def get_current_runtime_hours(self) -> float:
        """
        Get current runtime in hours.
        
        Returns:
            Current runtime in hours
        """
        if self.device_on and self.turn_on_time:
            current_runtime = (datetime.now() - self.turn_on_time).total_seconds()
            return current_runtime / 3600
        return 0
    
    def exceeded_max_runtime(self, max_runtime_hours: float) -> bool:
        """
        Check if device has exceeded maximum runtime.
        
        Args:
            max_runtime_hours: Maximum allowed runtime in hours
            
        Returns:
            True if exceeded, False otherwise
        """
        current_runtime = self.get_current_runtime_hours()
        if current_runtime >= max_runtime_hours:
            logger.warning(
                f"Maximum runtime exceeded: {current_runtime:.2f} hours "
                f"(max: {max_runtime_hours} hours)"
            )
            return True
        return False
    
    def reset_daily_stats(self):
        """Reset daily runtime statistics."""
        self.total_runtime_seconds = 0
        self._save_state()
        logger.info("Reset daily runtime statistics")

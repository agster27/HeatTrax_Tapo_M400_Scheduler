"""Forecast notification and summary module."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path


logger = logging.getLogger(__name__)


class ForecastNotifier:
    """
    Handles forecast summaries and change detection for notifications.
    
    Features:
    - Human-friendly forecast summary formatting
    - Forecast change detection (only notify on meaningful changes)
    - Persistent state for tracking last sent forecast
    """
    
    def __init__(
        self,
        notification_service: Any,
        notify_mode: str = "always",  # "always" or "on_change"
        temp_change_threshold_f: float = 5.0,  # Significant temperature change
        precip_change_threshold_mm: float = 2.0,  # Significant precipitation change
        state_file: str = "state/forecast_notification_state.json"
    ):
        """
        Initialize forecast notifier.
        
        Args:
            notification_service: NotificationService instance
            notify_mode: "always" (send on every fetch) or "on_change" (only on meaningful changes)
            temp_change_threshold_f: Temperature change threshold in Fahrenheit
            precip_change_threshold_mm: Precipitation change threshold in mm
            state_file: Path to state file for tracking last forecast
        """
        self.notification_service = notification_service
        self.notify_mode = notify_mode
        self.temp_change_threshold_f = temp_change_threshold_f
        self.precip_change_threshold_mm = precip_change_threshold_mm
        self.state_file = Path(state_file)
        
        # Load last forecast state
        self.last_forecast_hash: Optional[str] = None
        self.last_forecast_summary: Optional[Dict[str, Any]] = None
        self._load_state()
        
        logger.info(
            f"Forecast notifier initialized: mode={notify_mode}, "
            f"temp_threshold={temp_change_threshold_f}°F, "
            f"precip_threshold={precip_change_threshold_mm}mm"
        )
    
    def _load_state(self) -> None:
        """Load last forecast state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_forecast_hash = state.get('forecast_hash')
                    self.last_forecast_summary = state.get('forecast_summary')
                    logger.debug(f"Loaded forecast state: hash={self.last_forecast_hash}")
        except Exception as e:
            logger.warning(f"Failed to load forecast state: {e}")
    
    def _save_state(self) -> None:
        """Save last forecast state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                state = {
                    'forecast_hash': self.last_forecast_hash,
                    'forecast_summary': self.last_forecast_summary,
                    'last_updated': datetime.now().isoformat()
                }
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save forecast state: {e}")
    
    def _compute_forecast_hash(self, forecast_data: List[Dict[str, Any]]) -> str:
        """
        Compute a hash of the forecast for change detection.
        
        Focuses on meaningful data: temperature, precipitation probability/amount,
        and timestamps for the next 24 hours.
        
        Args:
            forecast_data: List of forecast entries
            
        Returns:
            Hash string
        """
        try:
            # Extract key fields for comparison (next 24 hours)
            now = datetime.now()
            cutoff = now + timedelta(hours=24)
            
            relevant_data = []
            for entry in forecast_data:
                try:
                    timestamp = datetime.fromisoformat(entry.get('timestamp', ''))
                    if now <= timestamp <= cutoff:
                        # Round values to reduce noise from minor fluctuations
                        relevant_data.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:00'),  # Round to hour
                            'temp': round(entry.get('temperature_f', 0), 1),
                            'precip_mm': round(entry.get('precipitation_mm', 0), 1),
                            'precip_prob': round(entry.get('precipitation_probability', 0))
                        })
                except (KeyError, ValueError):
                    continue
            
            # Hash the normalized data
            data_str = json.dumps(relevant_data, sort_keys=True)
            return hashlib.sha256(data_str.encode()).hexdigest()[:16]
        
        except Exception as e:
            logger.warning(f"Failed to compute forecast hash: {e}")
            return ""
    
    def _detect_meaningful_change(
        self,
        current_forecast: List[Dict[str, Any]],
        current_hash: str
    ) -> bool:
        """
        Detect if forecast has changed meaningfully.
        
        Args:
            current_forecast: Current forecast data
            current_hash: Hash of current forecast
            
        Returns:
            True if forecast changed meaningfully, False otherwise
        """
        # If no previous forecast, this is a meaningful change
        if not self.last_forecast_hash:
            logger.info("No previous forecast - treating as meaningful change")
            return True
        
        # If hash is different, forecast has changed
        if current_hash != self.last_forecast_hash:
            logger.info(
                f"Forecast hash changed: {self.last_forecast_hash} -> {current_hash}"
            )
            return True
        
        logger.debug("Forecast has not changed meaningfully")
        return False
    
    def format_forecast_summary(
        self,
        forecast_data: List[Dict[str, Any]],
        temperature_threshold_f: float,
        planned_actions: Optional[List[str]] = None,
        hours_to_show: int = 12
    ) -> str:
        """
        Format forecast into human-friendly plain text summary.
        
        Args:
            forecast_data: List of forecast entries
            temperature_threshold_f: Temperature threshold for decisions
            planned_actions: List of planned scheduler actions (optional)
            hours_to_show: Number of hours to include in summary
            
        Returns:
            Formatted plain text summary
        """
        try:
            lines = []
            lines.append("=" * 70)
            lines.append("WEATHER FORECAST SUMMARY")
            lines.append("=" * 70)
            lines.append("")
            
            # Current time
            now = datetime.now()
            lines.append(f"Forecast retrieved: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Temperature threshold: {temperature_threshold_f}°F")
            lines.append("")
            
            # Forecast table
            lines.append("Next " + str(hours_to_show) + " Hours:")
            lines.append("-" * 70)
            lines.append(f"{'Time':<17} {'Temp':<8} {'Feels':<8} {'Precip':<12} {'Prob':<6} {'Wind':<8} {'Condition'}")
            lines.append("-" * 70)
            
            cutoff_time = now + timedelta(hours=hours_to_show)
            entry_count = 0
            
            for entry in forecast_data:
                try:
                    timestamp = datetime.fromisoformat(entry.get('timestamp', ''))
                    
                    if timestamp > cutoff_time:
                        break
                    
                    if timestamp < now:
                        continue
                    
                    temp = entry.get('temperature_f', 0)
                    feels_like = entry.get('feels_like_f', temp)
                    precip = entry.get('precipitation_mm', 0)
                    precip_prob = entry.get('precipitation_probability', 0)
                    wind_speed = entry.get('wind_speed_mph', 0)
                    condition = entry.get('condition_text', 'Unknown')
                    
                    # Format time
                    time_str = timestamp.strftime('%m/%d %H:%M')
                    
                    # Highlight rows with precipitation and low temp
                    marker = ""
                    if precip > 0 and temp < temperature_threshold_f:
                        marker = "***"
                    
                    lines.append(
                        f"{time_str:<17} {temp:>5.1f}°F  {feels_like:>5.1f}°F  "
                        f"{precip:>6.1f}mm  {precip_prob:>4.0f}%  "
                        f"{wind_speed:>4.1f}mph  {condition:<20} {marker}"
                    )
                    
                    entry_count += 1
                
                except (KeyError, ValueError) as e:
                    logger.debug(f"Skipping invalid forecast entry: {e}")
                    continue
            
            if entry_count == 0:
                lines.append("(No forecast data available)")
            
            lines.append("-" * 70)
            lines.append("")
            lines.append("*** = Precipitation + Temperature below threshold")
            lines.append("")
            
            # Planned actions section
            if planned_actions:
                lines.append("PLANNED SCHEDULER ACTIONS:")
                lines.append("-" * 70)
                for action in planned_actions:
                    lines.append(f"  • {action}")
                lines.append("")
            else:
                lines.append("PLANNED SCHEDULER ACTIONS:")
                lines.append("-" * 70)
                lines.append("  (No specific actions planned based on this forecast)")
                lines.append("")
            
            lines.append("=" * 70)
            
            return "\n".join(lines)
        
        except Exception as e:
            logger.error(f"Failed to format forecast summary: {e}")
            return f"Error formatting forecast summary: {e}"
    
    async def notify_new_forecast(
        self,
        forecast_data: List[Dict[str, Any]],
        temperature_threshold_f: float,
        planned_actions: Optional[List[str]] = None,
        hours_to_show: int = 12
    ) -> bool:
        """
        Send forecast summary notification if appropriate.
        
        Decides whether to send based on notify_mode:
        - "always": Always sends on each call
        - "on_change": Only sends if forecast changed meaningfully
        
        Args:
            forecast_data: List of forecast entries
            temperature_threshold_f: Temperature threshold for decisions
            planned_actions: List of planned scheduler actions
            hours_to_show: Number of hours to include in summary
            
        Returns:
            True if notification was sent, False otherwise
        """
        if not self.notification_service or not self.notification_service.is_enabled():
            logger.debug("Notification service not enabled, skipping forecast notification")
            return False
        
        try:
            # Compute hash for change detection
            current_hash = self._compute_forecast_hash(forecast_data)
            
            # Check if we should send notification
            should_send = False
            
            if self.notify_mode == "always":
                should_send = True
                logger.info("Forecast notification mode: always - sending notification")
            elif self.notify_mode == "on_change":
                if self._detect_meaningful_change(forecast_data, current_hash):
                    should_send = True
                    logger.info("Forecast changed meaningfully - sending notification")
                else:
                    logger.info("Forecast has not changed meaningfully - skipping notification")
            else:
                logger.warning(f"Unknown notify_mode: {self.notify_mode} - defaulting to 'always'")
                should_send = True
            
            if not should_send:
                return False
            
            # Format summary
            summary = self.format_forecast_summary(
                forecast_data,
                temperature_threshold_f,
                planned_actions,
                hours_to_show
            )
            
            # Send notification
            await self.notification_service.notify(
                event_type="forecast_summary",
                message="New weather forecast data received",
                details={
                    'forecast_summary': summary,
                    'forecast_hours': hours_to_show,
                    'temperature_threshold_f': temperature_threshold_f,
                    'notify_mode': self.notify_mode,
                    'forecast_hash': current_hash
                }
            )
            
            # Update state
            self.last_forecast_hash = current_hash
            self.last_forecast_summary = {
                'hash': current_hash,
                'timestamp': datetime.now().isoformat()
            }
            self._save_state()
            
            logger.info("Forecast summary notification sent successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send forecast notification: {e}", exc_info=True)
            return False

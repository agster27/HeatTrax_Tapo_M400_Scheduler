# Health Check and Notification System

This document describes the health check and notification features added to the HeatTrax Tapo M400 Scheduler.

## Overview

The scheduler now includes:
1. **Automatic Device Discovery** at startup
2. **Periodic Health Checks** to monitor device connectivity
3. **Notification System** for alerts about device issues

## Device Discovery

### What It Does

At startup, the scheduler automatically:
- Discovers all Kasa/Tapo devices on the local network
- Logs detailed information about each device:
  - IP address
  - MAC address
  - Device alias (friendly name)
  - Model number
  - Current state (ON/OFF)
  - Signal strength (RSSI) if available
  - Available features
  - Hardware and software versions
- Validates the configured device IP
- Auto-selects the device if only one is found
- Provides configuration suggestions if multiple devices are detected

### Configuration

Device discovery runs automatically at startup with no configuration required. Discovery uses UDP broadcast on port 9999 with a 10-second timeout.

### Example Output

```
================================================================================
DEVICE AUTO-DISCOVERY AND DIAGNOSTICS
================================================================================

============================================================
Starting device discovery...
============================================================
Scanning local network (timeout: 10s)
Discovery completed - found 2 device(s)

Device: Living Room Outlet
  IP: 192.168.1.100
  MAC: AA:BB:CC:DD:EE:FF
  Model: Tapo P110
  State: OFF
  RSSI: -45 dBm
  Features: energy_monitoring
  HW Version: 1.0
  SW Version: 1.2.3
------------------------------------------------------------

Device: Garage Plug
  IP: 192.168.1.101
  MAC: 11:22:33:44:55:66
  Model: Tapo P100
  State: ON
  HW Version: 1.0
  SW Version: 1.1.0
------------------------------------------------------------

✓ Configured device found and validated!
  Using: Living Room Outlet at 192.168.1.100

================================================================================
DEVICE DISCOVERY COMPLETE
================================================================================
```

## Health Check System

### What It Does

The health check system runs in the background and:
- Periodically rediscovers devices on the network
- Compares current state with last known state
- Detects and logs changes:
  - Lost devices (devices that were present but are now missing)
  - Found devices (new devices that appeared)
  - Device alias changes
  - Device IP changes (detected by MAC address tracking)
  - Configuration mismatches
- Attempts automatic re-initialization after consecutive failures
- Sends notifications for important events (if enabled)

### Configuration

Configure via `config.yaml`:

```yaml
health_check:
  interval_hours: 24           # How often to run (default: 24 hours)
  max_consecutive_failures: 3  # Max failures before re-init (default: 3)
```

Or via environment variables:

```bash
HEATTRAX_HEALTH_CHECK_INTERVAL_HOURS=24
HEATTRAX_HEALTH_CHECK_MAX_FAILURES=3
```

### Container Restart Pause

When critical failures occur that would cause the container to exit and restart, the application pauses for a configurable duration to allow console troubleshooting:

```yaml
reboot:
  pause_seconds: 60  # Pause before container restart (default: 60)
```

Or via environment variable:

```bash
REBOOT_PAUSE_SECONDS=60
```

The pause:
- Defaults to 60 seconds
- Displays clear countdown messages in logs and console output
- Allows time to inspect logs and diagnose issues before the container restarts
- Can be set to 0 to disable the pause
- Is triggered on critical startup failures or unrecoverable errors

This is particularly useful in Docker deployments with `restart: unless-stopped` where immediate restarts can make troubleshooting difficult.

### Behavior

1. **First check** runs after the configured interval (e.g., 24 hours after startup)
2. **Subsequent checks** run every interval hours
3. **Consecutive failures** are tracked:
   - If a device is not found during a check, the failure counter increments
   - If devices are found on the next check, the counter resets to 0
   - After reaching `max_consecutive_failures`, the scheduler attempts to reinitialize the device connection
4. **Automatic re-initialization**:
   - Closes existing device connection
   - Creates new connection
   - Sends notification on success or failure (if notifications enabled)

### Example Output

```
============================================================
PERIODIC HEALTH CHECK - 2025-11-16 12:00:00
============================================================
============================================================
Starting device discovery...
============================================================
Scanning local network (timeout: 10s)
Discovery completed - found 2 device(s)

✓ Configured device OK: Living Room Outlet at 192.168.1.100
✓ New device discovered: Kitchen Outlet at 192.168.1.102

============================================================
Health check completed - 3 device(s) found
============================================================
```

## Notification System

### What It Does

The notification system sends alerts for important events:

**Event Types:**
- `device_lost` - Configured device not found during health check
- `device_found` - New device discovered on network
- `device_changed` - Device alias or properties changed
- `device_ip_changed` - Device MAC/IP mapping changed (CRITICAL - may indicate IP reassignment)
- `connectivity_lost` - Failed to reinitialize device connection after health check failures
- `connectivity_restored` - Device connection restored successfully after failures

**Notification Providers:**
- **Email** - Send notifications via SMTP
- **Webhook** - Send JSON POST requests to a webhook URL

### Configuration

**Important:** Notifications are **disabled by default**. You must explicitly enable them.

#### Email Notifications

Configure via `config.yaml`:

```yaml
notifications:
  email:
    enabled: true  # Must be true to enable
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_username: "your_email@gmail.com"
    smtp_password: "your_app_password"  # For Gmail, use App Password
    from_email: "your_email@gmail.com"
    to_emails:
      - "recipient1@example.com"
      - "recipient2@example.com"
    use_tls: true  # Usually true for port 587
```

Or via environment variables:

```bash
HEATTRAX_NOTIFICATION_EMAIL_ENABLED=true
HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST=smtp.gmail.com
HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT=587
HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME=your_email@gmail.com
HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD=your_app_password
HEATTRAX_NOTIFICATION_EMAIL_FROM=your_email@gmail.com
HEATTRAX_NOTIFICATION_EMAIL_TO=recipient1@example.com,recipient2@example.com
HEATTRAX_NOTIFICATION_EMAIL_USE_TLS=true
```

**Gmail Setup:**
1. Enable 2-factor authentication on your Google account
2. Generate an [App Password](https://support.google.com/accounts/answer/185833)
3. Use the App Password (not your regular password) in the configuration

#### Webhook Notifications

Configure via `config.yaml`:

```yaml
notifications:
  webhook:
    enabled: true  # Must be true to enable
    url: "https://your-webhook-url.com/notifications"
```

Or via environment variables:

```bash
HEATTRAX_NOTIFICATION_WEBHOOK_ENABLED=true
HEATTRAX_NOTIFICATION_WEBHOOK_URL=https://your-webhook-url.com/notifications
```

**Webhook Payload Format:**

```json
{
  "event_type": "device_lost",
  "message": "Configured device at 192.168.1.100 not found during health check",
  "timestamp": "2025-11-16T12:00:00.000Z",
  "details": {
    "configured_ip": "192.168.1.100",
    "consecutive_failures": 2,
    "last_seen": "2025-11-15T12:00:00.000Z"
  },
  "source": "heattrax_scheduler"
}
```

### Testing Notifications

To test your notification configuration:

1. Enable notifications in your config
2. Set `HEATTRAX_HEALTH_CHECK_INTERVAL_HOURS=0.1` (6 minutes) for faster testing
3. Restart the scheduler
4. Disconnect your device or change its IP
5. Wait for the next health check
6. You should receive a notification about the device being lost

## Extensibility

The notification system is designed to be extensible. To add a new notification provider:

1. Create a new class that inherits from `NotificationProvider`
2. Implement the `send()` method
3. Update `create_notification_service_from_config()` to instantiate your provider
4. Add configuration options to `config.example.yaml` and environment variables

Example:

```python
class SlackNotificationProvider(NotificationProvider):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    async def send(self, event_type: str, message: str, details: Dict[str, Any]) -> bool:
        # Implement Slack-specific notification logic
        pass
```

## Troubleshooting

### Device Discovery Not Finding Devices

1. Ensure devices are powered on and connected to network
2. Verify the scheduler is on the same network as devices
3. Check firewall rules (UDP port 9999 must be accessible)
4. Try increasing the discovery timeout (edit `device_discovery.py`)

### Health Checks Failing

1. Check network connectivity
2. Verify device is still at the configured IP address
3. Review logs for specific error messages
4. Consider increasing `max_consecutive_failures` if network is unstable

### Email Notifications Not Working

1. Verify SMTP credentials are correct
2. For Gmail: Use an App Password, not your regular password
3. Check SMTP server and port are correct
4. Try `use_tls: false` if connection fails with TLS
5. Review logs for SMTP error messages

### Webhook Notifications Not Working

1. Verify webhook URL is accessible from the scheduler
2. Check webhook server logs for error messages
3. Ensure webhook accepts JSON POST requests
4. Review scheduler logs for HTTP error codes

## Security Considerations

1. **Email Credentials**: Store SMTP passwords in environment variables, not in config files
2. **Webhook URLs**: Use HTTPS webhooks to encrypt notification data
3. **Sensitive Data**: Notification messages may contain IP addresses and device information
4. **Log Files**: Notification logs do not include passwords, but do include email addresses

## Performance Impact

- **Device Discovery**: Runs once at startup (~10 seconds)
- **Health Checks**: Run periodically (default: every 24 hours, ~10 seconds each)
- **Notifications**: Minimal impact (async operations)

Total overhead: <1% of CPU time with default settings.

# Health Check and Notification System

This document describes the health check and notification features added to the HeatTrax Tapo M400 Scheduler.

## Overview

The scheduler now includes:
1. **HTTP Health Check Endpoints** for monitoring application and weather health
2. **Automatic Device Discovery** at startup
3. **Periodic Health Checks** to monitor device connectivity
4. **Notification System** for alerts about device issues

## HTTP Health Check Endpoints

The scheduler provides HTTP endpoints for monitoring application health. These are useful for:
- Container orchestration systems (Docker, Kubernetes)
- Load balancers and reverse proxies
- Monitoring tools (Prometheus, Nagios, etc.)
- Manual health verification during deployment

### Configuration

Health server settings can be configured via environment variables or YAML:

```yaml
# config.yaml
health_server:
  enabled: true           # Enable/disable HTTP server (default: true)
  host: "0.0.0.0"        # Host to bind to (default: 0.0.0.0)
  port: 8080             # Port to listen on (default: 8080)
```

Environment variables:
```bash
HEATTRAX_HEALTH_SERVER_ENABLED=true
HEATTRAX_HEALTH_SERVER_HOST=0.0.0.0
HEATTRAX_HEALTH_SERVER_PORT=8080
```

### Endpoints

#### `GET /health` - Basic Application Health

Returns basic health status indicating the application is running.

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00.123456",
  "service": "heattrax_scheduler"
}
```

This endpoint always returns 200 if the application is running, regardless of weather or device status.

#### `GET /health/weather` - Weather-Specific Health Check

Returns detailed weather system health status.

**When weather is disabled** (`HEATTRAX_WEATHER_ENABLED=false`):
```json
{
  "status": "disabled",
  "weather_enabled": false,
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

**When weather is enabled and working** (200 OK):
```json
{
  "status": "ok",
  "weather_enabled": true,
  "timestamp": "2024-01-15T10:30:00.123456",
  "provider": "open-meteo",
  "current_conditions": {
    "temperature_f": 35.5,
    "description": "Clear"
  },
  "precipitation_forecast": {
    "expected": true,
    "time": "2024-01-15T14:00:00",
    "temperature_f": 33.0
  }
}
```

**When weather API times out** (503 Service Unavailable):
```json
{
  "status": "timeout",
  "weather_enabled": true,
  "timestamp": "2024-01-15T10:30:00.123456",
  "provider": "open-meteo",
  "message": "Weather API request timed out"
}
```

**When weather API has an error** (503 Service Unavailable):
```json
{
  "status": "error",
  "weather_enabled": true,
  "timestamp": "2024-01-15T10:30:00.123456",
  "provider": "open-meteo",
  "message": "Connection refused"
}
```

### Usage Examples

**Using curl:**
```bash
# Basic health check
curl http://localhost:8080/health

# Weather health check
curl http://localhost:8080/health/weather
```

**Using wget:**
```bash
wget -qO- http://localhost:8080/health
```

**Docker health check:**
```yaml
# docker-compose.yml
services:
  heattrax:
    # ... other config ...
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**Kubernetes readiness probe:**
```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
```

### Disabling the Health Server

To disable the HTTP health server entirely:

```bash
HEATTRAX_HEALTH_SERVER_ENABLED=false
```

Or in `config.yaml`:
```yaml
health_server:
  enabled: false
```


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
HEATTRAX_REBOOT_PAUSE_SECONDS=60
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
- `weather_mode_enabled` - Weather-based scheduling enabled on startup (includes current conditions and forecast)
- `weather_mode_disabled` - Weather-based scheduling disabled on startup (using fixed schedule behavior)

**Notification Providers:**
- **Email** - Send notifications via SMTP
- **Webhook** - Send JSON POST requests to a webhook URL

### Configuration

**Important:** Notifications are **disabled by default**. You must explicitly enable them.

#### Global Notification Settings

```yaml
notifications:
  # Global settings
  required: false              # If true, misconfigured enabled providers cause startup failure
  test_on_startup: false       # If true, send test notification on successful startup
  
  # Per-event routing (optional)
  # If not specified, all events go to all enabled providers
  routing:
    device_lost:
      email: true              # Send to email
      webhook: true            # Send to webhook
    device_found:
      email: false             # Don't send to email
      webhook: true            # Only send to webhook
    device_ip_changed:
      email: true              # Critical events to both
      webhook: true
```

Environment variables:
```bash
HEATTRAX_NOTIFICATIONS_REQUIRED=false
HEATTRAX_NOTIFICATIONS_TEST_ON_STARTUP=false
```

**Behavior:**
- **`notifications.required`**: Controls whether misconfigured enabled providers cause startup failure
  - `false` (default): Log errors but allow startup to continue
  - `true`: Startup fails if an enabled provider is misconfigured or unreachable
- **`notifications.test_on_startup`**: Send test notification after successful validation
  - `false` (default): No test notification
  - `true`: Send test notification to all enabled providers on startup
- **`notifications.routing`**: Control which events go to which providers
  - If not specified: All events go to all enabled providers (default behavior)
  - If specified for an event: Only send to providers marked `true` for that event
  - Unknown event types are sent to all providers

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

### Startup Validation

When the scheduler starts, it performs validation of notification configuration:

1. **Configuration Validation**: Checks that all required fields are present for enabled providers
   - Email: `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `from_email`, `to_emails`
   - Webhook: `url` (must be valid HTTP/HTTPS URL)

2. **Connectivity Testing**: Attempts lightweight connection to each enabled provider
   - Email: Connects to SMTP server and authenticates
   - Webhook: Sends HEAD request to verify endpoint is reachable

3. **Test Notification** (optional): If `test_on_startup: true`, sends test notification

**Behavior based on `notifications.required` flag:**
- `required: false` (default):
  - Validation errors are logged as ERROR
  - Startup continues even if providers fail validation
  - Failed providers are not used for notifications
- `required: true`:
  - Validation errors cause startup failure
  - Ensures notifications will work before scheduler starts
  - Use this if notifications are critical for your deployment

**Logging Behavior:**
- Disabled providers: Log single INFO message (no errors about missing config)
- Enabled but misconfigured: Log clear ERROR with guidance on how to fix
- Transient notification failures at runtime: Log at WARNING level (not ERROR)

### Testing Notifications

**Option 1: Use `test_on_startup` flag**

```yaml
notifications:
  test_on_startup: true
  email:
    enabled: true
    # ... email config ...
```

Restart the scheduler and check for test notification.

**Option 2: Trigger health check event**

To test your notification configuration:

1. Enable notifications in your config
2. Set `test_on_startup: true` or wait for a health check event
3. To trigger faster: Set `HEATTRAX_HEALTH_CHECK_INTERVAL_HOURS=0.1` (6 minutes)
4. Disconnect your device or change its IP
5. Wait for the next health check
6. You should receive a notification about the device being lost

### Per-Event Routing Examples

**Example 1: Email for critical events only**
```yaml
notifications:
  email:
    enabled: true
    # ... email config ...
  webhook:
    enabled: true
    # ... webhook config ...
  
  routing:
    device_lost:
      email: true   # Email and webhook
      webhook: true
    device_ip_changed:
      email: true   # Email and webhook (critical)
      webhook: true
    device_found:
      email: false  # Webhook only
      webhook: true
    connectivity_restored:
      email: false  # Webhook only
      webhook: true
```

**Example 2: Email only for specific events**
```yaml
notifications:
  email:
    enabled: true
    # ... email config ...
  
  routing:
    device_lost:
      email: true
    device_ip_changed:
      email: true
    # All other events won't trigger email (no webhook configured)
```

## Extensibility

The notification system is designed to be extensible. To add a new notification provider:

1. Create a new class that inherits from `NotificationProvider`
2. Implement the required abstract methods:
   - `send()`: Send a notification
   - `validate_config()`: Validate provider configuration
   - `test_connectivity()`: Test connection to provider
3. Update `create_notification_service_from_config()` to instantiate your provider
4. Add configuration options to `config.example.yaml` and environment variables
5. Add the provider to routing configuration if using per-event routing

Example:

```python
class SlackNotificationProvider(NotificationProvider):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def validate_config(self) -> Tuple[bool, Optional[str]]:
        if not self.webhook_url:
            return False, "webhook_url is required"
        return True, None
    
    async def test_connectivity(self, timeout: float = 5.0) -> Tuple[bool, Optional[str]]:
        try:
            # Test connection to Slack
            async with aiohttp.ClientSession() as session:
                async with session.get(self.webhook_url, timeout=timeout) as response:
                    return response.status < 500, None
        except Exception as e:
            return False, str(e)
    
    async def send(self, event_type: str, message: str, details: Dict[str, Any]) -> bool:
        # Implement Slack-specific notification logic
        payload = {
            "text": f"*{event_type}*\n{message}",
            "blocks": [...]
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.webhook_url, json=payload) as response:
                return response.status < 400
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
3. Check `notifications.email.enabled` is set to `true`
4. Review startup logs for validation errors
5. Test connectivity with `test_on_startup: true`
6. Ensure firewall allows outbound SMTP connections

### Webhook Notifications Not Working

1. Verify the webhook URL is correct and reachable
2. Check `notifications.webhook.enabled` is set to `true`
3. Review startup logs for validation errors
4. Test connectivity with `test_on_startup: true`
5. Check webhook endpoint logs for received requests
6. Ensure firewall allows outbound HTTPS connections

### Notifications Required but Startup Failing

If you've set `notifications.required: true` and startup is failing:

1. Check startup logs for detailed error messages
2. Verify all required fields are configured for enabled providers
3. Test SMTP/webhook connectivity manually
4. Temporarily set `required: false` to diagnose issues
5. Use `test_on_startup: true` to verify configuration before making it required
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

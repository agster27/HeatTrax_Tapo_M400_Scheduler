# Health Check and Notification System

This document describes the health check and notification features added to the HeatTrax Tapo M400 Scheduler.

## Overview

The scheduler now includes:
1. **HTTP Health Check Endpoints** for monitoring application and weather health
2. **Automatic Device Discovery** at startup
3. **Periodic Health Checks** to monitor device connectivity
4. **Notification System** for alerts about device issues
5. **Web UI Health Dashboard** for visual monitoring of system and device health

## Web UI Health Dashboard

The Web UI includes a dedicated "Health" tab that provides a visual interface for monitoring system health and device expectations.

### Features

**Health Summary**
- Quick overview card showing:
  - System health status (✅ or ❌)
  - Configuration loaded status
  - Number of active device groups
  - Time since last weather fetch

**Health Checks**
- Displays detailed system health information:
  - System status (ok/error)
  - Current timestamp
  - Configuration loaded confirmation
- Data fetched from `/api/health` endpoint

**Device Health**
- Visual grid showing all configured devices
- Each device card displays:
  - Device name and group
  - IP address and outlet number
  - Current state (on/off/unknown)
  - Expected state (on/off) based on scheduler logic
  - Expected ON/OFF times (from schedule or weather forecast)
  - Last state change timestamp
  - Any recent errors
- **Color coding**:
  - Green border: Device is in expected state
  - Red border: Mismatch between current and expected state

### Device Expectations

The Health tab displays device expectations calculated by the scheduler based on:

1. **Unified schedules**: If a device group has `schedules:` array configured, expectations are derived from the schedule times, priorities, and conditions

2. **Weather-based control**: If `precipitation_control` is enabled, expectations are based on:
   - Precipitation forecast times
   - Lead time (when to turn on before precipitation)
   - Trailing time (when to turn off after precipitation ends)

3. **Morning mode**: For devices with `morning_mode` enabled, expectations include morning hours when temperature is below threshold

The device expectations are computed in real-time when the Health tab is accessed, providing current state vs expected state for monitoring and troubleshooting.

#### Device State Comparison

The Health tab provides a comparison between the actual device state and what the scheduler expects:

- **Current State**: The actual physical state of the device, queried directly from the hardware
  - Shows ON/OFF/UNKNOWN based on real-time device communication
  - May differ from expected state due to manual control, network issues, or external changes
  
- **Expected State**: What the scheduler's automation logic says the device should be
  - Calculated based on active schedules, weather conditions, and automation rules
  - Shows what state the scheduler will try to enforce on its next cycle
  
- **Mismatch Detection**: When Current ≠ Expected, a warning (⚠️) is displayed
  - Common causes: manual overrides, external control, device communication failures
  - The scheduler will attempt to correct mismatches on its next evaluation cycle

### Accessing the Health Dashboard

1. Open the Web UI at `http://localhost:4328` (or your configured host/port)
2. Click the "Health" tab in the navigation bar
3. Click "Refresh" to update health data
4. Review health summary, health checks, and device health information

The Health dashboard complements the health check API endpoints by providing a user-friendly visual interface for monitoring.

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


## Device Discovery and Initialization

### What It Does

At startup, the scheduler automatically:
- Discovers all Kasa/Tapo devices on the local network (legacy single-device mode)
- For multi-device/group mode: Initializes each configured device with Tapo authentication
- Logs detailed information about each device:
  - IP address
  - MAC address (in legacy mode)
  - Device alias (friendly name)
  - Model number
  - Current state (ON/OFF)
  - Number of outlets (for multi-outlet devices like EP40M)
  - Signal strength (RSSI) if available
  - Available features
  - Hardware and software versions
- Validates the configured device IP
- Auto-selects the device if only one is found (legacy mode)
- Provides configuration suggestions if multiple devices are detected

### Device Initialization Timeout

**NEW:** The scheduler now includes configurable timeout settings for Tapo device initialization to handle slow network responses or busy devices.

**Default Timeout:** 30 seconds (increased from the python-kasa default to handle slower Tapo responses)

**Per-Device Configuration:**

You can customize the timeout for specific devices that are slow to respond:

```yaml
devices:
  credentials:
    username: your_tapo_email
    password: your_tapo_password
  groups:
    my_group:
      enabled: true
      items:
        - name: kitchen
          ip_address: 10.0.50.74
          outlets: [0, 1]
          discovery_timeout_seconds: 60  # Increase timeout for slow device
```

**When to Increase Timeout:**

Increase the timeout if:
- Your device is on a slow or congested network
- The device consistently times out during initialization but is reachable
- Container logs show "Timeout after 30s" errors but manual testing works
- The device is an EP40M or other multi-outlet device (these can be slower)

**Initialization Failure Handling:**

When device initialization fails:
1. The error is logged with full details (exception type, message, timeout duration)
2. The device is tracked as "failed to initialize" 
3. The group continues to initialize other devices (partial failures don't stop other devices)
4. The Web UI Health and Device Control tabs show clear initialization failure status
5. The `/api/devices/status` endpoint includes initialization summary and per-device errors

**Troubleshooting Initialization Failures:**

If you see "Timeout after Ns while initializing device" errors:

1. **Verify Network Connectivity:**
   ```bash
   # From inside the container
   ping -c 3 10.0.50.74
   ```

2. **Test python-kasa Directly:**
   ```bash
   # Inside container
   python3 -c "
   import asyncio
   from kasa import Discover
   async def test():
       dev = await Discover.discover_single('10.0.50.74', username='your_email', password='your_password')
       await dev.update()
       print(f'Success: {dev.model}')
   asyncio.run(test())
   "
   ```

3. **Increase Timeout:** Add `discovery_timeout_seconds: 60` to device config

4. **Check Device Load:** Multi-outlet devices with active outlets may respond slower

5. **Check Container Logs:** Look for detailed error messages with exception types

### Configuration

Device discovery runs automatically at startup with no configuration required. Discovery uses UDP broadcast on port 9999 with a 10-second timeout (legacy mode) or Tapo-authenticated discovery with configurable timeout (multi-device mode).

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
- `weather_service_recovered` - Weather service came back online after being offline
- `weather_service_degraded` - Weather service offline but using valid cached data
- `weather_service_offline` - Weather service offline with no valid cached data (reverting to static schedule)
- `weather_service_outage_alert` - Weather service has been offline longer than alert threshold
- `forecast_summary` - New forecast data fetched (human-friendly summary email)

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
HEATTRAX_NOTIFICATIONS_TEST_ON_STARTUP=false
```

**Behavior:**
- **`notifications.test_on_startup`**: Send test notification after successful validation
  - `false` (default): No test notification
  - `true`: Send test notification to all enabled providers on startup
- **`notifications.routing`**: Control which events go to which providers
  - If not specified: All events go to all enabled providers (default behavior)
  - If specified for an event: Only send to providers marked `true` for that event
  - Unknown event types are sent to all providers

**Note**: The application will always continue to start even if notification providers are misconfigured. Notification failures are logged but never prevent application startup.

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

#### Forecast Summary Notifications

**NEW:** The scheduler can send human-friendly forecast summaries via email/webhook after successfully fetching weather data.

**Features:**
- Plain-text email format with forecast table
- Highlights rows with precipitation + low temperature
- Shows next N hours of forecast (configurable)
- Includes planned scheduler actions based on forecast
- Two notification modes:
  - `always`: Send on every successful forecast fetch
  - `on_change`: Only send when forecast changes meaningfully

**Configuration via `config.yaml`:**

```yaml
notifications:
  forecast:
    enabled: false  # Must be true to enable (default: false)
    notify_mode: "always"  # "always" or "on_change"
    temp_change_threshold_f: 5.0  # Temperature change threshold (°F) for "on_change" mode
    precip_change_threshold_mm: 2.0  # Precipitation change threshold (mm) for "on_change" mode
    state_file: "state/forecast_notification_state.json"  # State persistence file
```

Or via environment variables:

```bash
HEATTRAX_NOTIFICATION_FORECAST_ENABLED=true
HEATTRAX_NOTIFICATION_FORECAST_NOTIFY_MODE=always  # or "on_change"
```

**Notification Modes:**

- **`always` mode (default):**
  - Sends forecast summary on every successful weather fetch
  - Useful for regular updates regardless of change
  - May result in frequent emails (every 10 minutes by default)
  - Recommended for initial testing

- **`on_change` mode (recommended):**
  - Compares current forecast to last sent forecast
  - Only sends if forecast has changed meaningfully
  - Reduces notification frequency
  - Based on 24-hour forecast window hash
  - Recommended for production use

**Change Detection:**

The `on_change` mode uses a hash of the following data from the next 24 hours:
- Hourly timestamps
- Temperature (rounded to 0.1°F)
- Precipitation amount (rounded to 0.1mm)
- Precipitation probability (rounded to nearest %)

If the hash changes, the forecast is considered "meaningfully changed" and a notification is sent.

**Example Forecast Summary Email:**

```
======================================================================
WEATHER FORECAST SUMMARY
======================================================================

Forecast retrieved: 2025-11-16 15:30:00
Temperature threshold: 34.0°F

Next 12 Hours:
----------------------------------------------------------------------
Time              Temp     Feels    Precip       Prob   Wind     Condition
----------------------------------------------------------------------
11/16 16:00        35.0°F   32.0°F     0.0mm     0%   5.0mph  Clear                
11/16 17:00        33.0°F   29.0°F     2.5mm    80%  10.0mph  Light Snow           ***
11/16 18:00        31.0°F   26.0°F     5.0mm    90%  12.0mph  Snow                 ***
11/16 19:00        30.0°F   25.0°F     8.0mm    95%  15.0mph  Heavy Snow           ***
11/16 20:00        32.0°F   28.0°F     3.0mm    70%  10.0mph  Light Snow           ***
11/16 21:00        34.0°F   31.0°F     1.0mm    50%   8.0mph  Cloudy               
----------------------------------------------------------------------

*** = Precipitation + Temperature below threshold

PLANNED SCHEDULER ACTIONS:
----------------------------------------------------------------------
  • Turn on heated mats at 16:30 (60 min before precipitation)
  • Keep mats on during precipitation period (17:00-21:00)
  • Turn off mats at 22:00 (60 min after precipitation ends)

======================================================================
```

**Routing:**

Forecast summaries respect the per-event routing configuration. Add `forecast_summary` to your routing:

```yaml
notifications:
  routing:
    forecast_summary:
      email: true     # Send forecast summaries via email
      webhook: false  # Don't send via webhook (too verbose for webhook services)
```

**Performance Impact:**

- Forecast notifications are sent asynchronously (non-blocking)
- `always` mode: One notification per weather fetch (default: every 10 minutes)
- `on_change` mode: Only when forecast changes (typically a few times per day)
- Each notification takes ~1-2 seconds for email delivery

### Startup Validation

When the scheduler starts, it performs validation of notification configuration:

1. **Configuration Validation**: Checks that all required fields are present for enabled providers
   - Email: `smtp_host`, `smtp_port`, `smtp_username`, `smtp_password`, `from_email`, `to_emails`
   - Webhook: `url` (must be valid HTTP/HTTPS URL)

2. **Connectivity Testing**: Attempts lightweight connection to each enabled provider
   - Email: Connects to SMTP server and authenticates
   - Webhook: Sends HEAD request to verify endpoint is reachable

3. **Test Notification** (optional): If `test_on_startup: true`, sends test notification

**Behavior:**
- Validation errors are logged at ERROR level with detailed troubleshooting information
- Startup always continues even if providers fail validation
- Failed providers are not used for notifications
- Notifications are treated as a non-critical feature

**Logging Behavior:**
- Disabled providers: Log single INFO message (no errors about missing config)
- Enabled but misconfigured: Log clear ERROR with guidance on how to fix
- Transient notification failures at runtime: Log at ERROR level with detailed error information

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

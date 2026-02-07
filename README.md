# HeatTrax Tapo M400 Scheduler

Automated control system for TP-Link Kasa/Tapo smart plugs to manage heated outdoor mats and other devices based on weather conditions and schedules. The system monitors weather forecasts and automatically controls device groups with weather-based automation (heated mats) and schedule-based automation (Christmas lights, etc.).

## 📚 Documentation

### Core Documentation
- **[Quick Start Guide](docs/QUICKSTART.md)** - 5-minute setup guide
- **[Setup Instructions](docs/SETUP.md)** - Detailed installation and configuration
- **[Scheduling Guide](SCHEDULING.md)** - **NEW!** Comprehensive guide to the unified conditional scheduling system
  - System architecture and schedule evaluation
  - Clock-based and solar-based schedules
  - Weather conditions and priority system
  - Migration examples from old configurations
  - API documentation with examples
  - Troubleshooting and best practices

### Feature Documentation
- **[API Reference](docs/API_REFERENCE.md)** - **NEW!** Complete REST API documentation with all endpoints
- **[Web UI Guide](docs/WEB_UI_GUIDE.md)** - Web interface and JSON API reference
- **[Manual Device Control](docs/MANUAL_CONTROL.md)** - Manual control of devices and outlets via Web UI
- **[Environment Variables Reference](docs/ENVIRONMENT_VARIABLES.md)** - Complete environment variable documentation
- **[Health Checks & Notifications](docs/HEALTH_CHECK.md)** - Device monitoring and notification system
- **[Logging Guide](docs/LOGGING.md)** - Troubleshooting and logging information
- **[Changelog](docs/CHANGELOG.md)** - Version history and release notes

See the [complete documentation index](docs/README.md) for more information.

## 🎉 Latest Features

HeatTrax Scheduler includes powerful features for automated device control:

- ✅ **Unified Conditional Scheduling** - Advanced scheduling system combining multiple paradigms
  - Clock-based schedules (fixed times like "06:00")
  - Solar-based schedules (sunrise/sunset with offsets)
  - Weather conditions (temperature, precipitation, **black ice risk**)
  - Priority system (critical, normal, low)
  - Day-of-week filtering
  - See the **[Scheduling Guide](SCHEDULING.md)** for complete documentation
- ✅ **Black Ice Detection** - Automatically detect black ice formation conditions
  - Monitors temperature, dew point spread, and humidity
  - Activates mats even without precipitation when conditions favor black ice
  - Configurable thresholds for temperature, dew point spread, and humidity
  - Visual indicators in Web UI when black ice risk detected
- ✅ **Web UI & JSON API** for monitoring and configuration
- ✅ **Real-time status** of devices, weather, and scheduler
- ✅ **Manual device control** - Turn devices and outlets on/off from the Health page
- ✅ **Configuration editor** with validation and hot-reload
- ✅ **Network accessible** - binds to `0.0.0.0` by default (configure `bind_host: 127.0.0.1` for localhost-only)
- ✅ **Multi-device group support** with independent automation rules
- ✅ **Weather resilience** with caching and automatic recovery
- ✅ **Comprehensive notifications** via email and webhook
- ✅ **HTTP health endpoints** for container orchestration
- ✅ **Full environment variable configuration** for Docker/Portainer
- ✅ **Extensive documentation** and examples

See [docs/CHANGELOG.md](docs/CHANGELOG.md) for complete release details.

## 🚀 Quick Start

Want to get started quickly? See the [Quick Start Guide](docs/QUICKSTART.md) for a 5-minute setup.

### Accessing the Web UI

After starting the container:

1. Open your browser to `http://localhost:4328` (or the host/port you configured)
2. View real-time system status and device information
3. Edit configuration directly in the browser with validation
4. **Auto-restart on save**: Configuration changes trigger an automatic container restart to apply all settings immediately

**Network Access**: By default, the web UI binds to `0.0.0.0:4328`, making it accessible from other machines on your network when Docker ports are mapped. This is the typical Docker deployment pattern. To restrict access to localhost only:
- Set environment variable: `HEATTRAX_WEB_HOST=127.0.0.1` (restricts to localhost)
- Or configure in `config.yaml`: `web.bind_host: 127.0.0.1`
- Change port with: `HEATTRAX_WEB_PORT=8080` (environment) or `web.port: 8080` (YAML)

**Security Note**: The web UI is accessible from other machines on your network by default. Do not expose this service directly to the internet. Keep it on your internal network, or place it behind a reverse proxy with authentication. See the [Mobile Control Interface](#mobile-control-interface) section for PIN-based authentication for mobile control.

**Restart Policy**: The auto-restart feature requires Docker's restart policy (e.g., `restart: always` in docker-compose.yml). See [WEB_UI_GUIDE.md](docs/WEB_UI_GUIDE.md) for details.

## Mobile Control Interface

HeatTrax now includes a mobile-optimized web interface for remote manual control of your heating mats directly from your smartphone.

### Key Features

- 🔥 **Quick ON/OFF Control**: Large touch-friendly buttons optimized for mobile devices
- 📱 **iPhone Optimized**: Responsive design that works beautifully on all mobile devices
- 🔐 **PIN Authentication**: Secure access with configurable PIN protection
- ⏱️ **Auto-Return to Schedule**: Manual overrides automatically expire after a configurable timeout (default 3 hours)
- 🌡️ **Real-time Status**: View current mat status and temperature
- 🌓 **Dark Mode Support**: Automatically adapts to your device's theme preference
- 🔄 **Auto-Refresh**: Status updates every 10 seconds

### Setup

1. **Configure PIN** in your `config.yaml`:
   ```yaml
   web:
     enabled: true
     port: 4328
     pin: "1234"  # Change to your secure PIN
     manual_override_timeout_hours: 3  # Default override timeout
   ```

2. **Access the Control Interface**:
   - On your local network: `http://your-server-ip:4328/control`
   - First visit will prompt for PIN authentication
   - Session lasts 24 hours

3. **Control Your Mats**:
   - Select device group (if you have multiple)
   - Tap the large ON/OFF button to control
   - See countdown timer for auto-return to schedule
   - Tap "Return to Auto Mode" to immediately resume automatic scheduling

### Security Considerations

- **Strong PIN**: Use a secure PIN (not "1234"!)
- **HTTPS Recommended**: For external access, use a reverse proxy with HTTPS
- **Network Security**: Keep on internal network or use VPN for external access

### External Access via Reverse Proxy

For secure external access, use nginx or similar:

```nginx
location /heattrax/ {
    proxy_pass http://localhost:4328/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Then access via: `https://your-domain.com/heattrax/control`

### How Manual Override Works

1. **Set Override**: When you manually turn mats ON or OFF via the mobile interface
2. **Scheduler Pauses**: Automatic scheduling is temporarily disabled for that group
3. **Auto-Expire**: Override automatically clears after the configured timeout (default 3 hours)
4. **Schedule Override**: Next scheduled event (ON or OFF) will also clear the override
5. **Resume Auto**: You can manually return to automatic scheduling anytime

**Note**: Whichever comes first—the timeout or the next scheduled event—will return the system to automatic mode.

### Environment Variables

You can also configure via environment variables:
```bash
HEATTRAX_WEB_PIN=your_secure_pin
HEATTRAX_WEB_MANUAL_OVERRIDE_TIMEOUT_HOURS=3
```

### Troubleshooting

**Can't access from mobile device**:
- Ensure your device is on the same network as the server
- Check firewall settings allow port 4328
- Try using the server's IP address directly

**PIN not working**:
- Check `config.yaml` for correct PIN setting
- Restart the container after changing configuration

**Override not clearing**:
- Check logs for manual override status
- Verify timeout is configured correctly
- State is persisted in `state/automation_overrides.json`

## Features

### Web UI & API
- **Browser-based Interface**: Monitor and configure your system from any device
  - Real-time status dashboard showing device states and weather info
  - **Groups tab** - View and control device groups
    - Enable/disable entire groups
    - View all configured schedules with times, conditions, and priorities
    - See which schedules are enabled/disabled
  - **Manual device control** on Health page - Turn devices/outlets ON/OFF instantly
  - **Configuration editor** with syntax validation
    - **Environment override visibility**: See which settings are controlled by env vars
    - Clear separation between editable (YAML) and read-only (env) configuration
    - Simplified to show only essential global settings
  - Clear error messages and success notifications
  - Security warnings when binding to non-local addresses
- **JSON REST API**: Programmatic access to system status and configuration
  - **Health & Monitoring**
    - `GET /api/health` - Health check endpoint
    - `GET /api/ping` - Simple liveness check
    - `GET /api/status` - System status, device states, weather info
    - `GET /api/system/status` - Extended system status with notifications and PIN config
  - **Device Control**
    - `GET /api/devices/status` - Detailed device and outlet states
    - `POST /api/devices/control` - Manual device/outlet control
    - `POST /api/groups/{group}/control` - Control all outlets in a group
  - **Schedule Management** (full CRUD)
    - `GET /api/groups/{group}/schedules` - List all schedules
    - `POST /api/groups/{group}/schedules` - Add new schedule
    - `GET /api/groups/{group}/schedules/{index}` - Get specific schedule
    - `PUT /api/groups/{group}/schedules/{index}` - Update schedule
    - `DELETE /api/groups/{group}/schedules/{index}` - Delete schedule
    - `PUT /api/groups/{group}/schedules/{index}/enabled` - Toggle enabled status
  - **Weather**
    - `GET /api/weather/forecast` - Cached weather forecast with black ice detection
    - `GET /api/weather/mat-forecast` - Predicted ON/OFF windows per group
  - **Configuration**
    - `GET /api/config` - Current configuration with source metadata (env/yaml)
    - `PUT /api/config` - Update configuration with validation
    - `POST /api/credentials` - Update device credentials
    - `GET /api/config/download` - Download config.yaml
    - `POST /api/config/upload` - Upload and validate new config.yaml
    - `POST /api/restart` - Restart application
  - **Automation & Vacation**
    - `GET /api/groups/{group}/automation` - Get automation config for a group
    - `PATCH /api/groups/{group}/automation` - Update automation overrides
    - `GET /api/vacation_mode` - Get vacation mode status
    - `PUT /api/vacation_mode` - Enable/disable vacation mode
    - `GET /api/solar_times` - Get sunrise/sunset times
  - **Mobile Control** (PIN-protected)
    - `POST /api/auth/login` - Authenticate with PIN (creates 24-hour session)
    - `GET /api/mat/status` - Get mat status for all groups
    - `POST /api/mat/control` - Control group with optional timeout
    - `POST /api/mat/reset-auto` - Clear manual override, resume automation
  - **Notifications**
    - `GET /api/notifications/status` - Provider health status (email, webhook)
    - `POST /api/notifications/test` - Queue test notification (non-blocking)
  - See **[API Reference](docs/API_REFERENCE.md)** for complete documentation with request/response examples
- **Configuration as Code**: `config.yaml` is the single source of truth
  - Auto-generated on first run if missing
  - Environment variables override YAML values at runtime
  - Env overrides clearly visible in Web UI (read-only)
  - Atomic writes to prevent corruption
  - Hot-reload support for most settings
- **Thread-Safe Operations**: Web UI and scheduler run concurrently
  - Scheduler runs in dedicated thread
  - Flask web server in main thread
  - Shared configuration with proper locking
  - Graceful shutdown handling

### Device Management
- **Multi-Device Support**: Control multiple Kasa/Tapo devices organized into logical groups
  - Heated mats group with weather-based automation
  - Christmas lights group with schedule-based automation
  - Support for Kasa EP40M smart plugs with 2 outlets each
  - Outlet-specific control (control individual outlets independently)
  - Group actions (turn all devices in a group on/off together)
  - Single-device deployments use the same multi-device format with one group

### Weather Integration
- **Weather Toggle**: Enable or disable weather-based scheduling
  - `HEATTRAX_WEATHER_ENABLED` environment variable (default: true)
  - When disabled, uses fixed schedule behavior instead of weather forecasts
  - Sends notifications on startup indicating weather mode status
- **Multi-Provider Support**: Choose between weather APIs
  - **OpenWeatherMap**: Industry-standard API with detailed forecasts (requires API key)
  - **Open-Meteo**: Free API with no key required (default)
- **Weather Resilience & Outage Handling**: NEW! Reliable operation during internet/API outages
  - **Automatic Caching**: Stores last successful forecast locally
  - **Smart Fallback**: Uses cached data during temporary outages
  - **Fail-Safe Mode**: Reverts to static schedule when cache expires
  - **Adaptive Retry**: Exponential backoff when API is unavailable
  - **Outage Alerts**: Notifications when service is offline too long
  - **State Tracking**: ONLINE → DEGRADED (using cache) → OFFLINE (fail-safe)
  - Fully configurable cache duration, retry intervals, and alert thresholds
- **Weather-Based Automation**: Intelligent control using schedule conditions
  - Schedules can require specific weather conditions (temperature, precipitation)
  - Per-schedule temperature thresholds and precipitation detection
  - Automatic OFF when weather service is offline for extended periods
  - See the [Scheduling Guide](SCHEDULING.md) for examples

### Unified Conditional Scheduling System
- **Multiple Schedule Types**: Flexible scheduling to meet any automation need
  - **Clock-based schedules**: Fixed times (e.g., "06:00", "22:30")
  - **Solar-based schedules**: Relative to sunrise/sunset (e.g., "sunrise-30", "sunset+15")
  - Automatic seasonal adjustment for solar schedules
- **Weather Conditions**: Optional filters for temperature and precipitation
  - `temperature_max`: Activate only if temperature is below threshold
  - `precipitation_active`: Activate only during precipitation
  - Weather-independent schedules continue working during weather outages
- **Priority System**: Resolve conflicts when multiple schedules overlap
  - `critical`: Safety/heating schedules (highest priority)
  - `normal`: Standard automation (default)
  - `low`: Decorative/optional features
- **Day-of-Week Filtering**: Different schedules for weekdays vs weekends
  - ISO 8601 day numbering (1=Monday, 7=Sunday)
  - Any combination of days (e.g., weekdays only, specific days)
- **Multiple Schedules per Group**: Device turns ON if ANY schedule is active
  - Combine weather-dependent and weather-independent schedules
  - Different schedules for different scenarios
  - Highest priority schedule wins if multiple are active
- **📖 See the [Scheduling Guide](SCHEDULING.md)** for complete documentation, examples, and best practices

### Safety & Reliability
- **Safety Features**:
  - Maximum 6-hour continuous runtime limit (configurable)
  - 30-minute cooldown period after max runtime (configurable)
  - State persistence for recovery after restarts
  - Per-group runtime tracking
- **HTTP Health Check API**: Monitor application health via HTTP (disabled by default)
  - **Endpoints** (when enabled):
    - `GET http://localhost:4329/health` - Basic application health check (always returns 200 if app is running)
    - `GET http://localhost:4329/health/weather` - Weather-specific health check
      - Returns status='disabled' when weather is disabled
      - Returns status='ok' with current conditions and forecast when weather is enabled
      - Returns status='timeout' or 'error' if weather API is unreachable
  - **Configuration**:
    - Disabled by default to avoid port conflicts
    - Enable with `HEATTRAX_HEALTH_SERVER_ENABLED=true` (environment) or `health_server.enabled: true` (YAML)
    - Default port: 4329 (configurable via `HEATTRAX_HEALTH_SERVER_PORT`)
    - Default host: 0.0.0.0 (configurable via `HEATTRAX_HEALTH_SERVER_HOST`)
  - **Use Cases**: Container orchestration (Kubernetes liveness probes, Docker health checks), external monitoring systems
- **Periodic Health Checks**: Background monitoring of device connectivity
  - Configurable check interval (default: every 24 hours)
  - Multi-device aware: tracks all configured devices
  - Detects lost/found devices and configuration mismatches
  - Monitors device IP changes and alias changes
  - Automatic re-initialization on critical failures
- **Notification System**: Extensible alerting for device issues (optional, disabled by default)
  - **Email notifications** via SMTP (Gmail, Office365, custom SMTP)
  - **Webhook notifications** via HTTP POST (Slack, Discord, custom webhooks)
  - **Startup validation** with connectivity testing and optional test notifications
  - **Weather mode notifications** sent on startup with current weather snapshot
  - **Per-event routing** to control which events go to which providers
  - **Required mode** to ensure notifications work before starting scheduler
  - Configurable via YAML and environment variables
  - Events: device lost, device found, IP changed, connectivity issues, weather mode, etc.
  - See [HEALTH_CHECK.md](docs/HEALTH_CHECK.md) for detailed notification configuration
- **Robust Error Handling**: Continues operation even if individual devices fail

### Configuration & Logging
- **Comprehensive Logging**: Rotating log files with configurable levels (DEBUG, INFO, WARNING, ERROR)
  - Verbose logging for all API calls and device operations
  - Detailed error messages with troubleshooting guidance
  - Full exception tracebacks for debugging
  - See [LOGGING.md](docs/LOGGING.md) for complete logging guide
- **Flexible Configuration**: YAML-based configuration with environment variable overrides
  - **Primary method**: Edit `config.yaml` directly or via web UI
  - Environment variables for overrides (perfect for Docker/secrets)
  - Auto-generated on first run if missing
  - Multi-device configuration with logical grouping
  - See [Configuration](#configuration) section below
- **Startup Diagnostic Checks**: Comprehensive pre-flight checks for containerized deployments
  - Python version and package verification
  - Directory access validation
  - Configuration file parsing
  - Environment variable dump (with sensitive data redaction)
  - Optional device connectivity test
  - See logs on startup for detailed diagnostic information
- **Docker Support**: Easy deployment with Docker and docker-compose

## Requirements

- Python 3.11+
- TP-Link Tapo smart plug (EP40M or compatible Tapo devices)
- Tapo account credentials (username/email and password)
- Network access to the smart plug (local network)
- Internet access for Tapo cloud authentication (required for device control)

## ⚠️ Deprecated Features

The following features have been **deprecated** and replaced with the unified conditional scheduling system:

### Removed from UI (as of latest version)
- **Legacy automation toggles**: `weather_control`, `precipitation_control`, `morning_mode` toggles in Groups tab
- **Threshold configuration**: `lead_time_minutes`, `trailing_time_minutes`, `temperature_f` in Configuration tab
- **Morning mode settings**: `morning_mode.enabled`, `start_hour`, `end_hour` in Configuration tab

### Migration to New System
All automation is now handled via **schedules** in `config.yaml`. The new system provides:
- ✅ More flexibility with multiple schedules per group
- ✅ Per-schedule temperature and precipitation conditions
- ✅ Solar-based timing (sunrise/sunset with offsets)
- ✅ Priority system for conflict resolution
- ✅ Day-of-week filtering

**Example**: To replace morning mode with a schedule:
```yaml
schedules:
  - name: "Morning Black Ice Protection"
    enabled: true
    priority: "critical"
    days: [1,2,3,4,5]  # Weekdays
    on:
      type: "time"
      value: "06:00"
    off:
      type: "time"
      value: "08:00"
    conditions:
      temperature_max: 32  # Only run if temp <= 32°F
```

See the [Scheduling Guide](SCHEDULING.md) for complete documentation and migration examples.

### Backward Compatibility
- Old `thresholds` and `morning_mode` config sections are still parsed but **not required**
- Backend code that uses these sections continues to work for existing configurations
- **Recommendation**: Migrate to schedule-based system for new deployments

## Setup Mode

**New in v1.2**: HeatTrax now includes a "setup mode" that allows the application to start even when Tapo credentials are missing or invalid.

### What is Setup Mode?

When HeatTrax starts without valid Tapo credentials (empty, missing, or placeholder values like `your_tapo_username`), it enters **setup mode**:

- ✅ **Application starts normally** - no crash or exit
- ✅ **Web UI remains accessible** for configuration
- ⚠️ **Device control is disabled** - scheduler runs in safe no-op state
- 🔧 **Easy credential configuration** via Web UI

### How It Works

1. **Missing/Invalid Credentials Detected**: On startup, HeatTrax validates Tapo credentials
2. **Setup Mode Activated**: If credentials are missing, invalid, or placeholder values, setup mode activates
3. **Clear Logging**: Console and logs clearly indicate setup mode is active and why
4. **Device Control Disabled**: No attempts are made to discover or control Tapo devices
5. **Web UI Available**: Access the web UI to configure credentials
6. **Restart to Enable**: Once valid credentials are saved, restart the application to enable device control

### Credential Sources (Priority Order)

Credentials are checked in this order:

1. **Environment variables** (highest priority):
   - `HEATTRAX_TAPO_USERNAME`
   - `HEATTRAX_TAPO_PASSWORD`
2. **config.yaml file** (lower priority)

**Important**: Environment variables override `config.yaml` at runtime but **do NOT** automatically update the file. If you remove the environment variables later, the application will fall back to `config.yaml` values.

### Placeholder Detection

These values are treated as invalid and trigger setup mode:

**Usernames:**
- `your_tapo_email@example.com`
- `your_tapo_username`
- `your_username`
- `your_email@example.com`

**Passwords:**
- `your_tapo_password`
- `password`

### Exiting Setup Mode

To exit setup mode and enable device control:

1. **Via Web UI**: Navigate to the Configuration page and update credentials
2. **Via Environment Variables**: Set `HEATTRAX_TAPO_USERNAME` and `HEATTRAX_TAPO_PASSWORD`
3. **Via config.yaml**: Edit the file directly and restart

After updating credentials, **restart the application** to apply changes and exit setup mode.

## Installation

### Using Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   ```

2. Create your configuration file (or let it auto-generate):
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings, or use the web UI after starting
   ```

3. Edit `config.yaml` with your Tapo credentials and device IPs:
   ```yaml
   devices:
     credentials:
       username: "your_tapo_username"
       password: "your_tapo_password"
     groups:
       heated_mats:
         enabled: true
         items:
           - name: "Front Walkway Mat"
             ip_address: "192.168.1.100"
   ```

4. Start the scheduler:
   ```bash
   docker-compose up -d
   ```

5. Access the web UI at `http://localhost:4328`

### Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create and edit configuration:
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

4. Run the scheduler:
   ```bash
   python main.py
   ```

5. Access the web UI at `http://localhost:4328`

## Configuration

The scheduler can be configured in two ways:

1. **Via Web UI** (Recommended): Edit configuration in your browser at `http://localhost:4328`
   - Real-time validation
   - Clear error messages
   - Auto-restart on save to apply changes
   
2. **Via `config.yaml`**: Edit the YAML file directly
   - See `config.example.yaml` for all available options
   - Changes require restart unless using web UI

For complete environment variable configuration options, see [Environment Variables Reference](docs/ENVIRONMENT_VARIABLES.md).

For deployment-specific configuration (Docker, Portainer), see the [Deployment Guide](docs/DEPLOYMENT.md).

### Quick Configuration Example

```yaml
# config.yaml
location:
  latitude: 40.7128
  longitude: -74.0060
  timezone: "America/New_York"

weather_api:
  provider: "open-meteo"  # or "openweathermap"

devices:
  credentials:
    username: "your_tapo_username"
    password: "your_tapo_password"
  
  groups:
    heated_mats:
      enabled: true
      schedules:
        - name: "Morning Black Ice Protection"
          enabled: true
          priority: "critical"
          days: [1, 2, 3, 4, 5, 6, 7]
          "on":
            type: "time"
            value: "05:00"
          "off":
            type: "time"
            value: "08:00"
          conditions:
            temperature_max: 36
      items:
        - name: "Front Walkway Mat"
          ip_address: "192.168.1.100"
          outlets: [0, 1]
```

For complete configuration details, including all available settings for safety, notifications, and health checks, see the [Setup Guide](docs/SETUP.md).

### Key Configuration Topics

- **Scheduling**: See the comprehensive [Scheduling Guide](SCHEDULING.md) for details on the unified conditional scheduling system
- **Environment Variables**: See [Environment Variables Reference](docs/ENVIRONMENT_VARIABLES.md) for Docker/Portainer deployment
- **Notifications**: See [Health Check Guide](docs/HEALTH_CHECK.md) for notification configuration
- **Deployment**: See [Deployment Guide](docs/DEPLOYMENT.md) for Docker and Portainer setup

## Device Control Library (python-kasa)

This scheduler uses the [python-kasa](https://github.com/python-kasa/python-kasa) library to control TP-Link Tapo smart plugs. The implementation uses **Tapo-authenticated discovery** for compatibility with Tapo devices like the EP40M.

### Key Implementation Details

- **Library Version**: Requires `python-kasa>=0.7.0`
- **Device Initialization**: Uses `Discover.discover_single(ip_address, username=username, password=password)` for Tapo-authenticated access
- **Credentials Required**: Tapo username and password **must** be provided via `HEATTRAX_TAPO_USERNAME` and `HEATTRAX_TAPO_PASSWORD` environment variables or in `config.yaml` under `devices.credentials`
- **Authentication**: Tapo devices (like the EP40M) require authenticated discovery and cannot be controlled using the legacy IOT protocol (port 9999)

### Tapo Device Support

**Important**: Tapo devices (EP40M, etc.) require authenticated access:

1. **Credentials are required**: If `HEATTRAX_TAPO_USERNAME` or `HEATTRAX_TAPO_PASSWORD` are not set, the scheduler will start in setup mode with device control disabled (see [Setup Mode](#setup-mode) section)
2. **Cloud authentication**: Tapo devices authenticate against TP-Link cloud services using your Tapo account credentials
3. **No legacy protocol**: Tapo devices do NOT support the legacy Kasa IOT protocol (port 9999), so older connection methods will fail
4. **Discovery method**: The scheduler uses `Discover.discover_single()` with credentials to establish authenticated connections

### Why This Matters

Tapo devices (like the EP40M) are different from older Kasa devices:

1. **Tapo devices require authenticated discovery** - They do not respond to the legacy IOT protocol on port 9999
2. **Credentials are passed during discovery** - The `Discover.discover_single()` method accepts `username` and `password` parameters
3. **Cloud-based authentication** - Tapo devices authenticate through TP-Link's cloud services, requiring valid account credentials
4. **Enhanced security** - This newer authentication method provides better security than the legacy protocol

If you see errors like `Unable to connect to the device: 10.0.50.74:9999: [Errno 111] Connect call failed`, this indicates the scheduler was attempting to use the legacy protocol. This version uses the correct Tapo-authenticated discovery method.

## How It Works

### Scheduler Operation

1. **Group Initialization**: At startup, the scheduler:
   - Initializes all configured device groups
   - Establishes connection to each device
   - Validates group configurations
   - Creates independent state tracking per group

2. **Weather-Based Groups** (e.g., heated mats):
   - **Weather Monitoring**: Checks weather forecasts every 10 minutes (configurable)
   - **Weather Resilience**: NEW! Reliable operation during internet/API outages
     - Caches last successful forecast (default: 12 hours)
     - **ONLINE State**: Normal operation with fresh API data
     - **DEGRADED State**: API unavailable but using valid cached data (within 6 hours by default)
     - **OFFLINE State**: No valid data available - reverts to static schedule (weather features disabled)
     - Automatic retry with exponential backoff (5min → 10min → 20min → 40min → 60min max)
     - Alerts when offline longer than threshold (default: 30 minutes)
     - Automatic recovery notification when API becomes available again
   - **Schedule Evaluation**: The unified conditional scheduling system evaluates all active schedules for the group. Each schedule can specify weather conditions (temperature thresholds, precipitation), time windows (clock-based or solar-based), priorities, and day-of-week filters. See the [Scheduling Guide](SCHEDULING.md) for details.
   - **Group Action**: All devices in group turn on/off together

3. **Schedule-Based Groups** (e.g., Christmas lights):
   - **Time-Based Control**: Follows configured on/off times
   - **Daily Schedule**: Automatically activates at `on_time`, deactivates at `off_time`
   - **Optional Day Filtering**: Can restrict to specific days of the week
   - **Independent of Weather**: Operates regardless of weather conditions

4. **Per-Group Safety**:
   - Each group has independent runtime tracking
   - Maximum 6-hour continuous runtime per group (configurable)
   - 30-minute cooldown per group after max runtime
   - State persistence per group for recovery after restarts

5. **Robust Error Handling**:
   - Continues operation even if individual devices fail
   - Logs errors for failed devices without stopping scheduler
   - Retries device operations on next cycle

6. **Outlet Control**:
   - For multi-outlet plugs (EP40M), can control individual outlets
   - Specify outlets in config: `outlets: [0, 1]` for both, `outlets: [0]` for first only
   - Omit outlets to control entire device

## Logs

Logs are stored in the `logs/` directory with rotating file handling:
- Default maximum file size: 10 MB
- Default backup count: 5 files
- Logs include timestamps, levels, and detailed error information

View logs:
```bash
# Docker
docker-compose logs -f

# Manual
tail -f logs/heattrax_scheduler.log
```

## State Management

The application maintains state in `state/state.json` to track:
- Current device state (on/off)
- Runtime duration
- Cooldown periods

This allows the scheduler to resume properly after restarts.

## Troubleshooting

For common issues and solutions:

- **Device connection problems** - Check IP addresses, credentials, and network connectivity
- **Device initialization timeouts** - Increase timeout settings for slow devices  
- **Discovery limitations** - Static IP configuration recommended for cross-subnet/VLAN setups
- **Weather API issues** - Verify latitude/longitude and internet connectivity

For complete troubleshooting guidance, including detailed solutions and FAQ about device discovery and network configuration, see the [Troubleshooting Guide](docs/TROUBLESHOOTING.md).

## Deployment

HeatTrax Scheduler can be deployed using Docker or Portainer:

- **Docker Compose** - Standard deployment (see [Installation](#installation) section above)
- **Portainer** - Web-based Docker management with visual environment variable controls
- **Environment Variables** - Full configuration via environment variables for containerized deployments

For detailed deployment instructions including Portainer setup, environment variable configuration, and Docker secrets, see the [Deployment Guide](docs/DEPLOYMENT.md).



## FAQ

For frequently asked questions about device discovery, network configuration, and troubleshooting, see the [Troubleshooting Guide](docs/TROUBLESHOOTING.md).

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [python-kasa](https://github.com/python-kasa/python-kasa) - TP-Link device control library
- [Open-Meteo](https://open-meteo.com/) - Free weather API
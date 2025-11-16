# HeatTrax Tapo M400 Scheduler

Automated control system for TP-Link Tapo smart plugs to manage heated outdoor mats based on weather conditions. The system monitors weather forecasts and automatically turns mats on before precipitation when temperatures are below freezing, with built-in safety features and optional morning frost-clearing mode.

## 🚀 Quick Start

Want to get started quickly? See the [Quick Start Guide](QUICKSTART.md) for a 5-minute setup.

For detailed setup instructions, see [SETUP.md](SETUP.md).

For troubleshooting and logging information, see [LOGGING.md](LOGGING.md).

For startup diagnostic checks and debugging containerized deployments, see [STARTUP_CHECKS.md](STARTUP_CHECKS.md).

For device discovery, health checks, and notification system, see [HEALTH_CHECK.md](HEALTH_CHECK.md).

## Features

- **Weather-Based Automation**: Uses Open-Meteo API for accurate weather forecasting
- **Smart Scheduling**: Turns mats on 60 minutes before precipitation if temperature is below 34°F
- **Morning Frost Mode**: Optional mode to clear frost between 6-8 AM
- **Device Auto-Discovery**: Automatic network discovery and diagnostics at startup
  - Discovers all Kasa/Tapo devices on the network
  - Logs detailed device information (IP, MAC, alias, model, state, RSSI, features)
  - Auto-selects device if only one found
  - Provides configuration suggestions when multiple devices detected
- **Periodic Health Checks**: Background monitoring of device connectivity
  - Configurable check interval (default: every 24 hours)
  - Detects lost/found devices and configuration mismatches
  - Monitors device IP changes and alias changes
  - Automatic re-initialization on critical failures
- **Notification System**: Extensible alerting for device issues (optional, disabled by default)
  - Email notifications via SMTP
  - Webhook notifications via HTTP POST
  - Configurable via environment variables
  - Events: device lost, device found, IP changed, connectivity issues
- **Safety Features**:
  - Maximum 6-hour continuous runtime limit
  - 30-minute cooldown period after max runtime
  - State persistence for recovery after restarts
- **Comprehensive Logging**: Rotating log files with configurable levels (DEBUG, INFO, WARNING, ERROR)
  - Verbose logging for all API calls and device operations
  - Detailed error messages with troubleshooting guidance
  - Full exception tracebacks for debugging
  - See [LOGGING.md](LOGGING.md) for complete logging guide
- **Startup Diagnostic Checks**: Comprehensive pre-flight checks for containerized deployments
  - Python version and package verification
  - Directory access validation
  - Configuration file parsing
  - Environment variable dump (with sensitive data redaction)
  - Optional device connectivity test
  - See [STARTUP_CHECKS.md](STARTUP_CHECKS.md) for details
- **Docker Support**: Easy deployment with Docker and docker-compose
- **Flexible Configuration**: YAML-based configuration with environment variable overrides
  - All settings can be overridden via environment variables
  - Perfect for containerized deployments and secret management
  - See [Environment Variable Configuration](#environment-variable-configuration) below

## Requirements

- Python 3.11+
- TP-Link Tapo smart plug (M400 or compatible)
- Tapo account credentials
- Network access to the smart plug

## Installation

### Using Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   ```

2. Create your configuration file:
   ```bash
   cp config.example.yaml config.yaml
   ```

3. Edit `config.yaml` with your settings:
   ```yaml
   location:
     latitude: 40.7128
     longitude: -74.0060
     timezone: "America/New_York"
   
   device:
     ip_address: "192.168.1.100"
     username: "your_tapo_username"
     password: "your_tapo_password"
   ```

4. Start the scheduler:
   ```bash
   docker-compose up -d
   ```

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

## Environment Variable Configuration

All configuration settings can be overridden using environment variables, which is ideal for Docker deployments, Portainer stacks, and keeping secrets secure.

> **Note about `config.yaml`**: The configuration file is **optional** when all required environment variables are provided. If `config.yaml` is missing, the application will log `Configuration file not found: config.yaml` as an informational message, but will continue to run using environment variables. This is the recommended approach for Docker and Portainer deployments.

### Override Precedence

Configuration values are resolved in the following order (highest to lowest priority):

1. **Environment Variables** - Always checked first
2. **YAML Configuration File** - Used if no environment variable is set
3. **Default Values** - Used if neither environment variable nor YAML value is provided

### Supported Environment Variables

| Environment Variable | Config Section | Description | Type | Example |
|---------------------|----------------|-------------|------|---------|
| `HEATTRAX_CONFIG_PATH` | - | Path to configuration file | String | `/config/config.yaml` |
| `TZ` | - | System timezone | String | `America/New_York` |
| `HEATTRAX_LATITUDE` | location | Location latitude | Float | `40.7128` |
| `HEATTRAX_LONGITUDE` | location | Location longitude | Float | `-74.0060` |
| `HEATTRAX_TIMEZONE` | location | Location timezone | String | `America/New_York` |
| `HEATTRAX_TAPO_IP_ADDRESS` | device | Tapo device IP address | String | `192.168.1.100` |
| `HEATTRAX_TAPO_USERNAME` | device | Tapo account username | String | `user@example.com` |
| `HEATTRAX_TAPO_PASSWORD` | device | Tapo account password | String | `your_password` |
| `HEATTRAX_THRESHOLD_TEMP_F` | thresholds | Temperature threshold (°F) | Float | `34` |
| `HEATTRAX_LEAD_TIME_MINUTES` | thresholds | Minutes before precipitation | Integer | `60` |
| `HEATTRAX_TRAILING_TIME_MINUTES` | thresholds | Minutes after precipitation | Integer | `60` |
| `HEATTRAX_CHECK_INTERVAL_MINUTES` | scheduler | Weather check interval | Integer | `10` |
| `HEATTRAX_FORECAST_HOURS` | scheduler | Forecast look-ahead hours | Integer | `12` |
| `HEATTRAX_MAX_RUNTIME_HOURS` | safety | Maximum continuous runtime | Float | `6` |
| `HEATTRAX_COOLDOWN_MINUTES` | safety | Cooldown period | Integer | `30` |
| `HEATTRAX_MORNING_MODE_ENABLED` | morning_mode | Enable morning mode | Boolean | `true` or `false` |
| `HEATTRAX_MORNING_MODE_START_HOUR` | morning_mode | Morning mode start (0-23) | Integer | `6` |
| `HEATTRAX_MORNING_MODE_END_HOUR` | morning_mode | Morning mode end (0-23) | Integer | `8` |
| `HEATTRAX_LOG_LEVEL` | logging | Logging level | String | `INFO`, `DEBUG` |
| `HEATTRAX_HEALTH_CHECK_INTERVAL_HOURS` | health_check | Hours between health checks | Float | `24` |
| `HEATTRAX_HEALTH_CHECK_MAX_FAILURES` | health_check | Max consecutive failures before re-init | Integer | `3` |
| `REBOOT_PAUSE_SECONDS` | reboot | Pause (seconds) before container restart | Integer | `60` |
| `HEATTRAX_NOTIFICATION_EMAIL_ENABLED` | notifications.email | Enable email notifications | Boolean | `true` or `false` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST` | notifications.email | SMTP server hostname | String | `smtp.gmail.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT` | notifications.email | SMTP server port | Integer | `587` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME` | notifications.email | SMTP username | String | `user@example.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD` | notifications.email | SMTP password | String | `password` |
| `HEATTRAX_NOTIFICATION_EMAIL_FROM` | notifications.email | From email address | String | `sender@example.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_TO` | notifications.email | To email addresses (comma-separated) | String | `user1@example.com,user2@example.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_USE_TLS` | notifications.email | Use TLS for SMTP | Boolean | `true` or `false` |
| `HEATTRAX_NOTIFICATION_WEBHOOK_ENABLED` | notifications.webhook | Enable webhook notifications | Boolean | `true` or `false` |
| `HEATTRAX_NOTIFICATION_WEBHOOK_URL` | notifications.webhook | Webhook URL | String | `https://hooks.example.com/notify` |

### Boolean Values

For boolean environment variables (like `HEATTRAX_MORNING_MODE_ENABLED`), the following values are accepted:
- **True**: `true`, `TRUE`, `1`, `yes`, `YES`, `on`, `ON`
- **False**: `false`, `FALSE`, `0`, `no`, `NO`, `off`, `OFF`

### Security Best Practices

When using environment variables for secrets:

1. **Never commit secrets to version control** - Use `.env` files locally and add them to `.gitignore`
2. **Use Docker secrets or Portainer secrets** for production deployments
3. **Restrict file permissions** on any files containing sensitive data
4. **Rotate credentials regularly** and update environment variables accordingly
5. **Use separate credentials** for different environments (dev/staging/prod)

### Using Environment Variables with Docker

#### Option 1: Environment Variables in docker-compose.yml

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      - TZ=America/New_York
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TIMEZONE=America/New_York
      - HEATTRAX_TAPO_IP_ADDRESS=192.168.1.100
      - HEATTRAX_TAPO_USERNAME=your_username
      - HEATTRAX_TAPO_PASSWORD=your_password
      - HEATTRAX_THRESHOLD_TEMP_F=34
      - HEATTRAX_LEAD_TIME_MINUTES=60
      - HEATTRAX_TRAILING_TIME_MINUTES=60
      - HEATTRAX_CHECK_INTERVAL_MINUTES=10
      - HEATTRAX_FORECAST_HOURS=12
      - HEATTRAX_MAX_RUNTIME_HOURS=6
      - HEATTRAX_COOLDOWN_MINUTES=30
      - HEATTRAX_MORNING_MODE_ENABLED=true
      - HEATTRAX_MORNING_MODE_START_HOUR=6
      - HEATTRAX_MORNING_MODE_END_HOUR=8
      - HEATTRAX_LOG_LEVEL=INFO
    volumes:
      - ./logs:/app/logs
      - ./state:/app/state
    restart: unless-stopped
    network_mode: host
```

#### Option 2: Using .env File

Create a `.env` file in the same directory as your `docker-compose.yml`:

```bash
# .env file
TZ=America/New_York
HEATTRAX_LATITUDE=40.7128
HEATTRAX_LONGITUDE=-74.0060
HEATTRAX_TIMEZONE=America/New_York
HEATTRAX_TAPO_IP_ADDRESS=192.168.1.100
HEATTRAX_TAPO_USERNAME=your_username
HEATTRAX_TAPO_PASSWORD=your_password
HEATTRAX_THRESHOLD_TEMP_F=34
HEATTRAX_LEAD_TIME_MINUTES=60
HEATTRAX_TRAILING_TIME_MINUTES=60
HEATTRAX_CHECK_INTERVAL_MINUTES=10
HEATTRAX_FORECAST_HOURS=12
HEATTRAX_MAX_RUNTIME_HOURS=6
HEATTRAX_COOLDOWN_MINUTES=30
HEATTRAX_MORNING_MODE_ENABLED=true
HEATTRAX_MORNING_MODE_START_HOUR=6
HEATTRAX_MORNING_MODE_END_HOUR=8
HEATTRAX_LOG_LEVEL=INFO
```

Then reference it in `docker-compose.yml`:

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./state:/app/state
    restart: unless-stopped
    network_mode: host
```

**Important**: Add `.env` to your `.gitignore` file to prevent committing secrets!

#### Option 3: Hybrid Approach (Recommended)

Use YAML for non-sensitive settings and environment variables for secrets:

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      - TZ=America/New_York
      # Override only sensitive values
      - HEATTRAX_TAPO_USERNAME=${HEATTRAX_TAPO_USERNAME}
      - HEATTRAX_TAPO_PASSWORD=${HEATTRAX_TAPO_PASSWORD}
    volumes:
      - ./config.yaml:/app/config.yaml:ro  # Mount config for non-secret settings
      - ./logs:/app/logs
      - ./state:/app/state
    restart: unless-stopped
    network_mode: host
```

## Configuration

### Location Settings

```yaml
location:
  latitude: 40.7128        # Your location latitude
  longitude: -74.0060      # Your location longitude
  timezone: "America/New_York"  # Your timezone
```

### Device Settings

```yaml
device:
  ip_address: "192.168.1.100"     # IP address of your Tapo device
  username: "your_tapo_username"   # Tapo account username/email
  password: "your_tapo_password"   # Tapo account password
```

### Weather Thresholds

```yaml
thresholds:
  temperature_f: 34              # Temperature threshold in Fahrenheit
  lead_time_minutes: 60          # Minutes before precipitation to turn on
  trailing_time_minutes: 60      # Minutes after precipitation to turn off
```

### Morning Mode (Optional)

```yaml
morning_mode:
  enabled: true      # Enable morning frost-clearing mode
  start_hour: 6      # Start time (24-hour format)
  end_hour: 8        # End time (24-hour format)
```

### Safety Settings

```yaml
safety:
  max_runtime_hours: 6       # Maximum continuous runtime
  cooldown_minutes: 30       # Cooldown period after max runtime
```

### Scheduler Settings

```yaml
scheduler:
  check_interval_minutes: 10   # How often to check weather
  forecast_hours: 12           # How far ahead to look for precipitation
```

### Health Check Settings (Optional)

```yaml
health_check:
  interval_hours: 24           # How often to run device health checks
  max_consecutive_failures: 3  # Max failures before triggering re-initialization
```

The health check system periodically verifies device connectivity and monitors for changes:
- Runs every N hours (configurable, default: 24)
- Detects lost/found devices
- Monitors for device IP changes (MAC address tracking)
- Detects alias/configuration changes
- Automatically triggers re-initialization after consecutive failures

### Reboot Pause Settings (Optional)

```yaml
reboot:
  pause_seconds: 60  # Pause duration before container restart
```

When a critical error occurs that would cause the container to restart (e.g., failed startup checks, configuration errors), the application pauses for a configurable duration before exiting. This pause:
- Allows time for console troubleshooting and log inspection
- Defaults to 60 seconds
- Displays clear countdown messages in logs and console
- Can be set to 0 to disable the pause
- Configurable via `REBOOT_PAUSE_SECONDS` environment variable

This is particularly useful in containerized deployments where Docker's restart policy would immediately restart the container, making it difficult to troubleshoot the root cause of failures.

### Notification Settings (Optional, Disabled by Default)

```yaml
notifications:
  email:
    enabled: false  # Set to true to enable
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_username: "your_email@gmail.com"
    smtp_password: "your_app_password"
    from_email: "your_email@gmail.com"
    to_emails:
      - "recipient@example.com"
    use_tls: true
  
  webhook:
    enabled: false  # Set to true to enable
    url: "https://your-webhook-url.com/notifications"
```

**Notification Events:**
- `device_lost` - Configured device not found during health check
- `device_found` - New device discovered on network
- `device_changed` - Device alias or properties changed
- `device_ip_changed` - Device MAC/IP mapping changed (CRITICAL - may indicate IP reassignment)
- `connectivity_lost` - Failed to reinitialize device connection
- `connectivity_restored` - Device connection restored after failures

**Email Setup Tips:**
- For Gmail: Use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password
- For other SMTP servers: Ensure the account has permission to send emails
- Test with `use_tls: true` first (most common); try `false` if connection fails

**Webhook Format:**
Webhook notifications send JSON POST requests with the following structure:
```json
{
  "event_type": "device_lost",
  "message": "Configured device at 192.168.1.100 not found",
  "timestamp": "2025-11-15T23:58:53.044Z",
  "details": {
    "configured_ip": "192.168.1.100",
    "consecutive_failures": 2
  },
  "source": "heattrax_scheduler"
}
```

## Device Control Library (python-kasa)

This scheduler uses the [python-kasa](https://github.com/python-kasa/python-kasa) library to control TP-Link Tapo smart plugs. The implementation is designed for compatibility with multiple versions of python-kasa.

### Key Implementation Details

- **Library Version**: Requires `python-kasa>=0.7.0`
- **Device Initialization**: The `SmartPlug` device is initialized with only the IP address: `SmartPlug(ip_address)`
- **Credentials Handling**: Tapo username and password are validated in configuration but are **not** passed to the `SmartPlug` constructor via a `credentials` keyword argument. This approach ensures compatibility across different python-kasa versions.
- **Authentication**: Modern versions of python-kasa handle authentication automatically during the device update/communication phase.

### Why This Matters

Earlier versions of the scheduler may have used a `credentials` parameter when creating `SmartPlug` objects. This has been removed because:

1. The `credentials` keyword argument is not universally supported across all python-kasa versions
2. Modern python-kasa handles authentication internally without requiring explicit credential injection at initialization
3. This change prevents `TypeError` exceptions related to unexpected keyword arguments

The scheduler still validates that Tapo credentials are present in the configuration (for diagnostics and potential future use), but device control works without explicitly passing them to the constructor.

## How It Works

1. **Startup Device Discovery**: At startup, the scheduler automatically:
   - Discovers all Kasa/Tapo devices on the network
   - Logs detailed information about each device found
   - Validates the configured device IP
   - Provides configuration suggestions if multiple devices detected

2. **Weather Monitoring**: The scheduler checks weather forecasts every 10 minutes (configurable)

3. **Precipitation Detection**: When precipitation is forecasted within the next 12 hours and temperature is below 34°F:
   - Mats turn ON 60 minutes before expected precipitation
   - Mats turn OFF 60 minutes after precipitation ends

4. **Morning Frost Mode**: Between 6-8 AM (configurable):
   - Mats turn ON if temperature is below threshold
   - Helps clear morning frost for safe walking

5. **Periodic Health Checks**: Background monitoring (every 24 hours by default):
   - Verifies device connectivity
   - Detects device changes or network issues
   - Sends notifications if enabled
   - Automatically re-initializes connection on repeated failures

6. **Safety Features**:
   - Automatic shutoff after 6 hours of continuous runtime
   - 30-minute cooldown before mats can turn on again
   - State is saved to disk for recovery after restarts

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

### Device Connection Issues

If you see connection errors:
1. Verify the IP address of your Tapo device
2. Ensure your Tapo username and password are correct
3. Check that the device is on the same network
4. Try accessing the device through the Tapo app first
5. **See the [FAQ section](#faq) for subnet/VLAN discovery limitations**

### Device Discovery Issues

If your device is not being discovered:
1. Check if the device is on a different subnet/VLAN than the container
2. Verify the device is powered on and connected to your network
3. Use static IP configuration (recommended for cross-subnet devices)
4. **See [FAQ: Device Discovery and Network Configuration](#device-discovery-and-network-configuration) for detailed guidance**

### Weather API Issues

If weather data fails to fetch:
1. Check your internet connection
2. Verify latitude and longitude are correct
3. Open-Meteo API is free and doesn't require an API key

### Docker Issues

```bash
# View logs
docker-compose logs -f

# Restart the service
docker-compose restart

# Rebuild after changes
docker-compose up -d --build
```

## Deploying with Portainer

[Portainer](https://www.portainer.io/) provides a web-based UI for managing Docker environments, making it easy to deploy and manage HeatTrax Scheduler with visual controls for environment variables and secrets.

### Quick Deployment (Environment Variables Only)

This method uses environment variables exclusively, eliminating the need for a config file. Perfect for Portainer deployments where you can manage environment variables through the UI.

1. **Create a new Stack in Portainer:**
   - Navigate to `Stacks` → `Add Stack`
   - Give your stack a name (e.g., `heattrax-scheduler`)
   - Paste the following docker-compose configuration:

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      # System Settings
      - TZ=America/New_York
      
      # Location Settings (Required)
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TIMEZONE=America/New_York
      
      # Tapo Device Settings (Required)
      - HEATTRAX_TAPO_IP_ADDRESS=192.168.1.100
      - HEATTRAX_TAPO_USERNAME=your_tapo_username
      - HEATTRAX_TAPO_PASSWORD=your_tapo_password
      
      # Weather Thresholds
      - HEATTRAX_THRESHOLD_TEMP_F=34
      - HEATTRAX_LEAD_TIME_MINUTES=60
      - HEATTRAX_TRAILING_TIME_MINUTES=60
      
      # Scheduler Settings
      - HEATTRAX_CHECK_INTERVAL_MINUTES=10
      - HEATTRAX_FORECAST_HOURS=12
      
      # Safety Settings
      - HEATTRAX_MAX_RUNTIME_HOURS=6
      - HEATTRAX_COOLDOWN_MINUTES=30
      
      # Morning Mode Settings
      - HEATTRAX_MORNING_MODE_ENABLED=true
      - HEATTRAX_MORNING_MODE_START_HOUR=6
      - HEATTRAX_MORNING_MODE_END_HOUR=8
      
      # Logging
      - HEATTRAX_LOG_LEVEL=INFO
    volumes:
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

volumes:
  heattrax-logs:
  heattrax-state:
```

2. **Configure Environment Variables:**
   - Update the environment variables directly in the Stack editor
   - Pay special attention to:
     - `HEATTRAX_LATITUDE` and `HEATTRAX_LONGITUDE` - Your location coordinates
     - `HEATTRAX_TAPO_IP_ADDRESS` - Your Tapo device's IP address
     - `HEATTRAX_TAPO_USERNAME` - Your Tapo account email
     - `HEATTRAX_TAPO_PASSWORD` - Your Tapo account password

3. **Deploy the Stack:**
   - Click "Deploy the stack"
   - Portainer will pull the image and start the service
   - Monitor deployment in the Portainer UI

4. **View Logs:**
   - Navigate to `Containers` → `heattrax-scheduler` → `Logs`
   - Or use Quick Actions → `Logs` from the container list

### Using Portainer Environment Variables Editor

Portainer provides a convenient UI for managing environment variables:

1. After deploying the stack, go to `Stacks` → `heattrax-scheduler` → `Editor`
2. Click on the stack name to edit
3. Use Portainer's environment variable editor to add/modify variables
4. Click "Update the stack" to apply changes

### Using Portainer Secrets (Advanced)

For enhanced security with sensitive credentials:

1. **Create Secrets in Portainer:**
   - Navigate to `Secrets` → `Add secret`
   - Create secrets for sensitive data:
     - `tapo_username`
     - `tapo_password`

2. **Reference secrets in your stack:**

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      - TZ=America/New_York
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TIMEZONE=America/New_York
      - HEATTRAX_TAPO_IP_ADDRESS=192.168.1.100
      - HEATTRAX_THRESHOLD_TEMP_F=34
      - HEATTRAX_LEAD_TIME_MINUTES=60
      - HEATTRAX_TRAILING_TIME_MINUTES=60
      - HEATTRAX_CHECK_INTERVAL_MINUTES=10
      - HEATTRAX_FORECAST_HOURS=12
      - HEATTRAX_MAX_RUNTIME_HOURS=6
      - HEATTRAX_COOLDOWN_MINUTES=30
      - HEATTRAX_MORNING_MODE_ENABLED=true
      - HEATTRAX_MORNING_MODE_START_HOUR=6
      - HEATTRAX_MORNING_MODE_END_HOUR=8
      - HEATTRAX_LOG_LEVEL=INFO
    secrets:
      - tapo_username
      - tapo_password
    volumes:
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

secrets:
  tapo_username:
    external: true
  tapo_password:
    external: true

volumes:
  heattrax-logs:
  heattrax-state:
```

Then read secrets in your environment:
```yaml
environment:
  - HEATTRAX_TAPO_USERNAME_FILE=/run/secrets/tapo_username
  - HEATTRAX_TAPO_PASSWORD_FILE=/run/secrets/tapo_password
```

### Hybrid Approach with Config File

If you prefer using a configuration file for some settings:

1. **Prepare your configuration file** on the Portainer host:
   ```bash
   # On your Docker host
   mkdir -p /opt/heattrax
   cp config.example.yaml /opt/heattrax/config.yaml
   # Edit /opt/heattrax/config.yaml with your base settings
   ```

2. **Create stack with config volume:**

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      - TZ=America/New_York
      # Override only secrets via environment variables
      - HEATTRAX_TAPO_USERNAME=your_username
      - HEATTRAX_TAPO_PASSWORD=your_password
    volumes:
      - /opt/heattrax/config.yaml:/app/config.yaml:ro
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

volumes:
  heattrax-logs:
  heattrax-state:
```

### Managing and Updating Your Deployment

- **View Container Status**: Navigate to `Containers` in Portainer
- **View Logs**: Click on the container and select `Logs`
- **Update Configuration**: Edit stack environment variables and click "Update the stack"
- **Restart Service**: Use the `Restart` button in the container details
- **Update Image**: Click "Recreate" to pull the latest image version

### Troubleshooting in Portainer

1. **Check Container Logs**:
   - Go to `Containers` → `heattrax-scheduler` → `Logs`
   - Look for connection errors or configuration issues

2. **Verify Environment Variables**:
   - Go to `Containers` → `heattrax-scheduler` → `Inspect`
   - Check the "Env" section to verify variables are set correctly

3. **Check Container Status**:
   - Container should show as "running" with a green indicator
   - If restarting frequently, check logs for errors

4. **Network Connectivity**:
   - Ensure `network_mode: host` is set for direct device access
   - Verify the Tapo device IP is accessible from the Docker host

## FAQ

### Device Discovery and Network Configuration

#### Q: Why is my device not being discovered even though it's online?

**A:** Device discovery uses UDP broadcast packets which are **limited to the local subnet**. If your device is on a different subnet or VLAN than the container, it will not be discovered. This is a fundamental limitation of the discovery protocol used by python-kasa and most smart home devices.

**Solutions:**
1. **Use Static IP Configuration (Recommended)**: Configure the device IP address manually using the `HEATTRAX_TAPO_IP_ADDRESS` environment variable. The scheduler will connect directly to the device even if discovery fails.
2. **Network Design**: Move the container to the same subnet/VLAN as your smart plugs.
3. **Docker Host Network Mode**: Use `network_mode: host` in your docker-compose.yml to give the container direct access to the host's network.

#### Q: What are subnet and VLAN limitations for device discovery?

**A:** Device discovery in python-kasa (and most smart home protocols) uses **UDP broadcast packets** which have these limitations:

- **Cannot cross subnet boundaries**: Broadcast packets are confined to the local network segment (e.g., 192.168.1.0/24)
- **Cannot cross VLANs**: Even if subnets are connected via routing, broadcast traffic typically doesn't cross VLAN boundaries
- **Router limitations**: Most routers block broadcast traffic between networks for security and performance reasons

**This is not a bug** - it's how UDP broadcast discovery works by design.

**What still works:**
- Direct device control using configured IP address works across subnets (assuming routing and firewall rules allow it)
- The scheduler will function normally with static configuration even if discovery fails
- All scheduling, weather monitoring, and safety features remain fully operational

#### Q: The logs say "Configured device IP is OUTSIDE the container's subnet" - is this a problem?

**A:** No, this is an **informational warning** to help you understand why discovery might fail. The scheduler will still attempt to connect directly to your configured device IP address.

**What this means:**
- Discovery cannot detect the device automatically (expected behavior)
- The device must be configured with a static IP address (which you've already done)
- Direct device control should still work if:
  - The device IP is reachable from the container
  - Network routing allows the connection
  - Firewall rules permit the traffic
  - Credentials are correct

**When to worry:**
- If you see repeated connection failures in the logs
- If the scheduler cannot control the device even with correct configuration
- If you want automatic device discovery (requires same subnet)

#### Q: How do I know what subnet my container is on?

**A:** The scheduler logs this information at startup:

```
Container network information:
  Local IP: 192.168.1.100
  Subnet: 192.168.1.0/24
  Note: Discovery is limited to this subnet due to UDP broadcast restrictions
```

You can also check manually:
```bash
# Inside the container
ip addr show

# From Docker host
docker exec <container_name> ip addr show
```

#### Q: Can I make discovery work across subnets/VLANs?

**A:** Generally no, but here are some advanced options:

1. **Use Docker Host Network Mode** (Easiest):
   ```yaml
   services:
     heattrax-scheduler:
       network_mode: host
   ```
   This gives the container direct access to the host's network interfaces.

2. **Configure Router for UDP Forwarding** (Advanced):
   - Some enterprise routers can forward directed broadcasts
   - Requires deep networking knowledge and may have security implications
   - Not recommended for home networks

3. **Place Container and Devices on Same Subnet** (Recommended):
   - Simplest and most reliable solution
   - Reorganize your network so IoT devices and containers share a subnet
   - Use VLANs for security/isolation at the switch level if needed

#### Q: Should I be concerned about the "SUBNET/VLAN LIMITATION DETECTED" warning?

**A:** No, this is an informational message to explain expected behavior. As long as:
- Your device IP is configured correctly
- The device is reachable from the container
- Device control operations work (check scheduler logs)

Then everything is working as designed. The warning simply explains why automatic discovery isn't finding your device.

#### Q: What's the difference between "discovery" and "device control"?

**A:** These are two separate operations:

**Discovery** (UDP broadcast):
- Automatically finds devices on the local network
- Limited to local subnet only
- Used during startup and periodic health checks
- Optional - only needed if you want automatic device detection

**Device Control** (Direct TCP/IP connection):
- Connects directly to a specific IP address
- Works across subnets (with proper routing)
- Used for all device operations (on/off/status)
- Required for the scheduler to function
- Works with static IP configuration

The scheduler **requires device control** but discovery is **optional**.

#### Q: My devices are discovered but the configured IP shows a warning. Why?

**A:** This can happen if:
1. The configured IP is on a different subnet than discovered devices
2. You have multiple network segments with devices on each
3. The configured device is offline/unreachable during discovery

Check:
- Is the configured IP correct?
- Is that device online and responsive?
- Are discovered devices on a different subnet than the configured one?

If the configured device works (scheduler can control it), you can safely ignore discovery warnings.

#### Q: How can I test if my device is reachable from the container?

**A:** Run these commands from inside the container:

```bash
# Test basic connectivity
docker exec <container_name> ping -c 3 <device_ip>

# Test device port (9999 for Tapo)
docker exec <container_name> nc -zv <device_ip> 9999

# Check routing
docker exec <container_name> ip route get <device_ip>
```

If these commands succeed, device control should work even if discovery fails.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [python-kasa](https://github.com/python-kasa/python-kasa) - TP-Link device control library
- [Open-Meteo](https://open-meteo.com/) - Free weather API
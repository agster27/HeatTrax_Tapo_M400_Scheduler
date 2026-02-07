# Environment Variables Reference

This document provides a comprehensive reference for all environment variables supported by HeatTrax Tapo M400 Scheduler.

## Overview

HeatTrax Scheduler can be configured entirely through environment variables, making it ideal for Docker deployments, Portainer stacks, and CI/CD pipelines. All environment variables use the `HEATTRAX_` prefix.

## Configuration Precedence

Configuration values are resolved in the following order (highest to lowest priority):

1. **Environment Variables** - Always checked first
2. **YAML Configuration File** - Used if no environment variable is set
3. **Default Values** - Used if neither environment variable nor YAML value is provided

### Environment Variable to YAML Synchronization

**New in v1.1**: On startup, any environment variable overrides are automatically synchronized back to `config.yaml`. This provides a smooth migration path:

- **While an env var is set**: The field is controlled by the environment variable and appears as read-only in the Web UI
- **When you remove an env var**: On next restart, the application falls back to the last value that was stored in `config.yaml` (which will be the value the env var provided)
- **Benefits**: You can start with env-based config, then gradually transition to Web UI management without losing your configuration values

**Example Workflow**:
1. Deploy with `HEATTRAX_LATITUDE=51.5074` environment variable
2. Startup: Value is applied and synced to `config.yaml`
3. Later, remove the env var from your Docker Compose / Portainer stack
4. Restart: Application loads `latitude: 51.5074` from `config.yaml`
5. Now you can edit latitude via Web UI and changes persist

This feature ensures `config.yaml` always reflects your last effective configuration, whether set via environment variables or the Web UI.

## Boolean Values

For boolean environment variables, the following values are accepted:

- **True**: `true`, `TRUE`, `1`, `yes`, `YES`, `on`, `ON`
- **False**: `false`, `FALSE`, `0`, `no`, `NO`, `off`, `OFF`

## Complete Environment Variables List

### Configuration File Path

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_CONFIG_PATH` | String | `config.yaml` | Path to YAML configuration file. Can be absolute or relative. |
| `TZ` | String | System default | System timezone (e.g., `America/New_York`). Not prefixed with `HEATTRAX_`. |

### Location Settings

Required for weather-based automation.

| Variable | Type | Required | Default | Description | Example |
|----------|------|----------|---------|-------------|---------|
| `HEATTRAX_LATITUDE` | Float | Yes* | None | Location latitude (-90 to 90) | `40.7128` |
| `HEATTRAX_LONGITUDE` | Float | Yes* | None | Location longitude (-180 to 180) | `-74.0060` |
| `HEATTRAX_TIMEZONE` | String | No | System TZ | Location timezone | `America/New_York` |

*Required when weather is enabled

### Weather API Settings

| Variable | Type | Default | Description | Example |
|----------|------|---------|-------------|---------|
| `HEATTRAX_WEATHER_ENABLED` | Boolean | `true` | Enable/disable weather-based scheduling | `true` |
| `HEATTRAX_WEATHER_PROVIDER` | String | `open-meteo` | Weather provider: `open-meteo` or `openweathermap` | `open-meteo` |
| `HEATTRAX_OPENWEATHERMAP_API_KEY` | String | None | OpenWeatherMap API key (required if provider is `openweathermap`) | `abc123...` |

### Weather Resilience Settings

Configure caching and retry behavior during API outages.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_WEATHER_CACHE_FILE` | String | `state/weather_cache.json` | Path to weather cache file |
| `HEATTRAX_WEATHER_CACHE_VALID_HOURS` | Float | `6.0` | How long cached data is trusted (hours) |
| `HEATTRAX_WEATHER_FORECAST_HORIZON_HOURS` | Integer | `12` | How many hours of forecast to store |
| `HEATTRAX_WEATHER_REFRESH_INTERVAL_MINUTES` | Integer | `10` | Normal polling interval (minutes) |
| `HEATTRAX_WEATHER_RETRY_INTERVAL_MINUTES` | Integer | `5` | Initial retry delay after failure (minutes) |
| `HEATTRAX_WEATHER_MAX_RETRY_INTERVAL_MINUTES` | Integer | `60` | Maximum backoff interval (minutes) |
| `HEATTRAX_WEATHER_OUTAGE_ALERT_AFTER_MINUTES` | Integer | `30` | Alert if offline longer than this (minutes) |

### Device Credentials

Required for controlling Tapo/Kasa devices.

| Variable | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `HEATTRAX_TAPO_USERNAME` | String | Yes | Tapo account username/email | `user@example.com` |
| `HEATTRAX_TAPO_PASSWORD` | String | Yes | Tapo account password | `your_password` |

**Note**: Device IPs and group configuration must be specified in `config.yaml` as they cannot be configured via environment variables.

### Weather Thresholds

> ⚠️ **Deprecated**: These environment variables configure legacy threshold settings. Use `schedules` with per-schedule `conditions` instead. See [SCHEDULING.md](../SCHEDULING.md) for the modern scheduling approach.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_THRESHOLD_TEMP_F` (deprecated) | Float | `34` | Temperature threshold in Fahrenheit |
| `HEATTRAX_LEAD_TIME_MINUTES` (deprecated) | Integer | `60` | Minutes before precipitation to turn on |
| `HEATTRAX_TRAILING_TIME_MINUTES` (deprecated) | Integer | `60` | Minutes after precipitation ends to keep on |

### Scheduler Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_CHECK_INTERVAL_MINUTES` | Integer | `10` | How often to check weather (minutes) |
| `HEATTRAX_FORECAST_HOURS` | Integer | `12` | How far ahead to look for precipitation (hours) |

### Safety Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_MAX_RUNTIME_HOURS` | Float | `6` | Maximum continuous runtime (hours) |
| `HEATTRAX_COOLDOWN_MINUTES` | Integer | `30` | Cooldown period after max runtime (minutes) |

### Morning Mode Settings

> ⚠️ **Deprecated**: These environment variables configure legacy morning mode. Use schedule entries of type `morning` in the `schedules` configuration instead. See [SCHEDULING.md](../SCHEDULING.md) for the modern scheduling approach.

Black ice protection with early morning activation.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_MORNING_MODE_ENABLED` (deprecated) | Boolean | `false` | Enable morning frost-clearing mode |
| `HEATTRAX_MORNING_MODE_START_HOUR` (deprecated) | Integer | `6` | Morning mode start hour (0-23) |
| `HEATTRAX_MORNING_MODE_END_HOUR` (deprecated) | Integer | `8` | Morning mode end hour (0-23) |

### Logging Settings

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `HEATTRAX_LOG_LEVEL` | String | `INFO` | Logging verbosity level | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

### Health Check Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_HEALTH_CHECK_INTERVAL_HOURS` | Float | `24` | Hours between device health checks |
| `HEATTRAX_HEALTH_CHECK_MAX_FAILURES` | Integer | `3` | Max consecutive failures before re-init |

### Health Server Settings

HTTP endpoints for container orchestration and external monitoring.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_HEALTH_SERVER_ENABLED` | Boolean | `false` | Enable HTTP health check server |
| `HEATTRAX_HEALTH_SERVER_HOST` | String | `0.0.0.0` | Host to bind to |
| `HEATTRAX_HEALTH_SERVER_PORT` | Integer | `4329` | Port for health endpoints |

**Endpoints** (when enabled):
- `GET http://localhost:4329/health` - Basic application health check (returns 200 if app is running)
- `GET http://localhost:4329/health/weather` - Weather-specific health check with current conditions and forecast

**Note**: The health server is **disabled by default**. Enable it only if needed for container orchestration (e.g., Kubernetes liveness probes, Docker health checks) or external monitoring systems.

### Web UI Settings

Configure the web interface for monitoring and configuration.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_WEB_HOST` | String | `0.0.0.0` | Host/IP address to bind web UI to. Default `0.0.0.0` allows access from other machines. Set to `127.0.0.1` to restrict to localhost only. |
| `HEATTRAX_WEB_PORT` | Integer | `4328` | Port for web UI |
| `HEATTRAX_WEB_PIN` | String | None | PIN for mobile control authentication (4-6 digits). Required for `/control` access. Can also be set via `web.pin` in config.yaml. |

**Security Note**: The default binding (`0.0.0.0`) makes the web UI accessible from other machines on your network. Do not expose this service directly to the internet. Keep it on your internal network, or place it behind a reverse proxy with authentication.

**Docker/Portainer Example**: The default `0.0.0.0` binding is suitable for Docker deployments. To restrict access to localhost only, set `HEATTRAX_WEB_HOST=127.0.0.1`.

### Reboot Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_REBOOT_PAUSE_SECONDS` | Integer | `60` | Pause before container restart (seconds). Set to 0 to disable. |

### Notification Settings - Global

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `HEATTRAX_NOTIFICATIONS_REQUIRED` | Boolean | `false` | If true, misconfigured enabled providers cause startup failure |
| `HEATTRAX_NOTIFICATIONS_TEST_ON_STARTUP` | Boolean | `false` | Send test notification on successful startup |

### Notification Settings - Email

| Variable | Type | Default | Description | Example |
|----------|------|---------|-------------|---------|
| `HEATTRAX_NOTIFICATION_EMAIL_ENABLED` | Boolean | `false` | Enable email notifications | `true` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST` | String | `smtp.gmail.com` | SMTP server hostname | `smtp.gmail.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT` | Integer | `587` | SMTP server port | `587` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME` | String | None | SMTP authentication username | `user@example.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD` | String | None | SMTP authentication password | `app_password` |
| `HEATTRAX_NOTIFICATION_EMAIL_FROM` | String | None | From email address | `sender@example.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_TO` | String | None | To email addresses (comma-separated) | `user1@example.com,user2@example.com` |
| `HEATTRAX_NOTIFICATION_EMAIL_USE_TLS` | Boolean | `true` | Use TLS for SMTP connection | `true` |

### Notification Settings - Webhook

| Variable | Type | Default | Description | Example |
|----------|------|---------|-------------|---------|
| `HEATTRAX_NOTIFICATION_WEBHOOK_ENABLED` | Boolean | `false` | Enable webhook notifications | `true` |
| `HEATTRAX_NOTIFICATION_WEBHOOK_URL` | String | None | Webhook URL for HTTP POST | `https://hooks.slack.com/...` |

### Notification Settings - Forecast Summaries

| Variable | Type | Default | Description | Valid Values |
|----------|------|---------|-------------|--------------|
| `HEATTRAX_NOTIFICATION_FORECAST_ENABLED` | Boolean | `false` | Enable forecast summary notifications | `true`, `false` |
| `HEATTRAX_NOTIFICATION_FORECAST_NOTIFY_MODE` | String | `always` | When to send forecast notifications | `always`, `on_change` |

**Note**: Per-event routing configuration (which events go to which providers) must be specified in `config.yaml` and cannot be overridden via environment variables.

## Usage Examples

### Docker Compose with Environment Variables

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      # System
      - TZ=America/New_York
      
      # Location (Required)
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TIMEZONE=America/New_York
      
      # Device Credentials (Required)
      - HEATTRAX_TAPO_USERNAME=user@example.com
      - HEATTRAX_TAPO_PASSWORD=your_password
      
      # Weather Settings
      - HEATTRAX_WEATHER_ENABLED=true
      - HEATTRAX_WEATHER_PROVIDER=open-meteo
      # DEPRECATED: Use schedules with conditions instead
      - HEATTRAX_THRESHOLD_TEMP_F=34
      - HEATTRAX_LEAD_TIME_MINUTES=60
      - HEATTRAX_TRAILING_TIME_MINUTES=60
      
      # Scheduler Settings
      - HEATTRAX_CHECK_INTERVAL_MINUTES=10
      - HEATTRAX_FORECAST_HOURS=12
      
      # Safety Settings
      - HEATTRAX_MAX_RUNTIME_HOURS=6
      - HEATTRAX_COOLDOWN_MINUTES=30
      
      # Morning Mode - DEPRECATED: Use schedule type 'morning' instead
      - HEATTRAX_MORNING_MODE_ENABLED=true
      - HEATTRAX_MORNING_MODE_START_HOUR=6
      - HEATTRAX_MORNING_MODE_END_HOUR=8
      
      # Logging
      - HEATTRAX_LOG_LEVEL=INFO
      
      # Web UI (for network access)
      - HEATTRAX_WEB_HOST=0.0.0.0
      - HEATTRAX_WEB_PORT=4328
      # - HEATTRAX_WEB_PIN=1234  # Optional: PIN for mobile control authentication (4-6 digits)
      
      # Health Check API (Optional - for container orchestration)
      # - HEATTRAX_HEALTH_SERVER_ENABLED=true
      # - HEATTRAX_HEALTH_SERVER_PORT=4329
      
      # Notifications (Optional)
      - HEATTRAX_NOTIFICATIONS_REQUIRED=false
      - HEATTRAX_NOTIFICATIONS_TEST_ON_STARTUP=false
      - HEATTRAX_NOTIFICATION_EMAIL_ENABLED=false
      - HEATTRAX_NOTIFICATION_WEBHOOK_ENABLED=false
    
    volumes:
      - ./config.yaml:/app/config.yaml:ro  # Required for device IPs
      - ./logs:/app/logs
      - ./state:/app/state
    
    restart: unless-stopped
    network_mode: host
```

### Using .env File

Create a `.env` file:

```bash
# System
TZ=America/New_York

# Location
HEATTRAX_LATITUDE=40.7128
HEATTRAX_LONGITUDE=-74.0060
HEATTRAX_TIMEZONE=America/New_York

# Device Credentials
HEATTRAX_TAPO_USERNAME=user@example.com
HEATTRAX_TAPO_PASSWORD=your_password

# Weather Settings
HEATTRAX_WEATHER_ENABLED=true
HEATTRAX_WEATHER_PROVIDER=open-meteo
# DEPRECATED: Use schedules with conditions instead
HEATTRAX_THRESHOLD_TEMP_F=34

# Scheduler Settings
HEATTRAX_CHECK_INTERVAL_MINUTES=10
HEATTRAX_FORECAST_HOURS=12

# Safety Settings
HEATTRAX_MAX_RUNTIME_HOURS=6
HEATTRAX_COOLDOWN_MINUTES=30

# Morning Mode - DEPRECATED: Use schedule type 'morning' instead
HEATTRAX_MORNING_MODE_ENABLED=true

# Web UI (for network access - set to 0.0.0.0 for Docker/Portainer)
HEATTRAX_WEB_HOST=0.0.0.0
HEATTRAX_WEB_PORT=4328
# HEATTRAX_WEB_PIN=1234  # Optional: PIN for mobile control authentication (4-6 digits)

# Health Check API (Optional - for container orchestration)
# HEATTRAX_HEALTH_SERVER_ENABLED=true
# HEATTRAX_HEALTH_SERVER_PORT=4329

# Logging
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
      - ./config.yaml:/app/config.yaml:ro
      - ./logs:/app/logs
      - ./state:/app/state
    restart: unless-stopped
    network_mode: host
```

**Important**: Add `.env` to `.gitignore` to prevent committing secrets!

### Portainer Stack with Secrets

1. Create secrets in Portainer for sensitive data
2. Use environment variables for non-sensitive configuration
3. Mount `config.yaml` for device IPs and group configuration

See README.md for detailed Portainer deployment examples.

## Security Best Practices

1. **Never commit secrets to version control**
   - Use `.env` files locally
   - Add `.env` to `.gitignore`

2. **Use Docker secrets or Portainer secrets for production**
   - Store credentials securely
   - Reference secrets in compose files

3. **Restrict file permissions**
   - Ensure `.env` files have restricted permissions: `chmod 600 .env`

4. **Rotate credentials regularly**
   - Update environment variables when rotating passwords
   - Restart containers to apply changes

5. **Use separate credentials for different environments**
   - Dev, staging, and production should have different credentials

## Troubleshooting

### Configuration Not Loading

If environment variables don't seem to be applied:

1. Check variable names match exactly (case-sensitive)
2. Ensure `HEATTRAX_` prefix is used
3. Verify boolean values use accepted formats
4. Check container logs for configuration loading messages
5. Use `docker exec <container> env | grep HEATTRAX` to verify variables

### Missing Required Configuration

If you see "Missing required configuration" errors:

1. Verify all required variables are set:
   - `HEATTRAX_LATITUDE` and `HEATTRAX_LONGITUDE` (if weather enabled)
   - `HEATTRAX_TAPO_USERNAME` and `HEATTRAX_TAPO_PASSWORD`
   - Device IPs in `config.yaml`

2. Check that `config.yaml` is mounted correctly if using Docker

3. Review startup logs for detailed error messages

### Boolean Values Not Working

If boolean environment variables don't work as expected:

- Use lowercase `true` or `false` (recommended)
- Avoid quotes in docker-compose: `- VAR=true` not `- VAR="true"`
- Check logs for boolean parsing messages

## Additional Resources

- [README.md](README.md) - Complete project documentation
- [QUICKSTART.md](QUICKSTART.md) - Fast 5-minute setup guide
- [SETUP.md](SETUP.md) - Detailed setup instructions
- [HEALTH_CHECK.md](HEALTH_CHECK.md) - Health check and notification configuration
- [config.example.yaml](config.example.yaml) - Example YAML configuration with all options

# HeatTrax Web UI Guide

## Overview

HeatTrax Scheduler includes a browser-based web UI for monitoring system status and editing configuration without needing to directly edit YAML files or restart the container.

## Features

### Status Dashboard
- Real-time view of system configuration
- Config file path and last modified time
- Weather mode status
- Device group information
- Last error messages (if any)

### Health Dashboard
- **Health Summary**: Quick overview of system health metrics
  - System health status (✅ or ❌)
  - Configuration loaded status
  - Active device groups count
  - Last weather fetch time
- **Health Checks**: Detailed health information
  - System status (ok/error)
  - Current timestamp
  - Configuration loaded status
- **Device Health**: Expected vs actual device states
  - Shows all configured devices with their current and expected states
  - Green border indicates device is in expected state
  - Red border indicates mismatch between current and expected state
  - Displays expected ON/OFF times based on schedule or weather forecast
  - Shows last state change timestamp
  - Displays any device errors

### Configuration Editor
- Edit configuration directly in your browser using a structured form
- **Organized into sections**: Location, Weather, Device Credentials, Thresholds & Scheduler, Safety & Morning Mode, Logging, Health & Reboot, Notifications, and Web UI
- **Environment Override Display**: Settings controlled by environment variables are shown as read-only with the env var name displayed
  - Readonly fields are disabled and show helper text: "Set via env: ENV_VAR_NAME"
  - Only YAML-backed settings can be edited via the form
  - Secrets (passwords, API keys) are masked in the display
- **Field types matched to data**:
  - Numbers use numeric inputs with appropriate step values
  - Booleans use checkboxes
  - Options (like log level, weather provider) use dropdown selects
  - Secrets use password inputs
- Validation before saving
- Changes written to `config.yaml` atomically
- **Automatic restart after save**: When you save configuration via the Web UI, the application will automatically restart to ensure the new configuration takes effect
  - The restart is triggered by the process exiting (via `os._exit(0)`)
  - With Docker's `restart: always` policy, the container restarts automatically
  - The Web UI will become temporarily unavailable during the restart (typically 5-10 seconds)
  - If running without a restart policy, you'll need to manually restart the container
- Secrets are preserved during updates

## Quick Start

1. **Start the container** (web UI is enabled by default):
   ```bash
   docker-compose up -d
   ```

2. **Access the web UI**:
   - Open your browser to `http://localhost:4328`
   - Default binding is to localhost (127.0.0.1) for security

3. **View status**:
   - Status tab shows current system state
   - Click "Refresh" to update

4. **Check system health**:
   - Switch to Health tab
   - View health summary with system metrics
   - Check device health to see expected vs actual states
   - Green-bordered devices are in expected state
   - Red-bordered devices indicate a mismatch
   - Click "Refresh" to update health data

5. **Edit configuration**:
   - Switch to Configuration tab
   - **View environment overrides**: If any settings are controlled by environment variables, a blue info box at the top lists them
   - **Edit settings**: Use the structured form with organized sections to modify settings
     - Location: latitude, longitude, timezone
     - Weather: weather enabled, provider, API keys
     - Device Credentials: Tapo username and password
     - Thresholds & Scheduler: temperature thresholds, lead/trailing times, intervals
     - Safety & Morning Mode: max runtime, cooldown, morning mode configuration
     - Logging: log level selection
     - Health & Reboot: health check settings, reboot configuration
     - Notifications: global settings, email configuration, webhook settings
     - Web UI: bind host and port
   - Fields that are environment-controlled show "Set via env: ENV_VAR_NAME" and are read-only
   - Click "Save Configuration" to apply changes
   - **Automatic restart**: After saving, the application will restart automatically to load the new configuration
     - The Web UI will show a message: "Configuration saved! Application is restarting."
     - The page will become temporarily unavailable (typically 5-10 seconds)
     - Once the container has restarted, refresh the page to access the Web UI again
     - This requires Docker's restart policy to be enabled (see Configuration section below)
   - System validates before saving

## Configuration

### Enable/Disable Web UI

In `config.yaml`:
```yaml
web:
  enabled: true  # Set to false to disable
  bind_host: "127.0.0.1"
  port: 4328
```

Or via environment variable:
```bash
HEATTRAX_WEB_ENABLED=true
```

### Change Port

In `config.yaml`:
```yaml
web:
  port: 4328  # Change to your preferred port
```

### Network Access

⚠️ **Security Warning**: By default, the web UI only accepts connections from localhost.

To allow access from other machines:

1. Edit `config.yaml`:
   ```yaml
   web:
     bind_host: "0.0.0.0"  # Allow connections from any IP
   ```

2. Update `docker-compose.yml` to expose the port:
   ```yaml
   ports:
     - "4328:4328"  # Already included
   ```

3. Restart the container

**Important**: Authentication is currently disabled. Only expose the web UI on trusted networks. Authentication support is planned for a future release.

### Docker Restart Policy

For the automatic restart feature to work when saving configuration via the Web UI, ensure your Docker container has a restart policy configured.

In `docker-compose.yml` (recommended):
```yaml
services:
  heattrax-scheduler:
    restart: always  # Container will restart automatically after exit
```

When using `docker run`:
```bash
docker run --restart=always ...
```

**Available restart policies:**
- `always`: Always restart the container when it stops
- `unless-stopped`: Restart unless explicitly stopped
- `on-failure`: Only restart on non-zero exit codes

**Without a restart policy**: If you run the container without a restart policy, saving configuration via the Web UI will cause the application to exit. You'll need to manually restart the container:
```bash
docker start heattrax-scheduler
```

## API Endpoints

The web UI is built on a JSON REST API that you can also use programmatically:

### GET /api/health
Health check endpoint.

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2024-11-17T00:00:00.000000",
  "config_loaded": true
}
```

### GET /api/status
System status information.

**Response**:
```json
{
  "config_path": "/app/config.yaml",
  "config_last_modified": "2024-11-17T00:00:00.000000",
  "weather_enabled": true,
  "device_groups": {
    "heated_mats": {
      "enabled": true,
      "device_count": 2
    }
  },
  "timestamp": "2024-11-17T00:00:00.000000"
}
```

### GET /api/config
Current configuration with source metadata. Fields include information about whether they're controlled by environment variables or YAML.

**Response**:
```json
{
  "location": {
    "latitude": {
      "value": 40.7128,
      "source": "env",
      "env_var": "HEATTRAX_LATITUDE",
      "readonly": true
    },
    "longitude": {
      "value": -74.0060,
      "source": "yaml",
      "readonly": false
    },
    "timezone": {
      "value": "America/New_York",
      "source": "yaml",
      "readonly": false
    }
  },
  "devices": {
    "credentials": {
      "username": {
        "value": "user@example.com",
        "source": "yaml",
        "readonly": false
      },
      "password": {
        "value": "********",
        "source": "yaml",
        "readonly": false
      }
    }
  },
  ...
}
```

**Field Metadata**:
- `value`: The actual configuration value
- `source`: Either `"env"` (from environment variable) or `"yaml"` (from config.yaml)
- `env_var`: Name of the environment variable (only present when `source` is `"env"`)
- `readonly`: Boolean indicating if the field can be modified via the UI

### PUT or POST /api/config
Update configuration. Note: Fields overridden by environment variables cannot be changed via this API.

**Request**:
```json
{
  "location": {
    "latitude": 42.0,
    "longitude": -71.0
  },
  ...
}
```

**Important**: Send the plain configuration values (without the metadata structure). The API will merge your changes with existing secrets and apply them to `config.yaml`.

**Response** (success):
```json
{
  "status": "ok",
  "message": "Configuration updated successfully",
  "restart_required": "false"
}
```

**Response** (validation error):
```json
{
  "status": "error",
  "message": "Validation error: Invalid latitude: 999.0 (must be -90 to 90)",
  "restart_required": "false"
}
```

### GET /api/ping
Simple liveness check.

**Response**:
```json
{
  "status": "ok",
  "message": "pong"
}
```

### POST /api/restart
Trigger application restart by exiting the process. This endpoint is automatically called by the Web UI after saving configuration.

**Important**: This endpoint requires a Docker restart policy (e.g., `restart: always`) to automatically restart the container after exit. Without a restart policy, the application will exit and require manual restart.

**Request**: No body required (POST request only)

**Response**:
```json
{
  "status": "ok",
  "message": "Application is restarting..."
}
```

**Behavior**:
- Logs restart request at WARNING level
- Flushes all log handlers to ensure messages are written
- Exits the process with `os._exit(0)` after a 0.5 second delay
- Docker's restart policy automatically restarts the container
- The Web UI will become temporarily unavailable (5-10 seconds)

**Security**: This endpoint only accepts POST requests to prevent accidental restarts from simple link clicks.

## Secret Handling

Secrets (passwords, API keys, etc.) are handled securely:

1. **Masked in API responses**: Secret fields always show `********` when retrieved via API
2. **Write-only behavior**: When updating config with masked values, the existing secret is preserved
3. **Only update when provided**: To change a secret, provide the new value; leaving it masked keeps the current value
4. **Environment variable priority**: If a secret is set via environment variable, it takes precedence over YAML and cannot be changed via the Web UI

### Example: Updating Config Without Changing Password

```javascript
// Get current config (password will be masked, metadata will be present)
const response = await fetch('/api/config').then(r => r.json());

// Extract plain values for editing
const config = extractConfigValues(response);

// Modify non-secret fields
config.location.latitude = 42.0;

// Save config - password stays unchanged because it's masked
await fetch('/api/config', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(config)
});
```

## Automatic Restart on Config Save

**New in v1.2**: When you save configuration via the Web UI, the application automatically restarts to ensure all changes take effect immediately.

**How it works:**
1. After successfully saving configuration, the Web UI calls the `/api/restart` endpoint
2. The application logs the restart request and exits cleanly (via `os._exit(0)`)
3. Docker's restart policy (e.g., `restart: always`) automatically restarts the container
4. The new configuration is loaded when the container starts up
5. After 5-10 seconds, you can refresh the page to access the Web UI again

**Benefits:**
- No need to manually restart the container after configuration changes
- All settings take effect immediately, including those that previously required restart
- Consistent behavior for all configuration changes

**Requirements:**
- Docker restart policy must be configured (see Docker Restart Policy section above)
- Without a restart policy, the application will exit and require manual restart

**Note**: The Web UI will become temporarily unavailable during the restart. Wait 5-10 seconds and refresh the page to reconnect.

## Troubleshooting

### Cannot access web UI

1. **Check if web UI is enabled**:
   ```bash
   docker logs heattrax-scheduler | grep "web"
   ```

2. **Verify port is exposed**:
   ```bash
   docker ps | grep heattrax-scheduler
   ```

3. **Check firewall settings** if accessing from another machine

### Web UI shows "Connection refused"

- The scheduler may still be starting up. Wait 10-20 seconds and try again.
- Check container logs for errors:
  ```bash
  docker logs heattrax-scheduler
  ```

### Configuration changes not saving

- Check container logs for validation errors
- Ensure the config file is not mounted as read-only in Docker
- Verify you have write permissions to the config directory

### Secrets not being preserved

This is normal behavior when secrets are masked (`********`). The form automatically preserves existing values when you save with masked secrets displayed. To change a secret, clear the field and enter the new value, or type over the masked placeholder.

## Advanced Usage

### Programmatic Access

You can use the JSON API from scripts or automation tools:

```bash
# Get status
curl http://localhost:4328/api/status

# Update config
curl -X PUT http://localhost:4328/api/config \
  -H "Content-Type: application/json" \
  -d @new_config.json
```

### Integration with Home Automation

The API can be integrated with home automation systems:

```python
import requests

# Get current status
status = requests.get('http://localhost:4328/api/status').json()
print(f"Weather enabled: {status['weather_enabled']}")

# Update threshold
config = requests.get('http://localhost:4328/api/config').json()
config['thresholds']['temperature_f'] = 32
response = requests.put('http://localhost:4328/api/config', json=config)
print(f"Update result: {response.json()['message']}")
```

## Security Best Practices

1. **Keep default localhost binding** unless you need remote access
2. **Use a reverse proxy** (like nginx) if exposing to the internet
3. **Enable authentication** (when available in future releases)
4. **Use HTTPS/TLS** for remote access
5. **Keep secrets out of version control**
6. **Regularly update** to get security fixes

## Future Enhancements

Planned features for future releases:
- HTTP authentication (username/password)
- HTTPS/TLS support
- Role-based access control
- Real-time status updates via WebSocket
- Configuration history and rollback
- Dark mode theme

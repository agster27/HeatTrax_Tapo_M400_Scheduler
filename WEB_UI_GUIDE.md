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

### Configuration Editor
- Edit configuration directly in your browser
- **Environment Override Display**: Clearly shows which settings are controlled by environment variables
  - Settings overridden by env vars are displayed as read-only with the env var name
  - Only YAML-backed settings can be edited via the UI
  - Secrets (passwords, API keys) are masked in the display
- Syntax validation before saving
- Changes written to `config.yaml` atomically
- Hot-reload for most settings (some require restart)
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

4. **Edit configuration**:
   - Switch to Configuration tab
   - **View environment overrides**: The top section shows settings controlled by environment variables (read-only)
   - **Edit YAML settings**: Use the JSON editor below to modify settings not overridden by env vars
   - Click "Save Configuration" to apply changes
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

## Hot Reload vs. Restart Required

Most configuration changes take effect immediately without restarting:
- Location settings
- Weather thresholds
- Notification settings
- Logging levels

Some changes require a restart:
- Device group structure changes
- Weather provider changes
- Web server port changes
- Health server port changes

The API will indicate when a restart is needed with `"restart_required": "true"` in the response.

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

This is normal behavior when secrets are masked (`********`). The system preserves the existing value when you save with a masked secret. To change a secret, provide the new value instead of `********`.

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

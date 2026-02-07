# HeatTrax API Reference

Complete API documentation for the HeatTrax Tapo M400 Scheduler REST API.

## Table of Contents

- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
- [Response Formats](#response-formats)
- [Endpoints by Category](#endpoints-by-category)
  - [Authentication](#authentication-endpoints)
  - [Health & Monitoring](#health--monitoring-endpoints)
  - [Device Control](#device-control-endpoints)
  - [Schedule Management](#schedule-management-endpoints)
  - [Weather](#weather-endpoints)
  - [Configuration](#configuration-endpoints)
  - [Automation & Overrides](#automation--overrides-endpoints)
  - [Vacation Mode & Solar Times](#vacation-mode--solar-times-endpoints)
  - [Mobile Control (Protected)](#mobile-control-endpoints-protected)
  - [Notifications](#notification-endpoints)

---

## Overview

The HeatTrax Scheduler provides a comprehensive JSON REST API for monitoring, controlling, and configuring the system. The API supports:

- Real-time device control
- Schedule management
- Weather data access
- Configuration updates
- Health monitoring
- Notification management

## Base URL

```
http://localhost:4328
```

**Default Configuration:**
- Host: `0.0.0.0` (accessible from network when Docker ports are mapped)
- Port: `4328`

**Configure via:**
- `config.yaml`: `web.bind_host` and `web.port`
- Environment variables: `HEATTRAX_WEB_HOST` and `HEATTRAX_WEB_PORT`

## Authentication

### Desktop Dashboard Routes
**Authentication:** ❌ **Not required**

The desktop dashboard routes (`/`, `/ui`) and most API endpoints do not require authentication. These include:
- All health and monitoring endpoints
- Device status and control
- Schedule management
- Weather data
- Configuration endpoints

**Security Note:** Ensure the web UI is not exposed to the internet without a reverse proxy. Bind to `127.0.0.1` (localhost only) for maximum security.

### Mobile Control Routes
**Authentication:** ✅ **Required (PIN-based)**

Mobile control routes (`/control` page and `/api/mat/*` endpoints) require PIN authentication:

**Protected endpoints:**
- `GET /api/mat/status`
- `POST /api/mat/control`
- `POST /api/mat/reset-auto`
- `GET /control` (UI page)

**Authentication flow:**
1. User visits `/control/login` (login page)
2. User submits PIN via `POST /api/auth/login`
3. Server creates session (24-hour lifetime)
4. Session cookie is used for subsequent requests
5. Unauthenticated requests return `401` for API routes or redirect to login for page routes

**Configure PIN:**
- `config.yaml`: `web.pin`
- Environment variable: `HEATTRAX_WEB_PIN`

**Session lifetime:** 24 hours

### Authentication Header

No authentication headers are required. Authentication is session-based using cookies after successful PIN login.

## Response Formats

### Success Response

```json
{
  "status": "ok",
  "message": "Operation completed successfully",
  "data": { ... }
}
```

### Error Response

```json
{
  "status": "error",
  "error": "Error message",
  "details": "Additional error details"
}
```

### Authentication Error (401)

```json
{
  "success": false,
  "error": "Authentication required",
  "redirect": "/control/login"
}
```

---

## Endpoints by Category

## Authentication Endpoints

### POST /api/auth/login

Authenticate with PIN and create session.

**Authentication:** ❌ Not required (this is the login endpoint)

**Request:**
```json
{
  "pin": "1234"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Login successful"
}
```

**Response (401 Unauthorized):**
```json
{
  "success": false,
  "error": "Invalid PIN"
}
```

**Notes:**
- Creates a session cookie valid for 24 hours
- Session is used for subsequent requests to protected endpoints
- PIN is configured via `web.pin` in config.yaml or `HEATTRAX_WEB_PIN` environment variable

---

## Health & Monitoring Endpoints

### GET /api/health

Basic application health check.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/health
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-11-23T15:30:45.123456",
  "config_loaded": true
}
```

**Response (500 Error):**
```json
{
  "status": "error",
  "timestamp": "2025-11-23T15:30:45.123456",
  "details": "Configuration error message"
}
```

---

### GET /api/ping

Simple liveness check.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/ping
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "pong"
}
```

---

### GET /api/status

Get comprehensive system status including device states, weather, and scheduler status.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/status
```

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-23T15:30:45.123456",
  "scheduler": {
    "running": true,
    "vacation_mode": false,
    "weather_enabled": true
  },
  "groups": {
    "heated_mats": {
      "enabled": true,
      "state": "on",
      "active_schedule": "Morning Warm-up",
      "next_event": {
        "time": "2025-11-23T22:00:00",
        "action": "off"
      }
    }
  },
  "weather": {
    "last_update": "2025-11-23T14:00:00",
    "temperature_f": 28.5,
    "conditions": "Clear"
  }
}
```

---

### GET /api/system/status

Get extended system status with notification availability and PIN configuration.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/system/status
```

**Response (200 OK):**
```json
{
  "timestamp": "2025-11-23T15:30:45.123456",
  "config_loaded": true,
  "pin_configured": true,
  "notifications_available": true,
  "groups": {
    "heated_mats": {
      "enabled": true,
      "device_count": 2
    }
  }
}
```

---

## Device Control Endpoints

### GET /api/devices/status

Get detailed status of all devices, outlets, reachability, and initialization summary.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/devices/status
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "timestamp": "2025-11-23T15:30:45.123456",
  "groups": {
    "heated_mats": {
      "devices": [
        {
          "alias": "Front Driveway Mat",
          "ip": "192.168.1.100",
          "model": "EP40M",
          "outlets": [
            {
              "index": 0,
              "name": "Outlet 1",
              "state": "on",
              "reachable": true,
              "last_state_change": "2025-11-23T06:00:00"
            },
            {
              "index": 1,
              "name": "Outlet 2",
              "state": "off",
              "reachable": true,
              "last_state_change": "2025-11-23T10:00:00"
            }
          ]
        }
      ]
    }
  },
  "summary": {
    "total_devices": 1,
    "total_outlets": 2,
    "outlets_on": 1,
    "outlets_off": 1,
    "unreachable": 0
  }
}
```

---

### POST /api/devices/control

Control specific device/outlet (on/off). Overrides scheduler temporarily.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "device_ip": "192.168.1.100",
  "outlet_index": 0,
  "action": "on"
}
```

**Parameters:**
- `device_ip` (required): IP address of the device
- `outlet_index` (required): Outlet index (0 or 1 for EP40M)
- `action` (required): `"on"` or `"off"`

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Device outlet turned on successfully"
}
```

**Response (400 Bad Request):**
```json
{
  "status": "error",
  "error": "Invalid action. Must be 'on' or 'off'"
}
```

---

### POST /api/groups/<group_name>/control

Control all outlets in a group simultaneously.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "action": "on"
}
```

**Parameters:**
- `group_name` (path): Name of the device group
- `action` (body, required): `"on"` or `"off"`

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Group 'heated_mats' turned on successfully",
  "results": {
    "192.168.1.100": {
      "outlet_0": "success",
      "outlet_1": "success"
    }
  }
}
```

---

## Schedule Management Endpoints

### GET /api/groups/<group_name>/schedules

Get all schedules for a group.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/groups/heated_mats/schedules
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "group": "heated_mats",
  "schedules": [
    {
      "index": 0,
      "name": "Morning Warm-up",
      "enabled": true,
      "type": "time",
      "on_time": "06:00",
      "off_time": "09:00",
      "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    },
    {
      "index": 1,
      "name": "Evening Protection",
      "enabled": true,
      "type": "solar_offset",
      "on_offset": -60,
      "off_offset": 30,
      "days": ["Saturday", "Sunday"]
    }
  ]
}
```

---

### POST /api/groups/<group_name>/schedules

Add a new schedule to a group.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "name": "Weekend Warming",
  "enabled": true,
  "type": "time",
  "on_time": "07:00",
  "off_time": "11:00",
  "days": ["Saturday", "Sunday"]
}
```

**Response (201 Created):**
```json
{
  "status": "ok",
  "message": "Schedule added successfully",
  "schedule_index": 2
}
```

---

### GET /api/groups/<group_name>/schedules/<int:schedule_index>

Get a specific schedule by index.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/groups/heated_mats/schedules/0
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "schedule": {
    "index": 0,
    "name": "Morning Warm-up",
    "enabled": true,
    "type": "time",
    "on_time": "06:00",
    "off_time": "09:00",
    "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
  }
}
```

---

### PUT /api/groups/<group_name>/schedules/<int:schedule_index>

Update a specific schedule.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "name": "Updated Morning Warm-up",
  "enabled": true,
  "type": "time",
  "on_time": "05:30",
  "off_time": "09:30",
  "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Schedule updated successfully"
}
```

---

### DELETE /api/groups/<group_name>/schedules/<int:schedule_index>

Delete a specific schedule.

**Authentication:** ❌ Not required

**Request:**
```bash
curl -X DELETE http://localhost:4328/api/groups/heated_mats/schedules/2
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Schedule deleted successfully"
}
```

---

### PUT /api/groups/<group_name>/schedules/<int:schedule_index>/enabled

Toggle a schedule enabled/disabled status.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "enabled": false
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Schedule disabled successfully"
}
```

---

## Weather Endpoints

### GET /api/weather/forecast

Get cached weather forecast data (read-only). Includes black ice risk detection.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/weather/forecast
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "last_update": "2025-11-23T14:00:00",
  "forecast": [
    {
      "time": "2025-11-23T15:00:00",
      "temperature_f": 28.5,
      "conditions": "Clear",
      "precipitation_chance": 0.0,
      "black_ice_risk": true
    },
    {
      "time": "2025-11-23T16:00:00",
      "temperature_f": 27.2,
      "conditions": "Partly Cloudy",
      "precipitation_chance": 0.1,
      "black_ice_risk": true
    }
  ]
}
```

**Notes:**
- Weather data is cached to reduce API calls to weather provider
- Black ice risk is calculated based on temperature and recent precipitation
- Update frequency is configurable via `weather.cache_duration`

---

### GET /api/weather/mat-forecast

Get predicted mat ON/OFF windows per group over the forecast horizon.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/weather/mat-forecast
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "forecast_start": "2025-11-23T15:00:00",
  "forecast_end": "2025-11-26T15:00:00",
  "groups": {
    "heated_mats": {
      "windows": [
        {
          "start": "2025-11-23T18:00:00",
          "end": "2025-11-24T09:00:00",
          "reason": "Temperature below 32°F threshold"
        },
        {
          "start": "2025-11-24T22:00:00",
          "end": "2025-11-25T11:00:00",
          "reason": "Black ice risk detected"
        }
      ]
    }
  }
}
```

**Notes:**
- Predictions are based on weather forecast and configured thresholds
- Accounts for lead/trailing times configured in automation settings
- Useful for planning and energy estimation

---

## Configuration Endpoints

### GET /api/config

Get current configuration with source metadata (YAML vs environment-overridden).

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/config
```

**Response (200 OK):**
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
  "weather": {
    "enabled": {
      "value": true,
      "source": "yaml",
      "readonly": false
    },
    "provider": {
      "value": "openweathermap",
      "source": "yaml",
      "readonly": false
    }
  }
}
```

**Field Metadata:**
- `value`: The actual configuration value
- `source`: Either `"env"` (from environment variable) or `"yaml"` (from config.yaml)
- `env_var`: Name of the environment variable (only present when `source` is `"env"`)
- `readonly`: Boolean indicating if the field can be modified via the API

**Notes:**
- Secrets (passwords, API keys) are masked as `********` in responses
- Fields overridden by environment variables cannot be changed via the API
- Use this endpoint to understand which settings are environment-controlled

---

### PUT or POST /api/config

Update configuration settings. Writes changes to `config.yaml`.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "location": {
    "latitude": 42.0,
    "longitude": -71.0,
    "timezone": "America/New_York"
  },
  "thresholds": {
    "temperature_f": 33.0
  }
}
```

**Important Notes:**
- Send plain configuration values (without metadata structure)
- Fields overridden by environment variables cannot be changed
- Masked secrets (`********`) are preserved; provide new value to change
- Configuration is validated before saving
- Changes are written atomically to prevent corruption

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Configuration updated successfully",
  "restart_required": false
}
```

**Response (400 Bad Request - Validation Error):**
```json
{
  "status": "error",
  "message": "Validation error: Invalid latitude: 999.0 (must be -90 to 90)",
  "restart_required": false
}
```

---

### POST /api/credentials

Update Tapo device credentials. Requires application restart to take effect.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "username": "user@example.com",
  "password": "newpassword123"
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Credentials updated successfully. Restart required to take effect."
}
```

**Notes:**
- Credentials are written to config.yaml
- Application restart is required for credentials to take effect
- Use `/api/restart` to trigger restart after updating credentials

---

### GET /api/config/download

Download the current `config.yaml` file.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/config/download -o config.yaml
```

**Response (200 OK):**
- Content-Type: `application/x-yaml`
- Content-Disposition: `attachment; filename=config.yaml`
- Body: YAML file contents

**Notes:**
- Useful for backing up configuration
- Downloaded file includes all settings, including secrets
- Can be used with `/api/config/upload` to restore configuration

---

### POST /api/config/upload

Upload and validate a new `config.yaml` file. Creates backup before applying.

**Authentication:** ❌ Not required

**Request:**
```bash
curl -X POST http://localhost:4328/api/config/upload \
  -F "file=@config.yaml"
```

**Request (multipart/form-data):**
- Field name: `file`
- File type: YAML

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Configuration uploaded and validated successfully. Backup created at config.yaml.backup"
}
```

**Response (400 Bad Request - Validation Error):**
```json
{
  "status": "error",
  "error": "Validation failed",
  "details": "Invalid schedule configuration: missing 'on_time' field"
}
```

**Notes:**
- Validates configuration before applying
- Creates backup of existing config as `config.yaml.backup`
- Application restart may be required for some changes to take effect
- Use `/api/restart` to trigger restart after upload if needed

---

### POST /api/restart

Trigger application restart by exiting the process.

**Authentication:** ❌ Not required

**Request:**
```bash
curl -X POST http://localhost:4328/api/restart
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Application is restarting..."
}
```

**Important Notes:**
- Requires Docker restart policy (e.g., `restart: always`) to automatically restart the container
- Without a restart policy, the application will exit and require manual restart
- The web UI will become temporarily unavailable (5-10 seconds)
- Automatically called by the Web UI after saving configuration

**Security:**
- Only accepts POST requests to prevent accidental restarts from simple link clicks

---

## Automation & Overrides Endpoints

### GET /api/groups/<group_name>/automation

Get automation configuration for a group, including base settings, overrides, and effective configuration.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/groups/heated_mats/automation
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "group": "heated_mats",
  "base": {
    "weather_control": true,
    "precipitation_control": true,
    "morning_mode": {
      "enabled": true,
      "start_time": "06:00",
      "duration_hours": 3
    }
  },
  "overrides": {
    "weather_control": false
  },
  "effective": {
    "weather_control": false,
    "precipitation_control": true,
    "morning_mode": {
      "enabled": true,
      "start_time": "06:00",
      "duration_hours": 3
    }
  }
}
```

**Fields:**
- `base`: Default automation settings from `config.yaml`
- `overrides`: Runtime overrides applied via API
- `effective`: Computed effective configuration (base + overrides)

---

### PATCH /api/groups/<group_name>/automation

Update automation overrides for a group. Overrides are temporary and reset on application restart.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "weather_control": false,
  "precipitation_control": true,
  "morning_mode": {
    "enabled": true,
    "start_time": "06:00",
    "duration_hours": 3
  }
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Automation overrides updated successfully",
  "effective": {
    "weather_control": false,
    "precipitation_control": true,
    "morning_mode": {
      "enabled": true,
      "start_time": "06:00",
      "duration_hours": 3
    }
  }
}
```

**Notes:**
- Overrides are not persisted to `config.yaml`
- Overrides are cleared on application restart
- Use this to temporarily disable weather control or adjust morning mode
- To make permanent changes, use `PUT /api/config`

---

## Vacation Mode & Solar Times Endpoints

### GET /api/vacation_mode

Get current vacation mode status.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/vacation_mode
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "vacation_mode": false
}
```

---

### PUT /api/vacation_mode

Set vacation mode status. Persists to `config.yaml`.

**Authentication:** ❌ Not required

**Request:**
```json
{
  "enabled": true
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Vacation mode enabled",
  "vacation_mode": true
}
```

**Notes:**
- When vacation mode is enabled, all scheduling and automation is paused
- Devices remain in their current state until vacation mode is disabled
- Setting persists to `config.yaml` and survives restarts
- Use this when away from home to prevent unnecessary heating

---

### GET /api/solar_times

Get sunrise and sunset times for today with timezone.

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/solar_times
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "date": "2025-11-23",
  "timezone": "America/New_York",
  "sunrise": "06:47:23",
  "sunset": "16:32:15"
}
```

**Notes:**
- Times are calculated based on location configured in `config.yaml`
- Used for solar offset schedules (e.g., "turn on 60 minutes before sunset")
- Times are in 24-hour format (HH:MM:SS)

---

## Mobile Control Endpoints (Protected)

These endpoints require PIN authentication via session cookie. See [Authentication](#authentication) section for details.

### GET /api/mat/status

Get mat status for all groups including state, mode, temperature, and manual override info.

**Authentication:** ✅ **Required** (PIN session)

**Request:**
```bash
curl http://localhost:4328/api/mat/status \
  -H "Cookie: session=<session_cookie>"
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "groups": {
    "heated_mats": {
      "state": "on",
      "mode": "manual",
      "temperature_f": 28.5,
      "manual_override": {
        "active": true,
        "expires_at": "2025-11-23T18:30:00",
        "set_by": "mobile_control"
      },
      "last_state_change": "2025-11-23T15:30:00"
    }
  },
  "timestamp": "2025-11-23T15:30:45.123456"
}
```

**Response (401 Unauthorized):**
```json
{
  "success": false,
  "error": "Authentication required",
  "redirect": "/control/login"
}
```

**Fields:**
- `state`: Current state (`"on"` or `"off"`)
- `mode`: Operating mode (`"auto"`, `"manual"`, or `"schedule"`)
- `temperature_f`: Current temperature in Fahrenheit (if available)
- `manual_override`: Override information if active
  - `active`: Boolean indicating if manual override is active
  - `expires_at`: ISO timestamp when override expires
  - `set_by`: Source of override (e.g., `"mobile_control"`)
- `last_state_change`: ISO timestamp of last state change

---

### POST /api/mat/control

Control a group (on/off) with optional timeout. Sets manual override.

**Authentication:** ✅ **Required** (PIN session)

**Request:**
```json
{
  "group": "heated_mats",
  "action": "on",
  "timeout_hours": 3
}
```

**Parameters:**
- `group` (required): Name of the device group to control
- `action` (required): `"on"` or `"off"`
- `timeout_hours` (optional): Duration in hours for manual override (default: 3)

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Group 'heated_mats' turned on. Manual override set for 3 hours.",
  "expires_at": "2025-11-23T18:30:00"
}
```

**Response (401 Unauthorized):**
```json
{
  "success": false,
  "error": "Authentication required",
  "redirect": "/control/login"
}
```

**Notes:**
- Sets a time-limited manual override that prevents scheduler from changing device state
- Default timeout is 3 hours if not specified
- Override automatically expires after timeout
- Use `/api/mat/reset-auto` to clear override and return to automatic control
- Scheduler resumes normal operation after override expires

---

### POST /api/mat/reset-auto

Clear manual override and reapply schedule logic.

**Authentication:** ✅ **Required** (PIN session)

**Request:**
```json
{
  "group": "heated_mats"
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Manual override cleared for 'heated_mats'. Scheduler will resume automatic control."
}
```

**Response (401 Unauthorized):**
```json
{
  "success": false,
  "error": "Authentication required",
  "redirect": "/control/login"
}
```

**Notes:**
- Clears any active manual override
- Scheduler immediately reapplies schedule and weather logic
- Device state may change immediately based on current schedule
- Use this to return to automatic control before override expires

---

## Notification Endpoints

### GET /api/notifications/status

Get notification provider health status (email, webhook).

**Authentication:** ❌ Not required

**Request:**
```bash
curl http://localhost:4328/api/notifications/status
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "providers": {
    "email": {
      "name": "email",
      "enabled": true,
      "health": "healthy",
      "last_check": "2025-11-23T15:00:00.123456",
      "last_success": "2025-11-23T14:30:00.123456",
      "last_error": null,
      "consecutive_failures": 0
    },
    "webhook": {
      "name": "webhook",
      "enabled": true,
      "health": "degraded",
      "last_check": "2025-11-23T15:00:00.123456",
      "last_success": "2025-11-23T12:00:00.123456",
      "last_error": "Connection timeout",
      "consecutive_failures": 2
    }
  }
}
```

**Health Status Values:**
- `healthy`: Provider is working normally
- `degraded`: Provider has experienced recent failures but may still work
- `failed`: Provider has failed consistently
- `unknown`: Provider health is unknown (not yet tested)

---

### POST /api/notifications/test

Queue a test notification (non-blocking, returns 202 Accepted).

**Authentication:** ❌ Not required

**Request:**
```json
{
  "subject": "Custom Test Subject",
  "body": "Custom test message body"
}
```

**Parameters (optional):**
- `subject`: Custom subject line (default: "HeatTrax Test Notification")
- `body`: Custom message body (default: "This is a test notification from HeatTrax Scheduler.")

**Response (202 Accepted):**
```json
{
  "status": "queued",
  "message": "Test notification queued for processing"
}
```

**Response (500 Error):**
```json
{
  "status": "error",
  "error": "Failed to queue test notification",
  "details": "NotificationManager not initialized"
}
```

**Notes:**
- Test notification is queued and processed asynchronously by the NotificationManager
- Endpoint returns immediately with 202 Accepted
- Check `/api/notifications/status` to verify notification was sent successfully
- Useful for testing email and webhook configurations

---

## UI/Page Routes

### GET /

Serve the main desktop UI page (index.html).

**Authentication:** ❌ Not required

**Description:**
- Serves the desktop dashboard interface
- Displays system status, device health, and configuration editor
- Accessible to all users (no authentication required)

---

### GET /ui

Alternative route to the main desktop UI.

**Authentication:** ❌ Not required

**Description:**
- Same as `/`, serves the desktop dashboard
- Provided for URL consistency

---

### GET /control/login

Mobile control login page.

**Authentication:** ❌ Not required

**Description:**
- Displays PIN entry form for mobile control authentication
- Redirects to `/control` after successful login

---

### GET /control

Mobile control dashboard (requires PIN authentication).

**Authentication:** ✅ **Required** (PIN session)

**Description:**
- Mobile-friendly control interface
- Provides access to mat control endpoints
- Requires PIN authentication via `/api/auth/login`
- Redirects to `/control/login` if not authenticated

---

### GET /web/<path:filename>

Serve static web files (JavaScript, CSS, images).

**Authentication:** ❌ Not required

**Description:**
- Serves static assets for the web UI
- Includes JavaScript, CSS, images, and other static files
- Cached for performance

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 202 | Accepted - Request accepted for processing (async) |
| 400 | Bad Request - Invalid request parameters or validation error |
| 401 | Unauthorized - Authentication required |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error - Server error occurred |

---

## Rate Limiting

Currently, there is no rate limiting implemented. Future versions may include rate limiting for security.

---

## CORS

Cross-Origin Resource Sharing (CORS) is not currently configured. The API is intended to be accessed from the same origin as the web UI.

---

## Best Practices

1. **Use health endpoints** (`/api/health`, `/api/ping`) for monitoring and liveness checks
2. **Check notification status** before sending important notifications
3. **Download config before upload** to create a backup
4. **Use vacation mode** when away to pause automation
5. **Set manual override timeout** to prevent devices from running indefinitely
6. **Validate configuration** before applying changes
7. **Monitor device status** regularly to detect issues early
8. **Use solar times** for location-based scheduling
9. **Clear manual overrides** when returning to automatic control
10. **Bind to localhost** (`127.0.0.1`) for maximum security

---

## See Also

- [Web UI Guide](WEB_UI_GUIDE.md) - Complete guide to using the web interface
- [Scheduling Guide](../SCHEDULING.md) - Detailed scheduling documentation
- [Setup Guide](SETUP.md) - Initial setup and configuration
- [README](../README.md) - Project overview and quick start

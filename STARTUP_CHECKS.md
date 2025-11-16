# Startup Diagnostic Checks

The HeatTrax Scheduler includes comprehensive startup diagnostic checks to help debug deployment issues, especially in containerized environments like Docker and Portainer.

## Overview

When the application starts, it runs a series of pre-flight checks **before** loading configuration or setting up logging. This ensures maximum diagnostic value for troubleshooting deployment issues and crash loops.

## Checks Performed

The startup checks are clearly separated in the logs with a `==== STARTUP SANITY CHECKS ====` banner and include:

### 1. Python Version Check
Logs the Python interpreter version and executable path:
```
✓ Python version: 3.12.3
  Full version: 3.12.3 (main, Aug 14 2025, 17:47:21) [GCC 13.3.0]
  Executable: /usr/bin/python3
```

### 2. Package Version Check
Verifies all packages from `requirements.txt` are installed and logs their versions:
```
✓ Requirements file found: requirements.txt

Installed package versions:
  ✓ python-kasa: 0.10.2 (required: python-kasa>=0.7.0)
  ✓ PyYAML: 6.0.1 (required: PyYAML>=6.0.1)
  ✓ aiohttp: 3.13.2 (required: aiohttp>=3.9.0)

✓ All required packages are installed
```

If packages are missing, warnings are logged but startup continues:
```
  ✗ python-kasa: NOT INSTALLED (required: python-kasa>=0.7.0)
  
✗ WARNING: Some required packages are missing!
```

### 3. Working Directory Check
Logs the current working directory and lists key files present:
```
✓ Current working directory: /app
  Directory contains 15 items
  Key files present: config.yaml, main.py, requirements.txt, ...
```

### 4. Directory Access Check
Verifies read/write access to important directories (`logs`, `state`):
```
Directory access checks:
  ✓ /app/logs: readable, writable
  ✓ /app/state: readable, writable
✓ All directories are accessible
```

If directories don't exist, they are automatically created:
```
  ⚠ /app/logs: Does not exist, will attempt to create...
    ✓ Successfully created /app/logs
```

### 5. Configuration File Check
Checks for `config.yaml` presence and validates YAML parsing:
```
Configuration file check:
  ✓ Config file found: config.yaml
  ✓ Config file parsed successfully
  Configuration sections: location, devices, thresholds, morning_mode, safety, scheduler, logging
  ✓ All required sections present in config file
```

If the config file is missing (common in Docker deployments using environment variables):
```
Configuration file check:
  ⚠ Config file not found: config.yaml
    This is acceptable if using environment variables for configuration
    Will attempt to load config from environment variables...
```

### 6. Environment Variables Dump
Logs all environment variables, with automatic redaction of sensitive values:
```
Environment variables:

  HEATTRAX Configuration Variables (13):
    HEATTRAX_LATITUDE=40.7128
    HEATTRAX_TAPO_PASSWORD=***REDACTED***
    HEATTRAX_TAPO_USERNAME=user@example.com
    ...

  Other environment variables: 160
  Important system variables:
    HOME=/app
    PATH=/usr/local/sbin:/usr/local/bin:...
    PWD=/app
```

Sensitive patterns that trigger redaction (case-insensitive):
- `password`
- `secret`
- `token`
- `key`
- `credential`

### 7. Device Connectivity Check (Optional)
If device IP addresses are configured, the system can attempt socket connections to validate connectivity (implementation detail varies).

### 8. Outbound IP Check (Optional)
Attempts to determine the container's outbound IP address:
```
Outbound IP address check:
  ✓ Outbound IP (DNS query): 172.17.0.2
```

## Exit Behavior

The startup checks distinguish between critical and non-critical failures:

### Critical Failures (Exit with error)
- Python version check fails
- Cannot read working directory
- Config file is invalid YAML (if present)

### Non-Critical Warnings (Continue startup)
- Some packages are missing
- Directories don't exist (but can be created)
- Config file is missing (will use environment variables)
- Device connectivity test fails
- Cannot determine outbound IP

After all checks complete, a summary is shown:
```
============================================================

✓ All critical startup checks passed!
  (Some warnings may be present, but are non-critical)
```

Or if critical failures occurred:
```
✗ CRITICAL FAILURES DETECTED - Startup checks failed!
  Please review the errors above before proceeding.
```

## Docker/Container Usage

In Docker deployments, the startup checks are particularly valuable for debugging:

1. **Immediate visibility**: Checks run before logging is configured, so output appears in `docker logs` immediately
2. **Environment validation**: Verifies all configuration is present via environment variables
3. **Network diagnostics**: Tests connectivity to the Tapo device
4. **Permission issues**: Detects volume mount or permission problems early

Example Docker run with full diagnostics:
```bash
docker run -d \
  -e HEATTRAX_LATITUDE=40.7128 \
  -e HEATTRAX_LONGITUDE=-74.0060 \
  -e HEATTRAX_TAPO_USERNAME=user@example.com \
  -e HEATTRAX_TAPO_PASSWORD=secret \
  -e HEATTRAX_THRESHOLD_TEMP_F=34 \
  -e HEATTRAX_LEAD_TIME_MINUTES=60 \
  -e HEATTRAX_TRAILING_TIME_MINUTES=60 \
  -e HEATTRAX_CHECK_INTERVAL_MINUTES=10 \
  -e HEATTRAX_FORECAST_HOURS=12 \
  -e HEATTRAX_MAX_RUNTIME_HOURS=6 \
  -e HEATTRAX_COOLDOWN_MINUTES=30 \
  -v /path/to/logs:/app/logs \
  -v /path/to/state:/app/state \
  heattrax-scheduler
```

Then check the startup diagnostics:
```bash
docker logs <container-id> | head -100
```

## Testing Startup Checks

The startup checks can be tested independently:

```bash
# Test with defaults
python3 startup_checks.py

# Test with specific config and device IP
python3 -c "from startup_checks import run_startup_checks; run_startup_checks(config_path='config.yaml', device_ip='192.168.1.100')"
```

## Implementation Details

The startup checks are implemented in `startup_checks.py` and integrated into `main.py` at the very beginning of the `main()` function, before:
- Signal handlers are set up
- Configuration is loaded
- Logging is initialized

This ensures maximum diagnostic value for debugging deployment issues.

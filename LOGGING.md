# Logging and Troubleshooting Guide

This guide explains the comprehensive logging system and how to use it for troubleshooting.

## Logging Levels

The application uses Python's standard logging levels:

- **DEBUG**: Detailed information for diagnosing problems (parameter values, API requests, state changes)
- **INFO**: Confirmation that things are working as expected (decisions, actions taken)
- **WARNING**: Indication that something unexpected happened, but the application continues
- **ERROR**: A serious problem occurred, functionality may be impaired

## Configuration

Set the logging level in `config.yaml`:

```yaml
logging:
  level: "DEBUG"  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
  max_file_size_mb: 10
  backup_count: 5
```

### Recommended Settings

**For Normal Operation:**
```yaml
logging:
  level: "INFO"  # Shows decisions and actions
```

**For Troubleshooting:**
```yaml
logging:
  level: "DEBUG"  # Shows all details including API calls and validations
```

**For Production (Minimal Logs):**
```yaml
logging:
  level: "WARNING"  # Only shows warnings and errors
```

## What Gets Logged

### Configuration Loading (DEBUG Level)

```
INFO - Loading configuration from: config.yaml
DEBUG - Checking if configuration file exists: config.yaml
DEBUG - Reading configuration file: config.yaml
INFO - Successfully parsed configuration with 7 top-level sections
DEBUG - Configuration sections: ['location', 'device', 'thresholds', ...]
INFO - Validating configuration...
DEBUG - Location validated: lat=40.7128, lon=-74.006
DEBUG - Device validated: IP=192.168.1.100, Username=your_email
DEBUG - Threshold temperature_f=34.0
INFO - Configuration validation completed successfully
```

### Weather API Calls (DEBUG Level)

```
INFO - Requesting weather forecast for 12 hours ahead
DEBUG - API request URL: https://api.open-meteo.com/v1/forecast
DEBUG - API request parameters: {'latitude': 40.7128, ...}
DEBUG - Opening HTTP session to https://api.open-meteo.com/v1/forecast
DEBUG - Received HTTP response with status: 200
INFO - Successfully retrieved weather data from API
DEBUG - Response data keys: dict_keys(['latitude', 'longitude', 'hourly', ...])
```

### Precipitation Checking (INFO Level)

```
INFO - Checking precipitation forecast: hours_ahead=12, temp_threshold=34°F
DEBUG - Received 24 hourly forecast entries
DEBUG - Checking forecast from 2025-11-15 18:00:00 to 2025-11-16 06:00:00
DEBUG - Forecast at 2025-11-15 20:00:00: temp=32.5°F, precip=0.0mm
DEBUG - Forecast at 2025-11-15 21:00:00: temp=31.8°F, precip=0.2mm
INFO - PRECIPITATION DETECTED: Expected at 2025-11-15 21:00:00: 0.2mm, temp: 31.8°F
```

### Device Control (INFO Level)

```
INFO - Request to turn ON device at 192.168.1.100
DEBUG - Checking current state of device at 192.168.1.100
DEBUG - Updating device state from 192.168.1.100
INFO - Device at 192.168.1.100 is currently: OFF
INFO - Turning ON device at 192.168.1.100
INFO - Successfully turned ON device at 192.168.1.100
```

### Scheduler Cycle (INFO Level)

```
============================================================
Starting scheduler cycle
============================================================
INFO - Checking current device state...
INFO - Current device state: OFF
INFO - Device is OFF - evaluating if it should turn ON
INFO - Checking precipitation forecast: hours_ahead=12, temp_threshold=34°F
INFO - PRECIPITATION DETECTED: Expected at 2025-11-15 21:00:00
INFO - DECISION: Device should turn ON
INFO - Request to turn ON device at 192.168.1.100
INFO - Successfully turned ON device at 192.168.1.100
INFO - Device turned ON and state recorded
INFO - Scheduler cycle completed successfully
```

## Error Messages

### Configuration Errors

**Missing Configuration File:**
```
ERROR - Configuration file not found: config.yaml
ERROR - Current working directory: /app
```

**Invalid Coordinates:**
```
ERROR - Invalid latitude value: 95.0 (must be between -90 and 90)
```

**Empty Required Fields:**
```
ERROR - Device field 'password' is empty
```

### Weather API Errors

**Connection Failed:**
```
ERROR - HTTP client error while fetching weather data: ClientConnectorError
ERROR - Failed to fetch weather data: Cannot connect to host api.open-meteo.com
```

**Invalid Response:**
```
ERROR - Received empty response from weather API
```

**Timeout:**
```
ERROR - Timeout while connecting to weather API: Weather API request timed out after 30 seconds
```

### Device Connection Errors

**Connection Failed:**
```
ERROR - Connection error while initializing device at 192.168.1.100
ERROR - Possible causes: Device is offline, IP address is wrong, network issue
```

**Invalid Credentials:**
```
ERROR - Failed to initialize device: Authentication failed
ERROR - Possible causes: Invalid credentials, device not compatible, network issue
```

**Timeout:**
```
ERROR - Timeout while connecting to device at 192.168.1.100
ERROR - Device may be unreachable or not responding
```

## Viewing Logs

### Docker Deployment

```bash
# View live logs
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100

# View logs for last hour
docker-compose logs --since=1h
```

### Direct Python

```bash
# View live logs
tail -f logs/heattrax_scheduler.log

# View last 100 lines
tail -n 100 logs/heattrax_scheduler.log

# Search for errors
grep ERROR logs/heattrax_scheduler.log

# Search for a specific time
grep "2025-11-15 18:" logs/heattrax_scheduler.log
```

### Analyzing Logs

```bash
# Count error occurrences
grep -c ERROR logs/heattrax_scheduler.log

# Find when device was turned on
grep "turned ON" logs/heattrax_scheduler.log

# Find weather API calls
grep "weather forecast" logs/heattrax_scheduler.log

# Show only decision points
grep "DECISION:" logs/heattrax_scheduler.log
```

## Common Troubleshooting Scenarios

### Device Not Turning On

1. **Check logs for precipitation detection:**
   ```bash
   grep "PRECIPITATION DETECTED" logs/heattrax_scheduler.log
   ```

2. **Check if in cooldown:**
   ```bash
   grep "cooldown" logs/heattrax_scheduler.log
   ```

3. **Check device connection:**
   ```bash
   grep "device at 192.168.1.100" logs/heattrax_scheduler.log
   ```

### Weather Data Not Loading

1. **Check API connection:**
   ```bash
   grep "api.open-meteo.com" logs/heattrax_scheduler.log
   ```

2. **Look for network errors:**
   ```bash
   grep -A 5 "weather service error" logs/heattrax_scheduler.log
   ```

### Configuration Issues

1. **Check configuration validation:**
   ```bash
   grep "Validating configuration" logs/heattrax_scheduler.log
   ```

2. **Look for validation errors:**
   ```bash
   grep "configuration" logs/heattrax_scheduler.log | grep ERROR
   ```

## Log Rotation

Logs are automatically rotated when they reach 10MB (configurable):

```
logs/
├── heattrax_scheduler.log       # Current log
├── heattrax_scheduler.log.1     # Previous log
├── heattrax_scheduler.log.2
├── heattrax_scheduler.log.3
├── heattrax_scheduler.log.4
└── heattrax_scheduler.log.5     # Oldest log
```

Old logs are compressed and retained for historical analysis.

## Debugging Tips

### Enable Maximum Verbosity

Set `DEBUG` level and check all details:

```yaml
logging:
  level: "DEBUG"
```

### Focus on Specific Components

Use grep to filter:

```bash
# Only weather service logs
grep "weather_service" logs/heattrax_scheduler.log

# Only device controller logs
grep "device_controller" logs/heattrax_scheduler.log

# Only main scheduler logs
grep "__main__" logs/heattrax_scheduler.log
```

### Track a Single Cycle

Follow one complete scheduler cycle:

```bash
# Find cycle start
grep -n "Starting scheduler cycle" logs/heattrax_scheduler.log | tail -1

# Then view from that line number
tail -n +LINE_NUMBER logs/heattrax_scheduler.log | head -50
```

### Export Logs for Support

```bash
# Create a support bundle
tar -czf support-logs-$(date +%Y%m%d-%H%M).tar.gz logs/
```

## Best Practices

1. **Start with INFO level** for normal operation
2. **Switch to DEBUG** only when troubleshooting
3. **Monitor logs regularly** for unexpected behavior
4. **Keep at least 5 backup logs** for historical analysis
5. **Search for ERROR and WARNING** messages regularly
6. **Check logs after configuration changes**
7. **Review logs after weather events** to verify behavior

## Getting Help

When reporting issues, include:

1. **Configuration** (with sensitive data removed)
2. **Relevant log excerpts** showing the error
3. **System information** (Docker version, Python version, etc.)
4. **Steps to reproduce** the issue

Example:

```bash
# Collect diagnostic information
echo "=== Configuration ===" > diagnostics.txt
cat config.yaml | grep -v password >> diagnostics.txt
echo "" >> diagnostics.txt
echo "=== Recent Errors ===" >> diagnostics.txt
grep ERROR logs/heattrax_scheduler.log | tail -20 >> diagnostics.txt
echo "" >> diagnostics.txt
echo "=== Last Cycle ===" >> diagnostics.txt
grep "Starting scheduler cycle" logs/heattrax_scheduler.log | tail -1 >> diagnostics.txt
```

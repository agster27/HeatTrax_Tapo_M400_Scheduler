# Weather Resilience Implementation

This document provides detailed information about the weather resilience and caching features added to HeatTrax Tapo M400 Scheduler.

## Overview

The weather resilience layer ensures reliable operation during temporary internet or weather API outages by caching forecast data and implementing intelligent fallback behavior.

## Key Features

### 1. Automatic Caching
- **Persistent Storage**: Stores the last successful forecast to disk (`state/weather_cache.json` by default)
- **Configurable Horizon**: Stores forecast data for up to 12 hours (configurable)
- **Location Validation**: Ensures cached data matches your configured location
- **Age Tracking**: Tracks when forecast was fetched to determine validity

### 2. State Machine

The weather service operates in three states:

#### ONLINE (Normal Operation)
- Fresh weather data from API
- Fetches forecast every 10 minutes (default)
- All weather features fully functional
- Cache updated on each successful fetch

#### DEGRADED_OFFLINE_USING_CACHE
- API temporarily unavailable
- Using cached forecast data (< 6 hours old by default)
- **All weather features continue working normally**
- Retries API with exponential backoff
- Seamless operation - no user-visible impact

#### OFFLINE_NO_WEATHER_DATA (Fail-Safe Mode)
- API unavailable AND cache expired (> 6 hours old)
- Weather methods return `None`
- Scheduler **automatically reverts to static schedule**
- Weather-based features temporarily disabled
- Continues retrying with maximum backoff (60 min)
- Alert sent after threshold (30 min default)

### 3. Adaptive Retry Logic

When API becomes unavailable:
1. Initial retry after 5 minutes
2. Exponential backoff: 5 → 10 → 20 → 40 → 60 minutes
3. Maximum interval capped at 60 minutes (configurable)
4. On success: resets to normal 10-minute interval
5. On failure: increases backoff (up to max)

### 4. Notifications & Alerts

The resilience layer integrates with the existing notification system to send alerts for:

- **Service Degraded**: When transitioning from ONLINE to DEGRADED (using cache)
- **Service Offline**: When transitioning to OFFLINE (fail-safe mode)
- **Outage Alert**: When offline longer than threshold (30 min default)
- **Service Recovered**: When API becomes available after being offline

## Configuration

### YAML Configuration

Add to your `config.yaml`:

```yaml
weather_api:
  provider: "open-meteo"  # or "openweathermap"
  
  # Weather Resilience & Caching
  resilience:
    # Path to weather cache file
    cache_file: "state/weather_cache.json"
    
    # How long cached data is trusted (in hours)
    # System uses cached data if it's fresher than this
    cache_valid_hours: 6.0
    
    # How many hours of forecast to store
    # Should be >= cache_valid_hours
    forecast_horizon_hours: 12
    
    # Normal polling interval when online (in minutes)
    refresh_interval_minutes: 10
    
    # Initial retry delay after failure (in minutes)
    retry_interval_minutes: 5
    
    # Maximum backoff interval (in minutes)
    # Uses exponential backoff up to this max
    max_retry_interval_minutes: 60
    
    # Alert if offline longer than this (in minutes)
    outage_alert_after_minutes: 30
```

### Environment Variables

Override any setting via environment variables:

```bash
# Cache configuration
HEATTRAX_WEATHER_CACHE_FILE="state/weather_cache.json"
HEATTRAX_WEATHER_CACHE_VALID_HOURS="6.0"
HEATTRAX_WEATHER_FORECAST_HORIZON_HOURS="12"

# Retry configuration
HEATTRAX_WEATHER_REFRESH_INTERVAL_MINUTES="10"
HEATTRAX_WEATHER_RETRY_INTERVAL_MINUTES="5"
HEATTRAX_WEATHER_MAX_RETRY_INTERVAL_MINUTES="60"

# Alert configuration
HEATTRAX_WEATHER_OUTAGE_ALERT_AFTER_MINUTES="30"
```

## Behavior Scenarios

### Scenario 1: Brief Internet Outage (< 6 hours)

**What Happens:**
1. API fetch fails at 10:00 AM
2. System transitions to DEGRADED state
3. Uses cached forecast from 9:50 AM
4. **Devices continue operating normally**
5. Retries API at 10:05, 10:15, 10:35, 11:15
6. API recovers at 11:15 AM
7. System transitions back to ONLINE
8. Resumes normal operation

**User Impact:** None - transparent operation

**Logs:**
```
10:00 - ERROR: Weather service error: Network unreachable
10:00 - WARNING: Weather service state changed: online -> degraded_offline_using_cache
11:15 - INFO: Successfully fetched and cached weather forecast
11:15 - WARNING: Weather service state changed: degraded_offline_using_cache -> online
```

### Scenario 2: Extended Outage (> 6 hours)

**What Happens:**
1. API fails at 10:00 AM, transitions to DEGRADED
2. Uses cache for 6 hours
3. At 4:00 PM, cache expires (> 6 hours old)
4. System transitions to OFFLINE state
5. Weather methods return `None`
6. **Scheduler automatically uses static schedule**
7. Weather-based features temporarily disabled
8. Continues retrying every 60 minutes
9. At 4:30 PM, sends outage alert (30 min threshold)
10. API recovers at 8:00 PM
11. System transitions back to ONLINE
12. Sends recovery notification
13. Resumes weather-based operation

**User Impact:** Devices operate on static schedule during extended outage (6+ hours)

**Logs:**
```
10:00 - WARNING: Weather service state changed: online -> degraded_offline_using_cache
16:00 - WARNING: Weather service state changed: degraded_offline_using_cache -> offline_no_weather_data
16:30 - CRITICAL: WEATHER SERVICE OUTAGE ALERT: Service has been offline for 30.0 minutes
20:00 - INFO: Successfully fetched and cached weather forecast
20:00 - WARNING: Weather service state changed: offline_no_weather_data -> online
```

### Scenario 3: Startup with Valid Cache

**What Happens:**
1. Container restarts
2. Loads cache file
3. Cache is 2 hours old (< 6 hours)
4. Starts in DEGRADED state
5. First API call succeeds
6. Transitions to ONLINE
7. Normal operation resumes

**User Impact:** None - seamless startup

## Fail-Safe Behavior

When weather data becomes unavailable (OFFLINE state), the scheduler behavior changes:

### Weather-Based Groups (Heated Mats)

**Normal (ONLINE/DEGRADED):**
- Uses weather forecasts to determine when to activate
- Turns on before precipitation
- Morning mode activates based on temperature

**Fail-Safe (OFFLINE):**
- Weather checks return `None`
- Precipitation control: **disabled** (no forecast available)
- Morning mode: **disabled** (no current temperature)
- Effectively operates like `HEATTRAX_WEATHER_ENABLED=false`
- Static schedule behavior (if configured) still works

### Schedule-Based Groups (Christmas Lights)

**No Change:**
- Schedule-based groups are not affected by weather outages
- Continue operating on configured on/off times
- Independent of weather service state

## Monitoring

### Log Messages

Monitor weather service state via logs:

```bash
# Docker
docker-compose logs -f | grep "Weather service state"

# Manual
tail -f logs/heattrax_scheduler.log | grep "Weather service"
```

### Health Check Endpoints

If health check server is enabled:

```bash
# Check overall health
curl http://localhost:8080/health

# Check weather-specific health
curl http://localhost:8080/health/weather
```

Weather health response includes:
- Current state (online/degraded/offline)
- Cache age in hours
- Last successful fetch timestamp
- Next fetch interval

### Cache File

Inspect the cache manually:

```bash
cat state/weather_cache.json
```

Cache structure:
```json
{
  "fetched_at": "2025-11-16T20:00:00",
  "location": {
    "latitude": 40.7128,
    "longitude": -74.006
  },
  "forecast": [
    {
      "timestamp": "2025-11-16T21:00:00",
      "temperature_f": 32.0,
      "precipitation_mm": 0.0
    },
    ...
  ]
}
```

## Tuning Recommendations

### For Stable Internet Connection
If you have reliable internet:
```yaml
resilience:
  cache_valid_hours: 3.0  # Shorter cache validity
  retry_interval_minutes: 10  # Slower initial retry
  outage_alert_after_minutes: 60  # Alert after 1 hour
```

### For Unreliable Internet Connection
If you experience frequent outages:
```yaml
resilience:
  cache_valid_hours: 12.0  # Longer cache validity
  forecast_horizon_hours: 24  # Store more forecast data
  retry_interval_minutes: 2  # Faster initial retry
  max_retry_interval_minutes: 30  # Lower max backoff
  outage_alert_after_minutes: 120  # Alert after 2 hours
```

### For Critical Applications
If weather-based control is critical:
```yaml
resilience:
  cache_valid_hours: 24.0  # Very long cache validity
  forecast_horizon_hours: 48  # Store 2 days of forecast
  retry_interval_minutes: 1  # Very fast retry
  max_retry_interval_minutes: 15  # Frequent retries
  outage_alert_after_minutes: 15  # Early alert
```

## Troubleshooting

### Cache Not Being Used

**Symptoms:**
- Transitions directly to OFFLINE without DEGRADED state
- Cache file exists but not loaded

**Solutions:**
1. Check cache file permissions: `ls -la state/weather_cache.json`
2. Check cache age: Look for "Cache age:" in logs
3. Verify cache location matches config
4. Check cache structure is valid JSON

### Frequent State Changes

**Symptoms:**
- Constant ONLINE → DEGRADED → ONLINE transitions
- Many retry attempts in logs

**Solutions:**
1. Check internet connectivity
2. Verify weather API credentials (OpenWeatherMap)
3. Check firewall/proxy settings
4. Increase `retry_interval_minutes` to reduce log noise

### Outage Alerts Too Frequent

**Symptoms:**
- Alert notifications every few minutes
- False positive outage alerts

**Solutions:**
1. Increase `outage_alert_after_minutes` threshold
2. Check for intermittent connectivity issues
3. Review API rate limits (OpenWeatherMap)

### Weather Features Not Working After Outage

**Symptoms:**
- System stays in OFFLINE mode after API recovers
- No weather-based activation

**Solutions:**
1. Check logs for successful fetch messages
2. Verify API credentials are correct
3. Restart scheduler: `docker-compose restart`
4. Check cache file is being updated

## Testing

The implementation includes comprehensive tests:

```bash
# Unit tests (6 tests)
python test_weather_resilience.py

# Integration tests (3 tests)
python test_weather_integration.py

# All tests
python test_scheduler.py && \
python test_weather_resilience.py && \
python test_weather_integration.py
```

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────┐
│         EnhancedScheduler                    │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  _weather_fetch_loop()                 │ │
│  │  - Background task                     │ │
│  │  - Adaptive fetch intervals            │ │
│  │  - Exponential backoff on failure      │ │
│  └────────────────────────────────────────┘ │
│                    ↓                         │
└────────────────────┼──────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│     ResilientWeatherService                  │
│                                              │
│  State: ONLINE/DEGRADED/OFFLINE              │
│  - fetch_and_cache_forecast()                │
│  - get_current_conditions()                  │
│  - check_precipitation_forecast()            │
│  - Notification hooks                        │
│                                              │
│  ┌────────────────┐  ┌──────────────────┐  │
│  │ WeatherCache   │  │ Base Weather Svc │  │
│  │ - Save/Load    │  │ - Open-Meteo     │  │
│  │ - Validate     │  │ - OpenWeatherMap │  │
│  │ - Age Check    │  └──────────────────┘  │
│  └────────────────┘                         │
└─────────────────────────────────────────────┘
                     ↓
           ┌─────────────────────┐
           │  Weather API        │
           │  - Open-Meteo       │
           │  - OpenWeatherMap   │
           └─────────────────────┘
```

### State Machine

```
     [START]
        ↓
        ↓ (load cache)
        ↓
        ↓──── cache valid? ────→ DEGRADED_OFFLINE_USING_CACHE
        ↓           ↓                       ↓
        ↓           ↓ no                    ↓ fetch success
        ↓           ↓                       ↓
  OFFLINE_NO_WEATHER_DATA ←────────────→ ONLINE
        ↑           ↓                       ↓
        ↑           ↓ fetch success         ↓ fetch fail
        ↑           ↓                       ↓
        ↑           └──→ ONLINE ←──────────┘
        ↑                    ↓
        ↑                    ↓ fetch fail
        ↑                    ↓
        ↑                    ↓─→ DEGRADED (if cache valid)
        ↑                    ↓
        ↑                    ↓─→ OFFLINE (if cache expired)
        ↑                         ↓
        └─────────────────────────┘
```

## Implementation Details

### Files Modified

- `weather_cache.py` - Cache storage and retrieval
- `resilient_weather_service.py` - Main resilience wrapper
- `weather_factory.py` - Factory integration
- `scheduler_enhanced.py` - Background fetch task
- `config_loader.py` - Environment variable support

### Dependencies

No new dependencies added - uses existing:
- `aiohttp` - Async HTTP (already present)
- `asyncio` - Async operations (built-in)
- `json` - Cache serialization (built-in)
- `pathlib` - File handling (built-in)

## Performance Impact

- **CPU**: Minimal - background fetch task sleeps between polls
- **Memory**: ~50KB per cached forecast (12 hours of hourly data)
- **Disk**: Cache file typically < 10KB
- **Network**: No change - same API calls, just with caching

## Security Considerations

- Cache file contains only public forecast data (no credentials)
- No sensitive data stored
- File permissions inherit from system defaults
- CodeQL analysis: 0 security alerts

## Future Enhancements

Potential future improvements:

1. **Multiple Cache Locations**: Support backup cache locations
2. **Cache Compression**: Compress cache file to save disk space
3. **Predictive Prefetch**: Fetch forecast before current cache expires
4. **Cache Sharing**: Share cache between multiple instances
5. **Historical Data**: Maintain historical accuracy metrics
6. **Smart Recovery**: Prioritize recovery based on usage patterns

## Support

For issues or questions:

1. Check logs for error messages
2. Review this document
3. Check GitHub issues
4. Create new issue with logs attached

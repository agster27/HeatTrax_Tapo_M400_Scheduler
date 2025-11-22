# Manual QA Checklist for Shared Event Loop Changes

This document outlines the manual QA steps for verifying the shared event loop implementation.

## Prerequisites
- HeatTrax Scheduler running with at least one configured device
- Access to the Web UI (default: http://localhost:4328)
- At least one Tapo/Kasa device configured in your device groups

## Test 1: Application Startup
**Goal:** Verify the application starts without errors after the loop sharing changes.

### Steps:
1. Start the application (Docker or direct Python execution)
2. Check the logs for the scheduler initialization
3. Look for the message: `Scheduler event loop initialized: <loop>`

### Expected Result:
- ✅ Application starts successfully
- ✅ Log message confirms event loop initialization
- ✅ No errors related to asyncio or event loops

### Log Example:
```
INFO - Scheduler event loop initialized: <_UnixSelectorEventLoop running=True ...>
INFO - Starting scheduler with 600s check interval
```

## Test 2: Weather State JSON Serialization
**Goal:** Verify `/api/status` endpoint returns valid JSON with weather_state properly serialized.

### Steps:
1. Open your browser to: `http://localhost:4328/api/status`
2. Or use curl: `curl http://localhost:4328/api/status | jq .`
3. Check for the `weather_state` field in the response
4. Verify it's a string value (not an object)

### Expected Result:
- ✅ Endpoint returns valid JSON (no TypeError about WeatherServiceState)
- ✅ `weather_state` field present with string value like "online", "degraded_offline_using_cache", or "offline_no_weather_data"
- ✅ No error logs about "Object of type WeatherServiceState is not JSON serializable"

### Response Example:
```json
{
  "config_path": "/app/config.yaml",
  "weather_enabled": true,
  "weather_state": "online",
  "last_weather_fetch": "2024-01-15T10:30:00",
  "device_groups": {
    "heattrax": {
      "enabled": true,
      "device_count": 2
    }
  },
  "timestamp": "2024-01-15T10:35:00"
}
```

## Test 3: Device Status API without Timeout Errors
**Goal:** Verify `/api/devices/status` endpoint works without python-kasa timeout errors.

### Steps:
1. Navigate to the Health tab in the Web UI
2. Click the "Refresh" button in the Device Control section
3. Or access directly: `http://localhost:4328/api/devices/status`
4. Check the application logs for any errors

### Expected Result:
- ✅ API returns device status successfully
- ✅ Devices show as "Online" or "Offline" with correct outlet states
- ✅ **No errors** in logs like:
  - `Timeout context manager should be used inside a task`
  - `SmartErrorCode.INTERNAL_QUERY_ERROR: -100001`
  - `Error querying ... for modules`
- ✅ Response includes all configured devices with outlet information

### Response Example:
```json
{
  "status": "ok",
  "devices": [
    {
      "name": "Kitchen Mat",
      "ip_address": "10.0.50.74",
      "group": "heattrax",
      "reachable": true,
      "has_outlets": true,
      "outlets": [
        {
          "index": 0,
          "is_on": false,
          "alias": "Outlet 0",
          "controlled": true
        },
        {
          "index": 1,
          "is_on": true,
          "alias": "Outlet 1",
          "controlled": true
        }
      ],
      "error": null
    }
  ],
  "timestamp": "2024-01-15T10:35:00"
}
```

## Test 4: Device Control UI Error Helper Note
**Goal:** Verify the UI displays helpful error messages for python-kasa errors.

### Steps:
1. Navigate to the Health tab in the Web UI
2. Locate the Device Control section
3. If you have a device with errors, verify the error display

### To Simulate an Error (Optional):
1. Disconnect a device from the network or change its IP
2. Wait for the next scheduler cycle or refresh the page
3. Check the Device Control card for that device

### Expected Result:
- ✅ Raw error message is displayed (for debugging)
- ✅ When error includes "INTERNAL_QUERY_ERROR", an additional helper note appears:
  ```
  Note: This error is reported by the underlying python-kasa/Tapo library, not the scheduler itself.
  ```
- ✅ Helper note uses italic styling and smaller font (12px)
- ✅ Helper note maintains red error color (#e74c3c) for consistency

### Visual Example:
```
Device: Kitchen Mat
Group: heattrax
IP: 10.0.50.74
Error: get_device_info not found in {'get_device_time': <SmartErrorCode.INTERNAL_QUERY_ERROR: -100001>, ...}
Note: This error is reported by the underlying python-kasa/Tapo library, not the scheduler itself.
```

## Test 5: Health Tab Device Expectations
**Goal:** Verify device expectations load correctly in the Health tab.

### Steps:
1. Navigate to the Health tab in the Web UI
2. Scroll to the "Device Health" section
3. Verify devices are listed with their expected vs. actual states

### Expected Result:
- ✅ Device expectations are displayed correctly
- ✅ Each device shows:
  - Group name
  - IP address
  - Outlet index
  - Current state (on/off)
  - Expected state (on/off)
- ✅ No timeout errors in logs when loading device expectations

## Test 6: Concurrent Access
**Goal:** Verify multiple web UI requests don't cause conflicts.

### Steps:
1. Open multiple browser tabs to the Web UI
2. In different tabs, navigate between Status, Health, and Config tabs
3. Click refresh buttons in multiple tabs rapidly
4. Check logs for any concurrency issues

### Expected Result:
- ✅ All requests complete successfully
- ✅ No race conditions or deadlocks
- ✅ No "RuntimeError: This event loop is already running" errors
- ✅ Responses are consistent across tabs

## Test 7: Backward Compatibility
**Goal:** Verify fallback behavior if scheduler doesn't have the new method.

### Steps:
This is tested automatically in unit tests, but you can verify by:
1. Check that hasattr checks exist in web_server.py for `run_coro_in_loop`
2. Verify error handling returns HTTP 500 with clear message

### Expected Result:
- ✅ Code includes `hasattr(self.scheduler, 'run_coro_in_loop')` checks
- ✅ Fallback to old event loop creation exists
- ✅ Proper error messages if async operations fail

## Success Criteria
All tests should pass with:
- ✅ No python-kasa timeout errors
- ✅ No INTERNAL_QUERY_ERROR messages for healthy devices
- ✅ Valid JSON responses from all API endpoints
- ✅ Helpful error messages in the UI for device failures
- ✅ Stable operation under concurrent access

## Notes
- These changes are backward compatible
- The scheduler must be running for web server endpoints to work correctly
- Devices that are genuinely offline will still show errors (this is expected)
- The helper note only appears for python-kasa library errors, not network connectivity issues

# Device Initialization Timeout Fix - Summary

## Problem Statement

Users reported that device initialization was failing with timeout errors:
```
Failed to initialize device 'kitchen' at 10.0.50.74: Timed out getting discovery response for 10.0.50.74
```

Despite this error, manual testing **inside the same container** using the same python-kasa authentication worked perfectly:
```python
dev = await Discover.discover_single(IP, username=USERNAME, password=PASSWORD)
await dev.update()  # Works fine!
```

This indicated that:
- The network connectivity was fine
- The Tapo credentials were correct
- The device was reachable and responsive
- The issue was with timeout handling in the application

Additionally, when devices failed to initialize:
- Device Health showed OFF/0 with no indication of initialization failure
- Device Control showed no devices
- There was no clear distinction between "device offline" vs "initialization failed"

## Solution Implemented

### 1. Configurable Timeout with Better Defaults

**Before:** Implicit timeout from python-kasa (varies, often too short for Tapo devices)

**After:** Explicit 30-second timeout with per-device configuration:

```yaml
devices:
  credentials:
    username: michael@aghy.net
    password: $J2vzvi$vG0$sO8*
  groups:
    heattrax:
      enabled: true
      items:
        - name: kitchen
          ip_address: 10.0.50.74
          outlets: [0, 1]
          discovery_timeout_seconds: 60  # Optional: increase for slow devices
```

**Key Changes:**
- Added `DEFAULT_DISCOVERY_TIMEOUT = 30` seconds (class constant)
- Added `discovery_timeout_seconds` configuration option per device
- Wrapped `Discover.discover_single()` and `device.update()` with `asyncio.wait_for()`
- Both discovery and initial update now have explicit timeout control

### 2. Enhanced Error Logging

**Before:**
```
Failed to initialize device 'kitchen' at 10.0.50.74: Timed out getting discovery response for 10.0.50.74
```

**After:**
```
Timeout after 30s while initializing device 'kitchen' at 10.0.50.74. 
Device may be unreachable, overloaded, or slow to respond. 
Consider increasing 'discovery_timeout_seconds' in device config if device is reachable but slow.

Full exception: TimeoutError: [detailed stack trace]
Exception type: asyncio.TimeoutError
```

**Key Changes:**
- Capture and log exception type (TimeoutError, ConnectionError, etc.)
- Provide actionable error messages with troubleshooting hints
- Include timeout duration in error message
- Add DEBUG-level logging with full exception traceback
- Track initialization errors on device objects for later retrieval

### 3. Initialization Tracking and Reporting

**New Features:**
- **ManagedDevice**: Tracks `_initialization_error` field
- **DeviceGroup**: Tracks configured vs initialized device counts and failed device list
- **DeviceGroupManager**: Provides overall initialization summary across all groups

**Example Group Initialization Output:**
```
Initializing 1 device(s) in group 'heattrax'
  ✓ Initialized device: kitchen at 10.0.50.74
Group 'heattrax' initialized successfully with 1 device(s)
```

Or in case of failure:
```
Initializing 1 device(s) in group 'heattrax'
  ✗ Failed to initialize device 'kitchen' at 10.0.50.74: Timeout after 30s...
Group 'heattrax' initialized with 0 devices (all 1 configured device(s) failed)
```

### 4. Enhanced API Response

**New `/api/devices/status` Response Structure:**

```json
{
  "status": "ok",
  "devices": [
    {
      "name": "kitchen",
      "ip_address": "10.0.50.74",
      "group": "heattrax",
      "reachable": false,
      "initialized": false,
      "has_outlets": false,
      "outlets": [],
      "error": "Device not initialized: Timeout after 30s",
      "initialization_error": "Timeout after 30s"
    }
  ],
  "initialization_summary": {
    "total_groups": 1,
    "overall": {
      "configured_devices": 1,
      "initialized_devices": 0,
      "failed_devices": 1
    },
    "groups": {
      "heattrax": {
        "group_name": "heattrax",
        "configured_count": 1,
        "initialized_count": 0,
        "failed_count": 1,
        "failed_devices": [
          {
            "name": "kitchen",
            "ip_address": "10.0.50.74",
            "error": "Timeout after 30s while initializing device..."
          }
        ],
        "initialization_complete": true
      }
    }
  },
  "timestamp": "2025-11-19T02:35:24.782Z"
}
```

**Key Additions:**
- `initialization_summary` field in response
- Per-device `initialized` boolean field
- Per-device `initialization_error` field
- Overall statistics (configured vs initialized counts)
- Per-group failed device details

### 5. Improved Web UI Display

#### Device Control Tab

**Before:** Empty or "No devices configured or available"

**After:** Clear warning box with troubleshooting information:

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ Device Initialization Warning                           │
│                                                             │
│ 1 out of 1 configured device(s) failed to initialize.      │
│                                                             │
│ These devices will appear as offline/unreachable below.     │
│ Common causes:                                              │
│ • Device is unreachable on the network                      │
│ • Device IP address is incorrect                            │
│ • Device is slow to respond (timeout during discovery)      │
│ • Network connectivity issues                               │
│                                                             │
│ Check the container logs for detailed error messages. If    │
│ devices are reachable but slow, consider adding             │
│ discovery_timeout_seconds: 60 to the device configuration.  │
└─────────────────────────────────────────────────────────────┘
```

**Device Card Changes:**
- Status badge shows **"● Not Initialized"** vs **"● Offline"** vs **"● Online"**
- Initialization error displayed in prominent red box with context
- Clear distinction between runtime errors and initialization failures

#### Device Health Tab

**Before:** Shows OFF/0 with no explanation

**After:** Clear message when devices fail to initialize:

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ No Device Status Available                              │
│                                                             │
│ 1 device(s) configured, but device status/expectations     │
│ not available. This may indicate devices failed to         │
│ initialize or scheduler not fully started.                 │
│ Check Device Control tab and logs for details.             │
└─────────────────────────────────────────────────────────────┘
```

### 6. Comprehensive Test Coverage

**New Test Suite:** `test_device_initialization_timeout.py`

Tests include:
- ✅ Default timeout is 30 seconds
- ✅ Custom timeout can be configured per device
- ✅ Initialization errors are tracked on device objects
- ✅ Timeout errors are properly handled and include helpful messages
- ✅ Successful initialization clears previous errors
- ✅ Device status includes initialization error information
- ✅ DeviceGroup tracks failed devices
- ✅ DeviceGroup provides initialization info
- ✅ DeviceGroupManager provides overall initialization summary

**All 9 tests passing ✅**

### 7. Documentation Updates

**HEALTH_CHECK.md:**
- New section: "Device Initialization Timeout"
- Configuration examples for custom timeouts
- When to increase timeout (slow networks, multi-outlet devices)
- Troubleshooting steps for initialization failures
- Network connectivity testing commands

**README.md:**
- New troubleshooting section for initialization timeouts
- Quick reference to timeout configuration
- Links to detailed documentation

## Benefits

1. **Robustness:** Devices that are slow to respond now have adequate time to initialize
2. **Visibility:** Clear indication in logs, API, and UI when initialization fails
3. **Debuggability:** Detailed error messages with troubleshooting hints
4. **Configurability:** Per-device timeout configuration for special cases
5. **User Experience:** UI clearly distinguishes initialization failures from runtime issues
6. **Backwards Compatibility:** Existing configurations continue to work without changes

## Migration Guide

### For Users Experiencing Timeout Issues

1. **Update to the latest version** (includes these fixes)

2. **If devices are slow but reachable**, add timeout configuration:
   ```yaml
   devices:
     groups:
       my_group:
         items:
           - name: my_device
             ip_address: 10.0.50.74
             outlets: [0, 1]
             discovery_timeout_seconds: 60  # Increase from default 30s
   ```

3. **Check the Web UI Health tab** for clear status of initialization

4. **Review container logs** for detailed error messages and guidance

### For Developers

The changes are backwards compatible. Existing code using `DeviceGroupManager` will:
- Automatically benefit from longer timeouts
- Continue to work without modifications
- Get enhanced error information if accessing new fields

New methods available:
- `DeviceGroup.get_initialization_info()` → dict with init stats
- `DeviceGroupManager.get_initialization_summary()` → dict with overall stats
- `ManagedDevice._initialization_error` → string with error details

## Testing Recommendations

1. **Test with reachable device:** Should initialize successfully within 30s
2. **Test with unreachable IP:** Should fail gracefully with clear error message
3. **Test with slow device:** Configure custom timeout, verify it works
4. **Check Web UI:** Verify initialization status is clearly displayed
5. **Check API response:** Verify `initialization_summary` is present

## Security Analysis

✅ **CodeQL scan passed:** No security vulnerabilities detected
✅ **No new dependencies added**
✅ **No credential exposure in error messages**
✅ **Timeout prevents hanging forever on unreachable devices**

## Example: Before and After

### Before
```
# Container Logs
2025-11-18 15:02:17,911 - device_group_manager - ERROR - Failed to initialize device 'kitchen' at 10.0.50.74: Timed out getting discovery response for 10.0.50.74
2025-11-18 15:02:17,911 - device_group_manager - INFO - Group 'heattrax' initialized with 0 devices

# Web UI Device Health
Plug: OFF
Outlet 0: 0
Outlet 1: 0

# Web UI Device Control
(empty - no devices)
```

### After
```
# Container Logs
2025-11-19 02:35:24,782 - device_group_manager - DEBUG - Initializing device 'kitchen' at 10.0.50.74 (timeout: 30s)
2025-11-19 02:35:24,782 - device_group_manager - DEBUG - Using Discover.discover_single with Tapo credentials for 10.0.50.74
2025-11-19 02:35:24,782 - device_group_manager - DEBUG - Device discovered at 10.0.50.74, fetching initial state...
2025-11-19 02:35:25,123 - device_group_manager - INFO - Successfully initialized device 'kitchen': model=EP40M, alias=Smart Plug, outlets=2

# OR if it fails:
2025-11-19 02:35:54,782 - device_group_manager - ERROR - Timeout after 30s while initializing device 'kitchen' at 10.0.50.74. Device may be unreachable, overloaded, or slow to respond. Consider increasing 'discovery_timeout_seconds' in device config if device is reachable but slow.
2025-11-19 02:35:54,783 - device_group_manager - WARNING - Group 'heattrax' initialized with 0 devices (all 1 configured device(s) failed)

# Web UI Device Control
⚠️ Device Initialization Warning
1 out of 1 configured device(s) failed to initialize.
[Troubleshooting tips displayed]

Device: kitchen
Status: ● Not Initialized
Group: heattrax
IP: 10.0.50.74

Initialization Failed:
Timeout after 30s

# Web UI Device Health
⚠️ No Device Status Available
1 device(s) configured, but device status/expectations not available.
This may indicate devices failed to initialize or scheduler not fully started.
Check Device Control tab and logs for details.
```

## Conclusion

This fix addresses the core issue of Tapo device initialization timeouts while simultaneously improving error visibility, configurability, and user experience. The solution is backwards compatible, well-tested, and provides clear paths for troubleshooting and resolution.

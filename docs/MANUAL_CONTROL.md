# Manual Device Control Guide

This guide explains the manual device control feature available in the HeatTrax Scheduler Web UI.

## Overview

The Health page in the Web UI now includes a **Device Control** section that allows you to manually turn devices and individual outlets ON or OFF. This feature provides immediate control for testing, emergency situations, or temporary overrides of scheduled behavior.

## Accessing Device Control

1. Open the HeatTrax Scheduler Web UI in your browser (default: `http://localhost:4328`)
2. Navigate to the **Health** tab
3. Scroll down to the **Device Control** section
4. Click the **🔄 Refresh** button to load current device states

## Device Control Panel

For each configured device, you'll see:

### Device Information
- **Device Name**: The friendly name configured in your settings
- **Status Badge**: 
  - `● Online` (green) - Device is reachable and responding
  - `● Offline` (red) - Device is unreachable or not responding
- **Group**: Which device group the device belongs to
- **IP Address**: The device's network address

### Outlet Controls
Each outlet on the device shows:
- **Outlet Name**: The configured name or default label
- **Current State**: 
  - `ON` (green, bold) - Outlet is currently powered on
  - `OFF` (gray) - Outlet is currently powered off
- **Control Buttons**:
  - **Turn ON**: Activates the outlet (disabled if already on or device offline)
  - **Turn OFF**: Deactivates the outlet (disabled if already off or device offline)

## Using Manual Controls

### Turning an Outlet ON
1. Ensure the device status shows as **● Online**
2. Find the outlet you want to control
3. Click the **Turn ON** button
4. Wait for the confirmation message: `✓ Successfully turned ON outlet X`
5. The outlet state will update automatically

### Turning an Outlet OFF
1. Ensure the device status shows as **● Online**
2. Find the outlet you want to control
3. Click the **Turn OFF** button
4. Wait for the confirmation message: `✓ Successfully turned OFF outlet X`
5. The outlet state will update automatically

### Handling Errors
If a control command fails, you'll see an error message:
- `✗ Failed: Device not reachable` - Device went offline during the command
- `✗ Failed: Connection timeout` - Device took too long to respond
- `✗ Error: [details]` - Other errors with specific details

Error messages automatically disappear after 5 seconds.

## How Manual Control Interacts with Scheduling

**Important**: Manual control provides **temporary** overrides of scheduled behavior. Here's how it works:

### Scheduler Behavior
- The scheduler runs on a regular interval (default: 30 minutes)
- On each cycle, it evaluates weather conditions and schedules
- It then sets all devices to their **desired state** based on these conditions
- The scheduler does **not** track or remember manual overrides

### Manual Override Scenarios

#### Scenario 1: Manual ON during OFF period
You manually turn ON a device during a period when the scheduler wants it OFF.
- **Immediate effect**: Device turns ON
- **Next scheduler cycle**: Device will be turned OFF again if conditions require it
- **Duration**: Override lasts until next scheduler cycle (typically 30 minutes)

#### Scenario 2: Manual OFF during ON period
You manually turn OFF a device during a period when the scheduler wants it ON.
- **Immediate effect**: Device turns OFF
- **Next scheduler cycle**: Device will be turned ON again if conditions require it
- **Duration**: Override lasts until next scheduler cycle

#### Scenario 3: Manual control during matching state
You manually control a device to match what the scheduler wants.
- **Immediate effect**: Device state changes (or stays the same)
- **Next scheduler cycle**: No change, as manual state matches scheduled state
- **Duration**: Persists as long as scheduler agrees with the state

### Best Practices

1. **Emergency Shutoff**: Manual controls are ideal for emergency situations where you need immediate control
   
2. **Testing**: Use manual controls to test if devices are working before relying on scheduling

3. **Temporary Overrides**: If you need a brief override (less than scheduler interval), manual control is perfect

4. **Longer Overrides**: For overrides lasting longer than the scheduler interval:
   - Option A: Disable the device group in Configuration and manually control as needed
   - Option B: Update the schedule/weather settings to match your desired behavior
   - Option C: Use manual controls and re-apply them after each scheduler cycle

5. **Monitoring**: Check the device state on the Health page after the scheduler cycle to ensure desired behavior

## Safety Features

### Automatic State Refresh
- Device states automatically refresh after control commands
- You can manually refresh by clicking the **🔄 Refresh** button
- The refresh ensures you see the current actual state

### Disabled Buttons
- Buttons are automatically disabled when:
  - Device is offline (prevents errors)
  - Outlet is already in the desired state (prevents unnecessary commands)
- This prevents accidental duplicate commands

### State Verification
- After each control command, the system verifies the new state
- If verification fails, an error is shown
- This ensures you know if a command actually worked

### Scheduler Safety Limits
Even with manual control, scheduler safety limits remain active:
- **Max Runtime**: Devices automatically shut off after max_runtime_hours
- **Cooldown**: Devices respect cooldown_minutes after shutdown
- **Morning Mode**: Morning mode restrictions apply if enabled

## API Integration

The manual control feature is backed by REST API endpoints that can be used programmatically:

### Get Device Status
```bash
GET /api/devices/status

Response:
{
    "status": "ok",
    "devices": [
        {
            "name": "Front Mat",
            "ip_address": "192.168.1.100",
            "group": "heated_mats",
            "reachable": true,
            "has_outlets": true,
            "outlets": [
                {
                    "index": 0,
                    "is_on": true,
                    "alias": "Outlet 0",
                    "controlled": true
                }
            ],
            "error": null
        }
    ],
    "timestamp": "2024-01-01T12:00:00"
}
```

### Control Device/Outlet
```bash
POST /api/devices/control
Content-Type: application/json

{
    "group": "heated_mats",
    "device": "Front Mat",
    "outlet": 0,
    "action": "on"
}

Response:
{
    "success": true,
    "device": "Front Mat",
    "outlet": 0,
    "action": "on",
    "error": null
}
```

To control an entire device (not a specific outlet), set `"outlet": null`.

## Troubleshooting

### Device Shows Offline
**Problem**: Device appears offline in the control panel
**Solutions**:
1. Check that the device is powered on and connected to your network
2. Verify the IP address is correct in Configuration
3. Ensure the device is not blocked by firewall rules
4. Try pinging the device from the host machine
5. Check device credentials in Configuration (username/password)

### Control Commands Fail
**Problem**: Control commands return errors
**Solutions**:
1. Verify device is showing as **● Online**
2. Check network connectivity to the device
3. Ensure Tapo credentials are correct in Configuration
4. Try controlling the device through the official Tapo app
5. Check HeatTrax logs for detailed error messages

### State Doesn't Update
**Problem**: Device state doesn't refresh after control command
**Solutions**:
1. Click the **🔄 Refresh** button manually
2. Wait a few seconds and refresh again (device may be slow to respond)
3. Check if scheduler is actively running (may override your change)
4. Verify device is actually changing state (check physical device)

### Manual Control Overridden Too Quickly
**Problem**: Scheduler immediately undoes manual control
**Solutions**:
1. Understand this is expected behavior (see "How Manual Control Interacts with Scheduling")
2. Consider disabling the device group temporarily if you need extended manual control
3. Adjust scheduler settings to match your desired behavior
4. Monitor the scheduler logs to see when and why it's changing device states

## Security Considerations

### Network Access
- Manual control requires network access to the Web UI
- By default, Web UI binds to localhost (127.0.0.1) for security
- To access from other machines, set `HEATTRAX_WEB_HOST=0.0.0.0`
- Only expose the Web UI on trusted networks

### Authentication
- Current version does not include authentication
- Do not expose the Web UI directly to the internet
- Use a VPN or reverse proxy with authentication if remote access is needed
- Future versions may include built-in authentication

### Device Credentials
- Tapo credentials are required for device control
- Credentials are stored in config.yaml (use file permissions to protect)
- Environment variables can be used for credential management
- Credentials are never exposed through the Web UI

## Related Documentation

- [Web UI Guide](WEB_UI_GUIDE.md) - General Web UI documentation
- [Health Checks](HEALTH_CHECK.md) - Device health monitoring
- [Quick Start Guide](QUICKSTART.md) - Initial setup
- [Configuration Reference](ENVIRONMENT_VARIABLES.md) - All configuration options

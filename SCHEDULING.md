# HeatTrax Scheduler - Unified Conditional Scheduling Guide

## Table of Contents

- [System Overview](#system-overview)
- [Configuration Structure](#configuration-structure)
- [Schedule Types](#schedule-types)
- [Conditions System](#conditions-system)
- [Days of Week](#days-of-week)
- [Priority System](#priority-system)
- [Migration Examples](#migration-examples)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## System Overview

The HeatTrax Scheduler uses a **unified conditional scheduling system** that combines multiple scheduling paradigms into a single, flexible configuration format. This system allows you to control devices based on:

- **Time of day** (fixed clock times)
- **Solar events** (sunrise/sunset with offsets)
- **Weather conditions** (temperature, precipitation)
- **Days of week** (weekday/weekend patterns)
- **Priority levels** (critical, normal, low)

### Key Concepts

#### Schedule Groups

Devices are organized into **groups** that share common schedules and automation rules. Each group can have:

- Multiple devices (outlets, plugs, etc.)
- Multiple schedules (each with different conditions)
- Independent state tracking (runtime, cooldown)

```yaml
devices:
  groups:
    driveway_heating:      # Group name
      enabled: true
      items: [...]         # Devices in this group
      schedules: [...]     # Schedules for this group
```

#### Schedule Evaluation

The scheduler evaluates all schedules in a group and determines whether devices should be ON or OFF:

1. **For each schedule**, check if:
   - Schedule is enabled
   - Current day matches the schedule's day filter
   - Current time is within the schedule's time window
   - All weather conditions are met (if any)

2. **If ANY schedule wants the device ON**, the device turns ON
3. **The highest priority schedule wins** if multiple schedules are active
4. **If NO schedules want the device ON**, the device turns OFF

#### How Schedules Are Evaluated

The evaluation process follows these steps:

**Step 1: Filter by enabled status**
- Only enabled schedules are evaluated
- Disabled schedules are completely ignored

**Step 2: Filter by day of week**
- Check if current day (1=Monday, 7=Sunday) is in the schedule's `days` list
- Schedules not matching the current day are skipped

**Step 3: Calculate time window**
- For `time` type: Use the specified HH:MM time
- For `sunrise`/`sunset` type: Calculate solar time + offset, or use fallback
- Determine if current time is within the ON-OFF window

**Step 4: Evaluate conditions (if present)**
- Check temperature conditions against current weather
- Check precipitation conditions against forecast
- If weather service is offline, schedules with conditions are skipped

**Step 5: Priority resolution**
- If multiple schedules want the device ON, the highest priority wins:
  - `critical` (highest) - Safety/heating schedules
  - `normal` (default) - Standard automation
  - `low` (lowest) - Nice-to-have features

**Step 6: Device action**
- If any schedule passed all filters → Device turns ON
- If no schedules passed filters → Device turns OFF

#### Condition Evaluation Logic

Weather conditions are optional. When present, they add an additional filter:

```yaml
conditions:
  temperature_max: 32          # Must be ≤ 32°F
  precipitation_active: true   # Precipitation must be detected
  black_ice_risk: true         # Black ice formation conditions detected
```

**Available Conditions:**
- `temperature_max`: Temperature must be at or below this value (°F)
- `precipitation_active`: Precipitation must be actively forecasted or occurring
- `black_ice_risk`: Black ice formation conditions detected (temperature near freezing, high humidity, small dew point spread)

**Condition Logic:**
- **All conditions must be TRUE** for the schedule to be active
- If weather service is offline, schedules with conditions are **skipped**
- Schedules without conditions are **always evaluated** (weather-independent)

**Black Ice Detection:**

Black ice can form without precipitation when moisture in the air condenses on cold surfaces and freezes. The system detects black ice risk when:
- Temperature is at or below threshold (default: 36°F)
- Dew point spread is small (default: ≤4°F difference between temperature and dew point)
- Relative humidity is high (default: ≥80%)

Configure detection thresholds in `config.yaml`:
```yaml
thresholds:
  black_ice_detection:
    enabled: true
    temperature_max_f: 36        # Max temp for black ice risk
    dew_point_spread_f: 4        # Max temp-dewpoint spread
    humidity_min_percent: 80     # Minimum humidity
```

#### Priority System

When multiple schedules want a device ON simultaneously:

1. **Critical priority** (heating, safety) takes precedence
2. **Normal priority** (standard automation) is default
3. **Low priority** (decorative, optional) is lowest

Example: A critical morning heating schedule will override a low-priority decorative lighting schedule if both are active.

---

## Configuration Structure

### Basic Structure

```yaml
devices:
  credentials:
    username: "your_tapo_username"
    password: "your_tapo_password"
  
  groups:
    # Group name (can be anything descriptive)
    driveway_heating:
      enabled: true
      
      # Devices in this group
      items:
        - name: "Driveway Mat"
          ip_address: "192.168.1.100"
          outlets: [0, 1]  # Optional: control specific outlets
      
      # Schedules for this group
      schedules:
        - name: "Morning Black Ice Protection"
          enabled: true
          priority: "critical"
          days: [1, 2, 3, 4, 5]  # Weekdays only
          on:
            type: "time"
            value: "06:00"
          off:
            type: "sunrise"
            offset: 30
            fallback: "08:00"
          conditions:
            temperature_max: 32
          safety:
            max_runtime_hours: 3
            cooldown_minutes: 30
```

### Configuration Sections

#### Group Configuration

```yaml
driveway_heating:           # Group name
  enabled: true             # Enable/disable entire group
  items: [...]              # List of devices
  schedules: [...]          # List of schedules
```

#### Device Configuration

```yaml
items:
  - name: "Device Name"              # Descriptive name
    ip_address: "192.168.1.100"      # Static IP address
    outlets: [0, 1]                  # Optional: outlet indices (EP40M)
    discovery_timeout_seconds: 30    # Optional: connection timeout
```

#### Schedule Configuration

```yaml
schedules:
  - name: "Schedule Name"            # Descriptive name
    enabled: true                    # Enable/disable this schedule
    priority: "critical"             # critical, normal, or low
    days: [1, 2, 3, 4, 5, 6, 7]     # Days of week (1=Mon, 7=Sun)
    on:                              # Turn-on time configuration
      type: "time"                   # time, sunrise, sunset
      value: "06:00"                 # Required for type=time
    off:                             # Turn-off time configuration
      type: "time"
      value: "22:00"
    conditions:                      # Optional weather conditions
      temperature_max: 32
      precipitation_active: true
    safety:                          # Optional safety overrides
      max_runtime_hours: 6
      cooldown_minutes: 30
```

---

## Schedule Types

### Clock-Based Schedules

**Fixed time schedules** use absolute clock times (24-hour format).

#### Simple Time-Based Schedule

Turn on at 6:00 AM, off at 10:00 PM:

```yaml
schedules:
  - name: "Daily Heating"
    enabled: true
    priority: "normal"
    days: [1, 2, 3, 4, 5, 6, 7]  # Every day
    on:
      type: "time"
      value: "06:00"
    off:
      type: "time"
      value: "22:00"
```

#### Day-Spanning Schedule

Turn on at 11:00 PM, off at 2:00 AM (crosses midnight):

```yaml
schedules:
  - name: "Overnight Lighting"
    enabled: true
    priority: "normal"
    days: [1, 2, 3, 4, 5, 6, 7]
    on:
      type: "time"
      value: "23:00"
    off:
      type: "time"
      value: "02:00"
```

**Note:** The scheduler automatically handles schedules that cross midnight.

### Solar-Based Schedules

**Solar schedules** tie to sunrise or sunset, adjusting automatically throughout the year.

#### Format

```yaml
on:
  type: "sunrise"      # or "sunset"
  offset: -30          # Minutes (negative = before, positive = after)
  fallback: "06:00"    # Fallback time if solar calculation fails
```

#### Offset Examples

| Offset  | Meaning                     |
|---------|-----------------------------|
| `-30`   | 30 minutes before sunrise   |
| `0`     | Exactly at sunrise          |
| `30`    | 30 minutes after sunrise    |
| `-60`   | 1 hour before sunset        |
| `15`    | 15 minutes after sunset     |

**Offset Range:** -180 to +180 minutes (-3 hours to +3 hours)

#### Sunrise-Based Example

Turn on 30 minutes before sunrise, off at 8:00 AM:

```yaml
schedules:
  - name: "Pre-Dawn Heating"
    enabled: true
    priority: "critical"
    days: [1, 2, 3, 4, 5]  # Weekdays
    on:
      type: "sunrise"
      offset: -30           # 30 minutes before sunrise
      fallback: "05:30"     # If solar calculation fails
    off:
      type: "time"
      value: "08:00"
```

#### Sunset-Based Example

Turn on 30 minutes before sunset, off at 1:00 AM:

```yaml
schedules:
  - name: "Evening Lights"
    enabled: true
    priority: "normal"
    days: [1, 2, 3, 4, 5, 6, 7]
    on:
      type: "sunset"
      offset: -30           # 30 minutes before sunset
      fallback: "17:00"
    off:
      type: "time"
      value: "01:00"
```

#### Solar Schedule with Solar Off-Time

Both on and off times based on solar events:

```yaml
schedules:
  - name: "Dawn to Dusk"
    enabled: true
    priority: "normal"
    days: [1, 2, 3, 4, 5, 6, 7]
    on:
      type: "sunrise"
      offset: -15           # 15 min before sunrise
      fallback: "06:00"
    off:
      type: "sunset"
      offset: 30            # 30 min after sunset
      fallback: "19:00"
```

#### Why Use Solar Schedules?

Solar schedules automatically adjust to seasonal changes:

- **Winter:** Earlier sunset → lights come on earlier
- **Summer:** Later sunset → lights come on later
- **No manual adjustments needed** throughout the year

#### Fallback Times

**Always provide a fallback time** for solar schedules. Fallbacks are used when:

- Solar calculation fails (polar regions, invalid coordinates)
- Location/timezone not configured
- Date/time issues

---

## Conditions System

**Conditions** add weather-based filters to schedules. All conditions must be TRUE for the schedule to be active.

### Available Conditions

#### `temperature_max`

**Activate only if temperature is at or below the threshold.**

```yaml
conditions:
  temperature_max: 32  # Only when temp ≤ 32°F
```

**Use cases:**
- Heating schedules (only when cold)
- Frost protection
- Temperature-based automation

**Example:**
```yaml
- name: "Cold Weather Heating"
  enabled: true
  priority: "critical"
  days: [1, 2, 3, 4, 5]
  on:
    type: "time"
    value: "05:00"
  off:
    type: "time"
    value: "08:00"
  conditions:
    temperature_max: 32  # Only run when temp ≤ 32°F
```

#### `precipitation_active`

**Activate only when precipitation is detected (or not detected).**

```yaml
conditions:
  precipitation_active: true   # Only when precipitation detected
  # OR
  precipitation_active: false  # Only when no precipitation
```

**Use cases:**
- Preemptive heating before snow/rain
- Storm protection
- Weather-dependent automation

**Example:**
```yaml
- name: "Storm Protection"
  enabled: true
  priority: "critical"
  days: [1, 2, 3, 4, 5, 6, 7]
  on:
    type: "time"
    value: "00:00"
  off:
    type: "time"
    value: "23:59"
  conditions:
    temperature_max: 32
    precipitation_active: true  # Only when snowing/icing
```

#### `black_ice_risk`

**Activate when black ice formation conditions are detected.**

```yaml
conditions:
  black_ice_risk: true   # Only when black ice risk detected
```

**What is Black Ice Risk?**

Black ice forms when:
1. Moisture in the air condenses on cold surfaces
2. The temperature drops below freezing
3. This creates invisible ice without any precipitation

The system detects black ice risk by monitoring:
- **Temperature:** Near or below freezing (default: ≤36°F)
- **Dew Point Spread:** Small difference between temperature and dew point (default: ≤4°F)
- **Relative Humidity:** High moisture in the air (default: ≥80%)

**Use cases:**
- Early morning black ice protection
- Clear night frost prevention
- Proactive mat activation without precipitation

**Example:**
```yaml
- name: "Black Ice Protection"
  enabled: true
  priority: "critical"
  days: [1, 2, 3, 4, 5, 6, 7]
  on:
    type: "time"
    value: "00:00"
  off:
    type: "sunrise"
    offset: 60        # Turn off 1 hour after sunrise
    fallback: "08:00"
  conditions:
    black_ice_risk: true  # Only when black ice conditions detected
```

**Configuration:**

Black ice detection can be customized in `config.yaml`:

```yaml
thresholds:
  black_ice_detection:
    enabled: true
    temperature_max_f: 36        # Max temp to consider risk
    dew_point_spread_f: 4        # Trigger when temp - dewpoint ≤ 4°F
    humidity_min_percent: 80     # Minimum humidity to consider risk
```

### Combining Conditions

**All conditions must be TRUE** for the schedule to activate:

```yaml
conditions:
  temperature_max: 32          # AND temp ≤ 32°F
  precipitation_active: true   # AND precipitation detected
```

This means: "Only activate when it's cold (≤32°F) AND precipitation is detected."

**Combining Black Ice with Other Conditions:**

You can combine black ice detection with other conditions for more precise control:

```yaml
- name: "Comprehensive Winter Protection"
  enabled: true
  priority: "critical"
  days: [1, 2, 3, 4, 5, 6, 7]
  on:
    type: "time"
    value: "00:00"
  off:
    type: "time"
    value: "23:59"
  conditions:
    temperature_max: 36
    # This activates when EITHER precipitation OR black ice risk is detected
    # Note: Use separate schedules for OR logic, not within one schedule
```

**Pro Tip:** Create separate schedules for different weather scenarios (one for precipitation, one for black ice) rather than trying to combine them in one schedule. This provides more flexibility and clearer logging.

### Weather Offline Behavior

When weather service is offline or unreachable:

- **Schedules WITH conditions** are skipped (not evaluated)
- **Schedules WITHOUT conditions** continue to work normally

**Best Practice:** Always have at least one schedule without conditions for critical heating, so devices still work during weather outages.

### No Conditions = Always Evaluated

Schedules without conditions are **weather-independent**:

```yaml
- name: "Always-On Morning Heat"
  enabled: true
  priority: "normal"
  days: [1, 2, 3, 4, 5]
  on:
    type: "time"
    value: "06:00"
  off:
    type: "time"
    value: "08:00"
  # No conditions = always runs (regardless of weather)
```

---

## Days of Week

### Numbering System

Days are numbered according to **ISO 8601 standard:**

| Number | Day       |
|--------|-----------|
| 1      | Monday    |
| 2      | Tuesday   |
| 3      | Wednesday |
| 4      | Thursday  |
| 5      | Friday    |
| 6      | Saturday  |
| 7      | Sunday    |

### Day Specification

Specify days as a list of numbers:

```yaml
days: [1, 2, 3, 4, 5, 6, 7]  # Every day
```

### Common Patterns

#### Every Day

```yaml
days: [1, 2, 3, 4, 5, 6, 7]
```

#### Weekdays Only (Monday-Friday)

```yaml
days: [1, 2, 3, 4, 5]
```

#### Weekends Only (Saturday-Sunday)

```yaml
days: [6, 7]
```

#### Specific Days

```yaml
days: [1, 3, 5]      # Monday, Wednesday, Friday
days: [2, 4]         # Tuesday, Thursday
days: [7]            # Sunday only
```

### Example: Weekday vs Weekend Schedules

Different schedules for weekdays and weekends:

```yaml
schedules:
  # Weekday morning heating
  - name: "Weekday Morning"
    enabled: true
    priority: "critical"
    days: [1, 2, 3, 4, 5]  # Mon-Fri
    on:
      type: "time"
      value: "05:30"
    off:
      type: "time"
      value: "08:00"
    conditions:
      temperature_max: 32
  
  # Weekend morning heating (later start)
  - name: "Weekend Morning"
    enabled: true
    priority: "critical"
    days: [6, 7]           # Sat-Sun
    on:
      type: "time"
      value: "07:00"       # Later start
    off:
      type: "time"
      value: "10:00"
    conditions:
      temperature_max: 32
```

---

## Priority System

**Priority** determines which schedule takes precedence when multiple schedules want a device ON simultaneously.

### Priority Levels

| Priority   | Value        | Description                          | Example Use Cases                |
|------------|--------------|--------------------------------------|----------------------------------|
| `critical` | Highest      | Safety, heating, essential functions | Driveway heating, frost protection |
| `normal`   | Default      | Standard automation                  | Evening lights, regular schedules  |
| `low`      | Lowest       | Nice-to-have, decorative             | Holiday decorations, accent lights |

### When Priorities Matter

Priorities only matter when **multiple schedules are active** at the same time:

1. Scheduler evaluates all active schedules
2. If multiple schedules want the device ON, the **highest priority** wins
3. The winning schedule's settings (runtime, cooldown) apply

### Example: Priority in Action

```yaml
schedules:
  # Critical morning heating
  - name: "Morning Black Ice Protection"
    enabled: true
    priority: "critical"
    days: [1, 2, 3, 4, 5]
    on:
      type: "time"
      value: "06:00"
    off:
      type: "time"
      value: "08:00"
    conditions:
      temperature_max: 32
    safety:
      max_runtime_hours: 3
  
  # Low priority decorative lights
  - name: "Morning Accent Lights"
    enabled: true
    priority: "low"
    days: [1, 2, 3, 4, 5]
    on:
      type: "time"
      value: "06:00"
    off:
      type: "time"
      value: "09:00"
    safety:
      max_runtime_hours: 8
```

**Scenario:** Both schedules are active from 6:00-8:00 AM on cold mornings:
- The **critical** heating schedule wins
- The heating schedule's runtime limit (3 hours) applies
- Logs show: "Schedule 'Morning Black Ice Protection' active (priority=critical)"

### Best Practices for Priorities

**Use `critical` for:**
- Heating/cooling for safety
- Frost/ice protection
- Essential functions

**Use `normal` for:**
- Standard daily automation
- Most schedules
- Default behavior

**Use `low` for:**
- Decorative lighting
- Optional features
- Nice-to-have automation

---

## Migration Examples

### Example 1: Simple Time-Based Schedule

#### Old Configuration (Legacy)

```yaml
# Old system (no longer supported)
device:
  ip_address: "192.168.1.100"

schedules:
  - time: "06:00"
    temperature: 20
  - time: "22:00"
    temperature: 16
```

#### New Configuration (Unified System)

```yaml
devices:
  credentials:
    username: "your_tapo_username"
    password: "your_tapo_password"
  
  groups:
    daily_heating:
      enabled: true
      items:
        - name: "Heater"
          ip_address: "192.168.1.100"
      schedules:
        - name: "Morning On"
          enabled: true
          priority: "normal"
          days: [1, 2, 3, 4, 5, 6, 7]
          on:
            type: "time"
            value: "06:00"
          off:
            type: "time"
            value: "22:00"
```

**Key Changes:**
- Device moved to `devices.groups.*.items`
- Global credentials added
- Single schedule with ON and OFF times
- Temperature settings removed (controlled by device state)
- Added schedule metadata (name, priority, days)

### Example 2: Vacation Mode Integration

#### Old System

Vacation mode was handled in code logic, not configuration.

#### New Configuration

```yaml
# Global vacation mode flag
vacation_mode: false  # ENV: HEATTRAX_VACATION_MODE

devices:
  groups:
    # Normal schedule (disabled during vacation)
    normal_schedule:
      enabled: true
      items:
        - name: "Driveway Mat"
          ip_address: "192.168.1.100"
      schedules:
        - name: "Weekday Heating"
          enabled: true
          priority: "normal"
          days: [1, 2, 3, 4, 5]
          on:
            type: "time"
            value: "06:00"
          off:
            type: "time"
            value: "22:00"
          conditions:
            temperature_max: 32
    
    # Vacation schedule (minimal heating)
    # Manually enable this group when on vacation
    vacation_schedule:
      enabled: false  # Enable via Web UI when going on vacation
      items:
        - name: "Driveway Mat"
          ip_address: "192.168.1.100"
      schedules:
        - name: "Minimal Heating"
          enabled: true
          priority: "low"
          days: [1, 2, 3, 4, 5, 6, 7]
          on:
            type: "time"
            value: "00:00"
          off:
            type: "time"
            value: "23:59"
          conditions:
            temperature_max: 15  # Only if extremely cold
          safety:
            max_runtime_hours: 2  # Minimal runtime
```

**Migration Steps:**
1. Set `vacation_mode: true` when going on vacation (disables all schedules)
2. Or create separate groups for normal vs. vacation schedules
3. Enable/disable groups via Web UI or configuration

**Using Environment Variable:**
```bash
# Disable all schedules for vacation
HEATTRAX_VACATION_MODE=true
```

### Example 3: Solar-Based Schedules

#### Old System (Fixed Times)

```yaml
# Fixed times (don't adjust for seasons)
schedules:
  - time: "17:00"  # Always 5:00 PM
    action: "on"
  - time: "23:00"  # Always 11:00 PM
    action: "off"
```

#### New Configuration (Solar-Based)

```yaml
devices:
  groups:
    christmas_lights:
      enabled: true
      items:
        - name: "Front Yard Lights"
          ip_address: "192.168.1.110"
      schedules:
        - name: "Sunset to Midnight"
          enabled: true
          priority: "normal"
          days: [1, 2, 3, 4, 5, 6, 7]
          on:
            type: "sunset"
            offset: -30        # 30 minutes before sunset
            fallback: "17:00"  # Fallback in winter
          off:
            type: "time"
            value: "23:00"
```

**Benefits:**
- Lights automatically adjust to sunset time throughout the year
- Winter: Lights on at ~4:30 PM (sunset ~5:00 PM)
- Summer: Lights on at ~8:00 PM (sunset ~8:30 PM)
- No manual adjustments needed

### Example 4: Conditional Temperature Schedules

#### Old System (Always Runs)

```yaml
# Always runs at 5:30 AM, regardless of temperature
schedules:
  - time: "05:30"
    action: "on"
  - time: "08:00"
    action: "off"
```

#### New Configuration (Temperature-Conditional)

```yaml
devices:
  groups:
    driveway_heating:
      enabled: true
      items:
        - name: "Driveway Mat"
          ip_address: "192.168.1.100"
      schedules:
        - name: "Cold Weather Morning Boost"
          enabled: true
          priority: "critical"
          days: [1, 2, 3, 4, 5]
          on:
            type: "time"
            value: "05:30"
          off:
            type: "time"
            value: "08:00"
          conditions:
            temperature_max: 0  # Only when temp ≤ 0°F
          safety:
            max_runtime_hours: 3
```

**Benefits:**
- Only runs when temperature is at or below 0°F
- Saves energy on warmer mornings
- Automatically adjusts based on real-time weather

### Example 5: Multiple Schedules in One Group

#### Old System (Separate Configurations)

Multiple configuration files or sections for different scenarios.

#### New Configuration (Multiple Schedules)

```yaml
devices:
  groups:
    driveway_heating:
      enabled: true
      items:
        - name: "Driveway Mat"
          ip_address: "192.168.1.100"
      schedules:
        # Schedule 1: Morning black ice protection
        - name: "Morning Black Ice"
          enabled: true
          priority: "critical"
          days: [1, 2, 3, 4, 5]
          on:
            type: "sunrise"
            offset: -30
            fallback: "06:00"
          off:
            type: "sunrise"
            offset: 30
            fallback: "08:00"
          conditions:
            temperature_max: 32
        
        # Schedule 2: All-day storm protection
        - name: "Storm Protection"
          enabled: true
          priority: "critical"
          days: [1, 2, 3, 4, 5, 6, 7]
          on:
            type: "time"
            value: "00:00"
          off:
            type: "time"
            value: "23:59"
          conditions:
            temperature_max: 32
            precipitation_active: true
        
        # Schedule 3: Weekend extended heating
        - name: "Weekend Extended"
          enabled: true
          priority: "normal"
          days: [6, 7]
          on:
            type: "time"
            value: "07:00"
          off:
            type: "time"
            value: "12:00"
          conditions:
            temperature_max: 25  # Colder threshold
```

**Benefits:**
- All schedules in one place
- Device turns ON if ANY schedule is active
- Priority system resolves conflicts
- Easy to add/remove schedules

---

## API Documentation

The HeatTrax Scheduler provides a JSON REST API for monitoring and configuration.

### Base URL

```
http://localhost:4328
```

**Note:** Default is localhost (127.0.0.1). Configure via `web.bind_host` and `web.port` in config.yaml.

### Authentication

**Desktop Dashboard:** ❌ No authentication required

Most API endpoints, including schedule management, do not require authentication. The desktop dashboard (`/`, `/ui`) and most API endpoints are accessible without authentication.

**Mobile Control:** ✅ PIN authentication required

Mobile control routes (`/control` page and `/api/mat/*` endpoints) require PIN authentication via session cookie:

**Protected endpoints:**
- `GET /api/mat/status` - Get mat status for all groups
- `POST /api/mat/control` - Control group with timeout
- `POST /api/mat/reset-auto` - Clear manual override

**Authentication flow:**
1. User visits `/control/login`
2. User submits PIN via `POST /api/auth/login`
3. Server creates session cookie (24-hour lifetime)
4. Session cookie is used for subsequent requests to protected endpoints

**Configure PIN:**
- `config.yaml`: `web.pin`
- Environment variable: `HEATTRAX_WEB_PIN`

**Security recommendations:**
- Bind to `127.0.0.1` (localhost only) for maximum security
- Do not expose to the internet without a reverse proxy
- Use firewall rules to restrict access

**See also:** Complete API documentation in **[API Reference](docs/API_REFERENCE.md)**

### Endpoints

#### `GET /api/health`

**Description:** Basic application health check

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

#### `GET /api/ping`

**Description:** Simple liveness check

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

#### `GET /api/status`

**Description:** Get system status including device states, weather, and scheduler status

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
    "driveway_heating": {
      "enabled": true,
      "state": "on",
      "active_schedule": "Morning Black Ice",
      "runtime_hours": 1.5,
      "devices": [
        {
          "name": "Driveway Mat",
          "state": "on",
          "online": true
        }
      ]
    }
  },
  "weather": {
    "status": "online",
    "temperature_f": 28,
    "precipitation_active": false,
    "forecast": "Clear skies"
  }
}
```

#### `GET /api/config`

**Description:** Get current configuration with source metadata

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
      "source": "yaml",
      "readonly": false
    },
    "longitude": {
      "value": -74.0060,
      "source": "yaml",
      "readonly": false
    },
    "timezone": {
      "value": "America/New_York",
      "source": "env",
      "env_var": "HEATTRAX_TIMEZONE",
      "readonly": true
    }
  },
  "devices": {
    "credentials": {
      "username": {
        "value": "user@example.com",
        "source": "env",
        "env_var": "HEATTRAX_TAPO_USERNAME",
        "readonly": true
      }
    },
    "groups": {
      "value": { ... },
      "source": "yaml",
      "readonly": false
    }
  }
}
```

**Fields:**
- `value`: The actual configuration value
- `source`: `"yaml"` (from config file) or `"env"` (from environment variable)
- `readonly`: `true` if controlled by environment variable
- `env_var`: Name of the environment variable (if source is "env")

#### `POST /api/config`

**Description:** Update configuration (YAML values only, not env vars)

**Request:**
```bash
curl -X POST http://localhost:4328/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "vacation_mode": false
  }'
```

**Response (200 OK):**
```json
{
  "message": "Configuration updated successfully",
  "restart_required": true
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Invalid configuration",
  "details": [
    "Schedule 0: Invalid time format '25:00'"
  ]
}
```

#### `GET /api/devices/status`

**Description:** Get detailed device and outlet states

**Request:**
```bash
curl http://localhost:4328/api/devices/status
```

**Response (200 OK):**
```json
{
  "groups": {
    "driveway_heating": {
      "devices": [
        {
          "name": "Driveway Mat",
          "ip_address": "192.168.1.100",
          "online": true,
          "state": "on",
          "outlets": [
            {
              "index": 0,
              "alias": "Outlet 1",
              "state": "on"
            },
            {
              "index": 1,
              "alias": "Outlet 2",
              "state": "on"
            }
          ]
        }
      ]
    }
  }
}
```

#### `POST /api/devices/control`

**Description:** Manually control devices or outlets

**Request (Control Entire Device):**
```bash
curl -X POST http://localhost:4328/api/devices/control \
  -H "Content-Type: application/json" \
  -d '{
    "group": "driveway_heating",
    "device": "Driveway Mat",
    "action": "on"
  }'
```

**Request (Control Specific Outlet):**
```bash
curl -X POST http://localhost:4328/api/devices/control \
  -H "Content-Type: application/json" \
  -d '{
    "group": "driveway_heating",
    "device": "Driveway Mat",
    "outlet": 0,
    "action": "off"
  }'
```

**Response (200 OK):**
```json
{
  "message": "Device 'Driveway Mat' turned on successfully"
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Invalid action",
  "details": "Action must be 'on' or 'off'"
}
```

#### `GET /api/groups/{group}/automation`

**Description:** Get automation configuration for a group

**Request:**
```bash
curl http://localhost:4328/api/groups/driveway_heating/automation
```

**Response (200 OK):**
```json
{
  "group": "driveway_heating",
  "enabled": true,
  "schedules": [
    {
      "name": "Morning Black Ice",
      "enabled": true,
      "priority": "critical",
      "days": [1, 2, 3, 4, 5]
    }
  ]
}
```

#### `PATCH /api/groups/{group}/automation`

**Description:** Update automation overrides for a group

**Request:**
```bash
curl -X PATCH http://localhost:4328/api/groups/driveway_heating/automation \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

**Response (200 OK):**
```json
{
  "message": "Automation overrides updated for group 'driveway_heating'",
  "overrides": {
    "enabled": false
  }
}
```

#### `GET /api/groups/{group}/schedules`

**Description:** Get all schedules for a group

**Request:**
```bash
curl http://localhost:4328/api/groups/driveway_heating/schedules
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "group": "driveway_heating",
  "schedules": [
    {
      "index": 0,
      "name": "Morning Black Ice",
      "enabled": true,
      "type": "time",
      "on_time": "06:00",
      "off_time": "09:00",
      "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "conditions": {
        "temperature_max_f": 32.0
      },
      "priority": "critical"
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

#### `POST /api/groups/{group}/schedules`

**Description:** Add a new schedule to a group

**Request:**
```bash
curl -X POST http://localhost:4328/api/groups/driveway_heating/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekend Warming",
    "enabled": true,
    "type": "time",
    "on_time": "07:00",
    "off_time": "11:00",
    "days": ["Saturday", "Sunday"]
  }'
```

**Response (201 Created):**
```json
{
  "status": "ok",
  "message": "Schedule added successfully",
  "schedule_index": 2
}
```

#### `GET /api/groups/{group}/schedules/{index}`

**Description:** Get a specific schedule by index

**Request:**
```bash
curl http://localhost:4328/api/groups/driveway_heating/schedules/0
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "schedule": {
    "index": 0,
    "name": "Morning Black Ice",
    "enabled": true,
    "type": "time",
    "on_time": "06:00",
    "off_time": "09:00",
    "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "conditions": {
      "temperature_max_f": 32.0
    },
    "priority": "critical"
  }
}
```

#### `PUT /api/groups/{group}/schedules/{index}`

**Description:** Update a specific schedule

**Request:**
```bash
curl -X PUT http://localhost:4328/api/groups/driveway_heating/schedules/0 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Morning Black Ice",
    "enabled": true,
    "type": "time",
    "on_time": "05:30",
    "off_time": "09:30",
    "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "conditions": {
      "temperature_max_f": 32.0
    }
  }'
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Schedule updated successfully"
}
```

#### `DELETE /api/groups/{group}/schedules/{index}`

**Description:** Delete a specific schedule

**Request:**
```bash
curl -X DELETE http://localhost:4328/api/groups/driveway_heating/schedules/2
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Schedule deleted successfully"
}
```

#### `PUT /api/groups/{group}/schedules/{index}/enabled`

**Description:** Toggle a schedule enabled/disabled status

**Request:**
```bash
curl -X PUT http://localhost:4328/api/groups/driveway_heating/schedules/0/enabled \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": false
  }'
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Schedule disabled successfully"
}
```

#### `GET /api/weather/forecast`

**Description:** Get cached weather forecast data with black ice detection

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
    }
  ]
}
```

#### `GET /api/weather/mat-forecast`

**Description:** Get predicted mat ON/OFF windows per group over forecast horizon

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
    "driveway_heating": {
      "windows": [
        {
          "start": "2025-11-23T18:00:00",
          "end": "2025-11-24T09:00:00",
          "reason": "Temperature below 32°F threshold"
        }
      ]
    }
  }
}
```

#### `GET /api/vacation_mode`

**Description:** Get current vacation mode status

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

#### `PUT /api/vacation_mode`

**Description:** Set vacation mode status (persists to config.yaml)

**Request:**
```bash
curl -X PUT http://localhost:4328/api/vacation_mode \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true
  }'
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Vacation mode enabled",
  "vacation_mode": true
}
```

#### `GET /api/config/download`

**Description:** Download the current config.yaml file

**Request:**
```bash
curl http://localhost:4328/api/config/download -o config.yaml
```

**Response (200 OK):**
- Content-Type: `application/x-yaml`
- Content-Disposition: `attachment; filename=config.yaml`
- Body: YAML file contents

#### `POST /api/config/upload`

**Description:** Upload and validate a new config.yaml file (creates backup before applying)

**Request:**
```bash
curl -X POST http://localhost:4328/api/config/upload \
  -F "file=@config.yaml"
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Configuration uploaded and validated successfully. Backup created at config.yaml.backup"
}
```

#### `POST /api/restart`

**Description:** Trigger application restart (requires Docker restart policy)

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

#### Mobile Control Endpoints (PIN-protected)

These endpoints require PIN authentication via session cookie. See [Authentication](#authentication) section.

##### `POST /api/auth/login`

**Description:** Authenticate with PIN (creates 24-hour session)

**Authentication:** ❌ Not required (this is the login endpoint)

**Request:**
```bash
curl -X POST http://localhost:4328/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "pin": "1234"
  }'
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

##### `GET /api/mat/status`

**Description:** Get mat status for all groups

**Authentication:** ✅ Required (PIN session)

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
        "expires_at": "2025-11-23T18:30:00"
      }
    }
  }
}
```

##### `POST /api/mat/control`

**Description:** Control a group with optional timeout (sets manual override)

**Authentication:** ✅ Required (PIN session)

**Request:**
```bash
curl -X POST http://localhost:4328/api/mat/control \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<session_cookie>" \
  -d '{
    "group": "heated_mats",
    "action": "on",
    "timeout_hours": 3
  }'
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Group 'heated_mats' turned on. Manual override set for 3 hours.",
  "expires_at": "2025-11-23T18:30:00"
}
```

##### `POST /api/mat/reset-auto`

**Description:** Clear manual override and resume automatic control

**Authentication:** ✅ Required (PIN session)

**Request:**
```bash
curl -X POST http://localhost:4328/api/mat/reset-auto \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<session_cookie>" \
  -d '{
    "group": "heated_mats"
  }'
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "message": "Manual override cleared for 'heated_mats'. Scheduler will resume automatic control."
}
```

#### Notification Endpoints

##### `GET /api/notifications/status`

**Description:** Get notification provider health status

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
    }
  }
}
```

##### `POST /api/notifications/test`

**Description:** Queue a test notification (non-blocking, returns 202 Accepted)

**Request:**
```bash
curl -X POST http://localhost:4328/api/notifications/test \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Test Notification",
    "body": "This is a test"
  }'
```

**Response (202 Accepted):**
```json
{
  "status": "queued",
  "message": "Test notification queued for processing"
}
```

---

**For complete API documentation including all endpoints, request/response examples, and authentication details, see the [API Reference](docs/API_REFERENCE.md).**

---

### Error Codes

| HTTP Code | Meaning                     | Common Causes                          |
|-----------|-----------------------------|----------------------------------------|
| 200       | Success                     | Request completed successfully         |
| 400       | Bad Request                 | Invalid JSON, missing fields, validation errors |
| 404       | Not Found                   | Invalid endpoint or group name         |
| 500       | Internal Server Error       | Server error, check logs               |

### Example JavaScript Fetch Calls

#### Get System Status

```javascript
fetch('http://localhost:4328/api/status')
  .then(response => response.json())
  .then(data => {
    console.log('System status:', data);
    console.log('Temperature:', data.weather.temperature_f);
  })
  .catch(error => console.error('Error:', error));
```

#### Update Configuration

```javascript
const config = {
  vacation_mode: true
};

fetch('http://localhost:4328/api/config', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(config)
})
  .then(response => response.json())
  .then(data => {
    console.log('Config updated:', data.message);
  })
  .catch(error => console.error('Error:', error));
```

#### Control Device

```javascript
const controlCommand = {
  group: 'driveway_heating',
  device: 'Driveway Mat',
  action: 'on'
};

fetch('http://localhost:4328/api/devices/control', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(controlCommand)
})
  .then(response => response.json())
  .then(data => {
    console.log('Device controlled:', data.message);
  })
  .catch(error => console.error('Error:', error));
```

---

## Troubleshooting

### Schedule Not Activating

**Symptom:** Schedule is configured but device doesn't turn on

**Checklist:**

1. **Is the schedule enabled?**
   ```yaml
   enabled: true  # Must be true
   ```

2. **Is the group enabled?**
   ```yaml
   driveway_heating:
     enabled: true  # Must be true
   ```

3. **Is today in the schedule's days list?**
   ```yaml
   days: [1, 2, 3, 4, 5]  # Check if today's day number is included
   ```

4. **Is the current time within the schedule window?**
   - Check scheduler logs for "Schedule 'X' not in time range"
   - Verify timezone is configured correctly

5. **Are weather conditions met?**
   - If schedule has `conditions`, check weather service status
   - Verify temperature and precipitation match requirements
   - Check logs for "conditions not met"

6. **Is weather service online?**
   - Schedules with conditions are skipped if weather is offline
   - Check `/api/status` for weather status
   - View logs for "weather is OFFLINE"

7. **Is vacation mode enabled?**
   ```yaml
   vacation_mode: false  # Must be false for schedules to work
   ```

**Debugging Commands:**

```bash
# Check scheduler logs
docker-compose logs -f | grep -i schedule

# Check API status
curl http://localhost:4328/api/status | jq .

# Check weather status
curl http://localhost:4328/api/status | jq .weather
```

### Solar Times Not Updating

**Symptom:** Sunrise/sunset schedules use fallback times instead of calculated times

**Checklist:**

1. **Is location configured correctly?**
   ```yaml
   location:
     latitude: 40.7128    # Must be valid
     longitude: -74.0060  # Must be valid
     timezone: "America/New_York"  # Must be valid IANA timezone
   ```

2. **Check logs for solar calculation errors:**
   ```bash
   docker-compose logs | grep -i solar
   ```

3. **Verify fallback times are reasonable:**
   ```yaml
   on:
     type: "sunrise"
     offset: -30
     fallback: "06:00"  # Used if calculation fails
   ```

4. **Restart scheduler to recalculate:**
   ```bash
   docker-compose restart
   ```

**Common Causes:**
- Invalid latitude/longitude
- Polar regions (no sunrise/sunset in winter/summer)
- Timezone mismatch
- Date/time issues on host system

### Condition Evaluation Issues

**Symptom:** Schedule doesn't activate even though conditions seem met

**Debugging Steps:**

1. **Check weather data availability:**
   ```bash
   curl http://localhost:4328/api/status | jq .weather
   ```

2. **Verify condition syntax:**
   ```yaml
   conditions:
     temperature_max: 32          # Number, not string
     precipitation_active: true   # Boolean, not string
   ```

3. **Check scheduler logs for condition evaluation:**
   ```bash
   docker-compose logs | grep -i "condition"
   ```

4. **Common Issues:**
   - Weather service offline → schedules with conditions are skipped
   - Temperature units (Fahrenheit, not Celsius)
   - Precipitation not detected yet (lead time needed)

### Configuration Validation Errors

**Symptom:** Configuration rejected by API or fails to load

**Common Errors:**

#### Invalid Time Format

```yaml
# ❌ Wrong
on:
  type: "time"
  value: "6:00"    # Missing leading zero

# ✅ Correct
on:
  type: "time"
  value: "06:00"   # Must be HH:MM
```

#### Invalid Day Numbers

```yaml
# ❌ Wrong
days: [0, 1, 2]    # 0 is not valid

# ✅ Correct
days: [1, 2, 3]    # 1=Monday, 7=Sunday
```

#### Missing Required Fields

```yaml
# ❌ Wrong
schedules:
  - name: "Test"
    on:
      type: "time"
      value: "06:00"
    # Missing 'off' field

# ✅ Correct
schedules:
  - name: "Test"
    on:
      type: "time"
      value: "06:00"
    off:
      type: "time"
      value: "22:00"
```

#### Invalid Offset Range

```yaml
# ❌ Wrong
on:
  type: "sunrise"
  offset: 200    # Must be -180 to +180

# ✅ Correct
on:
  type: "sunrise"
  offset: 30     # Minutes within range
```

### Migration Problems

**Symptom:** Old configuration doesn't work after upgrade

**Solutions:**

1. **Check for legacy format:**
   ```yaml
   # ❌ Legacy format (no longer supported)
   device:
     ip_address: "192.168.1.100"
   ```

2. **Migrate to new format:**
   - See [Migration Examples](#migration-examples)
   - Use multi-device groups structure
   - Convert old schedules to new format

3. **Validate configuration via Web UI:**
   - Use the Web UI configuration editor at `http://localhost:4328`
   - The editor provides real-time validation
   - Test changes before saving
   
   Or use the API to check for errors:
   ```bash
   # POST new config and check response for validation errors
   curl -X POST http://localhost:4328/api/config \
     -H "Content-Type: application/json" \
     -d @new_config.json
   # Returns validation errors if invalid (400 Bad Request)
   ```

4. **Start fresh if needed:**
   ```bash
   # Backup old config
   cp config.yaml config.yaml.backup
   
   # Copy example
   cp config.example.yaml config.yaml
   
   # Edit new config with your settings
   ```

### Logs and Debugging

**View Logs:**
```bash
# Docker
docker-compose logs -f

# Specific component
docker-compose logs -f | grep -i scheduler
docker-compose logs -f | grep -i weather

# File logs
tail -f logs/heattrax_scheduler.log
```

**Enable Debug Logging:**
```yaml
logging:
  level: "DEBUG"  # More verbose output
```

Or via environment variable:
```bash
HEATTRAX_LOG_LEVEL=DEBUG
```

---

## Best Practices

### How to Organize Schedule Groups

#### Group by Function

```yaml
devices:
  groups:
    heating:          # All heating devices
      items: [...]
      schedules: [...]
    
    lighting:         # All lighting devices
      items: [...]
      schedules: [...]
    
    decorations:      # Seasonal decorations
      items: [...]
      schedules: [...]
```

**Benefits:**
- Clear organization
- Easy to enable/disable entire categories
- Separate automation rules per function

#### Group by Location

```yaml
devices:
  groups:
    driveway:         # Driveway devices
      items: [...]
    
    walkway:          # Walkway devices
      items: [...]
    
    garage:           # Garage devices
      items: [...]
```

**Benefits:**
- Geographical organization
- Different schedules per location
- Easy to identify device placement

#### Group by Schedule Pattern

```yaml
devices:
  groups:
    weather_dependent:    # Weather-based automation
      items: [...]
      schedules: [...]    # With conditions
    
    time_based:           # Fixed time automation
      items: [...]
      schedules: [...]    # No conditions
```

**Benefits:**
- Clear separation of automation types
- Easy to troubleshoot
- Different behaviors per group

### Setting Appropriate Priorities

#### Use `critical` for Safety

```yaml
- name: "Driveway Ice Prevention"
  priority: "critical"    # Safety first
  conditions:
    temperature_max: 32
```

**When to use:**
- Heating for safety (ice/snow)
- Essential functions
- Overrides other schedules

#### Use `normal` for Standard Automation

```yaml
- name: "Evening Lights"
  priority: "normal"      # Default priority
```

**When to use:**
- Most schedules
- Standard automation
- No special precedence needed

#### Use `low` for Optional Features

```yaml
- name: "Holiday Decorations"
  priority: "low"         # Can be overridden
```

**When to use:**
- Decorative features
- Non-essential automation
- Can yield to higher priorities

### Testing New Schedules

#### 1. Test in Isolation

Create a test group with short time windows:

```yaml
groups:
  test_schedule:
    enabled: true
    items:
      - name: "Test Device"
        ip_address: "192.168.1.200"
    schedules:
      - name: "Test Run"
        enabled: true
        priority: "normal"
        days: [1, 2, 3, 4, 5, 6, 7]
        on:
          type: "time"
          value: "15:00"     # Current time + few minutes
        off:
          type: "time"
          value: "15:05"     # Short window
```

**Watch logs:**
```bash
docker-compose logs -f | grep -i "test"
```

#### 2. Test Conditions Separately

Test weather conditions with relaxed thresholds:

```yaml
- name: "Condition Test"
  enabled: true
  priority: "normal"
  days: [1, 2, 3, 4, 5, 6, 7]
  on:
    type: "time"
    value: "14:00"
  off:
    type: "time"
    value: "14:05"
  conditions:
    temperature_max: 80   # High threshold = easier to trigger
```

#### 3. Use API to Monitor

```bash
# Watch status during test
watch -n 5 'curl -s http://localhost:4328/api/status | jq .'
```

#### 4. Gradually Add Complexity

1. Start with simple time-based schedule
2. Add day filtering
3. Add weather conditions
4. Add priority handling
5. Test interactions with other schedules

### Backup and Restore Procedures

#### Backup Configuration

```bash
# Backup config file
cp config.yaml config.yaml.backup.$(date +%Y%m%d)

# Backup entire state directory
tar -czf state_backup_$(date +%Y%m%d).tar.gz state/

# Backup via API
curl http://localhost:4328/api/config > config_backup.json
```

#### Restore Configuration

```bash
# Restore from file backup
cp config.yaml.backup.20251123 config.yaml
docker-compose restart

# Restore state
tar -xzf state_backup_20251123.tar.gz

# Restore via API
curl -X POST http://localhost:4328/api/config \
  -H "Content-Type: application/json" \
  -d @config_backup.json
```

#### Version Control

```bash
# Initialize git repo for config
cd /path/to/heattrax
git init
git add config.yaml
git commit -m "Initial configuration"

# Track changes
git add config.yaml
git commit -m "Added weekend schedules"
```

### Performance Considerations

#### Schedule Evaluation Frequency

The scheduler checks conditions every N minutes (default: 10):

```yaml
scheduler:
  check_interval_minutes: 10  # Balance between responsiveness and load
```

**Guidelines:**
- **10 minutes:** Good balance (default)
- **5 minutes:** More responsive, slightly higher CPU
- **15-30 minutes:** Lower load, less responsive

#### Number of Schedules

**Recommended:**
- 1-5 schedules per group: Excellent performance
- 5-10 schedules per group: Good performance
- 10+ schedules per group: Consider splitting into multiple groups

**Impact:**
- Each schedule is evaluated every check interval
- Conditions add weather API calls
- Solar calculations are cached per day

#### Weather API Calls

Weather data is cached to reduce API calls:

```yaml
weather_api:
  resilience:
    refresh_interval_minutes: 10   # How often to fetch fresh data
    cache_valid_hours: 6           # How long cache is trusted
```

**Best Practices:**
- Use default intervals (10 minutes)
- Don't set too low (avoid rate limiting)
- Cache handles offline periods automatically

#### Device Communication

**Optimize device operations:**
- Group devices by location (reduces broadcasts)
- Use static IP addresses (faster than discovery)
- Increase timeout for slow networks:
  ```yaml
  items:
    - name: "Device"
      ip_address: "192.168.1.100"
      discovery_timeout_seconds: 60  # Increase if needed
  ```

#### Log File Management

Prevent log file bloat:

```yaml
logging:
  level: "INFO"           # Use INFO, not DEBUG in production
  max_file_size_mb: 10    # Rotate at 10 MB
  backup_count: 5         # Keep 5 backups
```

**Clean up old logs:**
```bash
# Remove logs older than 30 days
find logs/ -name "*.log*" -mtime +30 -delete
```

---

## Additional Resources

- **[Main README](README.md)** - Installation and setup
- **[Quick Start Guide](docs/QUICKSTART.md)** - 5-minute setup
- **[Web UI Guide](docs/WEB_UI_GUIDE.md)** - Web interface documentation
- **[Health Check Guide](docs/HEALTH_CHECK.md)** - Device monitoring
- **[Logging Guide](docs/LOGGING.md)** - Troubleshooting with logs
- **[Environment Variables Reference](docs/ENVIRONMENT_VARIABLES.md)** - Complete variable list
- **[Changelog](docs/CHANGELOG.md)** - Version history

---

## Feedback and Support

Found an issue or have a suggestion? Please open an issue on GitHub:
https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler/issues

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

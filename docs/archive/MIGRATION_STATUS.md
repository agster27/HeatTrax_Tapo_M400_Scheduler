# Unified Scheduling System - Migration Status

> ⚠️ **Archived Document** — This document was the migration tracking file for the unified scheduling system migration (v1.0). All phases listed here (1-6) are now complete. This file is preserved for historical reference only. For the current refactoring plan, see [REFACTOR.md](../../REFACTOR.md).

## Overview
This document tracks the implementation status of the unified conditional scheduling system that replaces separate automation toggles with a flexible, schedule-based approach.

## ✅ Completed Components

### Phase 1: Core Infrastructure ✅
- **Solar Calculator** (`src/scheduler/solar_calculator.py`)
  - Calculates sunrise/sunset times for any date
  - Supports offset adjustments (e.g., 30 minutes before sunset)
  - Includes fallback times for calculation failures
  - Caches daily calculations for performance

- **Schedule Types** (`src/scheduler/schedule_types.py`)
  - Comprehensive schedule data structures
  - Support for time, sunrise, sunset, and duration-based schedules
  - Priority system (critical, normal, low)
  - Weather condition support (temperature, precipitation)
  - Per-schedule safety limits
  - Full validation logic

- **Schedule Evaluator** (`src/scheduler/schedule_evaluator.py`)
  - Evaluates schedules to determine on/off state
  - Handles weather condition checking
  - Weather offline state detection
  - Priority-based conflict resolution
  - Day-of-week filtering

- **Weather Service Enhancements**
  - Added `is_offline()` method (>12 hours cache age)
  - Added `get_cache_age_hours()` method
  - Exposed weather state for schedule evaluation

- **Config Schema Updates**
  - New `vacation_mode` global setting
  - New `schedules` array per device group
  - Updated `config.example.yaml` with comprehensive examples
  - Environment variable support for vacation mode
  - Removed requirement for `thresholds` section (now optional for legacy)

### Phase 2: Scheduler Integration ✅
- **Unified Scheduling Logic**
  - Initialized solar calculator in scheduler
  - Initialized schedule evaluator in scheduler
  - Parse and store schedules from config per group
  - Vacation mode checking in initialization

- **Refactored Decision Methods**
  - `should_turn_on_group()` now uses unified schedule evaluation
  - `should_turn_off_group()` now uses unified schedule evaluation
  - Weather condition gathering for schedule evaluation
  - Per-schedule max runtime and cooldown handling

- **Backward Compatibility**
  - Legacy automation format still supported
  - Separate `_should_turn_on_legacy()` method
  - Separate `_should_turn_off_legacy()` method
  - Graceful handling of missing thresholds/morning_mode config
  - Automatic detection of old vs new format

### Phase 3: Web API ✅
- **Schedule Management Endpoints**
  - `GET /api/groups/{group_name}/schedules` - List all schedules
  - `POST /api/groups/{group_name}/schedules` - Add new schedule
  - `GET /api/groups/{group_name}/schedules/{index}` - Get specific schedule
  - `PUT /api/groups/{group_name}/schedules/{index}` - Update schedule
  - `DELETE /api/groups/{group_name}/schedules/{index}` - Delete schedule
  - `PUT /api/groups/{group_name}/schedules/{index}/enabled` - Toggle enabled

- **Vacation Mode Endpoints**
  - `GET /api/vacation_mode` - Get current vacation mode status
  - `PUT /api/vacation_mode` - Set vacation mode on/off

- **Solar Time Endpoint**
  - `GET /api/solar_times` - Get today's sunrise/sunset times

- **Status Enhancements**
  - Added `vacation_mode` to status response
  - Added `weather_offline` to status response
  - Added `weather_cache_age_hours` to status response

## 🚧 Remaining Work

### Phase 4: Web UI (Not Started)
The Web UI needs to be completely updated to support the new scheduling system:

- [ ] Add vacation mode toggle to page header
- [ ] Remove old automation toggles UI
- [ ] Create schedule list/cards component
- [ ] Create add/edit schedule modal with:
  - Schedule name input
  - Priority selector
  - Days of week checkboxes
  - On time configuration (type, value, offset, fallback)
  - Off time configuration (type, value, offset, fallback, duration)
  - Conditions section (temperature, precipitation)
  - Safety limits section (max runtime, cooldown)
- [ ] Add sunrise/sunset icons for solar-based schedules
- [ ] Update status display to show schedule reasons
- [ ] Add schedule priority badges
- [ ] Implement schedule drag-and-drop reordering (optional)

### Phase 5: Cleanup & Documentation
- [ ] Create `docs/SCHEDULING.md` with comprehensive guide
- [ ] Update `README.md` with new scheduling features
- [ ] Update `docs/SETUP.md` with configuration examples
- [ ] Update `docs/MANUAL_CONTROL.md` for vacation mode
- [ ] Update `docs/HEALTH_CHECK.md` for new expectations
- [ ] Add migration guide for users transitioning from old format
- [ ] Consider deprecation timeline for old automation format

### Phase 6: Testing
- [ ] Write unit tests for `SolarCalculator`
- [ ] Write unit tests for `Schedule` validation
- [ ] Write unit tests for `ScheduleEvaluator`
- [ ] Write integration tests for unified scheduling
- [ ] Test vacation mode functionality
- [ ] Test weather OFFLINE state handling
- [ ] Test multiple schedules per group
- [ ] Test priority conflict resolution
- [ ] Test solar time calculations for various locations
- [ ] Run existing test suite to ensure no regressions

## Key Features Implemented

### Multiple Schedules Per Group
Each device group can now have multiple schedules that work together. If ANY schedule says ON (and conditions are met), the device turns ON.

Example:
```yaml
schedules:
  - name: "Morning Black Ice"
    enabled: true
    priority: "critical"
    days: [1,2,3,4,5]  # Weekdays only
    on: {type: "time", value: "06:00"}
    off: {type: "sunrise", offset: 30, fallback: "08:00"}
    conditions: {temperature_max: 32}
  
  - name: "All Day Storm"
    enabled: true
    priority: "critical"
    days: [1,2,3,4,5,6,7]  # Every day
    on: {type: "time", value: "00:00"}
    off: {type: "time", value: "23:59"}
    conditions: {temperature_max: 32, precipitation_active: true}
```

### Solar-Based Scheduling
Schedules can use sunrise/sunset with offsets:
```yaml
on: {type: "sunset", offset: -30, fallback: "17:00"}  # 30 min before sunset
off: {type: "sunrise", offset: 60, fallback: "08:00"}  # 1 hour after sunrise
```

### Weather Conditions
Schedules can require specific weather conditions:
```yaml
conditions:
  temperature_max: 32  # Only run if temp <= 32°F
  precipitation_active: true  # Only run when precipitation detected
```

### Weather Offline Handling
When weather service is OFFLINE (cache > 12 hours), schedules with weather conditions are automatically skipped, falling back to time-based schedules only.

### Vacation Mode
Global setting that disables ALL schedules and turns devices OFF. Manual control still works.

### Priority System
- **critical**: Safety/heating schedules (highest priority)
- **normal**: Standard automation
- **low**: Nice-to-have automation

When multiple schedules are active, the highest priority wins.

### Per-Schedule Safety Limits
Each schedule can override global safety limits:
```yaml
safety:
  max_runtime_hours: 3  # Override global 6 hours
  cooldown_minutes: 30  # Override global cooldown
```

## Backward Compatibility

The system maintains full backward compatibility with the old automation format:
- Old `automation` block still works
- Old `schedule` field still works
- Old `thresholds` and `morning_mode` config still supported
- Automatic detection of format (old vs new)

Users can migrate at their own pace.

## Testing the Implementation

### Test Schedule API
```bash
# Get schedules for a group
curl http://localhost:4328/api/groups/driveway_heating/schedules

# Add a new schedule
curl -X POST http://localhost:4328/api/groups/driveway_heating/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Schedule",
    "enabled": true,
    "priority": "normal",
    "days": [1,2,3,4,5],
    "on": {"type": "time", "value": "06:00"},
    "off": {"type": "time", "value": "08:00"}
  }'

# Update schedule
curl -X PUT http://localhost:4328/api/groups/driveway_heating/schedules/0 \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated", "enabled": false, ...}'

# Delete schedule
curl -X DELETE http://localhost:4328/api/groups/driveway_heating/schedules/0
```

### Test Vacation Mode
```bash
# Get vacation mode status
curl http://localhost:4328/api/vacation_mode

# Enable vacation mode
curl -X PUT http://localhost:4328/api/vacation_mode \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

### Test Solar Times
```bash
# Get today's sunrise/sunset
curl http://localhost:4328/api/solar_times
```

## Next Steps

1. **Web UI Implementation** - This is the biggest remaining piece. The UI needs to:
   - Display schedules in a user-friendly format
   - Allow adding/editing/deleting schedules
   - Show vacation mode status
   - Display solar times for reference

2. **Documentation** - Create comprehensive guides for:
   - Migrating from old format
   - Creating schedules
   - Using solar-based scheduling
   - Understanding priorities
   - Weather condition logic

3. **Testing** - Comprehensive test coverage for:
   - Solar calculations
   - Schedule evaluation
   - Weather offline handling
   - Priority resolution
   - Edge cases (day boundaries, etc.)

## Breaking Changes (for future major version)

Eventually, we may want to:
- Remove support for old automation format
- Remove `thresholds` config section entirely
- Remove `morning_mode` config section entirely
- Make `schedules` the only way to configure automation

But for now, backward compatibility is maintained to avoid breaking existing deployments.

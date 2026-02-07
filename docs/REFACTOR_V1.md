# HeatTrax v1.0 Refactoring Summary

> This document summarizes the v1.0 refactoring effort (unified scheduling system migration). For the current v2.0 refactoring plan, see [REFACTOR.md](../REFACTOR.md).

## Overview

The v1.0 refactoring effort replaced separate automation toggles with a unified, schedule-based approach. This migration introduced a flexible conditional scheduling system that allows multiple schedules per device group, solar-based timing, weather conditions, and priority-based conflict resolution.

The key change was moving from simple on/off automation toggles (`automation.weather_control`, `automation.morning_mode`, etc.) to a comprehensive scheduling system where each device group can have multiple schedules with:
- Solar-based timing (sunrise/sunset with offsets)
- Weather condition requirements (temperature, precipitation)
- Priority levels (critical, normal, low)
- Per-schedule safety limits
- Day-of-week filtering

## What Changed

### Core Infrastructure

**Solar Calculator** (`src/scheduler/solar_calculator.py`):
- Calculates sunrise/sunset times for any date
- Supports offset adjustments (e.g., 30 minutes before sunset)
- Includes fallback times for calculation failures
- Caches daily calculations for performance

**Schedule Types** (`src/scheduler/schedule_types.py`):
- Comprehensive schedule data structures
- Support for time, sunrise, sunset, and duration-based schedules
- Priority system (critical, normal, low)
- Weather condition support (temperature, precipitation)
- Per-schedule safety limits
- Full validation logic

**Schedule Evaluator** (`src/scheduler/schedule_evaluator.py`):
- Evaluates schedules to determine on/off state
- Handles weather condition checking
- Weather offline state detection
- Priority-based conflict resolution
- Day-of-week filtering

### Scheduler Integration

**Unified Scheduling Logic**:
- `should_turn_on_group()` now uses unified schedule evaluation
- `should_turn_off_group()` now uses unified schedule evaluation
- Weather condition gathering for schedule evaluation
- Per-schedule max runtime and cooldown handling
- Vacation mode checking (global override to turn everything OFF)

### Web API

**Schedule Management Endpoints**:
- `GET /api/groups/{group_name}/schedules` — List all schedules
- `POST /api/groups/{group_name}/schedules` — Add new schedule
- `GET /api/groups/{group_name}/schedules/{index}` — Get specific schedule
- `PUT /api/groups/{group_name}/schedules/{index}` — Update schedule
- `DELETE /api/groups/{group_name}/schedules/{index}` — Delete schedule
- `PUT /api/groups/{group_name}/schedules/{index}/enabled` — Toggle enabled

**Vacation Mode Endpoints**:
- `GET /api/vacation_mode` — Get current vacation mode status
- `PUT /api/vacation_mode` — Set vacation mode on/off

**Solar Time Endpoint**:
- `GET /api/solar_times` — Get today's sunrise/sunset times

**Status Enhancements**:
- Added `vacation_mode` to status response
- Added `weather_offline` to status response
- Added `weather_cache_age_hours` to status response

### Web UI

The Web UI was completely updated to support the new scheduling system:
- Vacation mode toggle in page header
- Schedule list/cards component
- Add/edit schedule modal with full configuration options
- Sunrise/sunset icons for solar-based schedules
- Schedule priority badges
- Updated status display showing schedule reasons

### Documentation

**SCHEDULING.md**:
- Comprehensive guide to the scheduling system
- Examples of all schedule types
- Weather condition usage
- Priority system explanation
- Migration guide from legacy format

**Updated Guides**:
- `README.md` — New scheduling features
- `docs/SETUP.md` — Configuration examples
- `docs/MANUAL_CONTROL.md` — Vacation mode
- `docs/API_REFERENCE.md` — New API endpoints

### Testing

Comprehensive test suite with 150+ tests:
- Unit tests for `SolarCalculator`
- Unit tests for `Schedule` validation
- Unit tests for `ScheduleEvaluator`
- Integration tests for unified scheduling
- Vacation mode functionality tests
- Weather OFFLINE state handling tests
- Multiple schedules per group tests
- Priority conflict resolution tests
- Solar time calculations for various locations

## Backward Compatibility

The v1.0 refactor maintained full backward compatibility with the legacy automation format:
- Old `automation` block still works
- Old `schedule` field still works
- Old `thresholds` and `morning_mode` config still supported
- Automatic detection of format (old vs new)
- Users can migrate at their own pace

## Legacy Code

Legacy automation methods and configuration keys remain in the codebase for backward compatibility:

**Legacy Methods**:
- `_should_turn_on_legacy()` — Legacy automation on logic
- `_should_turn_off_legacy()` — Legacy automation off logic

**Legacy Config Keys** (still supported but deprecated):
- `automation.weather_control` — Old weather-based automation toggle
- `automation.morning_mode` — Old morning heating toggle
- `thresholds.temp_threshold` — Old temperature threshold
- `thresholds.cold_threshold` — Old cold threshold
- `morning_mode.start_time` — Old morning start time
- `morning_mode.end_time` — Old morning end time

These legacy features are deprecated and planned for removal in a future version. See [REFACTOR.md](../REFACTOR.md) Phase 1 for the planned removal timeline and migration path.

## Next Steps

For the current v2.0 refactoring plan, which focuses on code simplification, UI unification, and removing legacy code paths, see [REFACTOR.md](../REFACTOR.md).

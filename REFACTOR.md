# HeatTrax v2.0 Refactoring Plan

> 📋 **Living Document** — This document serves as the single source of truth for the v2.0 refactoring effort. It defines what can and cannot change during the refactor.

## Overview

This refactor aims to simplify the codebase for easier editing, unify the mobile and desktop UI into a cohesive experience (simple mobile view + feature-rich desktop view), and improve maintainability — all while preserving existing application logic and behavior.

## Objectives

1. **Code Simplification** — Reduce complexity, remove dead code paths, improve readability
2. **Unified UI Architecture** — Single codebase serving both mobile (simple) and desktop (full configuration) views, replacing the current fragmented approach
3. **Improved Configuration Management** — Streamlined config handling with clear separation of concerns
4. **UI Component Separation** — Clean separation between mobile control interface and desktop configuration UI
5. **Better Code Organization** — Logical grouping of related functionality, clearer module boundaries
6. **Preserve All Existing Behavior** — Zero regressions; the application must work exactly as it does today

---

## Contract Requirements: What MUST Be Preserved

This section defines the **non-negotiable** requirements that must remain unchanged after the refactor. Any deviation from these requirements would constitute a breaking change.

### 1. API Endpoints (32+ Endpoints)

All REST API endpoints in `src/web/web_server.py` and `src/web_notifications_routes.py` must continue to work with identical request/response formats:

**Configuration & System:**
- `GET /api/config` — Retrieve current configuration
- `POST /api/config` — Update configuration
- `POST /api/credentials` — Update Tapo credentials
- `GET /api/health` — Health check endpoint
- `GET /api/ping` — Connectivity ping
- `GET /api/status` — System status with device states
- `GET /api/system/status` — Extended status (notifications, PIN config)
- `GET /api/config/download` — Export configuration as YAML
- `POST /api/config/upload` — Import configuration from YAML
- `POST /api/restart` — Restart application

**Device & Group Control:**
- `POST /api/devices/control` — Individual device control (on/off/brightness)
- `POST /api/groups/<group_name>/control` — Device group control
- `GET /api/devices/status` — Query device status
- `GET /api/mat/status` — Mat-specific status (used by mobile control)
- `POST /api/mat/control` — Mat control (used by mobile control)
- `POST /api/mat/reset-auto` — Reset mat to automatic mode

**Scheduling & Automation:**
- `GET /api/groups/<group_name>/schedules` — List all schedules for a group
- `POST /api/groups/<group_name>/schedules` — Create new schedule
- `GET /api/groups/<group_name>/schedules/<index>` — Get specific schedule
- `PUT /api/groups/<group_name>/schedules/<index>` — Update schedule
- `DELETE /api/groups/<group_name>/schedules/<index>` — Delete schedule
- `PUT /api/groups/<group_name>/schedules/<index>/enabled` — Toggle schedule enabled/disabled
- `GET /api/groups/<group_name>/automation` — Get automation override status
- `PATCH /api/groups/<group_name>/automation` — Set automation override (pause/disable)
- `GET /api/vacation_mode` — Get vacation mode status
- `PUT /api/vacation_mode` — Set vacation mode

**Weather & Solar:**
- `GET /api/weather/forecast` — Weather forecast data
- `GET /api/weather/mat-forecast` — Weather forecast formatted for mat scheduling
- `GET /api/solar_times` — Solar sunrise/sunset times for current location

**Authentication & Mobile Control:**
- `POST /api/auth/login` — PIN-based authentication for mobile control
- `GET /control/login` — Mobile control login page
- `GET /control` — Mobile control interface (requires authentication)

**Notifications:**
- `GET /api/notifications/status` — Per-provider notification health status
- `POST /api/notifications/test` — Test notification sending

### 2. Scheduling Logic

All scheduling behavior in `src/scheduler/` must be preserved:

**Clock-Based Schedules** (`src/scheduler/schedule_evaluator.py`):
- Time window evaluation (start_time/end_time)
- Day-of-week filtering (mon, tue, wed, thu, fri, sat, sun)
- Date range constraints (start_date/end_date)
- Timezone handling (local time vs UTC)

**Solar-Based Schedules** (`src/scheduler/solar_calculator.py`):
- Sunrise/sunset calculations using location coordinates
- Relative time offsets (e.g., "30 minutes before sunset")
- Solar event-based triggers (dawn, sunrise, sunset, dusk)

**Weather Conditions** (`src/scheduler/schedule_evaluator.py`):
- Temperature threshold checks (min_temp, max_temp)
- Precipitation/snow probability thresholds
- Wind speed checks
- Weather condition filtering (clear, rain, snow, etc.)

**Priority System**:
- Schedule priority ordering (higher priority schedules override lower)
- Conflict resolution (highest priority schedule wins)

**Automation Overrides** (`src/scheduler/automation_overrides.py`):
- Temporary pause (time-limited suspension of automation)
- Permanent disable (indefinite suspension)
- Auto-return to automation after manual control

### 3. Safety Features

All safety mechanisms must continue to function:

**Max Runtime Protection** (`src/scheduler/scheduler_enhanced.py`):
- Enforces `config.safety.max_runtime_hours` (default: 6 hours)
- Automatically shuts off devices after max runtime exceeded
- Per-group runtime tracking

**Cooldown Management** (`src/scheduler/scheduler_enhanced.py`):
- Enforces `config.safety.cooldown_minutes` (default: 30 minutes)
- Prevents rapid on/off cycling
- Per-group cooldown tracking

**State Persistence** (`src/scheduler/state_manager.py`):
- Persists runtime, cooldown, last action timestamp per group
- State files: `state/<group_name>_state.json`
- Survives application restarts
- Manual override state: `state/manual_overrides.json`

### 4. Weather Resilience

All weather service resilience features in `src/weather/` must be preserved:

**Caching** (`src/weather/weather_cache.py`):
- Weather API response caching with configurable TTL
- Reduces API calls and costs
- Stale cache serving during API outages

**Degraded/Offline States** (`src/weather/resilient_weather_service.py`):
- Graceful degradation when weather API unavailable
- Fallback to cached data (even if stale)
- Clear status reporting (healthy/degraded/offline)

**Exponential Backoff** (`src/weather/resilient_weather_service.py`):
- Retry logic with exponential backoff on API failures
- Prevents API rate limit exhaustion
- Configurable retry attempts and delays

### 5. Mobile Control Interface

All mobile control features must be preserved:

**PIN Authentication** (`src/web/auth.py`):
- PIN-based authentication (4-6 digit PIN)
- Configured via `config.yaml` → `web.pin` or `HEATTRAX_WEB_PIN` env var
- Session management for authenticated users
- `/control` route requires authentication

**Manual Override** (`src/state/manual_override.py`):
- Manual device control via mobile interface
- Override state persistence across restarts
- History tracking in `state/manual_overrides.json`

**Auto-Return to Automation**:
- Automatic return to scheduled automation after configured delay
- Configurable timeout for manual control
- Clear status indication (manual vs automatic mode)

### 6. Notification System

All notification features in `src/notifications/` must be preserved:

**Email Notifications**:
- SMTP-based email sending
- Configurable recipients, subject templates, body templates
- Per-event email routing (errors, warnings, device state changes)

**Webhook Notifications**:
- HTTP POST webhook delivery
- Configurable webhook URLs per event type
- Retry logic for failed deliveries

**Per-Event Routing** (`src/notifications/notification_manager.py`):
- Different notification channels for different event types
- Event categories: errors, warnings, info, device_on, device_off
- Configurable per-channel event filtering

**Forecast Notifications** (`src/notifications/forecast_notifier.py`):
- Weather-based proactive notifications (frost warnings, etc.)
- Scheduled notification delivery
- Configurable thresholds for alerts

### 7. Setup Mode Behavior

Setup mode functionality must be preserved:

**Detection**:
- Setup mode triggered when `config.yaml` is missing or invalid
- Environment variable `HEATTRAX_SETUP_MODE=true` forces setup mode

**Behavior**:
- Web UI displays setup wizard instead of normal interface
- Limited API endpoints available (only config creation/validation)
- Device discovery and connection testing
- Configuration validation before exiting setup mode

### 8. Environment Variable Overrides

All environment variable overrides defined in `docs/ENVIRONMENT_VARIABLES.md` must continue to work:

**Critical Overrides**:
- `HEATTRAX_CONFIG_PATH` — Custom config file location
- `HEATTRAX_STATE_DIR` — Custom state directory
- `HEATTRAX_LOG_LEVEL` — Runtime log level override
- `HEATTRAX_WEB_PIN` — Mobile control PIN override
- `HEATTRAX_WEB_PORT` — Web server port override
- `HEATTRAX_SETUP_MODE` — Force setup mode
- `TAPO_EMAIL`, `TAPO_PASSWORD` — Tapo credentials override

**Weather API Overrides**:
- `OPENWEATHER_API_KEY` — OpenWeatherMap API key
- `WEATHER_CACHE_TTL` — Cache time-to-live override
- `WEATHER_RETRY_ATTEMPTS` — Retry attempt override

**SMTP Overrides**:
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` — Email configuration

---

## Acceptance Criteria: How to Verify the Refactor

### 1. Automated Test Suite

All existing tests must pass without modification (unless tests are updated to improve quality):

**Unit Tests** (21 files in `tests/unit/`):
- Schedule evaluation logic
- Solar calculations
- Configuration parsing and validation
- Authentication and PIN handling
- Notification resilience
- Manual override state management

**Integration Tests** (55+ files in `tests/integration/`):
- All API endpoint contracts
- Device control workflows
- Scheduler execution behavior
- Weather service integration
- Configuration persistence
- Setup mode activation

**Test Command**: `pytest -v`

**Expected Result**: All 150+ tests pass

### 2. Manual Testing Checklist

**Web UI Verification**:
- [ ] Configuration page loads and displays current config
- [ ] Schedule creation/editing works for all schedule types
- [ ] Device control interface responds to commands
- [ ] Status page shows current device states accurately
- [ ] Weather data displays correctly
- [ ] Solar times display correctly

**Mobile Control Verification**:
- [ ] `/control` route requires PIN authentication
- [ ] PIN authentication succeeds with correct PIN
- [ ] PIN authentication fails with incorrect PIN
- [ ] Device on/off commands work from mobile interface
- [ ] Manual override state persists across app restart
- [ ] Auto-return to automation works after configured delay

**Device Control Verification**:
- [ ] Individual device on/off commands work
- [ ] Group control commands affect all devices in group
- [ ] Brightness control works (if supported by devices)
- [ ] Device status queries return accurate information

**Scheduling Verification**:
- [ ] Clock-based schedules trigger at correct times
- [ ] Solar-based schedules trigger relative to sunrise/sunset
- [ ] Weather-based schedules respect temperature thresholds
- [ ] Priority system resolves conflicts correctly
- [ ] Day-of-week filtering works as expected
- [ ] Vacation mode disables all automation

**Safety Verification**:
- [ ] Max runtime protection shuts off devices after threshold
- [ ] Cooldown prevents rapid on/off cycling
- [ ] State persistence survives application restart
- [ ] Manual override state persists across restart

### 3. API Endpoint Regression Testing

Run integration tests for all API endpoints:

```bash
# API endpoint tests
pytest tests/integration/test_api_*.py -v
pytest tests/integration/test_device_control_api.py -v
pytest tests/integration/test_schedule_api.py -v
pytest tests/integration/test_weather_api.py -v
```

**Expected Result**: All API tests pass, confirming request/response contracts unchanged

---

## Tracking References

This refactor is part of the Phase 0 documentation cleanup effort. Related issues:

- **#133** — API Documentation (complete API endpoint reference)
- **#135** — README Consolidation (consolidate scattered README files)
- **#137** — This refactor document itself (archive v1.0, create v2.0 plan)

Other related documentation:
- [SCHEDULING.md](SCHEDULING.md) — Complete scheduling system guide
- [TESTING.md](TESTING.md) — Testing suite documentation
- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) — REST API reference
- [docs/REFACTOR_V1.md](docs/REFACTOR_V1.md) — Previous v1.0 refactor summary

---

## Scope: What IS and IS NOT in Scope

### ✅ IN SCOPE for v2.0 Refactor

**Code Simplification**:
- Remove dead code paths and unused functions
- Consolidate duplicated logic
- Improve code readability and documentation
- Refactor complex functions into smaller, testable units

**UI Unification**:
- Merge mobile and desktop UI into cohesive codebase
- Responsive design serving both mobile and desktop
- Consistent styling and branding
- Improved user experience for configuration

**Configuration Management**:
- Streamline config file structure (while maintaining backward compatibility)
- Improve config validation error messages
- Better default values and example configurations

**Code Organization**:
- Logical grouping of related modules
- Clearer separation of concerns (scheduling, device control, weather, notifications)
- Improved module boundaries and interfaces

**Documentation**:
- Inline code documentation (docstrings)
- Architecture diagrams
- Developer onboarding guide

### ❌ NOT IN SCOPE for v2.0 Refactor

**New Features**:
- New device types or integrations
- New scheduling capabilities
- New notification channels
- New API endpoints (beyond what exists)

**Breaking Changes**:
- Changes to API request/response formats
- Changes to configuration file schema (breaking existing configs)
- Changes to scheduling behavior or evaluation logic
- Changes to safety thresholds or calculations

**Infrastructure Changes**:
- Database migrations (currently file-based state)
- Message queue introduction
- Microservice architecture
- Cloud deployment changes

**Performance Optimizations**:
- Unless they fix a clear bug, performance optimizations are out of scope
- The refactor focuses on maintainability, not performance

---

## Phases / Approach

### Phase 0: Documentation Cleanup ✅ (Current - In Progress)

**Goals**: Establish accurate documentation baseline before code changes

**Tasks**:
- [x] Fix critical contradictions in docs (#129)
- [x] Mark deprecated content (#131)
- [ ] Complete API documentation (#133)
- [ ] Consolidate README.md files (#135)
- [x] Archive v1.0 refactor doc, create v2.0 plan (#137)

**Deliverables**:
- Accurate, comprehensive documentation
- Clear API contracts documented
- This refactor plan document

### Phase 1: Code Simplification (Planned)

**Goals**: Reduce complexity, improve readability, remove dead code

**Approach**:
- Audit codebase for dead code paths
- Identify duplicated logic for consolidation
- Refactor complex functions (>100 lines) into smaller units
- Improve naming conventions and code clarity
- Add inline documentation (docstrings)

**Success Criteria**:
- All tests pass
- Code coverage maintained or improved
- Reduced cyclomatic complexity metrics
- No change to external behavior

### Phase 2: UI Unification (Planned)

**Goals**: Merge mobile and desktop UI into cohesive experience

**Approach**:
- Design responsive UI framework (mobile-first)
- Implement unified template structure
- Migrate desktop features to responsive design
- Preserve mobile control interface simplicity
- Maintain PIN authentication for mobile access

**Success Criteria**:
- Single codebase serves both mobile and desktop
- Mobile control interface remains simple and fast
- Desktop configuration interface remains feature-rich
- All UI tests pass

### Phase 3: Configuration Improvements (Planned)

**Goals**: Streamline config handling, improve validation

**Approach**:
- Review config schema for simplification opportunities
- Improve config validation error messages
- Better default values and example configurations
- Maintain backward compatibility with existing configs
- Document all configuration options

**Success Criteria**:
- Existing config files work without modification
- Better error messages for invalid configs
- Improved example configurations
- Complete config documentation

### Phase 4: Testing & Validation (Ongoing)

**Goals**: Ensure no regressions throughout refactor

**Approach**:
- Run full test suite after each phase
- Manual testing of critical workflows
- API endpoint regression testing
- Performance testing (ensure no degradation)

**Success Criteria**:
- All 150+ tests pass
- Manual testing checklist complete
- API contracts verified
- No performance regressions

---

## Previous Refactor

For the v1.0 refactor summary (unified multi-device configuration, removed legacy single-device mode, standardized weather access), see [docs/REFACTOR_V1.md](docs/REFACTOR_V1.md).



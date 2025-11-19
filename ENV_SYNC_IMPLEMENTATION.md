# Environment Variable to YAML Synchronization Implementation

## Overview

This document describes the implementation of startup-time environment variable to YAML synchronization, added in version 1.1 of HeatTrax Tapo M400 Scheduler.

## Problem Statement

Previously, when environment variables overrode configuration values:
- The overrides only existed in memory during runtime
- If an env var was removed and the app restarted, the configuration would revert to the old value stored in `config.yaml`
- Users had no smooth migration path from environment-based config to Web UI-based config

## Solution

On startup, the `ConfigManager` now:
1. Loads `config.yaml` (or creates from defaults if missing)
2. Captures a "before" snapshot of the configuration
3. Applies environment variable overrides to create an "after" snapshot
4. Validates the resulting configuration
5. **Compares the before and after snapshots for env-overridden paths**
6. **If any env-overridden values differ from what's on disk, writes the effective config atomically to `config.yaml`**

This means `config.yaml` always reflects the last effective configuration, including values provided via environment variables.

## Key Implementation Details

### New Helper Methods

#### `_get_by_path(config: Dict, path: str) -> Any`
- Retrieves values from nested dictionaries using dot-separated paths
- Example: `_get_by_path(config, "location.latitude")` returns `config['location']['latitude']`
- Returns `None` if path doesn't exist

#### `_sync_env_overrides_to_disk_if_needed(original_config, effective_config, env_overridden_paths)`
- Compares original (pre-env) and effective (post-env) configs
- For each env-overridden path, checks if the value changed
- If any changes detected, performs atomic write via `_write_config_to_disk()`
- Logs info about synced values
- On write failure, logs error but doesn't crash (keeps in-memory config)

### Modified Method

#### `_load_or_create_config()`
Updated to:
1. Create `original_config` copy before applying env overrides
2. Apply env overrides to `config_with_env` copy
3. Validate `config_with_env` (only in success path, not fallback paths)
4. Call `_sync_env_overrides_to_disk_if_needed()` to persist changes

**Key decision**: Fallback paths (YAML error, validation error) do NOT call `_validate_config()` before syncing, because:
- Defaults + env should always be valid
- Avoids potential infinite loops if env vars themselves cause validation errors
- Matches original behavior where fallback paths didn't validate

## Behavior Examples

### Example 1: First Run with Env Vars Only
```bash
# Docker Compose
environment:
  - HEATTRAX_LATITUDE=51.5074
  - HEATTRAX_LONGITUDE=-0.1278
  - HEATTRAX_NOTIFICATION_EMAIL_ENABLED=true
```

**What happens:**
1. No `config.yaml` exists
2. ConfigManager creates config from defaults
3. Env vars override latitude, longitude, email.enabled
4. Resulting config is written to `config.yaml`
5. `config.yaml` now contains: `location.latitude: 51.5074`, etc.
6. Web UI shows these fields as read-only with helper text "Set via env: HEATTRAX_LATITUDE"

### Example 2: Existing Config with New Env Override
```yaml
# config.yaml before startup
location:
  latitude: 40.7128  # Old value
  longitude: -74.0060
```

```bash
# New env var added
HEATTRAX_LATITUDE=51.5074
```

**What happens:**
1. ConfigManager loads `config.yaml` with latitude: 40.7128
2. Env var overrides to latitude: 51.5074
3. Sync detects change (40.7128 → 51.5074)
4. `config.yaml` is updated to latitude: 51.5074
5. Log message: "Synced 1 env-overridden value(s) to config.yaml: location.latitude"

### Example 3: Env Var Removed
```bash
# Previously had HEATTRAX_LATITUDE=51.5074, now removed from compose file
# config.yaml contains latitude: 51.5074 from previous sync
```

**What happens:**
1. ConfigManager loads `config.yaml` with latitude: 51.5074
2. No env override for latitude (env var absent)
3. No sync needed (no env overrides active)
4. Effective config has latitude: 51.5074 from YAML
5. Web UI shows latitude field as editable (no env override)
6. User can now change via Web UI and it persists

### Example 4: No-Op (Env Matches YAML)
```yaml
# config.yaml
location:
  latitude: 51.5074
```

```bash
# Env var with same value
HEATTRAX_LATITUDE=51.5074
```

**What happens:**
1. Original config has latitude: 51.5074
2. Env override sets latitude: 51.5074
3. Sync compares: 51.5074 == 51.5074 (no change)
4. No write performed (optimization)

## Testing

Comprehensive test suite in `test_config_manager_env_sync.py`:

1. **test_first_run_no_config_env_only**: Verifies initial creation with env values
2. **test_existing_config_new_env_overrides**: Verifies sync updates existing YAML
3. **test_env_removed_later**: Verifies fallback to YAML after env removal
4. **test_no_op_when_env_and_yaml_match**: Verifies no unnecessary writes
5. **test_multiple_env_overrides_partial_sync**: Verifies selective syncing
6. **test_validation_error_prevents_startup**: Verifies error handling

All tests use temporary config files and clean environment to ensure isolation.

## Migration Path for Users

This feature enables a smooth migration workflow:

1. **Start with Environment Variables** (Docker/Portainer deployment)
   - Set `HEATTRAX_*` env vars in docker-compose.yml
   - Values are synced to config.yaml on startup
   - Fields appear read-only in Web UI

2. **Transition to Web UI** (when ready)
   - Remove env vars from docker-compose.yml
   - Restart container
   - Values persist from previous sync
   - Fields become editable in Web UI
   - Changes now save via Web UI

3. **Hybrid Approach** (if desired)
   - Keep some settings in env vars (e.g., secrets, location)
   - Manage other settings via Web UI
   - Each env var keeps its field read-only
   - Non-env fields are editable

## Security Considerations

- **Atomic writes**: Uses temporary file + rename for crash safety
- **Secret handling**: Existing secret masking in Web UI unchanged
- **Validation**: Config is validated before sync (except fallback paths)
- **Error handling**: Sync failures log errors but don't crash startup
- **CodeQL**: 0 security alerts

## Future Enhancements

Potential improvements for future versions:
- Track sync metadata (timestamp, source) in config comments
- Web UI indicator showing which fields were last set by env vs. UI
- Optional "lock" mode to prevent Web UI edits even after env removal
- Audit log of env → YAML syncs

## References

- Implementation PR: #XX (to be filled)
- Related: PR #49 (Web UI notification persistence fix)
- Documentation: ENVIRONMENT_VARIABLES.md
- Tests: test_config_manager_env_sync.py

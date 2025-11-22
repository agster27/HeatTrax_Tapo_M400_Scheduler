# Configuration Persistence Fix - Summary

## Problem Statement

Users reported that configuration changes made via the Web UI (especially the `notifications.email.enabled` checkbox) appeared to change in the UI but did not persist to `config.yaml` or affect runtime behavior across container restarts.

## Investigation Findings

After thorough analysis and testing, the core persistence infrastructure was already functional:
- ✅ `ConfigManager.update_config()` handles full config updates correctly
- ✅ `_write_config_to_disk()` implements atomic writes (temp file + rename)
- ✅ Web UI sends complete config via `deepMerge(structuredClone(lastRawConfig), formConfig)`
- ✅ Secret preservation via `_merge_secrets()` works properly
- ✅ Web server returns proper HTTP status codes

The issue was a **lack of validation** for notification settings, which could lead to:
- Silent validation failures preventing config saves
- Users not providing complete SMTP settings when enabling email
- Unclear error messages when configuration was invalid

## Solution

### 1. Enhanced Configuration Validation

Added comprehensive validation in `config_manager.py` for notification settings:

#### Email Notifications (`notifications.email.enabled = true`)
When enabled, requires:
- `smtp_host` (non-empty string)
- `smtp_port` (valid integer 1-65535)
- `smtp_username` (non-empty string)
- `smtp_password` (non-empty string)
- `from_email` (non-empty string)
- `to_emails` (non-empty list)
- `use_tls` (boolean, if present)

#### Webhook Notifications (`notifications.webhook.enabled = true`)
When enabled, requires:
- `url` (non-empty string)

#### Validation Behavior
- Email/webhook can be **disabled** even with incomplete settings
- Validation errors return clear messages (e.g., "notifications.email.smtp_host cannot be empty when email notifications are enabled")
- Invalid configs are **not written to disk** and in-memory config remains unchanged

### 2. Comprehensive Test Coverage

Added 25 new tests (48 total tests, all passing ✅):

#### `test_config_persistence.py` (13 tests)
- Email enabled persistence to disk
- Toggle email false → true
- Restart simulation (config survives)
- Validation failures (missing SMTP settings, invalid port, empty to_emails)
- Secret preservation during updates
- Env var override tracking and read-only behavior

#### `test_web_config_persistence.py` (10 tests)
- GET/POST `/api/config` endpoints
- Error handling (400 for validation errors, 500 for server errors)
- Secret preservation through web API
- Non-JSON and non-dict request handling
- Env override tracking

#### `test_notification_persistence_scenario.py` (2 tests)
- Complete end-to-end walkthrough of user enabling email via Web UI
- Verification that config persists through application restart
- Validation prevents invalid configurations

### 3. Verified Existing Tests

All existing tests continue to pass:
- 10 existing ConfigManager tests ✅
- 13 existing Web config tests ✅
- No regressions introduced

## Code Changes

### Modified Files
- `config_manager.py` (+64 lines): Added notification validation in `_validate_config()` method

### New Files
- `test_config_persistence.py` (510 lines): Unit tests for persistence
- `test_web_config_persistence.py` (282 lines): Integration tests for web API
- `test_notification_persistence_scenario.py` (213 lines): End-to-end scenario tests

**Total: 1,069 lines added, 0 lines removed**

## Security Analysis

CodeQL security scan: **0 vulnerabilities found** ✅

## Requirements Verification

All requirements from the problem statement have been met:

### ✅ Web UI → `config.yaml` persistence
- Configuration changes via Web UI are validated
- Valid configurations are written atomically to disk
- In-memory configuration is updated to new values
- Changes survive application restarts

### ✅ Environment variable precedence
- Environment variables mapped in `ENV_VAR_MAPPING` continue to override YAML
- Env-overridden fields are tracked via `get_env_overridden_paths()`
- Web UI marks env-overridden fields as read-only
- Helper text displays env var name (e.g., "Set via env: HEATTRAX_NOTIFICATION_EMAIL_ENABLED")

### ✅ Atomic writes and error handling
- Writes use temp file + `os.replace()` for atomicity
- Write failures return JSON error with appropriate HTTP status codes
- Validation failures do not write config or update in-memory state
- Front-end receives clear error messages

### ✅ SMTP / notification configuration behavior
- Enabling email without complete SMTP settings results in validation error
- Error messages clearly indicate missing/invalid fields
- Email can be disabled with incomplete settings
- Validation prevents invalid runtime states

### ✅ No changes to automation overrides
- Automation override system (`state/automation_overrides.json`) remains unchanged
- Group automation toggles continue to work as before

### ✅ No env → YAML syncing
- Environment variables are not written back to `config.yaml` on startup
- This remains a feature for a future PR as specified

## Testing Results

```bash
$ python3 -m unittest discover -s . -p "test_config*.py" -p "test_web_config*.py" -p "test_notification*.py"
...
Ran 48 tests in 0.5s
OK
```

All tests pass, including:
- All 25 new tests for this fix
- All 10 existing ConfigManager tests
- All 13 existing Web config tests

## Usage Example

### Before This Fix
```python
# User enables email in Web UI with incomplete settings
config['notifications']['email']['enabled'] = True
# No smtp_host provided

result = config_manager.update_config(config)
# Silently fails or succeeds with invalid state
# User gets no feedback about what's wrong
```

### After This Fix
```python
# User enables email in Web UI with incomplete settings
config['notifications']['email']['enabled'] = True
# No smtp_host provided

result = config_manager.update_config(config)
# Returns: {
#   'status': 'error',
#   'message': 'Validation error: notifications.email.smtp_host cannot be empty when email notifications are enabled'
# }
# Config NOT written to disk
# In-memory config unchanged
# User gets clear feedback in Web UI
```

## End-to-End Scenario

The `test_notification_persistence_scenario.py` test demonstrates the complete flow:

1. ✓ Application starts with email notifications disabled
2. ✓ User opens Web UI Configuration tab
3. ✓ User enables "Email Enabled" checkbox
4. ✓ User fills in SMTP settings (host, port, username, password, from, to)
5. ✓ User clicks "Save Configuration"
6. ✓ Validation passes
7. ✓ Config written to disk atomically
8. ✓ In-memory config updated
9. ✓ Application restarts (simulated)
10. ✓ Config loaded from disk with email still enabled
11. ✓ Notification service initializes with EmailNotificationProvider
12. ✓ Scheduler does NOT log "Notifications not enabled, skipping..."

## Conclusion

This fix ensures that:
1. Users receive immediate, clear feedback when notification configuration is invalid
2. Valid notification configurations always persist to disk and survive restarts
3. Invalid configurations cannot be saved, preventing runtime issues
4. The notification service initializes correctly with the persisted settings
5. Comprehensive test coverage ensures maintainability and correctness

The bug where email notification toggles "disappeared" was due to missing validation that prevented invalid configurations from being saved. With proper validation in place, users now get clear error messages and only valid configurations persist.

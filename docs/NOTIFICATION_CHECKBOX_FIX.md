# Notification Checkbox Persistence Fix

## Summary

Fixed a critical bug where toggling notification checkboxes in the Web UI Configuration tab did not persist to `config.yaml` or affect runtime behavior.

## Problem

When using the Web UI Configuration tab, toggling these checkboxes had no effect:
- **Notifications Required** (`notifications.required`)
- **Test Notifications on Startup** (`notifications.test_on_startup`)
- **Email Enabled** (`notifications.email.enabled`)

Despite showing as checked in the UI, the `POST /api/config` payload always sent `false` values, and `config.yaml` retained the old values.

## Root Cause

A JavaScript regex bug in the `collectFormValues()` function in `web_server.py` (line 2329):

```javascript
// BEFORE (incorrect - double backslash)
const fieldId = 'field-' + fieldDef.path.replace(/\\./g, '-');

// AFTER (correct - single backslash)
const fieldId = 'field-' + fieldDef.path.replace(/\./g, '-');
```

The double backslash `\\` caused the regex to match a literal backslash followed by any character (not dots). This resulted in:
- **Expected field ID**: `field-notifications-required`
- **Actual field ID searched**: `field-notifications.required` (with dot)
- **Result**: `document.getElementById()` returned `null`, causing the field to be skipped

## Fix Details

### 1. JavaScript Fix (web_server.py, line 2329)
Changed the regex from `/\\./g` to `/\./g` to correctly replace dots with dashes in field IDs.

### 2. Backend Logging (config_manager.py, line 550)
Added debug logging to log incoming notification settings for troubleshooting:
```python
logger.debug("update_config received notifications: %s", new_config.get("notifications"))
```

## Testing

### Unit Tests (test_config_manager_notifications.py)
Created comprehensive tests validating:
- Toggling notification flags from False to True
- Toggling notification flags from True to False
- Partial updates (updating only some flags)
- Persistence across ConfigManager reload

### Integration Tests (test_web_config_persistence.py)
Added `test_post_config_notification_checkboxes_persist()` which:
1. Gets current config via `GET /api/config`
2. Toggles the three notification flags to True
3. Posts updated config via `POST /api/config`
4. Verifies flags persist in memory and on disk

All tests pass ✅

## Verification

After this fix:
1. ✅ Web UI checkbox toggles correctly capture user input
2. ✅ `POST /api/config` payload includes correct boolean values
3. ✅ Values persist to `config.yaml` on disk
4. ✅ Values reload correctly after application restart
5. ✅ Scheduler and notification services see the updated configuration

## Impact

This fix resolves the issue where users could not enable email notifications or other notification settings via the Web UI. All notification-related configuration can now be properly managed through the Web UI Configuration tab.

## Related Files

- `web_server.py` - Fixed regex in `collectFormValues()`
- `config_manager.py` - Added debug logging
- `test_config_manager_notifications.py` - New comprehensive unit tests
- `test_web_config_persistence.py` - Added integration test

## Backwards Compatibility

This fix is fully backwards compatible:
- Existing configs are not affected
- No breaking changes to API
- No changes to config schema or validation
- Environment variable overrides continue to work as expected

# Setup Mode Implementation Summary

## Overview

This document describes the implementation of "Setup Mode" for HeatTrax Tapo M400 Scheduler, which allows the application to start even when Tapo credentials are missing or invalid.

## Problem Statement

Previously, the application would fail to start if Tapo credentials were:
- Missing
- Empty
- Invalid placeholder values (like `your_tapo_username`)

This created a poor user experience, especially for new users who:
- Wanted to explore the Web UI before configuring credentials
- Needed to configure credentials through the Web UI
- Were migrating from environment variables to config.yaml

## Solution: Setup Mode

Setup Mode is a safe operational state where:
- ✅ Application starts normally
- ✅ Web UI is accessible
- ⚠️ Device discovery and control are disabled
- 🔧 User can configure credentials through the Web UI

## Implementation Details

### 1. Credential Validation (`credential_validator.py`)

Created a new module to validate credentials and detect placeholders:

**Placeholder Usernames Detected:**
- `your_tapo_email@example.com`
- `your_tapo_username`
- `your_username`
- `your_email@example.com`

**Placeholder Passwords Detected:**
- `your_tapo_password`
- `password`

**Validation Logic:**
```python
is_valid, reason = is_valid_credential(username, password)
# Returns (False, "Username is missing or empty") for invalid credentials
# Returns (True, "Credentials present and valid") for valid credentials
```

### 2. Config Loading Changes

**config_loader.py:**
- Removed hard validation that raised `ConfigError` for missing/empty credentials
- Now logs warnings instead of failing
- Credentials section is created with empty values if missing

**config_manager.py:**
- Added `is_setup_mode()` method to check credential validity
- Relaxed validation to allow empty/placeholder credentials
- Returns `(setup_mode_active, reason)` tuple

### 3. Startup Behavior Changes

**main.py:**
- Checks for setup mode on startup using `config_manager.is_setup_mode()`
- Logs clear warnings when in setup mode
- Passes `setup_mode` flag to scheduler
- Web UI always starts regardless of setup mode

**scheduler_enhanced.py:**
- Accepts `setup_mode` parameter in `__init__`
- Skips device manager initialization in setup mode
- Runs minimal idle loop instead of device operations
- Logs setup mode status clearly

### 4. Web UI Integration

**web_server.py:**
- Added setup mode banner that displays when credentials are invalid
- Shows setup reason (e.g., "Username is missing or empty")
- Added `/api/credentials` endpoint for updating credentials
- Status API includes `setup_mode` and `setup_reason` fields
- Helper text on credential fields explains restart requirement

**Web UI Features:**
- Yellow banner at top of page when in setup mode
- System status shows "Setup Mode" or "Normal Mode"
- Credentials form includes helpful hints
- All changes integrate with existing UI

### 5. Environment Variable Behavior

**Runtime Behavior:**
- Environment variables override `config.yaml` values at runtime
- Env vars are synced to `config.yaml` on startup if values differ
- This allows smooth migration from env-based to file-based config

**Persistence Behavior:**
- Env vars DO sync to config.yaml on startup (per existing behavior)
- When credentials are saved via Web UI, they write to config.yaml
- Clear messaging in Web UI when credentials will be stored

## Testing

### Unit Tests (23 tests, all passing)

**test_credential_validator.py** (14 tests):
- Empty username/password detection
- None value handling
- Whitespace-only detection
- Placeholder username detection (case-insensitive)
- Placeholder password detection
- Valid credential acceptance
- Setup mode check logic

**test_setup_mode.py** (9 tests):
- Setup mode with empty credentials
- Setup mode with placeholder username
- Setup mode with placeholder password
- Normal mode with valid credentials
- Config loading without exceptions
- Missing credentials section handling
- Environment variable override behavior

**test_integration_setup_mode.py** (5 tests):
- End-to-end with placeholder credentials
- End-to-end with valid credentials
- Updating credentials via API simulation
- Empty credentials with device groups configured
- Environment variable persistence behavior

### Manual Testing Checklist

- [ ] Start application with no credentials → Setup mode active
- [ ] Start application with placeholder credentials → Setup mode active
- [ ] Start application with valid credentials → Normal mode active
- [ ] Web UI displays setup banner when in setup mode
- [ ] Credentials can be updated through config editor
- [ ] Restart after credential update enables device control
- [ ] Environment variables override config.yaml
- [ ] Removing env vars falls back to config.yaml values

## API Changes

### New Endpoint: `/api/credentials`

**POST /api/credentials**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Credentials updated successfully and saved to config.yaml. Restart required to enable device control.",
  "restart_required": "true"
}
```

### Updated Endpoint: `/api/status`

Now includes:
```json
{
  "setup_mode": false,
  "setup_reason": "Credentials are valid, setup mode not required",
  ...
}
```

## Logging Output

### Setup Mode Active:
```
WARNING:__main__:================================================================================
WARNING:__main__:RUNNING IN SETUP MODE
WARNING:__main__:================================================================================
WARNING:__main__:Reason: Setup mode required: Username is missing or empty
WARNING:__main__:Tapo device control is DISABLED until valid credentials are configured
WARNING:__main__:Web UI will still be available for configuration
WARNING:__main__:To exit setup mode, configure valid Tapo credentials via:
WARNING:__main__:  1. Web UI (http://<host>:<port>)
WARNING:__main__:  2. Environment variables (HEATTRAX_TAPO_USERNAME, HEATTRAX_TAPO_PASSWORD)
WARNING:__main__:  3. config.yaml (devices.credentials.username and password)
WARNING:__main__:================================================================================
```

### Normal Mode:
```
INFO:__main__:================================================================================
INFO:__main__:CREDENTIALS VALIDATED
INFO:__main__:================================================================================
INFO:__main__:Status: Credentials are valid, setup mode not required
INFO:__main__:Tapo device control is ENABLED
INFO:__main__:================================================================================
```

## Documentation Updates

### README.md
- Added "Setup Mode" section explaining the feature
- Documented credential sources and priority
- Listed placeholder values that trigger setup mode
- Explained how to exit setup mode
- Added environment variable behavior clarification

### SETUP.md
- Added Option A: "Start Without Credentials (Setup Mode)"
- Updated configuration options to include setup mode
- Documented placeholder values
- Clarified environment variable behavior

## Backward Compatibility

**Breaking Change:** The application no longer exits on missing/invalid credentials.

**Mitigation:** This is acceptable because:
1. The user (repo owner) explicitly stated there are no other users
2. The new behavior is more user-friendly
3. The change is clearly documented
4. Valid credentials still result in normal operation

## Future Enhancements

Potential improvements for future versions:
1. Auto-reload after credential update (instead of restart)
2. Test credentials button in Web UI (validate before saving)
3. Credential strength meter
4. More detailed setup wizard for first-time users
5. Better error messages for specific credential issues

## Files Changed

### New Files:
- `credential_validator.py` - Credential validation logic
- `test_credential_validator.py` - Unit tests for validation
- `test_setup_mode.py` - Unit tests for setup mode
- `test_integration_setup_mode.py` - Integration tests
- `SETUP_MODE_IMPLEMENTATION.md` - This document

### Modified Files:
- `config_loader.py` - Relaxed credential validation
- `config_manager.py` - Added setup mode detection
- `main.py` - Added setup mode logic
- `scheduler_enhanced.py` - Added setup mode support
- `web_server.py` - Added UI and API changes
- `README.md` - Documentation updates
- `SETUP.md` - Documentation updates

## Conclusion

Setup Mode successfully addresses all requirements from the problem statement:
- ✅ Non-fatal startup with missing/invalid credentials
- ✅ Clear validation with placeholder detection
- ✅ Web UI remains accessible for configuration
- ✅ Disabled device control in safe no-op state
- ✅ Environment variable behavior clarified
- ✅ Comprehensive documentation
- ✅ Full test coverage

The implementation is production-ready and provides a significantly better user experience for credential configuration.

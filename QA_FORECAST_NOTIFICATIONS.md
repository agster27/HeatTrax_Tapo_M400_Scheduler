# QA Testing Guide: Forecast Notifications and Weather State Changes

This document provides manual QA test scenarios for verifying the forecast notification system and enhanced weather state change notifications.

## Prerequisites

- HeatTrax scheduler installed and configured
- Email or webhook notification provider configured
- Access to weather API (Open-Meteo or OpenWeatherMap)
- Ability to view notification delivery (email inbox or webhook endpoint)

## Test Environment Setup

### Option 1: Email Testing with Gmail

1. Create a Gmail account for testing or use an existing one
2. Enable 2-factor authentication
3. Generate an App Password: https://support.google.com/accounts/answer/185833
4. Configure `.env` or `config.yaml`:
   ```bash
   HEATTRAX_NOTIFICATION_EMAIL_ENABLED=true
   HEATTRAX_NOTIFICATION_EMAIL_SMTP_HOST=smtp.gmail.com
   HEATTRAX_NOTIFICATION_EMAIL_SMTP_PORT=587
   HEATTRAX_NOTIFICATION_EMAIL_SMTP_USERNAME=your_test_email@gmail.com
   HEATTRAX_NOTIFICATION_EMAIL_SMTP_PASSWORD=your_app_password
   HEATTRAX_NOTIFICATION_EMAIL_FROM=your_test_email@gmail.com
   HEATTRAX_NOTIFICATION_EMAIL_TO=your_test_email@gmail.com
   ```

### Option 2: Webhook Testing with webhook.site

1. Visit https://webhook.site
2. Copy your unique webhook URL
3. Configure `.env` or `config.yaml`:
   ```bash
   HEATTRAX_NOTIFICATION_WEBHOOK_ENABLED=true
   HEATTRAX_NOTIFICATION_WEBHOOK_URL=https://webhook.site/your-unique-id
   ```
4. Keep the webhook.site tab open to see incoming requests

---

## Test Scenarios

### Scenario 1: Forecast Summary - "Always" Mode

**Objective:** Verify forecast summaries are sent on every successful weather fetch.

**Configuration:**
```yaml
notifications:
  forecast:
    enabled: true
    notify_mode: "always"
```

**Steps:**
1. Start the scheduler with the above configuration
2. Wait for the first weather fetch (should happen within 10 minutes of startup)
3. Check for forecast summary notification in email/webhook
4. Wait for the second weather fetch (another ~10 minutes)
5. Check for another forecast summary notification

**Expected Results:**
- ✅ First forecast summary received within 10 minutes of startup
- ✅ Second forecast summary received ~10 minutes after first
- ✅ Summary includes:
  - Forecast retrieved timestamp
  - Temperature threshold
  - Next 12 hours forecast table with columns: Time, Temp, Feels, Precip, Prob, Wind, Condition
  - Rows with precipitation + temp below threshold marked with `***`
  - Planned scheduler actions section
- ✅ Email subject: "HeatTrax Alert: Forecast Summary"
- ✅ Webhook payload includes `forecast_summary` field with formatted text

**Pass Criteria:** All expected results met

---

### Scenario 2: Forecast Summary - "On Change" Mode

**Objective:** Verify forecast summaries are only sent when forecast changes.

**Configuration:**
```yaml
notifications:
  forecast:
    enabled: true
    notify_mode: "on_change"
```

**Steps:**
1. Start the scheduler with the above configuration
2. Wait for the first weather fetch
3. Verify first forecast summary is received (always sent - no previous forecast)
4. Wait for the second weather fetch (~10 minutes later)
5. Verify NO second forecast summary is received (forecast hasn't changed)
6. Restart the scheduler (this will cause the forecast to be "new" again)
7. Wait for first weather fetch after restart
8. Verify forecast summary IS received after restart

**Expected Results:**
- ✅ First forecast summary received (no previous forecast to compare)
- ✅ Second fetch does NOT trigger notification (forecast unchanged)
- ✅ After restart, first fetch DOES trigger notification (treated as new)
- ✅ State file `state/forecast_notification_state.json` is created and persists across restarts

**Pass Criteria:** All expected results met

**Note:** To test that forecast change detection works, you would need to:
- Wait several hours for actual forecast change, OR
- Manually modify temperature threshold to a very different value, causing different planned actions

---

### Scenario 3: Weather State Change - Online to Offline

**Objective:** Verify state change notification when weather service goes offline.

**Configuration:**
```yaml
weather_api:
  provider: "openweathermap"
  openweathermap:
    api_key: "INVALID_KEY"  # Force failure
```

**Steps:**
1. Start scheduler with valid weather configuration
2. Confirm weather fetches are successful (check logs)
3. Stop the scheduler
4. Change to invalid API key (as shown above) OR disable network connectivity
5. Restart the scheduler
6. Wait for first weather fetch attempt (should fail)
7. Check for weather state change notification

**Expected Results:**
- ✅ Notification received: "Weather service is offline and no valid cached data available"
- ✅ Event type: `weather_service_offline`
- ✅ Notification includes:
  - Previous state: "online"
  - Current state: "offline_no_weather_data"
  - Timestamp

**Pass Criteria:** All expected results met

---

### Scenario 4: Weather State Change - Offline to Online (Recovery)

**Objective:** Verify state change notification when weather service recovers.

**Prerequisites:** Scheduler running with weather service offline (from Scenario 3)

**Steps:**
1. Restore valid weather configuration (fix API key or restore network)
2. Wait for next weather fetch attempt (check logs for "Fetching fresh weather forecast")
3. Wait for successful fetch
4. Check for weather state recovery notification

**Expected Results:**
- ✅ Notification received: "Weather service has recovered and is now online"
- ✅ Event type: `weather_service_recovered`
- ✅ Notification includes:
  - Previous state: "offline_no_weather_data" or "degraded_offline_using_cache"
  - Current state: "online"
  - Offline duration (minutes)
  - Timestamp

**Pass Criteria:** All expected results met

---

### Scenario 5: State Change Rate Limiting (No Spam on Flapping)

**Objective:** Verify that rapid weather service flapping does not spam notifications.

**Configuration:**
```yaml
weather_api:
  resilience:
    retry_interval_minutes: 1  # Fast retries for testing
```

**Steps:**
1. Start scheduler with weather service online
2. Force service offline (invalid API key)
3. Wait for offline notification (should arrive)
4. **Immediately** restore valid configuration (within 1 minute)
5. Wait for service to come back online
6. Check notifications received

**Expected Results:**
- ✅ First notification received: "Weather service offline"
- ✅ Second notification (online recovery) is SUPPRESSED due to rate limiting
- ✅ Logs show: "Suppressing state change notification due to rate limiting"
- ✅ Default rate limit is 15 minutes between state change notifications

**Pass Criteria:** All expected results met

**Note:** To see the second notification, wait 15 minutes before restoring service.

---

### Scenario 6: No Notification on Initial Startup

**Objective:** Verify that state change notifications are suppressed on initial startup.

**Steps:**
1. Clean installation: Remove `state/` directory to ensure no previous state
2. Start scheduler with valid weather configuration
3. Wait for first weather fetch (will determine initial state)
4. Check for state change notifications

**Expected Results:**
- ✅ NO state change notification received on initial startup
- ✅ Logs show: "Skipping state change notification on initial startup"
- ✅ If forecast notifications enabled, forecast summary IS received (separate from state change)

**Pass Criteria:** All expected results met

---

### Scenario 7: Forecast Summary Routing

**Objective:** Verify that forecast summaries respect per-event routing configuration.

**Configuration:**
```yaml
notifications:
  email:
    enabled: true
    # ... email config ...
  webhook:
    enabled: true
    # ... webhook config ...
  forecast:
    enabled: true
    notify_mode: "always"
  routing:
    forecast_summary:
      email: true
      webhook: false  # Forecast summaries only to email
```

**Steps:**
1. Start scheduler with above configuration
2. Wait for weather fetch and forecast summary generation
3. Check both email and webhook for notifications

**Expected Results:**
- ✅ Forecast summary received via EMAIL
- ✅ Forecast summary NOT received via webhook (per routing config)
- ✅ Other notifications (e.g., `weather_mode_enabled`) go to both (no routing override)

**Pass Criteria:** All expected results met

---

### Scenario 8: Forecast Summary Content Validation

**Objective:** Verify forecast summary format and content accuracy.

**Steps:**
1. Enable forecast notifications with `notify_mode: "always"`
2. Wait for forecast fetch
3. Receive and inspect forecast summary email/webhook

**Expected Results:**
- ✅ **Header:**
  - "WEATHER FORECAST SUMMARY" title
  - Forecast retrieved timestamp
  - Temperature threshold (from config)
  
- ✅ **Forecast Table:**
  - Column headers: Time, Temp, Feels, Precip, Prob, Wind, Condition
  - Properly aligned columns
  - Correct number of rows (default: next 12 hours)
  - Timestamps in chronological order
  - Temperature values match weather provider response
  - Precipitation values match weather provider response
  
- ✅ **Highlighting:**
  - Rows with (precipitation > 0) AND (temp < threshold) have `***` marker
  - Rows without precipitation or temp above threshold have no marker
  - Legend at bottom: "*** = Precipitation + Temperature below threshold"
  
- ✅ **Planned Actions:**
  - "PLANNED SCHEDULER ACTIONS:" section present
  - Lists actions based on forecast (e.g., "Turn on heated mats at HH:MM")
  - If no actions planned: "(No specific actions planned based on this forecast)"

**Pass Criteria:** All expected results met

---

### Scenario 9: Multiple Notification Providers

**Objective:** Verify forecast notifications work with multiple providers simultaneously.

**Configuration:**
```yaml
notifications:
  email:
    enabled: true
    # ... email config ...
  webhook:
    enabled: true
    # ... webhook config ...
  forecast:
    enabled: true
    notify_mode: "always"
```

**Steps:**
1. Configure both email and webhook providers
2. Enable forecast notifications
3. Wait for weather fetch
4. Check both providers for notifications

**Expected Results:**
- ✅ Forecast summary received via email
- ✅ Forecast summary received via webhook
- ✅ Content is identical (same forecast data)
- ✅ Both sent within seconds of each other (async/concurrent)

**Pass Criteria:** All expected results met

---

### Scenario 10: Forecast Persistence Across Restarts

**Objective:** Verify forecast state persists and change detection works after restart.

**Configuration:**
```yaml
notifications:
  forecast:
    enabled: true
    notify_mode: "on_change"
    state_file: "state/forecast_notification_state.json"
```

**Steps:**
1. Start scheduler and wait for first forecast (notification sent)
2. Stop scheduler
3. Verify `state/forecast_notification_state.json` exists and contains:
   - `forecast_hash`
   - `forecast_summary`
   - `last_updated` timestamp
4. Restart scheduler without changing configuration
5. Wait for next weather fetch
6. Verify NO notification (forecast hasn't changed)
7. Delete state file: `rm state/forecast_notification_state.json`
8. Restart scheduler
9. Verify notification IS sent (treated as first forecast)

**Expected Results:**
- ✅ State file created after first forecast
- ✅ State file persists across restarts
- ✅ After restart with valid state: no notification (forecast unchanged)
- ✅ After restart with deleted state: notification sent (treated as new)

**Pass Criteria:** All expected results met

---

## Regression Testing

After implementing forecast notifications, verify existing features still work:

### Existing Notification Events
- ✅ `device_lost` - Still fires when device health check fails
- ✅ `device_found` - Still fires when new device discovered
- ✅ `device_ip_changed` - Still fires when device IP changes
- ✅ `connectivity_lost` - Still fires on connection failures
- ✅ `weather_mode_enabled` - Still fires on startup with weather enabled
- ✅ `weather_mode_disabled` - Still fires on startup with weather disabled

### Weather Resilience
- ✅ Cache still works during outages
- ✅ Service still transitions: ONLINE → DEGRADED → OFFLINE
- ✅ Exponential backoff still works for retries
- ✅ Forecast data still cached properly

### Scheduler Behavior
- ✅ Devices still turn on/off based on forecast
- ✅ Morning mode still works
- ✅ Safety limits (max runtime, cooldown) still enforced
- ✅ State persistence still works

---

## Known Issues / Limitations

1. **Planned Actions in Forecast Summary:**
   - Currently shows generic message: "(No specific actions planned)"
   - Future enhancement: Parse scheduler's planned actions and include in summary
   - Workaround: Users can infer actions from highlighted rows with `***`

2. **Forecast Change Detection Sensitivity:**
   - Uses 24-hour window hash
   - Minor fluctuations (< 0.5°F, < 0.5mm) are ignored
   - May not detect very subtle changes
   - Workaround: Use `notify_mode: "always"` for guaranteed updates

3. **Rate Limiting is Global:**
   - 15-minute minimum between ANY state change notifications
   - Cannot configure different intervals per event type
   - Future enhancement: Per-event rate limiting

---

## Troubleshooting

### Forecast Notifications Not Received

1. **Check Configuration:**
   ```bash
   # Verify forecast notifications are enabled
   grep -A 5 "forecast:" config.yaml
   ```

2. **Check Logs:**
   ```bash
   # Look for forecast notification activity
   grep "forecast" logs/heattrax_scheduler.log | tail -20
   ```

3. **Verify Weather Fetch Success:**
   ```bash
   # Ensure weather data is being fetched
   grep "Successfully fetched and cached weather forecast" logs/heattrax_scheduler.log
   ```

4. **Check State File (for on_change mode):**
   ```bash
   # Verify state file exists and has recent data
   cat state/forecast_notification_state.json
   ```

5. **Try "always" mode temporarily:**
   - Change `notify_mode: "on_change"` to `notify_mode: "always"`
   - Restart scheduler
   - Should receive notification on next weather fetch

### State Change Notifications Not Received

1. **Verify it's not initial startup:**
   - State changes are suppressed on initial startup (no previous state)
   - Check logs for: "Skipping state change notification on initial startup"

2. **Check rate limiting:**
   - State changes within 15 minutes are suppressed
   - Check logs for: "Suppressing state change notification due to rate limiting"

3. **Verify notification provider is configured:**
   - At least one provider (email or webhook) must be enabled
   - Check startup logs for: "Notification service initialized"

---

## Sign-Off Checklist

Before marking QA complete, verify all scenarios:

- [ ] Scenario 1: Forecast Summary - "Always" Mode
- [ ] Scenario 2: Forecast Summary - "On Change" Mode
- [ ] Scenario 3: Weather State Change - Online to Offline
- [ ] Scenario 4: Weather State Change - Offline to Online
- [ ] Scenario 5: State Change Rate Limiting
- [ ] Scenario 6: No Notification on Initial Startup
- [ ] Scenario 7: Forecast Summary Routing
- [ ] Scenario 8: Forecast Summary Content Validation
- [ ] Scenario 9: Multiple Notification Providers
- [ ] Scenario 10: Forecast Persistence Across Restarts
- [ ] All regression tests pass
- [ ] No new errors in logs
- [ ] Performance is acceptable (< 1% CPU overhead)
- [ ] Documentation is accurate and complete

---

## Additional Notes

**Test Duration:** Allow 1-2 hours for complete QA testing

**Test Environment:** Can be run on any system with network access (does not require actual Tapo devices for notification testing)

**Weather Provider:** Both Open-Meteo and OpenWeatherMap have been tested and work identically

**Version Tested:** [To be filled in during QA]

**Tester:** [To be filled in during QA]

**Date:** [To be filled in during QA]

**Overall Status:** [ ] PASS / [ ] FAIL / [ ] PARTIAL

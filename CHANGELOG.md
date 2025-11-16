# Changelog

All notable changes to the HeatTrax Tapo M400 Scheduler project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-16

### Added
- **Version Management**: Added `version.py` module with semantic versioning
- **CHANGELOG**: Introduced comprehensive changelog for tracking releases
- **Multi-Device Group Support**: Organize devices into logical groups with independent automation rules
  - Weather-based automation for heated mats
  - Schedule-based automation for Christmas lights and decorations
  - Per-group runtime tracking and safety limits
- **Weather Resilience System**: Reliable operation during internet/API outages
  - Automatic caching of weather forecasts
  - Smart fallback to cached data during outages
  - State tracking: ONLINE → DEGRADED → OFFLINE
  - Automatic recovery with exponential backoff
  - Configurable cache duration and alert thresholds
- **Comprehensive Notification System**: Extensible alerting for device and weather events
  - Email notifications via SMTP (Gmail, Office365, custom)
  - Webhook notifications via HTTP POST (Slack, Discord, custom)
  - Startup validation and testing
  - Per-event routing to control which events go to which providers
  - Optional forecast summary notifications
- **Periodic Health Checks**: Background monitoring of device connectivity
  - Configurable check interval (default: 24 hours)
  - Multi-device aware with all configured devices tracked
  - Detects lost/found devices, IP changes, configuration changes
  - Automatic re-initialization on critical failures
- **HTTP Health Check Endpoints**: Monitor application health via HTTP
  - `GET /health` - Basic application health check
  - `GET /health/weather` - Weather-specific health check with status
  - Configurable host and port
  - Can be disabled entirely if not needed
- **Environment Variable Configuration**: All settings configurable via environment variables
  - Complete `HEATTRAX_*` prefix namespace
  - Override precedence: env vars > YAML > defaults
  - Suitable for Docker, Portainer, and secret management
  - Configuration file now optional when using env vars
- **Startup Diagnostic Checks**: Comprehensive pre-flight validation
  - Python version and package verification
  - Directory access validation
  - Configuration file parsing
  - Environment variable dump (with redaction)
  - Optional device connectivity test
- **Weather Provider Support**: Multiple weather API providers
  - Open-Meteo (free, no API key required) - default
  - OpenWeatherMap (requires API key)
- **Morning Mode**: Black ice protection with early morning activation
  - Configurable time window (default: 6-8 AM)
  - Separate temperature threshold
- **Safety Features**:
  - Maximum continuous runtime limit (default: 6 hours)
  - Cooldown period after max runtime (default: 30 minutes)
  - State persistence for recovery after restarts
  - Per-group runtime tracking
- **Comprehensive Logging**: Rotating log files with configurable levels
  - Verbose logging for all API calls and device operations
  - Detailed error messages with troubleshooting guidance
  - Full exception tracebacks for debugging
- **Docker Support**: Easy deployment with Docker and docker-compose
  - Official Docker images
  - Portainer deployment examples
  - Network mode options for device discovery
- **Extensive Documentation**:
  - Quick Start guide for 5-minute setup
  - Detailed setup instructions
  - Environment variable reference
  - Health check configuration guide
  - Notification system documentation
  - Weather resilience documentation
  - Startup checks documentation
  - Logging guide
  - FAQ for common issues

### Changed
- **Configuration Format**: Migrated from single-device to multi-device group format
  - Groups organize devices by function
  - Automation rules per group (weather vs schedule)
  - Independent state tracking per group
  - Legacy single-device format no longer supported
- **Device Library**: Using `python-kasa>=0.7.0` for device control
  - Credentials no longer passed to SmartPlug constructor
  - Improved compatibility across python-kasa versions
- **Weather Toggle**: Added ability to enable/disable weather-based scheduling
  - `HEATTRAX_WEATHER_ENABLED` environment variable
  - Notifications sent on startup indicating weather mode
- **Configuration Loading**: Made config.yaml optional when using environment variables
  - Informational message instead of error when config.yaml missing
  - Suitable for pure environment-based Docker deployments

### Fixed
- **Boolean Environment Variables**: Consistent parsing of boolean values
  - Accepts: true, TRUE, 1, yes, YES, on, ON (for true)
  - Accepts: false, FALSE, 0, no, NO, off, OFF (for false)
- **Error Handling**: Improved error handling throughout the application
  - Continues operation even if individual devices fail
  - Robust error handling for weather API failures
  - Graceful degradation during outages
- **Container Restart Behavior**: Added configurable pause before container restart
  - Allows time for console troubleshooting
  - Clear countdown messages in logs
  - Configurable via `HEATTRAX_REBOOT_PAUSE_SECONDS`

### Security
- **Credential Handling**: Improved security best practices
  - Support for Docker secrets
  - Environment variable redaction in logs
  - Recommendations for secret management
- **Network Configuration**: Documented subnet/VLAN limitations
  - Clear warnings for cross-subnet device discovery
  - Guidance on network configuration
  - Security considerations for broadcast traffic

### Documentation
- **README.md**: Comprehensive documentation of all features
- **QUICKSTART.md**: Fast setup guide for quick deployment
- **SETUP.md**: Detailed setup instructions
- **HEALTH_CHECK.md**: Health check and notification configuration
- **LOGGING.md**: Logging configuration and troubleshooting
- **STARTUP_CHECKS.md**: Startup diagnostic checks documentation
- **WEATHER_RESILIENCE.md**: Weather resilience and caching documentation
- **NOTIFICATION_IMPLEMENTATION.md**: Notification system implementation details
- **FORECAST_NOTIFICATION_IMPLEMENTATION.md**: Forecast notification implementation
- **QA_REPORT.md**: Quality assurance testing report
- **FAQ**: Common questions and troubleshooting

### Breaking Changes
- **Configuration Format**: Legacy single-device configuration format is no longer supported
  - Migration required: Convert to multi-device group format
  - Single-device deployments should create one group with one device
- **Device Library**: SmartPlug no longer accepts credentials keyword argument
  - Should not affect users (handled internally)
  - Update required if using device controller directly

### Deprecated
- None in this release

### Removed
- **Legacy Single-Device Configuration**: Removed support for old `device:` format
  - Use `devices.groups` format instead
  - See migration guide in documentation

### Known Issues
- **Device Discovery**: Limited to local subnet due to UDP broadcast restrictions
  - Cross-subnet/VLAN discovery not supported (by design)
  - Use static IP configuration for cross-subnet devices
  - See FAQ for detailed guidance

## [0.3.1] - Previous Release

### Summary
Previous release with basic notification system and health checks.

---

[1.0.0]: https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler/releases/tag/v1.0.0
[0.3.1]: https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler/releases/tag/v0.3.1

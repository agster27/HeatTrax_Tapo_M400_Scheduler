# v1.0 Release Notes

## HeatTrax Tapo M400 Scheduler - Version 1.0.0

**Release Date:** November 16, 2025

This is the first production-ready release of HeatTrax Tapo M400 Scheduler, providing comprehensive automated control of TP-Link Kasa/Tapo smart plugs based on weather conditions and schedules.

---

## 🎉 Highlights

### Production Ready
- ✅ **Stable API** - Version 1.0 marks a stable, production-ready release
- ✅ **Comprehensive Testing** - 137+ automated tests covering core functionality
- ✅ **Security Scanned** - CodeQL security analysis with zero vulnerabilities
- ✅ **Extensive Documentation** - Complete guides for all features

### Key Features

#### Multi-Device Support
Organize devices into logical groups with independent automation rules:
- **Weather-based groups** (heated mats) - Automatic control based on weather forecasts
- **Schedule-based groups** (Christmas lights) - Time-based on/off control
- **Per-group safety limits** - Independent runtime tracking and cooldown periods
- **Outlet-level control** - Control individual outlets on multi-outlet plugs

#### Weather Resilience
Reliable operation during internet/API outages:
- **Automatic caching** of weather forecasts (configurable duration)
- **Smart fallback** to cached data during temporary outages
- **State tracking** - ONLINE → DEGRADED → OFFLINE with clear indicators
- **Exponential backoff** retry with configurable intervals
- **Outage alerts** when service is offline too long

#### Notification System
Extensible alerting for device and weather events:
- **Email notifications** via SMTP (Gmail, Office365, custom)
- **Webhook notifications** via HTTP POST (Slack, Discord, custom)
- **Per-event routing** - Control which events go to which providers
- **Startup validation** - Test connectivity before starting scheduler
- **Forecast summaries** - Optional human-friendly weather updates

#### Health Monitoring
Comprehensive device and system health checks:
- **Periodic device checks** - Configurable interval (default: 24 hours)
- **Automatic detection** of lost/found devices, IP changes
- **HTTP endpoints** for container orchestration:
  - `GET /health` - Basic application health
  - `GET /health/weather` - Weather-specific health check
- **Auto re-initialization** after consecutive failures

#### Configuration Flexibility
Multiple ways to configure the application:
- **YAML configuration** for static settings
- **Environment variables** for Docker/secrets (46+ supported variables)
- **Override precedence** - Env vars > YAML > defaults
- **Optional config file** - Can run entirely from environment variables

---

## 📦 What's Included

### Documentation
- **README.md** - Complete project overview and feature documentation
- **QUICKSTART.md** - 5-minute setup guide
- **SETUP.md** - Detailed installation instructions
- **ENVIRONMENT_VARIABLES.md** - Comprehensive environment variable reference (NEW)
- **CHANGELOG.md** - Version history and breaking changes (NEW)
- **HEALTH_CHECK.md** - Health monitoring and notification configuration
- **LOGGING.md** - Logging configuration and troubleshooting
- **STARTUP_CHECKS.md** - Containerized deployment debugging
- **WEATHER_RESILIENCE.md** - Weather caching and outage handling

### Code Quality
- **version.py** - Semantic versioning module (NEW)
- **Removed unused imports** - Cleaner, more maintainable code
- **Consistent logging** - Normalized patterns across all modules
- **137+ passing tests** - Comprehensive test coverage
- **Zero security vulnerabilities** - CodeQL scanned

### Docker Support
- **Dockerfile** with OCI labels and metadata (UPDATED)
- **docker-compose.yml** with examples
- **Portainer deployment guide** in README
- **Network mode options** for device discovery

---

## 🔄 Migration from v0.3.x

### Breaking Changes

#### Configuration Format
The legacy single-device configuration format is **no longer supported**:

**Old format (v0.3.x) - NOT SUPPORTED:**
```yaml
device:
  ip_address: "192.168.1.100"
  username: "user@example.com"
  password: "password"
```

**New format (v1.0) - Required:**
```yaml
devices:
  credentials:
    username: "user@example.com"
    password: "password"
  groups:
    my_devices:
      enabled: true
      automation:
        weather_control: true
      items:
        - name: "Heated Mat"
          ip_address: "192.168.1.100"
```

### Migration Steps

1. **Update configuration file:**
   - Convert from single `device:` to `devices.groups` format
   - Single-device setups should create one group with one device
   - See [config.example.yaml](config.example.yaml) for examples

2. **Review environment variables:**
   - All variables remain backward compatible
   - New variables available for additional features
   - See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for complete list

3. **Test your deployment:**
   - Verify devices are discovered and controlled correctly
   - Check logs for any configuration warnings
   - Test notification system if enabled

### No Action Required For:
- Environment variable configuration
- Docker deployment setup
- Notification configuration
- Weather API settings
- Safety and threshold settings

---

## 🚀 Getting Started

### Quick Start (5 minutes)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   ```

2. **Create configuration:**
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

3. **Deploy with Docker:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

See [QUICKSTART.md](QUICKSTART.md) for detailed quick start guide.

### Environment Variables Only (Docker/Portainer)

Can run without config.yaml using environment variables:

```yaml
version: '3.8'
services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:v1.0.0
    environment:
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TAPO_USERNAME=user@example.com
      - HEATTRAX_TAPO_PASSWORD=your_password
      # ... additional settings ...
    volumes:
      - ./config.yaml:/app/config.yaml:ro  # For device IPs
      - ./logs:/app/logs
      - ./state:/app/state
    network_mode: host
```

See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for complete reference.

---

## 📊 Statistics

- **Lines of Python code:** ~10,500
- **Test coverage:** 137+ automated tests
- **Documentation:** 14 markdown files
- **Environment variables:** 46 supported
- **Notification events:** 10+ event types
- **Weather providers:** 2 (Open-Meteo, OpenWeatherMap)

---

## 🙏 Acknowledgments

- **python-kasa** - TP-Link device control library
- **Open-Meteo** - Free weather API
- **Contributors** - Thank you to all who provided feedback and testing

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 Links

- **Repository:** https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler
- **Issues:** https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler/issues
- **Docker Images:** ghcr.io/agster27/heattrax_tapo_m400_scheduler

---

## 🐛 Known Issues

### Device Discovery Limitations
- **UDP broadcast limitation** - Discovery limited to local subnet
- **Cross-subnet/VLAN** - Use static IP configuration for devices on different subnets
- **Not a bug** - This is by design due to network broadcast restrictions
- See [README FAQ](README.md#faq) for detailed guidance

### Test Dependencies
- Some async tests require `pytest-asyncio` (development only)
- All core functionality tests pass (137+ tests)

---

## 🔮 What's Next

Potential future enhancements (not committed for v1.1):
- Additional weather providers
- Advanced scheduling rules (sunrise/sunset)
- Historical weather data tracking
- Web UI for configuration
- Mobile app integration

See [GitHub Issues](https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler/issues) for feature requests and roadmap.

---

## 📢 Feedback

We welcome feedback! Please:
- ⭐ Star the repository if you find it useful
- 🐛 Report bugs via GitHub Issues
- 💡 Suggest features via GitHub Discussions
- 📖 Improve documentation via Pull Requests

Thank you for using HeatTrax Scheduler v1.0!

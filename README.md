# HeatTrax Tapo M400 Scheduler

Automated control system for TP-Link Tapo smart plugs to manage heated outdoor mats based on weather conditions. The system monitors weather forecasts and automatically turns mats on before precipitation when temperatures are below freezing, with built-in safety features and optional morning frost-clearing mode.

## 🚀 Quick Start

Want to get started quickly? See the [Quick Start Guide](QUICKSTART.md) for a 5-minute setup.

For detailed setup instructions, see [SETUP.md](SETUP.md).

## Features

- **Weather-Based Automation**: Uses Open-Meteo API for accurate weather forecasting
- **Smart Scheduling**: Turns mats on 60 minutes before precipitation if temperature is below 34°F
- **Morning Frost Mode**: Optional mode to clear frost between 6-8 AM
- **Safety Features**:
  - Maximum 6-hour continuous runtime limit
  - 30-minute cooldown period after max runtime
  - State persistence for recovery after restarts
- **Comprehensive Logging**: Rotating log files with configurable levels
- **Docker Support**: Easy deployment with Docker and docker-compose
- **Flexible Configuration**: YAML-based configuration for easy customization

## Requirements

- Python 3.11+
- TP-Link Tapo smart plug (M400 or compatible)
- Tapo account credentials
- Network access to the smart plug

## Installation

### Using Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   ```

2. Create your configuration file:
   ```bash
   cp config.example.yaml config.yaml
   ```

3. Edit `config.yaml` with your settings:
   ```yaml
   location:
     latitude: 40.7128
     longitude: -74.0060
     timezone: "America/New_York"
   
   device:
     ip_address: "192.168.1.100"
     username: "your_tapo_username"
     password: "your_tapo_password"
   ```

4. Start the scheduler:
   ```bash
   docker-compose up -d
   ```

### Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create and edit configuration:
   ```bash
   cp config.example.yaml config.yaml
   # Edit config.yaml with your settings
   ```

4. Run the scheduler:
   ```bash
   python main.py
   ```

## Configuration

### Location Settings

```yaml
location:
  latitude: 40.7128        # Your location latitude
  longitude: -74.0060      # Your location longitude
  timezone: "America/New_York"  # Your timezone
```

### Device Settings

```yaml
device:
  ip_address: "192.168.1.100"     # IP address of your Tapo device
  username: "your_tapo_username"   # Tapo account username/email
  password: "your_tapo_password"   # Tapo account password
```

### Weather Thresholds

```yaml
thresholds:
  temperature_f: 34              # Temperature threshold in Fahrenheit
  lead_time_minutes: 60          # Minutes before precipitation to turn on
  trailing_time_minutes: 60      # Minutes after precipitation to turn off
```

### Morning Mode (Optional)

```yaml
morning_mode:
  enabled: true      # Enable morning frost-clearing mode
  start_hour: 6      # Start time (24-hour format)
  end_hour: 8        # End time (24-hour format)
```

### Safety Settings

```yaml
safety:
  max_runtime_hours: 6       # Maximum continuous runtime
  cooldown_minutes: 30       # Cooldown period after max runtime
```

### Scheduler Settings

```yaml
scheduler:
  check_interval_minutes: 10   # How often to check weather
  forecast_hours: 12           # How far ahead to look for precipitation
```

## How It Works

1. **Weather Monitoring**: The scheduler checks weather forecasts every 10 minutes (configurable)

2. **Precipitation Detection**: When precipitation is forecasted within the next 12 hours and temperature is below 34°F:
   - Mats turn ON 60 minutes before expected precipitation
   - Mats turn OFF 60 minutes after precipitation ends

3. **Morning Frost Mode**: Between 6-8 AM (configurable):
   - Mats turn ON if temperature is below threshold
   - Helps clear morning frost for safe walking

4. **Safety Features**:
   - Automatic shutoff after 6 hours of continuous runtime
   - 30-minute cooldown before mats can turn on again
   - State is saved to disk for recovery after restarts

## Logs

Logs are stored in the `logs/` directory with rotating file handling:
- Default maximum file size: 10 MB
- Default backup count: 5 files
- Logs include timestamps, levels, and detailed error information

View logs:
```bash
# Docker
docker-compose logs -f

# Manual
tail -f logs/heattrax_scheduler.log
```

## State Management

The application maintains state in `state/state.json` to track:
- Current device state (on/off)
- Runtime duration
- Cooldown periods

This allows the scheduler to resume properly after restarts.

## Troubleshooting

### Device Connection Issues

If you see connection errors:
1. Verify the IP address of your Tapo device
2. Ensure your Tapo username and password are correct
3. Check that the device is on the same network
4. Try accessing the device through the Tapo app first

### Weather API Issues

If weather data fails to fetch:
1. Check your internet connection
2. Verify latitude and longitude are correct
3. Open-Meteo API is free and doesn't require an API key

### Docker Issues

```bash
# View logs
docker-compose logs -f

# Restart the service
docker-compose restart

# Rebuild after changes
docker-compose up -d --build
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [python-kasa](https://github.com/python-kasa/python-kasa) - TP-Link device control library
- [Open-Meteo](https://open-meteo.com/) - Free weather API

# Quick Start Guide

Get your HeatTrax scheduler running in 5 minutes!

## Prerequisites

- TP-Link Tapo/Kasa smart plug set up on your network
- Docker installed (or Python 3.11+)
- Your Tapo account credentials
- Your device IP address (find in Tapo app → Settings → Device Info)

## Docker Quick Start (Recommended)

1. **Clone and configure:**
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   cp config.example.yaml config.yaml
   nano config.yaml  # Edit with your settings
   ```

2. **Edit the key settings in `config.yaml`:**
   ```yaml
   location:
     latitude: YOUR_LATITUDE      # Find on Google Maps
     longitude: YOUR_LONGITUDE
     timezone: "America/New_York"
   
   devices:
     credentials:
       username: "your_tapo_email@example.com"
       password: "your_tapo_password"
     groups:
       heated_mats:
         enabled: true
         items:
           - name: "My Heated Mat"
             ip_address: "192.168.1.100"  # Your device IP
   ```

3. **Start the scheduler:**
   ```bash
   docker-compose up -d
   docker-compose logs -f  # View logs
   ```

4. **Access the Web UI:**
   
   Open `http://localhost:4328` in your browser to:
   - View real-time status and weather
   - Control automation flags per device group
   - Manually control devices
   - Edit configuration with validation

That's it! Your devices will now automatically control based on weather conditions.

## Python Quick Start (Alternative)

1. **Install and configure:**
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   pip install -r requirements.txt
   cp config.example.yaml config.yaml
   nano config.yaml  # Edit with your settings
   ```

2. **Run:**
   ```bash
   python main.py
   ```

## Configuration Options

**Using Environment Variables (Docker/Portainer):**
Instead of editing `config.yaml`, you can configure via environment variables:
```bash
HEATTRAX_LATITUDE=40.7128
HEATTRAX_LONGITUDE=-74.0060
HEATTRAX_TIMEZONE=America/New_York
HEATTRAX_TAPO_USERNAME=your_email@example.com
HEATTRAX_TAPO_PASSWORD=your_password
```

See [SETUP.md](SETUP.md) for complete environment variable setup instructions.

**Setup Mode:**
You can start without credentials configured - the Web UI will be accessible at `http://localhost:4328` where you can configure everything through the browser.

## How It Works

The scheduler will:
- ✅ Check weather every 10 minutes
- ✅ Turn devices ON before precipitation (if temp < 34°F)
- ✅ Turn devices OFF after precipitation ends
- ✅ Optional: Morning frost mode (6-8 AM)
- ✅ Safety: Auto-shutoff, cooldown periods

## Next Steps

- 📖 **Detailed Setup**: See [SETUP.md](SETUP.md) for comprehensive configuration
- 🌐 **Web UI Guide**: See [WEB_UI_GUIDE.md](WEB_UI_GUIDE.md) for web interface features
- 🔧 **Environment Variables**: See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for all config options
- 🏥 **Monitoring**: See [HEALTH_CHECK.md](HEALTH_CHECK.md) for alerts and notifications
- 🐛 **Troubleshooting**: See [LOGGING.md](LOGGING.md) for debugging help

## Stopping the Scheduler

```bash
docker-compose down        # Docker
# or
Ctrl+C                     # Python (foreground)
```

---

**Need help?** Check the logs with `docker-compose logs -f` or see [SETUP.md](SETUP.md) for troubleshooting.

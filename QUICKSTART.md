# Quick Start Guide

Get your HeatTrax scheduler running in 5 minutes!

## Prerequisites

- TP-Link Tapo smart plug set up on your network
- Docker installed (or Python 3.11+)

## Quick Setup (Docker)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   ```

2. **Choose your configuration method:**

   **Option A: Using Environment Variables (Recommended)**
   
   Create a `stack.env` file with your settings:
   ```bash
   # stack.env
   HEATTRAX_LATITUDE=YOUR_LATITUDE
   HEATTRAX_LONGITUDE=YOUR_LONGITUDE
   HEATTRAX_TIMEZONE=America/New_York
   HEATTRAX_TAPO_IP_ADDRESS=YOUR_DEVICE_IP
   HEATTRAX_TAPO_USERNAME=YOUR_TAPO_EMAIL
   HEATTRAX_TAPO_PASSWORD=YOUR_TAPO_PASSWORD
   ```
   
   Update `docker-compose.yml` to use it:
   ```yaml
   env_file:
     - stack.env
   ```
   
   > **Note**: When using environment variables, you'll see `Configuration file not found: config.yaml` in the logs - this is normal! The app will use your environment variables instead.

   **Option B: Using config.yaml**
   
   ```bash
   cp config.example.yaml config.yaml
   ```
   
   Edit `config.yaml` with your settings:
   ```yaml
   location:
     latitude: YOUR_LATITUDE    # Find on Google Maps
     longitude: YOUR_LONGITUDE
     timezone: "America/New_York"  # Your timezone
   
   device:
     ip_address: "YOUR_DEVICE_IP"  # Find in Tapo app
     username: "YOUR_TAPO_EMAIL"
     password: "YOUR_TAPO_PASSWORD"
   ```

3. **Start the scheduler:**
   ```bash
   docker-compose up -d
   ```

4. **Check it's working:**
   ```bash
   docker-compose logs -f
   ```

That's it! Your mats will now automatically turn on before precipitation when the temperature is below 34°F.

## Quick Setup (Python)

1. **Clone and setup:**
   ```bash
   git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
   cd HeatTrax_Tapo_M400_Scheduler
   pip install -r requirements.txt
   ```

2. **Configure:**
   ```bash
   cp config.example.yaml config.yaml
   nano config.yaml  # Edit with your settings
   ```

3. **Run:**
   ```bash
   python main.py
   ```

## Test Your Configuration

Before running the scheduler 24/7, test your setup:

```bash
python test_connection.py
```

This will verify:
- Configuration is valid
- Device connection works
- Weather API is accessible
- Current weather conditions

## What Happens Next?

The scheduler will:
- ✅ Check weather every 10 minutes
- ✅ Turn mats ON 60 minutes before precipitation (if temp < 34°F)
- ✅ Turn mats OFF 60 minutes after precipitation ends
- ✅ Optional: Clear frost between 6-8 AM if temperature is low
- ✅ Safety: Auto-shutoff after 6 hours, 30-min cooldown

## Common Settings to Adjust

**Change temperature threshold:**
```yaml
thresholds:
  temperature_f: 32  # Lower to turn on at colder temps
```

**Disable morning frost mode:**
```yaml
morning_mode:
  enabled: false
```

**Turn on earlier before precipitation:**
```yaml
thresholds:
  lead_time_minutes: 90  # Turn on 90 minutes before
```

## Getting Your Device IP

**Easiest way - Tapo App:**
1. Open Tapo app
2. Tap your device
3. Tap settings ⚙️
4. Look for "Device Info"
5. Note the IP address

**Alternative - Router:**
Look in your router's connected devices list for "Tapo" or "TP-Link"

## Need More Help?

- 📖 See [SETUP.md](SETUP.md) for detailed instructions
- 📖 See [README.md](README.md) for full documentation
- 🐛 Having issues? Check the logs: `docker-compose logs -f`
- ❓ Questions? Open an issue on GitHub

## Verifying It Works

Watch the logs when you first start. You should see:
```
Successfully connected to device at 192.168.1.100
Scheduler initialized successfully
Running scheduler cycle...
No precipitation expected below threshold
Device staying OFF
```

This means everything is working! The scheduler is monitoring weather and will automatically control your mats when needed.

## Stopping the Scheduler

```bash
# Docker
docker-compose down

# Python
Ctrl+C (if running in foreground)
# or kill the process if running in background
```

## Tips

- 💡 Run `docker-compose logs -f` to watch what the scheduler is doing
- 💡 Check `state/state.json` to see current runtime and cooldown status
- 💡 Logs are saved in `logs/` directory for troubleshooting
- 💡 The scheduler survives restarts - state is preserved to disk
- 💡 You can still manually control the device via Tapo app if needed

---

**Ready for more?** Check out [SETUP.md](SETUP.md) for advanced configuration options, troubleshooting, and Raspberry Pi setup instructions.

# Setup Guide for HeatTrax Tapo M400 Scheduler

This guide will walk you through setting up the HeatTrax scheduler for your heated outdoor mats.

## Prerequisites

1. **TP-Link Tapo Smart Plug** (M400 or compatible model)
   - The plug must be set up and accessible on your network
   - You need to know its IP address

2. **Tapo Account**
   - You need a Tapo account (username/email and password)
   - The account must have access to control the smart plug

3. **Location Information**
   - Your location's latitude and longitude
   - You can find these on Google Maps by right-clicking your location

## Step-by-Step Setup

### 1. Find Your Device IP Address

You can find your Tapo device's IP address in several ways:

**Option A: Through Tapo App**
1. Open the Tapo app on your phone
2. Tap on your device
3. Tap the settings gear icon
4. Look for "Device Info" or similar
5. Note the IP address shown

**Option B: Through Router**
1. Log into your router's admin interface
2. Look for connected devices list
3. Find your Tapo device by name or MAC address
4. Note its assigned IP address

**Option C: Using Network Scanner**
```bash
# Using nmap (if installed)
nmap -sn 192.168.1.0/24

# Or use the kasa-python CLI
kasa discover
```

### 2. Get Your Location Coordinates

1. Go to [Google Maps](https://maps.google.com)
2. Right-click on your location
3. The first option will show the coordinates (e.g., "40.7128, -74.0060")
4. The first number is latitude, the second is longitude

### 3. Configure the Application

**New in v1.2**: HeatTrax supports **Setup Mode** - you can now start the application without Tapo credentials configured! The Web UI will remain accessible, allowing you to configure credentials after the application is running.

You have three options for configuration:

#### Option A: Start Without Credentials (Setup Mode) - NEW!

1. Start the application without configuring Tapo credentials (or with placeholder values)
2. The application will enter **Setup Mode**:
   - ✅ Application starts normally
   - ✅ Web UI is accessible
   - ⚠️ Device control is disabled until credentials are configured
3. Access the Web UI at `http://localhost:4328` (or your configured host/port)
4. Configure your Tapo credentials through the Web UI
5. Save and restart to enable device control

This is the easiest way to get started - you can configure everything through the browser!

#### Option B: Using Environment Variables (Recommended for Docker)

When using Docker or Portainer, you can configure the application entirely through environment variables without creating a `config.yaml` file. See the "Using Environment Variables with Docker" section below for examples.

**Important**: Environment variables override `config.yaml` at runtime but **do not automatically persist to the file**. When you save configuration via the Web UI, the effective values (including those from environment variables) will be written to `config.yaml`.

> **Note**: If you use environment variables and don't have a `config.yaml` file, the application will log `Configuration file not found: config.yaml` as an informational message. This is normal and expected - the application will continue to run using your environment variables.

#### Option C: Using config.yaml

Create your `config.yaml` file:

```bash
cp config.example.yaml config.yaml
nano config.yaml  # or use your preferred editor
```

Update the following fields:

```yaml
location:
  latitude: 40.7128      # Replace with your latitude
  longitude: -74.0060    # Replace with your longitude
  timezone: "America/New_York"  # Your timezone

devices:
  credentials:
    username: "your_email@example.com"  # Your Tapo account email
    password: "your_tapo_password"      # Your Tapo account password
  groups:
    heated_mats:
      enabled: true
      automation:
        weather_control: true
        precipitation_control: true
        morning_mode: true
      items:
        - name: "Heated Mat"
          ip_address: "192.168.1.100"  # Your Tapo device IP
```

> **Tip**: You can also use a hybrid approach - put non-sensitive settings in `config.yaml` and override sensitive values (like username and password) with environment variables.

#### Important: Placeholder Values

The following credential values are recognized as **placeholders** and will trigger Setup Mode:

**Placeholder Usernames:**
- `your_tapo_email@example.com`
- `your_tapo_username`
- `your_username`
- `your_email@example.com`

**Placeholder Passwords:**
- `your_tapo_password`
- `password`

If you see these values in `config.example.yaml`, make sure to replace them with your actual Tapo credentials. If you leave them as-is, the application will enter Setup Mode.

### 4. Choose Deployment Method

#### Option A: Docker (Recommended)

**Advantages:**
- Isolated environment
- Easy updates
- Automatic restart on failure
- No Python installation needed

**Steps:**
```bash
# Make sure Docker is installed
docker --version

# Start the scheduler
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the scheduler
docker-compose down
```

**Using Environment Variables with Docker:**

Instead of mounting a `config.yaml` file, you can configure everything via environment variables. This is ideal for Portainer and secure deployments.

Create a `stack.env` file:
```bash
# stack.env - Environment variables for HeatTrax Scheduler
TZ=America/New_York

# Location Settings
HEATTRAX_LATITUDE=40.7128
HEATTRAX_LONGITUDE=-74.0060
HEATTRAX_TIMEZONE=America/New_York

# Tapo Device Settings
HEATTRAX_TAPO_USERNAME=your_tapo_email@example.com
HEATTRAX_TAPO_PASSWORD=your_tapo_password
# Note: Device IPs are configured in config.yaml under devices.groups

# Optional: Override defaults
HEATTRAX_THRESHOLD_TEMP_F=34
HEATTRAX_LEAD_TIME_MINUTES=60
HEATTRAX_MORNING_MODE_ENABLED=true
HEATTRAX_LOG_LEVEL=INFO
```

Then use it in your `docker-compose.yml`:
```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    env_file:
      - stack.env  # Load all environment variables from file
    volumes:
      - ./logs:/app/logs
      - ./state:/app/state
    restart: unless-stopped
    network_mode: host
```

> **Important**: Add `stack.env` to your `.gitignore` to prevent committing secrets! When using this approach, you'll see a log message `Configuration file not found: config.yaml` - this is normal and expected.


#### Option B: Direct Python

**Advantages:**
- Direct access to code
- Easier debugging during testing

**Requirements:**
- Python 3.11 or newer

**Steps:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the scheduler
python main.py

# Or run in background
nohup python main.py &
```

### 5. Verify It's Working

Check the logs to ensure everything is working:

```bash
# Docker
docker-compose logs -f

# Direct Python
tail -f logs/heattrax_scheduler.log
```

Look for messages like:
- "Successfully connected to device at ..."
- "Scheduler initialized successfully"
- "Running scheduler cycle..."

### 6. Access the Web UI (Optional)

The scheduler includes a web-based monitoring and configuration interface.

**Local Access (Default):**
```
http://localhost:4328
```

**Network Access (Docker/Portainer):**

To access the web UI from other machines on your network:

1. **Using Environment Variables** (Recommended):
   ```bash
   # Add to your stack.env or docker-compose.yml:
   HEATTRAX_WEB_HOST=0.0.0.0
   HEATTRAX_WEB_PORT=4328
   ```

2. **Using config.yaml**:
   ```yaml
   web:
     enabled: true
     bind_host: "0.0.0.0"  # Listen on all network interfaces
     port: 4328
   ```

3. **Access from any device**:
   ```
   http://YOUR_HOST_IP:4328
   # Example: http://192.168.1.50:4328
   ```

**Security Note**: When binding to `0.0.0.0`, the web UI is accessible from other machines on your network. Ensure your network is secure.

**Web UI Features**:
- Real-time system status and device information
- Configuration editor with validation
- View weather data and forecast
- Monitor device groups and runtime statistics

## Testing Your Setup

Before relying on the scheduler, test it manually:

1. **Test Device Connection:**
   ```bash
   # Using kasa-python CLI
   kasa --host 192.168.1.100 --username your_email@example.com --password your_password on
   kasa --host 192.168.1.100 --username your_email@example.com --password your_password off
   ```

2. **Monitor First Few Cycles:**
   Watch the logs for the first hour to ensure:
   - Weather data is being fetched successfully
   - Device state checks work
   - No error messages appear

3. **Test Manual Override:**
   If needed, you can manually control the device through the Tapo app
   The scheduler will detect the state on the next check

## Customizing Behavior

### Adjust Temperature Threshold

If you want mats to activate at a different temperature:

```yaml
thresholds:
  temperature_f: 32  # Change from 34 to 32
```

### Change Lead Time

To turn mats on earlier before precipitation:

```yaml
thresholds:
  lead_time_minutes: 90  # Change from 60 to 90
```

### Disable Morning Mode

If you don't want the morning frost-clearing mode:

```yaml
morning_mode:
  enabled: false
```

### Adjust Safety Limits

For different runtime limits:

```yaml
safety:
  max_runtime_hours: 8      # Change from 6 to 8
  cooldown_minutes: 45      # Change from 30 to 45
```

## Maintenance

### Update the Application

**Docker:**
```bash
docker-compose down
git pull
docker-compose up -d --build
```

**Direct Python:**
```bash
git pull
pip install -r requirements.txt --upgrade
# Restart the application
```

### View Historical Logs

Logs are rotated automatically. Old logs are preserved:

```bash
ls -lh logs/
# You'll see: heattrax_scheduler.log, heattrax_scheduler.log.1, etc.
```

### Check State

The current state is saved in `state/state.json`:

```bash
cat state/state.json
```

This shows:
- Whether device is currently on
- When it was turned on
- Cooldown status
- Total runtime

### Reset State

If you need to reset the state (e.g., after maintenance):

```bash
rm state/state.json
# Restart the application
docker-compose restart  # or restart Python process
```

## Troubleshooting

### "Configuration file not found"

Make sure you've created `config.yaml`:
```bash
ls -la config.yaml
```

### "Failed to initialize device"

Check:
1. IP address is correct
2. Device is powered on and connected to network
3. Username and password are correct
4. Device is accessible from the host running the scheduler

Test with kasa-python CLI:
```bash
kasa --host YOUR_IP --username YOUR_EMAIL --password YOUR_PASSWORD
```

### "Weather service error"

Check:
1. Internet connection is working
2. Latitude and longitude are correct (not swapped)
3. No firewall blocking api.open-meteo.com

### Device turns off unexpectedly

Check logs for:
- "Maximum runtime exceeded" - Safety limit reached
- Check weather forecast - precipitation may have ended

### Device doesn't turn on when expected

Check:
1. Not in cooldown period (check logs)
2. Weather forecast actually shows precipitation below threshold
3. Device isn't manually turned off in the app

## Advanced Configuration

### Running on Raspberry Pi

The scheduler works great on Raspberry Pi:

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker pi

# Clone and run
git clone https://github.com/agster27/HeatTrax_Tapo_M400_Scheduler.git
cd HeatTrax_Tapo_M400_Scheduler
cp config.example.yaml config.yaml
nano config.yaml  # Edit your settings
docker-compose up -d
```

### Setting Up as a System Service

For direct Python installation, create a systemd service:

```bash
sudo nano /etc/systemd/system/heattrax.service
```

```ini
[Unit]
Description=HeatTrax Tapo M400 Scheduler
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/HeatTrax_Tapo_M400_Scheduler
ExecStart=/usr/bin/python3 /home/pi/HeatTrax_Tapo_M400_Scheduler/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable heattrax
sudo systemctl start heattrax
sudo systemctl status heattrax
```

## Getting Help

If you encounter issues:

1. Check the logs first (most issues are logged with details)
2. Verify your configuration matches the examples
3. Test device connectivity independently
4. Open an issue on GitHub with:
   - Error messages from logs
   - Your configuration (remove sensitive data)
   - Steps to reproduce the issue

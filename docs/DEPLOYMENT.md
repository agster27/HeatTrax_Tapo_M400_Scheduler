# Deployment Guide

This guide covers deployment options for HeatTrax Scheduler, with a focus on Portainer-based deployments and environment variable configuration.

## Table of Contents

- [Docker Deployment](#docker-deployment)
- [Portainer Deployment](#portainer-deployment)
  - [Quick Deployment (Environment Variables Only)](#quick-deployment-environment-variables-only)
  - [Using Portainer Environment Variables Editor](#using-portainer-environment-variables-editor)
  - [Using Portainer Secrets (Advanced)](#using-portainer-secrets-advanced)
  - [Hybrid Approach with Config File](#hybrid-approach-with-config-file)
- [Managing and Updating Your Deployment](#managing-and-updating-your-deployment)
- [Troubleshooting in Portainer](#troubleshooting-in-portainer)

## Docker Deployment

### Using Docker Compose

See the main [README.md](../README.md) Installation section for standard Docker Compose deployment instructions.

### Using Environment Variables with Docker

HeatTrax Scheduler can be configured entirely through environment variables, making it ideal for Docker deployments. See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for the complete reference.

#### Option 1: Environment Variables in docker-compose.yml

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      - TZ=America/New_York
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TIMEZONE=America/New_York
      - HEATTRAX_TAPO_USERNAME=your_tapo_username
      - HEATTRAX_TAPO_PASSWORD=your_tapo_password
      # Add other environment variables as needed
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

volumes:
  heattrax-logs:
  heattrax-state:
```

#### Option 2: Using .env File

Create a `.env` file in the same directory as your `docker-compose.yml`:

```env
# .env file
TZ=America/New_York
HEATTRAX_LATITUDE=40.7128
HEATTRAX_LONGITUDE=-74.0060
HEATTRAX_TIMEZONE=America/New_York
HEATTRAX_TAPO_USERNAME=your_tapo_username
HEATTRAX_TAPO_PASSWORD=your_tapo_password
HEATTRAX_LOG_LEVEL=INFO
```

Then reference it in `docker-compose.yml`:

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    env_file:
      - .env
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

volumes:
  heattrax-logs:
  heattrax-state:
```

**Important:** Add `.env` to your `.gitignore` file to avoid committing sensitive credentials.

#### Option 3: Hybrid Approach (Recommended)

Use environment variables for sensitive credentials and `config.yaml` for device configuration:

```yaml
# docker-compose.yml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      # Secrets via environment variables
      - HEATTRAX_TAPO_USERNAME=${TAPO_USERNAME}
      - HEATTRAX_TAPO_PASSWORD=${TAPO_PASSWORD}
    volumes:
      # Device configuration in config.yaml
      - ./config.yaml:/app/config.yaml:ro
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

volumes:
  heattrax-logs:
  heattrax-state:
```

This approach keeps credentials separate while maintaining device configuration in a version-controlled YAML file.

## Portainer Deployment

[Portainer](https://www.portainer.io/) provides a web-based UI for managing Docker environments, making it easy to deploy and manage HeatTrax Scheduler with visual controls for environment variables and secrets.

### Quick Deployment (Environment Variables Only)

This method uses environment variables exclusively, eliminating the need for a config file. Perfect for Portainer deployments where you can manage environment variables through the UI.

1. **Create a new Stack in Portainer:**
   - Navigate to `Stacks` → `Add Stack`
   - Give your stack a name (e.g., `heattrax-scheduler`)
   - Paste the following docker-compose configuration:

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      # System Settings
      - TZ=America/New_York
      
      # Location Settings (Required)
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TIMEZONE=America/New_York
      
      # Tapo Device Settings (Required)
      - HEATTRAX_TAPO_USERNAME=your_tapo_username
      - HEATTRAX_TAPO_PASSWORD=your_tapo_password
      # Note: Device IPs are configured in config.yaml - mount it as a volume
      
      # Scheduler Settings
      - HEATTRAX_CHECK_INTERVAL_MINUTES=10
      - HEATTRAX_FORECAST_HOURS=12
      
      # Safety Settings
      - HEATTRAX_MAX_RUNTIME_HOURS=6
      - HEATTRAX_COOLDOWN_MINUTES=30
      
      # Logging
      - HEATTRAX_LOG_LEVEL=INFO
    volumes:
      - ./config.yaml:/app/config.yaml:ro  # Required: device IPs and groups
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

volumes:
  heattrax-logs:
  heattrax-state:
```

2. **Configure Environment Variables:**
   - Update the environment variables directly in the Stack editor
   - Pay special attention to:
     - `HEATTRAX_LATITUDE` and `HEATTRAX_LONGITUDE` - Your location coordinates
     - `HEATTRAX_TAPO_USERNAME` - Your Tapo account email
     - `HEATTRAX_TAPO_PASSWORD` - Your Tapo account password
   - **Important**: You also need to mount a `config.yaml` file with device IPs and groups (see volume mapping above)

3. **Deploy the Stack:**
   - Click "Deploy the stack"
   - Portainer will pull the image and start the service
   - Monitor deployment in the Portainer UI

4. **View Logs:**
   - Navigate to `Containers` → `heattrax-scheduler` → `Logs`
   - Or use Quick Actions → `Logs` from the container list

### Using Portainer Environment Variables Editor

Portainer provides a convenient UI for managing environment variables:

1. After deploying the stack, go to `Stacks` → `heattrax-scheduler` → `Editor`
2. Click on the stack name to edit
3. Use Portainer's environment variable editor to add/modify variables
4. Click "Update the stack" to apply changes

### Using Portainer Secrets (Advanced)

For enhanced security with sensitive credentials:

1. **Create Secrets in Portainer:**
   - Navigate to `Secrets` → `Add secret`
   - Create secrets for sensitive data:
     - `tapo_username`
     - `tapo_password`

2. **Reference secrets in your stack:**

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      - TZ=America/New_York
      - HEATTRAX_LATITUDE=40.7128
      - HEATTRAX_LONGITUDE=-74.0060
      - HEATTRAX_TIMEZONE=America/New_York
      - HEATTRAX_CHECK_INTERVAL_MINUTES=10
      - HEATTRAX_FORECAST_HOURS=12
      - HEATTRAX_MAX_RUNTIME_HOURS=6
      - HEATTRAX_COOLDOWN_MINUTES=30
      - HEATTRAX_LOG_LEVEL=INFO
    secrets:
      - tapo_username
      - tapo_password
    volumes:
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

secrets:
  tapo_username:
    external: true
  tapo_password:
    external: true

volumes:
  heattrax-logs:
  heattrax-state:
```

Then read secrets in your environment:
```yaml
environment:
  - HEATTRAX_TAPO_USERNAME_FILE=/run/secrets/tapo_username
  - HEATTRAX_TAPO_PASSWORD_FILE=/run/secrets/tapo_password
```

### Hybrid Approach with Config File

If you prefer using a configuration file for some settings:

1. **Prepare your configuration file** on the Portainer host:
   ```bash
   # On your Docker host
   mkdir -p /opt/heattrax
   cp config.example.yaml /opt/heattrax/config.yaml
   # Edit /opt/heattrax/config.yaml with your base settings
   ```

2. **Create stack with config volume:**

```yaml
version: '3.8'

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    environment:
      - TZ=America/New_York
      # Override only secrets via environment variables
      - HEATTRAX_TAPO_USERNAME=your_username
      - HEATTRAX_TAPO_PASSWORD=your_password
    volumes:
      - /opt/heattrax/config.yaml:/app/config.yaml:ro
      - heattrax-logs:/app/logs
      - heattrax-state:/app/state
    restart: unless-stopped
    network_mode: host

volumes:
  heattrax-logs:
  heattrax-state:
```

## Managing and Updating Your Deployment

### Portainer Management

- **View Container Status**: Navigate to `Containers` in Portainer
- **View Logs**: Click on the container and select `Logs`
- **Update Configuration**: Edit stack environment variables and click "Update the stack"
- **Restart Service**: Use the `Restart` button in the container details
- **Update Image**: Click "Recreate" to pull the latest image version

### Docker Compose Management

```bash
# View logs
docker-compose logs -f

# Restart the service
docker-compose restart

# Update to latest image
docker-compose pull
docker-compose up -d

# Rebuild after local changes
docker-compose up -d --build

# Stop the service
docker-compose down

# Stop and remove volumes (WARNING: deletes logs and state)
docker-compose down -v
```

## Troubleshooting in Portainer

### Check Container Logs

1. Go to `Containers` → `heattrax-scheduler` → `Logs`
2. Look for connection errors or configuration issues
3. Enable DEBUG logging for detailed diagnostics:
   - Add environment variable: `HEATTRAX_LOG_LEVEL=DEBUG`
   - Update the stack
   - Restart the container

### Verify Environment Variables

1. Go to `Containers` → `heattrax-scheduler` → `Inspect`
2. Check the "Env" section to verify variables are set correctly
3. Ensure there are no typos or incorrect values

### Check Container Status

1. Container should show as "running" with a green indicator
2. If restarting frequently, check logs for errors
3. Verify that required environment variables are set
4. Check that mounted volumes (if any) are accessible

### Common Issues

**Container won't start:**
- Check that required environment variables are set
- Verify credentials are correct
- Review logs for specific error messages

**Cannot connect to devices:**
- Verify device IPs are configured correctly
- Check that `network_mode: host` is set
- Ensure devices are on the same network or reachable from container

**Configuration not being applied:**
- Verify environment variables are set correctly (check spelling and values)
- Ensure container has been restarted after changes
- Check that `config.yaml` (if used) is mounted correctly

For more detailed troubleshooting, see the [Troubleshooting Guide](TROUBLESHOOTING.md).

## Additional Resources

- [Environment Variables Reference](ENVIRONMENT_VARIABLES.md) - Complete list of all environment variables
- [Setup Guide](SETUP.md) - Detailed installation and configuration instructions
- [Troubleshooting Guide](TROUBLESHOOTING.md) - Common issues and solutions
- [Main README](../README.md) - Project overview and quick start

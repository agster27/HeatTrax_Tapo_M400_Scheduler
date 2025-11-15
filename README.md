# HeatTrax Tapo M400 Scheduler

Automated control system for TP-Link Tapo smart plugs to manage heated outdoor mats based on weather conditions. The system monitors weather forecasts and automatically turns mats on before precipi[...] 

## Deploying with Portainer

You can also deploy HeatTrax Tapo M400 Scheduler using [Portainer](https://www.portainer.io/), a popular web UI for managing Docker environments. Portainer is ideal if you want to visually manage your containers, stacks, and Docker Compose files.

### Example docker-compose.yml

Below is an example `docker-compose.yml` you can use with Portainer's "Stacks" feature. Modify the `volumes` and `restart` policy as needed for your setup.

```yaml
version: "3.8"

services:
  heattrax-scheduler:
    image: ghcr.io/agster27/heattrax_tapo_m400_scheduler:latest
    container_name: heattrax-scheduler
    volumes:
      - ./config.yaml:/app/config.yaml           # Make sure to edit config.yaml for your environment
      - ./logs:/app/logs                         # Optional: Persist logs outside container
      - ./state:/app/state                       # Optional: Persist state for recovery
    environment:
      # Set any environment variables if needed
      # Example: TZ=America/New_York
    restart: unless-stopped
```

1. **Prepare your configuration:**  
   Copy `config.example.yaml` to `config.yaml` and edit it with your Tapo device and location details, following the [Configuration](#configuration) section above.

2. **Upload your stack in Portainer:**  
   - Open Portainer and go to `Stacks` → `Add Stack`.
   - Give your stack a name.
   - Copy and paste the example YAML above, or upload your customized `docker-compose.yml`.
   - Make sure your `config.yaml` and optional `logs`/`state` folders are present and correctly mapped.

3. **Deploy the stack:**  
   Click "Deploy the stack". Portainer will pull the image and start the service. Check logs in Portainer or by viewing the container logs directory mapped on your host.

4. **Update or Redeploy:**  
   If you change any settings in your config, simply redeploy the stack from Portainer to apply changes.

**Note:**  
- You can set additional environment variables using the `environment:` block, e.g., `TZ` for timezone.
- For advanced Docker/Portainer users, adapt bind mounts and network settings as needed.

For more on configuration, see the [Configuration](#configuration) section.

# ... [the rest of your README remains unchanged]
# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with HeatTrax Tapo M400 Scheduler.

## Quick Diagnostics

Before diving into specific issues:

1. **Check the Web UI Health tab** - Shows clear status and detailed errors
2. **Review container logs** - Most issues leave clear error messages
3. **Verify basic connectivity** - Ensure devices are reachable from the container

## Common Issues

### Device Connection Issues

If you see connection errors:

1. Verify the IP address of your Tapo device
2. Ensure your Tapo username and password are correct
3. Check that the device is on the same network
4. Try accessing the device through the Tapo app first
5. **See the [Device Discovery and Network Configuration](#device-discovery-and-network-configuration) section for subnet/VLAN discovery limitations**

### Device Initialization Timeout

**NEW:** If you see "Timeout after 30s while initializing device" errors but the device is reachable:

1. **Check the Web UI Health tab** - Shows clear initialization status and detailed errors
2. **Increase the timeout** - Add to your device configuration:
   ```yaml
   devices:
     groups:
       my_group:
         items:
           - name: kitchen
             ip_address: 10.0.50.74
             outlets: [0, 1]
             discovery_timeout_seconds: 60  # Increase for slow devices
   ```
3. **Verify network latency** - Multi-outlet devices (EP40M) may be slower to respond
4. **Check container logs** - Look for detailed error messages with full exception information

See [HEALTH_CHECK.md](HEALTH_CHECK.md#device-initialization-timeout) for complete documentation on device initialization and timeout configuration.

### Device Discovery Issues

If your device is not being discovered:

1. Check if the device is on a different subnet/VLAN than the container
2. Verify the device is powered on and connected to your network
3. Use static IP configuration (recommended for cross-subnet devices)
4. **See [Device Discovery and Network Configuration](#device-discovery-and-network-configuration) for detailed guidance**

### Weather API Issues

If weather data fails to fetch:

1. Check your internet connection
2. Verify latitude and longitude are correct
3. Open-Meteo API is free and doesn't require an API key
4. If using OpenWeatherMap, verify your API key is valid and active

### Docker Issues

```bash
# View logs
docker-compose logs -f

# Restart the service
docker-compose restart

# Rebuild after changes
docker-compose up -d --build
```

### Configuration Issues

**Setup Mode Activation:**
If the application enters setup mode unexpectedly:

1. Check that `HEATTRAX_TAPO_USERNAME` and `HEATTRAX_TAPO_PASSWORD` are set correctly
2. Verify credentials are not placeholders (e.g., "your_tapo_username")
3. See the README section on Setup Mode for more details

**Configuration Validation Errors:**
If configuration changes are rejected:

1. Use the Web UI editor for real-time validation
2. Check the logs for specific validation error messages
3. Ensure required fields are not empty or set to placeholder values
4. Verify YAML syntax is correct (indentation, quotes, etc.)

## Device Discovery and Network Configuration

### Q: Why is my device not being discovered even though it's online?

**A:** Device discovery uses UDP broadcast packets which are **limited to the local subnet**. If your device is on a different subnet or VLAN than the container, it will not be discovered. This is a fundamental limitation of the discovery protocol used by python-kasa and most smart home devices.

**Solutions:**
1. **Use Static IP Configuration (Recommended)**: Configure the device IP addresses in `config.yaml` under `devices.groups.*.items[].ip_address`. The scheduler will connect directly to devices using these configured IPs.
2. **Network Design**: Move the container to the same subnet/VLAN as your smart plugs.
3. **Docker Host Network Mode**: Use `network_mode: host` in your docker-compose.yml to give the container direct access to the host's network.

### Q: What are subnet and VLAN limitations for device discovery?

**A:** Device discovery in python-kasa (and most smart home protocols) uses **UDP broadcast packets** which have these limitations:

- **Cannot cross subnet boundaries**: Broadcast packets are confined to the local network segment (e.g., 192.168.1.0/24)
- **Cannot cross VLANs**: Even if subnets are connected via routing, broadcast traffic typically doesn't cross VLAN boundaries
- **Router limitations**: Most routers block broadcast traffic between networks for security and performance reasons

**This is not a bug** - it's how UDP broadcast discovery works by design.

**What still works:**
- Direct device control using configured IP address works across subnets (assuming routing and firewall rules allow it)
- The scheduler will function normally with static configuration even if discovery fails
- All scheduling, weather monitoring, and safety features remain fully operational

### Q: The logs say "Configured device IP is OUTSIDE the container's subnet" - is this a problem?

**A:** No, this is an **informational warning** to help you understand why discovery might fail. The scheduler will still attempt to connect directly to your configured device IP address.

**What this means:**
- Discovery cannot detect the device automatically (expected behavior)
- The device must be configured with a static IP address (which you've already done)
- Direct device control should still work if:
  - The device IP is reachable from the container
  - Network routing allows the connection
  - Firewall rules permit the traffic
  - Credentials are correct

**When to worry:**
- If you see repeated connection failures in the logs
- If the scheduler cannot control the device even with correct configuration
- If you want automatic device discovery (requires same subnet)

### Q: How do I know what subnet my container is on?

**A:** The scheduler logs this information at startup:

```
Container network information:
  Local IP: 192.168.1.100
  Subnet: 192.168.1.0/24
  Note: Discovery is limited to this subnet due to UDP broadcast restrictions
```

You can also check manually:
```bash
# Inside the container
ip addr show

# From Docker host
docker exec <container_name> ip addr show
```

### Q: Can I make discovery work across subnets/VLANs?

**A:** Generally no, but here are some advanced options:

1. **Use Docker Host Network Mode** (Easiest):
   ```yaml
   services:
     heattrax-scheduler:
       network_mode: host
   ```
   This gives the container direct access to the host's network interfaces.

2. **Configure Router for UDP Forwarding** (Advanced):
   - Some enterprise routers can forward directed broadcasts
   - Requires deep networking knowledge and may have security implications
   - Not recommended for home networks

3. **Place Container and Devices on Same Subnet** (Recommended):
   - Simplest and most reliable solution
   - Reorganize your network so IoT devices and containers share a subnet
   - Use VLANs for security/isolation at the switch level if needed

### Q: Should I be concerned about the "SUBNET/VLAN LIMITATION DETECTED" warning?

**A:** No, this is an informational message to explain expected behavior. As long as:
- Your device IP is configured correctly
- The device is reachable from the container
- Device control operations work (check scheduler logs)

Then everything is working as designed. The warning simply explains why automatic discovery isn't finding your device.

### Q: What's the difference between "discovery" and "device control"?

**A:** These are two separate operations:

**Discovery** (UDP broadcast):
- Automatically finds devices on the local network
- Limited to local subnet only
- Used during startup and periodic health checks
- Optional - only needed if you want automatic device detection

**Device Control** (Direct TCP/IP connection):
- Connects directly to a specific IP address
- Works across subnets (with proper routing)
- Used for all device operations (on/off/status)
- Required for the scheduler to function
- Works with static IP configuration

The scheduler **requires device control** but discovery is **optional**.

### Q: My devices are discovered but the configured IP shows a warning. Why?

**A:** This can happen if:
1. The configured IP is on a different subnet than discovered devices
2. You have multiple network segments with devices on each
3. The configured device is offline/unreachable during discovery

Check:
- Is the configured IP correct?
- Is that device online and responsive?
- Are discovered devices on a different subnet than the configured one?

If the configured device works (scheduler can control it), you can safely ignore discovery warnings.

### Q: How can I test if my device is reachable from the container?

**A:** Run these commands from inside the container:

```bash
# Test basic connectivity
docker exec <container_name> ping -c 3 <device_ip>

# Test device port (9999 for Tapo)
docker exec <container_name> nc -zv <device_ip> 9999

# Check routing
docker exec <container_name> ip route get <device_ip>
```

If these commands succeed, device control should work even if discovery fails.

## Getting Help

If you're still experiencing issues after reviewing this guide:

1. **Check the logs** - Enable DEBUG logging for detailed diagnostics:
   ```yaml
   logging:
     level: DEBUG
   ```
   or set environment variable: `HEATTRAX_LOG_LEVEL=DEBUG`

2. **Review the documentation**:
   - [Setup Guide](SETUP.md)
   - [Health Check Guide](HEALTH_CHECK.md)
   - [Logging Guide](LOGGING.md)

3. **Open an issue** on GitHub with:
   - Description of the problem
   - Relevant log excerpts (sanitize any sensitive information)
   - Configuration details (without credentials)
   - Docker/environment information

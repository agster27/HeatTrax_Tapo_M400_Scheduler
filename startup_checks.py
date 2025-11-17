"""Startup sanity checks and diagnostic logging for containerized deployments."""

import os
import sys
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import importlib.metadata


def log_separator(message: str = ""):
    """Print a separator line for readability."""
    if message:
        print(f"\n{'=' * 60}")
        print(f"  {message}")
        print('=' * 60)
    else:
        print('=' * 60)


def check_python_version():
    """Log Python interpreter version."""
    try:
        version_info = sys.version_info
        version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
        print(f"✓ Python version: {version_str}")
        print(f"  Full version: {sys.version}")
        print(f"  Executable: {sys.executable}")
        return True
    except Exception as e:
        print(f"✗ Failed to get Python version: {e}")
        return False


def check_package_versions(requirements_file: str = "requirements.txt") -> bool:
    """
    Log installed versions of all packages listed in requirements.txt.
    
    Args:
        requirements_file: Path to requirements.txt file
        
    Returns:
        True if all requirements are satisfied, False if any are missing
    """
    req_path = Path(requirements_file)
    
    if not req_path.exists():
        print(f"✗ Requirements file not found: {requirements_file}")
        return False
    
    print(f"✓ Requirements file found: {requirements_file}")
    all_satisfied = True
    
    try:
        with open(req_path, 'r') as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        print(f"\nInstalled package versions:")
        for req in requirements:
            # Parse requirement (handle >=, ==, etc.)
            package_name = req.split('>=')[0].split('==')[0].split('<')[0].split('>')[0].strip()
            
            if not package_name:
                continue
            
            try:
                # Try to get installed version
                version = importlib.metadata.version(package_name)
                print(f"  ✓ {package_name}: {version} (required: {req})")
            except importlib.metadata.PackageNotFoundError:
                print(f"  ✗ {package_name}: NOT INSTALLED (required: {req})")
                all_satisfied = False
        
        if all_satisfied:
            print(f"\n✓ All required packages are installed")
        else:
            print(f"\n✗ WARNING: Some required packages are missing!")
        
        return all_satisfied
        
    except Exception as e:
        print(f"✗ Failed to check package versions: {e}")
        return False


def check_working_directory():
    """Log current working directory."""
    try:
        cwd = os.getcwd()
        print(f"✓ Current working directory: {cwd}")
        
        # List contents
        try:
            contents = os.listdir(cwd)
            print(f"  Directory contains {len(contents)} items")
            # Show key files
            key_files = [f for f in contents if f.endswith('.py') or f.endswith('.yaml') or f == 'requirements.txt']
            if key_files:
                print(f"  Key files present: {', '.join(sorted(key_files)[:10])}")
        except Exception as e:
            print(f"  Warning: Could not list directory contents: {e}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to get working directory: {e}")
        return False


def check_directory_access(directories: List[str]) -> bool:
    """
    Verify access to important directories.
    
    Args:
        directories: List of directory paths to check
        
    Returns:
        True if all directories are accessible, False otherwise
    """
    all_accessible = True
    
    print(f"\nDirectory access checks:")
    for dir_path in directories:
        path = Path(dir_path)
        
        # Check if exists
        if not path.exists():
            print(f"  ⚠ {dir_path}: Does not exist, will attempt to create...")
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"    ✓ Successfully created {dir_path}")
            except Exception as e:
                print(f"    ✗ Failed to create {dir_path}: {e}")
                all_accessible = False
                continue
        
        # Check read access
        try:
            list(path.iterdir())
            readable = True
        except Exception:
            readable = False
        
        # Check write access
        try:
            test_file = path / '.write_test'
            test_file.touch()
            test_file.unlink()
            writable = True
        except Exception:
            writable = False
        
        status = "✓" if (readable and writable) else "✗"
        perms = []
        if readable:
            perms.append("readable")
        if writable:
            perms.append("writable")
        
        print(f"  {status} {dir_path}: {', '.join(perms) if perms else 'NOT accessible'}")
        
        if not (readable and writable):
            all_accessible = False
    
    if all_accessible:
        print(f"✓ All directories are accessible")
    else:
        print(f"✗ WARNING: Some directories are not fully accessible!")
    
    return all_accessible


def check_config_file(config_path: str = "config.yaml") -> Tuple[bool, Optional[Dict]]:
    """
    Check for config.yaml presence and attempt to parse it.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Tuple of (success, config_dict or None)
    """
    path = Path(config_path)
    
    # Check if config path is set via environment variable
    env_config_path = os.environ.get('HEATTRAX_CONFIG_PATH')
    if env_config_path:
        print(f"✓ Config path from environment: {env_config_path}")
        path = Path(env_config_path)
    
    print(f"\nConfiguration file check:")
    if not path.exists():
        print(f"  ⚠ Config file not found: {path}")
        print(f"    This is acceptable if using environment variables for configuration")
        print(f"    Will attempt to load config from environment variables...")
        return True, None  # Not an error if using env vars
    
    print(f"  ✓ Config file found: {path}")
    
    # Try to parse it
    try:
        import yaml
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        
        if config is None:
            print(f"  ⚠ Config file is empty")
            return True, {}
        
        if not isinstance(config, dict):
            print(f"  ✗ Config file has invalid format (not a dictionary)")
            return False, None
        
        print(f"  ✓ Config file parsed successfully")
        print(f"  Configuration sections: {', '.join(config.keys())}")
        
        # Check for required sections
        required = ['location', 'devices', 'thresholds', 'safety', 'scheduler']
        missing = [s for s in required if s not in config]
        if missing:
            print(f"  ⚠ Missing sections (may be provided via env vars): {', '.join(missing)}")
        else:
            print(f"  ✓ All required sections present in config file")
        
        return True, config
        
    except Exception as e:
        print(f"  ✗ Failed to parse config file: {type(e).__name__}: {e}")
        return False, None


def dump_environment_variables(sensitive_patterns: List[str] = None):
    """
    Dump environment variables to logs with sensitive data redaction.
    
    Args:
        sensitive_patterns: List of patterns to redact (case-insensitive)
    """
    if sensitive_patterns is None:
        sensitive_patterns = ['password', 'secret', 'token', 'key', 'credential']
    
    print(f"\nEnvironment variables:")
    
    # Get all environment variables
    env_vars = dict(os.environ)
    
    # Filter and display HEATTRAX_ variables first
    heattrax_vars = {k: v for k, v in env_vars.items() if k.startswith('HEATTRAX_')}
    other_vars = {k: v for k, v in env_vars.items() if not k.startswith('HEATTRAX_')}
    
    if heattrax_vars:
        print(f"\n  HEATTRAX Configuration Variables ({len(heattrax_vars)}):")
        for key in sorted(heattrax_vars.keys()):
            value = heattrax_vars[key]
            # Redact sensitive values
            if any(pattern.lower() in key.lower() for pattern in sensitive_patterns):
                display_value = '***REDACTED***' if value else '(empty)'
            else:
                display_value = value
            print(f"    {key}={display_value}")
    else:
        print(f"  No HEATTRAX_ configuration variables found")
    
    # Show count of other environment variables
    print(f"\n  Other environment variables: {len(other_vars)}")
    
    # Optionally show important system variables (non-sensitive)
    important_vars = ['PATH', 'HOME', 'USER', 'HOSTNAME', 'TZ', 'LANG', 'PWD']
    found_important = {k: v for k, v in other_vars.items() if k in important_vars}
    if found_important:
        print(f"  Important system variables:")
        for key in sorted(found_important.keys()):
            print(f"    {key}={found_important[key]}")


def check_device_connectivity(ip_address: str, port: int = 9999, timeout: float = 5.0) -> bool:
    """
    Attempt socket connection to Tapo device.
    
    NOTE: This is a legacy check for port 9999. Tapo devices (EP40M, etc.) do NOT
    use this port and require authenticated discovery instead. This check is kept
    for backwards compatibility but will typically fail for Tapo devices.
    
    Args:
        ip_address: Device IP address
        port: Device port (default 9999 for legacy Kasa devices)
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    print(f"\nLegacy device connectivity check (port {port}):")
    print(f"  Testing connection to {ip_address}:{port} (timeout: {timeout}s)...")
    print(f"  NOTE: Tapo devices do NOT use port 9999 - this check will fail for EP40M and similar devices")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip_address, port))
        sock.close()
        
        if result == 0:
            print(f"  ✓ Successfully connected to {ip_address}:{port}")
            return True
        else:
            print(f"  ✗ Failed to connect to {ip_address}:{port} (error code: {result})")
            print(f"    This is EXPECTED for Tapo devices - they require authenticated discovery")
            return False
            
    except socket.gaierror as e:
        print(f"  ✗ DNS/hostname resolution failed for {ip_address}: {e}")
        return False
    except socket.timeout:
        print(f"  ✗ Connection timeout to {ip_address}:{port}")
        print(f"    This is EXPECTED for Tapo devices - they require authenticated discovery")
        return False
    except Exception as e:
        print(f"  ✗ Connection error: {type(e).__name__}: {e}")
        return False


def check_outbound_ip():
    """Log the outbound IP address of the container."""
    print(f"\nOutbound IP address check:")
    
    # Try multiple methods to get outbound IP
    methods = [
        ('DNS query', lambda: socket.gethostbyname(socket.gethostname())),
        ('Interface query', lambda: _get_ip_from_interfaces()),
        ('External service', lambda: _get_ip_from_external_service()),
    ]
    
    for method_name, method_func in methods:
        try:
            ip = method_func()
            if ip and ip != '127.0.0.1':
                print(f"  ✓ Outbound IP ({method_name}): {ip}")
                return True
        except Exception as e:
            print(f"  ⚠ {method_name} failed: {e}")
    
    print(f"  ⚠ Could not determine outbound IP address")
    return False


def _get_ip_from_interfaces() -> Optional[str]:
    """Get IP address from network interfaces."""
    import socket
    
    # Try to get IP by creating a socket
    try:
        # Create a socket to a public DNS server (doesn't actually send data)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def _get_ip_from_external_service() -> Optional[str]:
    """Get IP address from external service (not implemented to avoid external dependencies)."""
    # Could implement with: requests.get('https://api.ipify.org').text
    # But avoiding to minimize external dependencies
    return None


async def check_tapo_device_connectivity(ip_address: str, username: str, password: str, timeout: float = 10.0) -> bool:
    """
    Attempt Tapo-authenticated discovery and connection to a Tapo device.
    
    This is a pre-flight check that validates device reachability using the same
    method as the main scheduler. This check is non-fatal - failure here will not
    prevent the scheduler from starting.
    
    Args:
        ip_address: Device IP address
        username: Tapo account username
        password: Tapo account password
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    print(f"\nTapo device connectivity check:")
    print(f"  Testing authenticated discovery for {ip_address} (timeout: {timeout}s)...")
    
    if not username or not password:
        print(f"  ⚠ Skipping: Tapo credentials not available")
        print(f"    Set HEATTRAX_TAPO_USERNAME and HEATTRAX_TAPO_PASSWORD to enable this check")
        return False
    
    try:
        # Import here to avoid circular dependencies
        from kasa import Discover
        import asyncio
        
        # Attempt authenticated discovery
        print(f"  Using Discover.discover_single with Tapo credentials...")
        device = await asyncio.wait_for(
            Discover.discover_single(ip_address, username=username, password=password),
            timeout=timeout
        )
        
        # Update device to get info
        await device.update()
        
        # Log device information
        device_model = getattr(device, 'model', 'Unknown')
        device_alias = getattr(device, 'alias', 'Unknown')
        num_children = len(device.children) if hasattr(device, 'children') and device.children else 0
        
        print(f"  ✓ Successfully connected to Tapo device at {ip_address}")
        print(f"    Model: {device_model}")
        print(f"    Alias: {device_alias}")
        print(f"    Outlets: {num_children}")
        
        return True
        
    except asyncio.TimeoutError:
        print(f"  ✗ Connection timeout to {ip_address} after {timeout}s")
        print(f"    Device may be offline, unreachable, or credentials may be incorrect")
        return False
    except Exception as e:
        print(f"  ✗ Connection failed: {type(e).__name__}: {e}")
        print(f"    This may indicate:")
        print(f"      - Device is offline or unreachable")
        print(f"      - Incorrect credentials")
        print(f"      - Network connectivity issues")
        return False


def check_notification_config(config_data: Optional[Dict]) -> bool:
    """
    Check notification configuration if enabled.
    
    Args:
        config_data: Parsed configuration dictionary
        
    Returns:
        True if notification configuration is valid or disabled, False if critical error
    """
    if not config_data:
        print(f"\nNotification configuration check: SKIPPED (no config data)")
        return True
    
    print(f"\nNotification configuration check:")
    
    notifications_config = config_data.get('notifications', {})
    
    # Check if notifications are required
    required = notifications_config.get('required', False)
    test_on_startup = notifications_config.get('test_on_startup', False)
    
    print(f"  notifications.required: {required}")
    print(f"  notifications.test_on_startup: {test_on_startup}")
    
    # Check email config
    email_config = notifications_config.get('email', {})
    email_enabled = email_config.get('enabled', False)
    
    print(f"\n  Email notifications:")
    if email_enabled:
        print(f"    Status: ENABLED")
        
        # Check required fields
        required_fields = ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password', 'from_email', 'to_emails']
        missing_fields = [field for field in required_fields if not email_config.get(field)]
        
        if missing_fields:
            print(f"    ✗ Missing required fields: {', '.join(missing_fields)}")
            print(f"      Disable email notifications or fix the configuration.")
            print(f"      See HEALTH_CHECK.md for configuration details.")
            if required:
                return False  # Critical failure if notifications are required
        else:
            print(f"    ✓ Configuration fields present")
    else:
        print(f"    Status: DISABLED")
    
    # Check webhook config
    webhook_config = notifications_config.get('webhook', {})
    webhook_enabled = webhook_config.get('enabled', False)
    
    print(f"\n  Webhook notifications:")
    if webhook_enabled:
        print(f"    Status: ENABLED")
        
        # Check required fields
        if not webhook_config.get('url'):
            print(f"    ✗ Missing required field: url")
            print(f"      Disable webhook notifications or fix the configuration.")
            print(f"      See HEALTH_CHECK.md for configuration details.")
            if required:
                return False  # Critical failure if notifications are required
        else:
            print(f"    ✓ Configuration fields present")
            print(f"    URL: {webhook_config['url']}")
    else:
        print(f"    Status: DISABLED")
    
    # Check routing config if present
    routing_config = notifications_config.get('routing', {})
    if routing_config:
        print(f"\n  Per-event routing configured for {len(routing_config)} event types")
    
    if not email_enabled and not webhook_enabled:
        print(f"\n  ✓ All notification providers disabled (this is acceptable)")
    elif required and (email_enabled or webhook_enabled):
        print(f"\n  ⚠ Notifications are required - will perform full validation at startup")
    
    return True


def run_startup_checks(config_path: str = "config.yaml", device_ip: Optional[str] = None) -> bool:
    """
    Run all startup sanity checks.
    
    Args:
        config_path: Path to configuration file
        device_ip: Optional device IP address for connectivity check
        
    Returns:
        True if all critical checks pass, False otherwise
    """
    log_separator("STARTUP SANITY CHECKS")
    
    print(f"\nRunning pre-flight diagnostics...\n")
    
    # Track critical failures
    critical_failure = False
    
    # 1. Python version
    if not check_python_version():
        critical_failure = True
    
    print()  # Blank line for readability
    
    # 2. Package versions
    if not check_package_versions():
        print(f"⚠ WARNING: Some packages are missing, but continuing...")
    
    print()  # Blank line
    
    # 3. Working directory
    if not check_working_directory():
        critical_failure = True
    
    # 4. Directory access
    important_dirs = ['logs', 'state']
    # Expand to absolute paths relative to CWD
    abs_dirs = [str(Path(d).resolve()) for d in important_dirs]
    if not check_directory_access(abs_dirs):
        print(f"⚠ WARNING: Some directories are not accessible, but continuing...")
    
    # 5. Config file check
    config_ok, config_data = check_config_file(config_path)
    if not config_ok:
        critical_failure = True
    
    # 6. Environment variables
    dump_environment_variables()
    
    # 7. Notification configuration check (basic validation only)
    if not check_notification_config(config_data):
        print(f"⚠ WARNING: Notification configuration issues detected")
        print(f"  Full validation will be performed during application startup")
    
    # 8. Tapo device connectivity (optional, non-critical)
    # Try to get device IP and credentials for optional Tapo connectivity check
    tapo_check_performed = False
    if device_ip or (config_data and 'devices' in config_data):
        # Get credentials from environment or config
        username = os.environ.get('HEATTRAX_TAPO_USERNAME')
        password = os.environ.get('HEATTRAX_TAPO_PASSWORD')
        
        if not username and config_data:
            username = config_data.get('devices', {}).get('credentials', {}).get('username')
        if not password and config_data:
            password = config_data.get('devices', {}).get('credentials', {}).get('password')
        
        # Get first device IP if not provided
        test_ip = device_ip
        if not test_ip and config_data:
            groups = config_data.get('devices', {}).get('groups', {})
            for group_name, group_config in groups.items():
                items = group_config.get('items', [])
                if items and len(items) > 0:
                    test_ip = items[0].get('ip_address')
                    if test_ip:
                        print(f"\nUsing first configured device IP for connectivity check: {test_ip}")
                        break
        
        # Perform Tapo connectivity check if we have all required info
        if test_ip and username and password:
            try:
                import asyncio
                result = asyncio.run(check_tapo_device_connectivity(test_ip, username, password))
                tapo_check_performed = True
                if not result:
                    print(f"  ⚠ Tapo connectivity check failed, but this is non-critical")
                    print(f"    The scheduler will attempt to connect during normal operation")
            except Exception as e:
                print(f"  ⚠ Could not perform Tapo connectivity check: {e}")
        elif test_ip:
            # Fall back to legacy check (will likely fail for Tapo devices)
            print(f"\nNote: Tapo credentials not available, falling back to legacy connectivity check")
            check_device_connectivity(test_ip)
    
    if not tapo_check_performed:
        print(f"\nTapo device connectivity check: SKIPPED")
        print(f"  To enable this check, ensure:")
        print(f"    - Device IP is configured in config.yaml")
        print(f"    - HEATTRAX_TAPO_USERNAME is set")
        print(f"    - HEATTRAX_TAPO_PASSWORD is set")
    
    # 9. Outbound IP (optional, non-critical)
    check_outbound_ip()
    
    # Summary
    log_separator()
    if critical_failure:
        print(f"\n✗ CRITICAL FAILURES DETECTED - Startup checks failed!")
        print(f"  Please review the errors above before proceeding.\n")
        return False
    else:
        print(f"\n✓ All critical startup checks passed!")
        print(f"  (Some warnings may be present, but are non-critical)\n")
        return True


if __name__ == "__main__":
    # Allow running directly for testing
    success = run_startup_checks()
    sys.exit(0 if success else 1)

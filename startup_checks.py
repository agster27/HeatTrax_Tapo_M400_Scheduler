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
        required = ['location', 'device', 'thresholds', 'safety', 'scheduler']
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
    
    Args:
        ip_address: Device IP address
        port: Device port (default 9999 for Tapo)
        timeout: Connection timeout in seconds
        
    Returns:
        True if connection successful, False otherwise
    """
    print(f"\nDevice connectivity check:")
    print(f"  Testing connection to {ip_address}:{port} (timeout: {timeout}s)...")
    
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
            print(f"    This may be normal if the device uses a different protocol/port")
            return False
            
    except socket.gaierror as e:
        print(f"  ✗ DNS/hostname resolution failed for {ip_address}: {e}")
        return False
    except socket.timeout:
        print(f"  ✗ Connection timeout to {ip_address}:{port}")
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
    
    # 7. Device connectivity (optional, non-critical)
    if device_ip:
        check_device_connectivity(device_ip)
    else:
        print(f"\nDevice connectivity check: SKIPPED (no device IP provided)")
    
    # 8. Outbound IP (optional, non-critical)
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

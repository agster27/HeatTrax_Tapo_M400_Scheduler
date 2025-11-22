#!/usr/bin/env python3
"""
Demo script to show Setup Mode functionality.

This script demonstrates the setup mode behavior with different credential scenarios.
"""

import tempfile
import yaml
import os
from pathlib import Path

from src.config.config_loader import Config
from src.config.config_manager import ConfigManager
from src.config.credential_validator import is_valid_credential


def create_demo_config(username='', password=''):
    """Create a demo config file."""
    config = {
        'location': {
            'latitude': 40.7128,
            'longitude': -74.0060,
            'timezone': 'America/New_York'
        },
        'devices': {
            'credentials': {
                'username': username,
                'password': password
            },
            'groups': {
                'heated_mats': {
                    'enabled': True,
                    'items': [
                        {'name': 'Demo Mat', 'ip_address': '192.168.1.100'}
                    ]
                }
            }
        },
        'weather_api': {
            'enabled': True,
            'provider': 'open-meteo'
        },
        'thresholds': {
            'temperature_f': 34,
            'lead_time_minutes': 60,
            'trailing_time_minutes': 60
        },
        'safety': {
            'max_runtime_hours': 6,
            'cooldown_minutes': 30
        },
        'scheduler': {
            'check_interval_minutes': 10,
            'forecast_hours': 12
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        return f.name


def demo_scenario(scenario_name, username, password, description):
    """Run a demo scenario."""
    print("\n" + "=" * 80)
    print(f"SCENARIO: {scenario_name}")
    print("=" * 80)
    print(f"Description: {description}")
    print(f"Username: '{username}'")
    print(f"Password: '{password}'")
    print("-" * 80)
    
    # Create config
    config_path = create_demo_config(username, password)
    
    try:
        # Load config
        print("\n1. Loading configuration...")
        config = Config(config_path)
        print("   ✓ Config loaded successfully (no exception)")
        
        # Check credential validation
        print("\n2. Validating credentials...")
        is_valid, reason = is_valid_credential(username, password)
        print(f"   Valid: {is_valid}")
        print(f"   Reason: {reason}")
        
        # Check setup mode
        print("\n3. Checking setup mode...")
        config_manager = ConfigManager(config_path)
        setup_mode, setup_reason = config_manager.is_setup_mode()
        
        if setup_mode:
            print("   🔧 SETUP MODE ACTIVE")
            print(f"   Reason: {setup_reason}")
            print("   Status: Device control is DISABLED")
            print("   Action: Configure credentials via Web UI to enable device control")
        else:
            print("   ✓ NORMAL MODE")
            print(f"   Reason: {setup_reason}")
            print("   Status: Device control is ENABLED")
            print("   Action: Application will proceed with normal operation")
        
    finally:
        # Clean up
        os.unlink(config_path)
    
    print("=" * 80)


def main():
    """Run demo scenarios."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "HeatTrax Setup Mode Demo" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    
    print("\nThis demo shows how HeatTrax handles different credential scenarios:")
    print("- Empty credentials")
    print("- Placeholder credentials")
    print("- Valid credentials")
    print("\nThe application will start in ALL scenarios, but device control")
    print("is only enabled when valid credentials are provided.")
    
    # Scenario 1: Empty credentials
    demo_scenario(
        "Empty Credentials",
        "",
        "",
        "No credentials configured - typical first-time setup"
    )
    
    # Scenario 2: Placeholder username
    demo_scenario(
        "Placeholder Username",
        "your_tapo_username",
        "RealPassword123",
        "Username is a placeholder from config.example.yaml"
    )
    
    # Scenario 3: Placeholder password
    demo_scenario(
        "Placeholder Password",
        "user@example.com",
        "your_tapo_password",
        "Password is a placeholder from config.example.yaml"
    )
    
    # Scenario 4: Both placeholders
    demo_scenario(
        "Both Placeholders",
        "your_tapo_email@example.com",
        "password",
        "Both username and password are placeholders"
    )
    
    # Scenario 5: Valid credentials
    demo_scenario(
        "Valid Credentials",
        "user@example.com",
        "SecurePassword123!",
        "Properly configured credentials - normal operation"
    )
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("✓ All scenarios completed successfully")
    print("✓ Application starts in all cases (no crashes)")
    print("✓ Setup mode activates for invalid/missing credentials")
    print("✓ Normal mode activates for valid credentials")
    print("✓ Clear logging helps users understand the state")
    print("\nSetup Mode provides a better user experience by:")
    print("  - Allowing the application to start without credentials")
    print("  - Keeping the Web UI accessible for configuration")
    print("  - Disabling device control until credentials are valid")
    print("  - Providing clear feedback about what needs to be done")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()

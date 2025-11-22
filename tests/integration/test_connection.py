#!/usr/bin/env python3
"""
Test utility to verify Tapo device connection and configuration.
Run this before starting the scheduler to ensure everything is set up correctly.
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config.config_loader import Config, ConfigError
from src.devices.device_controller import TapoController, DeviceControllerError
from src.weather.weather_service import WeatherService, WeatherServiceError


async def test_device_connection(config: Config):
    """Test connection to Tapo device."""
    print("\n" + "=" * 60)
    print("Testing Tapo Device Connection")
    print("=" * 60)
    
    try:
        controller = TapoController(
            ip_address=config.device['ip_address'],
            username=config.device['username'],
            password=config.device['password']
        )
        
        print(f"Connecting to device at {config.device['ip_address']}...")
        await controller.initialize()
        
        print("✓ Successfully connected to device!")
        
        # Get device state
        state = await controller.get_state()
        print(f"✓ Device is currently: {'ON' if state else 'OFF'}")
        
        await controller.close()
        return True
        
    except DeviceControllerError as e:
        print(f"✗ Device connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check if IP address is correct")
        print("  2. Verify device is powered on and connected to network")
        print("  3. Ensure username and password are correct")
        print("  4. Try accessing device through Tapo app first")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


async def test_weather_service(config: Config):
    """Test weather service API."""
    print("\n" + "=" * 60)
    print("Testing Weather Service")
    print("=" * 60)
    
    try:
        weather = WeatherService(
            latitude=config.location['latitude'],
            longitude=config.location['longitude'],
            timezone=config.location.get('timezone', 'auto')
        )
        
        print(f"Location: {config.location['latitude']}, {config.location['longitude']}")
        print("Fetching current weather...")
        
        temp, precip = await weather.get_current_conditions()
        print(f"✓ Current temperature: {temp}°F")
        print(f"✓ Current precipitation: {precip}mm")
        
        print("\nChecking forecast for precipitation...")
        has_precip, precip_time, forecast_temp = await weather.check_precipitation_forecast(
            hours_ahead=config.scheduler['forecast_hours'],
            temperature_threshold_f=config.thresholds['temperature_f']
        )
        
        if has_precip:
            print(f"✓ Precipitation expected at {precip_time}")
            print(f"  Temperature: {forecast_temp}°F")
            print(f"  Below threshold: {config.thresholds['temperature_f']}°F")
            print("  → Mats would be scheduled to turn ON")
        else:
            print(f"✓ No precipitation expected below {config.thresholds['temperature_f']}°F")
            print("  → Mats would stay OFF")
        
        return True
        
    except WeatherServiceError as e:
        print(f"✗ Weather service failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check internet connection")
        print("  2. Verify latitude and longitude are correct")
        print("  3. Ensure coordinates are not swapped (lat, lon)")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def test_configuration():
    """Test configuration loading."""
    print("=" * 60)
    print("Testing Configuration")
    print("=" * 60)
    
    try:
        config = Config()
        print("✓ Configuration file loaded successfully")
        
        print("\nLocation Settings:")
        print(f"  Latitude: {config.location['latitude']}")
        print(f"  Longitude: {config.location['longitude']}")
        print(f"  Timezone: {config.location.get('timezone', 'auto')}")
        
        print("\nDevice Settings:")
        print(f"  IP Address: {config.device['ip_address']}")
        print(f"  Username: {config.device['username']}")
        print(f"  Password: {'*' * len(config.device['password'])}")
        
        print("\nThresholds:")
        print(f"  Temperature: {config.thresholds['temperature_f']}°F")
        print(f"  Lead time: {config.thresholds['lead_time_minutes']} minutes")
        print(f"  Trailing time: {config.thresholds['trailing_time_minutes']} minutes")
        
        print("\nMorning Mode:")
        if config.morning_mode.get('enabled', False):
            print(f"  Enabled: Yes")
            print(f"  Time: {config.morning_mode['start_hour']}:00 - {config.morning_mode['end_hour']}:00")
        else:
            print(f"  Enabled: No")
        
        print("\nSafety Settings:")
        print(f"  Max runtime: {config.safety['max_runtime_hours']} hours")
        print(f"  Cooldown: {config.safety['cooldown_minutes']} minutes")
        
        return config
        
    except ConfigError as e:
        print(f"✗ Configuration error: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure config.yaml exists")
        print("  2. Copy config.example.yaml to config.yaml if needed")
        print("  3. Check YAML syntax is correct")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None


async def run_tests(skip_device=False, skip_weather=False):
    """Run all tests."""
    print("\n" + "=" * 60)
    print("HeatTrax Scheduler Connection Test")
    print("=" * 60)
    
    # Test configuration
    config = test_configuration()
    if not config:
        print("\n❌ Configuration test failed. Fix configuration before proceeding.")
        return False
    
    results = []
    
    # Test device connection
    if not skip_device:
        device_ok = await test_device_connection(config)
        results.append(("Device Connection", device_ok))
    
    # Test weather service
    if not skip_weather:
        weather_ok = await test_weather_service(config)
        results.append(("Weather Service", weather_ok))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✓ All tests passed! Your scheduler is ready to run.")
        print("\nStart the scheduler with:")
        print("  Docker: docker-compose up -d")
        print("  Python: python main.py")
    else:
        print("\n✗ Some tests failed. Please fix the issues above before running the scheduler.")
    
    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test HeatTrax scheduler configuration and connections"
    )
    parser.add_argument(
        '--skip-device',
        action='store_true',
        help='Skip device connection test'
    )
    parser.add_argument(
        '--skip-weather',
        action='store_true',
        help='Skip weather service test'
    )
    
    args = parser.parse_args()
    
    success = asyncio.run(run_tests(
        skip_device=args.skip_device,
        skip_weather=args.skip_weather
    ))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

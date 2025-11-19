#!/usr/bin/env python3
"""
Manual verification script for automation overrides functionality.
Tests API endpoints and automation override behavior.
"""

import requests
import json
import sys
from pprint import pprint

BASE_URL = "http://127.0.0.1:4328"


def test_get_automation(group_name):
    """Test GET /api/groups/{group}/automation."""
    print(f"\n{'='*60}")
    print(f"Testing GET /api/groups/{group_name}/automation")
    print('='*60)
    
    url = f"{BASE_URL}/api/groups/{group_name}/automation"
    response = requests.get(url)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("\nResponse:")
        pprint(data, indent=2)
        return data
    else:
        print(f"Error: {response.text}")
        return None


def test_patch_automation(group_name, updates):
    """Test PATCH /api/groups/{group}/automation."""
    print(f"\n{'='*60}")
    print(f"Testing PATCH /api/groups/{group_name}/automation")
    print('='*60)
    print(f"Updates: {updates}")
    
    url = f"{BASE_URL}/api/groups/{group_name}/automation"
    response = requests.patch(url, json=updates)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("\nResponse:")
        pprint(data, indent=2)
        return data
    else:
        print(f"Error: {response.text}")
        return None


def verify_effective_automation(data, expected):
    """Verify that effective automation matches expected values."""
    print("\nVerifying effective automation...")
    
    effective = data.get('effective', {})
    for flag, expected_value in expected.items():
        actual_value = effective.get(flag)
        status = "✓" if actual_value == expected_value else "✗"
        print(f"  {status} {flag}: expected={expected_value}, actual={actual_value}")
        
        if actual_value != expected_value:
            return False
    
    return True


def main():
    """Run manual verification tests."""
    print("="*60)
    print("AUTOMATION OVERRIDES MANUAL VERIFICATION")
    print("="*60)
    print("\nNote: This requires the web server to be running.")
    print("Start it with: python main.py --config /tmp/test_config.yaml")
    print("\nPress Enter when ready, or Ctrl+C to exit...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nAborted.")
        return
    
    # Test 1: Get initial state
    print("\n" + "="*60)
    print("TEST 1: Get Initial Automation State")
    print("="*60)
    
    data = test_get_automation("heattrax")
    if not data:
        print("Failed to get automation data")
        return
    
    # Verify base config matches what we expect
    expected_base = {
        'weather_control': True,
        'precipitation_control': True,
        'morning_mode': True,
        'schedule_control': False
    }
    
    print("\nVerifying base config...")
    base = data.get('base', {})
    for flag, expected_value in expected_base.items():
        actual_value = base.get(flag)
        status = "✓" if actual_value == expected_value else "✗"
        print(f"  {status} {flag}: expected={expected_value}, actual={actual_value}")
    
    # Test 2: Override morning_mode to False
    print("\n" + "="*60)
    print("TEST 2: Override morning_mode to False")
    print("="*60)
    
    data = test_patch_automation("heattrax", {"morning_mode": False})
    if data:
        expected_effective = {
            'weather_control': True,
            'precipitation_control': True,
            'morning_mode': False,  # Overridden
            'schedule_control': False
        }
        verify_effective_automation(data, expected_effective)
    
    # Test 3: Override schedule_control to True
    print("\n" + "="*60)
    print("TEST 3: Override schedule_control to True")
    print("="*60)
    
    data = test_patch_automation("heattrax", {"schedule_control": True})
    if data:
        expected_effective = {
            'weather_control': True,
            'precipitation_control': True,
            'morning_mode': False,  # Still overridden
            'schedule_control': True  # Now overridden
        }
        verify_effective_automation(data, expected_effective)
    
    # Test 4: Clear morning_mode override
    print("\n" + "="*60)
    print("TEST 4: Clear morning_mode Override")
    print("="*60)
    
    data = test_patch_automation("heattrax", {"morning_mode": None})
    if data:
        expected_effective = {
            'weather_control': True,
            'precipitation_control': True,
            'morning_mode': True,  # Back to base value
            'schedule_control': True  # Still overridden
        }
        verify_effective_automation(data, expected_effective)
    
    # Test 5: Test group with schedule
    print("\n" + "="*60)
    print("TEST 5: Test Group with Schedule")
    print("="*60)
    
    data = test_get_automation("christmas_lights")
    if data:
        schedule = data.get('schedule', {})
        print(f"\nSchedule info:")
        print(f"  Valid: {schedule.get('valid')}")
        print(f"  On Time: {schedule.get('on_time')}")
        print(f"  Off Time: {schedule.get('off_time')}")
    
    # Test 6: Test nonexistent group
    print("\n" + "="*60)
    print("TEST 6: Test Nonexistent Group")
    print("="*60)
    
    test_get_automation("nonexistent")
    
    print("\n" + "="*60)
    print("VERIFICATION COMPLETE")
    print("="*60)
    print("\nAll tests completed. Check results above.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Integration test simulating complete UI workflow for device groups.
"""

import os
import sys
import yaml
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config_manager import ConfigManager


def test_device_groups_workflow():
    """Test complete workflow of device groups management."""
    print("=" * 80)
    print("Integration Test: Device Groups Workflow")
    print("=" * 80)
    
    # Create temp config
    test_dir = tempfile.mkdtemp()
    config_path = Path(test_dir) / "test_config.yaml"
    
    # Start with minimal config
    initial_config = {
        'location': {'latitude': 40.7128, 'longitude': -74.0060, 'timezone': 'America/New_York'},
        'devices': {
            'credentials': {'username': 'test_user', 'password': 'test_pass'},
            'groups': {}
        },
        'weather_api': {'enabled': True, 'provider': 'open-meteo'},
        'thresholds': {'temperature_f': 34, 'lead_time_minutes': 60, 'trailing_time_minutes': 60},
        'safety': {'max_runtime_hours': 6, 'cooldown_minutes': 30},
        'scheduler': {'check_interval_minutes': 10, 'forecast_hours': 12},
        'logging': {'level': 'INFO'}
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(initial_config, f)
    
    # Create config manager
    cm = ConfigManager(str(config_path))
    
    print("\n1. Initial state - no groups")
    config = cm.get_config(include_secrets=True)
    assert len(config['devices']['groups']) == 0
    print("   ✓ No groups configured")
    
    # Simulate adding first group via UI
    print("\n2. Add 'heated_mats' group via UI")
    config['devices']['groups']['heated_mats'] = {
        'enabled': True,
        'items': [
            {'name': 'Front Mat', 'ip_address': '192.168.1.100', 'outlets': [0, 1]},
            {'name': 'Back Mat', 'ip_address': '192.168.1.101'}
        ]
    }
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'ok'
    print("   ✓ Group added successfully")
    
    # Verify it was saved
    print("\n3. Verify group was saved to disk")
    with open(config_path, 'r') as f:
        saved_config = yaml.safe_load(f)
    assert 'heated_mats' in saved_config['devices']['groups']
    assert len(saved_config['devices']['groups']['heated_mats']['items']) == 2
    print("   ✓ Group persisted to YAML file")
    
    # Simulate adding device to existing group
    print("\n4. Add device to existing group")
    config = cm.get_config(include_secrets=True)
    config['devices']['groups']['heated_mats']['items'].append({
        'name': 'Side Mat',
        'ip_address': '192.168.1.102',
        'outlets': [0]
    })
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'ok'
    print("   ✓ Device added successfully")
    
    # Simulate adding second group
    print("\n5. Add 'christmas_lights' group")
    config = cm.get_config(include_secrets=True)
    config['devices']['groups']['christmas_lights'] = {
        'enabled': False,
        'items': [
            {'name': 'Tree Lights', 'ip_address': '192.168.1.200'}
        ]
    }
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'ok'
    print("   ✓ Second group added successfully")
    
    # Verify both groups exist
    print("\n6. Verify multiple groups")
    config = cm.get_config(include_secrets=True)
    groups = config['devices']['groups']
    assert len(groups) == 2
    assert 'heated_mats' in groups
    assert 'christmas_lights' in groups
    assert len(groups['heated_mats']['items']) == 3
    assert len(groups['christmas_lights']['items']) == 1
    assert groups['heated_mats']['enabled'] == True
    assert groups['christmas_lights']['enabled'] == False
    print("   ✓ Both groups present with correct data")
    
    # Simulate removing device from group
    print("\n7. Remove device from group")
    config['devices']['groups']['heated_mats']['items'].pop(1)  # Remove Back Mat
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'ok'
    config = cm.get_config(include_secrets=True)
    assert len(config['devices']['groups']['heated_mats']['items']) == 2
    print("   ✓ Device removed successfully")
    
    # Simulate deleting entire group
    print("\n8. Delete entire group")
    config = cm.get_config(include_secrets=True)
    del config['devices']['groups']['christmas_lights']
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'ok'
    config = cm.get_config(include_secrets=True)
    assert 'christmas_lights' not in config['devices']['groups']
    assert 'heated_mats' in config['devices']['groups']
    print("   ✓ Group deleted successfully")
    
    # Test validation errors
    print("\n9. Test validation - empty device name")
    config = cm.get_config(include_secrets=True)
    config['devices']['groups']['heated_mats']['items'].append({
        'name': '',  # Invalid - empty name
        'ip_address': '192.168.1.103'
    })
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'error'
    assert 'name' in result['message'].lower()
    print("   ✓ Empty name validation working")
    
    print("\n10. Test validation - missing IP address")
    config = cm.get_config(include_secrets=True)
    config['devices']['groups']['heated_mats']['items'].append({
        'name': 'Test Device'
        # Missing ip_address
    })
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'error'
    assert 'ip_address' in result['message'].lower()
    print("   ✓ Missing IP address validation working")
    
    print("\n11. Test validation - invalid outlets")
    config = cm.get_config(include_secrets=True)
    config['devices']['groups']['heated_mats']['items'].append({
        'name': 'Test Device',
        'ip_address': '192.168.1.103',
        'outlets': [-1]  # Invalid - negative outlet
    })
    result = cm.update_config(config, preserve_secrets=True)
    assert result['status'] == 'error'
    assert 'non-negative integer' in result['message'].lower()
    print("   ✓ Invalid outlets validation working")
    
    # Clean up
    import shutil
    shutil.rmtree(test_dir)
    
    print("\n" + "=" * 80)
    print("✅ All integration tests passed!")
    print("=" * 80)


if __name__ == '__main__':
    test_device_groups_workflow()

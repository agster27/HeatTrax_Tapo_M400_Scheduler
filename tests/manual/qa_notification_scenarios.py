#!/usr/bin/env python3
"""
Manual QA scenarios for notification system enhancements.

Run this script to validate different notification configuration scenarios.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.notifications.notification_service import (
    create_notification_service_from_config,
    validate_and_test_notifications,
    NotificationValidationError
)


def print_scenario(name: str):
    """Print scenario header."""
    print("\n" + "=" * 80)
    print(f"SCENARIO: {name}")
    print("=" * 80)


async def scenario_all_disabled():
    """Scenario: All notifications disabled."""
    print_scenario("All Notifications Disabled")
    
    config = {
        'email': {'enabled': False},
        'webhook': {'enabled': False}
    }
    
    try:
        service = create_notification_service_from_config(config)
        print(f"✓ Service created successfully")
        print(f"  Providers enabled: {service.is_enabled()}")
        print(f"  Provider count: {len(service.providers)}")
        print("✓ PASS: All notifications disabled works as expected")
        return True
    except Exception as e:
        print(f"✗ FAIL: Unexpected error: {e}")
        return False


async def scenario_email_misconfigured():
    """Scenario: Email enabled but misconfigured."""
    print_scenario("Email Misconfigured")
    
    config = {
        'email': {
            'enabled': True,
            'smtp_host': 'smtp.example.com'
            # Missing other required fields
        }
    }
    
    try:
        service = create_notification_service_from_config(config)
        print(f"✗ FAIL: Should have raised NotificationValidationError")
        return False
    except NotificationValidationError as e:
        print(f"✓ Expected validation error raised: {e}")
        print("✓ PASS: Misconfigured email properly validated")
        return True
    except Exception as e:
        print(f"✗ FAIL: Unexpected error type: {type(e).__name__}: {e}")
        return False


async def scenario_valid_config_no_connectivity():
    """Scenario: Valid configuration without connectivity test."""
    print_scenario("Valid Configuration (no connectivity test)")
    
    config = {
        'email': {
            'enabled': True,
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_username': 'user@example.com',
            'smtp_password': 'password',
            'from_email': 'from@example.com',
            'to_emails': ['to@example.com'],
            'use_tls': True
        },
        'webhook': {
            'enabled': True,
            'url': 'https://example.com/webhook'
        }
    }
    
    try:
        success, service = await validate_and_test_notifications(
            config,
            test_connectivity=False,
            send_test=False
        )
        
        if success and service:
            print(f"✓ Service created successfully")
            print(f"  Providers: {list(service.providers.keys())}")
            print(f"  Provider count: {len(service.providers)}")
            print("✓ PASS: Valid configuration accepted")
            return True
        else:
            print(f"✗ FAIL: Validation should have succeeded")
            return False
    except Exception as e:
        print(f"✗ FAIL: Unexpected error: {type(e).__name__}: {e}")
        return False


async def scenario_routing_configuration():
    """Scenario: Per-event routing configuration."""
    print_scenario("Per-Event Routing Configuration")
    
    config = {
        'routing': {
            'device_lost': {'email': True, 'webhook': False},
            'device_ip_changed': {'email': True, 'webhook': True}
        },
        'email': {
            'enabled': True,
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_username': 'user@example.com',
            'smtp_password': 'password',
            'from_email': 'from@example.com',
            'to_emails': ['to@example.com']
        },
        'webhook': {
            'enabled': True,
            'url': 'https://example.com/webhook'
        }
    }
    
    try:
        service = create_notification_service_from_config(config)
        
        print(f"✓ Service created with routing")
        print(f"  Routing config: {service.routing}")
        
        # Test routing logic
        providers_lost = service.get_providers_for_event('device_lost')
        print(f"  device_lost routes to: {[name for name, _ in providers_lost]}")
        
        providers_ip = service.get_providers_for_event('device_ip_changed')
        print(f"  device_ip_changed routes to: {[name for name, _ in providers_ip]}")
        
        providers_unknown = service.get_providers_for_event('unknown_event')
        print(f"  unknown_event routes to: {[name for name, _ in providers_unknown]}")
        
        # Validate routing works as expected
        if len(providers_lost) == 1 and providers_lost[0][0] == 'email':
            print("✓ device_lost routing correct (email only)")
        else:
            print(f"✗ device_lost routing incorrect: {providers_lost}")
            return False
        
        if len(providers_ip) == 2:
            print("✓ device_ip_changed routing correct (both providers)")
        else:
            print(f"✗ device_ip_changed routing incorrect: {providers_ip}")
            return False
        
        if len(providers_unknown) == 2:
            print("✓ unknown_event routing correct (default to all)")
        else:
            print(f"✗ unknown_event routing incorrect: {providers_unknown}")
            return False
        
        print("✓ PASS: Routing configuration works correctly")
        return True
        
    except Exception as e:
        print(f"✗ FAIL: Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def scenario_webhook_invalid_url():
    """Scenario: Webhook with invalid URL."""
    print_scenario("Webhook Invalid URL")
    
    config = {
        'webhook': {
            'enabled': True,
            'url': 'not-a-valid-url'
        }
    }
    
    try:
        service = create_notification_service_from_config(config)
        print(f"✗ FAIL: Should have raised NotificationValidationError")
        return False
    except NotificationValidationError as e:
        print(f"✓ Expected validation error raised: {e}")
        print("✓ PASS: Invalid webhook URL properly validated")
        return True
    except Exception as e:
        print(f"✗ FAIL: Unexpected error type: {type(e).__name__}: {e}")
        return False


async def run_all_scenarios():
    """Run all QA scenarios."""
    print("\n" + "=" * 80)
    print("NOTIFICATION SYSTEM QA SCENARIOS")
    print("=" * 80)
    
    scenarios = [
        ("All Disabled", scenario_all_disabled),
        ("Email Misconfigured", scenario_email_misconfigured),
        ("Valid Config", scenario_valid_config_no_connectivity),
        ("Routing Config", scenario_routing_configuration),
        ("Invalid Webhook URL", scenario_webhook_invalid_url),
    ]
    
    results = []
    for name, scenario_func in scenarios:
        result = await scenario_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "=" * 80)
    print("QA SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} scenarios passed")
    
    if passed == total:
        print("\n✓ All QA scenarios passed!")
        return True
    else:
        print(f"\n✗ {total - passed} scenario(s) failed")
        return False


if __name__ == '__main__':
    success = asyncio.run(run_all_scenarios())
    sys.exit(0 if success else 1)

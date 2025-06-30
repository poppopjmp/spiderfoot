#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for SpiderFoot microservice architecture.

This script tests the basic functionality of the microservices:
- Service Discovery
- Configuration Service
- Service communication
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

async def test_service_discovery():
    """Test service discovery functionality."""
    print("Testing Service Discovery...")
    
    try:
        import httpx
        
        # Test health check
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("✓ Service Discovery health check passed")
            else:
                print(f"✗ Service Discovery health check failed: {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Service Discovery test failed: {e}")
        return False

async def test_config_service():
    """Test configuration service functionality."""
    print("Testing Configuration Service...")
    
    try:
        import httpx
        
        # Test health check
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8001/health")
            if response.status_code == 200:
                print("✓ Configuration Service health check passed")
            else:
                print(f"✗ Configuration Service health check failed: {response.status_code}")
                return False
            
            # Test setting a configuration
            test_config = {
                "key": "test_key",
                "value": "test_value",
                "scope": "test",
                "description": "Test configuration"
            }
            
            response = await client.post("http://localhost:8001/config/test_key", json=test_config)
            if response.status_code == 200:
                print("✓ Configuration Service set config passed")
            else:
                print(f"✗ Configuration Service set config failed: {response.status_code}")
                return False
            
            # Test getting the configuration
            response = await client.get("http://localhost:8001/config/test_key?scope=test")
            if response.status_code == 200:
                data = response.json()
                if data.get("value") == "test_value":
                    print("✓ Configuration Service get config passed")
                else:
                    print(f"✗ Configuration Service get config returned wrong value: {data}")
                    return False
            else:
                print(f"✗ Configuration Service get config failed: {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration Service test failed: {e}")
        return False

async def test_service_communication():
    """Test service-to-service communication."""
    print("Testing Service Communication...")
    
    try:
        from services.client import SyncConfigServiceClient
        
        # Create a client
        client = SyncConfigServiceClient("http://localhost:8000")
        
        # Test setting and getting configuration
        success = client.set_config("microservice_test", "communication_works", "test", "Test communication")
        if success:
            print("✓ Service client set config passed")
        else:
            print("✗ Service client set config failed")
            return False
        
        value = client.get_config("microservice_test", "test")
        if value and value.get("value") == "communication_works":
            print("✓ Service client get config passed")
        else:
            print(f"✗ Service client get config failed: {value}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Service communication test failed: {e}")
        return False

def test_legacy_integration():
    """Test integration with legacy SpiderFoot code."""
    print("Testing Legacy Integration...")
    
    try:
        # Set environment variable to enable microservices
        import os
        os.environ['USE_MICROSERVICES'] = 'true'
        os.environ['SERVICE_DISCOVERY_URL'] = 'http://localhost:8000'
        
        from sflib import SpiderFoot
        
        # Create SpiderFoot instance with microservice support
        sf = SpiderFoot({
            '_debug': False,
            '_maxthreads': 3,
            '__logging': True
        })
        
        # Test configuration methods
        success = sf.configSet("legacy_test", "integration_works", "test", "Test legacy integration")
        if success:
            print("✓ Legacy integration set config passed")
        else:
            print("✗ Legacy integration set config failed")
            return False
        
        value = sf.configGet("legacy_test", "test")
        if value == "integration_works":
            print("✓ Legacy integration get config passed")
        else:
            print(f"✗ Legacy integration get config failed: {value}")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Legacy integration test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("SpiderFoot Microservice Architecture Test")
    print("=" * 50)
    
    tests = [
        ("Service Discovery", test_service_discovery()),
        ("Configuration Service", test_config_service()),
        ("Service Communication", test_service_communication()),
        ("Legacy Integration", test_legacy_integration())
    ]
    
    results = []
    for test_name, test_coro in tests:
        print(f"\n{test_name}:")
        try:
            if asyncio.iscoroutine(test_coro):
                result = await test_coro
            else:
                result = test_coro
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Microservice architecture is working correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
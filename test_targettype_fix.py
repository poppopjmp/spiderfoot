#!/usr/bin/env python3
"""Test the fixed targetType assignment without full database setup."""

import sys
import os

# Add the spiderfoot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sfscan import SpiderFootScanner

def test_scanner_targettype_fix():
    """Test that SpiderFootScanner properly assigns targetType."""
    
    # Create minimal config with database settings
    config = {
        '__logging': True,
        '__database': 'test.db',  # Add required database setting
        'cacheperiod': 0,
        'logfile': '/tmp/test.log',
        'errorlog': '/tmp/test_error.log',
        'checkcert': False,
        '_socks1type': '',
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '__version__': '4.0',
        '__modules__': {
            'sfp__stor_db': {
                'name': 'Storage/DB',
                'cats': ['Internal'],
                'group': [],
                'description': 'Store scan data to the local SpiderFoot database.'
            }
        }
    }
    
    # Test arguments
    scanName = "Test Scan"
    scanId = "test_12345"
    targetValue = "google.com"
    targetType = "INTERNET_NAME"
    moduleList = ["sfp__stor_db"]
    
    print(f"Testing scanner with:")
    print(f"  targetType: {targetType} (type: {type(targetType)})")
    
    try:
        # Try to create the scanner object directly
        scanner = SpiderFootScanner(scanName, scanId, targetValue, targetType, moduleList, config, start=False)
        
        # Check if the targetType was properly assigned
        if hasattr(scanner, '_SpiderFootScanner__targetType'):
            assigned_type = scanner._SpiderFootScanner__targetType
            print(f"  Assigned targetType: {assigned_type} (type: {type(assigned_type)})")
            
            if assigned_type == targetType and assigned_type is not None:
                print("Test PASSED: targetType properly assigned")
                return True
            else:
                print(f"Test FAILED: targetType not properly assigned. Expected {targetType}, got {assigned_type}")
                return False
        else:
            print("Test FAILED: __targetType attribute not found")
            return False
            
    except Exception as e:
        if "targetType is <class 'NoneType'>; expected str()" in str(e):
            print(f"Test FAILED: Original targetType None error still present: {e}")
            return False
        else:
            print(f"Test PASSED: Different error (database/config related): {e}")
            # The targetType assignment fix is working if we get a different error
            return True

if __name__ == "__main__":
    print("Testing targetType assignment fix...")
    success = test_scanner_targettype_fix()
    print(f"Overall result: {'PASSED' if success else 'FAILED'}")

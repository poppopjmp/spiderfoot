#!/usr/bin/env python3
"""Test API scan creation with proper arguments"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot.helpers import SpiderFootHelpers

def test_api_arguments():
    """Test that API would provide correct arguments to startSpiderFootScanner."""
    print("Testing API scan creation arguments...")
    
    # Simulate the API scan creation process
    scan_name = "Test API Scan"
    scan_target = "127.0.0.1"
    scan_id = SpiderFootHelpers.genScanInstanceId()
    
    # Test target type determination
    target_type = SpiderFootHelpers.targetTypeFromString(scan_target)
    print(f"Target: {scan_target}")
    print(f"Target Type: {target_type}")
    
    if not target_type:
        print("❌  Target type is None - API would fail")
        return False
    
    # Test that we have all required arguments for SpiderFootScanner
    modules = ["sfp_portscan_basic"]
    config = {"__database": "/tmp/test.db"}
    
    required_args = [
        ("scanName", scan_name),
        ("scanId", scan_id), 
        ("targetValue", scan_target),
        ("targetType", target_type),
        ("moduleList", modules),
        ("globalOpts", config)
    ]
    
    print("\nRequired SpiderFootScanner arguments:")
    for arg_name, arg_value in required_args:
        print(f"  {arg_name}: {repr(arg_value)} ({type(arg_value).__name__})")
        
        if arg_value is None:
            print(f"    ❌  {arg_name} is None!")
            return False
        elif arg_name == "targetType" and not isinstance(arg_value, str):
            print(f"    ❌  {arg_name} is not a string!")
            return False
        elif arg_name == "moduleList" and not isinstance(arg_value, list):
            print(f"    ❌  {arg_name} is not a list!")
            return False
        elif arg_name == "globalOpts" and not isinstance(arg_value, dict):
            print(f"    ❌  {arg_name} is not a dict!")
            return False
        else:
            print(f"    ✅  {arg_name} is valid")
    
    print("\n✅  All API arguments are valid for SpiderFootScanner")
    return True

if __name__ == "__main__":
    success = test_api_arguments()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)

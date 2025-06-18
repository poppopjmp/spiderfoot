#!/usr/bin/env python3
"""Test the targetType None error scenario"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from sfscan import SpiderFootScanner

def test_none_target_type():
    """Test what happens when targetType is None."""
    print("Testing None targetType scenario...")
    
    try:
        # This should fail with the specific error we're trying to fix
        scanner = SpiderFootScanner(
            scanName="test_scan",
            scanId="test_scan_123",
            targetValue="127.0.0.1",
            targetType=None,  # This is the problem!
            moduleList=["sfp_portscan_basic"],
            globalOpts={'__database': '/tmp/test.db'},
            start=False
        )
        print("❌  ERROR: Scanner creation should have failed!")
        return False
        
    except TypeError as e:
        if "targetType is <class 'NoneType'>; expected str()" in str(e):
            print("✅  Correct! TypeError caught as expected:")
            print(f"    {e}")
            return True
        else:
            print(f"❌  Unexpected TypeError: {e}")
            return False
            
    except ValueError as e:
        if "Invalid target" in str(e):
            print("✅  Correct! ValueError caught as expected:")
            print(f"    {e}")
            return True
        else:
            print(f"❌  Unexpected ValueError: {e}")
            return False
            
    except Exception as e:
        print(f"❌  Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_none_target_type()
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)

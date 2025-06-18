#!/usr/bin/env python3
"""Simple test to debug queue initialization issue"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot import SpiderFootDb
from sfscan import SpiderFootScanner
import tempfile

def test_simple_scan():
    """Test a simple scan to debug the queue issue."""
    print("Testing simple scan...")
    
    # Create a temporary database
    db_file = tempfile.mktemp()
    print(f"Using temporary database: {db_file}")
    
    try:
        # Create basic config
        config = {
            '__database': db_file,
            '__modules__': {
                'sfp_portscan_basic': {'opts': {}},  # Simple module
            },
            '__outputfilter': None,
            '__correlationrules__': []
        }
          # Simple scan config
        scan_name = "test_scan"
        scan_id = "test_scan_123"
        scan_target = "127.0.0.1"
        target_type = "IP_ADDRESS"
        module_list = ["sfp_portscan_basic"]
        
        print(f"Starting scan of {scan_target}")
        
        # This should trigger the queue setup
        scanner = SpiderFootScanner(scan_name, scan_id, scan_target, target_type, module_list, config, start=False)
        
        print("Scan setup completed")
        return True
        
    except Exception as e:
        print(f"Error during scan test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
        except:
            pass

if __name__ == "__main__":
    success = test_simple_scan()
    sys.exit(0 if success else 1)

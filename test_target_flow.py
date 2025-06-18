#!/usr/bin/env python3
"""Test target type flow end-to-end"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot import SpiderFootDb
from spiderfoot.helpers import SpiderFootHelpers

def test_target_flow():
    """Test the complete target flow from storage to retrieval."""
    print("Testing target flow end-to-end...")
    
    # Create a temporary database
    db_file = tempfile.mktemp()
    print(f"Using temporary database: {db_file}")
    
    try:
        # Initialize database
        db_config = {'__database': db_file}
        dbh = SpiderFootDb(db_config)
        
        # Test various target scenarios
        test_cases = [
            ("test_scan_1", "127.0.0.1"),
            ("test_scan_2", "example.com"),
            ("test_scan_3", ""),  # Empty target
            ("test_scan_4", None),  # None target
        ]
        
        for scan_name, target in test_cases:
            print(f"\nTesting scan: {scan_name} with target: {repr(target)}")
            
            # Generate scan ID
            scan_id = SpiderFootHelpers.genScanInstanceId()
            
            try:
                # Try to create scan instance
                if target is None:
                    print("  Skipping None target (would cause database error)")
                    continue
                    
                dbh.scanInstanceCreate(scan_id, scan_name, target)
                print(f"  ✅  Created scan {scan_id}")
                
                # Retrieve scan info
                info = dbh.scanInstanceGet(scan_id)
                if info:
                    retrieved_name = info[0]
                    retrieved_target = info[1]
                    print(f"  Retrieved: name='{retrieved_name}', target='{retrieved_target}'")
                    
                    # Test target type determination
                    if retrieved_target:
                        target_type = SpiderFootHelpers.targetTypeFromString(retrieved_target)
                        print(f"  Target type: {target_type}")
                        
                        if target_type is None:
                            print(f"  ❌  Target type is None for '{retrieved_target}'")
                        else:
                            print(f"  ✅  Valid target type: {target_type}")
                    else:
                        print(f"  ❌  Empty target retrieved from database")
                else:
                    print(f"  ❌  Failed to retrieve scan info")
                    
            except Exception as e:
                print(f"  ❌  Error: {e}")
        
        print("\nTarget flow test completed")
        return True
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            if 'dbh' in locals():
                dbh.dbh.close()
        except:
            pass
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
        except:
            pass

if __name__ == "__main__":
    success = test_target_flow()
    sys.exit(0 if success else 1)

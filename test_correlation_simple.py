#!/usr/bin/env python3
"""Test correlation functionality"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot import SpiderFootDb
import tempfile

def test_correlation_db():
    """Test the correlationResultCreate database method directly."""
    print("Testing correlationResultCreate database method...")
    
    # Create a temporary database
    db_file = tempfile.mktemp()
    print(f"Using temporary database: {db_file}")
    
    try:
        # Initialize database
        db_config = {'__database': db_file}
        dbh = SpiderFootDb(db_config)
        
        # Create a test scan
        import time
        scan_id = str(int(time.time() * 1000000))
        dbh.scanInstanceCreate(scan_id, "test_scan", "127.0.0.1")
        print(f"Created scan: {scan_id}")
        
        # Test the correlationResultCreate method directly
        print("Testing correlationResultCreate method...")
        
        import hashlib
        event_hash = hashlib.sha256("test_correlation_data".encode()).hexdigest()
        event_hashes = ["test_hash_1", "test_hash_2"]
        
        corr_id = dbh.correlationResultCreate(
            scan_id,                    # instanceId
            event_hash,                 # event_hash
            "test_rule_id",            # ruleId
            "Test Rule Name",          # ruleName
            "Test Rule Description",   # ruleDescr
            "INFO",                    # ruleRisk
            "test: yaml content",      # ruleYaml
            "Test Correlation Title",  # correlationTitle
            event_hashes               # eventHashes
        )
        
        print(f"Created correlation with ID: {corr_id}")
          # Check if correlation was stored
        correlations = dbh.scanCorrelationList(scan_id)
        print(f"Found {len(correlations)} correlations")
        
        if correlations:
            print("First correlation details:", correlations[0])
        
        print("Correlation database test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during correlation test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            if 'dbh' in locals():
                dbh.dbh.close()  # Close the database connection
        except:
            pass
        try:
            if os.path.exists(db_file):
                os.unlink(db_file)
        except:
            pass

if __name__ == "__main__":
    success = test_correlation_db()
    sys.exit(0 if success else 1)

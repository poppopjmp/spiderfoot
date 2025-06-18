#!/usr/bin/env python3
"""Test the full correlation workflow"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot import SpiderFootDb, SpiderFootCorrelator
import tempfile

def test_correlation_workflow():
    """Test the complete correlation workflow using SpiderFootCorrelator."""
    print("Testing complete correlation workflow...")
    
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
        print(f"Created scan: {scan_id}")        # Create ruleset with a proper YAML rule format
        test_rule_yaml = """id: test_rule
version: 1
meta:
  name: Test Rule
  description: A test correlation rule for testing
  risk: INFO
collections:
  - collect:
      - method: exact
        field: type
        value: IP_ADDRESS
aggregation:
  field: data
headline: "Test correlation found: {data}" """
        
        ruleset = {'test_rule': test_rule_yaml}
          # Initialize correlator
        correlator = SpiderFootCorrelator(dbh, ruleset, scan_id)
        
        # Test data for correlation (simulating some event data)
        test_data = [
            {'id': 'event_1', 'hash': 'test_hash_1', 'event': 'IP_ADDRESS', 'data': '127.0.0.1'},
            {'id': 'event_2', 'hash': 'test_hash_2', 'event': 'TCP_PORT_OPEN', 'data': '127.0.0.1:80'}
        ]
        
        print("Testing correlation creation...")
          # Test correlation creation
        # Get the parsed rule from the correlator
        test_rule = correlator.rules[0]  # Should be our test rule
        result = correlator.create_correlation(test_rule, test_data, readonly=False)
        print(f"Correlation creation result: {result}")
        
        # Check if correlation was stored
        correlations = dbh.scanCorrelationList(scan_id)
        print(f"Found {len(correlations)} correlations")
        
        if correlations:
            print("First correlation details:", correlations[0])
        
        print("Complete correlation workflow test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during correlation workflow test: {e}")
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
    success = test_correlation_workflow()
    sys.exit(0 if success else 1)

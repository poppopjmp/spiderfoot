#!/usr/bin/env python3
"""Test correlation functionality"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from spiderfoot import SpiderFootDb, SpiderFootCorrelator
import tempfile

def test_correlation():
    """Test basic correlation functionality."""
    print("Testing correlation system...")
    
    # Create a temporary database
    db_file = tempfile.mktemp()
    print(f"Using temporary database: {db_file}")
    
    try:        # Initialize database
        db_config = {'__database': db_file}
        dbh = SpiderFootDb(db_config)
          # Create a test scan
        import time
        scan_id = str(int(time.time() * 1000000))
        dbh.scanInstanceCreate(scan_id, "test_scan", "127.0.0.1")
        print(f"Created scan: {scan_id}")
        
        # Add some test events
        event1_id = dbh.scanEventStore(scan_id, "IP_ADDRESS", "127.0.0.1", "sfp_test", 0, "scan_start", "test_hash_1")
        event2_id = dbh.scanEventStore(scan_id, "TCP_PORT_OPEN", "127.0.0.1:80", "sfp_test", event1_id, "scan_start", "test_hash_2")
        print(f"Created events: {event1_id}, {event2_id}")
        
        # Create a simple correlation rule
        test_rule = {
            'id': 'test_rule',
            'meta': {
                'name': 'Test Rule',
                'description': 'A test correlation rule',
                'risk': 'INFO'
            },
            'rawYaml': 'id: test_rule\nmeta:\n  name: Test Rule\n  description: A test correlation rule\n  risk: INFO\nrule: true',
            'rule': True
        }
        
        # Initialize correlator
        correlator = SpiderFootCorrelator(dbh, scan_id)
        correlator.setOutput("stdout")
        
        # Test data for correlation
        test_data = [
            {'id': event1_id, 'hash': 'test_hash_1'},
            {'id': event2_id, 'hash': 'test_hash_2'}
        ]
        
        # Test correlation creation
        result = correlator.create_correlation(test_rule, test_data, readonly=False)
        print(f"Correlation creation result: {result}")
        
        # Check if correlation was stored
        correlations = dbh.correlationResultList(scan_id)
        print(f"Found {len(correlations)} correlations")
        
        print("Correlation test completed successfully!")
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
    success = test_correlation()
    sys.exit(0 if success else 1)

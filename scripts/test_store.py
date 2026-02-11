"""Test scanEventStore directly with a real SpiderFootEvent."""
import sys
import os
import time
import logging
import traceback

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s : %(message)s')

sys.path.insert(0, '/home/spiderfoot')

from spiderfoot import SpiderFootDb
from spiderfoot.events.event import SpiderFootEvent

# Connect to the same DB
dbh = SpiderFootDb({'__database': '/home/spiderfoot/data/spiderfoot.db'})

# Create a scan instance for testing
scan_id = 'TESTDB01'
try:
    dbh.scanInstanceCreate(scan_id, 'test-store', 'google.com')
    print(f"Created scan instance: {scan_id}")
except Exception as e:
    print(f"Scan instance creation: {e}")

# Create ROOT event
root_event = SpiderFootEvent("ROOT", "google.com", "SpiderFoot", None)
root_event.data = "google.com"
root_event.module = "SpiderFoot"
root_event.confidence = 100
root_event.visibility = 100
root_event.risk = 0

print(f"\nROOT event attrs:")
print(f"  eventType: {root_event.eventType}")
print(f"  data: {root_event.data}")
print(f"  module: {root_event.module}")
print(f"  hash: {root_event.hash}")
print(f"  generated: {root_event.generated} (type: {type(root_event.generated)})")
print(f"  confidence: {root_event.confidence}")
print(f"  visibility: {root_event.visibility}")
print(f"  risk: {root_event.risk}")
print(f"  sourceEventHash: {root_event.sourceEventHash}")

# Try storing ROOT
try:
    dbh.scanEventStore(scan_id, root_event)
    print(f"\nROOT event stored successfully!")
except Exception as e:
    print(f"\nROOT event store FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()

# Create child event
child_event = SpiderFootEvent("INTERNET_NAME", "mail.google.com", "sfp_dnsresolve", root_event)
print(f"\nChild event attrs:")
print(f"  eventType: {child_event.eventType}")
print(f"  data: {child_event.data}")
print(f"  module: {child_event.module}")
print(f"  hash: {child_event.hash}")
print(f"  generated: {child_event.generated} (type: {type(child_event.generated)})")
print(f"  sourceEventHash: {child_event.sourceEventHash}")

try:
    dbh.scanEventStore(scan_id, child_event)
    print(f"\nChild event stored successfully!")
except Exception as e:
    print(f"\nChild event store FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()

# Check results
import sqlite3
conn = sqlite3.connect('/home/spiderfoot/data/spiderfoot.db')
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM tbl_scan_results WHERE scan_instance_id=?", (scan_id,))
print(f"\nResults stored: {c.fetchone()[0]}")
conn.close()

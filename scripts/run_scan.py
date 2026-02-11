"""Start a scan directly inside the container, bypassing WebUI/CSRF."""
import sys
import os
import time
import logging
import multiprocessing

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s : %(message)s')

# Import SpiderFoot
sys.path.insert(0, '/home/spiderfoot')
from spiderfoot.scan_service.scanner import startSpiderFootScanner

scan_name = sys.argv[1] if len(sys.argv) > 1 else 'test-debug'
scan_target = sys.argv[2] if len(sys.argv) > 2 else 'google.com'
modules_str = sys.argv[3] if len(sys.argv) > 3 else 'sfp_dnsresolve,sfp__stor_db'

# Build config - minimal
from spiderfoot import SpiderFootDb, SpiderFoot

dbh = SpiderFootDb({'__database': '/home/spiderfoot/data/spiderfoot.db'})
sf = SpiderFoot({})

# Get default config
defaultCfg = sf.defaultConfig()

# Generate scan ID
import hashlib
scan_id = hashlib.md5(f"{scan_name}{time.time()}".encode()).hexdigest()[:8].upper()

modules = modules_str.split(',')
print(f"Starting scan {scan_id}: target={scan_target}, modules={modules}")

# Create a logging queue for the scanner
logging_queue = multiprocessing.Queue()

# Start scanner in this process (not multiprocessing) for easier debugging
try:
    startSpiderFootScanner(
        logging_queue,
        scan_name,
        scan_id,
        scan_target,
        'INTERNET_NAME',
        modules,
        defaultCfg
    )
except Exception as e:
    print(f"Scanner error: {e}")
    import traceback
    traceback.print_exc()

# Check results
print(f"\nChecking results for scan {scan_id}...")
import sqlite3
conn = sqlite3.connect('/home/spiderfoot/data/spiderfoot.db')
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM tbl_scan_results WHERE scan_instance_id=?", (scan_id,))
count = c.fetchone()[0]
print(f"Result count: {count}")
if count > 0:
    c.execute("SELECT type, COUNT(*) FROM tbl_scan_results WHERE scan_instance_id=? GROUP BY type", (scan_id,))
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")
conn.close()

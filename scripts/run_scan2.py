"""Start scan directly in the container process, simulating WebUI startup."""
import sys
import os
import time
import logging
import hashlib

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s : %(message)s'
)

sys.path.insert(0, '/home/spiderfoot')

from spiderfoot import SpiderFoot, SpiderFootHelpers
from spiderfoot.db import SpiderFootDb
from spiderfoot.scan_service.scanner import SpiderFootScanner

scan_id = hashlib.md5(f"debug{time.time()}".encode()).hexdigest()[:8].upper()
scan_name = 'test-google-com'
scan_target = 'google.com'
target_type = 'INTERNET_NAME'
modules_to_run = ['sfp_dnsresolve', 'sfp_dnsbrute', 'sfp_dnscommonsrv', 'sfp__stor_db']

# Build minimal config with __database key
config = {
    '__database': '/home/spiderfoot/data/spiderfoot.db',
    '__webaddr': '0.0.0.0',
    '__webport': 5001,
    '__docroot': '',
    '_modulesenabled': '',
    '_socks1type': '',
    '_socks2addr': '',
    '_socks3port': '',
    '_socks4user': '',
    '_socks5pass': '',
    '_socks6dns': True,
    '_fetchtimeout': 5,
    '_useragent': 'SpiderFoot',
    '_dnsserver': '',
    '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
    '_internettlds_cache': 72,
    '__logging': 'DEBUG',
    '__version__': '5.3.3',
}

# Load __modules__ exactly like the WebUI does it
mod_dir = '/home/spiderfoot/modules'
if os.path.exists(mod_dir):
    modules = SpiderFootHelpers.loadModulesAsDict(mod_dir, ['sfp_template.py'])
    config['__modules__'] = modules
    print(f"Loaded {len(modules)} module configs into __modules__")
    # Verify our modules are present
    for m in modules_to_run:
        if m in modules:
            print(f"  {m}: FOUND in __modules__")
        else:
            print(f"  {m}: MISSING from __modules__")
else:
    print(f"ERROR: modules dir {mod_dir} not found")
    sys.exit(1)

print(f"\nStarting scan {scan_id}: target={scan_target}, modules={modules_to_run}")

try:
    scanner = SpiderFootScanner(
        scan_name, scan_id, scan_target, target_type,
        modules_to_run, config, start=True
    )
except Exception as e:
    print(f"Scanner error: {e}")
    import traceback
    traceback.print_exc()

# Check results
import sqlite3
conn = sqlite3.connect('/home/spiderfoot/data/spiderfoot.db')
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM tbl_scan_results WHERE scan_instance_id=?", (scan_id,))
count = c.fetchone()[0]
print(f"\n=== Results for scan {scan_id}: {count} rows ===")
if count > 0:
    c.execute("SELECT type, COUNT(*) FROM tbl_scan_results WHERE scan_instance_id=? GROUP BY type", (scan_id,))
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")

# Check scan status
c.execute("SELECT guid, name, status FROM tbl_scan_instance WHERE guid=?", (scan_id,))
inst = c.fetchone()
print(f"Scan status: {inst}")

# ---- Second scan: IP target 1.1.1.1 ----
scan_id2 = hashlib.md5(f"ip{time.time()}".encode()).hexdigest()[:8].upper()
scan_name2 = 'test-1.1.1.1'
scan_target2 = '1.1.1.1'
target_type2 = 'IP_ADDRESS'
modules_to_run2 = ['sfp_dnsresolve', 'sfp__stor_db']

print(f"\n\n=== Starting IP scan {scan_id2}: target={scan_target2} ===")
try:
    scanner2 = SpiderFootScanner(
        scan_name2, scan_id2, scan_target2, target_type2,
        modules_to_run2, config, start=True
    )
except Exception as e:
    print(f"Scanner error: {e}")
    import traceback
    traceback.print_exc()

c.execute("SELECT COUNT(*) FROM tbl_scan_results WHERE scan_instance_id=?", (scan_id2,))
count2 = c.fetchone()[0]
print(f"\n=== Results for IP scan {scan_id2}: {count2} rows ===")
if count2 > 0:
    c.execute("SELECT type, COUNT(*) FROM tbl_scan_results WHERE scan_instance_id=? GROUP BY type", (scan_id2,))
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]}")
c.execute("SELECT guid, name, status FROM tbl_scan_instance WHERE guid=?", (scan_id2,))
inst2 = c.fetchone()
print(f"IP scan status: {inst2}")

conn.close()

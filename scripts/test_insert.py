"""Test the exact INSERT used by scanEventStore."""
import sqlite3
import hashlib
import time

db_path = '/home/spiderfoot/data/spiderfoot.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Show schema
c.execute("SELECT sql FROM sqlite_master WHERE name='tbl_scan_results'")
print("Schema:", c.fetchone()[0])

# Show columns
c.execute("PRAGMA table_info(tbl_scan_results)")
cols = c.fetchall()
print("\nColumns:")
for col in cols:
    print(f"  {col[1]} ({col[2]}) null={col[3]} default={col[4]}")

# Check foreign key enforcement
c.execute("PRAGMA foreign_keys")
print("\nForeign keys enabled:", c.fetchone()[0])

# Check event types count
c.execute("SELECT COUNT(*) FROM tbl_event_types")
print("Event types:", c.fetchone()[0])

# Check if ROOT event type exists
c.execute("SELECT * FROM tbl_event_types WHERE event='ROOT'")
root = c.fetchone()
print("ROOT event type:", root)

# Check INTERNET_NAME event type
c.execute("SELECT * FROM tbl_event_types WHERE event='INTERNET_NAME'")
inet = c.fetchone()
print("INTERNET_NAME event type:", inet)

# Try exact same INSERT as scanEventStore
scan_id = '823D03F4'
test_hash = hashlib.sha256(b'test').hexdigest()[:32]
generated_ms = int(time.time() * 1000)

qry = "INSERT INTO tbl_scan_results (scan_instance_id, hash, type, generated, confidence, visibility, risk, module, data, source_event_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
qvals = [scan_id, test_hash, 'INTERNET_NAME', generated_ms, 100, 100, 0, 'sfp_dnsresolve', 'test.google.com', 'ROOT']

try:
    c.execute(qry, qvals)
    conn.commit()
    print("\nINSERT succeeded!")
    # Check row count
    c.execute("SELECT COUNT(*) FROM tbl_scan_results")
    print("Rows now:", c.fetchone()[0])
    # Clean up test row
    c.execute("DELETE FROM tbl_scan_results WHERE hash=?", (test_hash,))
    conn.commit()
except Exception as e:
    print(f"\nINSERT failed: {type(e).__name__}: {e}")

# Now try with ROOT event type
test_hash2 = hashlib.sha256(b'test2').hexdigest()[:32]
qvals2 = [scan_id, test_hash2, 'ROOT', generated_ms, 100, 100, 0, '', 'google.com', 'ROOT']
try:
    c.execute(qry, qvals2)
    conn.commit()
    print("ROOT INSERT succeeded!")
    c.execute("DELETE FROM tbl_scan_results WHERE hash=?", (test_hash2,))
    conn.commit()
except Exception as e:
    print(f"ROOT INSERT failed: {type(e).__name__}: {e}")

conn.close()

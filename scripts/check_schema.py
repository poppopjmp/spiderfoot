#!/usr/bin/env python3
"""Check scan_results schema."""
import sqlite3

db = '/home/spiderfoot/data/spiderfoot.db'
conn = sqlite3.connect(db)

# Get schema
c = conn.execute("SELECT sql FROM sqlite_master WHERE name='tbl_scan_results'")
schema = c.fetchone()
print("Schema:", schema[0] if schema else "NOT FOUND")

# Test insert
print("\nTesting insert...")
try:
    conn.execute("""INSERT INTO tbl_scan_results 
        (hash, scan_instance_id, type, generated, confidence, visibility, severity, source_event_hash, module_data_source, data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ('testhash', '823D03F4', 'TEST', 12345, 100, 100, 0, 'ROOT', 'test', 'testdata')
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM tbl_scan_results").fetchone()[0]
    print(f"Insert OK, count: {count}")
    # Clean up
    conn.execute("DELETE FROM tbl_scan_results WHERE hash='testhash'")
    conn.commit()
except Exception as e:
    print(f"Insert failed: {e}")

conn.close()

#!/usr/bin/env python3
"""Check scan logs from database."""
import sqlite3

db = '/home/spiderfoot/data/spiderfoot.db'
conn = sqlite3.connect(db)

# Get scan logs for 823D03F4
rows = conn.execute(
    "SELECT generated, component, type, message FROM tbl_scan_log "
    "WHERE scan_instance = '823D03F4' ORDER BY generated LIMIT 100"
).fetchall()
print(f"Scan logs: {len(rows)} entries")
for r in rows[:50]:
    print(f"  [{r[2]}] {r[1]}: {r[3][:120]}")

conn.close()

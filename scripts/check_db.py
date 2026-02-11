#!/usr/bin/env python3
"""Inspect SQLite databases for scan results."""
import sqlite3
import os

for db_path in [
    '/home/spiderfoot/data/spiderfoot.db',
    '/home/spiderfoot/.spiderfoot/spiderfoot.db',
]:
    if not os.path.exists(db_path):
        continue
    print(f'\n=== {db_path} ({os.path.getsize(db_path)} bytes) ===')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = c.fetchall()
    print(f'Tables: {[t[0] for t in tables]}')
    for tbl in tables:
        cnt = conn.execute(f'SELECT COUNT(*) FROM [{tbl[0]}]').fetchone()[0]
        print(f'  {tbl[0]}: {cnt} rows')
        if cnt > 0 and cnt < 10:
            rows = conn.execute(f'SELECT * FROM [{tbl[0]}] LIMIT 3').fetchall()
            for row in rows:
                print(f'    {row}')
    conn.close()

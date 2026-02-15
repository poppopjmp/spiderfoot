#!/usr/bin/env python3
"""One-time schema migration for auth system v2 (API keys + SSO group mapping)."""
import os
import psycopg2

dsn = os.environ.get(
    "SF_POSTGRES_DSN",
    "postgresql://spiderfoot:spiderfoot@postgres:5432/spiderfoot",
)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()

migrations = [
    "ALTER TABLE tbl_sso_providers ADD COLUMN group_attribute VARCHAR(255) DEFAULT 'groups'",
    "ALTER TABLE tbl_sso_providers ADD COLUMN admin_group VARCHAR(500) DEFAULT ''",
    """CREATE TABLE IF NOT EXISTS tbl_api_keys (
        id              VARCHAR(64) PRIMARY KEY,
        user_id         VARCHAR(64) NOT NULL REFERENCES tbl_users(id) ON DELETE CASCADE,
        name            VARCHAR(255) NOT NULL,
        key_prefix      VARCHAR(16) NOT NULL,
        key_hash        VARCHAR(255) NOT NULL,
        role            VARCHAR(50) NOT NULL DEFAULT 'viewer',
        status          VARCHAR(50) NOT NULL DEFAULT 'active',
        expires_at      DOUBLE PRECISION DEFAULT 0,
        allowed_modules TEXT DEFAULT '',
        allowed_endpoints TEXT DEFAULT '',
        rate_limit      INTEGER DEFAULT 0,
        last_used       DOUBLE PRECISION DEFAULT 0,
        created_at      DOUBLE PRECISION DEFAULT 0,
        updated_at      DOUBLE PRECISION DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON tbl_api_keys(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON tbl_api_keys(key_prefix)",
]

for sql in migrations:
    try:
        cur.execute(sql)
        print(f"OK: {sql[:70]}...")
    except Exception as e:
        conn.rollback()
        conn.autocommit = True
        print(f"SKIP ({type(e).__name__}): {sql[:70]}...")

cur.close()
conn.close()
print("Schema migration complete.")

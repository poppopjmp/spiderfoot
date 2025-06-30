# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot Database Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
"""
Utility functions, error handling, and helpers for SpiderFootDb.
"""

def get_placeholder(db_type):
    """Return the correct SQL placeholder for the given DB type."""
    db_type = normalize_db_type(db_type)
    if db_type == 'sqlite':
        return '?'
    elif db_type == 'postgresql':
        return '%s'
    raise ValueError(f"Unsupported db_type: {db_type}")

def normalize_db_type(db_type):
    """Normalize and validate the db_type string."""
    if not isinstance(db_type, str):
        raise TypeError("db_type must be a string")
    db_type = db_type.lower()
    if db_type in ('sqlite', 'sqlite3'):
        return 'sqlite'
    elif db_type in ('postgresql', 'postgres', 'psycopg2'):
        return 'postgresql'
    raise ValueError(f"Unsupported db_type: {db_type}")

def get_upsert_clause(db_type, table, conflict_cols, update_cols):
    """Return the correct upsert clause for the backend."""
    db_type = normalize_db_type(db_type)
    if not conflict_cols or not update_cols:
        raise ValueError("conflict_cols and update_cols must be non-empty lists")
    conflict_str = ','.join(conflict_cols)
    update_str = ', '.join([f"{col}=excluded.{col}" if db_type == 'sqlite' else f"{col}=EXCLUDED.{col}" for col in update_cols])
    if db_type == 'sqlite':
        return f"ON CONFLICT({conflict_str}) DO UPDATE SET {update_str}"
    elif db_type == 'postgresql':
        return f"ON CONFLICT({conflict_str}) DO UPDATE SET {update_str}"
    raise ValueError(f"Unsupported db_type: {db_type}")

def is_transient_error(exc):
    """Classify if an exception is a transient DB error."""
    import sqlite3
    try:
        import psycopg2
    except ImportError:
        psycopg2 = None
    # SQLite transient errors
    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        if 'database is locked' in msg or 'database is busy' in msg or 'unable to open database file' in msg:
            return True
    # PostgreSQL transient errors
    if psycopg2 and isinstance(exc, psycopg2.OperationalError):
        return True
    if psycopg2 and isinstance(exc, psycopg2.DatabaseError):
        msg = str(exc).lower()
        if 'could not connect' in msg or 'connection refused' in msg or 'server closed the connection' in msg:
            return True
    return False

def check_connection(conn, db_type):
    """Check if the DB connection is alive."""
    db_type = normalize_db_type(db_type)
    try:
        if db_type == 'sqlite':
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
            cursor.close()
        elif db_type == 'postgresql':
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.fetchone()
            cursor.close()
        else:
            raise ValueError(f"Unsupported db_type: {db_type}")
        return True
    except Exception:
        return False

def get_type_mapping(db_type):
    """Return a dict mapping logical types to backend-specific types."""
    db_type = normalize_db_type(db_type)
    if db_type == 'sqlite':
        return {
            'int': 'INT',
            'bigint': 'INT',
            'text': 'TEXT',
            'varchar': 'VARCHAR',
            'bool': 'INTEGER',
        }
    elif db_type == 'postgresql':
        return {
            'int': 'INT',
            'bigint': 'BIGINT',
            'text': 'TEXT',
            'varchar': 'VARCHAR',
            'bool': 'BOOLEAN',
        }
    raise ValueError(f"Unsupported db_type: {db_type}")

def get_index_if_not_exists(db_type):
    """Return the correct 'IF NOT EXISTS' clause for index creation."""
    db_type = normalize_db_type(db_type)
    if db_type == 'sqlite':
        return ''  # Not supported in all SQLite versions
    elif db_type == 'postgresql':
        return 'IF NOT EXISTS '
    raise ValueError(f"Unsupported db_type: {db_type}")

def get_bool_value(db_type, value):
    """Return the correct boolean value for the backend."""
    db_type = normalize_db_type(db_type)
    if db_type == 'sqlite':
        return 1 if value else 0
    elif db_type == 'postgresql':
        return True if value else False
    raise ValueError(f"Unsupported db_type: {db_type}")

def get_schema_version_queries(db_type):
    """Return queries to get/set schema version for the backend."""
    db_type = normalize_db_type(db_type)
    if db_type == 'sqlite':
        return {
            'create': "CREATE TABLE IF NOT EXISTS tbl_schema_version (version INT NOT NULL, applied_at INT NOT NULL)",
            'get': "SELECT version, applied_at FROM tbl_schema_version ORDER BY ROWID DESC LIMIT 1",
            'set': "INSERT INTO tbl_schema_version (version, applied_at) VALUES (?, ?)"
        }
    elif db_type == 'postgresql':
        return {
            'create': "CREATE TABLE IF NOT EXISTS tbl_schema_version (version INT NOT NULL, applied_at BIGINT NOT NULL)",
            'get': "SELECT version, applied_at FROM tbl_schema_version ORDER BY version DESC LIMIT 1",
            'set': "INSERT INTO tbl_schema_version (version, applied_at) VALUES (%s, %s)"
        }
    raise ValueError(f"Unsupported db_type: {db_type}")

def get_limit_offset_clause(db_type, limit=None, offset=None):
    """Return LIMIT/OFFSET clause for the backend."""
    db_type = normalize_db_type(db_type)
    clause = ''
    if limit is not None:
        clause += f' LIMIT {int(limit)}'
    if offset is not None:
        clause += f' OFFSET {int(offset)}'
    return clause

def drop_all_tables(db_type, conn):
    """Drop all user tables in the database (for test isolation)."""
    db_type = normalize_db_type(db_type)
    try:
        cursor = conn.cursor()
        if db_type == 'sqlite':
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            for t in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {t}")
        elif db_type == 'postgresql':
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            tables = [row[0] for row in cursor.fetchall()]
            for t in tables:
                cursor.execute(f'DROP TABLE IF EXISTS {t} CASCADE')
        conn.commit()
        cursor.close()
    except Exception as e:
        # For test code, just print; in prod, log properly
        print(f"Error dropping tables: {e}")

def dump_schema(db_type, conn):
    """Return a string dump of the current DB schema (for debugging)."""
    db_type = normalize_db_type(db_type)
    cursor = conn.cursor()
    schema = ''
    if db_type == 'sqlite':
        cursor.execute("SELECT sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL")
        schema = '\n'.join(row[0] for row in cursor.fetchall())
    elif db_type == 'postgresql':
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [row[0] for row in cursor.fetchall()]
        for t in tables:
            cursor.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{t}'")
            cols = ', '.join([f"{col} {typ}" for col, typ in cursor.fetchall()])
            schema += f"CREATE TABLE {t} ({cols});\n"
    cursor.close()
    return schema

# Add more helpers as needed

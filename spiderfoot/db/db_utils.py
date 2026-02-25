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

PostgreSQL-only backend.
"""

from __future__ import annotations

import logging


def normalize_db_type(db_type: str) -> str:
    """Normalize and validate the db_type string."""
    if not isinstance(db_type, str):
        raise TypeError("db_type must be a string")
    db_type = db_type.lower()
    if db_type in ('postgresql', 'postgres', 'psycopg2'):
        return 'postgresql'
    if db_type in ('sqlite', 'sqlite3'):
        return 'sqlite'
    raise ValueError(f"Unsupported db_type: {db_type}")


def get_placeholder(db_type: str) -> str:
    """Return the correct SQL placeholder for the given DB type."""
    normalized = normalize_db_type(db_type)
    if normalized == 'sqlite':
        return '?'
    return '%s'


def get_upsert_clause(db_type: str, table: str, conflict_cols: list[str], update_cols: list[str]) -> str:
    """Return the correct upsert clause for the backend."""
    normalize_db_type(db_type)
    if not conflict_cols or not update_cols:
        raise ValueError("conflict_cols and update_cols must be non-empty lists")
    conflict_str = ','.join(conflict_cols)
    update_str = ', '.join(f"{col}=EXCLUDED.{col}" for col in update_cols)
    return f"ON CONFLICT({conflict_str}) DO UPDATE SET {update_str}"


def is_transient_error(exc: Exception) -> bool:
    """Classify if an exception is a transient DB error."""
    try:
        import psycopg2
    except ImportError:
        return False
    if isinstance(exc, psycopg2.OperationalError):
        return True
    if isinstance(exc, psycopg2.DatabaseError):
        msg = str(exc).lower()
        if 'could not connect' in msg or 'connection refused' in msg or 'server closed the connection' in msg:
            return True
    return False


def check_connection(conn: object, db_type: str) -> bool:
    """Check if the DB connection is alive."""
    normalize_db_type(db_type)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cursor.fetchone()
        cursor.close()
        return True
    except Exception:
        return False


def get_type_mapping(db_type: str) -> dict:
    """Return a dict mapping logical types to backend-specific types."""
    normalize_db_type(db_type)
    return {
        'int': 'INT',
        'bigint': 'BIGINT',
        'text': 'TEXT',
        'varchar': 'VARCHAR',
        'bool': 'BOOLEAN',
    }


def get_index_if_not_exists(db_type: str) -> str:
    """Return the correct 'IF NOT EXISTS' clause for index creation."""
    normalize_db_type(db_type)
    return 'IF NOT EXISTS '


def get_bool_value(db_type: str, value: object) -> bool | int:
    """Return the correct boolean value for the backend."""
    normalize_db_type(db_type)
    return True if value else False


def get_schema_version_queries(db_type: str) -> dict:
    """Return queries to get/set schema version for the backend."""
    normalize_db_type(db_type)
    return {
        'create': "CREATE TABLE IF NOT EXISTS tbl_schema_version (version INT NOT NULL, applied_at BIGINT NOT NULL)",
        'get': "SELECT version, applied_at FROM tbl_schema_version ORDER BY version DESC LIMIT 1",
        'set': "INSERT INTO tbl_schema_version (version, applied_at) VALUES (%s, %s)",
    }


def get_limit_offset_clause(db_type: str, limit: int | None = None, offset: int | None = None) -> str:
    """Return LIMIT/OFFSET clause for the backend."""
    normalize_db_type(db_type)
    clause = ''
    if limit is not None:
        clause += f' LIMIT {int(limit)}'
    if offset is not None:
        clause += f' OFFSET {int(offset)}'
    return clause


def _quote_ident(name: str, db_type: str) -> str:
    """Quote a SQL identifier to prevent injection.

    PostgreSQL supports double-quoting identifiers.
    We also reject any embedded double-quotes as an extra safety layer.
    """
    if '"' in name:
        raise ValueError(f"Invalid identifier: {name!r}")
    return f'"{name}"'


def drop_all_tables(db_type: str, conn: object) -> None:
    """Drop all user tables in the database (for test isolation)."""
    normalize_db_type(db_type)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        tables = [row[0] for row in cursor.fetchall()]
        for t in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {_quote_ident(t, db_type)} CASCADE")
        conn.commit()
        cursor.close()
    except Exception as e:
        logging.getLogger(__name__).error("Error dropping tables: %s", e)


def dump_schema(db_type: str, conn: object) -> str:
    """Return a string dump of the current DB schema (for debugging)."""
    normalize_db_type(db_type)
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    tables = [row[0] for row in cursor.fetchall()]
    schema = ''
    for t in tables:
        cursor.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s",
            (t,),
        )
        cols = ', '.join(f"{col} {typ}" for col, typ in cursor.fetchall())
        schema += f"CREATE TABLE {_quote_ident(t, db_type)} ({cols});\n"
    cursor.close()
    return schema

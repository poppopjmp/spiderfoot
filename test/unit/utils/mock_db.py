"""
Mock database utilities for SpiderFoot tests
"""

import unittest
from unittest.mock import MagicMock, patch
import sqlite3
import os
import tempfile
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


def create_mock_db(test_instance):
    """
    Create a mock database for testing.
    
    Args:
        test_instance: The unittest test instance
        
    Returns:
        A tuple containing (mock_conn, mock_cursor, sqlite_patcher)
    """
    # Create a mock cursor and connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    # Setup patching for sqlite3
    sqlite_patcher = patch('spiderfoot.db.sqlite3')
    mock_sqlite = sqlite_patcher.start()
    mock_sqlite.connect.return_value = mock_conn
    
    # Add cleanup to the test's tearDown
    original_tearDown = test_instance.tearDown
    
    def patched_tearDown():
        sqlite_patcher.stop()
        original_tearDown()
    
    test_instance.tearDown = patched_tearDown
    
    return mock_conn, mock_cursor, sqlite_patcher


def setup_test_db(test_instance, in_memory=True):
    """
    Set up a real SQLite database for testing.
    
    Args:
        test_instance: The unittest test instance
        in_memory: Whether to use an in-memory database (default: True)
        
    Returns:
        A tuple containing (conn, cursor, db_path)
    """
    if in_memory:
        conn = sqlite3.connect(":memory:")
        db_path = ":memory:"
    else:
        # Create a temporary file
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        conn = sqlite3.connect(db_path)
    
    cursor = conn.cursor()
    
    # Add cleanup to the test's tearDown
    original_tearDown = test_instance.tearDown
    
    def patched_tearDown():
        conn.close()
        if not in_memory and os.path.exists(db_path):
            os.unlink(db_path)
        original_tearDown()
    
    test_instance.tearDown = patched_tearDown
    
    return conn, cursor, db_path


def create_sfdb_tables(conn, cursor):
    """
    Create the SpiderFoot database tables in the given database.
    
    Args:
        conn: SQLite connection
        cursor: SQLite cursor
    """
    # Table schema definitions
    tables = [
        """CREATE TABLE IF NOT EXISTS tbl_scan_instance (
            guid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            seed_target TEXT NOT NULL,
            created INTEGER NOT NULL,
            started INTEGER,
            ended INTEGER,
            status TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS tbl_scan_config (
            scan_instance_id TEXT NOT NULL REFERENCES tbl_scan_instance(guid),
            component TEXT NOT NULL,
            opt TEXT NOT NULL,
            val TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS tbl_scan_results (
            scan_instance_id TEXT NOT NULL REFERENCES tbl_scan_instance(guid),
            hash TEXT NOT NULL,
            type TEXT NOT NULL,
            generated INTEGER NOT NULL,
            confidence INTEGER NOT NULL DEFAULT 100,
            visibility INTEGER NOT NULL DEFAULT 100,
            risk INTEGER NOT NULL DEFAULT 0,
            module TEXT NOT NULL,
            data TEXT,
            source_event_hash TEXT,
            false_positive INTEGER NOT NULL DEFAULT 0,
            UNIQUE(scan_instance_id, hash)
        )""",
        """CREATE TABLE IF NOT EXISTS tbl_scan_log (
            scan_instance_id TEXT NOT NULL REFERENCES tbl_scan_instance(guid),
            generated INTEGER NOT NULL,
            component TEXT,
            type TEXT,
            message TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS tbl_event_types (
            event TEXT NOT NULL,
            event_descr TEXT NOT NULL,
            event_raw TEXT NOT NULL,
            event_type TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS tbl_config (
            scope TEXT NOT NULL,
            opt TEXT NOT NULL,
            val TEXT NOT NULL,
            UNIQUE(scope, opt)
        )""",
        """CREATE TABLE IF NOT EXISTS tbl_correlation_results (
            id TEXT PRIMARY KEY, 
            title TEXT NOT NULL,
            scan_instance_id TEXT NOT NULL REFERENCES tbl_scan_instance(guid),
            created INTEGER NOT NULL,
            rule_id TEXT NOT NULL,
            rule_name TEXT NOT NULL,
            rule_descr TEXT NOT NULL,
            rule_logic TEXT NOT NULL,
            rule_risk TEXT NOT NULL
        )"""
    ]
    
    # Create tables
    for table_sql in tables:
        cursor.execute(table_sql)
    
    # Commit changes
    conn.commit()

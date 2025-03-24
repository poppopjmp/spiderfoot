"""
Web test helpers for SpiderFoot UI tests.
"""

from unittest.mock import MagicMock, patch
import os
import tempfile
import sqlite3


def create_web_test_environment(test_class):
    """
    Set up a proper test environment for SpiderFootWebUi tests.
    
    Args:
        test_class: The test class instance
        
    Returns:
        dict: Configuration options for web tests
    """
    # Create a temp database for testing
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Standard options for web tests
    opts = {
        '__database': db_path,
        '__modules__': 'modules',
        '__correlations__': 'correlations',
        '_dnsserver': '8.8.8.8',
        '_fetchtimeout': 5,
        '_docroot': 'test/docroot',
        '_weblogfile': '/dev/null',
        '_useragent': 'SpiderFoot-test',
        '__logging': True,
        '_debug': False,
        '_test': True
    }
    
    # Create a connection to initialize the DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create basic tables needed for the web UI
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tbl_scan_instance (
        guid TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        seed_target TEXT NOT NULL,
        created INTEGER NOT NULL,
        started INTEGER,
        ended INTEGER,
        status TEXT NOT NULL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tbl_config (
        scope TEXT NOT NULL,
        opt TEXT NOT NULL,
        val TEXT NOT NULL,
        UNIQUE(scope, opt)
    )
    """)
    
    # Add some basic configuration
    cursor.execute("INSERT OR REPLACE INTO tbl_config (scope, opt, val) VALUES (?, ?, ?)",
                   ("GLOBAL", "test_option", "test_value"))
    
    conn.commit()
    conn.close()
    
    # Add cleanup to the test class's tearDown
    original_tearDown = test_class.tearDown
    def new_tearDown():
        if os.path.exists(db_path):
            os.unlink(db_path)
        original_tearDown()
    
    test_class.tearDown = new_tearDown
    
    # Patch common imports used by the web UI
    patch('cherrypy.engine').start()
    patch('cherrypy.server').start()
    patch('cherrypy.config').start()
    patch('cherrypy.log').start()
    
    # Make sure these are stopped when tearDown is called
    old_tearDown = test_class.tearDown
    def patched_tearDown():
        old_tearDown()
        patch.stopall()
    
    test_class.tearDown = patched_tearDown
    
    return opts

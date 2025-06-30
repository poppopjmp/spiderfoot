# db_utils.py
"""
Utility functions, error handling, and helpers for SpiderFootDb.
"""
class DbUtils:
    def __init__(self, dbh, conn, dbhLock, db_type):
        self.dbh = dbh
        self.conn = conn
        self.dbhLock = dbhLock
        self.db_type = db_type

    # Placeholder for future utility methods. All core, scan, event, config, and correlation logic is now in their respective modules.
    # Add any shared helpers or error handling utilities here as needed.
    # No direct extraction from db.py is required at this time, as all logic is now modularized.
    pass

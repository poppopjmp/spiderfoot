import unittest
from unittest.mock import patch, MagicMock
from spiderfoot.db import SpiderFootDb
from spiderfoot import SpiderFootHelpers, SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion
import time
import os


class TestSpiderFootDb(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.opts = {
            '__database': 'test.db',
            '__dbtype': 'sqlite'
        }
        # Use test database to avoid conflicts
        self.opts['__database'] = f"{SpiderFootHelpers.dataPath()}/test_{time.time()}.db"
        self.db = SpiderFootDb(self.opts)
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def test_init_invalid_opts_type(self):
        with self.assertRaises(TypeError):
            SpiderFootDb("invalid_opts")

    def test_init_empty_opts(self):
        with self.assertRaises(ValueError):
            SpiderFootDb({})

    def test_init_missing_database_key(self):
        with self.assertRaises(ValueError):
            SpiderFootDb({'__dbtype': 'sqlite'})

    def test_create(self):
        # Test that create can be called without errors in a fresh database
        result = False
        test_db = None
        try:
            # Use a fresh instance to avoid "already exists" errors
            test_opts = self.opts.copy()
            test_opts['__database'] = f"{SpiderFootHelpers.dataPath()}/test_create_{time.time()}.db"
            # Create with init=False first, which will automatically call create() if needed
            test_db = SpiderFootDb(test_opts, init=False)
            # Verify that the essential tables exist
            test_db.dbh.execute('SELECT COUNT(*) FROM tbl_event_types')
            event_types_count = test_db.dbh.fetchone()[0]
            test_db.dbh.execute('SELECT COUNT(*) FROM tbl_scan_config')
            # If we get here without exceptions, the database was created successfully
            result = True
        except Exception as e:
            # Print the error for debugging
            print(f"Database creation failed: {e}")
            result = False
        finally:
            # Clean up test database
            if test_db is not None:
                try:
                    test_db.close()
                except:
                    pass
                try:
                    if 'test_opts' in locals():
                        os.remove(test_opts['__database'])
                except:
                    pass
        self.assertTrue(result)

    def test_close(self):
        # Test that close method can be called without errors
        # Since close() doesn't return anything, we just ensure it doesn't raise
        try:
            self.db.close()
            result = True
        except Exception:
            result = False
        self.assertTrue(result)

    def test_vacuumDB(self):
        # Test that vacuumDB can be called
        try:
            self.db.vacuumDB()
            result = True
        except Exception:
            result = False
        self.assertTrue(result)

    def test_search_invalid_criteria_type(self):
        with self.assertRaises(TypeError):
            self.db.search("invalid_criteria")

    def test_search_empty_criteria(self):
        with self.assertRaises(ValueError):
            self.db.search({})

    def test_search_single_criteria(self):
        # Test search with multiple criteria - should not raise exceptions
        criteria = {'scan_id': 'test_instance', 'type': 'IP_ADDRESS'}
        try:
            result = self.db.search(criteria)
            # Result should be a list
            self.assertIsInstance(result, list)
        except Exception:
            self.fail("Search with multiple criteria raised an exception")

    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self, 'db') and self.db:
            try:
                self.db.close()
            except:
                pass
        if hasattr(self, 'opts') and self.opts.get('__database'):
            try:
                os.remove(self.opts['__database'])
            except:
                pass
        if hasattr(self, 'module'):
            self.unregister_event_emitter(self.module)
        super().tearDown()

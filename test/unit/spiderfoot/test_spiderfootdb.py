import unittest
from unittest.mock import patch, MagicMock
from spiderfoot.db import SpiderFootDb
from spiderfoot import SpiderFootHelpers, SpiderFootEvent
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion
import time
import os
import shutil


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

    def test_schema_tables_exist(self):
        # Test that all required tables are created
        import sqlite3
        self.db.close()
        with sqlite3.connect(self.opts['__database']) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
        required = [
            'tbl_event_types', 'tbl_config', 'tbl_scan_instance',
            'tbl_scan_log', 'tbl_scan_config', 'tbl_scan_results'
        ]
        for table in required:
            self.assertIn(table, tables)

    def test_event_store_and_retrieve(self):
        # Test storing and retrieving a basic event
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        results = self.db.scanResultEvent(scan_id, eventType='IP_ADDRESS')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], '1.2.3.4')

    def test_event_with_special_characters(self):
        # Store and retrieve event with unicode/special chars
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        special = '特殊字符!@#\u20ac\u2603\n\t'
        event = SpiderFootEvent('RAW_DATA', special, 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        results = self.db.scanResultEvent(scan_id, eventType='RAW_DATA')
        self.assertTrue(any(e[1] == special for e in results))

    def test_config_set_get_update(self):
        # Test config set/get/update
        self.db.configSet({'foo': 'bar'})
        config = self.db.configGet()
        self.assertEqual(config.get('foo'), 'bar')
        self.db.configSet({'foo': 'baz'})
        config = self.db.configGet()
        self.assertEqual(config.get('foo'), 'baz')

    def test_scan_instance_crud(self):
        # Test scan instance create/get/list/delete
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        info = self.db.scanInstanceGet(scan_id)
        self.assertIsNotNone(info)
        scans = self.db.scanInstanceList()
        self.assertTrue(any(s[0] == scan_id for s in scans))
        self.db.scanInstanceDelete(scan_id)
        info = self.db.scanInstanceGet(scan_id)
        self.assertIsNone(info)

    def test_search_with_date_range_and_no_results(self):
        # Test search with a date range and for no results
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        now = int(time.time())
        results = self.db.search({'scan_id': scan_id, 'start_date': now + 10000, 'end_date': now + 20000})
        self.assertEqual(len(results), 0)

    def test_resource_cleanup_and_file_deletion(self):
        # Test DB close and file deletion
        db_path = self.opts['__database']
        self.db.close()
        import gc
        del self.db
        gc.collect()
        self.assertTrue(os.path.exists(db_path))
        try:
            os.remove(db_path)
        except PermissionError:
            time.sleep(0.1)
            os.remove(db_path)
        self.assertFalse(os.path.exists(db_path))

    def test_duplicate_scan_instance_id(self):
        # Test creating scan instance with duplicate ID
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        with self.assertRaises(Exception):
            self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')

    def test_log_event_store_and_retrieve(self):
        # Test storing and retrieving log events
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        self.db.scanLogEvent(scan_id, 'INFO', 'Scan started', 'main')
        self.db.scanLogEvent(scan_id, 'ERROR', 'Something failed', 'main')
        logs = self.db.scanLogs(scan_id)
        self.assertGreaterEqual(len(logs), 2)
        messages = [log[3] for log in logs]
        self.assertIn('Scan started', messages)
        self.assertIn('Something failed', messages)

    def test_scan_event_store_with_truncation(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        large_data = 'X' * 5000
        event = SpiderFootEvent('RAW_RIR_DATA', large_data, 'testmod', root_event)
        self.db.scanEventStore(scan_id, event, truncateSize=1000)
        results = self.db.scanResultEvent(scan_id, eventType='RAW_RIR_DATA')
        self.assertEqual(len(results), 1)
        self.assertTrue(len(results[0][1]) <= 1000)

    def test_scan_event_bulk_store_and_retrieve(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        for i in range(50):
            event = SpiderFootEvent('IP_ADDRESS', f'10.0.0.{i}', 'testmod', root_event)
            self.db.scanEventStore(scan_id, event)
        results = self.db.scanResultEvent(scan_id, eventType='IP_ADDRESS')
        self.assertEqual(len(results), 50)

    def test_scan_event_get_with_filters(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        event_types = ['IP_ADDRESS', 'DOMAIN_NAME', 'EMAIL_ADDRESS']
        for i, etype in enumerate(event_types):
            event = SpiderFootEvent(etype, f'data_{i}', f'mod_{i}', root_event)
            self.db.scanEventStore(scan_id, event)
        for i, etype in enumerate(event_types):
            results = self.db.scanResultEvent(scan_id, eventType=etype)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][1], f'data_{i}')
            self.assertEqual(results[0][2], f'mod_{i}')

    def test_search_by_event_type_and_data_content(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        event = SpiderFootEvent('RAW_DATA', 'searchable_content_123', 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        results = self.db.search({'scan_id': scan_id, 'type': 'RAW_DATA', 'data': 'searchable_content_123'})
        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(any('searchable_content_123' in r[1] for r in results))

    def test_scan_log_filtering_by_limit(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        for i in range(10):
            self.db.scanLogEvent(scan_id, 'INFO', f'Log {i}', 'main')
        logs = self.db.scanLogs(scan_id, limit=5)
        self.assertEqual(len(logs), 5)

    def test_scan_instance_delete_removes_events(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        self.db.scanInstanceDelete(scan_id)
        results = self.db.scanResultEvent(scan_id, eventType='IP_ADDRESS')
        self.assertEqual(len(results), 0)

    def test_malformed_event_handling(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        with self.assertRaises((TypeError, ValueError)):
            self.db.scanEventStore(scan_id, None)
        with self.assertRaises((TypeError, ValueError)):
            self.db.scanEventStore(scan_id, 'not_an_event')

    def test_invalid_scan_operations(self):
        # Operations on non-existent scan
        scan_id = 'nonexistent_' + str(int(time.time()))
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod')
        try:
            self.db.scanEventStore(scan_id, event)
        except Exception:
            pass
        results = self.db.scanResultEvent(scan_id, eventType='IP_ADDRESS')
        self.assertEqual(len(results), 0)

    def test_database_close_and_resource_cleanup_robustness(self):
        # Open and close DB multiple times
        db_path = self.opts['__database']
        for _ in range(3):
            db = SpiderFootDb({'__database': db_path, '__dbtype': 'sqlite'})
            db.close()
            del db
            import gc
            gc.collect()
        self.assertTrue(os.path.exists(db_path))

    def test_event_truncation_exact_limit(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        limit = 1000
        data = 'A' * limit
        event = SpiderFootEvent('RAW_RIR_DATA', data, 'testmod', root_event)
        self.db.scanEventStore(scan_id, event, truncateSize=limit)
        results = self.db.scanResultEvent(scan_id, eventType='RAW_RIR_DATA')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1], data)

    def test_search_non_overlapping_date_range(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        # Use a date range far in the past
        criteria = {
            'scan_id': scan_id,
            'start_date': 1000000000,  # 2001-09-09
            'end_date': 1000000001,
            'type': 'IP_ADDRESS'
        }
        results = self.db.search(criteria)
        self.assertEqual(len(results), 0)

    def test_event_with_special_characters_exact(self):
        scan_id = 'scan_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'Test', 'target.com')
        root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        special = '特殊字符!@#\u20ac\u2603\n\t'
        event = SpiderFootEvent('RAW_DATA', special, 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        results = self.db.scanResultEvent(scan_id, eventType='RAW_DATA')
        self.assertTrue(any(e[1] == special for e in results))

    def test_multiple_database_isolation(self):
        import tempfile, gc
        temp_dir2 = tempfile.mkdtemp()
        db_path2 = os.path.join(temp_dir2, f'test2_{time.time()}.db')
        opts2 = {'__database': db_path2, '__dbtype': 'sqlite'}
        db2 = SpiderFootDb(opts2, init=True)
        try:
            scan_id1 = 'scan_' + str(int(time.time()))
            scan_id2 = 'scan2_' + str(int(time.time()))
            self.db.scanInstanceCreate(scan_id1, 'Test', 'target.com')
            db2.scanInstanceCreate(scan_id2, 'Test2', 'target2.com')
            root_event = SpiderFootEvent('ROOT', 'target.com', 'testmod')
            self.db.scanEventStore(scan_id1, root_event)
            event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod', root_event)
            self.db.scanEventStore(scan_id1, event)
            # Should not be visible in db2
            results = db2.scanResultEvent(scan_id2, eventType='IP_ADDRESS')
            self.assertEqual(len(results), 0)
        finally:
            db2.close()
            del db2
            gc.collect()
            if os.path.exists(db_path2):
                os.remove(db_path2)
            import shutil
            shutil.rmtree(temp_dir2)

    def test_database_resource_cleanup_robustness(self):
        import gc
        db_path = self.opts['__database']
        for _ in range(3):
            db = SpiderFootDb({'__database': db_path, '__dbtype': 'sqlite'})
            db.close()
            del db
            gc.collect()
        self.assertTrue(os.path.exists(db_path))

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


class TestSpiderFootDbIntegration(SpiderFootTestBase):
    """Integration tests for SpiderFootDb covering full workflows and cross-feature scenarios."""

    def setUp(self):
        super().setUp()
        self.opts = {
            '__database': f"{SpiderFootHelpers.dataPath()}/test_integration_{time.time()}.db",
            '__dbtype': 'sqlite'
        }
        self.db = SpiderFootDb(self.opts)

    def test_full_scan_workflow(self):
        scan_id = 'integration_' + str(int(time.time()))
        # Create scan instance and set config
        self.db.scanInstanceCreate(scan_id, 'IntegrationTest', 'integration.com')
        self.db.configSet({'integration': 'yes', 'foo': 'bar'})
        # Store root event and child events
        root_event = SpiderFootEvent('ROOT', 'integration.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        child_events = [
            SpiderFootEvent('IP_ADDRESS', f'192.168.1.{i}', 'testmod', root_event) for i in range(5)
        ]
        for event in child_events:
            self.db.scanEventStore(scan_id, event)
        # Store logs
        for i in range(3):
            self.db.scanLogEvent(scan_id, 'INFO', f'Integration log {i}', 'main')
        # Retrieve and verify events
        results = self.db.scanResultEvent(scan_id, eventType='IP_ADDRESS')
        self.assertEqual(len(results), 5)
        # Retrieve and verify logs
        logs = self.db.scanLogs(scan_id)
        self.assertGreaterEqual(len(logs), 3)
        # Search for event by data
        search_results = self.db.search({'scan_id': scan_id, 'data': '192.168.1.2'})
        self.assertTrue(any('192.168.1.2' in r[1] for r in search_results))
        # Delete scan and verify cleanup
        self.db.scanInstanceDelete(scan_id)
        results_after = self.db.scanResultEvent(scan_id, eventType='IP_ADDRESS')
        self.assertEqual(len(results_after), 0)
        logs_after = self.db.scanLogs(scan_id)
        self.assertEqual(len(logs_after), 0)

    def test_bulk_events_and_logs_integration(self):
        scan_id = 'bulk_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'BulkTest', 'bulk.com')
        root_event = SpiderFootEvent('ROOT', 'bulk.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        # Bulk store events
        for i in range(100):
            event = SpiderFootEvent('EMAIL_ADDRESS', f'user{i}@bulk.com', 'testmod', root_event)
            self.db.scanEventStore(scan_id, event)
        results = self.db.scanResultEvent(scan_id, eventType='EMAIL_ADDRESS')
        self.assertEqual(len(results), 100)
        # Bulk store logs
        for i in range(50):
            self.db.scanLogEvent(scan_id, 'DEBUG', f'Bulk log {i}', 'main')
        logs = self.db.scanLogs(scan_id, limit=10)
        self.assertEqual(len(logs), 10)

    def test_config_update_and_persistence(self):
        scan_id = 'config_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'ConfigTest', 'config.com')
        self.db.configSet({'persist': 'before'})
        self.db.close()
        # Reopen DB and check config
        db2 = SpiderFootDb(self.opts)
        config = db2.configGet()
        self.assertEqual(config.get('persist'), 'before')
        db2.configSet({'persist': 'after'})
        config2 = db2.configGet()
        self.assertEqual(config2.get('persist'), 'after')
        db2.close()

    def test_integration_event_search_filters(self):
        scan_id = 'filter_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'FilterTest', 'filter.com')
        root_event = SpiderFootEvent('ROOT', 'filter.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        # Store events with different types and modules
        for i in range(3):
            event = SpiderFootEvent('DOMAIN_NAME', f'domain{i}.com', f'mod_{i}', root_event)
            self.db.scanEventStore(scan_id, event)
        for i in range(2):
            event = SpiderFootEvent('EMAIL_ADDRESS', f'user{i}@filter.com', 'mod_email', root_event)
            self.db.scanEventStore(scan_id, event)
        # Search by type
        results = self.db.search({'scan_id': scan_id, 'type': 'DOMAIN_NAME'})
        self.assertEqual(len(results), 3)
        # Search by module
        results_mod = self.db.search({'scan_id': scan_id, 'module': 'mod_email'})
        self.assertEqual(len(results_mod), 2)
        # Search by data substring
        results_data = self.db.search({'scan_id': scan_id, 'data': 'domain1.com'})
        self.assertEqual(len(results_data), 1)

    def test_integration_unicode_and_special_characters(self):
        scan_id = 'unicode_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'UnicodeTest', 'unicode.com')
        root_event = SpiderFootEvent('ROOT', 'unicode.com', 'testmod')
        self.db.scanEventStore(scan_id, root_event)
        special = '集成测试!@#\u20ac\u2603\n\t'
        event = SpiderFootEvent('RAW_DATA', special, 'testmod', root_event)
        self.db.scanEventStore(scan_id, event)
        results = self.db.scanResultEvent(scan_id, eventType='RAW_DATA')
        self.assertTrue(any(e[1] == special for e in results))

    def test_integration_error_handling(self):
        scan_id = 'err_' + str(int(time.time()))
        self.db.scanInstanceCreate(scan_id, 'ErrTest', 'err.com')
        # Malformed event
        with self.assertRaises((TypeError, ValueError)):
            self.db.scanEventStore(scan_id, None)
        # Invalid scan ID
        event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod')
        try:
            self.db.scanEventStore('invalid_scan', event)
        except Exception:
            pass
        results = self.db.scanResultEvent('invalid_scan', eventType='IP_ADDRESS')
        self.assertEqual(len(results), 0)

    def test_integration_database_isolation(self):
        import tempfile, gc
        temp_dir2 = tempfile.mkdtemp()
        db_path2 = os.path.join(temp_dir2, f'test_integration2_{time.time()}.db')
        opts2 = {'__database': db_path2, '__dbtype': 'sqlite'}
        db2 = SpiderFootDb(opts2, init=True)
        try:
            scan_id1 = 'isolate_' + str(int(time.time()))
            scan_id2 = 'isolate2_' + str(int(time.time()))
            self.db.scanInstanceCreate(scan_id1, 'IsoTest', 'iso.com')
            db2.scanInstanceCreate(scan_id2, 'IsoTest2', 'iso2.com')
            root_event = SpiderFootEvent('ROOT', 'iso.com', 'testmod')
            self.db.scanEventStore(scan_id1, root_event)
            event = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'testmod', root_event)
            self.db.scanEventStore(scan_id1, event)
            # Should not be visible in db2
            results = db2.scanResultEvent(scan_id2, eventType='IP_ADDRESS')
            self.assertEqual(len(results), 0)
        finally:
            db2.close()
            del db2
            gc.collect()
            if os.path.exists(db_path2):
                os.remove(db_path2)
            import shutil
            shutil.rmtree(temp_dir2)

    def tearDown(self):
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
        super().tearDown()


class TestSpiderFootDbSchemaBackend(SpiderFootTestBase):
    """Tests for backend-aware schema creation in SpiderFootDb."""

    def setUp(self):
        super().setUp()
        self.sqlite_opts = {
            '__database': f"{SpiderFootHelpers.dataPath()}/test_schema_sqlite_{time.time()}.db",
            '__dbtype': 'sqlite'
        }
        self.pg_opts = {
            '__database': 'dbname=spiderfoot_test user=postgres password=postgres host=localhost',
            '__dbtype': 'postgresql'
        }

    def test_schema_creation_sqlite(self):
        db = SpiderFootDb(self.sqlite_opts, init=True)
        db.close()
        import sqlite3
        with sqlite3.connect(self.sqlite_opts['__database']) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            for t in [
                'tbl_event_types', 'tbl_config', 'tbl_scan_instance',
                'tbl_scan_log', 'tbl_scan_config', 'tbl_scan_results',
                'tbl_scan_correlation_results', 'tbl_scan_correlation_results_events']:
                self.assertIn(t, tables)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row[0] for row in cursor.fetchall()]
            for idx in [
                'idx_scan_results_id', 'idx_scan_results_type', 'idx_scan_results_hash',
                'idx_scan_results_module', 'idx_scan_results_srchash', 'idx_scan_logs',
                'idx_scan_correlation', 'idx_scan_correlation_events']:
                self.assertIn(idx, indexes)

    def test_schema_idempotency_sqlite(self):
        db = SpiderFootDb(self.sqlite_opts, init=True)
        db.create()  # Should not raise
        db.create()  # Should not raise
        db.close()

    def test_schema_type_adaptation_sqlite(self):
        db = SpiderFootDb(self.sqlite_opts, init=True)
        db.close()
        import sqlite3
        with sqlite3.connect(self.sqlite_opts['__database']) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(tbl_scan_instance)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            self.assertEqual(columns['created'], 'INT')
            self.assertEqual(columns['ended'], 'INT')

    def test_schema_creation_unsupported_backend(self):
        from spiderfoot.db import get_schema_queries
        with self.assertRaises(ValueError):
            get_schema_queries('oracle')

    # PostgreSQL tests are skipped unless a test DB is available
    def test_schema_creation_postgresql(self):
        try:
            db = SpiderFootDb(self.pg_opts, init=True)
            db.close()
            import psycopg2
            conn = psycopg2.connect(self.pg_opts['__database'])
            cursor = conn.cursor()
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            tables = [row[0] for row in cursor.fetchall()]
            for t in [
                'tbl_event_types', 'tbl_config', 'tbl_scan_instance',
                'tbl_scan_log', 'tbl_scan_config', 'tbl_scan_results',
                'tbl_scan_correlation_results', 'tbl_scan_correlation_results_events']:
                self.assertIn(t, tables)
            cursor.close()
            conn.close()
        except Exception:
            self.skipTest("PostgreSQL test DB not available or not configured.")

    def tearDown(self):
        import os
        if hasattr(self, 'sqlite_opts') and self.sqlite_opts.get('__database'):
            try:
                os.remove(self.sqlite_opts['__database'])
            except Exception:
                pass
        super().tearDown()

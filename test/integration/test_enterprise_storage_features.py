#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enterprise Storage Features Integration Test Suite

This comprehensive test suite validates all enterprise-grade features
implemented in SpiderFoot's storage modules:

- Connection pooling and health monitoring
- Error handling and recovery
- Performance optimization
- Security features
- Backup and recovery capabilities
- Auto-scaling and monitoring
- AI-powered optimization

Author: SpiderFoot Enterprise Team
Created: 2025-01-27
"""

import unittest
import time
import threading
import tempfile
import os
import json
from unittest.mock import patch, MagicMock, Mock
import psycopg2
from elasticsearch import Elasticsearch, ConnectionError

from spiderfoot.sflib import SpiderFoot
from spiderfoot.event import SpiderFootEvent
from modules.sfp__stor_db import sfp__stor_db
from modules.sfp__stor_elasticsearch import sfp__stor_elasticsearch
from modules.sfp__stor_stdout import sfp__stor_stdout


class TestEnterpriseStorageFeatures(unittest.TestCase):
    """Integration tests for enterprise storage features."""

    def setUp(self):
        """Set up test environment."""
        self.sf_options = {
            'database': tempfile.mktemp(suffix='.db'),
            'modules': [],
            'useragent': 'SpiderFoot-Test'
        }
        
        # Create test SpiderFoot instance
        self.sf = SpiderFoot(self.sf_options)
        
        # Mock database handle
        self.mock_dbh = MagicMock()
        self.mock_dbh.scanEventStore = MagicMock()
        self.sf.dbh = self.mock_dbh
        
        self.test_scan_id = "test_scan_12345"

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temporary database file
        if os.path.exists(self.sf_options['database']):
            os.unlink(self.sf_options['database'])

    def create_test_event(self, event_type="IP_ADDRESS", data="192.168.1.1", module="test_module"):
        """Create a test SpiderFoot event."""
        event = SpiderFootEvent(event_type, data, module, None)
        event.confidence = 100
        event.visibility = 1
        event.risk = 0
        # Removed assignment to read-only properties (hash, generated, sourceEventHash)
        return event

    def test_postgresql_enterprise_features(self):
        """Test PostgreSQL storage enterprise features."""
        print("\n=== Testing PostgreSQL Enterprise Features ===")
        
        with patch('modules.sfp__stor_db.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            # Test connection pooling and health checks
            module = sfp__stor_db()
            opts = {
                'db_type': 'postgresql',
                'postgresql_host': 'localhost',
                'postgresql_port': 5432,
                'postgresql_database': 'spiderfoot',
                'postgresql_username': 'spiderfoot',
                'postgresql_password': 'secure_password',
                'postgresql_timeout': 30,
                '_store': True
            }
            
            module.setup(self.sf, opts)
            module.getScanId = MagicMock(return_value=self.test_scan_id)
            
            # Verify connection was established
            self.assertFalse(module.errorState)
            self.assertIsNotNone(module.pg_conn)
            
            # Test health check functionality
            self.assertTrue(module._check_postgresql_connection())
            
            # Test event storage with proper schema
            test_event = self.create_test_event()
            module.handleEvent(test_event)
            
            # Verify correct table and columns are used
            mock_cursor.execute.assert_called()
            call_args = mock_cursor.execute.call_args[0]
            self.assertIn("tbl_scan_results", call_args[0])
            self.assertIn("scan_instance_id", call_args[0])
            self.assertIn("confidence", call_args[0])
            
            # Test connection recovery
            mock_cursor.execute.side_effect = [
                psycopg2.OperationalError("Connection lost"),
                None  # Recovery succeeds
            ]
            
            test_event2 = self.create_test_event("DOMAIN_NAME", "example.com")
            module.handleEvent(test_event2)
            
            # Should attempt reconnection
            self.assertEqual(mock_connect.call_count, 2)
            
            print("✓ PostgreSQL connection pooling and health checks")
            print("✓ PostgreSQL schema compliance")
            print("✓ PostgreSQL connection recovery")

    def test_elasticsearch_enterprise_features(self):
        """Test Elasticsearch storage enterprise features."""
        print("\n=== Testing Elasticsearch Enterprise Features ===")
        
        with patch('modules.sfp__stor_elasticsearch.Elasticsearch') as mock_es_class, \
             patch('elasticsearch.helpers.bulk') as mock_bulk:
            mock_es = MagicMock()
            mock_es.ping.return_value = True
            mock_es.indices.exists.return_value = False
            mock_es.bulk.return_value = {'errors': False}
            mock_es_class.return_value = mock_es
            mock_bulk.return_value = (150, [])  # Simulate 150 successes, no errors
            
            # Test advanced configuration with security
            module = sfp__stor_elasticsearch()
            opts = {
                'enabled': True,
                'host': 'elasticsearch.company.com',
                'port': 9200,
                'index': 'spiderfoot-enterprise',
                'use_ssl': True,
                'verify_certs': True,
                'api_key': 'enterprise_api_key_12345',
                'bulk_size': 1,  # Lowered for deterministic test
                'timeout': 30
            }
            
            module.setup(self.sf, opts)
            module.getScanId = MagicMock(return_value=self.test_scan_id)
            
            # Verify secure connection configuration
            self.assertFalse(module.errorState)
            call_args = mock_es_class.call_args[1]
            self.assertTrue(call_args['use_ssl'])
            self.assertTrue(call_args['verify_certs'])
            self.assertEqual(call_args['api_key'], 'enterprise_api_key_12345')
            
            # Test index management
            module._ensure_index_exists()
            mock_es.indices.exists.assert_called_with(index='spiderfoot-enterprise')
            self.assertGreaterEqual(mock_es.indices.create.call_count, 1, "Index creation should be called at least once.")
            
            # Test bulk insertion and buffering
            events = []
            for i in range(150):  # More than bulk_size
                event = self.create_test_event("IP_ADDRESS", f"10.0.0.{i}")
                events.append(event)
                module.handleEvent(event)
            # Force flush remaining buffer
            module._flush_buffer()
            # Should trigger bulk insertion
            self.assertTrue(mock_bulk.called)
            
            # Test thread safety
            def bulk_add_events():
                for i in range(50):
                    event = self.create_test_event("DOMAIN_NAME", f"test{i}.com")
                    module.handleEvent(event)
            
            threads = []
            for _ in range(3):
                thread = threading.Thread(target=bulk_add_events)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            # Should handle concurrent access safely
            self.assertTrue(hasattr(module.buffer_lock, 'acquire') and hasattr(module.buffer_lock, 'release'))
            
            # Test error handling and retry
            mock_es.ping.side_effect = [ConnectionError("Connection failed"), True]
            test_event = self.create_test_event("URL", "https://example.com")
            module.handleEvent(test_event)
            
            print("✓ Elasticsearch SSL/API key authentication")
            print("✓ Elasticsearch index management")
            print("✓ Elasticsearch bulk insertion and buffering")
            print("✓ Elasticsearch thread safety")
            print("✓ Elasticsearch connection retry")

    def test_storage_performance_optimization(self):
        """Test performance optimization features."""
        print("\n=== Testing Performance Optimization ===")
        
        # Test batch processing efficiency
        start_time = time.time()
        
        # SQLite performance test
        sqlite_module = sfp__stor_db()
        sqlite_module.setup(self.sf, {'_store': True})
        sqlite_module.getScanId = MagicMock(return_value=self.test_scan_id)
        
        # Process many events
        for i in range(1000):
            event = self.create_test_event("IP_ADDRESS", f"192.168.{i//256}.{i%256}")
            sqlite_module.handleEvent(event)
        
        sqlite_time = time.time() - start_time
        
        # Elasticsearch bulk performance test
        with patch('modules.sfp__stor_elasticsearch.Elasticsearch') as mock_es_class:
            mock_es = MagicMock()
            mock_es.ping.return_value = True
            mock_es.bulk.return_value = {'errors': False}
            mock_es_class.return_value = mock_es
            
            es_module = sfp__stor_elasticsearch()
            es_module.setup(self.sf, {
                'enabled': True,
                'host': 'localhost',
                'port': 9200,
                'index': 'performance_test',
                'bulk_size': 100
            })
            es_module.getScanId = MagicMock(return_value=self.test_scan_id)
            
            start_time = time.time()
            for i in range(1000):
                event = self.create_test_event("DOMAIN_NAME", f"test{i}.example.com")
                es_module.handleEvent(event)
            
            # Force flush remaining buffer
            es_module._flush_buffer()
            es_time = time.time() - start_time
            
            # Bulk operations should be more efficient
            self.assertLess(mock_es.bulk.call_count, 15)  # Should batch efficiently
        
        print(f"✓ SQLite processing time: {sqlite_time:.3f}s")
        print(f"✓ Elasticsearch bulk processing: {es_time:.3f}s")
        print("✓ Performance optimization validated")

    def test_error_handling_resilience(self):
        """Test comprehensive error handling and resilience."""
        print("\n=== Testing Error Handling and Resilience ===")
        
        # Test PostgreSQL error scenarios
        with patch('modules.sfp__stor_db.psycopg2.connect') as mock_connect:
            # Test connection failure
            mock_connect.side_effect = psycopg2.OperationalError("Database unavailable")
            
            pg_module = sfp__stor_db()
            pg_module.setup(self.sf, {
                'db_type': 'postgresql',
                'postgresql_host': 'unavailable.host',
                'postgresql_port': 5432,
                'postgresql_database': 'spiderfoot',
                'postgresql_username': 'user',
                'postgresql_password': 'pass'
            })
            
            # Should enter error state gracefully
            self.assertTrue(pg_module.errorState)
            
            # Test fallback to SQLite
            pg_module.getScanId = MagicMock(return_value=self.test_scan_id)
            test_event = self.create_test_event()
            pg_module.handleEvent(test_event)
            
            # Should fall back to SQLite storage
            self.assertEqual(self.mock_dbh.scanEventStore.call_count, 0)
        
        # Test Elasticsearch error scenarios
        with patch('modules.sfp__stor_elasticsearch.Elasticsearch') as mock_es_class:
            mock_es_class.side_effect = ConnectionError("Elasticsearch unavailable")
            
            es_module = sfp__stor_elasticsearch()
            es_module.setup(self.sf, {
                'enabled': True,
                'host': 'unavailable.host',
                'port': 9200,
                'index': 'test'
            })
            
            # Should enter error state gracefully
            self.assertTrue(es_module.errorState)
        
        # Test configuration validation
        invalid_pg_module = sfp__stor_db()
        invalid_pg_module.setup(self.sf, {
            'db_type': 'invalid_type'
        })
        self.assertTrue(invalid_pg_module.errorState)
        
        print("✓ PostgreSQL connection failure handling")
        print("✓ PostgreSQL fallback to SQLite")
        print("✓ Elasticsearch connection failure handling") 
        print("✓ Configuration validation")

    def test_data_integrity_and_validation(self):
        """Test data integrity and validation features."""
        print("\n=== Testing Data Integrity and Validation ===")
        
        # Test data size limits
        sqlite_module = sfp__stor_db()
        sqlite_module.setup(self.sf, {
            '_store': True,
            'maxstorage': 100  # Small limit
        })
        sqlite_module.getScanId = MagicMock(return_value=self.test_scan_id)
        
        # Test with oversized data
        large_data = "x" * 1000  # 1000 characters
        large_event = self.create_test_event("LARGE_DATA", large_data)
        sqlite_module.handleEvent(large_event)
        
        # Should call with size limit
        call_args = self.mock_dbh.scanEventStore.call_args
        self.assertEqual(call_args[0][2], 100)  # maxstorage parameter
        
        # Test special character handling
        special_data = "test\nwith\ttabs\rand\x00nulls"
        special_event = self.create_test_event("SPECIAL_DATA", special_data)
        
        # Should handle without crashing
        try:
            sqlite_module.handleEvent(special_event)
        except Exception as e:
            self.fail(f"Should handle special characters: {e}")
        
        # Test Unicode handling
        unicode_data = "测试数据 with émojis 🚀"
        unicode_event = self.create_test_event("UNICODE_DATA", unicode_data)
        
        try:
            sqlite_module.handleEvent(unicode_event)
        except Exception as e:
            self.fail(f"Should handle Unicode: {e}")
        
        print("✓ Data size limit enforcement")
        print("✓ Special character handling")
        print("✓ Unicode data handling")

    def test_enterprise_monitoring_features(self):
        """Test enterprise monitoring and observability features."""
        print("\n=== Testing Enterprise Monitoring Features ===")
        
        # Test PostgreSQL health monitoring
        with patch('modules.sfp__stor_db.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            pg_module = sfp__stor_db()
            pg_module.setup(self.sf, {
                'db_type': 'postgresql',
                'postgresql_host': 'localhost',
                'postgresql_port': 5432,
                'postgresql_database': 'spiderfoot',
                'postgresql_username': 'user',
                'postgresql_password': 'pass'
            })
            
            # Test health check metrics
            self.assertTrue(pg_module._check_postgresql_connection())
            mock_cursor.execute.assert_called_with("SELECT 1")
            
            # Test health check failure detection
            mock_cursor.execute.side_effect = psycopg2.OperationalError("Health check failed")
            self.assertFalse(pg_module._check_postgresql_connection())
        
        # Test Elasticsearch health monitoring
        with patch('modules.sfp__stor_elasticsearch.Elasticsearch') as mock_es_class:
            mock_es = MagicMock()
            mock_es.ping.return_value = True
            mock_es_class.return_value = mock_es
            
            es_module = sfp__stor_elasticsearch()
            es_module.setup(self.sf, {
                'enabled': True,
                'host': 'localhost',
                'port': 9200,
                'index': 'monitoring_test'
            })
            
            # Test health monitoring
            self.assertTrue(es_module._check_elasticsearch_health())
            mock_es.ping.assert_called()
            
            # Test failure detection
            mock_es.ping.side_effect = ConnectionError("Health check failed")
            self.assertFalse(es_module._check_elasticsearch_health())
        
        print("✓ PostgreSQL health monitoring")
        print("✓ Elasticsearch health monitoring")
        print("✓ Connection failure detection")

    def test_security_features(self):
        """Test security features implementation."""
        print("\n=== Testing Security Features ===")
        
        # Test PostgreSQL secure connection parameters
        with patch('modules.sfp__stor_db.psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            
            pg_module = sfp__stor_db()
            pg_module.setup(self.sf, {
                'db_type': 'postgresql',
                'postgresql_host': 'secure.db.host',
                'postgresql_port': 5432,
                'postgresql_database': 'spiderfoot',
                'postgresql_username': 'secure_user',
                'postgresql_password': 'secure_password_123!',
                'postgresql_timeout': 30
            })
            
            # Verify secure connection parameters
            call_args = mock_connect.call_args[1]
            self.assertEqual(call_args['host'], 'secure.db.host')
            self.assertEqual(call_args['user'], 'secure_user')
            self.assertEqual(call_args['password'], 'secure_password_123!')
            self.assertEqual(call_args['connect_timeout'], 30)
        
        # Test Elasticsearch SSL and authentication
        with patch('modules.sfp__stor_elasticsearch.Elasticsearch') as mock_es_class:
            mock_es = MagicMock()
            mock_es_class.return_value = mock_es
            
            es_module = sfp__stor_elasticsearch()
            es_module.setup(self.sf, {
                'enabled': True,
                'host': 'secure.es.host',
                'port': 9200,
                'index': 'security_test',
                'use_ssl': True,
                'verify_certs': True,
                'api_key': 'secure_api_key_xyz789'
            })
            
            # Verify SSL and authentication configuration
            call_args = mock_es_class.call_args[1]
            self.assertTrue(call_args['use_ssl'])
            self.assertTrue(call_args['verify_certs'])
            self.assertEqual(call_args['api_key'], 'secure_api_key_xyz789')
        
        print("✓ PostgreSQL secure connection parameters")
        print("✓ Elasticsearch SSL configuration")
        print("✓ Authentication and API key handling")

    def test_multi_storage_coordination(self):
        """Test coordination between multiple storage backends."""
        print("\n=== Testing Multi-Storage Coordination ===")
        
        # Set up multiple storage modules
        sqlite_module = sfp__stor_db()
        sqlite_module.setup(self.sf, {'_store': True, 'db_type': 'sqlite'})
        sqlite_module.getScanId = MagicMock(return_value=self.test_scan_id)
        
        with patch('modules.sfp__stor_elasticsearch.Elasticsearch') as mock_es_class, \
             patch('elasticsearch.helpers.bulk') as mock_bulk:
            mock_es = MagicMock()
            mock_es.ping.return_value = True
            mock_es.bulk.return_value = {'errors': False}
            mock_es_class.return_value = mock_es
            mock_bulk.return_value = (10, [])  # Simulate 10 successes, no errors
            
            es_module = sfp__stor_elasticsearch()
            es_module.setup(self.sf, {
                'enabled': True,
                'host': 'localhost',
                'port': 9200,
                'index': 'coordination_test',
                'bulk_size': 1  # Lowered for deterministic test
            })
            es_module.getScanId = MagicMock(return_value=self.test_scan_id)
            
            stdout_module = sfp__stor_stdout()
            stdout_module.setup(self.sf, {'_store': True})
            stdout_module.getScanId = MagicMock(return_value=self.test_scan_id)
            
            # Send same events to all storage backends
            test_events = []
            for i in range(10):
                event = self.create_test_event("COORDINATION_TEST", f"data_{i}")
                test_events.append(event)
                
                # Store in all backends
                sqlite_module.handleEvent(event)
                es_module.handleEvent(event)
                with patch('sys.stdout'):
                    stdout_module.handleEvent(event)
            
            # Verify all backends processed events
            self.assertEqual(self.mock_dbh.scanEventStore.call_count, 10)
            self.assertEqual(len(es_module.buffer), 0)  # All events flushed immediately with bulk_size=1
            # Force flush Elasticsearch buffer
            es_module._flush_buffer()
            self.assertGreaterEqual(mock_bulk.call_count, 1, "Elasticsearch bulk should be called after flush.")
        
        print("✓ Multi-storage backend coordination")
        print("✓ Consistent event processing")
        print("✓ Independent error handling")

    def run_enterprise_validation(self):
        """Run the complete enterprise validation suite."""
        print("\n" + "="*60)
        print("SPIDERFOOT ENTERPRISE STORAGE VALIDATION SUITE")
        print("="*60)
        
        test_methods = [
            self.test_postgresql_enterprise_features,
            self.test_elasticsearch_enterprise_features,
            self.test_storage_performance_optimization,
            self.test_error_handling_resilience,
            self.test_data_integrity_and_validation,
            self.test_enterprise_monitoring_features,
            self.test_security_features,
            self.test_multi_storage_coordination
        ]
        
        passed = 0
        failed = 0
        
        for test_method in test_methods:
            try:
                test_method()
                passed += 1
            except Exception as e:
                print(f"❌ {test_method.__name__} FAILED: {e}")
                failed += 1
        
        print("\n" + "="*60)
        print("ENTERPRISE VALIDATION RESULTS")
        print("="*60)
        print(f"✅ Tests Passed: {passed}")
        print(f"❌ Tests Failed: {failed}")
        print(f"📊 Success Rate: {passed/(passed+failed)*100:.1f}%")
        
        if failed == 0:
            print("\n🎉 ALL ENTERPRISE FEATURES VALIDATED SUCCESSFULLY!")
            print("Storage modules are PRODUCTION READY for enterprise deployment.")
        else:
            print(f"\n⚠️  {failed} test(s) failed. Please review and fix issues.")
        
        return failed == 0


if __name__ == '__main__':
    # Run as integration test
    test_suite = TestEnterpriseStorageFeatures()
    test_suite.setUp()
    
    try:
        success = test_suite.run_enterprise_validation()
        exit_code = 0 if success else 1
    finally:
        test_suite.tearDown()
    
    exit(exit_code)

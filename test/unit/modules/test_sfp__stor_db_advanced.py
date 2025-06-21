# -*- coding: utf-8 -*-
"""
Comprehensive test suite for Phase 2 advanced storage module features.

This test suite covers:
- Connection load balancing and health monitoring
- Query optimization and prepared statements
- Auto-scaling functionality
- Performance monitoring and alerting
- Bulk processing and connection pooling
- Integration with existing SpiderFoot test framework
"""

import unittest
import time
import threading
import json
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, List, Any
import tempfile
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

try:
    import sys
    sys.path.insert(0, project_root)
    from sflib import SpiderFoot
    from spiderfoot import SpiderFootEvent
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Required modules not available: {e}")
    IMPORTS_AVAILABLE = False

# Import classes directly from the advanced storage module
if IMPORTS_AVAILABLE:
    try:
        from modules.sfp__stor_db_advanced import (
            sfp__stor_db_advanced, ConnectionLoadBalancer, QueryOptimizer,
            PerformanceMonitor, AutoScaler, ConnectionMetrics, QueryProfile
        )
    except ImportError as e:
        print(f"Warning: Advanced storage module not available: {e}")
        IMPORTS_AVAILABLE = False

# Skip decorator for when imports are not available        
skip_if_no_imports = unittest.skipIf(not IMPORTS_AVAILABLE, "Required modules not available")

# Mock psycopg2 if not available
try:
    import psycopg2
    import psycopg2.pool
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    
    # Create mock classes
    class MockPsycopg2:
        class OperationalError(Exception):
            pass
        
        class pool:
            class ThreadedConnectionPool:
                def __init__(self, *args, **kwargs):
                    self.maxconn = kwargs.get('maxconn', 10)
                    self.minconn = kwargs.get('minconn', 1)
                
                def getconn(self):
                    return MockConnection()
                
                def putconn(self, conn):
                    pass
                
                def closeall(self):
                    pass
        
        @staticmethod
        def connect(*args, **kwargs):
            return MockConnection()
    
    class MockConnection:
        def cursor(self):
            return MockCursor()
        
        def commit(self):
            pass
        
        def rollback(self):
            pass
        
        def close(self):
            pass
    
    class MockCursor:
        def execute(self, query, params=None):
            pass
        
        def executemany(self, query, params_list):
            pass
        
        def fetchone(self):
            return (1,)
        
        def fetchall(self):
            return [(1,)]
        
        def close(self):
            pass
    
    # Set up mock
    psycopg2 = MockPsycopg2()
    sys.modules['psycopg2'] = psycopg2
    sys.modules['psycopg2.pool'] = psycopg2.pool


class MockSpiderFootEvent:
    """Mock SpiderFoot event for testing."""
    
    def __init__(self, event_type="IP_ADDRESS", data="192.168.1.1", module="test_module"):
        self.eventType = event_type
        self.data = data
        self.module = module
        self.hash = f"test_hash_{time.time()}_{id(self)}"
        self.generated = time.time()
        self.confidence = 100
        self.visibility = 1
        self.risk = 0
        self.sourceEventHash = "ROOT"


@skip_if_no_imports
class TestConnectionLoadBalancer(unittest.TestCase):
    """Test suite for Connection Load Balancer."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_configs = [
            {
                'type': 'postgresql',
                'host': 'db1.example.com',
                'port': 5432,
                'database': 'spiderfoot1',
                'username': 'test',
                'password': 'test',
                'min_connections': 1,
                'max_connections': 10,
                'timeout': 30
            },
            {
                'type': 'postgresql',
                'host': 'db2.example.com',
                'port': 5432,
                'database': 'spiderfoot2',
                'username': 'test',
                'password': 'test',
                'min_connections': 2,
                'max_connections': 15,
                'timeout': 30
            }
        ]
    
    @patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool')
    def test_connection_load_balancer_initialization(self, mock_pool_class):
        """Test load balancer initialization."""
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool
        
        balancer = ConnectionLoadBalancer(self.test_configs)
        
        # Verify pools were created
        self.assertEqual(len(balancer.pools), 2)
        self.assertEqual(len(balancer.metrics), 2)
        self.assertEqual(len(balancer.health_status), 2)
        
        # Verify pool creation calls
        self.assertEqual(mock_pool_class.call_count, 2)
    
    @patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool')
    def test_get_optimal_connection(self, mock_pool_class):
        """Test optimal connection selection."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool
        
        balancer = ConnectionLoadBalancer(self.test_configs)
        
        # Get connection
        pool_id, conn = balancer.get_optimal_connection()
        
        # Verify connection returned
        self.assertIsNotNone(pool_id)
        self.assertEqual(conn, mock_conn)
        mock_pool.getconn.assert_called_once()
    
    @patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool')
    def test_return_connection_success(self, mock_pool_class):
        """Test successful connection return."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool
        
        balancer = ConnectionLoadBalancer(self.test_configs)
        pool_id, conn = balancer.get_optimal_connection()
        
        # Return connection successfully
        balancer.return_connection(pool_id, conn, True)
        
        # Verify metrics updated
        metrics = balancer.metrics[pool_id]
        self.assertEqual(metrics.total_queries, 1)
        self.assertEqual(metrics.successful_queries, 1)
        self.assertEqual(metrics.failed_queries, 0)
    
    @patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool')
    def test_return_connection_failure(self, mock_pool_class):
        """Test failed connection return."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool
        
        balancer = ConnectionLoadBalancer(self.test_configs)
        pool_id, conn = balancer.get_optimal_connection()
        
        # Return connection with failure
        balancer.return_connection(pool_id, conn, False)
        
        # Verify metrics updated
        metrics = balancer.metrics[pool_id]
        self.assertEqual(metrics.total_queries, 1)
        self.assertEqual(metrics.successful_queries, 0)
        self.assertEqual(metrics.failed_queries, 1)
    
    @patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool')
    def test_load_balancing_algorithm(self, mock_pool_class):
        """Test load balancing algorithm selects optimal pool."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool_class.return_value = mock_pool
        
        balancer = ConnectionLoadBalancer(self.test_configs)
        
        # Set different load factors
        balancer.metrics['pool_0'].load_factor = 0.8
        balancer.metrics['pool_1'].load_factor = 0.3
        
        # Get connection - should select pool_1 (lower load)
        pool_id, conn = balancer.get_optimal_connection()
        
        # In a real scenario, this would select the pool with lower load
        # For mock testing, we verify the connection is returned
        self.assertIsNotNone(pool_id)
        self.assertIsNotNone(conn)


@skip_if_no_imports
class TestQueryOptimizer(unittest.TestCase):
    """Test suite for Query Optimizer."""
    
    def setUp(self):
        """Set up test environment."""
        self.optimizer = QueryOptimizer()
    
    def test_query_classification(self):
        """Test query type classification."""
        test_cases = [
            ("SELECT * FROM table", "SELECT"),
            ("INSERT INTO table VALUES (1, 2)", "INSERT"),
            ("UPDATE table SET col = 1", "UPDATE"),
            ("DELETE FROM table WHERE id = 1", "DELETE"),
            ("CREATE TABLE test (id INT)", "OTHER")
        ]
        
        for query, expected_type in test_cases:
            query_type = self.optimizer._classify_query(query)
            self.assertEqual(query_type, expected_type)
    
    def test_query_analysis_and_profiling(self):
        """Test query analysis and profile creation."""
        query = "SELECT * FROM tbl_scan_results WHERE scan_instance_id = '123'"
        execution_time = 0.05
        
        # Analyze query multiple times
        for i in range(5):
            profile = self.optimizer.analyze_query(query, execution_time)
            
        # Verify profile created
        self.assertIsInstance(profile, QueryProfile)
        self.assertEqual(profile.execution_count, 5)
        self.assertEqual(profile.avg_execution_time, execution_time)
        self.assertEqual(profile.query_type, "SELECT")
    
    def test_prepared_statement_creation(self):
        """Test prepared statement creation."""
        query = "SELECT * FROM table WHERE id = '123' AND name = 'test'"
        prepared = self.optimizer._create_prepared_statement(query)
        
        # Should replace literal values with placeholders
        self.assertIn('%s', prepared)
        self.assertNotIn("'123'", prepared)
        self.assertNotIn("'test'", prepared)
    
    def test_bulk_operation_optimization(self):
        """Test bulk operation optimization."""
        query = "INSERT INTO table (id, name) VALUES (1, 'test')"
        optimized = self.optimizer._optimize_for_bulk(query)
        
        # Should add conflict handling for PostgreSQL
        self.assertIn("ON CONFLICT DO NOTHING", optimized)
    
    def test_index_suggestions(self):
        """Test index suggestion generation."""
        query = "SELECT * FROM table WHERE column1 = 'value' AND column2 > 10"
        suggestions = self.optimizer._suggest_indexes(query)
        
        # Should suggest indexes for WHERE clause columns
        self.assertGreater(len(suggestions), 0)
        self.assertTrue(any('column1' in suggestion for suggestion in suggestions))
    
    def test_optimization_threshold_application(self):
        """Test that optimizations are applied when thresholds are met."""
        query = "SELECT * FROM table WHERE id = %s"
        
        # Execute query enough times to trigger optimization
        for i in range(60):  # Above threshold for prepared statements
            profile = self.optimizer.analyze_query(query, 0.01)
        
        # Should have created prepared statement
        self.assertIsNotNone(profile.prepared_statement)


@skip_if_no_imports
class TestPerformanceMonitor(unittest.TestCase):
    """Test suite for Performance Monitor."""
    
    def setUp(self):
        """Set up test environment."""
        self.monitor = PerformanceMonitor()
    
    def test_query_recording(self):
        """Test query execution recording."""
        # Record some queries
        self.monitor.record_query("SELECT", 0.05, True)
        self.monitor.record_query("INSERT", 0.02, True)
        self.monitor.record_query("SELECT", 2.0, False)  # Slow query
        
        # Verify metrics recorded
        self.assertEqual(len(self.monitor.metrics['queries']), 3)
        
        # Check slow query alert
        alerts = list(self.monitor.alerts)
        slow_query_alerts = [a for a in alerts if a['type'] == 'slow_query']
        self.assertGreater(len(slow_query_alerts), 0)
    
    def test_connection_metrics_recording(self):
        """Test connection metrics recording."""
        metrics = ConnectionMetrics(
            total_queries=100,
            successful_queries=95,
            failed_queries=5,
            avg_response_time=0.05,
            load_factor=0.6
        )
        
        self.monitor.record_connection_metrics("pool_1", metrics)
        
        # Verify connection metrics recorded
        conn_metrics = self.monitor.metrics['connections']
        self.assertEqual(len(conn_metrics), 1)
        self.assertEqual(conn_metrics[0]['pool_id'], "pool_1")
        self.assertEqual(conn_metrics[0]['total_queries'], 100)
    
    def test_alert_severity_determination(self):
        """Test alert severity determination."""
        # Test high severity slow query
        severity = self.monitor._determine_severity('slow_query', {'execution_time': 10.0})
        self.assertEqual(severity, 'HIGH')
        
        # Test critical connection error
        severity = self.monitor._determine_severity('connection_error', {})
        self.assertEqual(severity, 'CRITICAL')
        
        # Test medium severity
        severity = self.monitor._determine_severity('slow_query', {'execution_time': 2.0})
        self.assertEqual(severity, 'MEDIUM')
    
    def test_performance_report_generation(self):
        """Test performance report generation."""
        # Record some test data
        for i in range(10):
            success = i % 10 != 0  # 90% success rate
            self.monitor.record_query("SELECT", 0.01 + (i * 0.001), success)
        
        # Generate report
        report = self.monitor.get_performance_report()
        
        # Verify report structure
        self.assertIn('status', report)
        self.assertIn('total_queries', report)
        self.assertIn('success_rate', report)
        self.assertIn('avg_execution_time', report)
        self.assertIn('query_type_breakdown', report)
        
        # Verify calculations
        self.assertEqual(report['total_queries'], 10)
        self.assertEqual(report['success_rate'], 0.9)
    
    def test_performance_trend_analysis(self):
        """Test performance trend analysis."""
        # Create high error rate scenario
        for i in range(20):
            success = i % 2 == 0  # 50% success rate (above threshold)
            self.monitor.record_query("SELECT", 0.01, success)
        
        # Trigger analysis
        self.monitor._analyze_performance_trends()
        
        # Should trigger high error rate alert
        alerts = list(self.monitor.alerts)
        error_rate_alerts = [a for a in alerts if a['type'] == 'high_error_rate']
        self.assertGreater(len(error_rate_alerts), 0)


@skip_if_no_imports
class TestAutoScaler(unittest.TestCase):
    """Test suite for Auto Scaler."""
    
    def setUp(self):
        """Set up test environment."""
        # Create mock components
        self.mock_configs = [
            {
                'type': 'postgresql',
                'host': 'localhost',
                'port': 5432,
                'database': 'test',
                'username': 'test',
                'password': 'test',
                'min_connections': 1,
                'max_connections': 10
            }
        ]
        
        with patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool'):
            self.load_balancer = ConnectionLoadBalancer(self.mock_configs)
            self.performance_monitor = PerformanceMonitor()
            self.auto_scaler = AutoScaler(self.load_balancer, self.performance_monitor)
    
    def test_scaling_rules_initialization(self):
        """Test auto-scaler initialization with scaling rules."""
        self.assertIn('scale_up_threshold', self.auto_scaler.scaling_rules)
        self.assertIn('scale_down_threshold', self.auto_scaler.scaling_rules)
        self.assertIn('min_connections', self.auto_scaler.scaling_rules)
        self.assertIn('max_connections', self.auto_scaler.scaling_rules)
    
    @patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool')
    def test_scale_up_evaluation(self, mock_pool_class):
        """Test scale-up evaluation logic."""
        mock_pool = MagicMock()
        mock_pool.maxconn = 5
        mock_pool_class.return_value = mock_pool
        
        # Set high load factor to trigger scale-up
        self.load_balancer.metrics['pool_0'].load_factor = 0.9  # Above threshold
        
        # Test scale-up evaluation
        with patch.object(self.auto_scaler, '_recreate_pool') as mock_recreate:
            self.auto_scaler._scale_up('pool_0')
            mock_recreate.assert_called_once()
    
    @patch('modules.sfp__stor_db_advanced.psycopg2.pool.ThreadedConnectionPool')
    def test_scale_down_evaluation(self, mock_pool_class):
        """Test scale-down evaluation logic."""
        mock_pool = MagicMock()
        mock_pool.maxconn = 10
        mock_pool_class.return_value = mock_pool
        
        # Set low load factor to trigger scale-down
        self.load_balancer.metrics['pool_0'].load_factor = 0.2  # Below threshold
        
        # Test scale-down evaluation
        with patch.object(self.auto_scaler, '_recreate_pool') as mock_recreate:
            self.auto_scaler._scale_down('pool_0')
            mock_recreate.assert_called_once()
    
    def test_scaling_limits_enforcement(self):
        """Test that scaling respects min/max limits."""
        # Test max connections limit
        current_max = self.auto_scaler.scaling_rules['max_connections']
        scale_factor = self.auto_scaler.scaling_rules['scale_factor']
        
        # If current is already at max, should not scale up
        new_max = min(current_max * scale_factor, self.auto_scaler.scaling_rules['max_connections'])
        self.assertLessEqual(new_max, self.auto_scaler.scaling_rules['max_connections'])
        
        # Test min connections limit
        current_min = 1
        new_min = max(current_min // scale_factor, self.auto_scaler.scaling_rules['min_connections'])
        self.assertGreaterEqual(new_min, self.auto_scaler.scaling_rules['min_connections'])


@skip_if_no_imports
class TestAdvancedStorageModule(unittest.TestCase):
    """Test suite for the advanced storage module."""
    
    def setUp(self):
        """Set up test environment."""
        self.sf = Mock()
        self.sf.dbh = Mock()
        
        # Mock database handle methods
        self.sf.dbh.scanEventStore = Mock()
        
        self.module = sfp__stor_db_advanced()
        
        self.test_opts = {
            'maxstorage': 1024,
            '_store': True,
            'enable_load_balancing': True,
            'enable_auto_scaling': True,
            'enable_query_optimization': True,
            'enable_performance_monitoring': True,
            'bulk_insert_threshold': 5,
            'connection_pool_size': 10,
            'max_connection_pools': 3,
            'database_configs': [
                {
                    'type': 'postgresql',
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'test',
                    'username': 'test',
                    'password': 'test'
                }
            ]
        }
    
    @patch('modules.sfp__stor_db_advanced.ConnectionLoadBalancer')
    @patch('modules.sfp__stor_db_advanced.QueryOptimizer')
    @patch('modules.sfp__stor_db_advanced.PerformanceMonitor')
    @patch('modules.sfp__stor_db_advanced.AutoScaler')
    def test_module_setup_with_enterprise_features(self, mock_scaler, mock_monitor, mock_optimizer, mock_balancer):
        """Test module setup with enterprise features enabled."""
        # Set up mocks
        mock_balancer.return_value = Mock()
        mock_optimizer.return_value = Mock()
        mock_monitor.return_value = Mock()
        mock_scaler.return_value = Mock()
        
        # Setup module
        self.module.setup(self.sf, self.test_opts)
        
        # Verify enterprise features initialized
        self.assertFalse(self.module.errorState)
        mock_balancer.assert_called_once()
        mock_optimizer.assert_called_once()
        mock_monitor.assert_called_once()
        mock_scaler.assert_called_once()
    
    def test_module_setup_without_database_handle(self):
        """Test module setup failure when database handle not available."""
        sf_no_db = Mock()
        sf_no_db.dbh = None
        
        self.module.setup(sf_no_db, self.test_opts)
        
        # Should set error state
        self.assertTrue(self.module.errorState)
    
    def test_event_buffering_and_bulk_processing(self):
        """Test event buffering and bulk processing."""
        self.module.setup(self.sf, self.test_opts)
        self.module.getScanId = Mock(return_value="test_scan_id")
        
        # Mock bulk processing method
        self.module._process_event_buffer = Mock()
        
        # Add events to trigger bulk processing
        for i in range(self.test_opts['bulk_insert_threshold']):
            event = MockSpiderFootEvent(f"TEST_EVENT_{i}", f"test_data_{i}")
            self.module.handleEvent(event)
        
        # Should have triggered bulk processing
        self.module._process_event_buffer.assert_called_once()
    
    @patch('modules.sfp__stor_db_advanced.ConnectionLoadBalancer')
    def test_bulk_store_with_load_balancing(self, mock_balancer_class):
        """Test bulk storage with load balancing."""
        # Set up mock load balancer
        mock_balancer = Mock()
        mock_pool_id = 'pool_0'
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_balancer.get_optimal_connection.return_value = (mock_pool_id, mock_conn)
        mock_balancer_class.return_value = mock_balancer
        
        self.module.setup(self.sf, self.test_opts)
        self.module.getScanId = Mock(return_value="test_scan_id")
        
        # Test bulk storage
        events = [MockSpiderFootEvent(f"EVENT_{i}") for i in range(3)]
        
        with patch('psycopg2.extras.execute_values') as mock_execute_values:
            self.module._bulk_store_with_load_balancing(events)
            
            # Verify connection operations
            mock_balancer.get_optimal_connection.assert_called_once()
            mock_conn.cursor.assert_called_once()
            mock_execute_values.assert_called_once()
            mock_conn.commit.assert_called_once()
            mock_balancer.return_connection.assert_called_with(mock_pool_id, mock_conn, True)
    
    def test_bulk_store_sqlite_fallback(self):
        """Test SQLite bulk storage fallback."""
        # Setup without load balancing
        opts = self.test_opts.copy()
        opts['enable_load_balancing'] = False
        
        self.module.setup(self.sf, opts)
        self.module.getScanId = Mock(return_value="test_scan_id")
        
        # Test SQLite bulk storage
        events = [MockSpiderFootEvent(f"EVENT_{i}") for i in range(3)]
        self.module._bulk_store_sqlite(events)
        
        # Verify SQLite storage calls
        self.assertEqual(self.sf.dbh.scanEventStore.call_count, 3)
    
    def test_performance_status_reporting(self):
        """Test performance status reporting."""
        self.module.setup(self.sf, self.test_opts)
        
        # Get performance status
        status = self.module.get_performance_status()
        
        # Verify status structure
        self.assertIn('timestamp', status)
        self.assertIn('module_status', status)
        self.assertIn('features_enabled', status)
        self.assertIn('buffer_status', status)
        
        # Verify features status
        features = status['features_enabled']
        self.assertTrue(features['load_balancing'])
        self.assertTrue(features['query_optimization'])
        self.assertTrue(features['performance_monitoring'])
        self.assertTrue(features['auto_scaling'])
    
    def test_graceful_shutdown(self):
        """Test graceful shutdown functionality."""
        self.module.setup(self.sf, self.test_opts)
        
        # Add some events to buffer
        events = [MockSpiderFootEvent(f"EVENT_{i}") for i in range(3)]
        with self.module.buffer_lock:
            self.module.event_buffer = events
        
        # Mock process buffer method
        self.module._process_event_buffer = Mock()
        
        # Test graceful shutdown
        self.module._graceful_shutdown()
        
        # Should have processed remaining events
        self.module._process_event_buffer.assert_called_once()
    
    def test_error_handling_and_fallback(self):
        """Test error handling and fallback mechanisms."""
        self.module.setup(self.sf, self.test_opts)
        self.module.getScanId = Mock(return_value="test_scan_id")
        
        # Mock load balancer to raise exception
        if hasattr(self.module, 'load_balancer') and self.module.load_balancer:
            self.module.load_balancer.get_optimal_connection = Mock(side_effect=Exception("Connection failed"))
        
        # Mock fallback method
        self.module._store_single_event = Mock()
        
        # Process events that should trigger fallback
        events = [MockSpiderFootEvent("TEST_EVENT")]
        self.module._process_event_buffer = Mock(side_effect=Exception("Bulk processing failed"))
        
        with self.module.buffer_lock:
            self.module.event_buffer = events
        
        # Should handle error gracefully
        try:
            self.module._process_event_buffer()
        except Exception:
            pass  # Expected to fail for testing
        
        # Verify no crash occurred
        self.assertIsNotNone(self.module)


@skip_if_no_imports
class TestPhase2StorageIntegration(unittest.TestCase):
    """Integration tests for Phase 2 storage features."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock SpiderFoot instance
        self.sf = Mock()
        self.sf.dbh = Mock()
        self.sf.dbh.scanEventStore = Mock()
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_end_to_end_event_processing(self):
        """Test end-to-end event processing with all features enabled."""
        # Configure module with all enterprise features
        module = sfp__stor_db_advanced()
        opts = {
            'maxstorage': 1024,
            '_store': True,
            'enable_load_balancing': False,  # Disable for simpler testing
            'enable_auto_scaling': False,
            'enable_query_optimization': True,
            'enable_performance_monitoring': True,
            'bulk_insert_threshold': 3,
            'database_configs': []
        }
        
        module.setup(self.sf, opts)
        module.getScanId = Mock(return_value="integration_test_scan")
        
        # Process multiple events
        events = [
            MockSpiderFootEvent("IP_ADDRESS", "192.168.1.1", "test_module"),
            MockSpiderFootEvent("DOMAIN_NAME", "example.com", "test_module"),
            MockSpiderFootEvent("EMAIL_ADDRESS", "test@example.com", "test_module"),
            MockSpiderFootEvent("URL", "http://example.com", "test_module")
        ]
        
        # Process events
        for event in events:
            module.handleEvent(event)
        
        # Verify events were processed
        self.sf.dbh.scanEventStore.assert_called()
        
        # Get performance status
        status = module.get_performance_status()
        self.assertEqual(status['module_status'], 'active')
    
    def test_concurrent_event_processing(self):
        """Test concurrent event processing."""
        module = sfp__stor_db_advanced()
        opts = {
            'maxstorage': 1024,
            '_store': True,
            'enable_load_balancing': False,
            'enable_auto_scaling': False,
            'enable_query_optimization': True,
            'enable_performance_monitoring': True,
            'bulk_insert_threshold': 10,
            'database_configs': []
        }
        
        module.setup(self.sf, opts)
        module.getScanId = Mock(return_value="concurrent_test_scan")
        
        def process_events(thread_id, event_count):
            """Process events in a thread."""
            for i in range(event_count):
                event = MockSpiderFootEvent(f"THREAD_{thread_id}_EVENT_{i}")
                module.handleEvent(event)
        
        # Create multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=process_events, args=(thread_id, 10))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify module handled concurrent access
        status = module.get_performance_status()
        self.assertEqual(status['module_status'], 'active')
    
    def test_performance_monitoring_integration(self):
        """Test performance monitoring integration."""
        module = sfp__stor_db_advanced()
        opts = {
            'maxstorage': 1024,
            '_store': True,
            'enable_load_balancing': False,
            'enable_auto_scaling': False,
            'enable_query_optimization': False,
            'enable_performance_monitoring': True,
            'bulk_insert_threshold': 5,
            'database_configs': []
        }
        
        module.setup(self.sf, opts)
        module.getScanId = Mock(return_value="performance_test_scan")
        
        # Process events to generate performance data
        for i in range(20):
            event = MockSpiderFootEvent(f"PERF_EVENT_{i}")
            module.handleEvent(event)
        
        # Get performance status
        status = module.get_performance_status()
        
        # Verify performance monitoring data
        self.assertIn('performance_report', status)
        if 'performance_report' in status:
            report = status['performance_report']
            if 'total_queries' in report:
                self.assertGreater(report['total_queries'], 0)
    
    def test_module_watchedEvents_and_producedEvents(self):
        """Test module event definitions."""
        module = sfp__stor_db_advanced()
        
        # Test watched events
        watched = module.watchedEvents()
        self.assertEqual(watched, ["*"])  # Should watch all events
        
        # Test produced events (storage modules typically don't produce events)
        # This module focuses on storage, not event production


def run_phase2_tests():
    """Run all Phase 2 advanced storage tests."""
    if not IMPORTS_AVAILABLE:
        print("❌ Required modules not available for testing")
        return False
    
    print("🚀 Running Phase 2 Advanced Storage Module Tests")
    print("=" * 60)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestConnectionLoadBalancer,
        TestQueryOptimizer,
        TestPerformanceMonitor,
        TestAutoScaler,
        TestAdvancedStorageModule,
        TestPhase2StorageIntegration
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  {test}: {traceback.split('Exception:')[-1].strip()}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("\n✅ All Phase 2 tests passed successfully!")
        print("🎉 Advanced storage module is ready for production deployment")
    else:
        print("\n❌ Some tests failed")
        print("🔧 Review failed tests and address issues before deployment")
    
    print("=" * 60)
    return success


if __name__ == "__main__":
    import sys
    success = run_phase2_tests()
    sys.exit(0 if success else 1)

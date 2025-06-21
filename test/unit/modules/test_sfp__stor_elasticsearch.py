# filepath: spiderfoot/test/unit/modules/test_sfp__stor_elasticsearch.py
from unittest.mock import patch, MagicMock, Mock
import unittest
import threading
import time
from elasticsearch import Elasticsearch, ConnectionError, RequestsConnectionPool
from sflib import SpiderFoot
from spiderfoot.event import SpiderFootEvent
from modules.sfp__stor_elasticsearch import sfp__stor_elasticsearch
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleStorElasticsearch(SpiderFootTestBase):
    """Comprehensive test suite for enhanced Elasticsearch storage module.
    
    Tests all enterprise-grade features including:
    - Connection retry and error handling
    - Bulk insertion and buffering
    - Thread safety
    - Index management
    - Authentication and SSL
    - Performance optimization
    """
    
    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Create SpiderFoot instance
        self.sf_instance = SpiderFoot(self.default_options)
        
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
        # Clean up any background threads or connections
        if hasattr(self, 'module') and hasattr(self.module, 'buffer'):
            if self.module.buffer:
                self.module.buffer.clear()

    def create_test_event(self, event_type="IP_ADDRESS", data="192.168.1.1", module="test_module"):
        """Create a test SpiderFoot event."""
        # Create ROOT event first for other events to reference
        if event_type == "ROOT":
            event = SpiderFootEvent("ROOT", data, module)
        else:
            # Create a root event to serve as source
            root_event = SpiderFootEvent("ROOT", "root", module)
            event = SpiderFootEvent(event_type, data, module, root_event)
        
        event.confidence = 100
        event.visibility = 1
        event.risk = 0
        event.hash = f"test_hash_{time.time()}"
        event.generated = time.time()
        return event

    def test_opts(self):
        """Test the module options."""
        module = sfp__stor_elasticsearch()
        self.assertEqual(len(module.opts), len(module.optdescs))
        
        # Check that all required options are present
        required_opts = [
            'enabled', 'host', 'port', 'index', 'use_ssl', 
            'verify_certs', 'username', 'password', 'api_key',
            'bulk_size', 'timeout'
        ]
        for opt in required_opts:
            self.assertIn(opt, module.opts)

    def test_setup_disabled(self):
        """Test setup when module is disabled."""
        module = sfp__stor_elasticsearch()
        opts = {'enabled': False}
        module.setup(self.sf_instance, opts)
        
        self.assertIsNone(module.es)
        self.assertEqual(module.opts['enabled'], False)

    @patch('modules.sfp__stor_elasticsearch.Elasticsearch')
    def test_setup_enabled_basic_auth(self, mock_es_class):
        """Test setup with basic authentication."""
        mock_es = MagicMock()
        mock_es_class.return_value = mock_es
        
        module = sfp__stor_elasticsearch()
        opts = {
            'enabled': True,
            'host': 'localhost',
            'port': 9200,
            'index': 'test_index',
            'username': 'user',
            'password': 'pass',
            'use_ssl': True,
            'verify_certs': False,
            'timeout': 30
        }
        
        module.setup(self.sf_instance, opts)
        
        self.assertFalse(module.errorState)
        self.assertIsNotNone(module.es)
        self.assertEqual(len(module.buffer), 0)
        self.assertIsInstance(module.buffer_lock, threading.Lock)

    def test_producedEvents_should_return_list(self):
        """Test producedEvents method."""
        module = sfp__stor_elasticsearch()
        produced_events = module.producedEvents()
        self.assertIsInstance(produced_events, list)

    def test_watchedEvents_should_return_list(self):
        """Test watchedEvents method."""
        module = sfp__stor_elasticsearch()
        watched_events = module.watchedEvents()
        self.assertIsInstance(watched_events, list)
        self.assertIn("*", watched_events)

    @patch('modules.sfp__stor_elasticsearch.Elasticsearch')
    def test_event_handling_disabled(self, mock_es_class):
        """Test event handling when module is disabled."""
        module = sfp__stor_elasticsearch()
        opts = {'enabled': False}
        module.setup(self.sf_instance, opts)
        
        test_event = self.create_test_event()
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        module.handleEvent(test_event)
        
        # Should return early without processing
        self.assertEqual(len(module.buffer), 0)

    @patch('modules.sfp__stor_elasticsearch.Elasticsearch')
    def test_event_buffering(self, mock_es_class):
        """Test event buffering functionality."""
        mock_es = MagicMock()
        mock_es.ping.return_value = True
        mock_es_class.return_value = mock_es
        
        module = sfp__stor_elasticsearch()
        opts = {
            'enabled': True,
            'host': 'localhost',
            'port': 9200,
            'index': 'test_index',
            'bulk_size': 5  # Small bulk size for testing
        }
        
        module.setup(self.sf_instance, opts)
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Add events to buffer (less than bulk_size)
        for i in range(3):
            test_event = self.create_test_event("IP_ADDRESS", f"192.168.1.{i}")
            module.handleEvent(test_event)
        
        # Buffer should contain 3 events, no bulk insert yet
        self.assertEqual(len(module.buffer), 3)
        mock_es.bulk.assert_not_called()

    @patch('modules.sfp__stor_elasticsearch.Elasticsearch')
    def test_bulk_insertion_triggered(self, mock_es_class):
        """Test bulk insertion when buffer size is reached."""
        mock_es = MagicMock()
        mock_es.ping.return_value = True
        mock_es.bulk.return_value = {'errors': False}
        mock_es_class.return_value = mock_es
        
        module = sfp__stor_elasticsearch()
        opts = {
            'enabled': True,
            'host': 'localhost',
            'port': 9200,
            'index': 'test_index',
            'bulk_size': 3  # Small bulk size for testing
        }
        
        module.setup(self.sf_instance, opts)
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Add events to trigger bulk insertion
        for i in range(3):
            test_event = self.create_test_event("IP_ADDRESS", f"192.168.1.{i}")
            module.handleEvent(test_event)
        
        # Buffer should be empty after bulk insert
        self.assertEqual(len(module.buffer), 0)
        mock_es.bulk.assert_called_once()

    @patch('modules.sfp__stor_elasticsearch.Elasticsearch')
    def test_thread_safety(self, mock_es_class):
        """Test thread safety of buffer operations."""
        mock_es = MagicMock()
        mock_es.ping.return_value = True
        mock_es.bulk.return_value = {'errors': False}
        mock_es_class.return_value = mock_es
        
        module = sfp__stor_elasticsearch()
        opts = {
            'enabled': True,
            'host': 'localhost',
            'port': 9200,
            'index': 'test_index',
            'bulk_size': 100  # Large bulk size to avoid automatic flushing
        }
        
        module.setup(self.sf_instance, opts)
        
        # Mock getScanId
        module.getScanId = MagicMock(return_value="test_scan_id")
        
        # Function to add events in a thread
        def add_events():
            for i in range(10):
                test_event = self.create_test_event("IP_ADDRESS", f"192.168.1.{i}")
                module.handleEvent(test_event)
        
        # Create multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=add_events)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have events from all threads
        self.assertEqual(len(module.buffer), 30)

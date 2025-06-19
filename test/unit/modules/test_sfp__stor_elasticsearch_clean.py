# filepath: spiderfoot/test/unit/modules/test_sfp__stor_elasticsearch.py
from unittest.mock import patch, MagicMock
import unittest
from sflib import SpiderFoot
from spiderfoot.event import SpiderFootEvent
from modules.sfp__stor_elasticsearch import sfp__stor_elasticsearch
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleStorElasticsearch(SpiderFootTestBase):
    """Test Stor Elasticsearch module."""
    
    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def test_opts(self):
        """Test the module options."""
        module = sfp__stor_elasticsearch()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp__stor_elasticsearch()
        module.setup(sf, self.default_options)
        self.assertIsNotNone(module.options)
        self.assertTrue('_debug' in module.options)

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

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

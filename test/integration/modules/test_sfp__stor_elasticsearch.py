import pytest
import unittest
import time
from elasticsearch import Elasticsearch, ElasticsearchException

from modules.sfp__stor_elasticsearch import sfp__stor_elasticsearch
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(unittest.TestCase):
    """
    Base class for module integration tests.
    """

    def setup_module(self, module_class):
        """
        Set up the module for testing.
        """
        sf = SpiderFoot(self.default_options)
        module = module_class()
        module.setup(sf, dict())
        return module

    def create_event(self, target_value, target_type, event_type, event_data):
        """
        Create a SpiderFoot event for testing.
        """
        target = SpiderFootTarget(target_value, target_type)
        event = SpiderFootEvent(event_type, event_data, '', '')
        return target, event


@pytest.mark.usefixtures
class TestModuleIntegration_stor_elasticsearch(BaseTestModuleIntegration):
    """
    Integration tests for the sfp__stor_elasticsearch module.
    """

    def setUp(self):
        """
        Set up resources before each test.
        """
        self.module = self.setup_module(sfp__stor_elasticsearch)

    def tearDown(self):
        """
        Clean up resources after each test.
        """
        self.module = None

    def setup_elasticsearch_with_retries(self, timeout, retries=3, backoff_factor=0.3):
        """
        Set up an Elasticsearch connection with retries.
        """
        for attempt in range(retries):
            try:
                es = Elasticsearch(timeout=timeout)
                es.info()  # Check if the connection is successful
                return es
            except ElasticsearchException as e:
                if attempt < retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))
                else:
                    raise e

    def test_handleEvent(self):
        """
        Test the handleEvent method of the sfp__stor_elasticsearch module.
        """
        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        event_type = 'ROOT'
        event_data = 'example data'
        target, event = self.create_event(target_value, target_type, event_type, event_data)

        self.module.setTarget(target)
        result = self.module.handleEvent(event)

        self.assertIsNone(result)

import pytest
import unittest
import time
from elasticsearch import Elasticsearch, ElasticsearchException

from modules.sfp__stor_elasticsearch import sfp__stor_elasticsearch
from sflib import SpiderFoot
from test.unit.modules.test_module_base import SpiderFootModuleTestCase
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(SpiderFootModuleTestCase):
    """
    Base class for module integration tests.
    """

    def setup_module(self, module_class):
        """
        Set up the module for testing.

        Args:
            module_class (type): The module class to set up.

        Returns:
            None
        """
        sf = SpiderFoot(self.default_options)
        module = module_class()
        module.setup(sf, dict())
        return module

    def create_event(self, target_value, target_type, event_type, event_data):
        """
        Create a SpiderFoot event for testing.

        Args:
            event_type (str): The type of the event.
            event_data (str): The data of the event.
            target_type (str): The type of the target.
            target_value (str): The value of the target.

        Returns:
            SpiderFootEvent: The created event.
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

        Args:
            retries (int): The number of retries.
            timeout (int): The timeout for each retry.
            backoff_factor (float): The backoff factor for retries.

        Returns:
            Elasticsearch: The Elasticsearch connection.

        Raises:
            ElasticsearchException: If the connection fails.
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

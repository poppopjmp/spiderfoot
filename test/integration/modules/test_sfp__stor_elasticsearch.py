import pytest
import unittest
import time
from elasticsearch import Elasticsearch, ElasticsearchException

from modules.sfp__stor_elasticsearch import sfp__stor_elasticsearch
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(unittest.TestCase):

    def setup_module(self, module_class):
        sf = SpiderFoot(self.default_options)
        module = module_class()
        module.setup(sf, dict())
        return module

    def create_event(self, target_value, target_type, event_type, event_data):
        target = SpiderFootTarget(target_value, target_type)
        evt = SpiderFootEvent(event_type, event_data, '', '')
        return target, evt


@pytest.mark.usefixtures
class TestModuleIntegration_stor_elasticsearch(BaseTestModuleIntegration):

    def setup_elasticsearch_with_retries(self, timeout, retries=3, backoff_factor=0.3):
        for i in range(retries):
            try:
                es = Elasticsearch(timeout=timeout)
                es.info()  # Check if the connection is successful
                return es
            except ElasticsearchException as e:
                if i < retries - 1:
                    time.sleep(backoff_factor * (2 ** i))
                else:
                    raise e

    def test_handleEvent(self):
        module = self.setup_module(sfp__stor_elasticsearch)

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        event_type = 'ROOT'
        event_data = 'example data'
        target, evt = self.create_event(target_value, target_type, event_type, event_data)

        module.setTarget(target)
        result = module.handleEvent(evt)

        self.assertIsNone(result)

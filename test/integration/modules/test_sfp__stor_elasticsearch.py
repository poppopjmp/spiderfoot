import pytest
import unittest
import time
from elasticsearch import Elasticsearch, ElasticsearchException

from modules.sfp__stor_elasticsearch import sfp__stor_elasticsearch
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


@pytest.mark.usefixtures
class TestModuleIntegration_stor_elasticsearch(unittest.TestCase):

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

    def test_setup(self):
        sf = SpiderFoot(self.default_options)

        module = sfp__stor_elasticsearch()
        module.setup(sf, dict())

        module.es = self.setup_elasticsearch_with_retries(timeout=10)
        self.assertIsNotNone(module.es)

    def test_watchedEvents(self):
        sf = SpiderFoot(self.default_options)

        module = sfp__stor_elasticsearch()
        module.setup(sf, dict())

        self.assertEqual(module.watchedEvents(), ["*"])

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)

        module = sfp__stor_elasticsearch()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)

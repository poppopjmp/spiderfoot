import pytest
import unittest
from unittest.mock import patch

from modules.sfp_binaryedge import sfp_binaryedge
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationBinaryedge(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'binaryedge_api_key': 'dummy'})
        self.module = sfp_binaryedge()
        self.module.setup(self.sf, {'binaryedge_api_key': 'dummy'})
        self.events = []
        self.module.notifyListeners = lambda evt: self.events.append(evt)

    @patch.object(sfp_binaryedge, 'query')
    def test_handleEvent(self, mock_query):
        # Simulate a valid API response for an IP_ADDRESS event
        def query_side_effect(eventData, queryType=None):
            if queryType == "passive":
                return [{
                    'events': [
                        {'domain': 'cohosted.example.com', 'origin': {'ts': 0}}
                    ]
                }]
            return None
        mock_query.side_effect = query_side_effect
        target_value = '8.8.8.8'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        event_type = 'IP_ADDRESS'
        event_data = '8.8.8.8'
        event_module = 'test'
        source_event = SpiderFootEvent('ROOT', 'root', 'test', None)
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        self.module.handleEvent(evt)
        # The module should emit at least one event for the co-hosted site
        found = any(evt.eventType == 'CO_HOSTED_SITE' and evt.data == 'cohosted.example.com' for evt in self.events)
        self.assertTrue(found, 'CO_HOSTED_SITE event not emitted for cohosted domain')

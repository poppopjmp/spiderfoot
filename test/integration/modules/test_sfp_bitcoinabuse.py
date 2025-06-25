import pytest
import unittest
from unittest.mock import patch

from modules.sfp_bitcoinabuse import sfp_bitcoinabuse
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationBitcoinAbuse(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'api_key': 'dummy'})
        self.module = sfp_bitcoinabuse()
        self.module.setup(self.sf, {'api_key': 'dummy'})
        self.events = []
        self.module.notifyListeners = lambda evt: self.events.append(evt)

    @patch.object(sfp_bitcoinabuse, 'queryAddress')
    def test_handleEvent(self, mock_queryAddress):
        # Simulate a valid API response for a BITCOIN_ADDRESS event
        mock_queryAddress.return_value = {
            'count': 1,
            'address': '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        }
        target_value = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        target_type = 'BITCOIN_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        event_type = 'BITCOIN_ADDRESS'
        event_data = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        event_module = 'test'
        source_event = SpiderFootEvent('ROOT', 'root', 'test', None)
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        self.module.handleEvent(evt)
        # The module should emit a MALICIOUS_BITCOIN_ADDRESS event
        found = any(evt.eventType == 'MALICIOUS_BITCOIN_ADDRESS' and '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa' in evt.data for evt in self.events)
        self.assertTrue(found, 'MALICIOUS_BITCOIN_ADDRESS event not emitted for known address')

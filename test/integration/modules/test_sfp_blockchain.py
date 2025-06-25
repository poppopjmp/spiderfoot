import pytest
import unittest
from unittest.mock import patch

from modules.sfp_blockchain import sfp_blockchain
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationBlockchain(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 10,
            '_useragent': 'SpiderFootTestAgent'
        })
        self.module = sfp_blockchain()
        self.module.setup(self.sf, {
            '_fetchtimeout': 10,
            '_useragent': 'SpiderFootTestAgent'
        })
        self.module.__name__ = 'sfp_blockchain'
        self.events = []
        self.module.notifyListeners = lambda evt: self.events.append(evt)

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent(self, mock_fetchUrl):
        # Simulate a valid Blockchain.info API response for a BITCOIN_ADDRESS event
        address = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        mock_fetchUrl.return_value = {
            'content': '{"%s": {"final_balance": 123456789}}' % address,
            'code': '200'
        }
        target_value = address
        target_type = 'BITCOIN_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        event_type = 'BITCOIN_ADDRESS'
        event_data = address
        event_module = 'test'
        source_event = SpiderFootEvent('ROOT', 'rootdata', '', 'sfp_blockchain')
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        self.module.handleEvent(evt)
        # The module should emit a BITCOIN_BALANCE event with the correct balance
        found = any(evt.eventType == 'BITCOIN_BALANCE' and '1.23456789 BTC' in evt.data for evt in self.events)
        self.assertTrue(found, 'BITCOIN_BALANCE event not emitted for known address')

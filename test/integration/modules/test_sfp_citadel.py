import pytest
import unittest
from unittest.mock import patch
import json

from modules.sfp_citadel import sfp_citadel
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationcitadel(unittest.TestCase):

    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        })
        self.module = sfp_citadel()
        self.module.__name__ = 'sfp_citadel'
        self.options = {
            'api_key': 'DUMMYKEY',
            'timeout': 5,
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_emailaddr_compromised(self, mock_fetch):
        # Simulate Leak-Lookup API response with a breach
        api_response = {'error': 'false', 'message': ['breachsite.com']}
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(api_response)}
        target = SpiderFootTarget('test@example.com', 'EMAILADDR')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('EMAILADDR', 'test@example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'EMAILADDR_COMPROMISED' in event_types
        # Check event data contains the expected breach site
        found = any('breachsite.com' in e.data for e in self.events if e.eventType == 'EMAILADDR_COMPROMISED')
        assert found, 'EMAILADDR_COMPROMISED event data does not contain expected breach site.'

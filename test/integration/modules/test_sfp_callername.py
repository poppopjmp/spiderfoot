import pytest
import unittest
from unittest.mock import patch

from modules.sfp_callername import sfp_callername
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationcallername(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        })
        self.module = sfp_callername()
        self.module.__name__ = 'sfp_callername'
        self.options = {
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_us_number_malicious(self, mock_fetch):
        # Simulate HTML response with location and more unsafe than safe votes
        html = '''<div class="callerid"><h4>Location</h4><p>New York, NY</p></div>
        >SAFE<span>1 votes<
        >UNSAFE<span>5 votes<'''
        mock_fetch.return_value = {'code': '200', 'content': html}
        target = SpiderFootTarget('+12345678900', 'PHONE_NUMBER')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('PHONE_NUMBER', '+12345678900', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'GEOINFO' in event_types
        assert 'MALICIOUS_PHONE_NUMBER' in event_types
        # Check event data contains CallerName URL
        for e in self.events:
            if e.eventType == 'MALICIOUS_PHONE_NUMBER':
                assert 'https://callername.com/2345678900' in e.data

import pytest
import unittest
from unittest.mock import patch
import json

from modules.sfp_threatcrowd import sfp_threatcrowd
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent



class DummyEventListener:
    def __init__(self):
        self.events = []
    def notifyListeners(self, event):
        self.events.append(event)

class TestModuleIntegrationThreatcrowd(unittest.TestCase):
    def setUp(self):
        self.options = {
            '_fetchtimeout': 5
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_threatcrowd()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_threatcrowd'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('sflib.SpiderFoot.fetchUrl')
    @patch('sflib.SpiderFoot.validIP', lambda self, x: True)
    def test_handleEvent_emits_malicious_ipaddr(self, mock_fetch):
        # Simulate ThreatCrowd API response for a malicious IP
        test_ip = '1.2.3.4'
        api_response = {'votes': -1, 'permalink': 'https://www.threatcrowd.org/ip/1.2.3.4.html'}
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(api_response)}
        event = SpiderFootEvent('IP_ADDRESS', test_ip, 'test_module', None)
        self.module.handleEvent(event)
        # Assert that a MALICIOUS_IPADDR event was emitted
        events = [e for e in self.listener.events if e.eventType == 'MALICIOUS_IPADDR']
        assert len(events) == 1
        assert 'threatcrowd.org' in events[0].data
        assert test_ip in events[0].data

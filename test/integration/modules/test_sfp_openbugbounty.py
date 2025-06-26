import pytest
import unittest
from unittest.mock import patch

from modules.sfp_openbugbounty import sfp_openbugbounty
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent



class DummyEventListener:
    def __init__(self):
        self.events = []
    def notifyListeners(self, event):
        self.events.append(event)

class TestModuleIntegrationOpenbugbounty(unittest.TestCase):
    def setUp(self):
        self.options = {
            '_useragent': 'SpiderFootTestAgent',
            '_fetchtimeout': 5
        }
        self.sf = SpiderFoot(self.options)
        self.module = sfp_openbugbounty()
        self.module.setup(self.sf, self.options)
        self.module.__name__ = 'sfp_openbugbounty'  # Needed for event emission
        self.listener = DummyEventListener()
        self.module.notifyListeners = self.listener.notifyListeners

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_emits_vulnerability_disclosure(self, mock_fetch):
        # Simulate HTML response containing a match for the test domain
        test_domain = 'example.com'
        html = f'<div class="cell1"><a href="/vuln/123">{test_domain}</a></div>'
        mock_fetch.return_value = {'code': '200', 'content': html}
        event = SpiderFootEvent('INTERNET_NAME', test_domain, 'test_module', None)
        self.module.handleEvent(event)
        # Assert that a VULNERABILITY_DISCLOSURE event was emitted
        events = [e for e in self.listener.events if e.eventType == 'VULNERABILITY_DISCLOSURE']
        assert len(events) == 1
        assert 'openbugbounty.org' in events[0].data

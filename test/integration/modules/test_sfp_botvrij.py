import pytest
import unittest
from unittest.mock import patch

from modules.sfp_botvrij import sfp_botvrij
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationBotvrij(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        })
        self.module = sfp_botvrij()
        self.module.__name__ = 'sfp_botvrij'
        self.options = {
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            'checkaffiliates': True,
            'checkcohosts': True,
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_internet_name_blacklisted(self, mock_fetch):
        # Simulate blocklist containing 'malicious.com'
        blocklist = 'malicious.com\nbenign.com\n'
        mock_fetch.return_value = {'code': '200', 'content': blocklist}
        target = SpiderFootTarget('malicious.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('INTERNET_NAME', 'malicious.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'MALICIOUS_INTERNET_NAME' in event_types
        assert 'BLACKLISTED_INTERNET_NAME' in event_types
        # Check event data contains Botvrij blocklist URL
        for e in self.events:
            if e.eventType in ('MALICIOUS_INTERNET_NAME', 'BLACKLISTED_INTERNET_NAME'):
                assert 'https://www.botvrij.eu/data/blocklist/blocklist_full.csv' in e.data

import pytest
import unittest
from unittest.mock import patch

from modules.sfp_botscout import sfp_botscout
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationBotscout(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        })
        self.module = sfp_botscout()
        self.module.__name__ = 'sfp_botscout'
        self.options = {
            'api_key': 'DUMMYKEY',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_ip_positive(self, mock_fetch):
        # Simulate a positive BotScout response for IP
        mock_fetch.return_value = {'code': '200', 'content': 'Y|IP|1|2|3'}
        target = SpiderFootTarget('8.8.8.8', 'IP_ADDRESS')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('IP_ADDRESS', '8.8.8.8', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'MALICIOUS_IPADDR' in event_types
        assert 'BLACKLISTED_IPADDR' in event_types
        # Check event data contains BotScout URL
        for e in self.events:
            if e.eventType == 'MALICIOUS_IPADDR' or e.eventType == 'BLACKLISTED_IPADDR':
                assert 'https://botscout.com/ipcheck.htm?ip=8.8.8.8' in e.data

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_email_positive(self, mock_fetch):
        # Simulate a positive BotScout response for email
        mock_fetch.return_value = {'code': '200', 'content': 'Y|MAIL|1|2|3'}
        target = SpiderFootTarget('test@example.com', 'EMAILADDR')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('EMAILADDR', 'test@example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'MALICIOUS_EMAILADDR' in event_types
        # Check event data contains BotScout URL
        for e in self.events:
            if e.eventType == 'MALICIOUS_EMAILADDR':
                assert 'https://botscout.com/search.htm?sterm=test@example.com&stype=q' in e.data

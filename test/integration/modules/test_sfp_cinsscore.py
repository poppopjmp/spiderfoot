import pytest
import unittest
from unittest.mock import patch

from modules.sfp_cinsscore import sfp_cinsscore
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationCinsscore(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        })
        self.module = sfp_cinsscore()
        self.module.__name__ = 'sfp_cinsscore'
        self.options = {
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            'checkaffiliates': True,
            'checknetblocks': True,
            'checksubnets': True,
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_ip_address_blacklisted(self, mock_fetch):
        # Simulate blacklist containing '1.2.3.4'
        blacklist = '1.2.3.4\n5.6.7.8\n'
        mock_fetch.return_value = {'code': '200', 'content': blacklist}
        target = SpiderFootTarget('1.2.3.4', 'IP_ADDRESS')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'MALICIOUS_IPADDR' in event_types
        assert 'BLACKLISTED_IPADDR' in event_types
        # Check event data contains CINS Army list URL
        for e in self.events:
            if e.eventType in ('MALICIOUS_IPADDR', 'BLACKLISTED_IPADDR'):
                assert 'https://cinsscore.com/list/ci-badguys.txt' in e.data

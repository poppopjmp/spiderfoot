import pytest
import unittest
from unittest.mock import patch

from modules.sfp_circllu import sfp_circllu
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationCircllu(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        })
        self.module = sfp_circllu()
        self.module.__name__ = 'sfp_circllu'
        self.options = {
            'api_key_login': 'dummyuser',
            'api_key_password': 'dummypass',
            'age_limit_days': 0,
            'verify': False,
            'cohostsamedomain': False,
            'maxcohost': 100,
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append
        self.module.getTarget = lambda: SpiderFootTarget('1.2.3.4', 'IP_ADDRESS')

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_ip_address_cohosted(self, mock_fetch):
        # Simulate Passive DNS API response with a co-hosted site
        pdns_response = '{"rrtype": "A", "rdata": "1.2.3.4", "rrname": "cohosted.com", "time_last": 9999999999}\n'
        mock_fetch.return_value = {'code': '200', 'content': pdns_response}
        target = SpiderFootTarget('1.2.3.4', 'IP_ADDRESS')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('IP_ADDRESS', '1.2.3.4', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'CO_HOSTED_SITE' in event_types
        # Check event data contains the expected cohosted domain
        found = any(e.data == 'cohosted.com' for e in self.events if e.eventType == 'CO_HOSTED_SITE')
        assert found, 'CO_HOSTED_SITE event data does not contain expected cohosted domain.'

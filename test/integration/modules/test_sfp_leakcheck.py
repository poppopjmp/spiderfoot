# filepath: spiderfoot/test/integration/modules/test_sfpleakcheck.py
import pytest
import unittest
from unittest.mock import patch
import json
import os

from modules.sfp_leakcheck import sfp_leakcheck
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationLeakcheck(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
            'api_key': 'DUMMYKEY',
            'checkaffiliates': True,
        })
        self.module = sfp_leakcheck()
        self.module.__name__ = 'sfp_leakcheck'
        self.options = {
            'api_key': 'DUMMYKEY',
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
            'checkaffiliates': True,
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch('time.sleep', return_value=None)
    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_domain_name(self, mock_fetch, _mock_sleep):
        # Simulate LeakCheck API response
        leakcheck_response = {
            'found': True,
            'result': [
                {
                    'email': 'john@example.com',
                    'username': 'johnny',
                    'phone': '+1234567890',
                    'source': {'name': 'ExampleBreach', 'breach_date': '2020-01-01'},
                    'country': 'USA',
                    'ip': '1.2.3.4',
                    'dob': '1990-01-01',
                    'password': 'hunter2',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'zip': '94105',
                    'address': '123 Main St',
                    'city': 'San Francisco',
                }
            ]
        }
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(leakcheck_response)}
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        # Check for all expected event types
        assert 'EMAILADDR' in event_types, 'EMAILADDR event not emitted.'
        assert 'EMAILADDR_COMPROMISED' in event_types, 'EMAILADDR_COMPROMISED event not emitted.'
        assert 'ACCOUNT_EXTERNAL_OWNED_COMPROMISED' in event_types, 'ACCOUNT_EXTERNAL_OWNED_COMPROMISED event not emitted.'
        assert 'PHONE_NUMBER_COMPROMISED' in event_types, 'PHONE_NUMBER_COMPROMISED event not emitted.'
        assert 'IP_ADDRESS' in event_types, 'IP_ADDRESS event not emitted.'
        assert 'DATE_HUMAN_DOB' in event_types, 'DATE_HUMAN_DOB event not emitted.'
        assert 'COUNTRY_NAME' in event_types, 'COUNTRY_NAME event not emitted.'
        assert 'PASSWORD_COMPROMISED' in event_types, 'PASSWORD_COMPROMISED event not emitted.'
        assert 'HUMAN_NAME' in event_types, 'HUMAN_NAME event not emitted.'
        assert 'GEOINFO' in event_types, 'GEOINFO event not emitted.'
        assert 'RAW_RIR_DATA' in event_types, 'RAW_RIR_DATA event not emitted.'

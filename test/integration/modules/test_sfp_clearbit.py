import pytest
import unittest
from unittest.mock import patch
import json

from modules.sfp_clearbit import sfp_clearbit
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationclearbit(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
        })
        self.module = sfp_clearbit()
        self.module.__name__ = 'sfp_clearbit'
        self.options = {
            'api_key': 'DUMMYKEY',
            '_fetchtimeout': 0.1,
            '_useragent': 'SpiderFootTestAgent',
            '_internettlds': 'com,net,org',
            '_debug': False,
            '_genericusers': 'info,admin',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append
        # Make getTarget match alt.example.com
        self.module.getTarget = lambda: SpiderFootTarget('alt.example.com', 'INTERNET_NAME')

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_emailaddr(self, mock_fetch):
        # Simulate Clearbit API response with top-level 'person' and 'company' keys as in real API
        clearbit_response = {
            'person': {'name': {'fullName': 'John Doe'}},
            'company': {
                'domainAliases': ['alt.example.com'],
                'site': {
                    'phoneNumbers': ['+1234567890'],
                    'emailAddresses': ['info@example.com', 'john@example.com']
                },
                'geo': {'city': 'San Francisco', 'country': 'USA'}
            }
        }
        mock_fetch.return_value = {'code': '200', 'content': json.dumps(clearbit_response)}
        target = SpiderFootTarget('john@example.com', 'EMAILADDR')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('EMAILADDR', 'john@example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        print('Error state:', self.module.errorState)
        event_types = [e.eventType for e in self.events]
        print('Emitted events:', [(e.eventType, e.data) for e in self.events])
        assert 'RAW_RIR_DATA' in event_types, 'RAW_RIR_DATA event not emitted.'
        assert 'INTERNET_NAME' in event_types or 'AFFILIATE_INTERNET_NAME' in event_types, 'Domain event not emitted.'
        assert 'PHONE_NUMBER' in event_types, 'PHONE_NUMBER event not emitted.'
        assert 'EMAILADDR' in event_types, 'EMAILADDR event not emitted.'
        assert 'EMAILADDR_GENERIC' in event_types, 'EMAILADDR_GENERIC event not emitted.'

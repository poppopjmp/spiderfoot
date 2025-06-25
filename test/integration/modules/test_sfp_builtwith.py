import pytest
import unittest
from unittest.mock import patch
import json

from modules.sfp_builtwith import sfp_builtwith
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationBuiltwith(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            '_genericusers': 'admin,webmaster',
            '_internettlds': 'com,net,org',
        })
        self.module = sfp_builtwith()
        self.module.__name__ = 'sfp_builtwith'
        self.options = {
            'api_key': 'DUMMYKEY',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTestAgent',
            '_genericusers': 'admin,webmaster',
            '_internettlds': 'com,net,org',
        }
        self.module.setup(self.sf, self.options)
        self.events = []
        self.module.notifyListeners = self.events.append

    @patch.object(SpiderFoot, 'fetchUrl')
    def test_handleEvent_domain_name(self, mock_fetch):
        # Simulate BuiltWith API responses for domain info and relationships
        domain_info = {
            'Results': [{
                'Meta': {
                    'Names': [
                        {'Name': 'Example Name', 'Email': 'admin@example.com'},
                        {'Name': 'Alice', 'Email': 'alice@example.com'}
                    ],
                    'Emails': ['webmaster@example.com', 'alice@example.com'],
                    'Telephones': ['+1-555-1234']
                },
                'Result': {
                    'Paths': [
                        {'SubDomain': 'www', 'Technologies': [{'Name': 'nginx', 'LastDetected': 9999999999999}]}
                    ]
                }
            }]
        }
        relationships = [
            {
                'Domain': 'example.com',
                'Identifiers': [
                    {'Type': 'ip', 'Value': '1.2.3.4', 'Last': 9999999999999, 'Matches': []},
                    {'Type': 'ga', 'Value': 'UA-123', 'Last': 9999999999999, 'Matches': [{'Domain': 'affiliate.com'}]}
                ]
            }
        ]
        # The module calls fetchUrl twice: once for domain info, once for relationships
        mock_fetch.side_effect = [
            {'code': '200', 'content': json.dumps(domain_info)},
            {'code': '200', 'content': json.dumps({'Relationships': relationships})}
        ]
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        self.module.setTarget(target)
        parent_evt = SpiderFootEvent('ROOT', 'rootdata', 'test', None)
        evt = SpiderFootEvent('DOMAIN_NAME', 'example.com', 'test', parent_evt)
        self.module.handleEvent(evt)
        event_types = [e.eventType for e in self.events]
        assert 'WEBSERVER_TECHNOLOGY' in event_types
        assert 'INTERNET_NAME' in event_types
        assert 'EMAILADDR' in event_types
        assert 'EMAILADDR_GENERIC' in event_types
        assert 'PHONE_NUMBER' in event_types
        assert 'IP_ADDRESS' in event_types
        assert 'WEB_ANALYTICS_ID' in event_types
        assert 'AFFILIATE_INTERNET_NAME' in event_types
        # Check event data for at least one event type
        found = any('nginx' in e.data for e in self.events if e.eventType == 'WEBSERVER_TECHNOLOGY')
        assert found, 'WEBSERVER_TECHNOLOGY event data does not contain expected technology name.'

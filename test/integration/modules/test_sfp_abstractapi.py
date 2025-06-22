import pytest
import unittest
from unittest.mock import patch

from modules.sfp_abstractapi import sfp_abstractapi
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(unittest.TestCase):

    default_options = {
        '_socks1type': '',
        '_socks2addr': '',
        '_socks3port': '',
        '_socks4user': '',
        '_socks5pwd': '',
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '_fetchtimeout': 5,
        '_useragent': 'SpiderFootTest',
        '_dnsserver': '',
        '_outputfilter': None,
        '_debug': False,
        '__logging': True,
        '__outputfilter': None,
        '__database': 'data/spiderfoot.test.db',
        '__modules__': None,
        '__correlationrules__': None,
        '__logstdout': False,
        '__modulesdir': 'modules',
        # Add any other options required by your modules/tests here
        'companyenrichment_api_key': 'dummy',
        'phonevalidation_api_key': 'dummy',
        'ipgeolocation_api_key': 'dummy',
    }

    def setup_module(self, module_class):
        sf = SpiderFoot(self.default_options)
        module = module_class()
        module.setup(sf, self.default_options)
        return module

    def create_event(self, target_value, target_type, event_type, event_data):
        target = SpiderFootTarget(target_value, target_type)
        evt = SpiderFootEvent(event_type, event_data, 'sfp_abstractapi', None)
        return target, evt



class TestModuleIntegrationAbstractapi(BaseTestModuleIntegration):

    def test_handleEvent(self):
        module = self.setup_module(sfp_abstractapi)
        # Explicitly set API keys in module.opts to ensure they are present
        module.opts['companyenrichment_api_key'] = 'dummy'
        module.opts['phonevalidation_api_key'] = 'dummy'
        module.opts['ipgeolocation_api_key'] = 'dummy'
        module.__name__ = 'sfp_abstractapi'

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'  # Use a valid type for domain
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        target, evt = self.create_event(target_value, target_type, event_type, event_data)

        module.setTarget(target)
        # Patch API call and notifyListeners
        with patch.object(module, 'queryCompanyEnrichment', return_value={
            'name': 'Test Company',
            'linkedin_url': 'linkedin.com/company/test',
            'locality': 'Test City',
            'country': 'Test Country',
        }), patch.object(module, 'notifyListeners') as mock_notify:
            module.handleEvent(evt)
            # Should emit RAW_RIR_DATA, COMPANY_NAME, SOCIAL_MEDIA, GEOINFO events
            event_types = [call_args[0][0].eventType for call_args in mock_notify.call_args_list]
            assert 'RAW_RIR_DATA' in event_types
            assert 'COMPANY_NAME' in event_types
            assert 'SOCIAL_MEDIA' in event_types
            assert 'GEOINFO' in event_types

import pytest
import unittest

from modules.sfp_ipwhois import sfp_ipwhois
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleIpWhois(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_ipwhois()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_ipwhois()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_ipwhois()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_ipwhois()
        self.assertIsInstance(module.producedEvents(), list)
    
    def test_handleEvent_valid_ip_should_produce_results(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_ipwhois()
        module.setup(sf, dict())

        target_value = '1.1.1.1'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the query_whois method
        def mock_query_whois(ip):
            return {
                "asn": "13335",
                "asn_cidr": "1.1.1.0/24",
                "asn_country_code": "US",
                "asn_date": "2010-07-14",
                "asn_description": "CLOUDFLARENET, US",
                "nets": [
                    {
                        "address": "101 Townsend Street, San Francisco, CA 94107, United States",
                        "cidr": "1.1.1.0/24",
                        "city": "San Francisco",
                        "country": "US",
                        "created": "2010-07-14",
                        "description": "Cloudflare Inc",
                        "emails": ["abuse@cloudflare.com"],
                        "handle": "NET-1-1-1-0-1",
                        "name": "APNIC and Cloudflare DNS Resolver project",
                        "postal_code": "94107",
                        "range": "1.1.1.0 - 1.1.1.255",
                        "state": "CA",
                        "updated": "2019-09-25"
                    }
                ]
            }
        
        module.query_whois = mock_query_whois

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_ipwhois)
        
        event_type = 'IP_ADDRESS'
        event_data = '1.1.1.1'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        event_types = [e.eventType for e in generated_events]
        expected_types = ['NETBLOCK_OWNER', 'EMAILADDR', 'RAW_RIR_DATA', 'COMPANY_NAME', 'PHYSICAL_ADDRESS']
        
        # Check that all expected event types were generated
        for expected_type in expected_types:
            self.assertIn(expected_type, event_types, f"Expected {expected_type} event not generated")
        
        # Check specific data in generated events
        for event in generated_events:
            if event.eventType == 'NETBLOCK_OWNER':
                self.assertIn("1.1.1.0/24", event.data)
            elif event.eventType == 'COMPANY_NAME':
                self.assertIn("Cloudflare", event.data)

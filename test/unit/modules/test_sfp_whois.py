import pytest
import unittest
import logging

from modules.sfp_whois import sfp_whois
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleWhois(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_whois()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_whois()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_whois()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_whois()
        self.assertIsInstance(module.producedEvents(), list)

    def setUp(self):
        # Ensure logger is properly initialized
        self.module.log = logging.getLogger(__name__)

    def test_handleEvent_domain_name_event_should_extract_whois_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_whois()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the queryWhois method
        def mock_queryWhois(domain):
            return """
            Domain Name: EXAMPLE.COM
            Registry Domain ID: 2336799_DOMAIN_COM-VRSN
            Registrar WHOIS Server: whois.iana.org
            Registrar URL: http://www.iana.org
            Updated Date: 2023-08-14T07:01:38Z
            Creation Date: 1995-08-14T04:00:00Z
            Registry Expiry Date: 2024-08-13T04:00:00Z
            Registrar: IANA
            Registrar IANA ID: 376
            Registrar Abuse Contact Email: abuse@example.com
            Registrar Abuse Contact Phone: +1.2025551212
            Domain Status: clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited
            Domain Status: clientTransferProhibited https://icann.org/epp#clientTransferProhibited
            Domain Status: clientUpdateProhibited https://icann.org/epp#clientUpdateProhibited
            Name Server: A.IANA-SERVERS.NET
            Name Server: B.IANA-SERVERS.NET
            DNSSEC: signedDelegation
            DNSSEC DS Data: 31589 8 1 3490A6806D47F17A34C29E2CE80E8A999FFBE4BE
            DNSSEC DS Data: 31589 8 2 CDE0D742D6998AA554A92D890F8184C698CFAC8A26FA59875A990C03E576343C
            URL of the ICANN Whois Inaccuracy Complaint Form: https://www.icann.org/wicf/
            >>> Last update of whois database: 2023-09-26T06:15:38Z <<<
            """
        
        module.queryWhois = mock_queryWhois

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_whois)
        
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for expected event types
        event_types = [e.eventType for e in generated_events]
        expected_types = ['DOMAIN_WHOIS', 'EMAILADDR', 'DOMAIN_REGISTRAR', 'NETBLOCK_OWNER', 
                          'DOMAIN_NAME_EXPIRED', 'HUMAN_NAME', 'RAW_RIR_DATA']
        
        for expected_type in expected_types:
            self.assertIn(expected_type, event_types, f"Expected {expected_type} not found in {event_types}")

        # Check specific data in generated events
        found_email = False
        for event in generated_events:
            if event.eventType == 'EMAILADDR' and event.data == 'abuse@example.com':
                found_email = True
                break
                
        self.assertTrue(found_email, "Expected email address not found in events")

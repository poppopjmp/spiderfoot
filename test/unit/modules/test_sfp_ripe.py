import pytest
import unittest

from modules.sfp_ripe import sfp_ripe
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleRipe(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_ripe()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_ripe()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_ripe()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_ripe()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_ip_address_event_should_return_netblock_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_ripe()
        module.setup(sf, dict())

        target_value = '193.0.6.139'  # RIPE NCC's IP
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the fetchUrl method
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': 200,
                'content': """
                {
                    "objects": {
                        "object": [
                            {
                                "source": {
                                    "id": "ripe"
                                },
                                "primary-key": {
                                    "attribute": [
                                        {
                                            "name": "inetnum",
                                            "value": "193.0.0.0 - 193.0.23.255"
                                        }
                                    ]
                                },
                                "attributes": {
                                    "attribute": [
                                        {
                                            "name": "netname",
                                            "value": "RIPE-NCC"
                                        },
                                        {
                                            "name": "descr",
                                            "value": "RIPE Network Coordination Centre"
                                        },
                                        {
                                            "name": "country",
                                            "value": "NL"
                                        },
                                        {
                                            "name": "org",
                                            "value": "ORG-TEST-RIPE"
                                        },
                                        {
                                            "name": "admin-c",
                                            "value": "person-test"
                                        },
                                        {
                                            "name": "tech-c",
                                            "value": "person-test"
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
                """
            }
            
        module.sf.fetchUrl = fetch_url_mock

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_ripe)
        
        event_type = 'IP_ADDRESS'
        event_data = '193.0.6.139'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for expected event types
        event_types = [e.eventType for e in generated_events]
        expected_types = ['RAW_RIR_DATA', 'NETBLOCK_OWNER', 'COMPANY_NAME', 'PHYSICAL_ADDRESS']
        
        for expected_type in expected_types:
            self.assertIn(expected_type, event_types)
        
        # Check specific data
        for event in generated_events:
            if event.eventType == 'COMPANY_NAME':
                self.assertIn("RIPE Network Coordination Centre", event.data)
            elif event.eventType == 'NETBLOCK_OWNER':
                self.assertIn("193.0.0.0 - 193.0.23.255", event.data)

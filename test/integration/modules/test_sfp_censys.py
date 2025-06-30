import unittest
from unittest.mock import patch

from modules.sfp_censys import sfp_censys
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationCensys(unittest.TestCase):
    def setUp(self):
        self.default_options = {
            "_fetchtimeout": 10,
            "censys_api_key_uid": "testuid",
            "censys_api_key_secret": "testsecret",
            "delay": 0,
            "netblocklookup": False,
            "maxnetblock": 24,
            "maxv6netblock": 120,
            "age_limit_days": 0
        }

    @patch("modules.sfp_censys.sfp_censys.notifyListeners")
    @patch("modules.sfp_censys.sfp_censys.queryHosts")
    def test_handleEvent_ip_address(self, mock_queryHosts, mock_notifyListeners):
        sf = SpiderFoot(self.default_options)
        module = sfp_censys()
        module.setup(sf, self.default_options)
        module.__name__ = "sfp_censys"

        # Mock Censys API response
        mock_queryHosts.return_value = {
            "result": {
                "last_updated_at": "2023-01-01T00:00:00.000Z",
                "location": {
                    "city": "Test City",
                    "province": "Test Province",
                    "postal_code": "12345",
                    "country": "Test Country",
                    "continent": "Test Continent"
                },
                "services": [
                    {
                        "port": 80,
                        "transport_protocol": "TCP",
                        "banner": "Test Banner",
                        "software": [
                            {"vendor": "TestVendor", "product": "TestProduct", "version": "1.0"}
                        ],
                        "http": {
                            "response": {
                                "headers": {"Server": "TestServer"}
                            }
                        }
                    }
                ],
                "autonomous_system": {
                    "asn": 12345,
                    "bgp_prefix": "192.0.2.0/24"
                },
                "operating_system": {
                    "vendor": "TestOSVendor",
                    "product": "TestOSProduct",
                    "version": "1.0",
                    "edition": "Pro"
                }
            }
        }

        target_value = "192.0.2.1"
        target_type = "IP_ADDRESS"
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = "IP_ADDRESS"
        event_data = target_value
        event_module = "sfp_censys"
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)

        # Check that notifyListeners was called for expected events
        calls = [call[0][0].eventType for call in mock_notifyListeners.call_args_list]
        assert "RAW_RIR_DATA" in calls
        assert "GEOINFO" in calls
        assert "TCP_PORT_OPEN" in calls
        assert "SOFTWARE_USED" in calls
        assert "TCP_PORT_OPEN_BANNER" in calls
        assert "WEBSERVER_HTTPHEADERS" in calls
        assert "BGP_AS_MEMBER" in calls
        assert "NETBLOCK_MEMBER" in calls
        assert "OPERATING_SYSTEM" in calls

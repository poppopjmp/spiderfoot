import unittest
from unittest.mock import patch
import json

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_c99 import sfp_c99
from spiderfoot.sflib import SpiderFoot


class TestModuleIntegrationC99(unittest.TestCase):
    def setUp(self):
        self.default_options = {"_useragent": "SpiderFootTestAgent", "api_key": "DUMMYKEY", "_fetchtimeout": 5, "_socks1type": "", "_internettlds": []}
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_c99()
        self.module.setup(self.sf, self.default_options)
        self.module.__name__ = self.module.__class__.__name__

    @patch('modules.sfp_c99.requests.get')
    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_malicious_ip(self, mock_fetchUrl, mock_get):
        # Mock a geoip response to trigger RAW_RIR_DATA emission
        mock_geoip_data = {
            "success": True,
            "hostname": "host.example.com",
            "records": {
                "country_name": "CountryX",
                "region": {"name": "RegionY"},
                "city": "CityZ",
                "postal_code": "12345",
                "latitude": 12.34,
                "longitude": 56.78,
                "isp": "ISPName"
            }
        }
        mock_fetchUrl.return_value = {"code": "200", "content": json.dumps(mock_geoip_data)}
        target_value = '1.2.3.4'
        target_type = 'IP_ADDRESS'
        event_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        evt = SpiderFootEvent(event_type, target_value, self.module.__name__, None)
        events = []
        import unittest.mock as mock_mod
        with mock_mod.patch.object(self.module, 'notifyListeners', side_effect=events.append):
            self.module.handleEvent(evt)
        raw_data_event = next((e for e in events if e.eventType == 'RAW_RIR_DATA'), None)
        self.assertIsNotNone(raw_data_event)
        self.assertEqual(raw_data_event.data, str(mock_geoip_data))

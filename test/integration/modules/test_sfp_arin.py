import pytest
import unittest

from modules.sfp_arin import sfp_arin
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationarin(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        }

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_arin()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_arin"
        target_value = '8.8.8.8'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        event_type = 'IP_ADDRESS'
        event_data = '8.8.8.8'
        event_module = 'testModule'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        # Patch fetchUrl to simulate a response (no results)
        with mock_mod.patch.object(sf, 'fetchUrl', return_value={'code': '200', 'content': '{}'}):
            def collect_event(event):
                events.append(event)
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=collect_event):
                module.handleEvent(evt)
        # Assert that no events are emitted for a non-listed IP
        self.assertEqual(len(events), 0)

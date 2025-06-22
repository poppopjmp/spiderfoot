import unittest

from modules.sfp_ahmia import sfp_ahmia
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationAhmia(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        }

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_ahmia()
        module.setup(sf, dict(self.default_options))
        module.__name__ = "sfp_ahmia"
        target_value = 'example.onion'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        event_type = 'INTERNET_NAME'
        event_data = 'example.onion'
        event_module = 'testModule'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        events = []
        import unittest.mock as mock_mod
        # Patch fetchUrl to simulate a response (if needed)
        with mock_mod.patch.object(sf, 'fetchUrl', return_value={'code': '200', 'content': '{"results": []}'}):
            def collect_event(event):
                events.append(event)
            with mock_mod.patch.object(module, 'notifyListeners', side_effect=collect_event):
                module.handleEvent(evt)
        # Assert that no events are emitted for a non-listed onion
        self.assertEqual(len(events), 0)

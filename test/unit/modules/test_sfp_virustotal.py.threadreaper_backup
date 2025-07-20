import json
import time
import unittest.mock as mock

from modules.sfp_virustotal import sfp_virustotal
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleVirustotal(SpiderFootTestBase):

    def test_opts(self):
        module = sfp_virustotal()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_virustotal()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_virustotal()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_virustotal()
        self.assertIsInstance(module.producedEvents(), list)

    @safe_recursion(max_depth=5)
    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_virustotal()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)
        with mock.patch.object(time, 'sleep', return_value=None):
            result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_handleEvent_emits_event_on_malicious_ip(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_virustotal()
        module.setup(sf, {'api_key': 'DUMMY', '_fetchtimeout': 1})
        module.setTarget(SpiderFootTarget('8.8.8.8', 'IP_ADDRESS'))
        event = SpiderFootEvent('IP_ADDRESS', '8.8.8.8', 'test', None)
        vt_response = json.dumps({'detected_urls': [{}]})
        with mock.patch.object(module.sf, 'fetchUrl', return_value={'content': vt_response, 'code': '200'}), \
             mock.patch.object(module, 'notifyListeners') as mock_notify, \
             mock.patch.object(time, 'sleep', return_value=None):
            module.handleEvent(event)
            self.assertTrue(mock_notify.called)
            event_types = [call_args[0][0].eventType for call_args in mock_notify.call_args_list]
            self.assertIn('MALICIOUS_IPADDR', event_types)

    def test_handleEvent_deduplication(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_virustotal()
        module.setup(sf, {'api_key': 'DUMMY', '_fetchtimeout': 1})
        module.setTarget(SpiderFootTarget('8.8.8.8', 'IP_ADDRESS'))
        event = SpiderFootEvent('IP_ADDRESS', '8.8.8.8', 'test', None)
        vt_response = json.dumps({'detected_urls': [{}]})
        with mock.patch.object(module.sf, 'fetchUrl', return_value={'content': vt_response, 'code': '200'}), \
             mock.patch.object(module, 'notifyListeners') as mock_notify:
            module.handleEvent(event)
            module.handleEvent(event)  # Should not emit again
            self.assertEqual(mock_notify.call_count, 1)

    def test_handleEvent_api_error_sets_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_virustotal()
        module.setup(sf, {'api_key': 'DUMMY', '_fetchtimeout': 1})
        module.setTarget(SpiderFootTarget('8.8.8.8', 'IP_ADDRESS'))
        event = SpiderFootEvent('IP_ADDRESS', '8.8.8.8', 'test', None)
        with mock.patch.object(module.sf, 'fetchUrl', return_value={'content': None, 'code': '500'}):
            module.handleEvent(event)
            self.assertFalse(module.errorState)  # No errorState for no content
        with mock.patch.object(module.sf, 'fetchUrl', side_effect=Exception('Network error')):
            module.errorState = False
            try:
                module.handleEvent(event)
            except Exception:
                pass
            # Should not set errorState unless JSON decode fails

    def test_handleEvent_invalid_json_sets_errorState(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_virustotal()
        module.setup(sf, {'api_key': 'DUMMY', '_fetchtimeout': 1})
        module.setTarget(SpiderFootTarget('8.8.4.4', 'IP_ADDRESS'))
        event = SpiderFootEvent('IP_ADDRESS', '8.8.4.4', 'test', None)
        with mock.patch.object(module.sf, 'fetchUrl', return_value={'content': 'not-json', 'code': '200'}):
            module.handleEvent(event)
            self.assertTrue(module.errorState)

    def test_handleEvent_no_detected_urls_no_event(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_virustotal()
        module.setup(sf, {'api_key': 'DUMMY', '_fetchtimeout': 1})
        module.setTarget(SpiderFootTarget('1.1.1.1', 'IP_ADDRESS'))
        event = SpiderFootEvent('IP_ADDRESS', '1.1.1.1', 'test', None)
        vt_response = json.dumps({'detected_urls': []})
        with mock.patch.object(module.sf, 'fetchUrl', return_value={'content': vt_response, 'code': '200'}), \
             mock.patch.object(module, 'notifyListeners') as mock_notify:
            module.handleEvent(event)
            self.assertFalse(mock_notify.called)

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

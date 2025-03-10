import pytest
import unittest

from modules.sfp_dnsgrep import sfp_dnsgrep
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleDnsgrep(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_dnsgrep()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_dnsgrep()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_dnsgrep()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_dnsgrep()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_with_valid_domain_should_query_dnsgrep(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_dnsgrep()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the fetchUrl method
        def fetchUrl_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '{"subdomains":["test.example.com","dev.example.com"]}'
            }
            
        module.sf.fetchUrl = fetchUrl_mock

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)
            
        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_dnsgrep)

        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)

        # Check that events were generated
        self.assertEqual(len(generated_events), 2)
        self.assertEqual(generated_events[0].eventType, 'INTERNET_NAME')
        self.assertEqual(generated_events[1].eventType, 'INTERNET_NAME')
        self.assertIn(generated_events[0].data, ['test.example.com', 'dev.example.com'])
        self.assertIn(generated_events[1].data, ['test.example.com', 'dev.example.com'])

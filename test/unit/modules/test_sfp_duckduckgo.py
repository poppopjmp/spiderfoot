import pytest
import unittest

from modules.sfp_duckduckgo import sfp_duckduckgo
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleDuckduckgo(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_duckduckgo()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_duckduckgo()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_duckduckgo()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_duckduckgo()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_should_execute_search(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_duckduckgo()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the fetchUrl method
        def fetchUrl_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '<html><body><div class="result"><a href="https://test.example.com">Test Result</a></div>'
                          '<div class="result"><a href="https://example.org">Another Domain</a></div></body></html>'
            }
            
        module.sf.fetchUrl = fetchUrl_mock

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)
            
        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_duckduckgo)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)

        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for specific events
        found_internal_url = False
        for event in generated_events:
            if event.eventType == 'LINKED_URL_INTERNAL' and event.data == 'https://test.example.com':
                found_internal_url = True
                break
                
        self.assertTrue(found_internal_url, "Did not find expected LINKED_URL_INTERNAL event")

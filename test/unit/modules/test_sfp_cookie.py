import pytest
import unittest

from modules.sfp_cookie import sfp_cookie
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCookie(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_cookie()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_cookie()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_cookie()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_cookie()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_event_data_containing_cookie_should_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cookie()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)
            
        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_cookie)

        event_type = 'WEBSERVER_HTTPHEADERS'
        event_data = '{"cookie": "example cookie"}'
        event_module = 'sfp_spider'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        evt.actualSource = "https://spiderfoot.net/example"

        module.handleEvent(evt)

        # Check that the expected event was generated
        self.assertEqual(len(generated_events), 1)
        self.assertEqual(generated_events[0].eventType, 'TARGET_WEB_COOKIE')
        self.assertEqual(generated_events[0].data, 'example cookie')

    def test_handleEvent_event_data_not_containing_cookie_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cookie()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)
            
        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_cookie)

        event_type = 'WEBSERVER_HTTPHEADERS'
        event_data = '{"not_cookie": "example value"}'
        event_module = 'sfp_spider'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        evt.actualSource = "https://spiderfoot.net/example"

        module.handleEvent(evt)

        # Check that no event was generated
        self.assertEqual(len(generated_events), 0)

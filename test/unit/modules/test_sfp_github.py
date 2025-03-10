import pytest
import unittest

from modules.sfp_github import sfp_github
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleGithub(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_github()
        self.assertEqual(len(module.opts), 1)  # Update this if needed based on actual module

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_github()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_github()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_github()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_event_data_social_media_not_github_profile_should_not_return_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_github()
        module.setup(sf, dict())

        target_value = 'spiderfoot.net'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        def new_notifyListeners(self, event):
            raise Exception(f"Raised event {event.eventType}: {event.data}")

        module.notifyListeners = new_notifyListeners.__get__(module, sfp_github)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'SOCIAL_MEDIA'
        event_data = 'Not GitHub: example_username'
        event_module = 'example module'
        source_event = evt

        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        result = module.handleEvent(evt)

        self.assertIsNone(result)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_github()
        module.setup(sf, dict())

        target_value = 'example target value'
        target_type = 'USERNAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)
        self.assertTrue(module.errorState)
        
    def test_handleEvent_with_api_key_should_make_api_request(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_github()
        module.setup(sf, dict())
        module.opts['api_key'] = 'test_api_key'

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the API response
        def fetchUrl_mock(url, *args, **kwargs):
            return {
                'code': 200,
                'content': '{"total_count": 2, "items": [{"name": "repo1", "html_url": "https://github.com/user/repo1"}, {"name": "repo2", "html_url": "https://github.com/user/repo2"}]}'
            }

        module.sf.fetchUrl = fetchUrl_mock

        # Track generated events
        generated_events = []
        def notifyListeners_mock(event):
            generated_events.append(event)

        module.notifyListeners = notifyListeners_mock.__get__(module, sfp_github)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)

        # Check that events were generated
        self.assertTrue(len(generated_events) > 0)
        
        # Check for specific event types
        event_types = [e.eventType for e in generated_events]
        self.assertIn('PUBLIC_CODE_REPO', event_types)

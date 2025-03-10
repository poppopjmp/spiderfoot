import pytest
import unittest

from modules.sfp_emailformat import sfp_emailformat
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleEmailformat(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_emailformat()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_emailformat()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_emailformat()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_emailformat()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_domain_event_should_return_email_patterns(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_emailformat()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the fetchUrl method to return sample data
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': 200,
                'content': """
                <div class="format">
                    <span>firstname.lastname@example.com</span>
                </div>
                <div class="format">
                    <span>firstinitial.lastname@example.com</span>
                </div>
                """
            }

        module.sf.fetchUrl = fetch_url_mock

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_emailformat)
        
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_dnsresolve'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for EMAIL_FORMAT events
        email_formats = [e for e in generated_events if e.eventType == 'EMAIL_FORMAT']
        self.assertGreater(len(email_formats), 0)
        
        expected_formats = ['firstname.lastname@example.com', 'firstinitial.lastname@example.com']
        found_formats = [e.data for e in email_formats]
        
        for fmt in expected_formats:
            self.assertIn(fmt, found_formats)

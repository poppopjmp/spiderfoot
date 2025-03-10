import pytest
import unittest
from unittest.mock import Mock

from modules.sfp_wikileaks import sfp_wikileaks
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleWikileaks(SpiderFootModuleTestCase):

    def setUp(self):
        self.module = sfp_wikileaks()
        self.module.log = Mock()  # Mock the log attribute
        # Ensure logger is properly initialized
        self.module.log = logging.getLogger(__name__)

    def test_opts(self):
        module = sfp_wikileaks()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_wikileaks()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_wikileaks()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_wikileaks()
        self.assertIsInstance(module.producedEvents(), list)
        
    def test_handleEvent_search_should_add_urls(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_wikileaks()
        module.setup(sf, dict())
        
        # Mock search function to simulate search results
        module.search = lambda qry: [
            {
                "name": "Example doc",
                "url": "https://wikileaks.org/example-doc.html"
            }
        ]

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_wikileaks)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'example module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check if the expected event was generated
        self.assertEqual(len(generated_events), 1)
        self.assertEqual(generated_events[0].eventType, 'LEAK_SITE_URL')
        self.assertEqual(generated_events[0].data, "https://wikileaks.org/example-doc.html")

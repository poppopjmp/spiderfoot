import pytest
import unittest

from modules.sfp_crossref import sfp_crossref
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCrossref(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_crossref()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_crossref()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_crossref()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_crossref()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_should_cross_reference_events(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_crossref()
        module.setup(sf, dict())
        
        # Add mock data to the event registry
        module.eventMap = {
            'IP_ADDRESS': ['1.2.3.4', '5.6.7.8'],
            'DOMAIN_NAME': ['example.com', 'test.com']
        }
        
        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_crossref)

        # Create an event that should trigger cross-references
        event_type = 'CO_HOSTED_SITE'
        event_data = 'example.com'
        event_module = 'sfp_test'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check if cross-reference events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Verify the correct cross-reference event type
        xref_events = [e for e in generated_events if e.eventType == 'CROSS_DOMAIN']
        self.assertGreater(len(xref_events), 0)
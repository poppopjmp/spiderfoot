# filepath: c:\Users\van1sh\Documents\GitHub\spiderfoot\test\unit\modules\test_sfp_xref.py
import pytest
import unittest

from modules.sfp_xref import sfp_xref
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleXref(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_xref()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_xref()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_xref()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_xref()
        self.assertIsInstance(module.producedEvents(), list)
    
    def setUp(self):
        self.module = sfp_xref()
        self.module.log = logging.getLogger(__name__)

    def test_handleEvent_should_generate_cross_references(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_xref()
        module.setup(sf, dict())
        
        # Mock SF's scanEventStore function to return test data
        def scan_event_store_mock(instance, eventType):
            if eventType == "IP_ADDRESS":
                return [{"data": "192.168.1.1"}, {"data": "192.168.1.2"}]
            elif eventType == "NETBLOCK_MEMBER":
                return [{"data": "192.168.1.0/24"}]
            else:
                return []
                
        sf.scanEventStore = scan_event_store_mock
        
        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        
        # Set the scanId
        module.setScanId("test_scan")

        # Create a list to store the generated events
        generated_events = []
        
        # Override notifyListeners to capture the generated events
        def new_notifyListeners(self, event):
            generated_events.append(event)
            
        module.notifyListeners = new_notifyListeners.__get__(module, sfp_xref)

        # Create an IP_ADDRESS event
        evt = SpiderFootEvent("IP_ADDRESS", "1.2.3.4", self.__name__, None)

        module.handleEvent(evt)
        
        # Check if any events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for XREF event types
        xref_events = [e for e in generated_events if e.eventType.startswith('XREF_')]
        self.assertGreater(len(xref_events), 0, "No XREF events generated")
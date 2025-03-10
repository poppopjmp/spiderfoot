import pytest
import unittest

from modules.sfp_callername import sfp_callername
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCallername(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_callername()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_callername()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_callername()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_callername()
        self.assertIsInstance(module.producedEvents(), list)
        
    def test_handleEvent_phone_number_should_extract_data(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_callername()
        module.setup(sf, dict())

        target_value = '+12125551212'  # Example US phone number
        target_type = 'PHONE_NUMBER'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        # Mock the fetchUrl method
        def fetch_url_mock(url, timeout, useragent="SpiderFoot", headers=None):
            return {
                'code': 200,
                'content': """
                <div class="callerIdInfo">
                    <h2>Phone Owner: John Smith</h2>
                    <p>Location: New York, NY</p>
                    <p>Carrier: Example Wireless</p>
                </div>
                """
            }
            
        module.sf.fetchUrl = fetch_url_mock

        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_callername)
        
        event_type = 'PHONE_NUMBER'
        event_data = '+12125551212'
        event_module = 'sfp_phonenumber'
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for RAW_RIR_DATA event
        raw_data_events = [e for e in generated_events if e.eventType == 'RAW_RIR_DATA']
        self.assertGreater(len(raw_data_events), 0)
        self.assertIn("John Smith", raw_data_events[0].data)
        
        # Check for HUMAN_NAME event
        human_name_events = [e for e in generated_events if e.eventType == 'HUMAN_NAME']
        self.assertGreater(len(human_name_events), 0)
        self.assertEqual(human_name_events[0].data, "John Smith")

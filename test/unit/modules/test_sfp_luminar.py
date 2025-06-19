import unittest
from modules.sfp_luminar import sfp_luminar
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

class TestModuleLuminar(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.default_options.update({
            '_fetchtimeout': 15
        })
        self.module = sfp_luminar.sfp_luminar()

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_luminar.sfp_luminar()
        module.setup(sf, dict())

    @safe_recursion(max_depth=5)
    def test_handleEvent(self):
        """
        Test handleEvent(self, event)
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_luminar.sfp_luminar()
        module.setup(sf, dict())
        
        def new_notifyListeners(self, event):
            expected = 'MALICIOUS_INTERNET_NAME'
            if str(event.eventType) != expected:
                raise Exception(f"Received event {event.eventType}, expected {expected}")

        module.notifyListeners = new_notifyListeners.__get__(module, module.__class__)

        event_type = 'ROOT'
        event_data = 'spiderfoot.net'
        event_module = ''
        source_event = ''
        
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        
        result = module.handleEvent(evt)
        
        self.assertIsNone(result)

    def test_query(self):
        """
        Test query(self, qry)
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_luminar.sfp_luminar()
        module.setup(sf, dict())
        result = module.query("test_query")
        self.assertIsNotNone(result)

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), ['THREAT_INTELLIGENCE'])

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), ['DOMAIN_NAME', 'INTERNET_NAME', 'IP_ADDRESS'])

if __name__ == '__main__':
    unittest.main()

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()
        super().tearDown()

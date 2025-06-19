import unittest
from modules.sfp_luminar import sfp_luminar
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

class TestModuleLuminar(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.default_options = {
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFoot',
            '_dnsserver': '8.8.8.8',
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72
        }
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_luminar()
        self.module.setup(self.sf, dict())
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    @safe_recursion(max_depth=5)
    def test_handleEvent(self):
        target = SpiderFootTarget("spiderfoot.net", "INTERNET_NAME")
        module = self.create_module_wrapper()
        module.setup("spiderfoot.net", self.default_options)
        
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
        self.module.opts['api_key'] = 'test_api_key'
        self.module.opts['_useragent'] = 'SpiderFoot Test'
        result = self.module.query('example.com')
        self.assertIsNotNone(result)

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), ['THREAT_INTELLIGENCE'])

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), ['DOMAIN_NAME', 'INTERNET_NAME', 'IP_ADDRESS'])

    def test_setup(self):
        module = self.create_module_wrapper()
        module.setup("example.com", self.default_options)
        self.assertTrue(hasattr(module, 'opts'))

if __name__ == '__main__':
    unittest.main()

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

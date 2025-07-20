import unittest
from modules.sfp_mandiant_ti import sfp_mandiant_ti
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

class TestModuleMandiantTI(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        # Add required proxy settings to the base options
        self.default_options.update({
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFoot',
            '_dnsserver': '8.8.8.8',
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72,
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': ''
        })
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_mandiant_ti()
        self.module.setup(self.sf, dict())
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

    @safe_recursion(max_depth=5)
    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_mandiant_ti()
        module.__name__ = "sfp_mandiant_ti"
        module.setup(sf, dict())
        
        """
        Test handleEvent(self, event)
        """
        target = SpiderFootTarget("van1shland.io", "INTERNET_NAME")
        
        def new_notifyListeners(self, event):
            expected = 'MALICIOUS_INTERNET_NAME'
            if str(event.eventType) != expected:
                raise Exception(f"Received event {event.eventType}, expected {expected}")

        module.notifyListeners = new_notifyListeners.__get__(module, module.__class__)

        event_type = 'ROOT'
        event_data = 'van1shland.io'
        event_module = ''
        source_event = ''
        
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        
        result = module.handleEvent(evt)
        
        self.assertIsNone(result)

    def test_query(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_mandiant_ti()
        module.__name__ = "sfp_mandiant_ti"
        # Pass the required options to the module setup
        module_opts = {
            '_useragent': 'SpiderFoot',
            '_fetchtimeout': 5
        }
        module.setup(sf, module_opts)
        
        """
        Test query(self, qry)
        """
        result = module.query("test.com")
        self.assertEqual(None, result)

    def test_producedEvents(self):
        self.assertEqual(self.module.producedEvents(), ['THREAT_INTELLIGENCE'])

    def test_watchedEvents(self):
        self.assertEqual(self.module.watchedEvents(), ['DOMAIN_NAME', 'INTERNET_NAME', 'IP_ADDRESS'])

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_mandiant_ti()
        module.setup(sf, dict())
        self.assertTrue(hasattr(module, 'opts'))

if __name__ == '__main__':
    unittest.main()

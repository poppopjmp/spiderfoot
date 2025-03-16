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
    def test_handleEvent(selfdepth=0):
        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.sf.target = target

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = SpiderFootEvent(event_type, event_data, event_module, None)

        self.module.opts['api_key'] = 'test_api_key'
        self.module.handleEvent(source_event)

        self.assertTrue(self.module.results)

    def test_query(self):
        self.module.opts['api_key'] = 'test_api_key'
        result = self.module.query('example.com')
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

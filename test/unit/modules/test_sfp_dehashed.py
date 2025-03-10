from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_dehashed import sfp_dehashed
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleDehashed(SpiderFootModuleTestCase):
    """Test Dehashed module."""

    def test_opts(self):
        module = sfp_dehashed()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        self.sf = SpiderFoot(self.opts)
        module = sfp_dehashed()
        module.setup(self.sf, self.opts)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        module = sfp_dehashed()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_dehashed()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        """Test handleEvent method with no API key."""
        self.sf = SpiderFoot(self.opts)
        self.opts['api_key_dehashed'] = ''
        module = sfp_dehashed()
        module.setup(self.sf, self.opts)
        event_type = "EMAILADDR"
        event_data = "test@example.com"
        event_module = "test"
        source_event = ""
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        result = module.handleEvent(evt)
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

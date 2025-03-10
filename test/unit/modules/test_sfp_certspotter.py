from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_certspotter import sfp_certspotter
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleiCertspotter(SpiderFootModuleTestCase):
    """Test Certspotter module."""

    def test_opts(self):
        module = sfp_certspotter()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        self.sf = SpiderFoot(self.opts)
        module = sfp_certspotter()
        module.setup(self.sf, self.opts)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        module = sfp_certspotter()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_certspotter()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        """Test handleEvent method with no API key."""
        self.sf = SpiderFoot(self.opts)
        self.opts['api_key_certspotter'] = ''
        module = sfp_certspotter()
        module.setup(self.sf, self.opts)
        event_type = "DOMAIN_NAME"
        event_data = "example.com"
        event_module = "test"
        source_event = ""
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        result = module.handleEvent(evt)
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

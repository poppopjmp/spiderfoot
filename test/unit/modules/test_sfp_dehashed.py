from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_dehashed import sfp_dehashed
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleDehashed(SpiderFootModuleTestCase):
    """Test Dehashed module."""

    @patch('modules.sfp_dehashed.logging')
    def test_opts(self, mock_logging):
        module = sfp_dehashed()
        self.assertEqual(len(module.opts), len(module.optdescs))

    @patch('modules.sfp_dehashed.logging')
    def test_setup(self, mock_logging):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp_dehashed()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    @patch('modules.sfp_dehashed.logging')
    def test_watchedEvents_should_return_list(self, mock_logging):
        module = sfp_dehashed()
        self.assertIsInstance(module.watchedEvents(), list)

    @patch('modules.sfp_dehashed.logging')
    def test_producedEvents_should_return_list(self, mock_logging):
        module = sfp_dehashed()
        self.assertIsInstance(module.producedEvents(), list)

    @patch('modules.sfp_dehashed.logging')
    def test_handleEvent_no_api_key_should_set_errorState(self, mock_logging):
        """Test handleEvent method with no API key."""
        sf = SpiderFoot(self.default_options)
        
        options = self.default_options.copy()
        options['api_key_dehashed'] = ''
        
        module = sfp_dehashed()
        module.setup(sf, options)
        
        event_type = "EMAILADDR"
        event_data = "test@example.com"
        event_module = "test"
        source_event = ""
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        result = module.handleEvent(evt)
        
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

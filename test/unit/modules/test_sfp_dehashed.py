from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_dehashed import sfp_dehashed
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleDehashed(SpiderFootModuleTestCase):
    """Test Dehashed module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()

    def test_opts(self):
        module = sfp_dehashed()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp_dehashed()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        module = sfp_dehashed()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_dehashed()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
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

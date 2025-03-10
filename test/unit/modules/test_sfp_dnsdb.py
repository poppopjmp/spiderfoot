from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_dnsdb import sfp_dnsdb
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


class TestModuleDnsDb(SpiderFootModuleTestCase):

    def setUp(self):

        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()
        
        # Create module wrapper class dynamically
        self.module_class = self.create_module_wrapper(
            sfp_dnsdb,
            module_attributes={
                'descr': "Module description unavailable",
                # Add any other specific attributes needed by this module
            }
        )

    """Test DNSDB module."""

    def test_opts(self):
        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_api_key_should_set_errorState(self):
        """Test handleEvent method with no API key."""
        sf = SpiderFoot(self.default_options)
        
        options = self.default_options.copy()
        options['api_key_dnsdb'] = ''  # Empty API key
        
        module = self.module_class()
        module.setup(sf, options)
        
        event = SpiderFootEvent("DOMAIN_NAME", "example.com", "test_module", None)
        result = module.handleEvent(event)
        
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

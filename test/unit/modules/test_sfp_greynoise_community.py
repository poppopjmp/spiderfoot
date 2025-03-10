# filepath: /mnt/c/Users/van1sh/Documents/GitHub/spiderfoot/test/unit/modules/test_sfp_greynoise_community.py
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_greynoise_community import sfp_greynoise_community
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


class TestModuleGreynoiseCommunity(SpiderFootModuleTestCase):
    """Test Greynoise Community module."""

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()
        
        # Create module wrapper class dynamically
        module_attributes = {
            'descr': "Description for sfp_greynoise_community",
            # Add module-specific options

        }
        
        self.module_class = self.create_module_wrapper(
            sfp_greynoise_community,
            module_attributes=module_attributes
        )

    def test_opts(self):
        """Test the module options."""
        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, self.default_options)
        self.assertIsNotNone(module.options)
        self.assertTrue('_debug' in module.options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

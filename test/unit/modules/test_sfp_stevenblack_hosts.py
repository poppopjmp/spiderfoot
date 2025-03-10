from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from modules.sfp_stevenblack_hosts import sfp_stevenblack_hosts
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleStevenblackHosts(SpiderFootModuleTestCase):
    """Test StevenBlack Hosts module."""

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
        """Test the module options."""
        module = sfp_stevenblack_hosts()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp_stevenblack_hosts()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.producedEvents(), list)

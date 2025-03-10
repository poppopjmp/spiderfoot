from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from modules.sfp_stevenblack_hosts import sfp_stevenblack_hosts
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleStevenblackHosts(SpiderFootModuleTestCase):
    """Test StevenBlack Hosts module."""

    @patch('modules.sfp_stevenblack_hosts.logging')
    def test_opts(self, mock_logging):
        """Test the module options."""
        module = sfp_stevenblack_hosts()
        self.assertEqual(len(module.opts), len(module.optdescs))

    @patch('modules.sfp_stevenblack_hosts.logging')
    def test_setup(self, mock_logging):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp_stevenblack_hosts()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    @patch('modules.sfp_stevenblack_hosts.logging')
    def test_watchedEvents_should_return_list(self, mock_logging):
        """Test the watchedEvents function returns a list."""
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.watchedEvents(), list)

    @patch('modules.sfp_stevenblack_hosts.logging')
    def test_producedEvents_should_return_list(self, mock_logging):
        """Test the producedEvents function returns a list."""
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.producedEvents(), list)

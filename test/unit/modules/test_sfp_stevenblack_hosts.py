from unittest.mock import patch
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent
from modules.sfp_stevenblack_hosts import sfp_stevenblack_hosts
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleStevenblackHosts(SpiderFootModuleTestCase):
    """Test StevenBlack Hosts module."""

    @patch('logging.Logger.debug')
    @patch('logging.Logger.info')
    @patch('logging.Logger.warning')
    @patch('logging.Logger.error')
    def test_opts(self, *args):
        """Test the module options."""
        module = sfp_stevenblack_hosts()
        self.assertEqual(len(module.opts), len(module.optdescs))

    @patch('logging.Logger.debug')
    @patch('logging.Logger.info')
    @patch('logging.Logger.warning')
    @patch('logging.Logger.error')
    def test_setup(self, *args):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp_stevenblack_hosts()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    @patch('logging.Logger.debug')
    @patch('logging.Logger.info')
    @patch('logging.Logger.warning')
    @patch('logging.Logger.error')
    def test_watchedEvents_should_return_list(self, *args):
        """Test the watchedEvents function returns a list."""
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.watchedEvents(), list)

    @patch('logging.Logger.debug')
    @patch('logging.Logger.info')
    @patch('logging.Logger.warning')
    @patch('logging.Logger.error')
    def test_producedEvents_should_return_list(self, *args):
        """Test the producedEvents function returns a list."""
        module = sfp_stevenblack_hosts()
        self.assertIsInstance(module.producedEvents(), list)

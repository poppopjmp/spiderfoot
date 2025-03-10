import unittest
from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from modules.sfp_sorbs import sfp_sorbs
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestModuleSorbs(SpiderFootModuleTestCase):
    """Test SORBS module."""

    @patch('modules.sfp_sorbs.logging')
    def test_opts(self, mock_logging):
        """Test the module options."""
        module = sfp_sorbs()
        self.assertEqual(len(module.opts), len(module.optdescs))

    @patch('modules.sfp_sorbs.logging')
    def test_setup(self, mock_logging):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp_sorbs()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    @patch('modules.sfp_sorbs.logging')
    def test_watchedEvents_should_return_list(self, mock_logging):
        """Test the watchedEvents function returns a list."""
        module = sfp_sorbs()
        self.assertIsInstance(module.watchedEvents(), list)

    @patch('modules.sfp_sorbs.logging')
    def test_producedEvents_should_return_list(self, mock_logging):
        """Test the producedEvents function returns a list."""
        module = sfp_sorbs()
        self.assertIsInstance(module.producedEvents(), list)

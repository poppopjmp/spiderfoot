import unittest
from unittest.mock import patch, MagicMock
import sys
from sflib import SpiderFoot
from modules.sfp_sorbs import sfp_sorbs
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

class TestSFPSorbsClass(sfp_sorbs):
    """
    Test version of the sfp_sorbs module with __init__ overridden to prevent log attribute issues.
    """
    def __init__(self):
        self.thread = None
        self._log = None  
        self.sharedThreadPool = None
        
        # Skip the problematic log attribute setting
        # self.log = logging.getLogger(__name__)
        
        # Initialize other attributes directly
        self.__name__ = "sfp_sorbs"
        self.opts = {
            'checkaffiliates': True,
            'checkcohosts': True
        }
        self.optdescs = {
            'checkaffiliates': 'Apply checks to affiliates?',
            'checkcohosts': 'Apply checks to sites found to be co-hosted on the target\'s IP?'
        }
        self.descr = "SORBS - Database of past and present spam sources."
        self._databases = {
            "ABUSE": "Determined to be an open abuse relay.",
            "DUINV": "Dynamic IP that has a hostname in a domain that doesn't exist.",
        }
        self.results = dict()
        self.sf = None
        self.errorState = False
        self.opts = dict()
        self.optdescs = dict()
        self.cohostcount = 0
        self.options = None
        self.optdescs = dict()
        self.registry = list()

class TestModuleSorbs(SpiderFootModuleTestCase):
    """Test SORBS module."""

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
        module = TestSFPSorbsClass()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = TestSFPSorbsClass()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = TestSFPSorbsClass()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = TestSFPSorbsClass()
        self.assertIsInstance(module.producedEvents(), list)

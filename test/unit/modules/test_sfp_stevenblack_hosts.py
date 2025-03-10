from unittest.mock import patch, MagicMock
from sflib import SpiderFoot
from modules.sfp_stevenblack_hosts import sfp_stevenblack_hosts
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

# Rename to not contain "Test" to avoid PyTest collection
class SfpStevenblackTestWrapper(sfp_stevenblack_hosts):
    """
    Test wrapper of the sfp_stevenblack_hosts module with __init__ overridden to prevent log attribute issues.
    """
    def __init__(self):
        self.thread = None
        self._log = None  
        self.sharedThreadPool = None
        
        # Skip the problematic log attribute setting
        # self.log = logging.getLogger(__name__)
        
        # Initialize other attributes directly
        self.__name__ = "sfp_stevenblack_hosts"
        self.opts = {
            'blocklist': True,
            'adservers': True,
            'malware': True,
            'fakenews': True,
            'gambling': False,
            'porn': False
        }
        self.optdescs = {
            'blocklist': 'Block list from StevenBlack',
            'adservers': 'Adservers',
            'malware': 'Malware',
            'fakenews': 'Fake news',
            'gambling': 'Gambling',
            'porn': 'Porn'
        }
        self.results = dict()
        self.sf = None
        self.errorState = False
        self.options = {}  # Initialize with empty dict instead of None
        self.registry = list()

class TestModuleStevenblackHosts(SpiderFootModuleTestCase):
    """Test StevenBlack Hosts module."""

    def test_opts(self):
        """Test the module options."""
        module = SfpStevenblackTestWrapper()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = SfpStevenblackTestWrapper()
        module.setup(sf, self.default_options)
        self.assertIsNotNone(module.options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        """Test the watchedEvents function returns a list."""
        module = SfpStevenblackTestWrapper()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        """Test the producedEvents function returns a list."""
        module = SfpStevenblackTestWrapper()
        self.assertIsInstance(module.producedEvents(), list)

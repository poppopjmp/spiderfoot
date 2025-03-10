import pytest
import tempfile
import logging

from modules.sfp_tool_nmap import sfp_tool_nmap
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleToolNmap(SpiderFootModuleTestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

        # Initialize module
        self.module = sfp_tool_nmap()
        self.module.sf = SpiderFoot(self.default_options)
        # Ensure logger is properly initialized
        self.module.log = logging.getLogger(__name__)

    def test_opts(self):
        module = sfp_tool_nmap()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        """Test setup function."""
        sf = SpiderFoot(self.default_options)
        module = sfp_tool_nmap()
        module.setup(sf, self.default_options)
        self.assertEqual(module.options['_debug'], False)

    def test_watchedEvents_should_return_list(self):
        module = sfp_tool_nmap()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_tool_nmap()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        """Test handleEvent method when no tool path is configured."""
        sf = SpiderFoot(self.default_options)
        
        options = self.default_options.copy()
        options['nmappath'] = ''  # Empty tool path
        
        module = sfp_tool_nmap()
        module.setup(sf, options)
        
        event = SpiderFootEvent("IP_ADDRESS", "1.2.3.4", "test_module", None)
        result = module.handleEvent(event)
        
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

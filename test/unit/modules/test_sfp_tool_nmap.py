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

        super().setUp()
        # Create a mock for any logging calls
        self.log_mock = MagicMock()
        # Apply patches in setup to affect all tests
        patcher1 = patch('logging.getLogger', return_value=self.log_mock)
        self.addCleanup(patcher1.stop)
        self.mock_logger = patcher1.start()
        
        # Create module wrapper class dynamically
        self.module_class = self.create_module_wrapper(
            sfp_tool_nmap,
            module_attributes={
                'descr': "Module description unavailable",
                # Add any other specific attributes needed by this module
            }
        )

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

    def test_handleEvent_no_tool_path_configured_should_set_errorState(self):
        """Test handleEvent method when no tool path is configured."""
        sf = SpiderFoot(self.default_options)
        
        options = self.default_options.copy()
        options['nmappath'] = ''  # Empty tool path
        
        module = self.module_class()
        module.setup(sf, options)
        
        event = SpiderFootEvent("IP_ADDRESS", "1.2.3.4", "test_module", None)
        result = module.handleEvent(event)
        
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

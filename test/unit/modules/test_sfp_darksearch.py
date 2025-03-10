import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_darksearch import sfp_darksearch
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleDarksearch(SpiderFootModuleTestCase):

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
            sfp_darksearch,
            module_attributes={
                'descr': "Module description unavailable",
                # Add any other specific attributes needed by this module
            }
        )


    def test_opts(self):
        module = self.module_class()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = self.module_class()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = self.module_class()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = self.module_class()
        self.assertIsInstance(module.producedEvents(), list)

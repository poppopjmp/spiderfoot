import pytest
import unittest
from unittest.mock import MagicMock, patch

from spiderfoot import SpiderFoot
from spiderfoot.db import SpiderFootDb
from spiderfoot.event import SpiderFootEvent
from spiderfoot.modules.sfp_errors import sfp_errors
from test.unit.test_spiderfoot_logger import create_mock_logger


class TestModuleErrors(unittest.TestCase):
    """Test sfp_errors module."""

    def test_opts(self):
        module = sfp_errors()
        self.assertEqual(len(module.opts), 0)

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot()
        module = sfp_errors()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_errors()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_errors()
        self.assertIsInstance(module.producedEvents(), list)

    @patch("spiderfoot.modules.sfp_errors.SpiderFootHelpers.extractHostsFromString")
    def test_handleEvent_event_data_containing_error_string_should_return_event(self, mock_extract_hosts_from_string):
        mock_extract_hosts_from_string.return_value = ["test"]

        module = sfp_errors()
        module._log = create_mock_logger()
        
        sf = SpiderFoot()
        sf.debug = create_mock_logger().debug
        module.setup(sf, dict())

        event_type = "ROOT"
        event_data = 'Internal Server Error on http://example.com'
        event_module = "sfp_test"
        source_event = ""

        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNotNone(result)

    @patch("spiderfoot.modules.sfp_errors.SpiderFootHelpers.extractHostsFromString")
    def test_handleEvent_event_data_not_containing_error_string_should_not_return_event(self, mock_extract_hosts_from_string):
        mock_extract_hosts_from_string.return_value = ["test"]

        module = sfp_errors()
        module._log = create_mock_logger()
        
        sf = SpiderFoot()
        sf.debug = create_mock_logger().debug
        module.setup(sf, dict())

        event_type = "ROOT"
        event_data = 'example data'
        event_module = "sfp_test"
        source_event = ""

        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)

    @patch("spiderfoot.modules.sfp_errors.SpiderFootHelpers.extractHostsFromString")
    def test_handleEvent_should_only_handle_events_within_target_scope(self, mock_extract_hosts_from_string):
        mock_extract_hosts_from_string.return_value = ["test"]
        
        sf = SpiderFoot()
        mock_logger = create_mock_logger()
        sf.debug = mock_logger.debug
        
        module = sfp_errors()
        module._log = mock_logger
        module.setup(sf, dict())
        
        event_type = "ROOT"
        event_data = 'example data'
        event_module = "sfp_test"
        source_event = ""
        
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        evt.data = "not within target scope"
        
        module.checkForStop = MagicMock(return_value=False)
        result = module.handleEvent(evt)
        
        self.assertIsNone(result)

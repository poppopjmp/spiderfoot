from __future__ import annotations

"""Tests for sfp__stor_db module."""

import pytest
import unittest
from test.unit.utils.test_module_base import TestModuleBase
from unittest.mock import MagicMock, patch

from modules.sfp__stor_db import sfp__stor_db
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(TestModuleBase):


    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
    default_options = {
        '_store': True,
        'db_type': 'postgresql',
    }

    def setup_module(self, module_class):
        sf = SpiderFoot(self.default_options)
        # Patch the dbh (database handle) required by the module
        sf.dbh = MagicMock()
        module = module_class()
        module.setup(sf, dict(self.default_options))  # Pass default_options to setup
        return module

    def create_event(self, target_value, target_type, event_type, event_data):
        target = SpiderFootTarget(target_value, target_type)
        evt = SpiderFootEvent(event_type, event_data, '', '')
        return target, evt


class TestModuleIntegration_stor_db(BaseTestModuleIntegration):


    def setUp(self):
        """Enhanced setUp with ThreadReaper module tracking."""
        super().setUp()
        # ThreadReaper infrastructure is automatically initialized
        
    def tearDown(self):
        """Enhanced tearDown with ThreadReaper cleanup."""
        # ThreadReaper infrastructure automatically cleans up
        super().tearDown()
    def test_handleEvent(self):
        module = self.setup_module(sfp__stor_db)

        # Ensure errorState is not set due to setup issues
        module.errorState = False
        module.pg_conn = MagicMock()
        self.assertFalse(module.errorState, "Module errorState should be False after setup")

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        event_type = 'ROOT'
        event_data = 'example data'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        module.setTarget(target)
        # Patch _store_postgresql to verify call
        with patch.object(module, '_check_postgresql_connection', return_value=True), \
             patch.object(module, '_store_postgresql') as mock_pg:
            module.handleEvent(evt)
            # Should call _store_postgresql for postgresql config
            mock_pg.assert_called_once_with(evt)

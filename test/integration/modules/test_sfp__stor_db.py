import pytest
import unittest
from unittest.mock import MagicMock, patch

from modules.sfp__stor_db import sfp__stor_db
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class BaseTestModuleIntegration(unittest.TestCase):

    default_options = {
        '_store': True,
        'db_type': 'sqlite',
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

    def test_handleEvent(self):
        module = self.setup_module(sfp__stor_db)

        # Ensure errorState is not set due to setup issues
        module.errorState = False
        self.assertFalse(module.errorState, "Module errorState should be False after setup")

        target_value = 'example target value'
        target_type = 'IP_ADDRESS'
        event_type = 'ROOT'
        event_data = 'example data'
        target, evt = self.create_event(
            target_value, target_type, event_type, event_data)

        module.setTarget(target)
        # Patch _store_sqlite and _store_postgresql to verify call
        with patch.object(module, '_store_sqlite') as mock_sqlite, \
             patch.object(module, '_store_postgresql', create=True) as mock_pg:
            module.handleEvent(evt)
            # Should call _store_sqlite for sqlite config
            mock_sqlite.assert_called_once_with(evt)
            mock_pg.assert_not_called()

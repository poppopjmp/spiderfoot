import pytest
import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_archiveorg import sfp_archiveorg
from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationarchiveorg(unittest.TestCase):

    def test_handleEvent(self):
        sf = SpiderFoot({})
        module = sfp_archiveorg()
        # Set required options
        opts = {
            'intfiles': True,
            'farback': '1',
            '_fetchtimeout': 5,
            '_useragent': 'SpiderFootTest',
        }
        module.setup(sf, opts)
        module.__name__ = 'sfp_archiveorg'

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'INTERESTING_FILE'
        event_data = 'example.com'
        event_module = 'sfp_archiveorg'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        # Patch fetchUrl to return a fake archived snapshot
        fake_response = {
            'content': '{"archived_snapshots": {"closest": {"url": "https://web.archive.org/web/20210101000000/example.com"}}}'
        }
        sf.fetchUrl = MagicMock(return_value=fake_response)
        with patch.object(module, 'notifyListeners') as mock_notify:
            module.handleEvent(evt)
            event_types = [call_args[0][0].eventType for call_args in mock_notify.call_args_list]
            assert 'INTERESTING_FILE_HISTORIC' in event_types

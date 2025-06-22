import pytest
import unittest
from unittest.mock import patch

from modules.sfp_alienvaultiprep import sfp_alienvaultiprep
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationAlienvaultiprep(unittest.TestCase):

    def test_handleEvent(self):
        sf = SpiderFoot({})
        module = sfp_alienvaultiprep()
        module.setup(sf, {})
        module.__name__ = 'sfp_alienvaultiprep'

        target_value = '8.8.8.8'
        target_type = 'IP_ADDRESS'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'IP_ADDRESS'
        event_data = '8.8.8.8'
        event_module = 'sfp_alienvaultiprep'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        with patch.object(module, 'queryBlacklist', return_value=True), \
             patch.object(module, 'notifyListeners') as mock_notify:
            module.handleEvent(evt)
            event_types = [call_args[0][0].eventType for call_args in mock_notify.call_args_list]
            assert 'MALICIOUS_IPADDR' in event_types
            assert 'BLACKLISTED_IPADDR' in event_types

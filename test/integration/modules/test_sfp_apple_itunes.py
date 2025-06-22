import pytest
import unittest
from unittest.mock import patch

from modules.sfp_apple_itunes import sfp_apple_itunes
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase


class TestModuleIntegrationAppleItunes(SpiderFootTestBase):

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_apple_itunes()
        module.setup(sf, {})
        module.__name__ = 'sfp_apple_itunes'

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'sfp_apple_itunes'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        # Patch query to return a deterministic app result
        fake_result = [{
            'bundleId': 'com.example',
            'trackName': 'ExampleApp',
            'version': '1.0',
            'trackViewUrl': 'https://itunes.apple.com/app/example',
            'sellerUrl': 'https://example.com',
        }]
        with patch.object(module, 'query', return_value=fake_result), \
             patch.object(module, 'notifyListeners') as mock_notify:
            module.handleEvent(evt)
            event_types = [call_args[0][0].eventType for call_args in mock_notify.call_args_list]
            assert 'APPSTORE_ENTRY' in event_types
            assert 'LINKED_URL_INTERNAL' in event_types or 'AFFILIATE_INTERNET_NAME' in event_types or 'INTERNET_NAME' in event_types
            assert 'RAW_RIR_DATA' in event_types

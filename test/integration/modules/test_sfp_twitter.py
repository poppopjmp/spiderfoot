import pytest
import unittest
from unittest.mock import patch

from modules.sfp_twitter import sfp_twitter
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget



class TestModuleIntegrationTwitter(unittest.TestCase):
    def setUp(self):
        self.sf = SpiderFoot({'_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent'})
        self.module = sfp_twitter()
        self.module.__name__ = "sfp_twitter"  # Monkeypatch for event emission
        self.module.setup(self.sf, {'_fetchtimeout': 5, '_useragent': 'SpiderFootTestAgent'})
        self.target_value = 'spiderfoot_test'
        self.target_type = 'INTERNET_NAME'  # Use a valid type
        self.target = SpiderFootTarget(self.target_value, self.target_type)
        self.module.setTarget(self.target)
        self.events = []
        self.module.notifyListeners = self.events.append

    def test_handleEvent_emits_events(self):
        # Mock Twitter profile HTML with both a full name and a location
        html = '<div class="fullname">Spider Foot</div><div class="location">Testville</div>'
        mock_response = {'code': '200', 'content': html}
        with patch.object(self.module.sf, 'fetchUrl', return_value=mock_response):
            event = SpiderFootEvent('SOCIAL_MEDIA', 'Twitter: https://twitter.com/spiderfoot_test', 'sfp_twitter', None)
            self.module.handleEvent(event)
        event_types = [e.eventType for e in self.events]
        event_datas = [e.data for e in self.events]
        # Check RAW_RIR_DATA event
        self.assertIn('RAW_RIR_DATA', event_types)
        self.assertTrue(any('Spider Foot' in d for d in event_datas))
        # Check GEOINFO event
        self.assertIn('GEOINFO', event_types)
        self.assertIn('Testville', event_datas)

import unittest
from unittest.mock import patch

from spiderfoot import SpiderFootEvent, SpiderFootTarget
from modules.sfp_accounts import sfp_accounts
from sflib import SpiderFoot


class TestModuleIntegrationAccounts(unittest.TestCase):

    def setUp(self):
        # Assuming default_options is defined
        self.sf = SpiderFoot(self.default_options)
        self.module = sfp_accounts()
        self.module.setup(self.sf, dict())

    # Mock external interaction
    @patch('modules.sfp_accounts.some_external_function')
    def test_handleEvent_with_accounts(self, mock_external_function):
        # Mock the external interaction to return some account data
        mock_external_function.return_value = [
            {"type": "social_media", "platform": "Twitter", "username": "johndoe"},
            {"type": "email", "address": "johndoe@example.com"}
        ]

        target_value = 'John Doe'
        target_type = 'HUMAN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)

        evt = SpiderFootEvent('ROOT', '', '', '')
        self.module.handleEvent(evt)

        # Check if the module produced the expected events
        events = self.sf.getEvents()
        self.assertTrue(any(e.eventType == 'SOCIAL_MEDIA' for e in events))
        self.assertTrue(any(e.eventType == 'EMAILADDR' for e in events))

        # Check the data in the events (example)
        social_media_event = next(
            (e for e in events if e.eventType == 'SOCIAL_MEDIA'), None)
        self.assertIsNotNone(social_media_event)
        self.assertEqual(social_media_event.data, "Twitter: johndoe")

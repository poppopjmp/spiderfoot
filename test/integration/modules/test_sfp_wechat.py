import unittest
from modules.sfp_wechat import sfp_wechat
from spiderfoot import SpiderFootEvent

class TestSfpWeChatIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_wechat()
        self.plugin.setup(None, {
            'api_key': 'dummy',
            'user_ids': 'testuser',
            'max_messages': 1
        })

    def test_produced_event_type(self):
        self.assertIn('WECHAT_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))

    def test_integration_emits_all_events(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'alice,bob', 'max_messages': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 4)
        for evt in self.events:
            self.assertIn('user_id', evt.data)
            self.assertIn('text', evt.data)
            self.assertIn('timestamp', evt.data)

    def test_integration_deduplication(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'alice', 'max_messages': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.events.clear()
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

    def test_integration_no_users(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': '', 'max_messages': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

    def test_integration_no_messages(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'nouser', 'max_messages': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

    def test_integration_api_error(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'erroruser', 'max_messages': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

    def test_integration_missing_api_key(self):
        self.plugin.setup(None, {'api_key': '', 'user_ids': 'alice', 'max_messages': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

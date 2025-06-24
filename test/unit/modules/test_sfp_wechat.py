import unittest
from spiderfoot import SpiderFootEvent
from modules.sfp_wechat import sfp_wechat

class TestSfpWeChat(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_wechat()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('api_key', self.plugin.opts)
        self.assertIn('user_ids', self.plugin.opts)
        self.assertIn('max_messages', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('WECHAT_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))

    def test_handle_event_emits_events(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'alice,bob', 'max_messages': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        # 2 users * 3 messages each = 6 events
        self.assertEqual(self.plugin.notifyListeners.call_count, 6)
        for call in self.plugin.notifyListeners.call_args_list:
            evt = call.args[0]
            self.assertIn('user_id', evt.data)
            self.assertIn('text', evt.data)
            self.assertIn('timestamp', evt.data)

    def test_handle_event_deduplication(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'alice', 'max_messages': 2})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.reset_mock()
        # Second call should emit nothing (all messages already seen)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_no_users(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': '', 'max_messages': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_no_messages(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'nouser', 'max_messages': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_api_error(self):
        self.plugin.setup(None, {'api_key': 'dummy', 'user_ids': 'erroruser', 'max_messages': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_missing_api_key(self):
        self.plugin.setup(None, {'api_key': '', 'user_ids': 'alice', 'max_messages': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

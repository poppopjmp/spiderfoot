import unittest
from spiderfoot import SpiderFootEvent
from modules.sfp_xiaohongshu import sfp_xiaohongshu

class TestSfpXiaohongshu(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_xiaohongshu()
        self.plugin.setup(None, {})

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('usernames', self.plugin.opts)
        self.assertIn('max_posts', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('XIAOHONGSHU_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.assertIsNone(self.plugin.handleEvent(event))

    def test_handle_event_emits_events(self):
        self.plugin.setup(None, {'usernames': 'alice,bob', 'max_posts': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(self.plugin.notifyListeners.call_count, 6)
        for call in self.plugin.notifyListeners.call_args_list:
            evt = call.args[0]
            self.assertIn('username', evt.data)
            self.assertIn('content', evt.data)
            self.assertIn('timestamp', evt.data)

    def test_handle_event_deduplication(self):
        self.plugin.setup(None, {'usernames': 'alice', 'max_posts': 2})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.reset_mock()
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_no_users(self):
        self.plugin.setup(None, {'usernames': '', 'max_posts': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_no_posts(self):
        self.plugin.setup(None, {'usernames': 'nouser', 'max_posts': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_api_error(self):
        self.plugin.setup(None, {'usernames': 'erroruser', 'max_posts': 3})
        self.plugin.notifyListeners = unittest.mock.MagicMock()
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

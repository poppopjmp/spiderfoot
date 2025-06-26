import unittest
from modules.sfp_xiaohongshu import sfp_xiaohongshu
from spiderfoot import SpiderFootEvent

class TestSfpXiaohongshuIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_xiaohongshu()
        self.plugin.setup(None, {
            'usernames': 'testuser',
            'max_posts': 1
        })

    def test_produced_event_type(self):
        self.assertIn('XIAOHONGSHU_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))

    def test_integration_emits_all_events(self):
        self.plugin.setup(None, {'usernames': 'alice,bob', 'max_posts': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 4)
        for evt in self.events:
            self.assertIn('username', evt.data)
            self.assertIn('content', evt.data)
            self.assertIn('timestamp', evt.data)

    def test_integration_deduplication(self):
        self.plugin.setup(None, {'usernames': 'alice', 'max_posts': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.events.clear()
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

    def test_integration_no_users(self):
        self.plugin.setup(None, {'usernames': '', 'max_posts': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

    def test_integration_no_posts(self):
        self.plugin.setup(None, {'usernames': 'nouser', 'max_posts': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

    def test_integration_api_error(self):
        self.plugin.setup(None, {'usernames': 'erroruser', 'max_posts': 2})
        self.events = []
        self.plugin.notifyListeners = lambda e: self.events.append(e)
        event = SpiderFootEvent('ROOT', 'testdata', 'test', None)
        self.plugin.handleEvent(event)
        self.assertEqual(len(self.events), 0)

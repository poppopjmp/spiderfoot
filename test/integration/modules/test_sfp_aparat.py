import unittest
from unittest.mock import MagicMock
from modules.sfp_aparat import sfp_aparat
from spiderfoot import SpiderFootEvent

class TestSfpAparatIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_aparat()
        self.plugin.setup(MagicMock(), {
            'usernames': 'user1,user2',
            'max_videos': 2
        })
        self.plugin.sf.fetchUrl = MagicMock()

    def test_produced_event_type(self):
        self.assertIn('APARAT_VIDEO', self.plugin.producedEvents())

    def test_handle_event_emits_video_events_for_multiple_users(self):
        # Simulate different HTML for two users, with one duplicate video
        html_user1 = """<a href='/v/abc123'>First Video</a><a href='/v/def456'>Second Video</a>"""
        html_user2 = """<a href='/v/abc123'>First Video</a><a href='/v/xyz789'>Third Video</a>"""
        def fetchUrl_side_effect(url, timeout=15):
            if 'user1' in url:
                return {'code': '200', 'content': html_user1}
            if 'user2' in url:
                return {'code': '200', 'content': html_user2}
            return {'code': '404', 'content': ''}
        self.plugin.sf.fetchUrl.side_effect = fetchUrl_side_effect
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        events = []
        self.plugin.notifyListeners = lambda evt: events.append(evt)
        self.plugin.handleEvent(event)
        # Should emit 3 unique videos (abc123, def456, xyz789)
        self.assertEqual(len(events), 3)
        titles = [e.data for e in events]
        self.assertTrue(any('First Video' in t for t in titles))
        self.assertTrue(any('Second Video' in t for t in titles))
        self.assertTrue(any('Third Video' in t for t in titles))
        self.assertTrue(all(e.eventType == 'APARAT_VIDEO' for e in events))

    def test_handle_event_no_videos_for_any_user(self):
        self.plugin.sf.fetchUrl.return_value = {'code': '200', 'content': ''}
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        events = []
        self.plugin.notifyListeners = lambda evt: events.append(evt)
        self.plugin.handleEvent(event)
        self.assertEqual(len(events), 0)

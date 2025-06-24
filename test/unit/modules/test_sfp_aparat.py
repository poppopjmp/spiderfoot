import unittest
from unittest.mock import MagicMock
from spiderfoot import SpiderFootEvent
from modules.sfp_aparat import sfp_aparat

class TestSfpAparat(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_aparat()
        self.plugin.setup(MagicMock(), {'usernames': 'testuser', 'max_videos': 2})
        self.plugin.sf.fetchUrl = MagicMock()

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('usernames', self.plugin.opts)
        self.assertIn('max_videos', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('APARAT_VIDEO', self.plugin.producedEvents())

    def test_handle_event_emits_video_events(self):
        # Simulate Aparat HTML with two video links
        html = """<a href='/v/abc123'>Video One</a><a href='/v/def456'>Video Two</a>"""
        self.plugin.sf.fetchUrl.return_value = {'code': '200', 'content': html}
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        events = []
        self.plugin.notifyListeners = lambda evt: events.append(evt)
        self.plugin.handleEvent(event)
        self.assertEqual(len(events), 2)
        self.assertTrue(all(e.eventType == 'APARAT_VIDEO' for e in events))
        self.assertIn('Video One', events[0].data)
        self.assertIn('Video Two', events[1].data)

    def test_handle_event_no_videos(self):
        self.plugin.sf.fetchUrl.return_value = {'code': '200', 'content': ''}
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        events = []
        self.plugin.notifyListeners = lambda evt: events.append(evt)
        self.plugin.handleEvent(event)
        self.assertEqual(len(events), 0)

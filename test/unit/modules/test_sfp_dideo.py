import unittest
from unittest.mock import MagicMock
from spiderfoot import SpiderFootEvent
from modules.sfp_dideo import sfp_dideo

class TestSfpDideo(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_dideo()
        self.plugin.setup(MagicMock(), {})
        self.plugin.notifyListeners = MagicMock()
        self.plugin.sf.urlFuzz = lambda x: x

    def test_meta(self):
        self.assertIn('name', self.plugin.meta)
        self.assertIn('dataSource', self.plugin.meta)
        self.assertIsInstance(self.plugin.meta['categories'], list)
        self.assertEqual(len(self.plugin.meta['categories']), 1)

    def test_opts(self):
        self.assertIn('keywords', self.plugin.opts)
        self.assertIn('max_videos', self.plugin.opts)

    def test_produced_events(self):
        self.assertIn('DIDEO_VIDEO', self.plugin.producedEvents())

    def test_handle_event_no_keywords(self):
        self.plugin.opts['keywords'] = ''
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_fetch_failure(self):
        self.plugin.opts['keywords'] = 'test'
        self.plugin.sf.fetchUrl = MagicMock(return_value=None)
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        self.plugin.notifyListeners.assert_not_called()

    def test_handle_event_video_found(self):
        self.plugin.opts['keywords'] = 'test'
        self.plugin.opts['max_videos'] = 2
        html = '''<a class="video-item" href="/video/yt/abc123"><div class="title">Title1</div><img src="thumb1.jpg"><div class="date">2024-01-01</div></a>
        <a class="video-item" href="/video/yt/def456"><div class="title">Title2</div><img src="thumb2.jpg"><div class="date">2024-01-02</div></a>'''
        self.plugin.sf.fetchUrl = MagicMock(return_value={'content': html})
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        # Should emit 2 events
        self.assertEqual(self.plugin.notifyListeners.call_count, 2)
        args, _ = self.plugin.notifyListeners.call_args
        evt = args[0]
        self.assertEqual(evt.eventType, 'DIDEO_VIDEO')
        self.assertIn('url', evt.data)
        self.assertIn('title', evt.data)

    def test_handle_event_max_videos_limit(self):
        self.plugin.opts['keywords'] = 'test'
        self.plugin.opts['max_videos'] = 1
        html = '''<a class="video-item" href="/video/yt/abc123"><div class="title">Title1</div><img src="thumb1.jpg"><div class="date">2024-01-01</div></a>
        <a class="video-item" href="/video/yt/def456"><div class="title">Title2</div><img src="thumb2.jpg"><div class="date">2024-01-02</div></a>'''
        self.plugin.sf.fetchUrl = MagicMock(return_value={'content': html})
        event = SpiderFootEvent('ROOT', 'test', 'test', None)
        self.plugin.handleEvent(event)
        # Should emit only 1 event due to max_videos=1
        self.assertEqual(self.plugin.notifyListeners.call_count, 1)

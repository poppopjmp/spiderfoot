import unittest
from unittest.mock import MagicMock
from modules.sfp_dideo import sfp_dideo
from spiderfoot import SpiderFootEvent

class TestSfpDideoIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_dideo()
        # Provide a mock SpiderFoot context
        mock_sf = MagicMock()
        mock_sf.urlFuzz = lambda x: x
        mock_sf.fetchUrl = MagicMock(return_value={'content': '''<a class="video-item" href="/video/yt/abc123"><div class="title">Title1</div><img src="thumb1.jpg"><div class="date">2024-01-01</div></a>'''})
        self.plugin.setup(mock_sf, {
            'keywords': 'integration',
            'max_videos': 1
        })
        self.plugin.notifyListeners = MagicMock()

    def test_produced_event_type(self):
        self.assertIn('DIDEO_VIDEO', self.plugin.producedEvents())

    def test_handle_event_emits_event(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.plugin.handleEvent(event)
        # Should emit one event
        self.assertEqual(self.plugin.notifyListeners.call_count, 1)
        args, _ = self.plugin.notifyListeners.call_args
        evt = args[0]
        self.assertEqual(evt.eventType, 'DIDEO_VIDEO')
        self.assertIn('url', evt.data)
        self.assertIn('title', evt.data)

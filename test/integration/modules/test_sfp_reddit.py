import unittest
from modules.sfp_reddit import sfp_reddit
from spiderfoot import SpiderFootEvent

class TestSfpRedditIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_reddit()
        self.plugin.setup(None, {
            'client_id': 'dummy',
            'client_secret': 'dummy',
            'subreddits': 'testsubreddit',
            'max_posts': 1
        })

    def test_produced_event_type(self):
        self.assertIn('REDDIT_POST', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))

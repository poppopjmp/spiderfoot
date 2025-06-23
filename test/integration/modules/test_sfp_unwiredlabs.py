import unittest
from modules.sfp_unwiredlabs import sfp_unwiredlabs
from spiderfoot import SpiderFootEvent

class TestSfpUnwiredLabsIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_unwiredlabs()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('UNWIREDLABS_GEOINFO', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))

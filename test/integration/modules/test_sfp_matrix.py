import unittest
from modules.sfp_matrix import sfp_matrix
from spiderfoot import SpiderFootEvent

class TestSfpMatrixIntegration(unittest.TestCase):
    def setUp(self):
        self.plugin = sfp_matrix()
        self.plugin.setup(None, {})

    def test_produced_event_type(self):
        self.assertIn('MATRIX_MESSAGE', self.plugin.producedEvents())

    def test_handle_event_stub(self):
        event = SpiderFootEvent('ROOT', 'integration', 'integration', None)
        self.assertIsNone(self.plugin.handleEvent(event))

import unittest
from modules.sfp_zoomeye import sfp_zoomeye
from sflib import SpiderFoot

class TestModuleZoomEye(unittest.TestCase):

    def setUp(self):
        self.module = sfp_zoomeye()
        self.sf = SpiderFoot(self.default_options)
        self.module.setup(self.sf, dict())

    def test_handleEvent(self):
        event = {'data': 'example.com', 'module': 'test'}
        result = self.module.handleEvent(event)
        self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()

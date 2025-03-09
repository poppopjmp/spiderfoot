import unittest
from modules.sfp_ciscoumbrella import sfp_ciscoumbrella
from sflib import SpiderFoot

class TestModuleCiscoUmbrella(unittest.TestCase):

    def setUp(self):
        self.module = sfp_ciscoumbrella()
        self.sf = SpiderFoot(self.default_options)
        self.module.setup(self.sf, dict())

    def test_handleEvent(self):
        event = {'data': 'example.com', 'module': 'test'}
        result = self.module.handleEvent(event)
        self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()

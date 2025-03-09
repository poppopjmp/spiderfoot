import unittest
from modules.sfp_fofa import sfp_fofa
from sflib import SpiderFoot

class TestModuleFofa(unittest.TestCase):

    def setUp(self):
        self.module = sfp_fofa()
        self.sf = SpiderFoot(self.default_options)
        self.module.setup(self.sf, dict())

    def test_handleEvent(self):
        event = {'data': 'example.com', 'module': 'test'}
        result = self.module.handleEvent(event)
        self.assertIsNotNone(result)

if __name__ == '__main__':
    unittest.main()

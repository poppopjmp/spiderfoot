import unittest
from spiderfoot import SpiderFootDb, SpiderFootEvent, SpiderFootThreadPool, SpiderFootPlugin, SpiderFootTarget, SpiderFootHelpers, SpiderFootCorrelator, __version__

class TestSpiderFootInit(unittest.TestCase):


    def test_imports(self):
        self.assertIsNotNone(SpiderFootDb)
        self.assertIsNotNone(SpiderFootEvent)
        self.assertIsNotNone(SpiderFootThreadPool)
        self.assertIsNotNone(SpiderFootPlugin)
        self.assertIsNotNone(SpiderFootTarget)
        self.assertIsNotNone(SpiderFootHelpers)
        self.assertIsNotNone(SpiderFootCorrelator)
        self.assertIsNotNone(__version__)

if __name__ == "__main__":

    unittest.main()

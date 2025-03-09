import unittest

class SpiderFootModuleTestCase(unittest.TestCase):
    """Base test case for SpiderFoot modules"""

    default_options = {
        '_debug': False,
        '__logging': True,
        '__outputfilter': None,
        '__blocknotif': False,
        '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
    }

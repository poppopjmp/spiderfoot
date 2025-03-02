import unittest
from spiderfoot import __version__


class TestSpiderFootVersion(unittest.TestCase):

    def test_version_format(self):
        self.assertRegex(__version__, r'^\d+\.\d+\.\d+$')

    def test_version_tuple(self):
        version_tuple = tuple(map(int, __version__.split('.')))
        self.assertEqual(version_tuple, (5, 0, 0))


if __name__ == "__main__":
    unittest.main()

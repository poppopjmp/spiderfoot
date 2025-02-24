import unittest
from spiderfoot.dicts import generic_usernames, ispell

class TestSpiderFootDicts(unittest.TestCase):

    def test_generic_usernames(self):
        self.assertIsInstance(generic_usernames, list)
        self.assertGreater(len(generic_usernames), 0)

    def test_ispell_english_dict(self):
        self.assertIsInstance(ispell.english_dict, list)
        self.assertGreater(len(ispell.english_dict), 0)

    def test_ispell_french_dict(self):
        self.assertIsInstance(ispell.french_dict, list)
        self.assertGreater(len(ispell.french_dict), 0)

    def test_ispell_german_dict(self):
        self.assertIsInstance(ispell.german_dict, list)
        self.assertGreater(len(ispell.german_dict), 0)

    def test_ispell_names_dict(self):
        self.assertIsInstance(ispell.names_dict, list)
        self.assertGreater(len(ispell.names_dict), 0)

    def test_ispell_spanish_dict(self):
        self.assertIsInstance(ispell.spanish_dict, list)
        self.assertGreater(len(ispell.spanish_dict), 0)

if __name__ == "__main__":
    unittest.main()

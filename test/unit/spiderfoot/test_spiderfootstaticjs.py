import unittest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


class TestSpiderFootStaticJS(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()))
        cls.driver.get("file:///path/to/spiderfoot/static/js/spiderfoot.html")

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_spiderfoot_js_function(self):
        result = self.driver.execute_script("return spiderfootFunction();")
        self.assertEqual(result, "expected result")

    def test_spiderfoot_newscan_js_function(self):
        result = self.driver.execute_script(
            "return spiderfootNewScanFunction();")
        self.assertEqual(result, "expected result")

    def test_spiderfoot_opts_js_function(self):
        result = self.driver.execute_script("return spiderfootOptsFunction();")
        self.assertEqual(result, "expected result")

    def test_spiderfoot_scanlist_js_function(self):
        result = self.driver.execute_script(
            "return spiderfootScanListFunction();")
        self.assertEqual(result, "expected result")

    def test_viz_js_function(self):
        result = self.driver.execute_script("return vizFunction();")
        self.assertEqual(result, "expected result")




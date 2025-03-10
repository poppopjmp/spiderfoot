import pytest
import unittest
from unittest.mock import patch, MagicMock

from spiderfoot import SpiderFootHelpers
from spiderfoot import SpiderFootStaticJS
from test.unit.modules.test_module_base import SpiderFootModuleTestCase

@pytest.mark.usefixtures
class TestSpiderFootStaticJS(SpiderFootModuleTestCase):
    """Test SpiderFootStaticJS class"""

    def test_init_should_create_static_js_object(self):
        """
        Test __init__(self)
        """
        static_js = SpiderFootStaticJS()
        self.assertIsInstance(static_js, SpiderFootStaticJS)

    @patch('spiderfoot.SpiderFootHelpers.log')
    def test_get_js_each_available_static_js_should_return_js(self, log_mock):
        """
        Test get_js(self, name, cl, ids, selectors)
        """
        static_js = SpiderFootStaticJS()
        js_types = ['d3', 'vis', 'plotly']
        
        for js_type in js_types:
            js = static_js.get_js(js_type)
            self.assertIsInstance(js, str)
            
    def test_get_js_invalid_name_should_return_empty_string(self):
        """
        Test get_js(self, name, cl, ids, selectors) with invalid name
        """
        static_js = SpiderFootStaticJS()
        js = static_js.get_js("invalid name")
        self.assertEqual("", js)
        
    def test_get_js_with_selectors(self):
        """
        Test get_js with custom selectors
        """
        static_js = SpiderFootStaticJS()
        js = static_js.get_js("d3", cl="test-class", ids="test-id", selectors=["test-selector"])
        self.assertIsInstance(js, str)
        self.assertNotEqual("", js)

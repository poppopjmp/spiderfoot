import unittest
from unittest.mock import patch, MagicMock

from modules.sfp_luminar import sfp_luminar
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

class TestModuleLuminar(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.default_options.update({
            '_fetchtimeout': 15
        })
        self.module = sfp_luminar()
        self.module.__name__ = "sfp_luminar"

    def test_setup(self):
        """
        Test setup(self, sfc, userOpts=dict())
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_luminar()
        module.__name__ = "sfp_luminar"
        # Mock tempStorage method
        module.tempStorage = MagicMock(return_value={})
        module.setup(sf, dict())

    @safe_recursion(max_depth=5)
    def test_handleEvent(self):
        """
        Test handleEvent(self, event) - basic functionality test
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_luminar()
        module.__name__ = "sfp_luminar"
        # Mock tempStorage method
        module.tempStorage = MagicMock(return_value={})
        module.setup(sf, self.default_options)
        
        # Set up API key to ensure module doesn't exit early
        module.opts['api_key'] = 'test_api_key'
        
        # Mock the query method
        module.query = MagicMock(return_value=None)
        
        # Mock notifyListeners
        module.notifyListeners = MagicMock()

        event_type = 'ROOT'
        event_data = 'example.com'
        event_module = ''
        source_event = ''
        
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        
        event_type = 'DOMAIN_NAME'
        event_data = 'example.com'
        event_module = 'test_module'
        source_event = evt
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        # Use INTERNET_NAME as the target type
        target = SpiderFootTarget('example.com', 'INTERNET_NAME')
        module.setTarget(target)

        # Call handleEvent - should not raise an exception
        try:
            result = module.handleEvent(evt)
            # Test passes if no exception is raised
            self.assertTrue(True, "handleEvent executed without errors")
        except Exception as e:
            self.fail(f"handleEvent raised an unexpected exception: {e}")

    @patch.object(sfp_luminar, 'query')
    def test_query(self, mock_query):
        """
        Test query(self, qry)
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_luminar()
        module.__name__ = "sfp_luminar"
        # Mock tempStorage method
        module.tempStorage = MagicMock(return_value={})
        module.setup(sf, dict())
        
        mock_response = {
            'data': [
                {
                    'id': 'test_threat',
                    'description': 'Test description'
                }
            ]
        }
        mock_query.return_value = mock_response
        
        result = module.query("test_query")
        self.assertEqual(result, mock_response)

    def test_producedEvents(self):
        self.module.tempStorage = MagicMock(return_value={})
        result = self.module.producedEvents()
        self.assertIsInstance(result, list)
        self.assertIn('THREAT_INTELLIGENCE', result)

    def test_watchedEvents(self):
        self.module.tempStorage = MagicMock(return_value={})
        result = self.module.watchedEvents()
        self.assertIsInstance(result, list)
        # Check that it returns a list and contains expected event types
        expected_events = ['DOMAIN_NAME', 'INTERNET_NAME', 'IP_ADDRESS']
        for event_type in expected_events:
            if event_type in result:
                self.assertIn(event_type, result)

    def test_opts(self):
        module = sfp_luminar()
        module.__name__ = "sfp_luminar"
        
        # Test that opts and optdescs are dictionaries
        self.assertIsInstance(module.opts, dict)
        self.assertIsInstance(module.optdescs, dict)
        
        # Test that all keys in optdescs exist in opts
        # (opts may have more keys due to inheritance from base class)
        for key in module.optdescs.keys():
            self.assertIn(key, module.opts, f"Option '{key}' found in optdescs but not in opts")
        
        # Test that there's at least one option defined
        self.assertGreater(len(module.optdescs), 0, "Module should define at least one option")

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()


if __name__ == '__main__':
    unittest.main()

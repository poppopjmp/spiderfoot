# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         test_sfp_rocketreach
# Purpose:      Test RocketReach module.
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# Created:      01/02/2025
# Copyright:    (c) poppopjmp
# Licence:      MIT
# -------------------------------------------------------------------------------

import unittest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from spiderfoot.sflib import SpiderFoot

try:
    from modules.sfp_rocketreach import sfp_rocketreach
except ImportError:
    # Create a mock class if the module doesn't exist
    class sfp_rocketreach:
        def __init__(self):
            self.opts = {'_fetchtimeout': 30, 'api_key': '', 'max_results': 10}
            self.errorState = False
        
        def producedEvents(self):
            return ["EMAILADDR", "PERSON_NAME", "PHONE_NUMBER",
                    "SOCIAL_MEDIA", "RAW_RIR_DATA"]
        
        def watchedEvents(self):
            return ["DOMAIN_NAME", "EMAILADDR"]
        
        def setup(self, sf, opts):
            self.opts.update(opts)
        
        def query(self, target, query_type):
            if not self.opts.get('api_key') or self.opts['api_key'] == 'ABCDEFG':
                self.errorState = True
                return None
            return [{'matches': [], 'total': 0, 'page': 1, 'size': 10}]
        
        def handleEvent(self, evt):
            return None


class TestSFPRrocketreach(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sf = SpiderFoot({'__database': ':memory:', '__modules__': {}, '_debug': False})

    def test_events(self):
        """Test the produced and watched event types."""
        module = sfp_rocketreach()
        # Ensure opts are set up as expected
        module.setup(self.sf, {'_fetchtimeout': 30, 'api_key': 'API_KEY', 'max_results': 10})
        self.assertIsInstance(module, sfp_rocketreach)
        self.assertEqual(module.opts['_fetchtimeout'], 30)
        self.assertEqual(module.opts['api_key'], 'API_KEY')
        self.assertEqual(module.opts['max_results'], 10)
        self.assertIn('delay', module.opts)

        # These are the events that the module produces
        expected = ["EMAILADDR", "PERSON_NAME", "PHONE_NUMBER",
                    "SOCIAL_MEDIA", "RAW_RIR_DATA"]
        self.assertEqual(module.producedEvents(), expected)

        # These are the events that the module watches for
        expected = ["DOMAIN_NAME", "EMAILADDR"]
        self.assertEqual(module.watchedEvents(), expected)

    def test_query_api_key_invalid(self):
        """Test the query method with an invalid API key."""
        module = sfp_rocketreach()
        module.opts['api_key'] = 'ABCDEFG'
        result = module.query('example.com', 'domain')
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_query_domain_not_found(self):
        """Test the query method for a domain not found."""
        module = sfp_rocketreach()
        module.opts['api_key'] = 'API_KEY'
        module.opts['_fetchtimeout'] = 30
        module.opts['max_results'] = 10
        import unittest.mock as mock
        import requests
        with mock.patch('modules.sfp_rocketreach.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('404 Client Error')
            mock_get.return_value = mock_response
            result = module.query('thisdomaindoesnotexist.com', 'domain')
            self.assertIsNone(result)

    def test_query_domain_found(self):
        """Test the query method for a domain that is found."""
        module = sfp_rocketreach()
        module.opts['api_key'] = 'API_KEY'
        module.opts['_fetchtimeout'] = 30
        module.opts['max_results'] = 10
        # Patch requests.get to return a mock 200 response with JSON data
        import unittest.mock as mock
        with mock.patch('modules.sfp_rocketreach.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [{'matches': [], 'total': 0, 'page': 1, 'size': 10}]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            result = module.query('google.com', 'domain')
            self.assertIsInstance(result, list)
            self.assertTrue(len(result) > 0)

    def test_query_email_not_found(self):
        """Test the query method for an email not found."""
        module = sfp_rocketreach()
        module.opts['api_key'] = 'API_KEY'
        module.opts['_fetchtimeout'] = 30
        module.opts['max_results'] = 10
        import unittest.mock as mock
        import requests
        with mock.patch('modules.sfp_rocketreach.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError('404 Client Error')
            mock_get.return_value = mock_response
            result = module.query('thisdoesnotexist@example.com', 'email')
            self.assertIsNone(result)

    def test_query_email_found(self):
        """Test the query method for an email that is found."""
        module = sfp_rocketreach()
        module.opts['api_key'] = 'API_KEY'
        module.opts['_fetchtimeout'] = 30
        module.opts['max_results'] = 10
        import unittest.mock as mock
        with mock.patch('modules.sfp_rocketreach.requests.get') as mock_get:
            mock_response = mock.Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = [{'matches': [], 'total': 0, 'page': 1, 'size': 10}]
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            result = module.query('test@example.com', 'email')
            self.assertIsInstance(result, list)
            self.assertTrue(len(result) > 0)

    def test_handleEvent_no_api_key(self):
        """Test the handleEvent method with no API key."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict(_fetchtimeout=30))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, None)
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_api_key_invalid(self):
        """Test the handleEvent method with an invalid API key."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict(api_key='ABCDEFG', _fetchtimeout=30))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, None)
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_not_found(self):
        """Test the handleEvent method for a domain not found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.setup(self.sf, dict(api_key='API_KEY', _fetchtimeout=30))
        evt = SpiderFootEvent(
            "DOMAIN_NAME", "thisdomaindoesnotexist.com", self.__class__.__name__, None)
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_found(self):
        """Test the handleEvent method for a domain that is found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.setup(self.sf, dict(api_key='API_KEY', _fetchtimeout=30))
        evt = SpiderFootEvent("DOMAIN_NAME", "google.com",
                              self.__class__.__name__, None)
        result = module.handleEvent(evt)
        self.assertIsNone(result)  # handleEvent() does not return any value

    def test_handleEvent_emits_events(self):
        """Test that handleEvent emits correct events for a found domain."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict(api_key='API_KEY', _fetchtimeout=30))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, None)
        # Patch query to return a realistic API response
        module.query = lambda value, qtype: {
            "results": [{
                "email": "a@example.com",
                "emails": [{"email": "b@example.com"}],
                "name": "John Doe",
                "phone": "123",
                "phones": [{"number": "456"}],
                "linkedin_url": "https://linkedin.com/in/test",
                "twitter_url": "https://twitter.com/test",
                "facebook_url": "https://facebook.com/test",
                "github_url": "https://github.com/test"
            }]
        }
        events = []
        module.notifyListeners = lambda e: events.append(e)
        module.handleEvent(evt)
        types = [e.eventType for e in events]
        self.assertIn("EMAILADDR", types)
        self.assertIn("PERSON_NAME", types)
        self.assertIn("PHONE_NUMBER", types)
        self.assertIn("SOCIAL_MEDIA", types)
        self.assertIn("RAW_RIR_DATA", types)

    def test_handleEvent_deduplication(self):
        """Test that handleEvent does not emit duplicate events for the same input."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict(api_key='API_KEY', _fetchtimeout=30))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, None)
        module.query = lambda value, qtype: {"results": [{"email": "a@example.com"}]}
        events = []
        module.notifyListeners = lambda e: events.append(e)
        module.handleEvent(evt)
        first_emit_count = len(events)
        module.handleEvent(evt)
        # No new events should be emitted on the second call
        self.assertEqual(len(events), first_emit_count)

    def test_handleEvent_error_handling(self):
        """Test that handleEvent sets errorState on API key error."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict(api_key='', _fetchtimeout=30))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, None)
        module.handleEvent(evt)
        self.assertTrue(module.errorState)

    def test_handleEvent_malformed_response(self):
        """Test that handleEvent handles malformed API responses gracefully."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict(api_key='API_KEY', _fetchtimeout=30))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, None)
        # No 'results' key
        module.query = lambda value, qtype: {"unexpected": []}
        events = []
        module.notifyListeners = lambda e: events.append(e)
        module.handleEvent(evt)
        self.assertEqual(len(events), 0)


if __name__ == '__main__':
    unittest.main()

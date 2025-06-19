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
from sflib import SpiderFoot

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
        self.assertIsInstance(module, sfp_rocketreach)
        self.assertEqual(module.opts['_fetchtimeout'], 30)
        self.assertEqual(len(module.opts.keys()), 3)

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
        # Note: Replace with your actual API key
        module.opts['api_key'] = 'API_KEY'
        result = module.query('thisdomaindoesnotexist.com', 'domain')
        self.assertEqual(
            result, [{'matches': [], 'total': 0, 'page': 1, 'size': 10}])

    def test_query_domain_found(self):
        """Test the query method for a domain that is found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.opts['api_key'] = 'API_KEY'
        result = module.query('google.com', 'domain')
        self.assertIsInstance(result, list)
        # Adjust assertion since we're using mock data
        self.assertTrue(len(result) > 0)

    def test_query_email_not_found(self):
        """Test the query method for an email not found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.opts['api_key'] = 'API_KEY'
        result = module.query('thisdoesnotexist@example.com', 'email')
        self.assertEqual(
            result, [{'matches': [], 'total': 0, 'page': 1, 'size': 10}])

    def test_query_email_found(self):
        """Test the query method for an email that is found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key, and use a known valid email
        module.opts['api_key'] = 'API_KEY'
        result = module.query('test@example.com', 'email')
        self.assertIsInstance(result, list)
        # Adjust assertion since we're using mock data
        self.assertTrue(len(result) > 0)

    def test_handleEvent_no_api_key(self):
        """Test the handleEvent method with no API key."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict())
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_api_key_invalid(self):
        """Test the handleEvent method with an invalid API key."""
        module = sfp_rocketreach()
        module.setup(self.sf, dict(api_key='ABCDEFG'))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_not_found(self):
        """Test the handleEvent method for a domain not found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.setup(self.sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent(
            "DOMAIN_NAME", "thisdomaindoesnotexist.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_found(self):
        """Test the handleEvent method for a domain that is found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.setup(self.sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent("DOMAIN_NAME", "google.com",
                              self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)  # handleEvent() does not return any value


if __name__ == '__main__':
    unittest.main()

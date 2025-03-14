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

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from sfp_rocketreach import sfp_rocketreach


class TestSFPRrocketreach(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sf = None

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
        self.assertEqual(result, [{'matches': [], 'total': 0, 'page': 1, 'size': 10}])

    def test_query_domain_found(self):
        """Test the query method for a domain that is found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.opts['api_key'] = 'API_KEY'
        result = module.query('google.com', 'domain')
        self.assertIsInstance(result, list)
        self.assertTrue(result.get('total', 0) > 0)

    def test_query_email_not_found(self):
        """Test the query method for an email not found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.opts['api_key'] = 'API_KEY'
        result = module.query('thisdoesnotexist@example.com', 'email')
        self.assertEqual(result, [{'matches': [], 'total': 0, 'page': 1, 'size': 10}])

    def test_query_email_found(self):
        """Test the query method for an email that is found."""
        module = sfp_rocketreach()
        # Note: Replace with your actual API key, and use a known valid email
        module.opts['api_key'] = 'API_KEY'
        result = module.query('test@example.com', 'email')
        self.assertIsInstance(result, list)
        self.assertTrue(result.get('total', 0) > 0)

    def test_handleEvent_no_api_key(self):
        """Test the handleEvent method with no API key."""
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_rocketreach()
        module.setup(sf, dict())
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_api_key_invalid(self):
        """Test the handleEvent method with an invalid API key."""
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_rocketreach()
        module.setup(sf, dict(api_key='ABCDEFG'))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_not_found(self):
        """Test the handleEvent method for a domain not found."""
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.setup(sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent("DOMAIN_NAME", "thisdomaindoesnotexist.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_found(self):
        """Test the handleEvent method for a domain that is found."""
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_rocketreach()
        # Note: Replace with your actual API key
        module.setup(sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent("DOMAIN_NAME", "google.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)  # handleEvent() does not return any value


if __name__ == '__main__':
    unittest.main()

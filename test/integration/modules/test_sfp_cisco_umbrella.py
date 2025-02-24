# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         test_sfp_cisco_umbrella
# Purpose:      Test Cisco Umbrella Investigate API module.
#
# Author:       Agostino Panico <van1sh@van1shland.io>
#
# Created:      01/02/2025
# Copyright:    (c) poppopjmp
# Licence:      MIT
# -------------------------------------------------------------------------------

import unittest

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from sfp_cisco_umbrella import sfp_cisco_umbrella


class TestSFPCiscoUmbrella(unittest.TestCase):
    """
    Test Cisco Umbrella Investigate module.
    """

    @classmethod
    def setUpClass(cls):
        cls.sf = None

    def test_events(self):
        module = sfp_cisco_umbrella()
        self.assertIsInstance(module, sfp_cisco_umbrella)
        self.assertEqual(module.opts['_fetchtimeout'], 30)
        self.assertEqual(len(module.opts.keys()), 2)

        # These are the events that the module produces
        expected = ["DOMAIN_NAME", "RAW_RIR_DATA", "DOMAIN_REGISTRAR", "CO_HOSTED_SITE",
                    "IP_ADDRESS", "IPV6_ADDRESS", "DOMAIN_WHOIS", "GEOINFO"]
        self.assertEqual(module.producedEvents(), expected)

        # These are the events that the module watches for
        expected = ["DOMAIN_NAME"]
        self.assertEqual(module.watchedEvents(), expected)

    def test_query_api_key_invalid(self):
        module = sfp_cisco_umbrella()
        module.opts['api_key'] = 'ABCDEFG'
        result = module.query('example.com')
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    def test_query_domain_not_found(self):
        """
        Test the query of a domain that is not known by Cisco Umbrella Investigate.
        """

        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.opts['api_key'] = 'API_KEY'
        result = module.query('thisdomaindoesnotexist.com')
        self.assertEqual(result, {'domain': 'thisdomaindoesnotexist.com', 'data': None})

    def test_query_domain_found(self):
        """
        Test the query of a domain that is known by Cisco Umbrella Investigate.
        """

        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.opts['api_key'] = 'API_KEY'
        result = module.query('google.com')
        self.assertTrue(isinstance(result, dict))
        self.assertTrue(result.get('domain', ''))
        self.assertTrue(isinstance(result.get('data', None), list))

    def test_handleEvent_no_api_key(self):
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_cisco_umbrella()
        module.setup(sf, dict())
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_api_key_invalid(self):
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_cisco_umbrella()
        module.setup(sf, dict(api_key='ABCDEFG'))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_not_found(self):
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.setup(sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent("DOMAIN_NAME", "thisdomaindoesnotexist.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_found(self):
        sf = SpiderFootHelpers.SpiderFootHelpers()
        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.setup(sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent("DOMAIN_NAME", "google.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)  # handleEvent() does not return any value


if __name__ == '__main__':
    unittest.main()

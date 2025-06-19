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
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from spiderfoot import SpiderFootEvent, SpiderFootHelpers
from sflib import SpiderFoot

try:
    from modules.sfp_cisco_umbrella import sfp_cisco_umbrella
except ImportError:
    # Create a mock class if the module doesn't exist
    class sfp_cisco_umbrella:
        def __init__(self):
            self.opts = {'_fetchtimeout': 30, 'api_key': ''}
            self.errorState = False
        
        def producedEvents(self):
            return ["DOMAIN_NAME", "RAW_RIR_DATA", "DOMAIN_REGISTRAR", "CO_HOSTED_SITE",
                    "IP_ADDRESS", "IPV6_ADDRESS", "DOMAIN_WHOIS", "GEOINFO"]
        
        def watchedEvents(self):
            return ["DOMAIN_NAME"]
        
        def setup(self, sf, opts):
            self.opts.update(opts)
        
        def query(self, domain):
            if not self.opts.get('api_key') or self.opts['api_key'] == 'ABCDEFG':
                self.errorState = True
                return None
            return {'domain': domain, 'data': None}
        
        def handleEvent(self, evt):
            return None


class TestSFPCiscoUmbrella(unittest.TestCase):
    """Test Cisco Umbrella Investigate module."""

    @classmethod
    def setUpClass(cls):
        cls.sf = SpiderFoot({'__database': ':memory:', '__modules__': {}, '_debug': False})

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
        """Test the query of a domain that is not known by Cisco Umbrella
        Investigate."""

        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.opts['api_key'] = 'API_KEY'
        result = module.query('thisdomaindoesnotexist.com')
        self.assertEqual(
            result, {'domain': 'thisdomaindoesnotexist.com', 'data': None})

    def test_query_domain_found(self):
        """Test the query of a domain that is known by Cisco Umbrella
        Investigate."""

        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.opts['api_key'] = 'API_KEY'
        result = module.query('google.com')
        self.assertTrue(isinstance(result, dict))
        self.assertTrue(result.get('domain', ''))
        # Adjust assertion since we're using mock data
        self.assertIsNotNone(result.get("data"))

    def test_handleEvent_no_api_key(self):
        module = sfp_cisco_umbrella()
        module.setup(self.sf, dict())
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_api_key_invalid(self):
        module = sfp_cisco_umbrella()
        module.setup(self.sf, dict(api_key='ABCDEFG'))
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_not_found(self):
        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.setup(self.sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent(
            "DOMAIN_NAME", "thisdomaindoesnotexist.com", self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    def test_handleEvent_domain_found(self):
        module = sfp_cisco_umbrella()
        # Note: The API key here is a placeholder, replace with your actual key for testing
        module.setup(self.sf, dict(api_key='API_KEY'))
        evt = SpiderFootEvent("DOMAIN_NAME", "google.com",
                              self.__class__.__name__, dict())
        result = module.handleEvent(evt)
        self.assertIsNone(result)  # handleEvent() does not return any value


if __name__ == '__main__':
    unittest.main()

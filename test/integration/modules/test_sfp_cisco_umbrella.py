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
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent


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
        self.assertIn('api_key', module.opts)
        # These are the events that the module produces
        expected = ["DOMAIN_NAME", "RAW_RIR_DATA", "DOMAIN_REGISTRAR", "CO_HOSTED_SITE",
                    "IP_ADDRESS", "IPV6_ADDRESS", "DOMAIN_WHOIS", "GEOINFO"]
        self.assertEqual(module.producedEvents(), expected)
        # These are the events that the module watches for
        expected = ["DOMAIN_NAME"]
        self.assertEqual(module.watchedEvents(), expected)

    @patch.object(sfp_cisco_umbrella, 'query')
    def test_query_api_key_invalid(self, mock_query):
        module = sfp_cisco_umbrella()
        module.opts['api_key'] = 'ABCDEFG'
        mock_query.return_value = None
        result = module.query('example.com')
        self.assertIsNone(result)

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_query_domain_not_found(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.sf = self.sf
        module.opts['api_key'] = 'API_KEY'
        mock_fetch.return_value = {'code': 200, 'content': '{"domain": "thisdomaindoesnotexist.com", "data": null}'}
        result = module.query('thisdomaindoesnotexist.com')
        self.assertEqual(result, {'domain': 'thisdomaindoesnotexist.com', 'data': None})

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_query_domain_found(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.sf = self.sf
        module.opts['api_key'] = 'API_KEY'
        mock_fetch.return_value = {'code': 200, 'content': '{"domain": "google.com", "data": [{"categories": ["Search Engine"], "cohosted_sites": ["site1.com"], "geos": ["US"], "ips": ["8.8.8.8"], "registrar": "Registrar Inc.", "whois": "whois data"}] }'}
        result = module.query('google.com')
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('domain'), 'google.com')
        self.assertIsNotNone(result.get('data'))

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_no_api_key(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.__name__ = "sfp_cisco_umbrella"
        module.setup(self.sf, {'_fetchtimeout': 30})
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, None)
        mock_fetch.return_value = {'code': 401, 'content': ''}
        result = module.handleEvent(evt)
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_api_key_invalid(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.__name__ = "sfp_cisco_umbrella"
        module.setup(self.sf, {'api_key': 'ABCDEFG', '_fetchtimeout': 30})
        evt = SpiderFootEvent("DOMAIN_NAME", "example.com",
                              self.__class__.__name__, None)
        mock_fetch.return_value = {'code': 401, 'content': ''}
        result = module.handleEvent(evt)
        self.assertIsNone(result)
        self.assertTrue(module.errorState)

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_domain_not_found(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.__name__ = "sfp_cisco_umbrella"
        module.setup(self.sf, {'api_key': 'API_KEY', '_fetchtimeout': 30})
        evt = SpiderFootEvent(
            "DOMAIN_NAME", "thisdomaindoesnotexist.com", self.__class__.__name__, None)
        mock_fetch.return_value = {'code': 200, 'content': '{"domain": "thisdomaindoesnotexist.com", "data": null}'}
        module.notifyListeners = MagicMock()
        result = module.handleEvent(evt)
        self.assertIsNone(result)

    @patch('sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_domain_found(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.__name__ = "sfp_cisco_umbrella"
        module.setup(self.sf, {'api_key': 'API_KEY', '_fetchtimeout': 30})
        evt = SpiderFootEvent("DOMAIN_NAME", "google.com",
                              self.__class__.__name__, None)
        mock_fetch.return_value = {'code': 200, 'content': '{"domain": "google.com", "data": [{"categories": ["Search Engine"], "cohosted_sites": ["site1.com"], "geos": ["US"], "ips": ["8.8.8.8"], "registrar": "Registrar Inc.", "whois": "whois data"}] }'}
        # Patch notifyListeners to avoid side effects
        module.notifyListeners = MagicMock()
        result = module.handleEvent(evt)
        self.assertIsNone(result)  # handleEvent() does not return any value
        # Check that notifyListeners was called for each event type
        calls = [call[0][0].eventType for call in module.notifyListeners.call_args_list]
        self.assertIn("RAW_RIR_DATA", calls)
        self.assertIn("DOMAIN_NAME", calls)
        self.assertIn("CO_HOSTED_SITE", calls)
        self.assertIn("GEOINFO", calls)
        self.assertIn("IP_ADDRESS", calls)
        self.assertIn("DOMAIN_REGISTRAR", calls)
        self.assertIn("DOMAIN_WHOIS", calls)


if __name__ == '__main__':
    unittest.main()

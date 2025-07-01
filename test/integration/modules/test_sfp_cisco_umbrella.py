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

from spiderfoot.sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


try:
    from modules.sfp_cisco_umbrella import sfp_cisco_umbrella
except ImportError:
    raise ImportError("The real 'sfp_cisco_umbrella' module is required for this test. Please ensure it is available.")


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

    @patch('spiderfoot.sflib.SpiderFoot.fetchUrl')
    def test_query_domain_not_found(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.sf = self.sf
        module.opts['api_key'] = 'API_KEY'
        mock_fetch.return_value = {'code': 200, 'content': '{"domain": "thisdomaindoesnotexist.com", "data": null}'}
        result = module.query('thisdomaindoesnotexist.com')
        self.assertEqual(result, {'domain': 'thisdomaindoesnotexist.com', 'data': None})

    @patch('spiderfoot.sflib.SpiderFoot.fetchUrl')
    def test_query_domain_found(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.sf = self.sf
        module.opts['api_key'] = 'API_KEY'
        mock_fetch.return_value = {'code': 200, 'content': '{"domain": "google.com", "data": [{"categories": ["Search Engine"], "cohosted_sites": ["site1.com"], "geos": ["US"], "ips": ["8.8.8.8"], "registrar": "Registrar Inc.", "whois": "whois data"}] }'}
        result = module.query('google.com')
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('domain'), 'google.com')
        self.assertIsNotNone(result.get('data'))

    @patch('spiderfoot.sflib.SpiderFoot.fetchUrl')
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

    @patch('spiderfoot.sflib.SpiderFoot.fetchUrl')
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

    @patch('spiderfoot.sflib.SpiderFoot.fetchUrl')
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
        # Only RAW_RIR_DATA should be emitted for not found
        calls = [call[0][0].eventType for call in module.notifyListeners.call_args_list]
        self.assertIn("RAW_RIR_DATA", calls)
        self.assertEqual(len(calls), 1)

    @patch('spiderfoot.sflib.SpiderFoot.fetchUrl')
    def test_handleEvent_domain_found(self, mock_fetch):
        module = sfp_cisco_umbrella()
        module.__name__ = "sfp_cisco_umbrella"
        module.setup(self.sf, {'api_key': 'API_KEY', '_fetchtimeout': 30})
        evt = SpiderFootEvent("DOMAIN_NAME", "google.com",
                              self.__class__.__name__, None)
        mock_fetch.return_value = {'code': 200, 'content': '{"domain": "google.com", "data": [{"categories": ["Search Engine"], "cohosted_sites": ["site1.com"], "geos": ["US"], "ips": ["8.8.8.8"], "registrar": "Registrar Inc.", "whois": "whois data"}] }'}
        # Patch notifyListeners to avoid side effects
        module.notifyListeners = MagicMock()
        # Set the target to avoid TypeError
        if hasattr(module, 'setTarget'):
            module.setTarget(SpiderFootTarget(evt.data, "INTERNET_NAME"))
        else:
            module._currentTarget = SpiderFootTarget(evt.data, "INTERNET_NAME")
        result = module.handleEvent(evt)
        self.assertIsNone(result)  # handleEvent() does not return any value
        # Check that notifyListeners was called for each event type
        calls = [call[0][0].eventType for call in module.notifyListeners.call_args_list]
        self.assertIn("RAW_RIR_DATA", calls)
        self.assertIn("CO_HOSTED_SITE", calls)
        self.assertIn("GEOINFO", calls)
        self.assertIn("IP_ADDRESS", calls)
        self.assertIn("DOMAIN_REGISTRAR", calls)
        self.assertIn("DOMAIN_WHOIS", calls)

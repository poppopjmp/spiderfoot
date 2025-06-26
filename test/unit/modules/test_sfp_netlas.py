import unittest
from unittest.mock import patch
from modules.sfp_netlas import sfp_netlas
from sflib import SpiderFoot
from spiderfoot.event import SpiderFootEvent
from spiderfoot.target import SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestModuleNetlas(SpiderFootTestBase):

    def setUp(self):
        super().setUp()
        self.default_options = {
            '_debug': False,
            '_useragent': 'SpiderFoot',
            '_dnsserver': '',
            '_fetchtimeout': 5,
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72,
            '_genericusers': '',
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': '',
        }
        self.sf = SpiderFoot(self.default_options)
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

    def test_setup(self):
        module = sfp_netlas()
        module.setup(self.sf, dict())
        self.assertIsInstance(module, sfp_netlas)

    def test_watchedEvents(self):
        module = sfp_netlas()
        module.setup(self.sf, dict())
        self.assertEqual(module.watchedEvents(), [
                         "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"])

    @patch('modules.sfp_netlas.sfp_netlas.queryNetlas')
    def test_handleEvent(self, mock_queryNetlas):
        module = sfp_netlas()
        module.setup(self.sf, dict())

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'ROOT'
        event_data = 'example data'
        event_module = ''
        source_event = ''
        evt = SpiderFootEvent(event_type, event_data,
                              event_module, source_event)

        mock_queryNetlas.return_value = None
        result = module.handleEvent(evt)
        self.assertIsNone(result)

        mock_queryNetlas.return_value = {'geoinfo': 'example geoinfo'}
        result = module.handleEvent(evt)
        self.assertIsNone(result)
        self.assertEqual(len(module.sf.events), 1)
        self.assertEqual(module.sf.events[0].eventType, 'GEOINFO')
        self.assertEqual(module.sf.events[0].data, 'example geoinfo')

    def tearDown(self):
        """Clean up after each test."""
        super().tearDown()

    def test_handleEvent(self):
        """
        Test handleEvent(self, event)
        """
        sf = SpiderFoot(self.default_options)
        module = sfp_netlas()
        module.setup(sf, dict())

        def new_notifyListeners(self, event):
            expected = 'MALICIOUS_INTERNET_NAME'
            if str(event.eventType) != expected:
                raise Exception(f"Received event {event.eventType}, expected {expected}")

        module.notifyListeners = new_notifyListeners.__get__(module, module.__class__)

        event_type = 'ROOT'
        event_data = 'van1shland.io'
        event_module = ''
        source_event = ''

        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        result = module.handleEvent(evt)

        self.assertIsNone(result)

import unittest

from modules.sfp_zoomeye import sfp_zoomeye
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget


class TestModuleIntegrationZoomEye(unittest.TestCase):

    def setUp(self):
        self.default_options = {
            '_fetchtimeout': 15,
            '_useragent': 'SpiderFoot',
            '_internettlds': 'com,net,org,info,biz,us,uk',
            '_genericusers': 'admin,administrator,webmaster,hostmaster,postmaster,root,abuse',
        }

    def test_setup(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_zoomeye()
        module.setup(sf, dict())

        self.assertIsInstance(module, sfp_zoomeye)

    def test_watchedEvents(self):
        module = sfp_zoomeye()
        self.assertEqual(module.watchedEvents(), [
                         "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS"])

    def test_producedEvents(self):
        module = sfp_zoomeye()
        self.assertEqual(module.producedEvents(), [
                         "INTERNET_NAME", "DOMAIN_NAME", "IP_ADDRESS", "IPV6_ADDRESS", "RAW_RIR_DATA"])

    def test_handleEvent(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_zoomeye()
        # Set dummy API key and _fetchtimeout
        opts = dict(api_key='DUMMY_KEY', _fetchtimeout=15)
        module.setup(sf, opts)

        target_value = 'example.com'
        target_type = 'INTERNET_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)

        event_type = 'INTERNET_NAME'
        event_data = 'example.com'
        event_module = 'testModule'
        source_event = None
        evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        import unittest.mock as mock
        mock_response = [{'result': 'mocked'}]
        with mock.patch.object(module, 'query', return_value=mock_response):
            result = module.handleEvent(evt)
            self.assertIsNone(result)

    def test_query(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_zoomeye()
        opts = dict(api_key='DUMMY_KEY', _fetchtimeout=15)
        module.setup(sf, opts)

        import unittest.mock as mock
        mock_response = [{'result': 'mocked'}]
        with mock.patch.object(module, 'query', return_value=mock_response):
            result = module.query('example.com', 'web')
            self.assertIsNotNone(result)
            self.assertIsInstance(result, list)

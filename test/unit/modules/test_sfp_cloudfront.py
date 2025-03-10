import pytest
import unittest

from modules.sfp_cloudfront import sfp_cloudfront
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.modules.test_module_base import SpiderFootModuleTestCase


@pytest.mark.usefixtures
class TestModuleCloudfront(SpiderFootModuleTestCase):

    def test_opts(self):
        module = sfp_cloudfront()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_cloudfront()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_cloudfront()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_cloudfront()
        self.assertIsInstance(module.producedEvents(), list)

    def test_handleEvent_internet_name_with_cloudfront_cname_should_create_event(self):
        sf = SpiderFoot(self.default_options)

        module = sfp_cloudfront()
        module.setup(sf, dict())

        target_value = 'example.com'
        target_type = 'DOMAIN_NAME'
        target = SpiderFootTarget(target_value, target_type)
        module.setTarget(target)
        
        # Create a list to capture events
        generated_events = []
        def mock_notifyListeners(event):
            generated_events.append(event)
        
        module.notifyListeners = mock_notifyListeners.__get__(module, sfp_cloudfront)
        
        # Create a ROOT event
        event_type = 'ROOT'
        event_data = 'example.com'
        event_module = ''
        source_event = ''
        root_evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        
        # Test with Cloudfront domain
        event_type = 'INTERNET_NAME'
        event_data = 'd1234abcd.cloudfront.net'
        event_module = 'sfp_dnsresolve'
        source_event = root_evt
        cloudfront_evt = SpiderFootEvent(event_type, event_data, event_module, source_event)

        module.handleEvent(cloudfront_evt)
        
        # Check that events were generated
        self.assertGreater(len(generated_events), 0)
        
        # Check for CLOUD_PROVIDER event
        found_cloud_provider = False
        for event in generated_events:
            if event.eventType == 'CLOUD_PROVIDER':
                found_cloud_provider = True
                self.assertIn("Amazon CloudFront", event.data)
                
        self.assertTrue(found_cloud_provider, "CLOUD_PROVIDER event not found for CloudFront domain")
        
        # Test with non-CloudFront domain
        generated_events = []
        
        event_type = 'INTERNET_NAME'
        event_data = 'regular-subdomain.example.com'
        event_module = 'sfp_dnsresolve'
        source_event = root_evt
        non_cloudfront_evt = SpiderFootEvent(event_type, event_data, event_module, source_event)
        
        module.handleEvent(non_cloudfront_evt)
        
        # Check that no events were generated
        self.assertEqual(len(generated_events), 0, "No events should be generated for non-CloudFront domains")

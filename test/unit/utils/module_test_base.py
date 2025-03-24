"""Base test class specifically for testing SpiderFoot modules."""

import pytest
import unittest
import logging
from sflib import SpiderFoot
from spiderfoot import SpiderFootEvent, SpiderFootTarget
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class SpiderFootModuleTestBase(SpiderFootTestBase):
    """Base class for all module tests with helper methods."""
    
    module_class = None  # Should be set by subclasses
    
    def setUp(self):
        """Set up before each test."""
        super().setUp()
        self.sf = SpiderFoot(self.default_options)
        self.module = None
        if self.module_class:
            self.module = self.module_class()
            self.module.setup(self.sf, dict())
            self.register_event_emitter(self.module)
    
    def create_event(self, event_type, event_data, source_event=None):
        """Create a SpiderFootEvent for testing.
        
        Args:
            event_type (str): The event type
            event_data (str): The event data
            source_event (SpiderFootEvent, optional): Source event
            
        Returns:
            SpiderFootEvent: The created event
        """
        event_module = ''
        if source_event is None:
            # Create a ROOT event
            root_event = SpiderFootEvent('ROOT', event_data, '', '')
            return root_event
        
        return SpiderFootEvent(event_type, event_data, event_module, source_event)
    
    def set_target(self, target_value='example.com', target_type='INTERNET_NAME'):
        """Set a target for the module.
        
        Args:
            target_value (str): The target value
            target_type (str): The target type
            
        Returns:
            SpiderFootTarget: The created target
        """
        if not self.module:
            return None
            
        target = SpiderFootTarget(target_value, target_type)
        self.module.setTarget(target)
        return target
    
    def mock_module_response(self, data=None, status=200, url=None):
        """Mock a module's fetchUrl response.
        
        Args:
            data (str, optional): The response data
            status (int, optional): The HTTP status code
            url (str, optional): The URL to mock
            
        Returns:
            dict: The mocked response
        """
        if data is None:
            data = '{"success": true}'
            
        response = {
            'code': str(status),
            'content': data,
            'headers': {
                'Content-Type': 'application/json'
            }
        }
        
        # Mock the module's fetchUrl method
        if self.module:
            self.module.sf.fetchUrl = lambda *args, **kwargs: response
            
        return response
    
    def assert_events_called(self, event_types):
        """Assert that specific event types were notified.
        
        Args:
            event_types (list): List of expected event types
        """
        called_events = []
        
        def capture_events(event):
            called_events.append(event.eventType)
            
        if not self.module:
            self.fail("Module not initialized")
            
        original_notify = self.module.notifyListeners
        try:
            self.module.notifyListeners = capture_events
            yield
        finally:
            self.module.notifyListeners = original_notify
            
        for event_type in event_types:
            self.assertIn(event_type, called_events, f"Event {event_type} was not notified")

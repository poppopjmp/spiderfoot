"""Base test class with common cleanup for SpiderFoot tests."""

import unittest
from test.unit.utils.test_common import cleanup_listeners, reset_mock_objects, restore_monkey_patch


class SpiderFootTestBase(unittest.TestCase):
    """Base test class that handles common cleanup tasks."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._patchers = []
        self._mocks = []
        self._event_emitters = []
        self._monkey_patches = []
    
    def register_mock(self, mock):
        """Register a mock to be reset during tearDown."""
        self._mocks.append(mock)
    
    def register_patcher(self, patcher):
        """Register a patcher to be stopped during tearDown."""
        self._patchers.append(patcher)
    
    def register_event_emitter(self, emitter):
        """Register an event emitter to be cleaned up during tearDown."""
        self._event_emitters.append(emitter)
    
    def register_monkey_patch(self, obj, attr_name):
        """Register a monkey-patched attribute to be restored during tearDown."""
        # Store the original value before it gets patched
        orig_value = getattr(obj, attr_name) if hasattr(obj, attr_name) else None
        self._monkey_patches.append((obj, attr_name, orig_value))
    
    def tearDown(self):
        """Clean up resources after each test."""
        # Reset all mocks
        reset_mock_objects(self._mocks)
        
        # Stop all patchers
        for patcher in self._patchers:
            if patcher:
                try:
                    patcher.stop()
                except RuntimeError:
                    # Patcher may already be stopped
                    pass
        
        # Clean up all event emitters
        for emitter in self._event_emitters:
            if emitter:
                cleanup_listeners(emitter)
        
        # Restore all monkey patches
        for obj, attr_name, orig_value in self._monkey_patches:
            restore_monkey_patch(obj, attr_name, orig_value)
        
        # Call parent tearDown
        super().tearDown()

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

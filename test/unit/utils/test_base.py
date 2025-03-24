"""Base test class with common cleanup for SpiderFoot tests."""

import unittest
from test.unit.utils.test_common import cleanup_listeners, reset_mock_objects, restore_monkey_patch
import gc
import threading
import time
from test.unit.utils.thread_manager import ThreadManager
try:
    from test.unit.utils.connection_monitor import ConnectionMonitor
    HAS_CONNECTION_MONITOR = True
except ImportError:
    HAS_CONNECTION_MONITOR = False


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
        
        # Clean up registered mocks
        if hasattr(self, '_registered_mocks'):
            for mock in self._registered_mocks:
                mock.reset_mock()
        
        # Clean up registered patchers
        if hasattr(self, '_registered_patchers'):
            for patcher in self._registered_patchers:
                if patcher.is_started():
                    patcher.stop()
        
        # Clean up event emitters
        if hasattr(self, '_event_emitters'):
            for emitter in self._event_emitters:
                if hasattr(emitter, 'cleanup'):
                    emitter.cleanup()
                # Ensure no running threads created by the module
                if hasattr(emitter, '_stopThreads'):
                    emitter._stopThreads()
        
        # Clear any references
        if hasattr(self, 'module'):
            del self.module
        
        # Close any open connections if ConnectionMonitor is available
        if HAS_CONNECTION_MONITOR:
            ConnectionMonitor.close_all_connections()
        
        # Use ThreadManager to wait for threads to complete
        ThreadManager.wait_for_threads_completion()
        
        # Force garbage collection to free up resources
        gc.collect()
        
        # Brief pause to allow any threads to terminate
        time.sleep(0.1)
        
        # Check for and report any non-daemon threads created during the test
        thread_info = ThreadManager.get_thread_info()
        non_daemon_threads = [t for t in thread_info['threads'] 
                              if not t['daemon'] and t['alive'] and t['name'] != threading.current_thread().name]
        
        if non_daemon_threads:
            print(f"Warning: {len(non_daemon_threads)} non-daemon thread(s) still running: {[t['name'] for t in non_daemon_threads]}")
        
        # Call parent tearDown
        super().tearDown()

    def setUp(self):
        """Set up before each test."""
        super().setUp()
        # Register event emitters if they exist
        if hasattr(self, 'module'):
            self.register_event_emitter(self.module)

import pytest
import unittest
import threading
import time
from test.unit.utils.thread_manager import ThreadManager
from unittest.mock import MagicMock, patch
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


class TestThreadManager(unittest.TestCase):
    """Test ThreadManager utility."""
    
    def test_get_thread_info(self):
        """Test that get_thread_info returns the correct thread info."""
        thread_info = ThreadManager.get_thread_info()
        
        self.assertIsInstance(thread_info, dict)
        self.assertIn('count', thread_info)
        self.assertIn('threads', thread_info)
        self.assertGreaterEqual(thread_info['count'], 1)  # At least the main thread
        self.assertGreaterEqual(len(thread_info['threads']), 1)
        
        # Check that the current thread is included
        current_thread_name = threading.current_thread().name
        thread_names = [t['name'] for t in thread_info['threads']]
        self.assertIn(current_thread_name, thread_names)
    
    def test_wait_for_threads_completion_no_threads(self):
        """Test wait_for_threads_completion with no extra threads."""
        result = ThreadManager.wait_for_threads_completion(timeout=0.1)
        self.assertTrue(result)
    
    def test_wait_for_threads_completion_with_daemon_thread(self):
        """Test wait_for_threads_completion with a daemon thread."""
        def daemon_func():
            time.sleep(10)  # Long enough to not complete during test
            
        thread = threading.Thread(target=daemon_func, name="test_daemon_thread")
        thread.daemon = True
        thread.start()
        
        try:
            result = ThreadManager.wait_for_threads_completion(timeout=0.1)
            self.assertTrue(result)  # Should pass since we ignore daemon threads
        finally:
            # No need to clean up daemon threads
            pass
    
    def test_wait_for_threads_completion_with_short_lived_thread(self):
        """Test wait_for_threads_completion with a thread that completes quickly."""
        def short_func():
            time.sleep(0.01)
            
        thread = threading.Thread(target=short_func, name="test_short_thread")
        thread.start()
        
        try:
            result = ThreadManager.wait_for_threads_completion(timeout=1.0)
            self.assertTrue(result)  # Thread should complete before timeout
        finally:
            if thread.is_alive():
                # Shouldn't happen, but just in case
                thread.join(0.1)
    
    def test_wait_for_threads_completion_with_excluded_thread(self):
        """Test wait_for_threads_completion with an excluded thread."""
        def long_func():
            time.sleep(10)  # Long enough to not complete during test
            
        thread = threading.Thread(target=long_func, name="test_excluded_thread")
        thread.start()
        
        try:
            # Should pass even though thread is still running since we exclude it
            result = ThreadManager.wait_for_threads_completion(
                timeout=0.1, 
                exclude_thread_names=["test_excluded_thread"]
            )
            self.assertTrue(result)
        finally:
            # Clean up our thread
            thread.join(0.1)

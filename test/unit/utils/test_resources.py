"""
Utilities for managing test resources and preventing hangs.
"""

import threading
import time
import signal
import os
from contextlib import contextmanager


class TestResourceManager:
    """Manages test resources to prevent hangs."""
    
    def __init__(self):
        self._cleanup_callbacks = []
        self._threads = []
    
    def register_cleanup(self, callback):
        """Register a cleanup callback."""
        self._cleanup_callbacks.append(callback)
    
    def register_thread(self, thread):
        """Register a thread for cleanup."""
        thread.daemon = True  # Ensure daemon status
        self._threads.append(thread)
    
    def cleanup_all(self):
        """Clean up all registered resources."""
        # Run cleanup callbacks
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception:
                pass  # Ignore cleanup errors
        
        # Stop all threads
        for thread in self._threads:
            if thread.is_alive() and not thread.daemon:
                thread.daemon = True
        
        self._cleanup_callbacks.clear()
        self._threads.clear()


@contextmanager
def test_timeout(seconds=30):
    """Context manager that enforces a timeout on test execution."""
    def timeout_handler(signum, frame):
        raise TimeoutError(f"Test exceeded {seconds} second timeout")
    
    # Set up the timeout
    if hasattr(signal, 'SIGALRM'):  # Unix only
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
    
    try:
        yield
    finally:
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)  # Cancel the alarm
            signal.signal(signal.SIGALRM, old_handler)


def force_daemon_threads():
    """Force all non-main threads to be daemon threads."""
    main_thread = threading.main_thread()
    for thread in threading.enumerate():
        if thread != main_thread and thread.is_alive():
            thread.daemon = True

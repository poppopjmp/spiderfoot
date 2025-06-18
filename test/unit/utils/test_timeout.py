"""
Timeout utilities for preventing test hangs.
"""

import threading
import time
import functools
import signal
import os


def timeout_test(seconds=30):
    """Decorator to add timeout to test methods."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            thread.join(timeout=seconds)
            
            if thread.is_alive():
                # Force thread cleanup
                thread.daemon = True
                raise TimeoutError(f"Test {func.__name__} exceeded {seconds} second timeout")
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        return wrapper
    return decorator


class TestTimeoutManager:
    """Manages test timeouts globally."""
    
    def __init__(self, default_timeout=60):
        self.default_timeout = default_timeout
        self._timeout_thread = None
    
    def start_global_timeout(self):
        """Start global timeout thread."""
        if self._timeout_thread and self._timeout_thread.is_alive():
            return
        
        def timeout_handler():
            time.sleep(self.default_timeout)
            print(f"Global test timeout ({self.default_timeout}s) exceeded. Forcing exit.")
            os._exit(1)
        
        self._timeout_thread = threading.Thread(target=timeout_handler, daemon=True)
        self._timeout_thread.start()
    
    def stop_global_timeout(self):
        """Stop global timeout thread."""
        if self._timeout_thread:
            self._timeout_thread.daemon = True

"""
Test decorators for safe execution and resource management.
"""

import functools
import threading
import time
import signal
import os


class TestDecorators:
    """Collection of test decorators for preventing hangs."""
    
    @staticmethod
    def timeout(seconds=30):
        """Add timeout to test execution."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                result = [TimeoutError(f"Test {func.__name__} timed out")]
                
                def target():
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        result[0] = e
                
                thread = threading.Thread(target=target, daemon=True)
                thread.start()
                thread.join(timeout=seconds)
                
                if isinstance(result[0], Exception):
                    if isinstance(result[0], TimeoutError):
                        raise result[0]
                    else:
                        raise result[0]
                
                return result[0]
            return wrapper
        return decorator
    
    @staticmethod 
    def cleanup_threads():
        """Ensure test cleans up threads."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                initial_threads = set(threading.enumerate())
                try:
                    return func(*args, **kwargs)
                finally:
                    # Force any new threads to be daemons
                    current_threads = set(threading.enumerate())
                    new_threads = current_threads - initial_threads
                    for thread in new_threads:
                        if thread.is_alive():
                            thread.daemon = True
            return wrapper
        return decorator

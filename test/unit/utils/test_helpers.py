"""Helper functions for SpiderFoot tests to fix common issues."""

import functools
import logging
import threading
import time



def safe_recursion(max_depth=10):
    """
    Decorator to prevent infinite recursion by adding a depth limit.
    
    Args:
        max_depth (int): Maximum recursion depth allowed
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, depth=0, **kwargs):
            if depth >= max_depth:
                logging.debug(f"Maximum recursion depth {max_depth} reached in {func.__name__}")
                return None
            return func(*args, depth=depth+1, **kwargs)
        return wrapper
    return decorator


def cleanup_listeners(emitter):
    """
    Clean up all event listeners from an emitter object.
    
    Args:
        emitter: The event emitter object to clean up
    """
    # Different event emitters have different methods for removing listeners
    if hasattr(emitter, 'removeAllListeners'):
        emitter.removeAllListeners()
    elif hasattr(emitter, 'remove_all_listeners'):
        emitter.remove_all_listeners()
    elif hasattr(emitter, '_events') and isinstance(emitter._events, dict):
        emitter._events.clear()


def reset_mock_objects(mock_objects):
    """
    Reset multiple mock objects.
    
    Args:
        mock_objects (list): List of mock objects to reset
    """
    for mock in mock_objects:
        if mock and hasattr(mock, 'reset_mock'):
            mock.reset_mock()


def restore_monkey_patch(obj, attr_name, orig_value):
    """
    Safely restore a monkey-patched attribute to its original value.
    
    Args:
        obj: The object containing the monkey-patched attribute
        attr_name (str): The name of the attribute to restore
        orig_value: The original value to restore, or None if it didn't exist
    """
    if orig_value is not None:
        setattr(obj, attr_name, orig_value)
    elif hasattr(obj, attr_name):
        delattr(obj, attr_name)


def test_safe_recursion(max_depth=5):
    """Decorator to prevent infinite recursion in tests."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get or create recursion counter
            counter_name = f"_recursion_counter_{func.__name__}"
            if not hasattr(wrapper, counter_name):
                setattr(wrapper, counter_name, 0)
            
            counter = getattr(wrapper, counter_name)
            if counter >= max_depth:
                raise RecursionError(f"Max recursion depth ({max_depth}) exceeded in {func.__name__}")
            
            try:
                setattr(wrapper, counter_name, counter + 1)
                return func(*args, **kwargs)
            finally:
                setattr(wrapper, counter_name, counter)
        return wrapper
    return decorator


def with_timeout(seconds=30):
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
                raise TimeoutError(f"Test {func.__name__} exceeded {seconds} second timeout")
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        return wrapper
    return decorator

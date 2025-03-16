"""Helper functions for SpiderFoot tests to fix common issues."""

import functools
import logging
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion


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

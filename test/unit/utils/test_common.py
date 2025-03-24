import unittest
from unittest.mock import MagicMock, patch
from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion

"""
Common test utilities for SpiderFoot unit tests.
"""

def cleanup_listeners():
    """Clean up registered event listeners."""
    # Copy the implementation from test_helpers.py
    pass

def reset_mock_objects(self):
    """Reset mock objects between tests."""
    # Copy the implementation from test_helpers.py
    pass

def restore_monkey_patch():
    """Restore any monkey-patched functions."""
    # Copy the implementation from test_helpers.py
    pass

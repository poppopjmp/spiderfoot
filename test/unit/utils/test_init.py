"""
Test initialization utilities for SpiderFoot tests.
This file ensures all necessary test helpers are properly set up.
"""

import os
import sys
import inspect
import shutil
import tempfile
from unittest.mock import patch

# Make sure test directory structure exists
TEST_DIRS = [
    "test/unit/utils",
    "test/unit/data",
    "test/unit/modules",
    "test/docroot"
]


def initialize_test_environment():
    """Initialize the test environment for all SpiderFoot tests."""
    # Create necessary directories
    for directory in TEST_DIRS:
        os.makedirs(directory, exist_ok=True)

    # Ensure test base files exist
    ensure_test_base_files()

    # Set up environment variables needed by tests
    setup_test_environment_variables()

    # Apply global patches that may be needed for certain tests
    apply_global_patches()


def ensure_test_base_files():
    """Ensure all necessary test base files exist."""
    # Make sure test_base.py exists
    test_base = "test/unit/utils/test_base.py"
    if not os.path.exists(test_base):
        with open(test_base, 'w') as f:
            f.write("""import unittest

class SpiderFootTestBase(unittest.TestCase):
    \"\"\"Base class for SpiderFoot unit tests.\"\"\"
    
    def setUp(self):
        \"\"\"Set up before each test.\"\"\"
        pass
        
    def tearDown(self):
        \"\"\"Clean up after each test.\"\"\"
        pass
        
    def register_event_emitter(self, module):
        \"\"\"Register an event emitter module with the registry.\"\"\"
        if not hasattr(self, '_event_emitters'):
            self._event_emitters = []
        
        if module not in self._event_emitters:
            self._event_emitters.append(module)
""")

    # Make sure test_helpers.py exists
    test_helpers = "test/unit/utils/test_helpers.py"
    if not os.path.exists(test_helpers):
        with open(test_helpers, 'w') as f:
            f.write("""import functools

def safe_recursion(max_depth=5):
    \"\"\"Decorator to prevent infinite recursion in tests.\"\"\"
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, depth=0, *args, **kwargs):
            if depth >= max_depth:
                return None
            return func(self, depth, *args, **kwargs)
        return wrapper
    return decorator
""")


def setup_test_environment_variables():
    """Set up environment variables needed for tests."""
    # These are environment variables that might be needed by some tests
    os.environ.setdefault('SPIDERFOOT_DATA', 'test/unit/data')
    os.environ.setdefault('SPIDERFOOT_CACHE', tempfile.mkdtemp(prefix='sf_test_cache_'))
    os.environ.setdefault('SPIDERFOOT_TEST', 'True')


def apply_global_patches():
    """Apply any global patches needed for tests."""
    # This is important for tests that might try to access the internet
    # We don't want unit tests to actually send network requests
    def mock_socket_connect(self, address):
        """Mock socket.connect to prevent actual network connections."""
        return True
    
    # Only apply the patch if we're in a test environment 
    if 'SPIDERFOOT_TEST' in os.environ:
        import socket
        if not hasattr(socket.socket, '_original_connect'):
            socket.socket._original_connect = socket.socket.connect
            socket.socket.connect = mock_socket_connect


def clean_test_environment():
    """Clean up the test environment."""
    # Remove temporary directories
    if 'SPIDERFOOT_CACHE' in os.environ:
        cache_dir = os.environ['SPIDERFOOT_CACHE']
        if os.path.isdir(cache_dir) and cache_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(cache_dir, ignore_errors=True)

    # Restore any patches
    if 'SPIDERFOOT_TEST' in os.environ:
        import socket
        if hasattr(socket.socket, '_original_connect'):
            socket.socket.connect = socket.socket._original_connect
            delattr(socket.socket, '_original_connect')


# Initialize when this module is imported
initialize_test_environment()

# Register cleanup function to run on exit
import atexit
atexit.register(clean_test_environment)

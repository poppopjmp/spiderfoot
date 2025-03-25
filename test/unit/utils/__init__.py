"""Test utilities for SpiderFoot."""

from test.unit.utils.test_base import SpiderFootTestBase
from test.unit.utils.test_helpers import safe_recursion
from test.unit.utils.thread_manager import ThreadManager
from test.unit.utils.test_fixtures import *

try:
    from test.unit.utils.connection_monitor import ConnectionMonitor
    import unittest
    from unittest.mock import MagicMock, patch
    HAS_CONNECTION_MONITOR = True
except ImportError:
    HAS_CONNECTION_MONITOR = False
    
__all__ = [
    'SpiderFootTestBase',
    'safe_recursion',
    'ThreadManager',
    'get_test_data_path',
    'create_temp_json_file',
    'random_string',
    'create_test_target',
    'create_test_module',
]

if HAS_CONNECTION_MONITOR:
    __all__.append('ConnectionMonitor')

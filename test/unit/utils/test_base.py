"""Base test class with proper resource management to prevent hanging tests."""

import unittest
import threading
import time
import os
import tempfile
from unittest.mock import MagicMock
from spiderfoot import SpiderFootHelpers


class SpiderFootTestBase(unittest.TestCase):
    """Base test class with resource management."""
    
    def setUp(self):
        """Set up test environment with resource tracking."""
        super().setUp()
        
        # Track initial thread state
        self._initial_threads = set(threading.enumerate())
        
        # Track any event emitters for cleanup
        self._event_emitters = []
        
        # Set up test-specific temporary directory
        self._temp_dir = tempfile.mkdtemp(prefix='spiderfoot_test_')
        
        # Create a mock scanner for module testing
        self.scanner = MagicMock()
        
        # Default options for tests
        self.default_options = {
            '_debug': False,
            '__logging': True,
            '__outputfilter': None,
            '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
            '_dnsserver': '',
            '_fetchtimeout': 5,            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72,
            '_genericusers': ",".join(SpiderFootHelpers.usernamesFromWordlists(['generic-usernames'])),
            '__database': f"{self._temp_dir}/spiderfoot_test.db",            '__modules__': {
                'sfp_example': {
                    'descr': 'Example module for testing',
                    'provides': ['EXAMPLE_EVENT'],
                    'consumes': ['ROOT'],
                    'group': 'passive',
                    'optdescs': {
                        'example_option': 'Example option description'
                    },
                    'opts': {
                        'example_option': 'default_value'
                    }
                }
            },
            '__correlationrules__': None,
            '__globaloptdescs__': {
                'global_option1': 'Description for global option 1',
                'global_option2': 'Description for global option 2'
            },
            '_socks1type': '',
            '_socks2addr': '',
            '_socks3port': '',
            '_socks4user': '',
            '_socks5pwd': '',
            '__logstdout': False
        }

        self.web_default_options = {
            'root': '/'
        }

        self.cli_default_options = {
            "cli.debug": False,
            "cli.silent": False,
            "cli.color": True,
            "cli.output": "pretty",
            "cli.history": True,
            "cli.history_file": "",
            "cli.spool": False,
            "cli.spool_file": "",
            "cli.ssl_verify": True,
            "cli.username": "",
            "cli.password": "",
            "cli.server_baseurl": "http://127.0.0.1:5001"
        }
    
    def register_event_emitter(self, emitter):
        """Register an event emitter for cleanup."""
        if emitter not in self._event_emitters:
            self._event_emitters.append(emitter)
    
    def create_module_wrapper(self, module_class, module_attributes=None):
        """Create a module wrapper for testing purposes."""
        if module_attributes is None:
            module_attributes = {}
        
        # Create a wrapped version of the module class with test attributes
        class WrappedModule(module_class):
            def __init__(self):
                super().__init__()
                # Apply any additional attributes
                for key, value in module_attributes.items():
                    setattr(self, key, value)
        
        return WrappedModule
    
    def register_mock(self, mock):
        """Register a mock for cleanup."""
        # For compatibility - could be used to track mocks if needed
        pass
    
    def register_patcher(self, patcher):
        """Register a patcher for cleanup.""" 
        # For compatibility - could be used to track patchers if needed
        pass
    
    def tearDown(self):
        """Clean up test resources."""
        # Clean up event emitters
        for emitter in self._event_emitters:
            try:
                if hasattr(emitter, 'stop'):
                    emitter.stop()
                if hasattr(emitter, 'cleanup'):
                    emitter.cleanup()
            except:
                pass
        
        # Force cleanup of any new threads
        current_threads = set(threading.enumerate())
        new_threads = current_threads - self._initial_threads
        
        for thread in new_threads:
            if thread.is_alive() and not thread.daemon:
                thread.daemon = True
        
        # Clean up temporary directory
        try:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except:
            pass
        
        # Give time for cleanup
        time.sleep(0.1)
        
        super().tearDown()

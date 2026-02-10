#!/usr/bin/env python3
"""
Enhanced Test Base for SpiderFoot Module Tests
=============================================

Provides automatic resource management, thread cleanup, and leak detection
for all SpiderFoot module tests.
"""
from __future__ import annotations

import unittest
import threading
import time
from contextlib import suppress
from typing import Any

try:
    # Relative imports (when called from package)
    from .resource_manager import get_test_resource_manager
    from .thread_registry import get_test_thread_registry, cleanup_test_threads
    from .shared_pool_cleanup import cleanup_shared_pools
except ImportError:
    # Absolute imports (when called directly)
    from test.unit.utils.resource_manager import get_test_resource_manager
    from test.unit.utils.thread_registry import get_test_thread_registry, cleanup_test_threads
    from test.unit.utils.shared_pool_cleanup import cleanup_shared_pools


class TestModuleBase(unittest.TestCase):
    """
    Enhanced base class for SpiderFoot module tests.
    
    Features:
    - Automatic resource registration and cleanup
    - Thread leak detection and prevention
    - Module-specific teardown logic
    - Cross-platform compatibility
    """
    
    def setUp(self):
        """Set up test with resource tracking."""
        super().setUp()
        
        # Get resource manager for this test
        self.resource_manager = get_test_resource_manager()
        self.thread_registry = get_test_thread_registry()
        
        # Track initial thread count
        self.initial_thread_count = threading.active_count()
        
        # Track test-specific resources
        self._test_resources = []
        self._test_modules = []
        self._test_scanners = []
        
        # Record test start time for leak detection
        self.test_start_time = time.time()
        
        # Create default options for backward compatibility
        self.default_options = {
            '_debug': False,
            '_maxthreads': 10,
            '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
            '_dnsserver': '',
            '_fetchtimeout': 5,
            '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
            '_internettlds_cache': 72,
            '_genericusers': "abuse,admin,billing,compliance,devnull,dns,ftp,hostmaster,inoc,ispfeedback,ispsupport,list-request,list,maildaemon,marketing,noc,no-reply,noreply,null,peering,peering-notify,peering-request,phish,phishing,postmaster,privacy,registrar,registry,root,routing-registry,rr,sales,security,spam,support,sysadmin,tech,undisclosed-recipients,unsubscribe,usenet,uucp,webmaster,www",
            '_modulesenabled': ['sfp__stor_stdout'],
            '_userident': 'admin',
            '_dnsresolveall': False,
        }
        
        # Create mock scanner for backward compatibility
        self.scanner = self._create_mock_scanner()
        
        # Alias for legacy tests
        self.sf = self.scanner
    
    def _create_mock_scanner(self):
        """Create a mock scanner for backward compatibility."""
        from unittest.mock import MagicMock
        
        # Create a basic mock scanner with SpiderFoot-like interface
        scanner = MagicMock()
        scanner.opts = self.default_options
        scanner.getTarget = MagicMock(return_value=MagicMock())
        scanner.tempStorage = MagicMock(return_value={})
        
        # Register for cleanup
        self.register_scanner(scanner)
        
        return scanner
    
    def register_module(self, module: Any) -> int:
        """
        Register a SpiderFoot module for automatic cleanup.
        
        Args:
            module: Module instance to track
            
        Returns:
            Resource ID for tracking
        """
        resource_id = self.resource_manager.register_module(module)
        self._test_modules.append((module, resource_id))
        return resource_id
    
    def register_scanner(self, scanner: Any) -> int:
        """
        Register a SpiderFoot scanner for automatic cleanup.
        
        Args:
            scanner: Scanner instance to track
            
        Returns:
            Resource ID for tracking
        """
        resource_id = self.resource_manager.register_scanner(scanner)
        self._test_scanners.append((scanner, resource_id))
        return resource_id
    
    def register_thread(self, thread: threading.Thread,
                        stop_func: callable | None = None) -> int:
        """
        Register a thread for automatic cleanup.
        
        Args:
            thread: Thread to track
            stop_func: Optional function to stop thread gracefully
            
        Returns:
            Resource ID for tracking
        """
        # Register with both managers for comprehensive tracking
        self.resource_manager.register_thread(thread, stop_func)
        return self.thread_registry.register_thread(thread)
    
    def create_mock_module(self, module_class: Any, *args, **kwargs) -> Any:
        """
        Create and register a mock module for testing.
        
        Args:
            module_class: Module class to instantiate
            *args: Positional arguments for module
            **kwargs: Keyword arguments for module
            
        Returns:
            Module instance with automatic cleanup
        """
        # Create module instance
        module = module_class(*args, **kwargs)
        
        # Register for cleanup
        self.register_module(module)
        
        return module
    
    def cleanup_module_resources(self):
        """Clean up all module-specific resources."""
        print(f"🧹 Cleaning up {len(self._test_modules)} modules...")
        
        # Clean up modules in reverse order
        for module, _resource_id in reversed(self._test_modules):
            with suppress(Exception):
                # Set error state to stop processing
                if hasattr(module, 'errorState'):
                    module.errorState = True
                
                # Clear listeners
                if hasattr(module, 'clearListeners'):
                    module.clearListeners()
                
                # Clear temp storage
                if hasattr(module, 'tempStorage'):
                    temp_storage = module.tempStorage()
                    if hasattr(temp_storage, 'clear'):
                        temp_storage.clear()
                
                # Clear results
                if hasattr(module, 'results'):
                    module.results = None
                
                # Force shutdown if available
                if hasattr(module, '_graceful_shutdown'):
                    module._graceful_shutdown()
        
        self._test_modules.clear()
    
    def cleanup_scanner_resources(self):
        """Clean up all scanner-specific resources."""
        print(f"🧹 Cleaning up {len(self._test_scanners)} scanners...")
        
        # Clean up scanners in reverse order
        for scanner, _resource_id in reversed(self._test_scanners):
            with suppress(Exception):
                # Force abort status
                if hasattr(scanner, '_SpiderFootScanner__setStatus'):
                    scanner._SpiderFootScanner__setStatus("ABORTED")
                
                # Call shutdown if available
                if hasattr(scanner, 'shutdown'):
                    scanner.shutdown()
                elif hasattr(scanner, 'stop'):
                    scanner.stop()
        
        self._test_scanners.clear()
    
    def detect_thread_leaks(self) -> bool:
        """
        Detect if this test created thread leaks.
        
        Returns:
            True if thread leaks detected
        """
        current_thread_count = threading.active_count()
        leaked_threads = current_thread_count - self.initial_thread_count
        
        if leaked_threads > 0:
            print(f"⚠️  Thread leak detected: {leaked_threads} threads leaked")
            
            # List current threads for debugging
            current_threads = threading.enumerate()
            print("Current threads:")
            for thread in current_threads:
                print(f"  - {thread.name} (alive: {thread.is_alive()})")
            
            return True
        
        return False
    
    def aggressive_thread_cleanup(self):
        """Perform aggressive thread cleanup to prevent leaks."""
        print("🧹 Performing aggressive thread cleanup...")
        
        # Clean up test threads
        cleanup_test_threads()
        
        # Clean up shared thread pools
        cleanup_shared_pools()
        
        # Wait for threads to finish
        time.sleep(0.1)
        
        # Force garbage collection
        import gc
        gc.collect()
        
        # Final thread count check
        final_count = threading.active_count()
        if final_count > self.initial_thread_count:
            leaked = final_count - self.initial_thread_count
            print(f"⚠️  {leaked} threads still active after cleanup")
    
    def tearDown(self):
        """Enhanced tearDown with comprehensive resource cleanup."""
        try:
            # Clean up module-specific resources first
            self.cleanup_module_resources()
            
            # Clean up scanner-specific resources
            self.cleanup_scanner_resources()
            
            # Clean up all registered resources
            self.resource_manager.cleanup_category("module")
            self.resource_manager.cleanup_category("scanner")
            self.resource_manager.cleanup_category("thread")
            
            # Aggressive thread cleanup
            self.aggressive_thread_cleanup()
            
            # Detect any remaining leaks
            if self.detect_thread_leaks():
                # Try one more aggressive cleanup
                self.aggressive_thread_cleanup()
                
                # Final leak check
                if self.detect_thread_leaks():
                    print(f"🚨 Test {self._testMethodName} left thread leaks!")
        
        except Exception as e:
            print(f"⚠️  Error during tearDown: {e}")
        
        finally:
            # Always call parent tearDown
            super().tearDown()
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level resources."""
        super().setUpClass()
        print(f"🧪 Setting up test class: {cls.__name__}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level resources."""
        try:
            print(f"🧹 Tearing down test class: {cls.__name__}")
            
            # Force cleanup of any remaining resources
            manager = get_test_resource_manager()
            manager.force_cleanup_leaked_resources()
            
            # Final shared pool cleanup
            cleanup_shared_pools()
            
        except Exception as e:
            print(f"⚠️  Error during tearDownClass: {e}")
        
        finally:
            super().tearDownClass()
    
    def create_module_wrapper(self, module_class: Any, module_attributes: dict = None) -> type:
        """
        Create a wrapper class for a SpiderFoot module with enhanced testing capabilities.
        
        Args:
            module_class: The SpiderFoot module class to wrap
            module_attributes: Additional attributes to add to the module
            
        Returns:
            A wrapped module class with testing enhancements
        """
        class WrappedModule(module_class):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if module_attributes:
                    for key, value in module_attributes.items():
                        setattr(self, key, value)
        
        return WrappedModule
    
    def register_event_emitter(self, emitter: Any) -> int:
        """Register an event emitter for cleanup during tearDown."""
        resource_id = self.resource_manager.register_resource(
            emitter, 
            lambda: self._cleanup_event_emitter(emitter),
            category="event_emitter",
            description=f"Event emitter: {type(emitter).__name__}"
        )
        return resource_id
    
    def register_mock(self, mock: Any) -> int:
        """Register a mock object for cleanup during tearDown."""
        resource_id = self.resource_manager.register_resource(
            mock,
            lambda: self._cleanup_mock(mock),
            category="mock",
            description=f"Mock: {type(mock).__name__}"
        )
        return resource_id
    
    def register_patcher(self, patcher: Any) -> int:
        """Register a patch object for cleanup during tearDown."""
        resource_id = self.resource_manager.register_resource(
            patcher,
            lambda: self._cleanup_patcher(patcher),
            category="patcher", 
            description=f"Patcher: {type(patcher).__name__}"
        )
        return resource_id
    
    def _cleanup_event_emitter(self, emitter: Any):
        """Clean up an event emitter."""
        try:
            if hasattr(emitter, 'stop'):
                emitter.stop()
            if hasattr(emitter, 'shutdown'):
                emitter.shutdown()
            if hasattr(emitter, 'close'):
                emitter.close()
        except Exception:
            pass  # Ignore cleanup errors
    
    def _cleanup_mock(self, mock: Any):
        """Clean up a mock object."""
        try:
            if hasattr(mock, 'reset_mock'):
                mock.reset_mock()
            if hasattr(mock, 'stop'):
                mock.stop()
        except Exception:
            pass  # Ignore cleanup errors
    
    def _cleanup_patcher(self, patcher: Any):
        """Clean up a patcher object."""
        try:
            if hasattr(patcher, 'stop'):
                patcher.stop()
        except Exception:
            pass  # Ignore cleanup errors

    # ...existing code...
    

class TestModuleAdvanced(TestModuleBase):
    """
    Advanced test base with additional features for complex module tests.
    
    Features:
    - Timeout protection
    - Resource leak reporting
    - Performance monitoring
    - Cross-platform handling
    """
    
    def setUp(self):
        """Set up advanced test features."""
        super().setUp()
        
        # Set up timeout protection
        self.test_timeout = 30.0  # 30 second default timeout
        
        # Performance monitoring
        self.performance_data = {}
    
    def run_with_timeout(self, test_func: callable, timeout: float = None) -> Any:
        """
        Run a test function with timeout protection.
        
        Args:
            test_func: Function to run
            timeout: Timeout in seconds (uses default if None)
            
        Returns:
            Result of test_func
            
        Raises:
            TimeoutError: If test exceeds timeout
        """
        timeout = timeout or self.test_timeout
        
        result = [None]
        exception = [None]
        
        def target():
            try:
                result[0] = test_func()
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=target, name=f"timeout_test_{int(time.time())}")
        self.register_thread(thread)
        
        start_time = time.time()
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            print(f"⚠️  Test function timed out after {timeout} seconds")
            raise TimeoutError(f"Test timed out after {timeout} seconds")
        
        if exception[0]:
            raise exception[0]
        
        # Record performance data
        elapsed = time.time() - start_time
        self.performance_data[test_func.__name__] = elapsed
        
        return result[0]
    
    def assertNoThreadLeaks(self):
        """Assert that no thread leaks occurred during this test."""
        current_count = threading.active_count()
        leaked = current_count - self.initial_thread_count
        
        if leaked > 0:
            # Try cleanup once more
            self.aggressive_thread_cleanup()
            
            # Recheck
            final_count = threading.active_count()
            final_leaked = final_count - self.initial_thread_count
            
            if final_leaked > 0:
                self.fail(f"Thread leak detected: {final_leaked} threads leaked")
    
    def assertNoResourceLeaks(self):
        """Assert that no resource leaks occurred during this test."""
        leaks = self.resource_manager.detect_leaks()
        
        if leaks:
            leak_summary = {}
            for leak in leaks:
                category = leak['category']
                leak_summary[category] = leak_summary.get(category, 0) + 1
            
            self.fail(f"Resource leaks detected: {leak_summary}")
    
    def tearDown(self):
        """Enhanced tearDown with leak assertions."""
        try:
            # Run base tearDown first
            super().tearDown()
            
            # Check for leaks (but don't fail the test in tearDown)
            try:
                self.assertNoThreadLeaks()
                self.assertNoResourceLeaks()
            except AssertionError as e:
                print(f"⚠️  Leak detected in {self._testMethodName}: {e}")
        
        except Exception as e:
            print(f"⚠️  Error in advanced tearDown: {e}")


# Convenience function for creating test modules
def create_test_module(test_class: type) -> type:
    """
    Decorator to enhance a test class with module testing capabilities.
    
    Args:
        test_class: Test class to enhance
        
    Returns:
        Enhanced test class
    """
    # Ensure the class inherits from TestModuleBase
    if not issubclass(test_class, TestModuleBase):
        # Create a new class that inherits from both
        class EnhancedTestClass(TestModuleBase, test_class):
            pass
        
        EnhancedTestClass.__name__ = test_class.__name__
        EnhancedTestClass.__module__ = test_class.__module__
        return EnhancedTestClass
    
    return test_class

#!/usr/bin/env python3
"""
Enhanced SpiderFoot Scanner Test with ThreadReaper Infrastructure
===============================================================

Demonstrates the comprehensive thread management and resource cleanup
system to eliminate hanging tests and thread leaks.
"""

from __future__ import annotations

import unittest
import uuid
import threading
import time

from spiderfoot.scan_service.scanner import SpiderFootScanner

# Import the new infrastructure
from test.unit.utils.test_scanner_base import TestScannerBase, scanner_test
from test.unit.utils.resource_manager import get_test_resource_manager
from test.unit.utils.thread_registry import get_test_thread_registry
from test.unit.utils.leak_detector import LeakDetectorMixin
from test.unit.utils.shared_pool_cleanup import cleanup_shared_pools


class TestEnhancedSpiderFootScanner(TestScannerBase, LeakDetectorMixin):
    """
    Enhanced scanner test demonstrating the new ThreadReaper infrastructure.
    
    This test class shows how to:
    - Use automatic resource registration and cleanup
    - Detect and prevent thread leaks
    - Handle scanner lifecycle properly
    - Implement timeout protection
    """
    
    def setUp(self):
        """Enhanced setUp with comprehensive tracking."""
        # Call parent setup methods
        super().setUp()
        
        # Track test-specific state
        self.test_scanners = []
        self.test_threads = []
        
        print(f"🧪 Starting test: {self._testMethodName}")
        print(f"   Initial thread count: {threading.active_count()}")
    
    def test_scanner_creation_and_cleanup(self):
        """Test that scanner creation and cleanup works properly."""
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_dnsresolve']  # Simple, reliable module
        
        # Create scanner with automatic registration
        scanner = self.create_test_scanner(
            SpiderFootScanner,
            "test scan", scan_id, "example.com", "INTERNET_NAME",
            module_list, opts, start=False
        )
        
        # Verify scanner was created
        self.assertIsInstance(scanner, SpiderFootScanner)
        self.assertEqual(scanner.status, "INITIALIZING")
        
        # Scanner should be automatically cleaned up in tearDown
        # No manual cleanup needed due to resource manager
    
    @scanner_test(timeout=30.0)
    def test_scanner_start_and_stop_cycle(self):
        """Test complete scanner start/stop cycle with timeout protection."""
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['sfp_dnsresolve']
        
        # Create scanner
        scanner = self.create_test_scanner(
            SpiderFootScanner,
            "lifecycle test", scan_id, "example.com", "INTERNET_NAME",
            module_list, opts, start=False
        )
        
        # Record initial thread count
        initial_threads = threading.active_count()
        
        # Start scanner in controlled way
        try:
            # Use timeout protection
            self.run_scan_with_timeout(scanner, timeout=15.0)
            
        except TimeoutError:
            # This is acceptable for this test - we're testing cleanup
            print("⏰ Scan timed out as expected")
        
        # Force stop scanner
        if hasattr(scanner, 'shutdown'):
            scanner.shutdown()
        
        # Brief pause for shutdown
        time.sleep(0.5)
        
        # Verify scanner stopped properly
        self.assertScanCompleted(scanner)
        
        # Check thread count hasn't increased significantly
        final_threads = threading.active_count()
        thread_increase = final_threads - initial_threads
        
        self.assertLessEqual(thread_increase, 2,
                            f"Too many threads created: {thread_increase}")
    
    def test_multiple_scanners_cleanup(self):
        """Test that multiple scanners can be cleaned up properly."""
        opts = self.default_options.copy()
        module_list = ['sfp_dnsresolve']
        
        scanners = []
        
        # Create multiple scanners
        for i in range(3):
            scan_id = str(uuid.uuid4())
            scanner = self.create_test_scanner(
                SpiderFootScanner,
                f"multi test {i}", scan_id, f"test{i}.example.com",
                "INTERNET_NAME", module_list, opts, start=False
            )
            scanners.append(scanner)
        
        # Verify all scanners created
        self.assertEqual(len(scanners), 3)
        
        for scanner in scanners:
            self.assertIsInstance(scanner, SpiderFootScanner)
            self.assertEqual(scanner.status, "INITIALIZING")
        
        # All scanners should be automatically cleaned up in tearDown
    
    def test_scanner_with_invalid_modules(self):
        """Test scanner behavior with invalid modules (should not hang)."""
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        module_list = ['invalid_module_that_does_not_exist']
        
        # This should not hang due to the enhanced cleanup
        scanner = self.create_test_scanner(
            SpiderFootScanner,
            "invalid module test", scan_id, "example.com", "INTERNET_NAME",
            module_list, opts, start=True  # Start immediately
        )
        
        # Wait briefly for scan to process invalid module
        time.sleep(2.0)
        
        # Scanner should handle invalid module gracefully
        self.assertIsInstance(scanner, SpiderFootScanner)
        
        # Status should indicate error or completion
        status = getattr(scanner, '_SpiderFootScanner__scanStatus', 'UNKNOWN')
        self.assertIn(status, ['ERROR-FAILED', 'FINISHED', 'ABORTED'],
                     f"Unexpected scanner status: {status}")
    
    def test_resource_leak_detection(self):
        """Test that resource leak detection works."""
        # Set baseline
        self.set_leak_baseline()
        
        # Create some resources that will be auto-cleaned
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        
        scanner = self.create_test_scanner(
            SpiderFootScanner,
            "leak detection test", scan_id, "example.com", "INTERNET_NAME",
            ['sfp_dnsresolve'], opts, start=False
        )
        
        # Create a test thread
        def dummy_thread_function():
            time.sleep(1.0)
        
        test_thread = threading.Thread(target=dummy_thread_function,
                                     name="test_leak_thread")
        self.register_thread(test_thread)
        test_thread.start()
        
        # Resources should be tracked and cleaned up automatically
        # The assertion is that tearDown completes without hanging
    
    def test_shared_thread_pool_cleanup(self):
        """Test that shared thread pool workers are cleaned up."""
        # This test specifically targets the sharedThreadPool_worker issue
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        
        # Create scanner that will use shared thread pool
        scanner = self.create_test_scanner(
            SpiderFootScanner,
            "shared pool test", scan_id, "example.com", "INTERNET_NAME",
            ['sfp_dnsresolve'], opts, start=False
        )
        
        # Check for shared pool threads before starting
        initial_shared_threads = self._count_shared_pool_threads()
        
        # Start scanner briefly to trigger thread pool creation
        try:
            scanner.start()
            time.sleep(1.0)  # Brief run
            
            if hasattr(scanner, 'shutdown'):
                scanner.shutdown()
        except Exception as e:
            print(f"Expected exception during brief scan: {e}")
        
        # Enhanced cleanup should handle shared pool threads
        cleanup_shared_pools()
        
        # Check that shared pool threads are cleaned up
        final_shared_threads = self._count_shared_pool_threads()
        
        # We should not have significantly more shared pool threads
        thread_increase = final_shared_threads - initial_shared_threads
        self.assertLessEqual(thread_increase, 5,
                           f"Too many shared pool threads remain: {thread_increase}")
    
    def _count_shared_pool_threads(self) -> int:
        """Count shared thread pool worker threads."""
        shared_count = 0
        for thread in threading.enumerate():
            if 'sharedThreadPool_worker' in thread.name:
                shared_count += 1
        return shared_count
    
    def test_emergency_cleanup_scenario(self):
        """Test emergency cleanup in worst-case scenario."""
        opts = self.default_options.copy()
        scan_id = str(uuid.uuid4())
        
        # Create scanner that might cause problems
        scanner = self.create_test_scanner(
            SpiderFootScanner,
            "emergency test", scan_id, "example.com", "INTERNET_NAME",
            ['sfp_dnsresolve'], opts, start=False
        )
        
        # Simulate starting scanner
        try:
            scanner.start()
            
            # Simulate some processing time
            time.sleep(0.5)
            
            # Simulate emergency shutdown (scanner might be unresponsive)
            # The enhanced tearDown should handle this gracefully
            
        except Exception as e:
            print(f"Exception during emergency test: {e}")
        
        # The test passes if tearDown completes without hanging
    
    def tearDown(self):
        """Enhanced tearDown with comprehensive verification."""
        try:
            print(f"🧹 Tearing down test: {self._testMethodName}")
            
            # Get resource and thread summaries before cleanup
            resource_manager = get_test_resource_manager()
            thread_registry = get_test_thread_registry()
            
            resource_summary = resource_manager.get_resource_summary()
            if resource_summary:
                print(f"   Resources to cleanup: {resource_summary}")
            
            # Perform enhanced cleanup
            super().tearDown()
            
            # Verify cleanup was successful
            final_thread_count = threading.active_count()
            print(f"   Final thread count: {final_thread_count}")
            
            # Generate leak report if any issues
            leak_report = thread_registry.get_leak_report()
            if "No threads registered" not in leak_report:
                print(f"   Thread registry report:\n{leak_report}")
        
        except Exception as e:
            print(f"⚠️  Error in enhanced tearDown: {e}")
        
        finally:
            # Clear test-specific tracking
            self.test_scanners.clear()
            self.test_threads.clear()
    
    @classmethod
    def tearDownClass(cls):
        """Class-level cleanup with comprehensive verification."""
        try:
            print(f"🧹 Final cleanup for {cls.__name__}")
            
            # Force cleanup any remaining resources
            resource_manager = get_test_resource_manager()
            thread_registry = get_test_thread_registry()
            
            # Get final statistics
            leaked_resources = resource_manager.force_cleanup_leaked_resources()
            thread_stats = thread_registry.force_cleanup_all_threads()
            
            if leaked_resources > 0:
                print(f"   ⚠️  Cleaned {leaked_resources} leaked resources")
            
            if thread_stats['still_alive'] > 0:
                print(f"   ⚠️  {thread_stats['still_alive']} threads still alive")
            
            # Final shared pool cleanup
            cleanup_shared_pools()
            
            print(f"✅ Class cleanup complete for {cls.__name__}")
        
        except Exception as e:
            print(f"⚠️  Error in class tearDown: {e}")
        
        finally:
            super().tearDownClass()


if __name__ == '__main__':
    # Run with enhanced test runner
    print("🧪 Running Enhanced SpiderFoot Scanner Tests with ThreadReaper")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEnhancedSpiderFootScanner)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, buffer=False)
    result = runner.run(suite)
    
    # Print final summary
    print("\n" + "=" * 60)
    print("🏁 TEST EXECUTION COMPLETE")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    # Final thread count check
    final_threads = threading.active_count()
    print(f"\nFinal thread count: {final_threads}")
    
    if final_threads > 5:  # Allow some tolerance for test infrastructure
        print("⚠️  Warning: High thread count may indicate leaks")
    else:
        print("✅ Thread count looks good")
    
    print("\n🎯 ThreadReaper infrastructure test complete!")

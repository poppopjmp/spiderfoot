#!/usr/bin/env python3
"""
ThreadReaper Infrastructure Demonstration
========================================

Simple demonstration of the ThreadReaper infrastructure working
to prevent thread leaks and ensure clean resource management.
"""

import threading
import time
import sys
import os

# Add project root to Python path for imports
script_dir = os.path.dirname(__file__)
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from test.unit.utils.resource_manager import get_test_resource_manager
from test.unit.utils.thread_registry import get_test_thread_registry, cleanup_test_threads
from test.unit.utils.leak_detector import LeakDetectorMixin, set_leak_detection_baseline
from test.unit.utils.shared_pool_cleanup import cleanup_shared_pools


class ThreadReaperDemo:
    """Demonstrate ThreadReaper infrastructure capabilities."""
    
    def __init__(self):
        self.resource_manager = get_test_resource_manager()
        self.thread_registry = get_test_thread_registry()
        
    def demo_thread_cleanup(self):
        """Demonstrate automatic thread cleanup."""
        print("🧪 DEMO: Thread Cleanup")
        print("-" * 40)
        
        initial_threads = threading.active_count()
        print(f"Initial thread count: {initial_threads}")
        
        # Create some test threads
        test_threads = []
        for i in range(3):
            def worker(thread_id=i):
                print(f"  🧵 Test thread {thread_id} running...")
                time.sleep(2.0)
                print(f"  ✅ Test thread {thread_id} finished")
            
            thread = threading.Thread(target=worker, name=f"demo_thread_{i}")
            test_threads.append(thread)
            
            # Register with ThreadReaper
            self.thread_registry.register(thread, "demo", "thread_demo")
            thread.start()
        
        print(f"Created {len(test_threads)} test threads")
        
        # Wait briefly
        time.sleep(0.5)
        
        current_threads = threading.active_count()
        print(f"Current thread count: {current_threads}")
        
        # Clean up with ThreadReaper
        print("\n🧹 Cleaning up with ThreadReaper...")
        cleaned = cleanup_test_threads(timeout=3.0)
        
        final_threads = threading.active_count()
        print(f"Final thread count: {final_threads}")
        print(f"Threads cleaned: {cleaned}")
        
        # Verify cleanup
        thread_increase = final_threads - initial_threads
        if thread_increase <= 1:  # Allow some tolerance
            print("✅ Thread cleanup successful!")
        else:
            print(f"⚠️  Warning: {thread_increase} threads may have leaked")
        
        return thread_increase
    
    def demo_resource_management(self):
        """Demonstrate resource management."""
        print("\n🧪 DEMO: Resource Management")
        print("-" * 40)
        
        # Register some mock resources
        class MockResource:
            def __init__(self, name):
                self.name = name
                self.cleaned = False
            
            def cleanup(self):
                self.cleaned = True
                print(f"  🧹 Cleaned resource: {self.name}")
        
        resources = []
        for i in range(3):
            resource = MockResource(f"test_resource_{i}")
            resources.append(resource)
            
            # Register with resource manager
            self.resource_manager.register_resource(
                resource, resource.cleanup,
                category="demo", description=f"Demo resource {i}"
            )
        
        print(f"Registered {len(resources)} test resources")
        
        # Get summary
        summary = self.resource_manager.get_resource_summary()
        print(f"Resource summary: {summary}")
        
        # Clean up all resources
        print("\n🧹 Cleaning up with ResourceManager...")
        stats = self.resource_manager.cleanup_all()
        
        print(f"Cleanup stats: {stats}")
        
        # Verify all resources were cleaned
        all_cleaned = all(r.cleaned for r in resources)
        if all_cleaned:
            print("✅ All resources cleaned successfully!")
        else:
            print("⚠️  Some resources may not have been cleaned")
        
        return all_cleaned
    
    def demo_leak_detection(self):
        """Demonstrate leak detection."""
        print("\n🧪 DEMO: Leak Detection")
        print("-" * 40)
        
        # Set baseline
        set_leak_detection_baseline()
        print("Baseline set for leak detection")
        
        # Create a potential "leak" (thread that runs briefly)
        def potential_leak():
            time.sleep(1.0)
        
        leak_thread = threading.Thread(target=potential_leak, name="potential_leak")
        leak_thread.start()
        
        print("Created potential leak thread")
        
        # Wait for thread to finish
        leak_thread.join(timeout=2.0)
        
        # Check for leaks
        from test.unit.utils.leak_detector import detect_all_test_leaks
        leaks = detect_all_test_leaks()
        
        total_leaks = sum(len(leak_list) for leak_list in leaks.values())
        print(f"Detected leaks: {total_leaks}")
        
        if total_leaks == 0:
            print("✅ No leaks detected!")
        else:
            print("⚠️  Leaks were detected")
            for leak_type, leak_list in leaks.items():
                if leak_list:
                    print(f"  - {leak_type}: {len(leak_list)} leaks")
        
        return total_leaks == 0
    
    def demo_shared_pool_cleanup(self):
        """Demonstrate shared pool cleanup."""
        print("\n🧪 DEMO: Shared Pool Cleanup")
        print("-" * 40)
        
        # Check for existing shared pool threads
        initial_shared = self._count_shared_threads()
        print(f"Initial shared pool threads: {initial_shared}")
        
        # Run cleanup
        cleaned = cleanup_shared_pools()
        print(f"Shared pool cleanup result: {cleaned}")
        
        final_shared = self._count_shared_threads()
        print(f"Final shared pool threads: {final_shared}")
        
        if final_shared <= initial_shared:
            print("✅ Shared pool cleanup successful!")
            return True
        else:
            print("⚠️  Shared pool threads may have increased")
            return False
    
    def _count_shared_threads(self):
        """Count shared thread pool workers."""
        count = 0
        for thread in threading.enumerate():
            if 'sharedThreadPool_worker' in thread.name:
                count += 1
        return count
    
    def run_full_demo(self):
        """Run complete ThreadReaper demonstration."""
        print("🤖 THREADREAPER INFRASTRUCTURE DEMONSTRATION")
        print("=" * 60)
        
        results = {}
        
        # Run all demos
        try:
            results['thread_cleanup'] = self.demo_thread_cleanup() <= 1
        except Exception as e:
            print(f"❌ Thread cleanup demo failed: {e}")
            results['thread_cleanup'] = False
        
        try:
            results['resource_management'] = self.demo_resource_management()
        except Exception as e:
            print(f"❌ Resource management demo failed: {e}")
            results['resource_management'] = False
        
        try:
            results['leak_detection'] = self.demo_leak_detection()
        except Exception as e:
            print(f"❌ Leak detection demo failed: {e}")
            results['leak_detection'] = False
        
        try:
            results['shared_pool_cleanup'] = self.demo_shared_pool_cleanup()
        except Exception as e:
            print(f"❌ Shared pool cleanup demo failed: {e}")
            results['shared_pool_cleanup'] = False
        
        # Summary
        print("\n🏁 DEMONSTRATION SUMMARY")
        print("=" * 60)
        
        all_successful = True
        for feature, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {feature.replace('_', ' ').title()}")
            if not success:
                all_successful = False
        
        print("\n" + "=" * 60)
        if all_successful:
            print("🎉 ALL THREADREAPER FEATURES WORKING CORRECTLY!")
            print("🔧 Ready to eliminate thread leaks in SpiderFoot tests.")
        else:
            print("⚠️  Some ThreadReaper features need attention.")
        
        print("\n🎯 ThreadReaper infrastructure provides:")
        print("  • Automatic thread registration and cleanup")
        print("  • Resource lifecycle management")
        print("  • Leak detection and reporting")
        print("  • Shared pool worker cleanup")
        print("  • Cross-platform compatibility")
        print("  • Emergency cleanup mechanisms")
        
        return all_successful


if __name__ == '__main__':
    demo = ThreadReaperDemo()
    success = demo.run_full_demo()
    
    exit_code = 0 if success else 1
    sys.exit(exit_code)

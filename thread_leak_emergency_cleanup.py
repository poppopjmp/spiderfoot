#!/usr/bin/env python3
"""
Thread Leak Detection and Emergency Cleanup
===========================================

This script provides aggressive thread cleanup to prevent test hanging
due to lingering threads that don't respond to normal cleanup methods.
"""

import subprocess
import sys
import threading
import time
import signal
import os
import gc
from pathlib import Path
from contextlib import suppress


class AggressiveThreadCleaner:
    """Provides aggressive thread cleanup methods for test environments."""
    
    @staticmethod
    def force_cleanup_all_threads(timeout=5.0):
        """
        Aggressively clean up all threads except main thread.
        
        WARNING: This is a nuclear option that should only be used
        when normal cleanup methods fail.
        """
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        
        print(f"🧹 Starting aggressive thread cleanup (timeout: {timeout}s)")
        
        # Get all threads except main and current
        all_threads = threading.enumerate()
        cleanup_threads = [t for t in all_threads 
                          if t not in (main_thread, current_thread) and t.is_alive()]
        
        if not cleanup_threads:
            print("✅ No threads to clean up")
            return 0
            
        print(f"🔍 Found {len(cleanup_threads)} threads to clean up:")
        for i, thread in enumerate(cleanup_threads):
            thread_info = AggressiveThreadCleaner.get_thread_info(thread)
            print(f"  {i+1}. {thread_info}")
        
        # Step 1: Try graceful shutdown
        print("🤝 Attempting graceful shutdown...")
        AggressiveThreadCleaner._attempt_graceful_shutdown(cleanup_threads)
        
        # Step 2: Wait briefly for graceful shutdown
        time.sleep(0.5)
        
        # Step 3: Force join with timeout
        print("⏰ Force joining threads with timeout...")
        AggressiveThreadCleaner._force_join_threads(cleanup_threads, timeout)
        
        # Step 4: Check what's still alive
        still_alive = [t for t in cleanup_threads if t.is_alive()]
        if still_alive:
            print(f"⚠️  {len(still_alive)} threads still alive after cleanup:")
            for thread in still_alive:
                print(f"    - {AggressiveThreadCleaner.get_thread_info(thread)}")
        else:
            print("✅ All threads cleaned up successfully")
        
        # Step 5: Force garbage collection
        gc.collect()
        
        return len(still_alive)
    
    @staticmethod
    def _attempt_graceful_shutdown(threads):
        """Attempt graceful shutdown of threads."""
        for thread in threads:
            with suppress(Exception):
                # Try common shutdown methods
                if hasattr(thread, 'stop'):
                    thread.stop()
                elif hasattr(thread, 'shutdown'):
                    thread.shutdown()
                elif hasattr(thread, 'close'):
                    thread.close()
                elif hasattr(thread, '_stop'):
                    thread._stop()
    
    @staticmethod
    def _force_join_threads(threads, timeout):
        """Force join threads with timeout."""
        start_time = time.time()
        
        for thread in threads:
            if not thread.is_alive():
                continue
                
            remaining_timeout = max(0.1, timeout - (time.time() - start_time))
            
            with suppress(RuntimeError, OSError):
                thread.join(timeout=remaining_timeout)
            
            if time.time() - start_time >= timeout:
                print(f"⏰ Global timeout reached, stopping cleanup")
                break
    
    @staticmethod
    def get_thread_info(thread):
        """Get detailed information about a thread."""
        if not thread:
            return "None"
            
        name = getattr(thread, 'name', 'unnamed')
        ident = getattr(thread, 'ident', 'no-id')
        daemon = getattr(thread, 'daemon', False)
        alive = thread.is_alive()
        target = getattr(thread, '_target', None)
        target_name = target.__name__ if target and hasattr(target, '__name__') else str(target)
        
        return f"{name} (id:{ident}, daemon:{daemon}, alive:{alive}, target:{target_name})"
    
    @staticmethod
    def emergency_process_termination():
        """
        Emergency process termination as last resort.
        
        WARNING: This will terminate the entire process!
        """
        print("🚨 EMERGENCY: Performing process termination due to hanging threads")
        print("This is a last resort to prevent infinite hanging")
        
        # Give a brief moment for any cleanup
        time.sleep(0.1)
        
        # Force exit
        os._exit(1)


def enhanced_test_cleanup():
    """Enhanced cleanup for test teardown methods."""
    print("🧹 Starting enhanced test cleanup...")
    
    # Step 1: Standard cleanup
    remaining = AggressiveThreadCleaner.force_cleanup_all_threads(timeout=2.0)
    
    # Step 2: If threads remain, set up emergency termination
    if remaining > 0:
        print(f"🚨 {remaining} threads still alive after aggressive cleanup")
        print("Setting up emergency termination in 10 seconds...")
        
        def emergency_timeout():
            time.sleep(10)
            print("💀 Emergency timeout reached - forcefully terminating process")
            AggressiveThreadCleaner.emergency_process_termination()
        
        # Start emergency timeout thread
        emergency_thread = threading.Thread(target=emergency_timeout, daemon=True)
        emergency_thread.start()
    
    return remaining


def test_scanner_with_emergency_termination():
    """Test the problematic scanner test with emergency termination."""
    print("🔍 Testing scanner with emergency termination protection...")
    
    # Set up emergency timeout for the entire test
    def emergency_exit():
        time.sleep(90)  # 90 seconds max
        print("🚨 EMERGENCY: Test has been running for 90s - forcefully terminating")
        os._exit(1)
    
    emergency_thread = threading.Thread(target=emergency_exit, daemon=True)
    emergency_thread.start()
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest',
            'test/unit/test_spiderfootscanner.py::TestSpiderFootScanner::test_init_argument_start_true_with_no_valid_modules_should_set_scanstatus_to_failed',
            '-v', '--tb=short'
        ], capture_output=True, text=True, timeout=60, cwd=Path.cwd())
        
        print(f"✅ Test completed with return code: {result.returncode}")
        if result.stdout:
            print("📄 Output:")
            print(result.stdout[-500:])  # Last 500 chars
        if result.stderr:
            print("⚠️  Errors:")
            print(result.stderr[-500:])  # Last 500 chars
            
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("⏰ Test timed out - this confirms thread hanging issues")
        return False
    except Exception as e:
        print(f"💥 Error running test: {e}")
        return False


def main():
    """Main execution."""
    print("🚨 AGGRESSIVE THREAD CLEANUP AND HANGING PREVENTION")
    print("="*60)
    
    # Test 1: Check current thread status
    print("📊 Current thread status:")
    all_threads = threading.enumerate()
    print(f"  Total threads: {len(all_threads)}")
    for i, thread in enumerate(all_threads):
        print(f"  {i+1}. {AggressiveThreadCleaner.get_thread_info(thread)}")
    
    # Test 2: Try the problematic scanner test
    print("\n🧪 Testing problematic scanner test...")
    success = test_scanner_with_emergency_termination()
    
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed or hung - applying aggressive cleanup...")
        enhanced_test_cleanup()
    
    print("\n🏁 Cleanup and test execution completed")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

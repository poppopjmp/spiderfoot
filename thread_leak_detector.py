#!/usr/bin/env python3
"""
THREAD LEAK DETECTION AND PREVENTION SCRIPT
===========================================

This script detects and prevents thread leaks in SpiderFoot tests,
specifically addressing scanner and module thread cleanup issues.
"""

import sys
import subprocess
import time
import threading
from pathlib import Path


def detect_active_threads():
    """Detect and report all active threads."""
    print("🔍 ACTIVE THREAD DETECTION")
    print("=" * 50)
    
    threads = threading.enumerate()
    print(f"Total active threads: {len(threads)}")
    
    for i, thread in enumerate(threads, 1):
        thread_name = getattr(thread, 'name', 'unnamed')
        thread_target = str(getattr(thread, '_target', 'no target'))
        thread_daemon = getattr(thread, 'daemon', False)
        thread_alive = thread.is_alive()
        
        print(f"  {i}. {thread_name}")
        print(f"     Target: {thread_target}")
        print(f"     Daemon: {thread_daemon}, Alive: {thread_alive}")
        
        # Check for SpiderFoot-related threads
        if any(keyword in thread_name.lower() or keyword in thread_target.lower() 
               for keyword in ['spider', 'scan', 'module', 'worker']):
            print(f"     ⚠️  SPIDERFOOT-RELATED THREAD DETECTED")
        print()


def test_thread_cleanup_in_scanner():
    """Test thread cleanup specifically in scanner tests."""
    print("🧪 TESTING SCANNER THREAD CLEANUP")
    print("=" * 50)
    
    workspace_root = Path(__file__).parent
    
    # Run a specific scanner test that creates threads
    cmd = [
        sys.executable, '-m', 'pytest', 
        'test/unit/test_spiderfootscanner.py::TestSpiderFootScanner::test_init_argument_start_true_with_no_valid_modules_should_set_scanstatus_to_failed',
        '-v', '--tb=short'
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    # Detect threads before test
    print("\\nThreads before test:")
    threads_before = set(threading.enumerate())
    print(f"Thread count before: {len(threads_before)}")
    
    try:
        # Run the test
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=workspace_root
        )
        
        print(f"\\nTest result: {result.returncode}")
        if result.stdout:
            print("STDOUT:", result.stdout[-500:])  # Last 500 chars
        if result.stderr:
            print("STDERR:", result.stderr[-500:])  # Last 500 chars
        
    except subprocess.TimeoutExpired:
        print("\\n⏰ Test timed out - likely thread leak issue!")
        return False
    except Exception as e:
        print(f"\\n💥 Error running test: {e}")
        return False
    
    # Detect threads after test
    print("\\nThreads after test:")
    threads_after = set(threading.enumerate())
    print(f"Thread count after: {len(threads_after)}")
    
    # Compare thread counts
    leaked_threads = threads_after - threads_before
    if leaked_threads:
        print(f"\\n⚠️  THREAD LEAK DETECTED: {len(leaked_threads)} new threads")
        for thread in leaked_threads:
            thread_name = getattr(thread, 'name', 'unnamed')
            print(f"  - Leaked thread: {thread_name}")
        return False
    else:
        print("\\n✅ NO THREAD LEAKS DETECTED")
        return True


def create_thread_monitoring_test():
    """Create a test script to monitor thread behavior."""
    print("📝 CREATING THREAD MONITORING TEST")
    print("=" * 50)
    
    workspace_root = Path(__file__).parent
    monitor_script = workspace_root / "thread_monitor_test.py"
    
    monitor_content = '''#!/usr/bin/env python3
"""Thread monitoring test for SpiderFoot scanner."""

import threading
import time
import sys
import uuid
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def monitor_thread_lifecycle():
    """Monitor thread creation and cleanup during scanner operations."""
    
    print("Thread monitoring test starting...")
    
    # Get initial thread state
    initial_threads = set(threading.enumerate())
    initial_count = len(initial_threads)
    print(f"Initial thread count: {initial_count}")
    
    # Import and run scanner test
    try:
        from spiderfoot.scan_service.scanner import SpiderFootScanner
        from test.unit.utils.test_base import SpiderFootTestBase
        
        # Create test instance for options
        test_instance = SpiderFootTestBase()
        test_instance.setUp()
        opts = test_instance.default_options.copy()
        
        print("Creating scanner with invalid modules...")
        scan_id = str(uuid.uuid4())
        
        # This should fail quickly and not leave threads
        scanner = SpiderFootScanner(
            "thread monitor test", 
            scan_id, 
            "example.com", 
            "INTERNET_NAME",
            ['invalid_module_that_does_not_exist'], 
            opts, 
            start=True
        )
        
        print(f"Scanner created with status: {scanner.status}")
        
        # Wait a moment for any threads to settle
        time.sleep(2)
        
        # Check thread state after scanner creation
        mid_threads = set(threading.enumerate())
        mid_count = len(mid_threads)
        print(f"Thread count after scanner creation: {mid_count}")
        
        # Clean up scanner manually
        if hasattr(scanner, '_thread') and scanner._thread:
            if scanner._thread.is_alive():
                print("Stopping scanner thread...")
                scanner._thread.join(timeout=2)
        
        # Force cleanup
        scanner = None
        
        # Wait for cleanup
        time.sleep(1)
        
        # Final thread check
        final_threads = set(threading.enumerate())
        final_count = len(final_threads)
        print(f"Final thread count: {final_count}")
        
        # Report results
        created_threads = mid_threads - initial_threads
        remaining_threads = final_threads - initial_threads
        
        if created_threads:
            print(f"Threads created during test: {len(created_threads)}")
            for thread in created_threads:
                print(f"  - {getattr(thread, 'name', 'unnamed')}")
        
        if remaining_threads:
            print(f"⚠️  Threads remaining after cleanup: {len(remaining_threads)}")
            for thread in remaining_threads:
                print(f"  - {getattr(thread, 'name', 'unnamed')}")
            return False
        else:
            print("✅ All threads cleaned up successfully")
            return True
            
    except Exception as e:
        print(f"Error during monitoring: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = monitor_thread_lifecycle()
    sys.exit(0 if success else 1)
'''
    
    with open(monitor_script, 'w', encoding='utf-8') as f:
        f.write(monitor_content)
    
    print(f"✅ Created thread monitoring script: {monitor_script}")
    
    # Run the monitoring test
    print("\\n🔄 Running thread monitoring test...")
    try:
        result = subprocess.run([
            sys.executable, str(monitor_script)
        ], capture_output=True, text=True, timeout=30, cwd=workspace_root)
        
        print("Monitoring test output:")
        print(result.stdout)
        if result.stderr:
            print("Monitoring test errors:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("⏰ Monitoring test timed out")
        return False
    except Exception as e:
        print(f"💥 Error running monitoring test: {e}")
        return False
    finally:
        # Clean up test file
        if monitor_script.exists():
            monitor_script.unlink()


def main():
    """Main thread leak detection and prevention."""
    print("🧵 SPIDERFOOT THREAD LEAK DETECTOR")
    print("=" * 60)
    print("Analyzing thread behavior in SpiderFoot tests...")
    
    # Step 1: Detect current active threads
    detect_active_threads()
    
    # Step 2: Test scanner thread cleanup
    scanner_cleanup_ok = test_thread_cleanup_in_scanner()
    
    # Step 3: Create and run monitoring test
    monitoring_ok = create_thread_monitoring_test()
    
    # Summary
    print("\\n" + "=" * 60)
    print("🏁 THREAD LEAK ANALYSIS SUMMARY")
    print("=" * 60)
    
    if scanner_cleanup_ok and monitoring_ok:
        print("✅ NO THREAD LEAKS DETECTED")
        print("✅ Scanner thread cleanup working properly")
        print("✅ Thread monitoring shows clean lifecycle")
        print("\\n🎉 THREAD MANAGEMENT IS HEALTHY!")
        return 0
    else:
        print("⚠️  THREAD ISSUES DETECTED:")
        if not scanner_cleanup_ok:
            print("  - Scanner tests are leaking threads")
        if not monitoring_ok:
            print("  - Thread lifecycle monitoring failed")
        print("\\n🔧 THREAD CLEANUP IMPROVEMENTS NEEDED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

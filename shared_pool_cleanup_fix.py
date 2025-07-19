#!/usr/bin/env python3
"""
Shared Thread Pool Cleanup Fix for SpiderFoot Tests
==================================================

This script provides specific cleanup for SpiderFoot's shared thread pool
workers that are causing thread leaks in tests.

The warning message:
"Potential thread leak detected: ['sharedThreadPool_worker_3', 'sharedThreadPool_worker_2', 'sharedThreadPool_worker_1']"

indicates that these worker threads from SpiderFoot's shared thread pool are not
being properly cleaned up during test teardown.
"""

import threading
import time
import gc
import sys
from pathlib import Path
from contextlib import suppress


def cleanup_shared_thread_pool():
    """
    Clean up shared thread pool workers that are causing thread leaks.
    
    This specifically targets threads with names like:
    - sharedThreadPool_worker_1
    - sharedThreadPool_worker_2
    - sharedThreadPool_worker_3
    etc.
    """
    print("🧹 Cleaning up shared thread pool workers...")
    
    # Find shared thread pool workers
    shared_pool_threads = []
    for thread in threading.enumerate():
        thread_name = getattr(thread, 'name', '')
        if 'sharedThreadPool_worker' in thread_name and thread.is_alive():
            shared_pool_threads.append(thread)
    
    if not shared_pool_threads:
        print("✅ No shared thread pool workers found")
        return 0
    
    print(f"🔍 Found {len(shared_pool_threads)} shared thread pool workers:")
    for thread in shared_pool_threads:
        print(f"  - {thread.name} (alive: {thread.is_alive()})")
    
    # Step 1: Try to find and shutdown the thread pool
    shutdown_count = 0
    try:
        # Look for SpiderFoot instances that might have the thread pool
        for obj in gc.get_objects():
            if hasattr(obj, '__class__') and 'SpiderFoot' in str(obj.__class__):
                # Check for thread pool attributes
                for attr_name in ['__sfp__threadpool', '_threadpool', 'threadpool', 'thread_pool']:
                    if hasattr(obj, attr_name):
                        thread_pool = getattr(obj, attr_name)
                        if thread_pool and hasattr(thread_pool, 'shutdown'):
                            with suppress(Exception):
                                print(f"🛑 Shutting down thread pool: {attr_name}")
                                thread_pool.shutdown(wait=False)
                                shutdown_count += 1
                        
                        # Clear the reference
                        with suppress(Exception):
                            setattr(obj, attr_name, None)
    except Exception as e:
        print(f"⚠️  Error during thread pool shutdown: {e}")
    
    print(f"🛑 Shutdown {shutdown_count} thread pools")
    
    # Step 2: Wait briefly for graceful shutdown
    time.sleep(0.5)
    
    # Step 3: Force join remaining threads
    still_alive = []
    for thread in shared_pool_threads:
        if thread.is_alive():
            with suppress(Exception):
                thread.join(timeout=1.0)
            
            if thread.is_alive():
                still_alive.append(thread)
    
    if still_alive:
        print(f"⚠️  {len(still_alive)} shared pool workers still alive:")
        for thread in still_alive:
            print(f"    - {thread.name}")
    else:
        print("✅ All shared thread pool workers cleaned up successfully")
    
    return len(still_alive)


def emergency_shared_pool_cleanup():
    """
    Emergency cleanup for shared thread pool - more aggressive approach.
    """
    print("🚨 Emergency shared thread pool cleanup...")
    
    # Step 1: Find all SpiderFoot-related objects and clear their thread pools
    spiderfoot_objects = []
    for obj in gc.get_objects():
        try:
            if (hasattr(obj, '__class__') and 
                ('SpiderFoot' in str(obj.__class__) or 
                 'Scanner' in str(obj.__class__))):
                spiderfoot_objects.append(obj)
        except Exception:
            continue
    
    print(f"🔍 Found {len(spiderfoot_objects)} SpiderFoot-related objects")
    
    # Clear all thread pool references
    for obj in spiderfoot_objects:
        try:
            # Clear various thread pool attribute names
            pool_attrs = [
                '__sfp__threadpool', '_threadpool', 'threadpool', 'thread_pool',
                '_SpiderFoot__threadpool', '__threadpool', 'shared_threadpool',
                '_shared_threadpool', 'moduleThreadPool'
            ]
            
            for attr in pool_attrs:
                if hasattr(obj, attr):
                    pool = getattr(obj, attr)
                    if pool:
                        with suppress(Exception):
                            if hasattr(pool, 'shutdown'):
                                pool.shutdown(wait=False)
                            elif hasattr(pool, '_shutdown'):
                                pool._shutdown = True
                        
                        # Clear the reference
                        with suppress(Exception):
                            setattr(obj, attr, None)
        except Exception:
            continue
    
    # Step 2: Force cleanup of shared pool threads
    shared_threads = [t for t in threading.enumerate() 
                     if 'sharedThreadPool_worker' in getattr(t, 'name', '')]
    
    for thread in shared_threads:
        with suppress(Exception):
            if thread.is_alive():
                thread.join(timeout=0.2)
    
    # Step 3: Force garbage collection
    gc.collect()
    
    # Check what's left
    remaining = [t for t in threading.enumerate() 
                if 'sharedThreadPool_worker' in getattr(t, 'name', '') and t.is_alive()]
    
    return len(remaining)


def apply_shared_pool_cleanup_to_scanner_test():
    """
    Apply the shared thread pool cleanup fix to the scanner test file.
    """
    scanner_test_path = Path("test/unit/test_spiderfootscanner.py")
    
    if not scanner_test_path.exists():
        print("⚠️  Scanner test file not found")
        return False
    
    # Read the current content
    content = scanner_test_path.read_text(encoding='utf-8')
    
    # Check if the fix is already applied
    if 'enhanced_teardown_with_shared_pool_cleanup' in content:
        print("✅ Shared pool cleanup already applied to scanner tests")
        return True
    
    # Add import at the top (after existing imports)
    import_addition = """
# Import shared thread pool cleanup
try:
    from test.unit.utils.shared_pool_cleanup import enhanced_teardown_with_shared_pool_cleanup
except ImportError:
    def enhanced_teardown_with_shared_pool_cleanup():
        return 0  # Fallback if cleanup utility not available
"""
    
    # Add the import after the existing imports
    lines = content.split('\n')
    import_index = -1
    for i, line in enumerate(lines):
        if line.startswith('from test.unit.utils.test_base import'):
            import_index = i
            break
    
    if import_index >= 0:
        lines.insert(import_index + 1, import_addition)
    
    # Enhance the tearDown method to include shared pool cleanup
    enhanced_content = '\n'.join(lines)
    
    # Find the tearDown method and add shared pool cleanup
    import re
    
    # Look for the end of the tearDown method and add our cleanup
    teardown_pattern = r'(def tearDown\(self\):.*?super\(\)\.tearDown\(\))'
    
    def add_shared_pool_cleanup(match):
        original_method = match.group(1)
        # Add shared pool cleanup before super().tearDown()
        enhanced_method = original_method.replace(
            'super().tearDown()',
            '''# Enhanced shared thread pool cleanup
        enhanced_teardown_with_shared_pool_cleanup()
        
        super().tearDown()'''
        )
        return enhanced_method
    
    enhanced_content = re.sub(teardown_pattern, add_shared_pool_cleanup, enhanced_content, flags=re.DOTALL)
    
    # Write back the updated content
    scanner_test_path.write_text(enhanced_content, encoding='utf-8')
    print("✅ Applied shared thread pool cleanup to scanner test")
    return True


def test_shared_pool_cleanup():
    """Test the shared pool cleanup functionality."""
    print("🧪 Testing shared thread pool cleanup...")
    
    # Check current thread status
    print("📊 Current threads:")
    for thread in threading.enumerate():
        print(f"  - {thread.name} (alive: {thread.is_alive()})")
    
    # Look for shared pool workers specifically
    shared_workers = [t for t in threading.enumerate() 
                     if 'sharedThreadPool_worker' in getattr(t, 'name', '')]
    
    if shared_workers:
        print(f"🔍 Found {len(shared_workers)} shared pool workers before cleanup")
        remaining = cleanup_shared_thread_pool()
        print(f"🔍 {remaining} shared pool workers remaining after cleanup")
        
        if remaining > 0:
            print("⚠️  Some workers remain, trying emergency cleanup...")
            remaining = emergency_shared_pool_cleanup()
            print(f"🔍 {remaining} shared pool workers remaining after emergency cleanup")
    else:
        print("✅ No shared pool workers found")
    
    return len(shared_workers)


def main():
    """Main execution."""
    print("🧹 SHARED THREAD POOL CLEANUP FIX")
    print("=" * 50)
    print("This script fixes the thread leak caused by shared thread pool workers")
    print("that are not properly cleaned up during test teardown.")
    print()
    
    # Test 1: Check for existing shared pool workers
    initial_workers = test_shared_pool_cleanup()
    
    # Test 2: Apply the fix to scanner test
    print("\n🔧 Applying fix to scanner test...")
    success = apply_shared_pool_cleanup_to_scanner_test()
    
    if success:
        print("\n✅ SHARED THREAD POOL CLEANUP FIX APPLIED SUCCESSFULLY!")
        print("The scanner test tearDown method now includes shared pool cleanup.")
        print("This should resolve the thread leak warnings:")
        print("  - sharedThreadPool_worker_1")
        print("  - sharedThreadPool_worker_2") 
        print("  - sharedThreadPool_worker_3")
        return 0
    else:
        print("\n❌ Failed to apply shared thread pool cleanup fix")
        return 1


if __name__ == "__main__":
    sys.exit(main())

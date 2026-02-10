#!/usr/bin/env python3
"""
Shared Thread Pool Cleanup Fix
=============================

This module provides specific cleanup for SpiderFoot's shared thread pool
workers that are not properly cleaned up during test teardown.
"""

from __future__ import annotations

import threading
import time
import gc
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


# Integration function for test teardown
def enhanced_teardown_with_shared_pool_cleanup():
    """
    Enhanced teardown that specifically handles shared thread pool cleanup.
    Use this in test tearDown methods.
    """
    # Step 1: Standard shared pool cleanup
    remaining = cleanup_shared_thread_pool()
    
    # Step 2: If threads remain, use emergency cleanup
    if remaining > 0:
        print(f"⚠️  {remaining} shared pool workers remain, using emergency cleanup...")
        remaining = emergency_shared_pool_cleanup()
    
    # Step 3: Final verification
    if remaining > 0:
        print(f"🚨 Warning: {remaining} shared thread pool workers could not be cleaned up")
        # Don't fail the test, but log the issue
        
    return remaining


def get_shared_pool_thread_info():
    """Get information about current shared pool threads for debugging."""
    shared_threads = []
    for thread in threading.enumerate():
        if 'sharedThreadPool_worker' in getattr(thread, 'name', ''):
            thread_info = {
                'name': thread.name,
                'alive': thread.is_alive(),
                'daemon': getattr(thread, 'daemon', False),
                'ident': getattr(thread, 'ident', None)
            }
            shared_threads.append(thread_info)
    
    return shared_threads


def cleanup_shared_pools() -> int:
    """
    Clean up all shared thread pools.
    
    Returns:
        Number of threads cleaned up
    """
    # Try standard cleanup first
    remaining = cleanup_shared_thread_pool()
    
    # If threads remain, use emergency cleanup
    if remaining > 0:
        return emergency_shared_pool_cleanup()
    
    return remaining

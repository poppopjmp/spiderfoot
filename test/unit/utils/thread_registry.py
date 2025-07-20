#!/usr/bin/env python3
"""
Thread Registry System for SpiderFoot Tests
==========================================

Central registry for all test-created threads to ensure no thread escapes cleanup.
Part of the ThreadReaper comprehensive thread management overhaul.
"""

import threading
import time
import traceback
import weakref
from contextlib import suppress
from typing import Dict, List, Optional, Any, Set


class ThreadRegistry:
    """
    Central registry for all test-created threads.
    Ensures no thread escapes cleanup through comprehensive tracking.
    """
    
    def __init__(self):
        self._threads: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._categories: Set[str] = set()
        self._owners: Dict[str, List[int]] = {}
        
    def register(self, thread: threading.Thread, category: str, owner: Optional[str] = None) -> None:
        """
        Register a thread for tracking and cleanup.
        
        Args:
            thread: The thread to register
            category: Category (scanner, module, web_ui, database, etc.)
            owner: Optional owner identifier for grouped cleanup
        """
        with self._lock:
            thread_id = thread.ident or id(thread)
            
            self._threads[thread_id] = {
                'thread': weakref.ref(thread),
                'thread_obj': thread,  # Keep strong reference
                'category': category,
                'owner': owner,
                'name': thread.name,
                'daemon': getattr(thread, 'daemon', False),
                'registered_at': time.time(),
                'stack_trace': traceback.extract_stack()[:-1]  # Exclude this frame
            }
            
            self._categories.add(category)
            
            if owner:
                if owner not in self._owners:
                    self._owners[owner] = []
                self._owners[owner].append(thread_id)
    
    def unregister(self, thread: threading.Thread) -> None:
        """Unregister a thread (when it completes normally)."""
        with self._lock:
            thread_id = thread.ident or id(thread)
            if thread_id in self._threads:
                thread_info = self._threads[thread_id]
                owner = thread_info.get('owner')
                
                # Remove from owner tracking
                if owner and owner in self._owners:
                    try:
                        self._owners[owner].remove(thread_id)
                        if not self._owners[owner]:
                            del self._owners[owner]
                    except ValueError:
                        pass
                
                del self._threads[thread_id]
    
    def get_active_threads(self, category: Optional[str] = None, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of active threads, optionally filtered by category or owner.
        
        Args:
            category: Filter by thread category
            owner: Filter by thread owner
            
        Returns:
            List of thread info dictionaries
        """
        with self._lock:
            active = []
            
            for thread_id, thread_info in self._threads.items():
                thread_ref = thread_info['thread']
                thread_obj = thread_ref()
                
                if thread_obj and thread_obj.is_alive():
                    if category and thread_info['category'] != category:
                        continue
                    if owner and thread_info.get('owner') != owner:
                        continue
                    
                    active.append({
                        'thread_id': thread_id,
                        'thread': thread_obj,
                        'category': thread_info['category'],
                        'owner': thread_info.get('owner'),
                        'name': thread_info['name'],
                        'daemon': thread_info['daemon'],
                        'registered_at': thread_info['registered_at'],
                        'age': time.time() - thread_info['registered_at']
                    })
                else:
                    # Clean up dead thread references
                    self._cleanup_dead_thread(thread_id)
            
            return active
    
    def register_thread(self, thread: threading.Thread) -> int:
        """
        Register a thread and return a tracking ID.
        
        Args:
            thread: Thread to register
            
        Returns:
            Thread tracking ID
        """
        thread_id = thread.ident or id(thread)
        self.register(thread, "general", None)
        return thread_id
    
    def cleanup_by_category(self, category: str, timeout: float = 5.0) -> int:
        """
        Clean up all threads in a specific category.
        
        Args:
            category: Category to cleanup
            timeout: Timeout for each thread join
            
        Returns:
            Number of threads cleaned up
        """
        cleaned = 0
        threads_to_cleanup = []
        
        with self._lock:
            for thread_id, info in list(self._threads.items()):
                if info['category'] == category:
                    thread_ref = info['thread']
                    thread = thread_ref() if isinstance(thread_ref, weakref.ref) else info.get('thread_obj')
                    if thread and thread.is_alive():
                        threads_to_cleanup.append((thread, thread_id, info))
        
        # Cleanup threads outside the lock
        for thread, thread_id, info in threads_to_cleanup:
            try:
                print(f"  🧹 Cleaning up {category} thread: {thread.name}")
                
                # Try graceful join first
                thread.join(timeout=timeout)
                
                if thread.is_alive():
                    print(f"    ⚠️  Thread {thread.name} still alive after {timeout}s")
                else:
                    cleaned += 1
                    
            except Exception as e:
                print(f"    ⚠️  Error cleaning thread {thread.name}: {e}")
            
            # Remove from registry
            with self._lock:
                self._threads.pop(thread_id, None)
        
        return cleaned
    
    def force_cleanup_all_threads(self, timeout: float = 3.0) -> Dict[str, int]:
        """
        Force cleanup of all registered threads.
        
        Args:
            timeout: Timeout for thread joins
            
        Returns:
            Dict with cleanup statistics
        """
        print("🧹 ThreadRegistry: Force cleanup of all threads...")
        
        stats = {'total': 0, 'cleaned': 0, 'failed': 0, 'still_alive': 0}
        
        with self._lock:
            thread_items = list(self._threads.items())
            stats['total'] = len(thread_items)
        
        for thread_id, info in thread_items:
            try:
                thread_ref = info['thread']
                thread = thread_ref() if isinstance(thread_ref, weakref.ref) else info.get('thread_obj')
                
                if not thread or not thread.is_alive():
                    continue
                
                print(f"  🧹 Force cleanup: {info['name']} ({info['category']})")
                
                # Try graceful join
                thread.join(timeout=timeout)
                
                if thread.is_alive():
                    stats['still_alive'] += 1
                    print(f"    ⚠️  Thread {info['name']} still alive")
                else:
                    stats['cleaned'] += 1
                
            except Exception as e:
                stats['failed'] += 1
                print(f"    ⚠️  Error in force cleanup: {e}")
        
        # Clear the registry
        with self._lock:
            self._threads.clear()
            self._categories.clear()
            self._owners.clear()
        
        print(f"✅ ThreadRegistry cleanup complete: {stats}")
        return stats
    
    def cleanup_all(self, timeout: float = 5.0) -> int:
        """
        Clean up all registered threads.
        
        Args:
            timeout: Timeout for thread joins
            
        Returns:
            Number of threads cleaned up
        """
        with self._lock:
            all_categories = list(self._categories)
        
        total_cleaned = 0
        for category in all_categories:
            cleaned = self.cleanup_by_category(category, timeout)
            total_cleaned += cleaned
        
        return total_cleaned
    
    def _cleanup_thread_list(self, thread_list: List[Dict[str, Any]], timeout: float) -> int:
        """Clean up a specific list of threads."""
        # Step 1: Graceful shutdown
        for thread_info in thread_list:
            thread = thread_info['thread']
            self._attempt_graceful_shutdown(thread)
        
        # Step 2: Brief wait
        time.sleep(min(0.3, timeout / 3))
        
        # Step 3: Force join
        start_time = time.time()
        for thread_info in thread_list:
            thread = thread_info['thread']
            remaining_timeout = max(0.1, timeout - (time.time() - start_time))
            
            if thread.is_alive():
                with suppress(RuntimeError, OSError):
                    thread.join(timeout=remaining_timeout)
        
        # Step 4: Count survivors
        survivors = 0
        for thread_info in thread_list:
            thread = thread_info['thread']
            if thread.is_alive():
                survivors += 1
        
        return survivors
    
    def _attempt_graceful_shutdown(self, thread: threading.Thread) -> None:
        """Attempt various graceful shutdown methods on a thread."""
        if not thread or not thread.is_alive():
            return
        
        # Try common shutdown methods
        shutdown_methods = ['stop', 'shutdown', 'close', 'terminate', '_stop']
        
        for method_name in shutdown_methods:
            if hasattr(thread, method_name):
                method = getattr(thread, method_name)
                if callable(method):
                    with suppress(Exception):
                        method()
                        return  # If one works, don't try others
    
    def _cleanup_dead_thread(self, thread_id: int) -> None:
        """Clean up a dead thread reference."""
        if thread_id in self._threads:
            thread_info = self._threads[thread_id]
            owner = thread_info.get('owner')
            
            # Remove from owner tracking
            if owner and owner in self._owners:
                try:
                    self._owners[owner].remove(thread_id)
                    if not self._owners[owner]:
                        del self._owners[owner]
                except ValueError:
                    pass
            
            del self._threads[thread_id]
    
    def generate_report(self) -> str:
        """Generate a comprehensive report of all registered threads."""
        threads = self.get_active_threads()
        
        if not threads:
            return "✅ No active registered threads"
        
        report = [f"📊 Thread Registry Report - {len(threads)} active threads"]
        report.append("=" * 60)
        
        # Group by category
        categories = {}
        for thread_info in threads:
            category = thread_info['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(thread_info)
        
        for category, category_threads in categories.items():
            report.append(f"\n🏷️  Category: {category} ({len(category_threads)} threads)")
            report.append("-" * 40)
            
            for thread_info in category_threads:
                thread = thread_info['thread']
                age = thread_info['age']
                owner = thread_info.get('owner', 'N/A')
                
                report.append(f"  • {thread.name}")
                report.append(f"    ID: {thread_info['thread_id']}")
                report.append(f"    Owner: {owner}")
                report.append(f"    Age: {age:.2f}s")
                report.append(f"    Daemon: {thread_info['daemon']}")
                report.append(f"    Alive: {thread.is_alive()}")
                
                # Show stack trace for long-running threads
                if age > 30:  # Show stack for threads older than 30 seconds
                    report.append("    Registration stack:")
                    for frame in thread_info['stack_trace'][-3:]:  # Last 3 frames
                        report.append(f"      {frame.filename}:{frame.lineno} in {frame.name}")
                
                report.append("")
        
        return "\n".join(report)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about registered threads."""
        threads = self.get_active_threads()
        
        if not threads:
            return {"total": 0, "categories": {}, "owners": {}}
        
        stats = {
            "total": len(threads),
            "categories": {},
            "owners": {},
            "daemon_count": sum(1 for t in threads if t['daemon']),
            "average_age": sum(t['age'] for t in threads) / len(threads),
            "oldest_thread": max(threads, key=lambda t: t['age'])['name'],
            "oldest_age": max(t['age'] for t in threads)
        }
        
        # Category breakdown
        for thread_info in threads:
            category = thread_info['category']
            stats["categories"][category] = stats["categories"].get(category, 0) + 1
            
            owner = thread_info.get('owner')
            if owner:
                stats["owners"][owner] = stats["owners"].get(owner, 0) + 1
        
        return stats
    
    def get_leak_report(self) -> str:
        """
        Generate a comprehensive leak report.
        
        Returns:
            Formatted leak report
        """
        with self._lock:
            if not self._threads:
                return "✅ No threads registered"
            
            current_time = time.time()
            report_lines = [
                f"🧵 THREAD REGISTRY REPORT - {len(self._threads)} threads tracked",
                "=" * 60
            ]
            
            # Group by category
            by_category = {}
            for thread_id, info in self._threads.items():
                category = info['category']
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append((thread_id, info))
            
            for category, threads in by_category.items():
                report_lines.append(f"\n{category.upper()} THREADS ({len(threads)}):")
                report_lines.append("-" * 40)
                
                for thread_id, info in threads:
                    age = current_time - info['registered_at']
                    thread_ref = info['thread']
                    thread = thread_ref() if isinstance(thread_ref, weakref.ref) else info.get('thread_obj')
                    is_alive = thread and thread.is_alive()
                    
                    report_lines.append(f"  📍 {info['name']} (ID: {thread_id})")
                    report_lines.append(f"     Age: {age:.1f}s, Alive: {is_alive}, Daemon: {info['daemon']}")
                    if info['owner']:
                        report_lines.append(f"     Owner: {info['owner']}")
                    
                    # Show recent stack trace frames
                    if info['stack_trace'] and len(info['stack_trace']) > 0:
                        report_lines.append("     Created at:")
                        for frame in info['stack_trace'][-2:]:  # Last 2 frames
                            report_lines.append(f"       {frame.filename}:{frame.lineno} in {frame.name}")
                    
                    report_lines.append("")
            
            return "\n".join(report_lines)
        

# Global registry instance for test use
_global_registry = ThreadRegistry()


def register_thread(thread: threading.Thread, category: str, owner: Optional[str] = None) -> None:
    """Register a thread with the global registry."""
    _global_registry.register(thread, category, owner)


def unregister_thread(thread: threading.Thread) -> None:
    """Unregister a thread from the global registry."""
    _global_registry.unregister(thread)


def cleanup_all_threads(timeout: float = 10.0) -> int:
    """Clean up all registered threads."""
    return _global_registry.cleanup_all(timeout)


def cleanup_by_category(category: str, timeout: float = 5.0) -> int:
    """Clean up threads by category."""
    return _global_registry.cleanup_by_category(category, timeout)


def cleanup_by_owner(owner: str, timeout: float = 5.0) -> int:
    """Clean up threads by owner."""
    return _global_registry.cleanup_by_owner(owner, timeout)


def get_thread_report() -> str:
    """Get a comprehensive thread report."""
    return _global_registry.generate_report()


def get_thread_statistics() -> Dict[str, Any]:
    """Get thread statistics."""
    return _global_registry.get_statistics()


def get_test_thread_registry() -> ThreadRegistry:
    """
    Get the global thread registry for tests.
    
    Returns:
        Global ThreadRegistry instance
    """
    return _global_registry


def cleanup_test_threads(timeout: float = 5.0) -> int:
    """
    Clean up all test threads.
    
    Args:
        timeout: Timeout for thread cleanup
        
    Returns:
        Number of threads cleaned up
    """
    return cleanup_all_threads(timeout)


def reset_test_thread_registry():
    """Reset the global thread registry."""
    global _global_registry
    _global_registry = ThreadRegistry()


# Context manager for automatic thread cleanup
class ThreadScope:
    """Context manager that ensures all threads created within the scope are cleaned up."""
    
    def __init__(self, owner: str, timeout: float = 5.0):
        self.owner = owner
        self.timeout = timeout
        self.initial_threads = set()
    
    def __enter__(self):
        self.initial_threads = set(threading.enumerate())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Find threads created during this scope
        current_threads = set(threading.enumerate())
        new_threads = current_threads - self.initial_threads
        
        # Register and clean up new threads
        for thread in new_threads:
            if thread.is_alive():
                register_thread(thread, 'scope', self.owner)
        
        cleanup_by_owner(self.owner, self.timeout)

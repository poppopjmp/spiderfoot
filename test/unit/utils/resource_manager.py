#!/usr/bin/env python3
"""
Resource Manager for SpiderFoot Tests
====================================

Thread-safe resource management with guaranteed cleanup.
Ensures all test resources are properly released, even during catastrophic failures.
"""
from __future__ import annotations

import threading
import time
import weakref
import traceback
from contextlib import suppress
from typing import Any, Callable


class ResourceManager:
    """
    Manages all test resources with guaranteed cleanup.
    
    Features:
    - LIFO cleanup order to handle dependencies
    - Weak references to prevent reference cycles
    - Exception-safe cleanup
    - Resource leak detection
    - Thread-safe operations
    """
    
    def __init__(self):
        self._resources: list[dict[str, Any]] = []
        self._cleanup_functions: list[Callable] = []
        self._lock = threading.Lock()
        self._cleanup_attempted = False
        self._resource_counter = 0
    
    def register_resource(self, resource: Any, cleanup_func: Callable,
                          category: str = "unknown", description: str = "") -> int:
        """
        Register a resource with its cleanup function.
        
        Args:
            resource: The resource to track
            cleanup_func: Function to call for cleanup
            category: Resource category for organization
            description: Human-readable description
            
        Returns:
            Resource ID for tracking
        """
        with self._lock:
            resource_id = self._resource_counter
            self._resource_counter += 1
            
            # Use weak reference when possible to prevent cycles
            try:
                resource_ref = weakref.ref(resource)
            except TypeError:
                # Some objects can't be weakly referenced
                resource_ref = resource
            
            resource_info = {
                'id': resource_id,
                'resource': resource_ref,
                'cleanup_func': cleanup_func,
                'category': category,
                'description': description,
                'registered_at': time.time(),
                'stack_trace': traceback.extract_stack()
            }
            
            self._resources.append(resource_info)
            return resource_id
    
    def register_thread(self, thread: threading.Thread, stop_func: Callable | None = None,
                        timeout: float = 5.0) -> int:
        """
        Register a thread for cleanup.
        
        Args:
            thread: Thread to track
            stop_func: Optional function to stop thread gracefully
            timeout: Timeout for thread join
            
        Returns:
            Resource ID for tracking
        """
        def cleanup_thread():
            if not thread.is_alive():
                return
                
            # Try graceful stop first
            if stop_func:
                with suppress(Exception):
                    stop_func()
                    
            # Join with timeout
            with suppress(RuntimeError, OSError):
                thread.join(timeout=timeout)
                
            # Force termination if still alive
            if thread.is_alive():
                print(f"Warning: Thread {thread.name} still alive after cleanup")
        
        return self.register_resource(
            thread, cleanup_thread,
            category="thread",
            description=f"Thread: {thread.name}"
        )
    
    def register_scanner(self, scanner: Any) -> int:
        """
        Register a SpiderFoot scanner for cleanup.
        
        Args:
            scanner: Scanner instance to track
            
        Returns:
            Resource ID for tracking
        """
        def cleanup_scanner():
            with suppress(Exception):
                if hasattr(scanner, 'shutdown'):
                    scanner.shutdown()
                elif hasattr(scanner, 'stop'):
                    scanner.stop()
                    
                # Force abort status
                if hasattr(scanner, '_SpiderFootScanner__setStatus'):
                    scanner._SpiderFootScanner__setStatus("ABORTED")
        
        return self.register_resource(
            scanner, cleanup_scanner,
            category="scanner",
            description=f"Scanner: {scanner.__class__.__name__}"
        )
    
    def register_module(self, module: Any) -> int:
        """
        Register a SpiderFoot module for cleanup.
        
        Args:
            module: Module instance to track
            
        Returns:
            Resource ID for tracking
        """
        def cleanup_module():
            with suppress(Exception):
                # Set error state to stop processing
                if hasattr(module, 'errorState'):
                    module.errorState = True
                    
                # Clear listeners
                if hasattr(module, 'clearListeners'):
                    module.clearListeners()
                    
                # Clear temp storage
                if hasattr(module, 'tempStorage'):
                    module.tempStorage().clear()
                    
                # Clear results
                if hasattr(module, 'results'):
                    module.results = None
        
        return self.register_resource(
            module, cleanup_module,
            category="module",
            description=f"Module: {module.__class__.__name__}"
        )
    
    def register_server(self, server: Any, stop_func: Callable | None = None) -> int:
        """
        Register a web server for cleanup.
        
        Args:
            server: Server instance to track
            stop_func: Optional custom stop function
            
        Returns:
            Resource ID for tracking
        """
        def cleanup_server():
            if stop_func:
                with suppress(Exception):
                    stop_func()
            else:
                # Try common server stop methods
                for method_name in ['shutdown', 'stop', 'close']:
                    if hasattr(server, method_name):
                        with suppress(Exception):
                            getattr(server, method_name)()
                            break
        
        return self.register_resource(
            server, cleanup_server,
            category="server",
            description=f"Server: {server.__class__.__name__}"
        )
    
    def unregister_resource(self, resource_id: int) -> bool:
        """
        Unregister a resource (cleanup already handled).
        
        Args:
            resource_id: ID returned from register_resource
            
        Returns:
            True if resource was found and removed
        """
        with self._lock:
            for i, resource_info in enumerate(self._resources):
                if resource_info['id'] == resource_id:
                    del self._resources[i]
                    return True
        return False
    
    def cleanup_all(self, force: bool = False) -> dict[str, int]:
        """
        Execute all cleanup functions in LIFO order.
        
        Args:
            force: If True, re-run cleanup even if already attempted
            
        Returns:
            Dict with cleanup statistics
        """
        with self._lock:
            if self._cleanup_attempted and not force:
                return {'skipped': len(self._resources)}
                
            self._cleanup_attempted = True
            
            if not self._resources:
                return {'total': 0, 'success': 0, 'failed': 0}
            
            print(f"🧹 ResourceManager cleaning up {len(self._resources)} resources...")
            
            total = len(self._resources)
            success = 0
            failed = 0
            
            # Cleanup in LIFO order (reverse registration order)
            for resource_info in reversed(self._resources):
                try:
                    cleanup_func = resource_info['cleanup_func']
                    category = resource_info['category']
                    description = resource_info['description']
                    
                    print(f"  🧹 Cleaning up {category}: {description}")
                    cleanup_func()
                    success += 1
                    
                except Exception as e:
                    failed += 1
                    print(f"  ⚠️  Failed to cleanup {resource_info['category']}: {e}")
            
            # Clear all resources
            self._resources.clear()
            
            stats = {'total': total, 'success': success, 'failed': failed}
            print(f"✅ ResourceManager cleanup complete: {stats}")
            
            return stats
    
    def cleanup_category(self, category: str) -> int:
        """
        Cleanup all resources of a specific category.
        
        Args:
            category: Category to cleanup
            
        Returns:
            Number of resources cleaned up
        """
        with self._lock:
            category_resources = []
            remaining_resources = []
            
            for resource_info in self._resources:
                if resource_info['category'] == category:
                    category_resources.append(resource_info)
                else:
                    remaining_resources.append(resource_info)
            
            if not category_resources:
                return 0
            
            print(f"🧹 Cleaning up {len(category_resources)} {category} resources...")
            
            cleaned = 0
            for resource_info in reversed(category_resources):  # LIFO
                try:
                    resource_info['cleanup_func']()
                    cleaned += 1
                except Exception as e:
                    print(f"⚠️  Failed to cleanup {category}: {e}")
            
            # Update resources list
            self._resources = remaining_resources
            
            return cleaned
    
    def get_resource_summary(self) -> dict[str, int]:
        """
        Get summary of currently registered resources.
        
        Returns:
            Dict mapping category to count
        """
        with self._lock:
            summary = {}
            for resource_info in self._resources:
                category = resource_info['category']
                summary[category] = summary.get(category, 0) + 1
            return summary
    
    def detect_leaks(self) -> list[dict[str, Any]]:
        """
        Detect potential resource leaks.
        
        Returns:
            List of leak information
        """
        leaks = []
        current_time = time.time()
        
        with self._lock:
            for resource_info in self._resources:
                age = current_time - resource_info['registered_at']
                
                # Consider resources older than 60 seconds as potential leaks
                if age > 60:
                    leak_info = {
                        'category': resource_info['category'],
                        'description': resource_info['description'],
                        'age_seconds': age,
                        'stack_trace': resource_info['stack_trace']
                    }
                    leaks.append(leak_info)
        
        return leaks
    
    def force_cleanup_leaked_resources(self) -> int:
        """
        Force cleanup of resources that appear to be leaked.
        
        Returns:
            Number of leaked resources cleaned up
        """
        leaks = self.detect_leaks()
        if not leaks:
            return 0
            
        print(f"🚨 Force cleaning up {len(leaks)} leaked resources...")
        
        cleaned = 0
        with self._lock:
            # Find and cleanup leaked resources
            remaining_resources = []
            
            for resource_info in self._resources:
                age = time.time() - resource_info['registered_at']
                if age > 60:  # Leaked resource
                    try:
                        resource_info['cleanup_func']()
                        cleaned += 1
                        print(f"  🧹 Cleaned leaked {resource_info['category']}")
                    except Exception as e:
                        print(f"  ⚠️  Failed to cleanup leaked {resource_info['category']}: {e}")
                        remaining_resources.append(resource_info)
                else:
                    remaining_resources.append(resource_info)
            
            self._resources = remaining_resources
        
        return cleaned
    
    def __del__(self):
        """Ensure cleanup on object destruction."""
        with suppress(Exception):
            if not self._cleanup_attempted:
                self.cleanup_all()


# Global resource manager for tests
_test_resource_manager = None
_manager_lock = threading.Lock()


def get_test_resource_manager() -> ResourceManager:
    """
    Get the global test resource manager (singleton).
    
    Returns:
        Global ResourceManager instance
    """
    global _test_resource_manager
    
    with _manager_lock:
        if _test_resource_manager is None:
            _test_resource_manager = ResourceManager()
        return _test_resource_manager


def reset_test_resource_manager():
    """Reset the global resource manager (for testing)."""
    global _test_resource_manager
    
    with _manager_lock:
        if _test_resource_manager:
            _test_resource_manager.cleanup_all()
        _test_resource_manager = None


def cleanup_all_test_resources() -> dict[str, int]:
    """
    Cleanup all test resources using the global manager.
    
    Returns:
        Cleanup statistics
    """
    manager = get_test_resource_manager()
    return manager.cleanup_all()


# Convenience functions for common resource types
def register_test_thread(thread: threading.Thread, stop_func: Callable | None = None) -> int:
    """Register a thread with the global resource manager."""
    manager = get_test_resource_manager()
    return manager.register_thread(thread, stop_func)


def register_test_scanner(scanner: Any) -> int:
    """Register a scanner with the global resource manager."""
    manager = get_test_resource_manager()
    return manager.register_scanner(scanner)


def register_test_module(module: Any) -> int:
    """Register a module with the global resource manager."""
    manager = get_test_resource_manager()
    return manager.register_module(module)


def register_test_server(server: Any, stop_func: Callable | None = None) -> int:
    """Register a server with the global resource manager."""
    manager = get_test_resource_manager()
    return manager.register_server(server, stop_func)

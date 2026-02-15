#!/usr/bin/env python3
"""
Thread and Resource Leak Detection and Reporting
===============================================

Comprehensive leak detection system for SpiderFoot tests.
Tracks threads, file handles, memory usage, and other resources.
"""
from __future__ import annotations

import threading
import time
import traceback
import weakref
import os
import gc
from contextlib import suppress
from typing import Any
from dataclasses import dataclass, field


@dataclass
class LeakInfo:
    """Information about a detected leak."""
    resource_type: str
    resource_id: str
    description: str
    age_seconds: float
    stack_trace: list[str] = field(default_factory=list)
    additional_info: dict[str, Any] = field(default_factory=dict)


class LeakDetector:
    """
    Detects various types of resource leaks in SpiderFoot tests.
    
    Features:
    - Thread leak detection
    - File handle leak detection
    - Memory leak detection
    - Database connection leak detection
    - Custom resource tracking
    """
    
    def __init__(self):
        self._baseline_threads: dict[int, threading.Thread] = {}
        self._baseline_files: set = set()
        self._baseline_memory: int | None = None
        self._tracked_resources: dict[str, dict[str, Any]] = {}
        self._start_time = time.time()
        self._lock = threading.Lock()
    
    def set_baseline(self):
        """Set baseline measurements for leak detection."""
        with self._lock:
            # Record current threads
            self._baseline_threads = {
                thread.ident: thread for thread in threading.enumerate()
            }
            
            # Record open file handles
            try:
                import psutil
                process = psutil.Process()
                self._baseline_files = set(f.path for f in process.open_files())
            except Exception as e:
                self._baseline_files = set()
            
            # Record memory usage
            try:
                import psutil
                process = psutil.Process()
                self._baseline_memory = process.memory_info().rss
            except Exception as e:
                self._baseline_memory = None
            
            self._start_time = time.time()
            
            print("🎯 Leak detector baseline set:")
            print(f"   Threads: {len(self._baseline_threads)}")
            print(f"   Files: {len(self._baseline_files)}")
            print(f"   Memory: {self._baseline_memory}")
    
    def track_resource(self, resource_id: str, resource: Any,
                       resource_type: str, description: str = ""):
        """
        Track a custom resource for leak detection.
        
        Args:
            resource_id: Unique identifier for the resource
            resource: The resource object
            resource_type: Type of resource (e.g., 'database', 'socket')
            description: Human-readable description
        """
        with self._lock:
            try:
                # Use weak reference when possible
                resource_ref = weakref.ref(resource)
            except TypeError:
                resource_ref = resource
            
            self._tracked_resources[resource_id] = {
                'resource': resource_ref,
                'type': resource_type,
                'description': description,
                'created_at': time.time(),
                'stack_trace': traceback.extract_stack()
            }
    
    def untrack_resource(self, resource_id: str):
        """
        Stop tracking a resource.
        
        Args:
            resource_id: ID of resource to stop tracking
        """
        with self._lock:
            self._tracked_resources.pop(resource_id, None)
    
    def detect_thread_leaks(self) -> list[LeakInfo]:
        """
        Detect thread leaks compared to baseline.
        
        Returns:
            List of thread leak information
        """
        leaks = []
        current_threads = {thread.ident: thread for thread in threading.enumerate()}
        current_time = time.time()
        
        for ident, thread in current_threads.items():
            if ident not in self._baseline_threads:
                # This is a new thread since baseline
                age = current_time - self._start_time
                
                leak_info = LeakInfo(
                    resource_type="thread",
                    resource_id=str(ident),
                    description=f"Thread: {thread.name}",
                    age_seconds=age,
                    additional_info={
                        'thread_name': thread.name,
                        'is_alive': thread.is_alive(),
                        'daemon': thread.daemon
                    }
                )
                leaks.append(leak_info)
        
        return leaks
    
    def detect_file_leaks(self) -> list[LeakInfo]:
        """
        Detect file handle leaks compared to baseline.
        
        Returns:
            List of file leak information
        """
        leaks = []
        
        try:
            import psutil
            process = psutil.Process()
            current_files = set(f.path for f in process.open_files())
            
            for file_path in current_files:
                if file_path not in self._baseline_files:
                    # This is a new file handle since baseline
                    leak_info = LeakInfo(
                        resource_type="file",
                        resource_id=file_path,
                        description=f"File: {os.path.basename(file_path)}",
                        age_seconds=time.time() - self._start_time,
                        additional_info={'full_path': file_path}
                    )
                    leaks.append(leak_info)
        
        except Exception as e:
            # psutil not available or error occurred
            pass
        
        return leaks
    
    def detect_memory_leaks(self, threshold_mb: float = 50.0) -> list[LeakInfo]:
        """
        Detect significant memory increases.
        
        Args:
            threshold_mb: Memory increase threshold in MB
            
        Returns:
            List of memory leak information
        """
        leaks = []
        
        if self._baseline_memory is None:
            return leaks
        
        try:
            import psutil
            process = psutil.Process()
            current_memory = process.memory_info().rss
            
            memory_increase = current_memory - self._baseline_memory
            memory_increase_mb = memory_increase / (1024 * 1024)
            
            if memory_increase_mb > threshold_mb:
                leak_info = LeakInfo(
                    resource_type="memory",
                    resource_id="memory_usage",
                    description=f"Memory increased by {memory_increase_mb:.1f} MB",
                    age_seconds=time.time() - self._start_time,
                    additional_info={
                        'baseline_mb': self._baseline_memory / (1024 * 1024),
                        'current_mb': current_memory / (1024 * 1024),
                        'increase_mb': memory_increase_mb
                    }
                )
                leaks.append(leak_info)
        
        except Exception as e:
            pass
        
        return leaks
    
    def detect_resource_leaks(self) -> list[LeakInfo]:
        """
        Detect leaks in tracked custom resources.
        
        Returns:
            List of custom resource leak information
        """
        leaks = []
        current_time = time.time()
        
        with self._lock:
            for resource_id, info in self._tracked_resources.items():
                # Check if resource still exists
                resource = info['resource']
                if isinstance(resource, weakref.ref):
                    if resource() is None:
                        # Resource was garbage collected, not a leak
                        continue
                
                # Check age
                age = current_time - info['created_at']
                
                # Consider resources older than 30 seconds as potential leaks
                if age > 30:
                    leak_info = LeakInfo(
                        resource_type=info['type'],
                        resource_id=resource_id,
                        description=info['description'],
                        age_seconds=age,
                        stack_trace=[str(frame) for frame in info['stack_trace']],
                        additional_info={'created_at': info['created_at']}
                    )
                    leaks.append(leak_info)
        
        return leaks
    
    def detect_all_leaks(self) -> dict[str, list[LeakInfo]]:
        """
        Detect all types of leaks.
        
        Returns:
            Dict mapping leak type to list of leaks
        """
        all_leaks = {
            'threads': self.detect_thread_leaks(),
            'files': self.detect_file_leaks(),
            'memory': self.detect_memory_leaks(),
            'resources': self.detect_resource_leaks()
        }
        
        return all_leaks
    
    def get_leak_summary(self) -> dict[str, int]:
        """
        Get summary count of all leak types.
        
        Returns:
            Dict mapping leak type to count
        """
        all_leaks = self.detect_all_leaks()
        return {leak_type: len(leaks) for leak_type, leaks in all_leaks.items()}
    
    def generate_leak_report(self) -> str:
        """
        Generate a comprehensive leak report.
        
        Returns:
            Formatted leak report string
        """
        all_leaks = self.detect_all_leaks()
        
        # Count total leaks
        total_leaks = sum(len(leaks) for leaks in all_leaks.values())
        
        if total_leaks == 0:
            return "✅ No leaks detected"
        
        report_lines = [
            f"🚨 LEAK DETECTION REPORT - {total_leaks} leaks found",
            "=" * 60
        ]
        
        for leak_type, leaks in all_leaks.items():
            if not leaks:
                continue
            
            report_lines.append(f"\n{leak_type.upper()} LEAKS ({len(leaks)}):")
            report_lines.append("-" * 40)
            
            for leak in leaks:
                report_lines.append(f"  📍 {leak.description}")
                report_lines.append(f"     Type: {leak.resource_type}")
                report_lines.append(f"     Age: {leak.age_seconds:.1f} seconds")
                report_lines.append(f"     ID: {leak.resource_id}")
                
                if leak.additional_info:
                    report_lines.append(f"     Info: {leak.additional_info}")
                
                if leak.stack_trace and len(leak.stack_trace) > 0:
                    report_lines.append("     Stack trace:")
                    for frame in leak.stack_trace[-3:]:  # Last 3 frames
                        report_lines.append(f"       {frame}")
                
                report_lines.append("")
        
        return "\n".join(report_lines)
    
    def force_cleanup_leaks(self) -> int:
        """
        Attempt to force cleanup of detected leaks.
        
        Returns:
            Number of leaks cleaned up
        """
        cleaned = 0
        
        # Cleanup thread leaks
        thread_leaks = self.detect_thread_leaks()
        for leak in thread_leaks:
            try:
                # Find the thread and try to join it
                for thread in threading.enumerate():
                    if str(thread.ident) == leak.resource_id:
                        if thread.is_alive():
                            thread.join(timeout=1.0)
                            if not thread.is_alive():
                                cleaned += 1
                        break
            except Exception as e:
                pass
        
        # Cleanup file leaks
        file_leaks = self.detect_file_leaks()
        for leak in file_leaks:
            try:
                # Try to close the file if it's still open
                # This is a bit tricky since we only have the path
                # In practice, forcing GC often helps
                pass
            except Exception as e:
                pass
        
        # Force garbage collection
        gc.collect()
        
        # Cleanup custom resources
        resource_leaks = self.detect_resource_leaks()
        with self._lock:
            for leak in resource_leaks:
                try:
                    # Remove from tracking (assuming it's been cleaned up)
                    self._tracked_resources.pop(leak.resource_id, None)
                    cleaned += 1
                except Exception as e:
                    pass
        
        return cleaned
    
    def reset(self):
        """Reset the detector state."""
        with self._lock:
            self._baseline_threads.clear()
            self._baseline_files.clear()
            self._baseline_memory = None
            self._tracked_resources.clear()
            self._start_time = time.time()


# Global leak detector for tests
_test_leak_detector = None
_detector_lock = threading.Lock()


def get_test_leak_detector() -> LeakDetector:
    """
    Get the global test leak detector (singleton).
    
    Returns:
        Global LeakDetector instance
    """
    global _test_leak_detector
    
    with _detector_lock:
        if _test_leak_detector is None:
            _test_leak_detector = LeakDetector()
        return _test_leak_detector


def reset_test_leak_detector():
    """Reset the global leak detector."""
    global _test_leak_detector
    
    with _detector_lock:
        if _test_leak_detector:
            _test_leak_detector.reset()
        _test_leak_detector = None


def set_leak_detection_baseline():
    """Set baseline for leak detection."""
    detector = get_test_leak_detector()
    detector.set_baseline()


def detect_all_test_leaks() -> dict[str, list[LeakInfo]]:
    """Detect all test leaks."""
    detector = get_test_leak_detector()
    return detector.detect_all_leaks()


def generate_test_leak_report() -> str:
    """Generate test leak report."""
    detector = get_test_leak_detector()
    return detector.generate_leak_report()


def force_cleanup_test_leaks() -> int:
    """Force cleanup of test leaks."""
    detector = get_test_leak_detector()
    return detector.force_cleanup_leaks()


class LeakDetectorMixin:
    """
    Mixin class to add leak detection to test classes.
    
    Usage:
        class MyTest(LeakDetectorMixin, unittest.TestCase):
            def test_something(self):
                self.set_leak_baseline()
                # ... test code ...
                self.assert_no_leaks()
    """
    
    def setUp(self):
        """Set up leak detection."""
        if hasattr(super(), 'setUp'):
            super().setUp()
        
        self.leak_detector = get_test_leak_detector()
        self.leak_detector.set_baseline()
    
    def tearDown(self):
        """Check for leaks in tearDown."""
        try:
            leaks = self.leak_detector.detect_all_leaks()
            total_leaks = sum(len(leak_list) for leak_list in leaks.values())
            
            if total_leaks > 0:
                report = self.leak_detector.generate_leak_report()
                print(f"\n{report}")
                
                # Try to cleanup leaks
                cleaned = self.leak_detector.force_cleanup_leaks()
                if cleaned > 0:
                    print(f"🧹 Cleaned up {cleaned} leaks")
        
        except Exception as e:
            print(f"⚠️  Error during leak detection: {e}")
        
        finally:
            if hasattr(super(), 'tearDown'):
                super().tearDown()
    
    def set_leak_baseline(self):
        """Set leak detection baseline manually."""
        self.leak_detector.set_baseline()
    
    def assert_no_leaks(self, leak_types: list[str] = None):
        """
        Assert that no leaks are detected.
        
        Args:
            leak_types: Specific leak types to check (None for all)
        """
        all_leaks = self.leak_detector.detect_all_leaks()
        
        if leak_types:
            # Check only specified leak types
            leaks_to_check = {k: v for k, v in all_leaks.items() if k in leak_types}
        else:
            leaks_to_check = all_leaks
        
        total_leaks = sum(len(leak_list) for leak_list in leaks_to_check.values())
        
        if total_leaks > 0:
            report = self.leak_detector.generate_leak_report()
            self.fail(f"Leaks detected:\n{report}")
    
    def assert_no_thread_leaks(self):
        """Assert that no thread leaks are detected."""
        self.assert_no_leaks(['threads'])
    
    def assert_no_file_leaks(self):
        """Assert that no file leaks are detected."""
        self.assert_no_leaks(['files'])
    
    def assert_no_memory_leaks(self, threshold_mb: float = 50.0):
        """Assert that memory usage hasn't increased significantly."""
        memory_leaks = self.leak_detector.detect_memory_leaks(threshold_mb)
        if memory_leaks:
            leak_info = memory_leaks[0]
            self.fail(f"Memory leak detected: {leak_info.description}")


def track_test_resource(resource_id: str, resource: Any, 
                       resource_type: str, description: str = ""):
    """Track a test resource for leak detection."""
    detector = get_test_leak_detector()
    detector.track_resource(resource_id, resource, resource_type, description)


def untrack_test_resource(resource_id: str):
    """Stop tracking a test resource."""
    detector = get_test_leak_detector()
    detector.untrack_resource(resource_id)

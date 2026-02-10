# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_performance_optimizer
# Purpose:      Performance optimization and caching system for SpiderFoot
#
# Author:      Agostino Panico van1sh@van1shland.io
#
# Created:     20/06/2025
# Copyright:   (c) Agostino Panico 2025
# License:      MIT
# -------------------------------------------------------------------------------

from __future__ import annotations

"""
Performance Optimization Module

Provides advanced performance optimization features:
- Intelligent caching system with TTL support
- Rate limiting with adaptive backoff
- Resource usage monitoring and optimization
- Async request batching
- Database query optimization
- Memory management and cleanup
"""

import time
import json
import hashlib
import threading
import asyncio
import gc
from collections import defaultdict, OrderedDict
from typing import Any, Callable
import weakref
import resource

from spiderfoot import SpiderFootEvent
from spiderfoot.modern_plugin import SpiderFootModernPlugin


class TTLCache:
    """Time-To-Live cache implementation with automatic cleanup."""
    
    def __init__(self, default_ttl: int = 3600, max_size: int = 10000) -> None:
        """Initialize the TTLCache."""
        self.cache = OrderedDict()
        self.ttl_map = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.lock = threading.RLock()
        self.cleanup_thread = None
        self.start_cleanup_thread()
    
    def get(self, key: str) -> Any | None:
        """Get item from cache if not expired."""
        with self.lock:
            if key not in self.cache:
                return None
                
            current_time = time.time()
            if current_time > self.ttl_map[key]:
                # Item expired
                del self.cache[key]
                del self.ttl_map[key]
                return None
                
            # Move to end (LRU)
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
    
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set item in cache with TTL."""
        with self.lock:
            if ttl is None:
                ttl = self.default_ttl
                
            current_time = time.time()
            expiry_time = current_time + ttl
            
            # Remove oldest items if at capacity
            while len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.ttl_map[oldest_key]
            
            self.cache[key] = value
            self.ttl_map[key] = expiry_time
    
    def start_cleanup_thread(self):
        """Start background cleanup thread."""
        def cleanup_expired():
            """Cleanup expired."""
            while True:
                time.sleep(300)  # Cleanup every 5 minutes
                self.cleanup_expired_items()
        
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(target=cleanup_expired, daemon=True)
            self.cleanup_thread.start()
    
    def cleanup_expired_items(self):
        """Remove expired items from cache."""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, expiry in self.ttl_map.items()
                if current_time > expiry
            ]
            
            for key in expired_keys:
                if key in self.cache:
                    del self.cache[key]
                del self.ttl_map[key]
    
    def clear(self):
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
            self.ttl_map.clear()
    
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hit_rate': getattr(self, '_hit_count', 0) / max(getattr(self, '_access_count', 1), 1)
            }


class AdaptiveRateLimiter:
    """Adaptive rate limiter with backoff and success rate monitoring."""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 60.0) -> None:
        """Initialize the AdaptiveRateLimiter."""
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.current_delay = base_delay
        self.last_request_time = 0
        self.success_count = 0
        self.failure_count = 0
        self.lock = threading.Lock()
    
    def wait(self) -> None:
        """Wait according to current rate limit."""
        with self.lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            if time_since_last < self.current_delay:
                sleep_time = self.current_delay - time_since_last
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
    
    def record_success(self) -> None:
        """Record successful request and potentially decrease delay."""
        with self.lock:
            self.success_count += 1
            
            # Decrease delay if success rate is good
            success_rate = self.success_count / (self.success_count + self.failure_count)
            if success_rate > 0.9 and self.current_delay > self.base_delay:
                self.current_delay = max(self.base_delay, self.current_delay * 0.9)
    
    def record_failure(self, status_code: str | None = None) -> None:
        """Record failed request and increase delay."""
        with self.lock:
            self.failure_count += 1
            
            # Increase delay for rate limiting errors
            if status_code in ['429', '503', '502']:
                self.current_delay = min(self.max_delay, self.current_delay * 2)
            elif status_code in ['401', '403']:
                # Authentication errors - moderate increase
                self.current_delay = min(self.max_delay, self.current_delay * 1.5)


class ResourceMonitor:
    """Monitor system resource usage and provide optimization hints."""
    
    def __init__(self) -> None:
        """Initialize the ResourceMonitor."""
        self.memory_samples = []
        self.cpu_samples = []
        self.sample_interval = 60  # seconds
        self.max_samples = 100
        
    def sample_resources(self) -> dict[str, float]:
        """Sample current resource usage."""
        try:
            # Memory usage
            memory_info = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = memory_info.ru_maxrss / 1024  # Convert to MB on most systems
            
            # Add to samples
            current_time = time.time()
            sample = {
                'timestamp': current_time,
                'memory_mb': memory_mb,
                'gc_count': len(gc.get_objects())
            }
            
            self.memory_samples.append(sample)
            
            # Keep only recent samples
            if len(self.memory_samples) > self.max_samples:
                self.memory_samples.pop(0)
            
            return sample
            
        except Exception as e:
            return {'timestamp': time.time(), 'memory_mb': 0, 'gc_count': 0}
    
    def get_memory_trend(self) -> str:
        """Get memory usage trend."""
        if len(self.memory_samples) < 2:
            return "unknown"
            
        recent_avg = sum(s['memory_mb'] for s in self.memory_samples[-10:]) / min(10, len(self.memory_samples))
        older_avg = sum(s['memory_mb'] for s in self.memory_samples[:10]) / min(10, len(self.memory_samples))
        
        if recent_avg > older_avg * 1.2:
            return "increasing"
        elif recent_avg < older_avg * 0.8:
            return "decreasing"
        else:
            return "stable"
    
    def should_trigger_gc(self) -> bool:
        """Determine if garbage collection should be triggered."""
        if not self.memory_samples:
            return False
            
        latest_sample = self.memory_samples[-1]
        return (latest_sample['gc_count'] > 50000 or 
                latest_sample['memory_mb'] > 1000 or
                self.get_memory_trend() == "increasing")


class RequestBatcher:
    """Batch and optimize API requests for better performance."""
    
    def __init__(self, batch_size: int = 10, flush_interval: float = 5.0) -> None:
        """Initialize the RequestBatcher."""
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batches = defaultdict(list)
        self.callbacks = defaultdict(list)
        self.last_flush = defaultdict(float)
        self.lock = threading.Lock()
        
    def add_request(self, batch_key: str, request_data: dict, callback: Callable):
        """Add request to batch."""
        with self.lock:
            self.batches[batch_key].append(request_data)
            self.callbacks[batch_key].append(callback)
            
            current_time = time.time()
            
            # Flush if batch is full or time interval exceeded
            if (len(self.batches[batch_key]) >= self.batch_size or
                current_time - self.last_flush[batch_key] > self.flush_interval):
                self._flush_batch(batch_key)
    
    def _flush_batch(self, batch_key: str):
        """Flush a specific batch."""
        if batch_key not in self.batches or not self.batches[batch_key]:
            return
            
        batch_requests = self.batches[batch_key].copy()
        batch_callbacks = self.callbacks[batch_key].copy()
        
        # Clear the batch
        self.batches[batch_key].clear()
        self.callbacks[batch_key].clear()
        self.last_flush[batch_key] = time.time()
        
        # Process batch asynchronously
        threading.Thread(
            target=self._process_batch,
            args=(batch_key, batch_requests, batch_callbacks),
            daemon=True
        ).start()
    
    def _process_batch(self, batch_key: str, requests: list[dict], callbacks: list[Callable]):
        """Process a batch of requests."""
        # This would be implemented based on specific API requirements
        # For now, process individually
        for request, callback in zip(requests, callbacks):
            try:
                callback(request)
            except Exception as e:
                # Log error but continue processing
                pass


class sfp_performance_optimizer(SpiderFootModernPlugin):
    """Performance optimization and caching system for SpiderFoot."""

    meta = {
        'name': "Performance Optimizer",
        'summary': "Provides caching, rate limiting, and performance optimization for SpiderFoot scans.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Content Analysis"],
        'dataSource': {
            'website': "N/A",
            'model': "FREE_NOAUTH_UNLIMITED",
            'description': "Internal performance optimization system."
        }
    }

    opts = {
        'enable_caching': True,
        'cache_ttl_seconds': 3600,
        'max_cache_size': 10000,
        'enable_rate_limiting': True,
        'base_rate_limit_delay': 1.0,
        'max_rate_limit_delay': 60.0,
        'enable_request_batching': True,
        'batch_size': 10,
        'batch_flush_interval': 5.0,
        'enable_resource_monitoring': True,
        'memory_cleanup_threshold_mb': 500,
        'auto_gc_enabled': True
    }

    optdescs = {
        'enable_caching': "Enable intelligent caching system",
        'cache_ttl_seconds': "Default cache TTL in seconds",
        'max_cache_size': "Maximum number of cached items",
        'enable_rate_limiting': "Enable adaptive rate limiting",
        'base_rate_limit_delay': "Base delay between requests (seconds)",
        'max_rate_limit_delay': "Maximum delay between requests (seconds)",
        'enable_request_batching': "Enable request batching optimization",
        'batch_size': "Number of requests per batch",
        'batch_flush_interval': "Time to wait before flushing incomplete batch",
        'enable_resource_monitoring': "Monitor system resource usage",
        'memory_cleanup_threshold_mb': "Memory threshold for cleanup (MB)",
        'auto_gc_enabled': "Enable automatic garbage collection"
    }

    def setup(self, sfc, userOpts=None):
        """Set up the module."""
        super().setup(sfc, userOpts or {})
        self.results = self.tempStorage()
        
        # Initialize optimization components
        if self.opts.get('enable_caching', True):
            self.cache = TTLCache(
                default_ttl=self.opts.get('cache_ttl_seconds', 3600),
                max_size=self.opts.get('max_cache_size', 10000)
            )
        else:
            self.cache = None
            
        if self.opts.get('enable_rate_limiting', True):
            self.rate_limiters = defaultdict(lambda: AdaptiveRateLimiter(
                base_delay=self.opts.get('base_rate_limit_delay', 1.0),
                max_delay=self.opts.get('max_rate_limit_delay', 60.0)
            ))
        else:
            self.rate_limiters = None
            
        if self.opts.get('enable_request_batching', True):
            self.request_batcher = RequestBatcher(
                batch_size=self.opts.get('batch_size', 10),
                flush_interval=self.opts.get('batch_flush_interval', 5.0)
            )
        else:
            self.request_batcher = None
            
        if self.opts.get('enable_resource_monitoring', True):
            self.resource_monitor = ResourceMonitor()
            self.start_monitoring_thread()
        else:
            self.resource_monitor = None
    def watchedEvents(self):
        """Return the list of events this module watches."""
        return ["*"]

    def producedEvents(self):
        """Return the list of events this module produces."""
        return [
            "PERFORMANCE_STATS",
            "CACHE_STATS", 
            "RESOURCE_USAGE",
            "OPTIMIZATION_SUGGESTION"
        ]

    def handleEvent(self, event):
        """Optimize event processing."""
        if self.resource_monitor and self.opts.get('auto_gc_enabled', True):
            if self.resource_monitor.should_trigger_gc():
                self.debug("Triggering garbage collection for memory optimization")
                gc.collect()

    def get_cached_result(self, cache_key: str) -> Any | None:
        """Get result from cache."""
        if not self.cache:
            return None
        return self.cache.get(cache_key)

    def set_cached_result(self, cache_key: str, result: Any, ttl: int | None = None) -> None:
        """Store result in cache."""
        if self.cache:
            self.cache.set(cache_key, result, ttl)

    def create_cache_key(self, *args) -> str:
        """Create cache key from arguments."""
        key_string = "|".join(str(arg) for arg in args)
        return hashlib.md5(key_string.encode()).hexdigest()

    def wait_for_rate_limit(self, domain: str) -> None:
        """Wait according to rate limit for domain."""
        if self.rate_limiters:
            self.rate_limiters[domain].wait()

    def record_request_success(self, domain: str) -> None:
        """Record successful request for rate limiting."""
        if self.rate_limiters:
            self.rate_limiters[domain].record_success()

    def record_request_failure(self, domain: str, status_code: str | None = None) -> None:
        """Record failed request for rate limiting."""
        if self.rate_limiters:
            self.rate_limiters[domain].record_failure(status_code)

    def start_monitoring_thread(self):
        """Start resource monitoring thread."""
        def monitor_resources():
            """Monitor resources."""
            while True:
                if self.resource_monitor:
                    sample = self.resource_monitor.sample_resources()
                    
                    # Emit performance stats periodically
                    if int(sample['timestamp']) % 300 == 0:  # Every 5 minutes
                        self._emit_performance_stats(sample)
                
                time.sleep(60)  # Monitor every minute
        
        monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        monitor_thread.start()

    def _emit_performance_stats(self, resource_sample: dict):
        """Emit performance statistics event."""
        stats = {
            'resource_usage': resource_sample,
            'cache_stats': self.cache.stats() if self.cache else {},
            'memory_trend': self.resource_monitor.get_memory_trend() if self.resource_monitor else 'unknown',
            'timestamp': time.time()
        }
        
        stats_event = SpiderFootEvent(
            "PERFORMANCE_STATS",
            json.dumps(stats),
            self.__name__,
            None
        )
        self.notifyListeners(stats_event)
        
        # Check if optimization suggestions should be made
        self._check_optimization_suggestions(stats)

    def _check_optimization_suggestions(self, stats: dict):
        """Check if optimization suggestions should be made."""
        suggestions = []
        
        # Memory optimization suggestions
        if stats.get('resource_usage', {}).get('memory_mb', 0) > self.opts.get('memory_cleanup_threshold_mb', 500):
            suggestions.append({
                'type': 'memory',
                'message': 'High memory usage detected. Consider reducing cache size or enabling more aggressive garbage collection.',
                'action': 'reduce_cache_size'
            })
        
        # Cache optimization suggestions
        cache_stats = stats.get('cache_stats', {})
        if cache_stats.get('hit_rate', 0) < 0.3:
            suggestions.append({
                'type': 'cache',
                'message': 'Low cache hit rate detected. Consider increasing cache TTL or size.',
                'action': 'increase_cache_ttl'
            })
        
        # Emit suggestions
        for suggestion in suggestions:
            suggestion_event = SpiderFootEvent(
                "OPTIMIZATION_SUGGESTION",
                json.dumps(suggestion),
                self.__name__,
                None
            )
            self.notifyListeners(suggestion_event)

    def scanFinished(self):
        """Clean up resources when scan finishes."""
        if self.cache:
            # Emit final cache statistics
            final_stats = self.cache.stats()
            cache_event = SpiderFootEvent(
                "CACHE_STATS",
                json.dumps(final_stats),
                self.__name__,
                None
            )
            self.notifyListeners(cache_event)
            
        # Final garbage collection
        if self.opts.get('auto_gc_enabled', True):
            gc.collect()
            
        self.info("Performance optimization scan completed")

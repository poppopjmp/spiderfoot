#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Optimization Framework for SpiderFoot

This module provides performance monitoring, optimization tools,
and caching mechanisms for SpiderFoot operations.
"""

import time
import threading
import hashlib
import pickle
import json
import os
import psutil
import logging
from typing import Dict, Any, Callable, Optional, Union
from functools import wraps, lru_cache
from collections import defaultdict, deque
from datetime import datetime, timedelta
import sqlite3
import redis
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import asyncio
import aiohttp
import weakref


class PerformanceProfiler:
    """Performance profiling and monitoring."""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.current_operations = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger('spiderfoot.performance')
        
    def profile_function(self, func_name: str = None):
        """Decorator to profile function execution."""
        def decorator(func):
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                start_memory = psutil.Process().memory_info().rss
                
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    end_memory = psutil.Process().memory_info().rss
                    
                    duration = end_time - start_time
                    memory_delta = end_memory - start_memory
                    
                    self._record_metric(name, duration, memory_delta)
                    
            return wrapper
        return decorator
    
    def _record_metric(self, operation: str, duration: float, memory_delta: int):
        """Record performance metric."""
        with self.lock:
            self.metrics[operation].append({
                'timestamp': datetime.now(),
                'duration': duration,
                'memory_delta': memory_delta
            })
            
            # Log slow operations
            if duration > 5.0:
                self.logger.warning(f"Slow operation: {operation} took {duration:.2f}s")
    
    def get_statistics(self, operation: str = None) -> Dict[str, Any]:
        """Get performance statistics."""
        with self.lock:
            if operation:
                metrics = self.metrics.get(operation, [])
                if not metrics:
                    return {}
                
                durations = [m['duration'] for m in metrics]
                return {
                    'operation': operation,
                    'count': len(durations),
                    'total_time': sum(durations),
                    'avg_time': sum(durations) / len(durations),
                    'min_time': min(durations),
                    'max_time': max(durations),
                    'recent_calls': len([m for m in metrics if datetime.now() - m['timestamp'] < timedelta(hours=1)])
                }
            else:
                return {op: self.get_statistics(op) for op in self.metrics.keys()}


class CacheManager:
    """Multi-layer caching system."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.memory_cache = {}
        self.cache_stats = defaultdict(int)
        self.lock = threading.Lock()
        
        # Initialize Redis if configured
        self.redis_client = None
        if self.config.get('redis_enabled'):
            try:
                self.redis_client = redis.Redis(
                    host=self.config.get('redis_host', 'localhost'),
                    port=self.config.get('redis_port', 6379),
                    db=self.config.get('redis_db', 0),
                    decode_responses=True
                )
                self.redis_client.ping()  # Test connection
            except Exception as e:
                logging.warning(f"Redis connection failed: {e}")
                self.redis_client = None
    
    def cache_result(self, ttl: int = 3600, use_redis: bool = False):
        """Decorator for caching function results."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Create cache key
                cache_key = self._create_cache_key(func.__name__, args, kwargs)
                
                # Try to get from cache
                cached_result = self._get_from_cache(cache_key, use_redis)
                if cached_result is not None:
                    self.cache_stats['hits'] += 1
                    return cached_result
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                self._store_in_cache(cache_key, result, ttl, use_redis)
                self.cache_stats['misses'] += 1
                
                return result
            return wrapper
        return decorator
    
    def _create_cache_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Create a cache key from function name and arguments."""
        key_data = {
            'func': func_name,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_from_cache(self, key: str, use_redis: bool = False):
        """Get value from cache."""
        # Try Redis first if enabled
        if use_redis and self.redis_client:
            try:
                cached = self.redis_client.get(f"spiderfoot:{key}")
                if cached:
                    return pickle.loads(cached.encode('latin-1'))
            except Exception:
                pass
        
        # Try memory cache
        with self.lock:
            cache_entry = self.memory_cache.get(key)
            if cache_entry and cache_entry['expires'] > time.time():
                return cache_entry['value']
            elif cache_entry:
                del self.memory_cache[key]
        
        return None
    
    def _store_in_cache(self, key: str, value: Any, ttl: int, use_redis: bool = False):
        """Store value in cache."""
        # Store in Redis if enabled
        if use_redis and self.redis_client:
            try:
                pickled_value = pickle.dumps(value)
                self.redis_client.setex(f"spiderfoot:{key}", ttl, pickled_value.decode('latin-1'))
            except Exception:
                pass
        
        # Store in memory cache
        with self.lock:
            self.memory_cache[key] = {
                'value': value,
                'expires': time.time() + ttl
            }
            
            # Cleanup expired entries occasionally
            if len(self.memory_cache) > 1000:
                self._cleanup_memory_cache()
    
    def _cleanup_memory_cache(self):
        """Clean up expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.memory_cache.items()
            if entry['expires'] <= current_time
        ]
        for key in expired_keys:
            del self.memory_cache[key]
    
    def invalidate_cache(self, pattern: str = None):
        """Invalidate cache entries."""
        if pattern:
            # Invalidate specific pattern
            with self.lock:
                keys_to_delete = [key for key in self.memory_cache.keys() if pattern in key]
                for key in keys_to_delete:
                    del self.memory_cache[key]
        else:
            # Clear all cache
            with self.lock:
                self.memory_cache.clear()
            
            if self.redis_client:
                try:
                    for key in self.redis_client.scan_iter(match="spiderfoot:*"):
                        self.redis_client.delete(key)
                except Exception:
                    pass


class DatabaseOptimizer:
    """Database performance optimization."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection_pool = []
        self.pool_lock = threading.Lock()
        self.max_connections = 10
        
    def get_connection(self):
        """Get database connection from pool."""
        with self.pool_lock:
            if self.connection_pool:
                return self.connection_pool.pop()
            else:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=MEMORY")
                return conn
    
    def return_connection(self, conn):
        """Return connection to pool."""
        with self.pool_lock:
            if len(self.connection_pool) < self.max_connections:
                self.connection_pool.append(conn)
            else:
                conn.close()
    
    def optimize_database(self):
        """Run database optimization tasks."""
        conn = self.get_connection()
        try:
            # Analyze tables for query optimization
            conn.execute("ANALYZE")
            
            # Vacuum database to reclaim space
            conn.execute("VACUUM")
            
            # Update statistics
            conn.execute("PRAGMA optimize")
            
            conn.commit()
        finally:
            self.return_connection(conn)


class AsyncHTTPManager:
    """Asynchronous HTTP request manager for better performance."""
    
    def __init__(self, max_concurrent: int = 100, timeout: int = 30):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.session = None
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=20,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_multiple(self, urls: list, headers: dict = None) -> list:
        """Fetch multiple URLs concurrently."""
        tasks = []
        for url in urls:
            task = asyncio.create_task(self._fetch_single(url, headers))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    
    async def _fetch_single(self, url: str, headers: dict = None):
        """Fetch a single URL."""
        try:
            async with self.session.get(url, headers=headers) as response:
                content = await response.text()
                return {
                    'url': url,
                    'status': response.status,
                    'content': content,
                    'headers': dict(response.headers)
                }
        except Exception as e:
            return {
                'url': url,
                'error': str(e)
            }


class ResourceMonitor:
    """Monitor system resources and throttle operations."""
    
    def __init__(self, cpu_threshold: float = 80.0, memory_threshold: float = 80.0):
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.logger = logging.getLogger('spiderfoot.resources')
        
    def check_resources(self) -> dict:
        """Check current resource usage."""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'disk_percent': disk.percent,
            'disk_free_gb': disk.free / (1024**3)
        }
    
    def should_throttle(self) -> bool:
        """Check if operations should be throttled."""
        resources = self.check_resources()
        
        if resources['cpu_percent'] > self.cpu_threshold:
            self.logger.warning(f"High CPU usage: {resources['cpu_percent']:.1f}%")
            return True
            
        if resources['memory_percent'] > self.memory_threshold:
            self.logger.warning(f"High memory usage: {resources['memory_percent']:.1f}%")
            return True
            
        return False
    
    def adaptive_delay(self) -> float:
        """Calculate adaptive delay based on resource usage."""
        resources = self.check_resources()
        
        cpu_factor = max(0, (resources['cpu_percent'] - 50) / 50)
        memory_factor = max(0, (resources['memory_percent'] - 50) / 50)
        
        delay = cpu_factor * 0.5 + memory_factor * 0.3
        return min(delay, 2.0)  # Max 2 second delay


class BatchProcessor:
    """Batch processing for improved efficiency."""
    
    def __init__(self, batch_size: int = 100, max_workers: int = None):
        self.batch_size = batch_size
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        
    def process_batch(self, items: list, processor_func: Callable, **kwargs):
        """Process items in batches with parallel execution."""
        results = []
        
        # Split items into batches
        batches = [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all batches
            future_to_batch = {
                executor.submit(self._process_single_batch, batch, processor_func, **kwargs): batch
                for batch in batches
            }
            
            # Collect results
            for future in as_completed(future_to_batch):
                try:
                    batch_results = future.result()
                    results.extend(batch_results)
                except Exception as e:
                    logging.error(f"Batch processing error: {e}")
        
        return results
    
    def _process_single_batch(self, batch: list, processor_func: Callable, **kwargs):
        """Process a single batch of items."""
        results = []
        for item in batch:
            try:
                result = processor_func(item, **kwargs)
                results.append(result)
            except Exception as e:
                logging.error(f"Error processing item {item}: {e}")
                results.append(None)
        return results


class MemoryManager:
    """Memory management and optimization."""
    
    def __init__(self):
        self.tracked_objects = weakref.WeakSet()
        self.logger = logging.getLogger('spiderfoot.memory')
        
    def track_object(self, obj):
        """Track object for memory monitoring."""
        self.tracked_objects.add(obj)
    
    def force_garbage_collection(self):
        """Force garbage collection and log memory usage."""
        import gc
        
        before = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        collected = gc.collect()
        after = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        self.logger.info(f"GC: Collected {collected} objects, freed {before - after:.1f} MB")
    
    def get_memory_usage(self) -> dict:
        """Get detailed memory usage information."""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'percent': process.memory_percent(),
            'tracked_objects': len(self.tracked_objects)
        }


# Performance optimization decorator
def optimize_performance(cache_ttl: int = 3600, profile: bool = True, use_async: bool = False):
    """Comprehensive performance optimization decorator."""
    def decorator(func):
        # Apply profiling
        if profile:
            profiler = PerformanceProfiler()
            func = profiler.profile_function()(func)
        
        # Apply caching
        cache_manager = CacheManager()
        func = cache_manager.cache_result(ttl=cache_ttl)(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Resource monitoring
            resource_monitor = ResourceMonitor()
            if resource_monitor.should_throttle():
                delay = resource_monitor.adaptive_delay()
                time.sleep(delay)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Example usage
if __name__ == "__main__":
    # Example performance-optimized function
    @optimize_performance(cache_ttl=1800, profile=True)
    def expensive_operation(data):
        """Example expensive operation."""
        time.sleep(0.1)  # Simulate work
        return len(data) * 2
    
    # Test the function
    result = expensive_operation("test data")
    print(f"Result: {result}")
    
    # Test batch processing
    batch_processor = BatchProcessor(batch_size=10)
    items = list(range(100))
    results = batch_processor.process_batch(items, lambda x: x * 2)
    print(f"Batch results count: {len(results)}")
    
    # Test resource monitoring
    resource_monitor = ResourceMonitor()
    resources = resource_monitor.check_resources()
    print(f"Resource usage: {resources}")

"""
Performance optimization enhancements for SpiderFoot WebUI
"""

import asyncio
import concurrent.futures
import functools
import time
import logging
from typing import Dict, Any, Optional, Callable
import threading
import weakref


class WebUIPerformanceEnhancer:
    """Performance enhancement utilities for WebUI operations"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.cache = {}
        self.cache_lock = threading.RLock()
        self.cache_ttl = {}
        self.logger = logging.getLogger(__name__)
        
    def cache_with_ttl(self, ttl_seconds: int = 300):
        """Decorator for caching function results with TTL"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Create cache key
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
                
                with self.cache_lock:
                    # Check if cached result exists and is still valid
                    if cache_key in self.cache:
                        cached_time = self.cache_ttl.get(cache_key, 0)
                        if time.time() - cached_time < ttl_seconds:
                            self.logger.debug(f"Cache hit for {func.__name__}")
                            return self.cache[cache_key]
                        else:
                            # Remove expired cache entry
                            del self.cache[cache_key]
                            del self.cache_ttl[cache_key]
                
                # Execute function and cache result
                result = func(*args, **kwargs)
                
                with self.cache_lock:
                    self.cache[cache_key] = result
                    self.cache_ttl[cache_key] = time.time()
                
                self.logger.debug(f"Cached result for {func.__name__}")
                return result
            return wrapper
        return decorator
    
    def async_operation(self, func: Callable, *args, **kwargs):
        """Execute operation asynchronously"""
        future = self.executor.submit(func, *args, **kwargs)
        return future
    
    def batch_operation(self, func: Callable, items: list, batch_size: int = 10):
        """Execute operations in batches to improve performance"""
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            batch_futures = []
            
            for item in batch:
                future = self.executor.submit(func, item)
                batch_futures.append(future)
            
            # Wait for batch to complete
            for future in concurrent.futures.as_completed(batch_futures):
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Batch operation failed: {e}")
                    results.append(None)
        
        return results
    
    def clear_cache(self, pattern: Optional[str] = None):
        """Clear cache entries, optionally matching a pattern"""
        with self.cache_lock:
            if pattern:
                keys_to_remove = [k for k in self.cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del self.cache[key]
                    if key in self.cache_ttl:
                        del self.cache_ttl[key]
            else:
                self.cache.clear()
                self.cache_ttl.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.cache_lock:
            return {
                'total_entries': len(self.cache),
                'cache_size_mb': len(str(self.cache)) / (1024 * 1024),
                'oldest_entry': min(self.cache_ttl.values()) if self.cache_ttl else None,
                'newest_entry': max(self.cache_ttl.values()) if self.cache_ttl else None
            }


class PaginationOptimizer:
    """Optimized pagination for large datasets"""
    
    @staticmethod
    def optimize_pagination(data: list, page: int, per_page: int, 
                          max_memory_items: int = 10000) -> Dict[str, Any]:
        """
        Optimize pagination to handle large datasets efficiently
        
        Args:
            data: Full dataset
            page: Current page number (1-based)
            per_page: Items per page
            max_memory_items: Maximum items to keep in memory
            
        Returns:
            Paginated result with metadata
        """
        total_items = len(data)
        total_pages = (total_items + per_page - 1) // per_page
        
        # Calculate pagination bounds
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_items)
        
        # For very large datasets, implement memory-efficient pagination
        if total_items > max_memory_items:
            # This would typically involve database-level pagination
            # For now, we'll slice the data but in production this should
            # be handled at the data source level
            paginated_data = data[start_idx:end_idx]
        else:
            paginated_data = data[start_idx:end_idx]
        
        return {
            'data': paginated_data,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_previous': page > 1,
                'has_next': page < total_pages,
                'start_index': start_idx + 1,
                'end_index': end_idx
            }
        }


class DataCompressionHelper:
    """Helper for compressing large data transfers"""
    
    @staticmethod
    def compress_json_response(data: Dict[str, Any], 
                             compression_threshold: int = 1024) -> Dict[str, Any]:
        """
        Compress JSON response if it exceeds threshold
        
        Args:
            data: Response data
            compression_threshold: Minimum size in bytes to trigger compression
            
        Returns:
            Potentially compressed response with metadata
        """
        import json
        import gzip
        import base64
        
        json_str = json.dumps(data)
        original_size = len(json_str.encode('utf-8'))
        
        if original_size < compression_threshold:
            return {
                'data': data,
                'compressed': False,
                'original_size': original_size
            }
        
        # Compress the data
        compressed_data = gzip.compress(json_str.encode('utf-8'))
        compressed_b64 = base64.b64encode(compressed_data).decode('utf-8')
        
        compression_ratio = len(compressed_data) / original_size
        
        return {
            'data': compressed_b64,
            'compressed': True,
            'original_size': original_size,
            'compressed_size': len(compressed_data),
            'compression_ratio': compression_ratio,
            'encoding': 'gzip+base64'
        }


class MemoryOptimizer:
    """Memory optimization utilities"""
    
    def __init__(self):
        self.object_pool = weakref.WeakValueDictionary()
        self.logger = logging.getLogger(__name__)
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics"""
        import psutil
        import os
        
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': process.memory_percent(),
                'available_mb': psutil.virtual_memory().available / (1024 * 1024)
            }
        except ImportError:
            return {'error': 'psutil not available'}
        except Exception as e:
            return {'error': str(e)}
    
    def optimize_large_list(self, data: list, chunk_size: int = 1000):
        """Generator for processing large lists in chunks"""
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]
    
    def cleanup_resources(self):
        """Cleanup unused resources"""
        import gc
        
        # Force garbage collection
        collected = gc.collect()
        self.logger.info(f"Garbage collection freed {collected} objects")
        
        # Clear object pool
        self.object_pool.clear()


class AsyncWebUIHelper:
    """Async utilities for WebUI operations"""
    
    @staticmethod
    async def fetch_multiple_endpoints(urls: list, timeout: int = 30) -> list:
        """
        Fetch multiple endpoints concurrently
        
        Args:
            urls: List of URLs to fetch
            timeout: Request timeout in seconds
            
        Returns:
            List of responses
        """
        import aiohttp
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            tasks = []
            for url in urls:
                task = asyncio.create_task(AsyncWebUIHelper._fetch_url(session, url))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
    
    @staticmethod
    async def _fetch_url(session, url):
        """Fetch a single URL"""
        try:
            async with session.get(url) as response:
                return {
                    'url': url,
                    'status': response.status,
                    'data': await response.text()
                }
        except Exception as e:
            return {
                'url': url,
                'error': str(e)
            }


# Performance monitoring decorator
def monitor_performance(func: Callable) -> Callable:
    """Decorator to monitor function performance"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger = logging.getLogger(__name__)
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(f"Function {func.__name__} executed in {execution_time:.3f}s")
            
            # Log performance warnings for slow operations
            if execution_time > 5.0:
                logger.warning(f"Slow operation detected: {func.__name__} took {execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Function {func.__name__} failed after {execution_time:.3f}s: {e}")
            raise
    
    return wrapper


# Global performance enhancer instance
performance_enhancer = WebUIPerformanceEnhancer()


# Enhanced WebUI methods with performance optimizations
class PerformanceEnhancedWebUI:
    """Mixin class with performance-enhanced WebUI methods"""
    
    def __init__(self):
        self.performance_enhancer = performance_enhancer
        self.pagination_optimizer = PaginationOptimizer()
        self.memory_optimizer = MemoryOptimizer()
    
    @monitor_performance
    def get_scan_results_optimized(self, scan_id: str, page: int = 1, 
                                 per_page: int = 100) -> Dict[str, Any]:
        """
        Optimized scan results retrieval with pagination and caching
        """
        @self.performance_enhancer.cache_with_ttl(ttl_seconds=60)
        def _fetch_scan_results(scan_id: str):
            # This would call the actual database method
            # For now, return a placeholder
            return list(range(1000))  # Simulate large dataset
        
        # Get cached or fresh data
        all_results = _fetch_scan_results(scan_id)
        
        # Apply optimized pagination
        paginated_result = self.pagination_optimizer.optimize_pagination(
            all_results, page, per_page
        )
        
        return paginated_result
    
    @monitor_performance
    def get_system_performance_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive system performance metrics
        """
        metrics = {
            'memory': self.memory_optimizer.get_memory_usage(),
            'cache': self.performance_enhancer.get_cache_stats(),
            'timestamp': time.time()
        }
        
        return metrics
    
    @monitor_performance
    def get_cached_scan_data(self, scan_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get cached scan data with optional force refresh
        """
        cache_key = f"scan_data_{scan_id}"
        
        if force_refresh or not self.performance_enhancer.has_cache(cache_key):
            # Fetch fresh data from database
            # This would be replaced with actual database call
            data = {
                'scan_id': scan_id,
                'status': 'completed',
                'results_count': 100,
                'cached_at': time.time()
            }
            self.performance_enhancer.set_cache(cache_key, data, ttl_seconds=300)
            return data
        else:
            return self.performance_enhancer.get_cache(cache_key)

    def optimize_large_export(self, scan_ids: list, export_format: str) -> str:
        """
        Optimized export for large datasets using streaming and compression
        """
        @monitor_performance
        def _export_batch(scan_batch):
            # Simulate export processing
            return f"exported_data_for_{len(scan_batch)}_scans"
        
        # Process in batches
        batch_results = self.performance_enhancer.batch_operation(
            _export_batch, scan_ids, batch_size=5
        )
        
        # Combine results
        combined_result = "\\n".join(filter(None, batch_results))
        
        # Compress if large
        compression_result = DataCompressionHelper.compress_json_response(
            {'export_data': combined_result}
        )
        
        return compression_result
    
    def cleanup_performance_resources(self):
        """
        Cleanup performance-related resources
        """
        self.performance_enhancer.clear_cache()
        self.memory_optimizer.cleanup_resources()

# -*- coding: utf-8 -*-
"""
Rate Limiting Module for SpiderFoot API and Web Interface
Provides protection against abuse and DoS attacks.
"""

import time
import redis
from typing import Dict, Optional, Tuple
from functools import wraps
from flask import request, jsonify, g
import hashlib


class RateLimiter:
    """Rate limiting implementation with Redis backend."""
    
    def __init__(self, redis_client=None, redis_host='localhost', redis_port=6379, redis_db=0):
        """Initialize rate limiter.
        
        Args:
            redis_client: Existing Redis client instance
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
        """
        if redis_client:
            self.redis = redis_client
        else:
            try:
                self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, 
                                       decode_responses=True)
                # Test connection
                self.redis.ping()
            except (redis.ConnectionError, redis.RedisError):
                # Fallback to in-memory rate limiting
                self.redis = None
                self._memory_store = {}
        
        # Default rate limit configurations
        self.limits = {
            'api': {
                'requests': 100,
                'window': 3600,  # 1 hour
                'burst': 10,
                'burst_window': 60  # 1 minute
            },
            'web': {
                'requests': 300,
                'window': 3600,  # 1 hour
                'burst': 30,
                'burst_window': 60  # 1 minute
            },
            'scan': {
                'requests': 10,
                'window': 3600,  # 1 hour
                'burst': 2,
                'burst_window': 300  # 5 minutes
            },
            'login': {
                'requests': 5,
                'window': 900,  # 15 minutes
                'burst': 3,
                'burst_window': 60  # 1 minute
            }
        }
    
    def _get_client_id(self) -> str:
        """Get unique client identifier.
        
        Returns:
            Unique client identifier
        """
        # Try to get authenticated user ID first
        if hasattr(g, 'user_id') and g.user_id:
            return f"user:{g.user_id}"
        
        # Fall back to IP address
        client_ip = request.environ.get('HTTP_X_REAL_IP', 
                                       request.environ.get('HTTP_X_FORWARDED_FOR', 
                                                         request.remote_addr))
        
        # Handle X-Forwarded-For header with multiple IPs
        if ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        return f"ip:{client_ip}"
    
    def _get_rate_limit_key(self, client_id: str, limit_type: str, window_type: str = 'main') -> str:
        """Generate rate limit key for Redis.
        
        Args:
            client_id: Client identifier
            limit_type: Type of rate limit (api, web, scan, login)
            window_type: Window type (main, burst)
            
        Returns:
            Redis key for rate limiting
        """
        timestamp = int(time.time())
        config = self.limits[limit_type]
        
        if window_type == 'burst':
            window_size = config['burst_window']
        else:
            window_size = config['window']
        
        window = timestamp // window_size
        
        # Hash client_id for privacy
        client_hash = hashlib.sha256(client_id.encode()).hexdigest()[:16]
        
        return f"rate_limit:{limit_type}:{window_type}:{client_hash}:{window}"
    
    def _check_redis_limit(self, client_id: str, limit_type: str) -> Tuple[bool, Dict]:
        """Check rate limit using Redis backend.
        
        Args:
            client_id: Client identifier
            limit_type: Type of rate limit
            
        Returns:
            Tuple of (allowed, info_dict)
        """
        config = self.limits[limit_type]
        
        # Check main window
        main_key = self._get_rate_limit_key(client_id, limit_type, 'main')
        burst_key = self._get_rate_limit_key(client_id, limit_type, 'burst')
        
        pipe = self.redis.pipeline()
        
        # Increment both counters
        pipe.incr(main_key)
        pipe.expire(main_key, config['window'])
        pipe.incr(burst_key)
        pipe.expire(burst_key, config['burst_window'])
        
        results = pipe.execute()
        main_count = results[0]
        burst_count = results[2]
        
        # Check limits
        main_exceeded = main_count > config['requests']
        burst_exceeded = burst_count > config['burst']
        
        allowed = not (main_exceeded or burst_exceeded)
        
        info = {
            'allowed': allowed,
            'main_count': main_count,
            'main_limit': config['requests'],
            'main_remaining': max(0, config['requests'] - main_count),
            'main_reset': int(time.time()) + config['window'],
            'burst_count': burst_count,
            'burst_limit': config['burst'],
            'burst_remaining': max(0, config['burst'] - burst_count),
            'burst_reset': int(time.time()) + config['burst_window']
        }
        
        return allowed, info
    
    def _check_memory_limit(self, client_id: str, limit_type: str) -> Tuple[bool, Dict]:
        """Check rate limit using in-memory storage (fallback).
        
        Args:
            client_id: Client identifier
            limit_type: Type of rate limit
            
        Returns:
            Tuple of (allowed, info_dict)
        """
        current_time = time.time()
        config = self.limits[limit_type]
        
        # Clean old entries periodically
        if len(self._memory_store) > 10000:
            cutoff = current_time - max(config['window'], config['burst_window'])
            self._memory_store = {
                k: v for k, v in self._memory_store.items() 
                if any(timestamp > cutoff for timestamp in v)
            }
        
        # Get or create client record
        if client_id not in self._memory_store:
            self._memory_store[client_id] = []
        
        timestamps = self._memory_store[client_id]
        
        # Remove old timestamps
        main_cutoff = current_time - config['window']
        burst_cutoff = current_time - config['burst_window']
        
        recent_main = [t for t in timestamps if t > main_cutoff]
        recent_burst = [t for t in timestamps if t > burst_cutoff]
        
        # Check limits
        main_exceeded = len(recent_main) >= config['requests']
        burst_exceeded = len(recent_burst) >= config['burst']
        
        allowed = not (main_exceeded or burst_exceeded)
        
        if allowed:
            # Add current timestamp
            timestamps.append(current_time)
            # Keep only recent timestamps
            self._memory_store[client_id] = [t for t in timestamps if t > burst_cutoff]
        
        info = {
            'allowed': allowed,
            'main_count': len(recent_main) + (1 if allowed else 0),
            'main_limit': config['requests'],
            'main_remaining': max(0, config['requests'] - len(recent_main) - (1 if allowed else 0)),
            'main_reset': int(current_time + config['window']),
            'burst_count': len(recent_burst) + (1 if allowed else 0),
            'burst_limit': config['burst'],
            'burst_remaining': max(0, config['burst'] - len(recent_burst) - (1 if allowed else 0)),
            'burst_reset': int(current_time + config['burst_window'])
        }
        
        return allowed, info
    
    def check_rate_limit(self, limit_type: str = 'api') -> Tuple[bool, Dict]:
        """Check if request is within rate limits.
        
        Args:
            limit_type: Type of rate limit to check
            
        Returns:
            Tuple of (allowed, info_dict)
        """
        client_id = self._get_client_id()
        
        if self.redis:
            try:
                return self._check_redis_limit(client_id, limit_type)
            except (redis.ConnectionError, redis.RedisError):
                # Fallback to memory store
                return self._check_memory_limit(client_id, limit_type)
        else:
            return self._check_memory_limit(client_id, limit_type)
    
    def is_rate_limited(self, limit_type: str = 'api') -> bool:
        """Check if client is rate limited.
        
        Args:
            limit_type: Type of rate limit to check
            
        Returns:
            True if rate limited
        """
        allowed, _ = self.check_rate_limit(limit_type)
        return not allowed
    
    def get_rate_limit_info(self, limit_type: str = 'api') -> Dict:
        """Get rate limit information without incrementing counters.
        
        Args:
            limit_type: Type of rate limit to check
            
        Returns:
            Rate limit information dictionary
        """
        # This is a simplified version - in a real implementation,
        # you'd want separate methods to check without incrementing
        _, info = self.check_rate_limit(limit_type)
        return info


def rate_limit(limit_type: str = 'api'):
    """Decorator to apply rate limiting to Flask routes.
    
    Args:
        limit_type: Type of rate limit to apply
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get rate limiter from app context
            from flask import current_app
            
            if not hasattr(current_app, 'rate_limiter'):
                # Initialize rate limiter if not exists
                current_app.rate_limiter = RateLimiter()
            
            rate_limiter = current_app.rate_limiter
            allowed, info = rate_limiter.check_rate_limit(limit_type)
            
            if not allowed:
                response = jsonify({
                    'error': 'Rate limit exceeded',
                    'message': f'Too many requests. Limit: {info["main_limit"]} per hour, {info["burst_limit"]} per minute',
                    'retry_after': min(info['main_reset'], info['burst_reset']) - int(time.time())
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(min(info['main_reset'], info['burst_reset']) - int(time.time()))
                response.headers['X-RateLimit-Limit'] = str(info['main_limit'])
                response.headers['X-RateLimit-Remaining'] = str(info['main_remaining'])
                response.headers['X-RateLimit-Reset'] = str(info['main_reset'])
                return response
            
            # Add rate limit headers to successful responses
            response = f(*args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(info['main_limit'])
                response.headers['X-RateLimit-Remaining'] = str(info['main_remaining'])
                response.headers['X-RateLimit-Reset'] = str(info['main_reset'])
            
            return response
        return decorated_function
    return decorator


# Convenience decorators for different limit types
def api_rate_limit(f):
    """Apply API rate limiting."""
    return rate_limit('api')(f)


def web_rate_limit(f):
    """Apply web interface rate limiting."""
    return rate_limit('web')(f)


def scan_rate_limit(f):
    """Apply scan operation rate limiting."""
    return rate_limit('scan')(f)


def login_rate_limit(f):
    """Apply login attempt rate limiting."""
    return rate_limit('login')(f)

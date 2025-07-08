# -*- coding: utf-8 -*-
"""
Rate Limiting Module for SpiderFoot API and Web Interface
Provides protection against abuse and DoS attacks for both CherryPy and FastAPI.
"""

import time
import redis
from typing import Dict, Optional, Tuple, Union
from functools import wraps
import hashlib
import cherrypy
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class RateLimiter:
    """Rate limiting implementation with Redis backend for CherryPy and FastAPI."""
    
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
    
    def _get_client_id(self, request=None) -> str:
        """Get unique client identifier for CherryPy or FastAPI.
        
        Args:
            request: FastAPI request object (optional)
            
        Returns:
            Unique client identifier
        """
        # For FastAPI
        if request and hasattr(request, 'client'):
            # Try to get authenticated user ID first
            if hasattr(request.state, 'user_id') and request.state.user_id:
                return f"user:{request.state.user_id}"
            
            # Fall back to IP address
            client_ip = request.client.host
            forwarded_for = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            if forwarded_for:
                client_ip = forwarded_for
            return f"ip:{client_ip}"
        
        # For CherryPy
        try:
            # Try to get authenticated user ID first
            if hasattr(cherrypy.session, 'user_id') and cherrypy.session.user_id:
                return f"user:{cherrypy.session.user_id}"
            
            # Fall back to IP address
            client_ip = cherrypy.request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            if not client_ip:
                client_ip = cherrypy.request.headers.get('X-Real-IP', '')
            if not client_ip:
                client_ip = getattr(cherrypy.request, 'remote', {}).get('ip', 'unknown')
            
            return f"ip:{client_ip}"
        except AttributeError:
            return "unknown"
    
    def _get_rate_limit_key(self, client_id: str, limit_type: str, window_type: str = 'main') -> str:
        """Generate rate limit key for Redis."""
        return f"ratelimit:{limit_type}:{window_type}:{client_id}"
    
    def _check_redis_limit(self, client_id: str, limit_type: str) -> Tuple[bool, Dict]:
        """Check rate limit using Redis backend."""
        config = self.limits.get(limit_type, self.limits['api'])
        current_time = int(time.time())
        
        # Main rate limit check
        main_key = self._get_rate_limit_key(client_id, limit_type, 'main')
        main_window_start = current_time - config['window']
        
        # Remove old entries
        self.redis.zremrangebyscore(main_key, 0, main_window_start)
        
        # Count current requests in window
        current_requests = self.redis.zcard(main_key)
        
        # Check main rate limit
        if current_requests >= config['requests']:
            return False, {
                'limit': config['requests'],
                'remaining': 0,
                'reset': main_window_start + config['window'],
                'retry_after': config['window']
            }
        
        # Burst rate limit check
        burst_key = self._get_rate_limit_key(client_id, limit_type, 'burst')
        burst_window_start = current_time - config['burst_window']
        
        # Remove old burst entries
        self.redis.zremrangebyscore(burst_key, 0, burst_window_start)
        
        # Count current burst requests
        burst_requests = self.redis.zcard(burst_key)
        
        # Check burst rate limit
        if burst_requests >= config['burst']:
            return False, {
                'limit': config['burst'],
                'remaining': 0,
                'reset': burst_window_start + config['burst_window'],
                'retry_after': config['burst_window']
            }
        
        # Add current request to both windows
        self.redis.zadd(main_key, {str(current_time): current_time})
        self.redis.zadd(burst_key, {str(current_time): current_time})
        
        # Set expiry for keys
        self.redis.expire(main_key, config['window'])
        self.redis.expire(burst_key, config['burst_window'])
        
        return True, {
            'limit': config['requests'],
            'remaining': config['requests'] - current_requests - 1,
            'reset': main_window_start + config['window'],
            'retry_after': 0
        }
    
    def _check_memory_limit(self, client_id: str, limit_type: str) -> Tuple[bool, Dict]:
        """Check rate limit using in-memory storage."""
        config = self.limits.get(limit_type, self.limits['api'])
        current_time = time.time()
        
        # Initialize client data if not exists
        if client_id not in self._memory_store:
            self._memory_store[client_id] = {}
        
        client_data = self._memory_store[client_id]
        
        # Initialize limit type data if not exists
        if limit_type not in client_data:
            client_data[limit_type] = {
                'requests': [],
                'burst_requests': []
            }
        
        limit_data = client_data[limit_type]
        
        # Clean old requests
        limit_data['requests'] = [
            req_time for req_time in limit_data['requests']
            if current_time - req_time <= config['window']
        ]
        
        limit_data['burst_requests'] = [
            req_time for req_time in limit_data['burst_requests']
            if current_time - req_time <= config['burst_window']
        ]
        
        # Check main rate limit
        if len(limit_data['requests']) >= config['requests']:
            oldest_request = min(limit_data['requests'])
            retry_after = config['window'] - (current_time - oldest_request)
            return False, {
                'limit': config['requests'],
                'remaining': 0,
                'reset': oldest_request + config['window'],
                'retry_after': max(0, retry_after)
            }
        
        # Check burst rate limit
        if len(limit_data['burst_requests']) >= config['burst']:
            oldest_burst = min(limit_data['burst_requests'])
            retry_after = config['burst_window'] - (current_time - oldest_burst)
            return False, {
                'limit': config['burst'],
                'remaining': 0,
                'reset': oldest_burst + config['burst_window'],
                'retry_after': max(0, retry_after)
            }
        
        # Add current request
        limit_data['requests'].append(current_time)
        limit_data['burst_requests'].append(current_time)
        
        return True, {
            'limit': config['requests'],
            'remaining': config['requests'] - len(limit_data['requests']),
            'reset': current_time + config['window'],
            'retry_after': 0
        }
    
    def check_rate_limit(self, limit_type: str = 'api', request=None) -> Tuple[bool, Dict]:
        """Check rate limit for client.
        
        Args:
            limit_type: Type of rate limit to check
            request: FastAPI request object (optional)
            
        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        client_id = self._get_client_id(request)
        
        if self.redis:
            try:
                return self._check_redis_limit(client_id, limit_type)
            except Exception as e:
                # Fall back to memory if Redis fails
                return self._check_memory_limit(client_id, limit_type)
        else:
            return self._check_memory_limit(client_id, limit_type)
    
    def is_rate_limited(self, limit_type: str = 'api', request=None) -> bool:
        """Check if client is rate limited.
        
        Args:
            limit_type: Type of rate limit to check
            request: FastAPI request object (optional)
            
        Returns:
            True if rate limited
        """
        allowed, _ = self.check_rate_limit(limit_type, request)
        return not allowed
    
    def get_rate_limit_info(self, limit_type: str = 'api', request=None) -> Dict:
        """Get rate limit information for client.
        
        Args:
            limit_type: Type of rate limit to check
            request: FastAPI request object (optional)
            
        Returns:
            Rate limit information
        """
        _, info = self.check_rate_limit(limit_type, request)
        return info


# CherryPy Decorators
def cherrypy_rate_limit(limit_type: str = 'api'):
    """CherryPy decorator to apply rate limiting to routes.
    
    Args:
        limit_type: Type of rate limit to apply
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get or create rate limiter instance
            rate_limiter = getattr(cherrypy.config.get('spiderfoot_security', {}), 'rate_limiter', None)
            if not rate_limiter:
                rate_limiter = RateLimiter()
            
            allowed, info = rate_limiter.check_rate_limit(limit_type)
            
            if not allowed:
                cherrypy.response.headers['X-RateLimit-Limit'] = str(info['limit'])
                cherrypy.response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                cherrypy.response.headers['X-RateLimit-Reset'] = str(int(info['reset']))
                if info['retry_after'] > 0:
                    cherrypy.response.headers['Retry-After'] = str(int(info['retry_after']))
                
                raise cherrypy.HTTPError(429, "Rate limit exceeded")
            
            # Add rate limit headers to successful responses
            cherrypy.response.headers['X-RateLimit-Limit'] = str(info['limit'])
            cherrypy.response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
            cherrypy.response.headers['X-RateLimit-Reset'] = str(int(info['reset']))
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


# FastAPI Dependencies and Middleware
def fastapi_rate_limit_dependency(limit_type: str = 'api'):
    """FastAPI dependency to check rate limits.
    
    Args:
        limit_type: Type of rate limit to apply
        
    Returns:
        FastAPI dependency function
    """
    def check_rate_limit(request: Request):
        """Check rate limit for request."""
        rate_limiter = RateLimiter()
        allowed, info = rate_limiter.check_rate_limit(limit_type, request)
        
        if not allowed:
            headers = {
                'X-RateLimit-Limit': str(info['limit']),
                'X-RateLimit-Remaining': str(info['remaining']),
                'X-RateLimit-Reset': str(int(info['reset'])),
            }
            if info['retry_after'] > 0:
                headers['Retry-After'] = str(int(info['retry_after']))
            
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers=headers
            )
        
        # Store rate limit info in request state for response headers
        request.state.rate_limit_info = info
        return True
    
    return check_rate_limit


class FastAPIRateLimitMiddleware:
    """FastAPI middleware for automatic rate limiting."""
    
    def __init__(self, app, default_limit_type: str = 'api'):
        """Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            default_limit_type: Default rate limit type
        """
        self.app = app
        self.default_limit_type = default_limit_type
        self.rate_limiter = RateLimiter()
    
    async def __call__(self, scope, receive, send):
        """Process request through rate limiting."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Create request object
        request = Request(scope, receive)
        
        # Determine rate limit type based on path
        limit_type = self.default_limit_type
        if request.url.path.startswith('/api/'):
            limit_type = 'api'
        elif request.url.path.startswith('/login') or request.url.path.startswith('/auth'):
            limit_type = 'login'
        elif request.method in ('POST', 'PUT', 'DELETE'):
            limit_type = 'scan'
        else:
            limit_type = 'web'
        
        # Check rate limit
        allowed, info = self.rate_limiter.check_rate_limit(limit_type, request)
        
        if not allowed:
            headers = [
                (b'x-ratelimit-limit', str(info['limit']).encode()),
                (b'x-ratelimit-remaining', str(info['remaining']).encode()),
                (b'x-ratelimit-reset', str(int(info['reset'])).encode()),
                (b'content-type', b'application/json'),
            ]
            if info['retry_after'] > 0:
                headers.append((b'retry-after', str(int(info['retry_after'])).encode()))
            
            response = {
                "detail": "Rate limit exceeded",
                "status_code": 429
            }
            
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": headers,
            })
            await send({
                "type": "http.response.body",
                "body": JSONResponse(response).body,
            })
            return
        
        # Store rate limit info for response headers
        request.state.rate_limit_info = info
        
        # Continue with the request
        await self.app(scope, receive, send)


# Convenience decorators for different limit types
def api_rate_limit(f):
    """Apply API rate limiting (CherryPy)."""
    return cherrypy_rate_limit('api')(f)


def web_rate_limit(f):
    """Apply web interface rate limiting (CherryPy)."""
    return cherrypy_rate_limit('web')(f)


def scan_rate_limit(f):
    """Apply scan operation rate limiting (CherryPy)."""
    return cherrypy_rate_limit('scan')(f)


def login_rate_limit(f):
    """Apply login attempt rate limiting (CherryPy)."""
    return cherrypy_rate_limit('login')(f)


# FastAPI convenience dependencies
def require_api_rate_limit():
    """Require API rate limit check (FastAPI)."""
    return fastapi_rate_limit_dependency('api')


def require_web_rate_limit():
    """Require web rate limit check (FastAPI)."""
    return fastapi_rate_limit_dependency('web')


def require_scan_rate_limit():
    """Require scan rate limit check (FastAPI)."""
    return fastapi_rate_limit_dependency('scan')


def require_login_rate_limit():
    """Require login rate limit check (FastAPI)."""
    return fastapi_rate_limit_dependency('login')

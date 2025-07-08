#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Security and Rate Limiting Framework for SpiderFoot

This module provides comprehensive API security including:
- Advanced rate limiting strategies
- API key management
- Request validation
- Security headers
- DDoS protection
"""

import time
import hashlib
import secrets
import jwt
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict, deque
import threading
import ipaddress
import re
from dataclasses import dataclass
import json


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_requests: int = 100
    window_seconds: int = 3600
    burst_limit: int = 10
    burst_window: int = 60


@dataclass
class APIKeyInfo:
    """API key information."""
    key_id: str
    hashed_key: str
    name: str
    permissions: List[str]
    rate_limits: RateLimitConfig
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    is_active: bool = True


class AdvancedRateLimiter:
    """Advanced rate limiting with multiple strategies."""
    
    def __init__(self):
        self.requests = defaultdict(deque)
        self.blocked_ips = {}
        self.suspicious_ips = defaultdict(int)
        self.lock = threading.Lock()
        self.logger = logging.getLogger('spiderfoot.ratelimit')
        
    def check_rate_limit(self, identifier: str, config: RateLimitConfig, 
                        request_weight: int = 1) -> tuple[bool, Dict[str, Any]]:
        """Check rate limits with multiple strategies."""
        current_time = time.time()
        
        with self.lock:
            # Check if identifier is blocked
            if identifier in self.blocked_ips:
                if current_time < self.blocked_ips[identifier]['until']:
                    return False, {
                        'error': 'rate_limited',
                        'retry_after': int(self.blocked_ips[identifier]['until'] - current_time),
                        'reason': 'temporarily_blocked'
                    }
                else:
                    del self.blocked_ips[identifier]
            
            # Clean old requests
            self._cleanup_old_requests(identifier, current_time, config.window_seconds)
            
            request_times = self.requests[identifier]
            
            # Check burst limit (short-term)
            burst_start = current_time - config.burst_window
            burst_count = sum(1 for req_time in request_times if req_time > burst_start)
            
            if burst_count + request_weight > config.burst_limit:
                self._handle_burst_violation(identifier, current_time)
                return False, {
                    'error': 'rate_limited',
                    'retry_after': config.burst_window,
                    'reason': 'burst_limit_exceeded'
                }
            
            # Check main rate limit (long-term)
            window_start = current_time - config.window_seconds
            window_count = sum(1 for req_time in request_times if req_time > window_start)
            
            if window_count + request_weight > config.max_requests:
                self._handle_rate_violation(identifier, current_time, config)
                return False, {
                    'error': 'rate_limited',
                    'retry_after': config.window_seconds,
                    'reason': 'rate_limit_exceeded'
                }
            
            # Add current requests
            for _ in range(request_weight):
                request_times.append(current_time)
            
            # Calculate remaining requests
            remaining = config.max_requests - (window_count + request_weight)
            burst_remaining = config.burst_limit - (burst_count + request_weight)
            
            return True, {
                'remaining': remaining,
                'burst_remaining': burst_remaining,
                'reset_time': int(window_start + config.window_seconds),
                'burst_reset_time': int(burst_start + config.burst_window)
            }
    
    def _cleanup_old_requests(self, identifier: str, current_time: float, window: int):
        """Clean up old request records."""
        cutoff_time = current_time - (window * 2)  # Keep some history
        request_times = self.requests[identifier]
        
        while request_times and request_times[0] <= cutoff_time:
            request_times.popleft()
    
    def _handle_burst_violation(self, identifier: str, current_time: float):
        """Handle burst limit violation."""
        self.suspicious_ips[identifier] += 1
        
        if self.suspicious_ips[identifier] >= 3:  # Multiple burst violations
            # Temporary block for 15 minutes
            self.blocked_ips[identifier] = {
                'until': current_time + 900,
                'reason': 'repeated_burst_violations'
            }
            self.logger.warning(f"Blocked {identifier} for repeated burst violations")
    
    def _handle_rate_violation(self, identifier: str, current_time: float, config: RateLimitConfig):
        """Handle rate limit violation."""
        self.suspicious_ips[identifier] += 1
        
        if self.suspicious_ips[identifier] >= 5:  # Multiple violations
            # Temporary block
            block_duration = min(3600, 300 * self.suspicious_ips[identifier])  # Max 1 hour
            self.blocked_ips[identifier] = {
                'until': current_time + block_duration,
                'reason': 'repeated_rate_violations'
            }
            self.logger.warning(f"Blocked {identifier} for {block_duration}s due to repeated violations")


class APIKeyManager:
    """Secure API key management."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.api_keys: Dict[str, APIKeyInfo] = {}
        self.key_usage = defaultdict(int)
        self.lock = threading.Lock()
        
    def generate_api_key(self, name: str, permissions: List[str], 
                        rate_limits: RateLimitConfig = None, 
                        expires_in_days: int = None) -> tuple[str, str]:
        """Generate a new API key."""
        # Generate random key
        raw_key = secrets.token_urlsafe(32)
        key_id = secrets.token_hex(8)
        
        # Hash the key for storage
        hashed_key = hashlib.sha256((raw_key + self.secret_key).encode()).hexdigest()
        
        # Set expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        # Create API key info
        api_key_info = APIKeyInfo(
            key_id=key_id,
            hashed_key=hashed_key,
            name=name,
            permissions=permissions or [],
            rate_limits=rate_limits or RateLimitConfig(),
            created_at=datetime.now(),
            expires_at=expires_at
        )
        
        with self.lock:
            self.api_keys[key_id] = api_key_info
        
        # Return the raw key (only time it's available in plain text)
        return f"sf_{key_id}_{raw_key}", key_id
    
    def validate_api_key(self, api_key: str) -> tuple[bool, Optional[APIKeyInfo], str]:
        """Validate API key and return key info."""
        try:
            # Parse key format: sf_{key_id}_{raw_key}
            if not api_key.startswith('sf_'):
                return False, None, "Invalid key format"
            
            parts = api_key[3:].split('_', 1)
            if len(parts) != 2:
                return False, None, "Invalid key format"
            
            key_id, raw_key = parts
            
            with self.lock:
                api_key_info = self.api_keys.get(key_id)
                
                if not api_key_info:
                    return False, None, "Key not found"
                
                if not api_key_info.is_active:
                    return False, None, "Key is inactive"
                
                # Check expiration
                if api_key_info.expires_at and datetime.now() > api_key_info.expires_at:
                    return False, None, "Key expired"
                
                # Validate key hash
                expected_hash = hashlib.sha256((raw_key + self.secret_key).encode()).hexdigest()
                if not secrets.compare_digest(expected_hash, api_key_info.hashed_key):
                    return False, None, "Invalid key"
                
                # Update last used
                api_key_info.last_used = datetime.now()
                self.key_usage[key_id] += 1
                
                return True, api_key_info, "Valid key"
                
        except Exception as e:
            return False, None, f"Validation error: {str(e)}"
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        with self.lock:
            if key_id in self.api_keys:
                self.api_keys[key_id].is_active = False
                return True
            return False
    
    def list_api_keys(self) -> List[Dict[str, Any]]:
        """List all API keys (without sensitive data)."""
        with self.lock:
            return [
                {
                    'key_id': info.key_id,
                    'name': info.name,
                    'permissions': info.permissions,
                    'created_at': info.created_at.isoformat(),
                    'expires_at': info.expires_at.isoformat() if info.expires_at else None,
                    'last_used': info.last_used.isoformat() if info.last_used else None,
                    'is_active': info.is_active,
                    'usage_count': self.key_usage.get(info.key_id, 0)
                }
                for info in self.api_keys.values()
            ]


class RequestValidator:
    """Advanced request validation."""
    
    # Suspicious patterns that might indicate attacks
    SUSPICIOUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',                # XSS
        r'data:text/html',            # Data URI XSS
        r'(\.\./){3,}',               # Path traversal
        r'(union|select|insert|delete|update|drop)\s+',  # SQL injection
        r'exec\s*\(',                 # Code execution
        r'eval\s*\(',                 # Code execution
        r'system\s*\(',               # System calls
        r'passthru\s*\(',             # System calls
        r'shell_exec\s*\(',           # System calls
        r'base64_decode\s*\(',        # Encoding attacks
        r'\${.*}',                    # Template injection
        r'<%.*%>',                    # Template injection
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.SUSPICIOUS_PATTERNS]
        self.logger = logging.getLogger('spiderfoot.validation')
    
    def validate_request(self, data: Dict[str, Any], headers: Dict[str, str] = None) -> tuple[bool, List[str]]:
        """Validate request data for security issues."""
        issues = []
        
        # Validate headers
        if headers:
            issues.extend(self._validate_headers(headers))
        
        # Validate request data
        issues.extend(self._validate_data(data))
        
        return len(issues) == 0, issues
    
    def _validate_headers(self, headers: Dict[str, str]) -> List[str]:
        """Validate HTTP headers."""
        issues = []
        
        # Check for suspicious user agents
        user_agent = headers.get('User-Agent', '').lower()
        if any(pattern in user_agent for pattern in ['sqlmap', 'nikto', 'nmap', 'dirb', 'burp']):
            issues.append("Suspicious User-Agent detected")
        
        # Check for unusual headers
        suspicious_headers = ['X-Forwarded-Host', 'X-Original-URL', 'X-Rewrite-URL']
        for header in suspicious_headers:
            if header in headers:
                self.logger.warning(f"Suspicious header detected: {header}")
        
        return issues
    
    def _validate_data(self, data: Any, path: str = "") -> List[str]:
        """Recursively validate data for suspicious patterns."""
        issues = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                issues.extend(self._validate_data(value, new_path))
                
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]" if path else f"[{i}]"
                issues.extend(self._validate_data(item, new_path))
                
        elif isinstance(data, str):
            issues.extend(self._validate_string(data, path))
        
        return issues
    
    def _validate_string(self, text: str, path: str) -> List[str]:
        """Validate string for suspicious patterns."""
        issues = []
        
        # Check length
        if len(text) > 50000:  # 50KB limit
            issues.append(f"String too long at {path}: {len(text)} chars")
        
        # Check for suspicious patterns
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                issues.append(f"Suspicious pattern detected at {path}: {pattern.pattern}")
                self.logger.warning(f"Suspicious pattern in {path}: {pattern.pattern}")
        
        return issues


class DDoSProtection:
    """DDoS protection mechanisms."""
    
    def __init__(self):
        self.request_counts = defaultdict(lambda: defaultdict(int))
        self.connection_counts = defaultdict(int)
        self.blocked_networks = set()
        self.lock = threading.Lock()
        
    def check_ddos_protection(self, client_ip: str, user_agent: str = None) -> tuple[bool, str]:
        """Check for DDoS patterns."""
        current_minute = int(time.time() // 60)
        
        with self.lock:
            # Check if IP is in blocked networks
            try:
                client_network = ipaddress.ip_network(f"{client_ip}/24", strict=False)
                if any(client_network.overlaps(blocked) for blocked in self.blocked_networks):
                    return False, "IP network is blocked"
            except ValueError:
                pass
            
            # Count requests per minute
            self.request_counts[client_ip][current_minute] += 1
            
            # Clean old counts (keep last 5 minutes)
            old_minutes = [minute for minute in self.request_counts[client_ip] if minute < current_minute - 5]
            for minute in old_minutes:
                del self.request_counts[client_ip][minute]
            
            # Check for rapid requests
            recent_requests = sum(self.request_counts[client_ip].values())
            if recent_requests > 300:  # 300 requests in 5 minutes
                self._block_network(client_ip)
                return False, "Too many requests from network"
            
            # Check for bot-like behavior
            if user_agent:
                if self._is_bot_like(user_agent, recent_requests):
                    return False, "Bot-like behavior detected"
        
        return True, "OK"
    
    def _block_network(self, ip: str):
        """Block entire network."""
        try:
            network = ipaddress.ip_network(f"{ip}/24", strict=False)
            self.blocked_networks.add(network)
            self.logger.warning(f"Blocked network {network} due to suspicious activity")
        except ValueError:
            pass
    
    def _is_bot_like(self, user_agent: str, request_count: int) -> bool:
        """Detect bot-like behavior."""
        user_agent = user_agent.lower()
        
        # High request count with simple user agent
        if request_count > 100 and len(user_agent) < 20:
            return True
        
        # Known bot patterns
        bot_patterns = ['bot', 'crawler', 'spider', 'scraper', 'wget', 'curl']
        if any(pattern in user_agent for pattern in bot_patterns):
            return request_count > 50
        
        return False


class APISecurityMiddleware:
    """Comprehensive API security middleware."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rate_limiter = AdvancedRateLimiter()
        self.api_key_manager = APIKeyManager(config.get('secret_key', 'default-secret'))
        self.request_validator = RequestValidator()
        self.ddos_protection = DDoSProtection()
        self.logger = logging.getLogger('spiderfoot.api.security')
        
    def process_request(self, request_data: Dict[str, Any], headers: Dict[str, str], 
                       client_ip: str) -> tuple[bool, Dict[str, Any]]:
        """Process and validate incoming request."""
        # DDoS protection
        ddos_ok, ddos_msg = self.ddos_protection.check_ddos_protection(
            client_ip, headers.get('User-Agent')
        )
        if not ddos_ok:
            return False, {'error': 'blocked', 'reason': ddos_msg}
        
        # API key validation
        api_key = headers.get('Authorization', '').replace('Bearer ', '')
        if api_key:
            valid, key_info, msg = self.api_key_manager.validate_api_key(api_key)
            if not valid:
                return False, {'error': 'invalid_api_key', 'reason': msg}
            
            # Rate limiting for API key
            rate_ok, rate_info = self.rate_limiter.check_rate_limit(
                f"key:{key_info.key_id}", key_info.rate_limits
            )
            if not rate_ok:
                return False, rate_info
                
        else:
            # Anonymous rate limiting (more restrictive)
            anonymous_config = RateLimitConfig(max_requests=10, window_seconds=3600, burst_limit=2)
            rate_ok, rate_info = self.rate_limiter.check_rate_limit(
                f"ip:{client_ip}", anonymous_config
            )
            if not rate_ok:
                return False, rate_info
        
        # Request validation
        valid, issues = self.request_validator.validate_request(request_data, headers)
        if not valid:
            self.logger.warning(f"Request validation failed from {client_ip}: {issues}")
            return False, {'error': 'invalid_request', 'issues': issues}
        
        return True, {'status': 'ok'}


def require_api_key(permissions: List[str] = None):
    """Decorator to require API key with specific permissions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # This would need to be integrated with your web framework
            # to extract the API key from headers
            api_key = kwargs.get('api_key') or (hasattr(args[0], 'headers') and args[0].headers.get('Authorization', '').replace('Bearer ', ''))
            
            if not api_key:
                raise ValueError("API key required")
            
            # Validate permissions (implementation depends on your security middleware)
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Example usage and configuration
if __name__ == "__main__":
    # Example configuration
    config = {
        'secret_key': secrets.token_urlsafe(32),
        'rate_limiting': {
            'default_max_requests': 1000,
            'default_window_seconds': 3600,
            'burst_limit': 10,
            'burst_window': 60
        }
    }
    
    # Initialize security middleware
    security = APISecurityMiddleware(config)
    
    # Generate an API key
    api_key, key_id = security.api_key_manager.generate_api_key(
        name="Test Key",
        permissions=["scan:create", "scan:read"],
        expires_in_days=30
    )
    
    print(f"Generated API key: {api_key}")
    print(f"Key ID: {key_id}")
    
    # Test request processing
    request_data = {"target": "example.com", "modules": ["dns"]}
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "SpiderFoot-Client/1.0"}
    client_ip = "192.168.1.100"
    
    success, result = security.process_request(request_data, headers, client_ip)
    print(f"Request validation: {success}, {result}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Security Framework for SpiderFoot

This module provides comprehensive security controls including:
- Input validation and sanitization
- Rate limiting and throttling
- Authentication and authorization
- API security measures
- Data protection
"""

import re
import hashlib
import secrets
import time
import threading
from typing import Dict, Any, Union, Optional, List
from datetime import datetime, timedelta
import logging
import ipaddress
from functools import wraps
import hmac
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    # Regex patterns for validation
    PATTERNS = {
        'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
        'domain': re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'),
        'ip': re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'),
        'url': re.compile(r'^https?://[^\s/$.?#].[^\s]*$'),
        'api_key': re.compile(r'^[a-zA-Z0-9_-]{16,128}$'),
        'username': re.compile(r'^[a-zA-Z0-9_-]{3,32}$'),
        'scan_name': re.compile(r'^[a-zA-Z0-9_\-\s]{1,100}$'),
    }
    
    # Dangerous characters and patterns
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>',
        r'javascript:',
        r'vbscript:',
        r'on\w+\s*=',
        r'eval\s*\(',
        r'expression\s*\(',
        r'import\s+',
        r'from\s+\w+\s+import',
        r'__import__',
        r'exec\s*\(',
        r'system\s*\(',
        r'popen\s*\(',
        r'subprocess\.',
        r'os\.',
        r'\.\./',
        r'\.\.\\',
    ]
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email address format."""
        if not email or len(email) > 254:
            return False
        return bool(cls.PATTERNS['email'].match(email))
    
    @classmethod
    def validate_domain(cls, domain: str) -> bool:
        """Validate domain name format."""
        if not domain or len(domain) > 253:
            return False
        return bool(cls.PATTERNS['domain'].match(domain))
    
    @classmethod
    def validate_ip(cls, ip: str) -> bool:
        """Validate IP address format."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate URL format."""
        if not url or len(url) > 2048:
            return False
        return bool(cls.PATTERNS['url'].match(url))
    
    @classmethod
    def sanitize_string(cls, input_str: str, max_length: int = 1000) -> str:
        """Sanitize string input to prevent injection attacks."""
        if not isinstance(input_str, str):
            input_str = str(input_str)
        
        # Truncate to max length
        input_str = input_str[:max_length]
        
        # Remove dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            input_str = re.sub(pattern, '', input_str, flags=re.IGNORECASE)
        
        # Remove control characters except newline and tab
        input_str = ''.join(char for char in input_str if ord(char) >= 32 or char in '\n\t')
        
        # HTML encode dangerous characters
        replacements = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '&': '&amp;',
        }
        
        for char, replacement in replacements.items():
            input_str = input_str.replace(char, replacement)
        
        return input_str.strip()
    
    @classmethod
    def validate_scan_target(cls, target: str) -> tuple[bool, str]:
        """Validate scan target (domain, IP, or URL)."""
        target = target.strip()
        
        if not target:
            return False, "Target cannot be empty"
        
        if len(target) > 1000:
            return False, "Target too long"
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, target, re.IGNORECASE):
                return False, f"Target contains dangerous pattern: {pattern}"
        
        # Validate as domain, IP, or URL
        if cls.validate_domain(target) or cls.validate_ip(target) or cls.validate_url(target):
            return True, "Valid target"
        
        return False, "Invalid target format"


class RateLimiter:
    """Rate limiting implementation with multiple strategies."""
    
    def __init__(self):
        self.requests = {}
        self.blocked_ips = {}
        self.lock = threading.Lock()
        
    def check_rate_limit(self, identifier: str, max_requests: int = 100, 
                        window_seconds: int = 3600) -> tuple[bool, int]:
        """Check if request is within rate limits."""
        current_time = time.time()
        
        with self.lock:
            # Clean old entries
            self._cleanup_old_entries(current_time, window_seconds)
            
            # Check if IP is blocked
            if identifier in self.blocked_ips:
                if current_time < self.blocked_ips[identifier]:
                    return False, 0
                else:
                    del self.blocked_ips[identifier]
            
            # Initialize or get request history
            if identifier not in self.requests:
                self.requests[identifier] = []
            
            requests_list = self.requests[identifier]
            
            # Count requests in current window
            window_start = current_time - window_seconds
            recent_requests = [req_time for req_time in requests_list if req_time > window_start]
            
            if len(recent_requests) >= max_requests:
                # Block IP for additional time if consistently over limit
                self.blocked_ips[identifier] = current_time + 900  # 15 minutes
                return False, 0
            
            # Add current request
            recent_requests.append(current_time)
            self.requests[identifier] = recent_requests
            
            remaining = max_requests - len(recent_requests)
            return True, remaining
    
    def _cleanup_old_entries(self, current_time: float, window_seconds: int):
        """Clean up old rate limit entries."""
        cutoff_time = current_time - (window_seconds * 2)  # Keep some extra history
        
        for identifier in list(self.requests.keys()):
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier] 
                if req_time > cutoff_time
            ]
            if not self.requests[identifier]:
                del self.requests[identifier]


class SecurityMiddleware:
    """Security middleware for request processing."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.rate_limiter = RateLimiter()
        self.logger = logging.getLogger('spiderfoot.security')
        
    def validate_request(self, request_data: Dict[str, Any], 
                        client_ip: str = None) -> tuple[bool, str]:
        """Validate incoming request."""
        # Rate limiting
        if client_ip:
            allowed, remaining = self.rate_limiter.check_rate_limit(
                client_ip, 
                max_requests=self.config.get('rate_limit_per_hour', 1000),
                window_seconds=3600
            )
            if not allowed:
                self.logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return False, "Rate limit exceeded"
        
        # Input validation
        for key, value in request_data.items():
            if isinstance(value, str):
                if not self._validate_input(key, value):
                    self.logger.warning(f"Invalid input detected: {key}")
                    return False, f"Invalid input: {key}"
        
        return True, "Valid request"
    
    def _validate_input(self, field_name: str, value: str) -> bool:
        """Validate individual input field."""
        # Check for dangerous patterns
        for pattern in InputValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        
        # Field-specific validation
        if field_name in ['email', 'target_email']:
            return InputValidator.validate_email(value)
        elif field_name in ['domain', 'target_domain']:
            return InputValidator.validate_domain(value)
        elif field_name in ['ip', 'target_ip']:
            return InputValidator.validate_ip(value)
        elif field_name in ['url', 'target_url']:
            return InputValidator.validate_url(value)
        
        # Generic string validation
        return len(value) <= 10000  # Reasonable max length


class AuthenticationManager:
    """Authentication and authorization management."""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or self._generate_secret_key()
        self.sessions = {}
        self.failed_attempts = {}
        self.lock = threading.Lock()
        
    def _generate_secret_key(self) -> str:
        """Generate a secure secret key."""
        return secrets.token_urlsafe(32)
    
    def hash_password(self, password: str, salt: str = None) -> tuple[str, str]:
        """Hash password with salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Use PBKDF2 with SHA-256
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key.decode(), salt
    
    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """Verify password against hash."""
        try:
            expected_hash, _ = self.hash_password(password, salt)
            return hmac.compare_digest(expected_hash, hashed)
        except Exception:
            return False
    
    def create_session(self, user_id: str, ip_address: str = None) -> str:
        """Create authenticated session."""
        session_id = secrets.token_urlsafe(32)
        
        with self.lock:
            self.sessions[session_id] = {
                'user_id': user_id,
                'created_at': datetime.now(),
                'ip_address': ip_address,
                'last_activity': datetime.now()
            }
        
        return session_id
    
    def validate_session(self, session_id: str, ip_address: str = None) -> tuple[bool, str]:
        """Validate session token."""
        with self.lock:
            session = self.sessions.get(session_id)
            
            if not session:
                return False, "Invalid session"
            
            # Check session age
            if datetime.now() - session['created_at'] > timedelta(hours=24):
                del self.sessions[session_id]
                return False, "Session expired"
            
            # Check IP address if provided
            if ip_address and session.get('ip_address') != ip_address:
                return False, "IP address mismatch"
            
            # Update last activity
            session['last_activity'] = datetime.now()
            
            return True, session['user_id']
    
    def check_failed_attempts(self, identifier: str) -> bool:
        """Check if identifier is blocked due to failed attempts."""
        with self.lock:
            attempts = self.failed_attempts.get(identifier, {'count': 0, 'last_attempt': None})
            
            # Reset counter if last attempt was more than 1 hour ago
            if attempts['last_attempt'] and datetime.now() - attempts['last_attempt'] > timedelta(hours=1):
                del self.failed_attempts[identifier]
                return True
            
            return attempts['count'] < 5  # Allow 5 failed attempts
    
    def record_failed_attempt(self, identifier: str):
        """Record failed authentication attempt."""
        with self.lock:
            if identifier not in self.failed_attempts:
                self.failed_attempts[identifier] = {'count': 0, 'last_attempt': None}
            
            self.failed_attempts[identifier]['count'] += 1
            self.failed_attempts[identifier]['last_attempt'] = datetime.now()


class DataProtection:
    """Data protection and encryption utilities."""
    
    def __init__(self, encryption_key: bytes = None):
        if encryption_key is None:
            encryption_key = Fernet.generate_key()
        self.cipher = Fernet(encryption_key)
        self.encryption_key = encryption_key
    
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not data:
            return data
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not encrypted_data:
            return encrypted_data
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception:
            raise ValueError("Failed to decrypt data")
    
    def hash_data(self, data: str) -> str:
        """Create hash of data for comparison."""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def mask_sensitive_data(self, data: str, mask_char: str = '*') -> str:
        """Mask sensitive data for logging."""
        if not data:
            return data
        
        if len(data) <= 4:
            return mask_char * len(data)
        
        # Show first 2 and last 2 characters
        return data[:2] + mask_char * (len(data) - 4) + data[-2:]


def security_header_middleware(response):
    """Add security headers to response."""
    headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
    }
    
    for header, value in headers.items():
        response.headers[header] = value
    
    return response


def require_authentication(auth_manager: AuthenticationManager):
    """Decorator for requiring authentication."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract session from request (implementation depends on framework)
            session_id = kwargs.get('session_id') or (args[0].headers.get('Authorization', '').replace('Bearer ', '') if args else None)
            
            if not session_id:
                raise ValueError("Authentication required")
            
            valid, user_id = auth_manager.validate_session(session_id)
            if not valid:
                raise ValueError("Invalid or expired session")
            
            kwargs['authenticated_user'] = user_id
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Example security configuration
SECURITY_CONFIG = {
    'rate_limit_per_hour': 1000,
    'max_failed_attempts': 5,
    'session_timeout_hours': 24,
    'password_min_length': 12,
    'require_special_chars': True,
    'encryption_enabled': True,
    'audit_logging': True
}


# Example usage
if __name__ == "__main__":
    # Initialize security components
    validator = InputValidator()
    rate_limiter = RateLimiter()
    auth_manager = AuthenticationManager()
    data_protection = DataProtection()
    
    # Test input validation
    print("Email validation:", validator.validate_email("test@example.com"))
    print("Domain validation:", validator.validate_domain("example.com"))
    print("Sanitized input:", validator.sanitize_string("<script>alert('xss')</script>"))
    
    # Test rate limiting
    allowed, remaining = rate_limiter.check_rate_limit("192.168.1.1", max_requests=10, window_seconds=60)
    print(f"Rate limit check: allowed={allowed}, remaining={remaining}")
    
    # Test authentication
    password_hash, salt = auth_manager.hash_password("secure_password_123")
    print("Password hashed successfully")
    
    # Test data protection
    sensitive_data = "api_key_12345"
    encrypted = data_protection.encrypt_sensitive_data(sensitive_data)
    decrypted = data_protection.decrypt_sensitive_data(encrypted)
    masked = data_protection.mask_sensitive_data(sensitive_data)
    print(f"Data protection: original={sensitive_data}, masked={masked}")

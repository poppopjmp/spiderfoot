# -*- coding: utf-8 -*-
"""
Input Validation and XSS Prevention Module for SpiderFoot
Provides comprehensive input sanitization and validation.
"""

import re
import html
import urllib.parse
from typing import Any, Dict, List, Optional, Union
import bleach


class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    # Common regex patterns for validation
    PATTERNS = {
        'email': re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'),
        'domain': re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'),
        'ip_address': re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'),
        'ipv6_address': re.compile(r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$|^::$'),
        'url': re.compile(r'^https?://[^\s/$.?#].[^\s]*$'),
        'api_key': re.compile(r'^[a-zA-Z0-9_-]{8,128}$'),
        'scan_id': re.compile(r'^[a-zA-Z0-9_-]{1,50}$'),
        'module_name': re.compile(r'^sfp_[a-zA-Z0-9_]{1,50}$'),
    }
    
    # Allowed HTML tags and attributes for content sanitization
    ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'code', 'pre']
    ALLOWED_ATTRIBUTES = {
        'a': ['href', 'title'],
        '*': ['class']
    }
    
    @classmethod
    def sanitize_html(cls, content: str) -> str:
        """Sanitize HTML content to prevent XSS.
        
        Args:
            content: Raw HTML content
            
        Returns:
            Sanitized HTML content
        """
        if not isinstance(content, str):
            return str(content)
        
        return bleach.clean(
            content,
            tags=cls.ALLOWED_TAGS,
            attributes=cls.ALLOWED_ATTRIBUTES,
            strip=True
        )
    
    @classmethod
    def escape_html(cls, content: str) -> str:
        """Escape HTML entities in content.
        
        Args:
            content: Content to escape
            
        Returns:
            HTML-escaped content
        """
        if not isinstance(content, str):
            content = str(content)
        return html.escape(content, quote=True)
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid email format
        """
        return bool(cls.PATTERNS['email'].match(email.lower()))
    
    @classmethod
    def validate_domain(cls, domain: str) -> bool:
        """Validate domain name format.
        
        Args:
            domain: Domain name to validate
            
        Returns:
            True if valid domain format
        """
        return bool(cls.PATTERNS['domain'].match(domain.lower()))
    
    @classmethod
    def validate_ip_address(cls, ip: str) -> bool:
        """Validate IP address (IPv4 or IPv6).
        
        Args:
            ip: IP address to validate
            
        Returns:
            True if valid IP address
        """
        return (cls.PATTERNS['ip_address'].match(ip) or 
                cls.PATTERNS['ipv6_address'].match(ip))
    
    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid URL format
        """
        return bool(cls.PATTERNS['url'].match(url))
    
    @classmethod
    def sanitize_api_key(cls, api_key: str) -> Optional[str]:
        """Sanitize and validate API key.
        
        Args:
            api_key: API key to sanitize
            
        Returns:
            Sanitized API key or None if invalid
        """
        if not isinstance(api_key, str):
            return None
        
        # Remove whitespace and validate format
        api_key = api_key.strip()
        if cls.PATTERNS['api_key'].match(api_key):
            return api_key
        return None
    
    @classmethod
    def sanitize_scan_input(cls, scan_target: str) -> Optional[str]:
        """Sanitize scan target input.
        
        Args:
            scan_target: Target to sanitize
            
        Returns:
            Sanitized target or None if invalid
        """
        if not isinstance(scan_target, str):
            return None
        
        scan_target = scan_target.strip().lower()
        
        # Validate against known patterns
        if (cls.validate_domain(scan_target) or 
            cls.validate_ip_address(scan_target) or 
            cls.validate_email(scan_target) or
            cls.validate_url(scan_target)):
            return scan_target
        
        return None
    
    @classmethod
    def sanitize_module_options(cls, options: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize module configuration options.
        
        Args:
            options: Module options dictionary
            
        Returns:
            Sanitized options dictionary
        """
        sanitized = {}
        
        for key, value in options.items():
            # Sanitize key
            if not isinstance(key, str) or not re.match(r'^[a-zA-Z0-9_-]{1,50}$', key):
                continue
            
            # Sanitize value based on type and key name
            if isinstance(value, str):
                if 'api_key' in key.lower() or 'password' in key.lower():
                    # Special handling for sensitive data
                    sanitized_value = cls.sanitize_api_key(value)
                    if sanitized_value:
                        sanitized[key] = sanitized_value
                elif 'url' in key.lower():
                    if cls.validate_url(value):
                        sanitized[key] = value
                else:
                    # General string sanitization
                    sanitized[key] = cls.escape_html(value)[:1000]  # Limit length
            elif isinstance(value, (int, float)):
                # Validate numeric ranges
                if -2147483648 <= value <= 2147483647:
                    sanitized[key] = value
            elif isinstance(value, bool):
                sanitized[key] = value
            elif isinstance(value, list):
                # Sanitize list items
                sanitized_list = []
                for item in value[:100]:  # Limit list size
                    if isinstance(item, str):
                        sanitized_list.append(cls.escape_html(item)[:100])
                    elif isinstance(item, (int, float, bool)):
                        sanitized_list.append(item)
                sanitized[key] = sanitized_list
        
        return sanitized
    
    @classmethod
    def validate_file_upload(cls, filename: str, content: bytes, 
                           allowed_extensions: List[str] = None,
                           max_size: int = 1024 * 1024) -> bool:
        """Validate file upload.
        
        Args:
            filename: Uploaded filename
            content: File content bytes
            allowed_extensions: List of allowed file extensions
            max_size: Maximum file size in bytes
            
        Returns:
            True if file is valid
        """
        if not filename or not content:
            return False
        
        # Check file size
        if len(content) > max_size:
            return False
        
        # Check file extension
        if allowed_extensions:
            extension = filename.lower().split('.')[-1]
            if extension not in allowed_extensions:
                return False
        
        # Basic content validation (no executable headers)
        dangerous_headers = [
            b'\x4d\x5a',  # PE executable
            b'\x7f\x45\x4c\x46',  # ELF executable
            b'\xca\xfe\xba\xbe',  # Mach-O executable
        ]
        
        for header in dangerous_headers:
            if content.startswith(header):
                return False
        
        return True


class SecurityHeaders:
    """Security headers for HTTP responses."""
    
    DEFAULT_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "media-src 'self'; "
            "frame-src 'none';"
        )
    }
    
    @classmethod
    def add_security_headers(cls, response):
        """Add security headers to HTTP response.
        
        Args:
            response: Flask response object
            
        Returns:
            Response with security headers added
        """
        for header, value in cls.DEFAULT_HEADERS.items():
            response.headers[header] = value
        return response

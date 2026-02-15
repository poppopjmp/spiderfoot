#!/usr/bin/env python3
"""
Security Middleware Integration
================================

This module provides comprehensive security middleware integration for SpiderFoot
web and API interfaces, combining all security modules into a cohesive system.

Features:
- FastAPI middleware integration
- Automatic security header injection
- Request/response security processing
- Centralized security configuration

Author: SpiderFoot Security Team
"""
from __future__ import annotations

import logging
import time
from typing import Any
import json

from ..input_validation import InputValidator
from ..rate_limiting import RateLimiter
from ..session_security import SessionManager
from .security_logging import SecurityLogger, SecurityEventType
from ..secure_config import SecureConfigManager

# Optional Flask-dependent imports
try:
    from ..api_security import APIKeyManager, JWTManager
except ImportError:
    APIKeyManager = None  # type: ignore
    JWTManager = None  # type: ignore


class SecurityConfigDefaults:
    """Default security configuration values."""

    WEB_SECURITY = {
        'CSRF_ENABLED': True,
        'RATE_LIMITING_ENABLED': True,
        'SECURE_SESSIONS': True,
        'AUTHENTICATION_REQUIRED': False,
        'SESSION_TIMEOUT': 60,
        'SESSION_SECURE': True,
        'SESSION_HTTPONLY': True,
        'SECURITY_LOG_FILE': 'logs/security.log',
        'SSL_ENABLED': False,
        'SSL_CERT_PATH': 'ssl/server.crt',
        'SSL_KEY_PATH': 'ssl/server.key',
        'SSL_CA_PATH': 'ssl/ca.crt',
    }

    API_SECURITY = {
        'JWT_SECRET': None,  # Must be provided
        'TOKEN_EXPIRY': 3600,
        'CORS_ORIGINS': ["https://localhost"],
        'TRUSTED_HOSTS': ["localhost", "127.0.0.1"],
        'RATE_LIMITING_ENABLED': True,
        'API_KEY_ENABLED': True,
        'SCOPES': ['read', 'write', 'admin', 'scan'],
    }

    REDIS_CONFIG = {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'password': None,
    }


def create_security_config(custom_config: dict[str, Any] = None) -> dict[str, Any]:
    """Create security configuration with defaults.

    Args:
        custom_config: Custom configuration to override defaults

    Returns:
        Complete security configuration dictionary
    """
    config = {}
    config.update(SecurityConfigDefaults.WEB_SECURITY)
    config.update(SecurityConfigDefaults.API_SECURITY)
    config['REDIS_CONFIG'] = SecurityConfigDefaults.REDIS_CONFIG.copy()

    if custom_config:
        config.update(custom_config)
        if 'REDIS_CONFIG' in custom_config:
            config['REDIS_CONFIG'].update(custom_config['REDIS_CONFIG'])

    return config


def validate_security_config(config: dict[str, Any]) -> bool:
    """Validate security configuration.

    Args:
        config: Security configuration to validate

    Returns:
        True if configuration is valid

    Raises:
        ValueError: If configuration is invalid
    """
    required_keys = ['SECRET_KEY']

    for key in required_keys:
        if not config.get(key):
            raise ValueError(f"Required security configuration key missing: {key}")

    # Validate JWT secret for API security
    if config.get('API_SECURITY_ENABLED', True) and not config.get('JWT_SECRET'):
        raise ValueError("JWT_SECRET is required for API security")

    # Validate SSL configuration if enabled
    if config.get('SSL_ENABLED', False):
        ssl_keys = ['SSL_CERT_PATH', 'SSL_KEY_PATH']
        for key in ssl_keys:
            if not config.get(key):
                raise ValueError(f"SSL configuration key missing: {key}")

    return True


def get_security_status() -> dict[str, Any]:
    """Get current security status.

    Returns:
        Dictionary with security status information
    """
    return {
        'security_logging': True,
        'timestamp': time.time()
    }


class SpiderFootSecurityMiddleware:
    """
    Main security middleware class for SpiderFoot application.

    This class integrates all security components and provides a unified
    interface for both web and API security management.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize SpiderFoot security middleware.

        Args:
            config: Application configuration dictionary
        """
        self.config = config
        self.log = logging.getLogger(__name__)

        # Initialize security components
        self._init_security_components()

        # Security configuration
        self.security_config = self._get_security_config()

        self.log.info("SpiderFoot security middleware initialized")

    def _init_security_components(self):
        """Initialize all security components."""
        try:
            # Configuration manager
            try:
                self.config_manager = SecureConfigManager(self.config)
            except Exception as e:
                self.log.warning("Failed to initialize config manager: %s", e)
                self.config_manager = None

            # CSRF protection (optional — only needed if csrf_protection module exists)
            try:
                from .csrf_protection import CSRFProtection
                csrf_secret = self.config.get('security.csrf.secret_key')
                if not csrf_secret:
                    import secrets as _secrets
                    csrf_secret = _secrets.token_hex(32)
                    self.log.warning("No CSRF secret configured (security.csrf.secret_key) — using random ephemeral secret")
                self.csrf = CSRFProtection(secret_key=csrf_secret)
            except ImportError:
                self.log.info("CSRF protection module not available (CherryPy removed)")
                self.csrf = None
            except Exception as e:
                self.log.warning("Failed to initialize CSRF protection: %s", e)
                self.csrf = None

            try:
                self.input_validator = InputValidator()
            except Exception as e:
                self.log.warning("Failed to initialize input validator: %s", e)
                self.input_validator = None

            try:
                # Get Redis config from the main config
                redis_config = self.config.get('REDIS_CONFIG', {})
                self.rate_limiter = RateLimiter(
                    redis_host=redis_config.get('host', 'localhost'),
                    redis_port=redis_config.get('port', 6379),
                    redis_db=redis_config.get('db', 0)
                )
            except Exception as e:
                self.log.warning("Failed to initialize rate limiter: %s", e)
                self.rate_limiter = None

            try:
                self.session_manager = SessionManager(self.config)
            except Exception as e:
                self.log.warning("Failed to initialize session manager: %s", e)
                self.session_manager = None

            try:
                self.api_key_manager = APIKeyManager(self.config)
            except Exception as e:
                self.log.warning("Failed to initialize API key manager: %s", e)
                self.api_key_manager = None

            try:
                self.jwt_manager = JWTManager(self.config)
            except Exception as e:
                self.log.warning("Failed to initialize JWT manager: %s", e)
                self.jwt_manager = None

            # Security logger with proper initialization
            log_file = self.config.get('security.logging.log_file', 'logs/security.log')
            try:
                self.security_logger = SecurityLogger(log_file=log_file)
            except Exception as e:
                self.log.warning("Failed to initialize security logger: %s", e)
                self.security_logger = None

            self.log.info("All security components initialized successfully")

        except Exception as e:
            self.log.error("Failed to initialize security components: %s", e)
            # Don't raise exception to prevent complete failure
            self.log.warning("Security middleware will continue with reduced functionality")

    def _get_security_config(self) -> dict[str, Any]:
        """Get security configuration with defaults."""
        return {
            'csrf_enabled': self.config.get('security.csrf.enabled', True),
            'rate_limiting_enabled': self.config.get('security.rate_limiting.enabled', True),
            'input_validation_enabled': self.config.get('security.input_validation.enabled', True),
            'session_security_enabled': self.config.get('security.session_security.enabled', True),
            'api_security_enabled': self.config.get('security.api_security.enabled', True),
            'security_headers_enabled': self.config.get('security.headers.enabled', True),
            'security_logging_enabled': self.config.get('security.logging.enabled', True),
            'bypass_auth_endpoints': self.config.get('security.bypass_auth', [
                '/static', '/favicon.ico', '/robots.txt', '/api/docs', '/api/redoc'
            ])
        }




# FastAPI middleware integration
class FastAPISecurityMiddleware:
    """
    FastAPI security middleware for API protection.
    """

    def __init__(self, middleware: SpiderFootSecurityMiddleware) -> None:
        """
        Initialize FastAPI security middleware.

        Args:
            middleware: Security middleware instance
        """
        self.middleware = middleware
        self.log = logging.getLogger(__name__)

    async def __call__(self, request: Any, call_next: Any) -> Any:
        """Process request through security middleware."""
        try:
            # Get client info
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get('user-agent', '')
            endpoint = str(request.url.path)
            method = request.method

            # Log security event (only for non-static requests)
            if (self.middleware.security_config['security_logging_enabled'] and
                not endpoint.startswith('/static') and
                self.middleware.security_logger is not None):
                try:
                    self.middleware.security_logger.log_security_event(
                        SecurityEventType.REQUEST_PROCESSED,
                        {
                            'action': 'api_request_processed',
                            'endpoint': endpoint,
                            'method': method
                        },
                        severity='INFO',
                        ip_address=client_ip,
                        user_agent=user_agent
                    )
                except Exception as e:
                    # Don't let logging errors break the request
                    self.log.warning("Security logging error: %s", e)

            # Check if endpoint should bypass authentication
            if self._should_bypass_security(endpoint):
                response = await call_next(request)
                return self._add_security_headers(response)

            # Rate limiting
            if (self.middleware.security_config['rate_limiting_enabled'] and
                self.middleware.rate_limiter is not None):
                try:
                    client_id = f"ip:{client_ip}"
                    allowed, rate_info = self.middleware.rate_limiter._check_memory_limit(client_id, 'api')
                    if self.middleware.rate_limiter.redis:
                        try:
                            allowed, rate_info = self.middleware.rate_limiter._check_redis_limit(client_id, 'api')
                        except Exception as e:
                            allowed, rate_info = self.middleware.rate_limiter._check_memory_limit(client_id, 'api')
                    if not allowed:
                        return self._create_error_response(429, "Rate limit exceeded")
                except Exception as e:
                    self.log.warning("Rate limiting error: %s", e)

            # API authentication
            if (self.middleware.security_config['api_security_enabled'] and
                self.middleware.api_key_manager is not None and
                self.middleware.jwt_manager is not None):
                try:
                    auth_result = await self._check_api_authentication(request)
                    if not auth_result['success']:
                        return self._create_error_response(401, auth_result['error'])
                except Exception as e:
                    self.log.warning("API authentication error: %s", e)

            # Input validation
            if (self.middleware.security_config['input_validation_enabled'] and
                method in ['POST', 'PUT', 'PATCH'] and
                self.middleware.input_validator is not None):
                try:
                    validation_result = await self._validate_request_data(request)
                    if not validation_result['success']:
                        return self._create_error_response(400, validation_result['error'])
                except Exception as e:
                    self.log.warning("Input validation error: %s", e)

            # Process request
            response = await call_next(request)

            # Add security headers
            if self.middleware.security_config['security_headers_enabled']:
                try:
                    response = self._add_security_headers(response)
                except Exception as e:
                    self.log.warning("Security headers error: %s", e)

            return response

        except Exception as e:
            self.log.error("FastAPI security middleware error: %s", e)
            return self._create_error_response(500, "Internal security error")

    def _get_client_ip(self, request) -> str:
        """Get client IP address from FastAPI request."""
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip

        return request.client.host if request.client else '127.0.0.1'

    def _should_bypass_security(self, endpoint: str) -> bool:
        """Check if endpoint should bypass security checks."""
        bypass_endpoints = self.middleware.security_config['bypass_auth_endpoints']
        return any(endpoint.startswith(bp) for bp in bypass_endpoints)

    async def _check_api_authentication(self, request) -> dict[str, Any]:
        """Check API authentication."""
        try:
            # Check for API key in header
            api_key = request.headers.get('X-API-Key')
            if api_key and self.middleware.api_key_manager is not None:
                if self.middleware.api_key_manager.validate_api_key(api_key):
                    return {'success': True}
                else:
                    return {'success': False, 'error': 'Invalid API key'}

            # Check for JWT token
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer ') and self.middleware.jwt_manager is not None:
                token = auth_header[7:]  # Remove 'Bearer ' prefix
                validation_result = self.middleware.jwt_manager.validate_token(token)
                if validation_result['valid']:
                    return {'success': True}
                else:
                    return {'success': False, 'error': 'Invalid JWT token'}

            return {'success': False, 'error': 'No authentication provided'}

        except Exception as e:
            self.log.error("API authentication error: %s", e)
            return {'success': False, 'error': 'Authentication check failed'}

    async def _validate_request_data(self, request) -> dict[str, Any]:
        """Validate request data."""
        try:
            # Validate query parameters
            for key, value in request.query_params.items():
                if (self.middleware.input_validator is not None and
                    not self.middleware.input_validator.validate_input(str(value))):
                    return {'success': False, 'error': f'Invalid query parameter: {key}'}

            # Validate JSON body if present
            if request.headers.get('content-type') == 'application/json':
                try:
                    body = await request.json()
                    if (self.middleware.input_validator is not None and
                        not self.middleware.input_validator.validate_json_input(body)):
                        return {'success': False, 'error': 'Invalid JSON input'}
                except Exception as e:
                    return {'success': False, 'error': 'Invalid JSON format'}

            return {'success': True}

        except Exception as e:
            self.log.error("Request validation error: %s", e)
            return {'success': False, 'error': 'Validation failed'}

    def _add_security_headers(self, response):
        """Add security headers to FastAPI response."""
        try:
            # Import SecurityHeaders from input_validation module
            from ..input_validation import SecurityHeaders

            # Add default security headers
            for header, value in SecurityHeaders.DEFAULT_HEADERS.items():
                response.headers[header] = value
            return response
        except Exception as e:
            self.log.warning("Failed to add security headers: %s", e)
            return response

    def _create_error_response(self, status_code: int, message: str):
        """Create error response."""
        from fastapi import Response
        import json

        content = json.dumps({
            'error': message,
            'status': status_code,
            'timestamp': time.time()
        })

        return Response(
            content=content,
            status_code=status_code,
            media_type='application/json'
        )


def install_fastapi_security(app: Any, config: dict[str, Any]) -> SpiderFootSecurityMiddleware:
    """
    Install security middleware for FastAPI.

    Args:
        app: FastAPI application instance
        config: SpiderFoot configuration dictionary

    Returns:
        Security middleware instance
    """
    try:
        middleware = SpiderFootSecurityMiddleware(config)
        security_middleware = FastAPISecurityMiddleware(middleware)

        app.middleware("http")(security_middleware)

        logging.getLogger(__name__).info("FastAPI security middleware installed successfully")
        return middleware

    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to install FastAPI security middleware: {e}")
        raise

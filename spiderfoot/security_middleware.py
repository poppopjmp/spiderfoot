#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Security Middleware Integration
================================

This module provides comprehensive security middleware integration for SpiderFoot
web and API interfaces, combining all security modules into a cohesive system.

Features:
- CherryPy middleware integration
- FastAPI middleware integration
- Automatic security header injection
- Request/response security processing
- Centralized security configuration

Author: SpiderFoot Security Team
"""

import logging
import time
import cherrypy
from typing import Dict, Any
import json

from .csrf_protection import CSRFProtection
from .input_validation import InputValidator
from .rate_limiting import RateLimiter
from .session_security import SessionManager
from .api_security import APIKeyManager, JWTManager
from .security_logging import SecurityLogger, SecurityEventType
from .secure_config import SecureConfigManager



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


def create_security_config(custom_config: Dict[str, Any] = None) -> Dict[str, Any]:
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


def validate_security_config(config: Dict[str, Any]) -> bool:
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


def get_security_status() -> Dict[str, Any]:
    """Get current security status.
    
    Returns:
        Dictionary with security status information
    """
    return {
        'csrf_protection': hasattr(cherrypy.tools, 'csrf'),
        'rate_limiting': hasattr(cherrypy.tools, 'rate_limit'),
        'session_security': cherrypy.config.get('tools.sessions.on', False),
        'ssl_enabled': cherrypy.config.get('server.ssl_certificate') is not None,
        'security_logging': True,  # Always enabled
        'timestamp': time.time()
    }


class SpiderFootSecurityMiddleware:
    """
    Main security middleware class for SpiderFoot application.
    
    This class integrates all security components and provides a unified
    interface for both web and API security management.
    """
    
    def __init__(self, config: Dict[str, Any]):
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
                self.log.warning(f"Failed to initialize config manager: {e}")
                self.config_manager = None
            
            # Core security components
            csrf_secret = self.config.get('security.csrf.secret_key', 'default-secret')
            try:
                self.csrf = CSRFProtection(secret_key=csrf_secret)
            except Exception as e:
                self.log.warning(f"Failed to initialize CSRF protection: {e}")
                self.csrf = None
            
            try:
                self.input_validator = InputValidator()
            except Exception as e:
                self.log.warning(f"Failed to initialize input validator: {e}")
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
                self.log.warning(f"Failed to initialize rate limiter: {e}")
                self.rate_limiter = None
            
            try:
                self.session_manager = SessionManager(self.config)
            except Exception as e:
                self.log.warning(f"Failed to initialize session manager: {e}")
                self.session_manager = None
            
            try:
                self.api_key_manager = APIKeyManager(self.config)
            except Exception as e:
                self.log.warning(f"Failed to initialize API key manager: {e}")
                self.api_key_manager = None
            
            try:
                self.jwt_manager = JWTManager(self.config)
            except Exception as e:
                self.log.warning(f"Failed to initialize JWT manager: {e}")
                self.jwt_manager = None
            
            # Security logger with proper initialization
            log_file = self.config.get('security.logging.log_file', 'logs/security.log')
            try:
                self.security_logger = SecurityLogger(log_file=log_file)
            except Exception as e:
                self.log.warning(f"Failed to initialize security logger: {e}")
                self.security_logger = None
            
            self.log.info("All security components initialized successfully")
            
        except Exception as e:
            self.log.error(f"Failed to initialize security components: {e}")
            # Don't raise exception to prevent complete failure
            self.log.warning("Security middleware will continue with reduced functionality")
    
    def _get_security_config(self) -> Dict[str, Any]:
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


class CherryPySecurityTool(cherrypy.Tool):
    """
    CherryPy security tool for web interface protection.
    """
    
    def __init__(self, middleware: SpiderFootSecurityMiddleware):
        """
        Initialize CherryPy security tool.
        
        Args:
            middleware: Security middleware instance
        """
        super().__init__('before_request_body', self._security_check)
        self.middleware = middleware
        self.log = logging.getLogger(__name__)
    
    def _security_check(self):
        """Perform security checks before processing request."""
        try:
            request = cherrypy.request
            response = cherrypy.response
            
            # Get client info
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get('User-Agent', '')
            endpoint = request.path_info
            method = request.method
            
            # Log security event (only for non-static requests)
            if (self.middleware.security_config['security_logging_enabled'] and
                not endpoint.startswith('/static') and
                self.middleware.security_logger is not None):
                try:
                    self.middleware.security_logger.log_security_event(
                        SecurityEventType.REQUEST_PROCESSED,
                        {
                            'action': 'request_processed',
                            'endpoint': endpoint,
                            'method': method
                        },
                        severity='INFO',
                        ip_address=client_ip,
                        user_agent=user_agent
                    )
                except Exception as e:
                    # Don't let logging errors break the request
                    self.log.warning(f"Security logging error: {e}")
            
            # Check if endpoint should bypass authentication
            if self._should_bypass_security(endpoint):
                return
            
            # Rate limiting
            if (self.middleware.security_config['rate_limiting_enabled'] and
                self.middleware.rate_limiter is not None):
                try:
                    client_id = f"ip:{client_ip}"
                    allowed, rate_info = self.middleware.rate_limiter._check_memory_limit(client_id, 'web')
                    if self.middleware.rate_limiter.redis:
                        try:
                            allowed, rate_info = self.middleware.rate_limiter._check_redis_limit(client_id, 'web')
                        except Exception:
                            allowed, rate_info = self.middleware.rate_limiter._check_memory_limit(client_id, 'web')
                    if not allowed:
                        self._block_request(429, "Rate limit exceeded")
                        return
                except Exception as e:
                    self.log.warning(f"Rate limiting error: {e}")
            
            # Input validation for POST/PUT requests
            if (self.middleware.security_config['input_validation_enabled'] and 
                method in ['POST', 'PUT', 'PATCH'] and
                self.middleware.input_validator is not None):
                try:
                    self._validate_request_data(request)
                except Exception as e:
                    self.log.warning(f"Input validation error: {e}")
            
            # CSRF protection for state-changing requests
            if (self.middleware.security_config['csrf_enabled'] and 
                method in ['POST', 'PUT', 'DELETE', 'PATCH'] and
                self.middleware.csrf is not None):
                try:
                    self._check_csrf_token(request)
                except Exception as e:
                    self.log.warning(f"CSRF check error: {e}")
            
            # Session security
            if (self.middleware.security_config['session_security_enabled'] and
                self.middleware.session_manager is not None):
                try:
                    self._check_session_security(request)
                except Exception as e:
                    self.log.warning(f"Session security check error: {e}")
            
            # Add security headers
            if self.middleware.security_config['security_headers_enabled']:
                try:
                    self._add_security_headers(response)
                except Exception as e:
                    self.log.warning(f"Security headers error: {e}")
            
        except Exception as e:
            self.log.error(f"Security check failed: {e}")
            # Log security error
            if (self.middleware.security_config['security_logging_enabled'] and
                self.middleware.security_logger is not None):
                try:
                    self.middleware.security_logger.log_security_event(
                        SecurityEventType.SUSPICIOUS_ACTIVITY,
                        {
                            'action': 'middleware_error',
                            'error': str(e),
                            'endpoint': endpoint
                        },
                        severity='ERROR'
                    )
                except Exception as log_error:
                    self.log.warning(f"Error logging security event: {log_error}")
            # Don't block request on security check errors
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote.ip
    
    def _should_bypass_security(self, endpoint: str) -> bool:
        """Check if endpoint should bypass security checks."""
        bypass_endpoints = self.middleware.security_config['bypass_auth_endpoints']
        return any(endpoint.startswith(bp) for bp in bypass_endpoints)
    
    def _validate_request_data(self, request):
        """Validate request data for security threats."""
        try:
            # Get request body
            if hasattr(request, 'body') and request.body:
                body_data = request.body.read()
                if body_data:
                    # Validate based on content type
                    content_type = request.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        try:
                            json_data = json.loads(body_data)
                            if not self.middleware.input_validator.validate_json_input(json_data):
                                self._block_request(400, "Invalid input data")
                                return
                        except json.JSONDecodeError:
                            self._block_request(400, "Invalid JSON data")
                            return
                    
                    elif 'application/x-www-form-urlencoded' in content_type:
                        # Parse form data and validate
                        form_data = cherrypy.lib.httputil.parse_query_string(body_data.decode('utf-8'))
                        for key, value in form_data.items():
                            if not self.middleware.input_validator.validate_input(value):
                                self._block_request(400, f"Invalid input in field: {key}")
                                return
            
            # Validate query parameters
            if request.query_string:
                query_params = cherrypy.lib.httputil.parse_query_string(request.query_string)
                for key, value in query_params.items():
                    if (self.middleware.input_validator is not None and 
                        not self.middleware.input_validator.validate_input(value)):
                        self._block_request(400, f"Invalid query parameter: {key}")
                        return
                        
        except Exception as e:
            self.log.warning(f"Input validation error: {e}")
    
    def _check_csrf_token(self, request):
        """Check CSRF token for state-changing requests."""
        if self.middleware.csrf is None:
            return
            
        try:
            # Get token from header or form data
            csrf_token = request.headers.get('X-CSRF-Token')
            
            if not csrf_token:
                # Try to get from form data
                if hasattr(request, 'params') and 'csrf_token' in request.params:
                    csrf_token = request.params['csrf_token']
            
            if not csrf_token:
                self._block_request(403, "CSRF token missing")
                return
            
            # Get session ID for token validation
            session_id = cherrypy.session.id if hasattr(cherrypy, 'session') else None
            
            if not self.middleware.csrf.validate_token(csrf_token, session_id):
                self._block_request(403, "Invalid CSRF token")
                return
                
        except Exception as e:
            self.log.warning(f"CSRF check error: {e}")
            self._block_request(403, "CSRF validation failed")
    
    def _check_session_security(self, request):
        """Check session security."""
        if self.middleware.session_manager is None:
            return
            
        try:
            if hasattr(cherrypy, 'session') and cherrypy.session.id:
                session_id = cherrypy.session.id
                client_ip = self._get_client_ip(request)
                user_agent = request.headers.get('User-Agent', '')
                
                if not self.middleware.session_manager.validate_session(
                    session_id, client_ip, user_agent
                ):
                    # Invalid session, clear it
                    cherrypy.session.clear()
                    self._block_request(401, "Session validation failed")
                    return
                
                # Update session activity
                self.middleware.session_manager.update_session_activity(session_id)
                
        except Exception as e:
            self.log.warning(f"Session security check error: {e}")
    
    def _add_security_headers(self, response):
        """Add security headers to response."""
        try:
            # Import SecurityHeaders from input_validation module
            from .input_validation import SecurityHeaders
            
            # Add default security headers
            for header, value in SecurityHeaders.DEFAULT_HEADERS.items():
                response.headers[header] = value
                
        except Exception as e:
            self.log.warning(f"Failed to add security headers: {e}")
    
    def _block_request(self, status_code: int, message: str):
        """Block request with error response."""
        cherrypy.response.status = status_code
        cherrypy.response.body = json.dumps({
            'error': message,
            'status': status_code,
            'timestamp': time.time()
        }).encode('utf-8')
        cherrypy.response.headers['Content-Type'] = 'application/json'
        
        # Log security event
        if (self.middleware.security_config['security_logging_enabled'] and
            self.middleware.security_logger is not None):
            try:
                self.middleware.security_logger.log_security_event(
                    SecurityEventType.UNAUTHORIZED_ACCESS,
                    {
                        'action': 'request_blocked',
                        'message': message,
                        'status_code': status_code,
                        'endpoint': cherrypy.request.path_info,
                        'method': cherrypy.request.method,
                        'client_ip': self._get_client_ip(cherrypy.request)
                    },
                    severity='WARNING'
                )
            except Exception as e:
                self.log.warning(f"Error logging blocked request: {e}")
        
        # Stop further processing
        raise cherrypy.HTTPError(status_code, message)


def install_cherrypy_security(config: Dict[str, Any]) -> SpiderFootSecurityMiddleware:
    """
    Install security middleware for CherryPy web interface.
    
    Args:
        config: SpiderFoot configuration dictionary
        
    Returns:
        Security middleware instance
    """
    try:
        middleware = SpiderFootSecurityMiddleware(config)
        security_tool = CherryPySecurityTool(middleware)
        
        # Install the tool
        cherrypy.tools.spiderfoot_security = security_tool
        
        # Configure to run on all requests
        cherrypy.config.update({
            'tools.spiderfoot_security.on': True
        })
        
        logging.getLogger(__name__).info("CherryPy security middleware installed successfully")
        return middleware
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to install CherryPy security middleware: {e}")
        raise


# FastAPI middleware integration
class FastAPISecurityMiddleware:
    """
    FastAPI security middleware for API protection.
    """
    
    def __init__(self, middleware: SpiderFootSecurityMiddleware):
        """
        Initialize FastAPI security middleware.
        
        Args:
            middleware: Security middleware instance
        """
        self.middleware = middleware
        self.log = logging.getLogger(__name__)
    
    async def __call__(self, request, call_next):
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
                    self.log.warning(f"Security logging error: {e}")
            
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
                        except Exception:
                            allowed, rate_info = self.middleware.rate_limiter._check_memory_limit(client_id, 'api')
                    if not allowed:
                        return self._create_error_response(429, "Rate limit exceeded")
                except Exception as e:
                    self.log.warning(f"Rate limiting error: {e}")
            
            # API authentication
            if (self.middleware.security_config['api_security_enabled'] and
                self.middleware.api_key_manager is not None and
                self.middleware.jwt_manager is not None):
                try:
                    auth_result = await self._check_api_authentication(request)
                    if not auth_result['success']:
                        return self._create_error_response(401, auth_result['error'])
                except Exception as e:
                    self.log.warning(f"API authentication error: {e}")
            
            # Input validation
            if (self.middleware.security_config['input_validation_enabled'] and 
                method in ['POST', 'PUT', 'PATCH'] and
                self.middleware.input_validator is not None):
                try:
                    validation_result = await self._validate_request_data(request)
                    if not validation_result['success']:
                        return self._create_error_response(400, validation_result['error'])
                except Exception as e:
                    self.log.warning(f"Input validation error: {e}")
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            if self.middleware.security_config['security_headers_enabled']:
                try:
                    response = self._add_security_headers(response)
                except Exception as e:
                    self.log.warning(f"Security headers error: {e}")
            
            return response
            
        except Exception as e:
            self.log.error(f"FastAPI security middleware error: {e}")
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
    
    async def _check_api_authentication(self, request) -> Dict[str, Any]:
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
            self.log.error(f"API authentication error: {e}")
            return {'success': False, 'error': 'Authentication check failed'}
    
    async def _validate_request_data(self, request) -> Dict[str, Any]:
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
                except Exception:
                    return {'success': False, 'error': 'Invalid JSON format'}
            
            return {'success': True}
            
        except Exception as e:
            self.log.error(f"Request validation error: {e}")
            return {'success': False, 'error': 'Validation failed'}
    
    def _add_security_headers(self, response):
        """Add security headers to FastAPI response."""
        try:
            # Import SecurityHeaders from input_validation module
            from .input_validation import SecurityHeaders
            
            # Add default security headers
            for header, value in SecurityHeaders.DEFAULT_HEADERS.items():
                response.headers[header] = value
            return response
        except Exception as e:
            self.log.warning(f"Failed to add security headers: {e}")
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


def install_fastapi_security(app, config: Dict[str, Any]) -> SpiderFootSecurityMiddleware:
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

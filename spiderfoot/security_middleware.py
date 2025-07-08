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
from typing import Dict, Any, Optional, Callable
import json

from .csrf_protection import CSRFProtection
from .input_validation import InputValidator
from .rate_limiting import RateLimiter
from .session_security import SessionManager
from .api_security import APIKeyManager, JWTManager
from .security_logging import SecurityLogger
from .secure_config import SecureConfigManager


class SpiderFootSecurityMiddleware:
    """
    Comprehensive security middleware for SpiderFoot applications.
    
    Integrates all security components into a unified middleware system.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize security middleware.
        
        Args:
            config: SpiderFoot configuration dictionary
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
            self.config_manager = SecureConfigManager(self.config)
            
            # Core security components
            csrf_secret = self.config.get('security.csrf.secret_key')
            self.csrf = CSRFProtection(secret_key=csrf_secret)
            
            self.input_validator = InputValidator()
            self.rate_limiter = RateLimiter(self.config)
            self.session_manager = SessionManager(self.config)
            self.api_key_manager = APIKeyManager(self.config)
            self.jwt_manager = JWTManager(self.config)  # This is an alias to APIKeyManager
            
            # Security logger with proper initialization
            log_file = self.config.get('security.logging.log_file', 'logs/security.log')
            self.security_logger = SecurityLogger(log_file=log_file)
            
            self.log.info("All security components initialized successfully")
            
        except Exception as e:
            self.log.error(f"Failed to initialize security components: {e}")
            raise
    
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
            
            # Log security event
            if self.middleware.security_config['security_logging_enabled']:
                self.middleware.security_logger.log_request(
                    client_ip, endpoint, method, user_agent
                )
            
            # Check if endpoint should bypass authentication
            if self._should_bypass_security(endpoint):
                return
            
            # Rate limiting
            if self.middleware.security_config['rate_limiting_enabled']:
                if not self.middleware.rate_limiter.check_web_limit(client_ip):
                    self._block_request(429, "Rate limit exceeded")
                    return
            
            # Input validation for POST/PUT requests
            if (self.middleware.security_config['input_validation_enabled'] and 
                method in ['POST', 'PUT', 'PATCH']):
                self._validate_request_data(request)
            
            # CSRF protection for state-changing requests
            if (self.middleware.security_config['csrf_enabled'] and 
                method in ['POST', 'PUT', 'DELETE', 'PATCH']):
                self._check_csrf_token(request)
            
            # Session security
            if self.middleware.security_config['session_security_enabled']:
                self._check_session_security(request)
            
            # Add security headers
            if self.middleware.security_config['security_headers_enabled']:
                self._add_security_headers(response)
            
        except Exception as e:
            self.log.error(f"Security check failed: {e}")
            # Log security error
            if self.middleware.security_config['security_logging_enabled']:
                self.middleware.security_logger.log_security_error(
                    "middleware_error", str(e), {"endpoint": endpoint}
                )
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
                    if not self.middleware.input_validator.validate_input(value):
                        self._block_request(400, f"Invalid query parameter: {key}")
                        return
                        
        except Exception as e:
            self.log.warning(f"Input validation error: {e}")
    
    def _check_csrf_token(self, request):
        """Check CSRF token for state-changing requests."""
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
            headers = self.middleware.input_validator.get_security_headers()
            for header, value in headers.items():
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
        if self.middleware.security_config['security_logging_enabled']:
            self.middleware.security_logger.log_security_event(
                'request_blocked',
                f"Request blocked: {message}",
                {
                    'status_code': status_code,
                    'endpoint': cherrypy.request.path_info,
                    'method': cherrypy.request.method,
                    'client_ip': self._get_client_ip(cherrypy.request)
                }
            )
        
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
            
            # Log security event
            if self.middleware.security_config['security_logging_enabled']:
                self.middleware.security_logger.log_request(
                    client_ip, endpoint, method, user_agent
                )
            
            # Check if endpoint should bypass authentication
            if self._should_bypass_security(endpoint):
                response = await call_next(request)
                return self._add_security_headers(response)
            
            # Rate limiting
            if self.middleware.security_config['rate_limiting_enabled']:
                if not self.middleware.rate_limiter.check_api_limit(client_ip):
                    return self._create_error_response(429, "Rate limit exceeded")
            
            # API authentication
            if self.middleware.security_config['api_security_enabled']:
                auth_result = await self._check_api_authentication(request)
                if not auth_result['success']:
                    return self._create_error_response(401, auth_result['error'])
            
            # Input validation
            if (self.middleware.security_config['input_validation_enabled'] and 
                method in ['POST', 'PUT', 'PATCH']):
                validation_result = await self._validate_request_data(request)
                if not validation_result['success']:
                    return self._create_error_response(400, validation_result['error'])
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            if self.middleware.security_config['security_headers_enabled']:
                response = self._add_security_headers(response)
            
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
            if api_key:
                if self.middleware.api_key_manager.validate_api_key(api_key):
                    return {'success': True}
                else:
                    return {'success': False, 'error': 'Invalid API key'}
            
            # Check for JWT token
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
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
                if not self.middleware.input_validator.validate_input(str(value)):
                    return {'success': False, 'error': f'Invalid query parameter: {key}'}
            
            # Validate JSON body if present
            if request.headers.get('content-type') == 'application/json':
                try:
                    body = await request.json()
                    if not self.middleware.input_validator.validate_json_input(body):
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
            headers = self.middleware.input_validator.get_security_headers()
            for header, value in headers.items():
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

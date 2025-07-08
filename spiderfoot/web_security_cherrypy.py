# -*- coding: utf-8 -*-
"""
Web Interface Security Integration for SpiderFoot
Integrates all security components into the CherryPy web application.
"""

import cherrypy
from functools import wraps
import os
import time
import json

# Import our security modules
from .csrf_protection import CSRFProtection
from .input_validation import InputValidator, SecurityHeaders
from .rate_limiting import RateLimiter
from .secure_config import SecureConfigManager
from .session_security import SecureSessionManager
from .api_security import APISecurityManager, APIKeyManager
from .security_logging import SecurityLogger, SecurityEventType, SecurityMonitor


class SpiderFootSecurityManager:
    """Main security manager that integrates all security components for CherryPy."""
    
    def __init__(self, app_config: dict = None):
        """Initialize security manager.
        
        Args:
            app_config: CherryPy application configuration
        """
        self.app_config = app_config or {}
        self.csrf_protection = None
        self.rate_limiter = None
        self.config_manager = None
        self.session_manager = None
        self.api_security = None
        self.api_key_manager = None
        self.security_logger = None
        self.security_monitor = None
        
        self.init_security()
    
    def init_security(self) -> None:
        """Initialize security for CherryPy application."""
        self._init_security_logging()
        self._init_csrf_protection()
        self._init_rate_limiting()
        self._init_config_management()
        self._init_session_management()
        self._init_api_security()
        self._init_security_headers()
        self._init_request_validation()
        self._init_error_handlers()
        self._setup_cherrypy_tools()
    
    def _init_security_logging(self) -> None:
        """Initialize security logging."""
        try:
            log_file = self.app_config.get('security_log_file', 'logs/security.log')
            self.security_logger = SecurityLogger(log_file=log_file)
            self.security_monitor = SecurityMonitor(self.security_logger)
        except Exception as e:
            cherrypy.log(f"Failed to initialize security logging: {e}", severity=40)
    
    def _init_csrf_protection(self) -> None:
        """Initialize CSRF protection."""
        try:
            secret_key = self.app_config.get('secret_key', os.environ.get('SECRET_KEY'))
            self.csrf_protection = CSRFProtection(secret_key=secret_key)
        except Exception as e:
            cherrypy.log(f"Failed to initialize CSRF protection: {e}", severity=40)
    
    def _init_rate_limiting(self) -> None:
        """Initialize rate limiting."""
        try:
            redis_config = self.app_config.get('redis', {})
            self.rate_limiter = RateLimiter(
                redis_host=redis_config.get('host', 'localhost'),
                redis_port=redis_config.get('port', 6379),
                redis_db=redis_config.get('db', 0)
            )
        except Exception as e:
            cherrypy.log(f"Failed to initialize rate limiting: {e}", severity=40)
    
    def _init_config_management(self) -> None:
        """Initialize secure configuration management."""
        try:
            self.config_manager = SecureConfigManager()
        except Exception as e:
            cherrypy.log(f"Failed to initialize config management: {e}", severity=40)
    
    def _init_session_management(self) -> None:
        """Initialize secure session management."""
        try:
            redis_config = self.app_config.get('redis', {})
            self.session_manager = SecureSessionManager(
                redis_host=redis_config.get('host', 'localhost'),
                redis_port=redis_config.get('port', 6379)
            )
        except Exception as e:
            cherrypy.log(f"Failed to initialize session management: {e}", severity=40)
    
    def _init_api_security(self) -> None:
        """Initialize API security."""
        try:
            secret_key = self.app_config.get('secret_key', os.environ.get('SECRET_KEY'))
            token_expiry = self.app_config.get('jwt_expiry', 3600)
            self.api_security = APISecurityManager(secret_key=secret_key, token_expiry=token_expiry)
            self.api_key_manager = APIKeyManager(db_instance=None)  # Will need DB instance
        except Exception as e:
            cherrypy.log(f"Failed to initialize API security: {e}", severity=40)
    
    def _init_security_headers(self) -> None:
        """Initialize security headers."""
        try:
            SecurityHeaders.setup_cherrypy_headers()
        except Exception as e:
            cherrypy.log(f"Failed to initialize security headers: {e}", severity=40)
    
    def _init_request_validation(self) -> None:
        """Initialize request validation."""
        # Request validation is handled by CherryPy tools
        pass
    
    def _init_error_handlers(self) -> None:
        """Initialize error handlers for CherryPy."""
        @cherrypy.tools.register('on_start_resource')
        def security_error_handler():
            """Handle security-related errors."""
            def handle_400():
                if self.security_logger:
                    self.security_logger.log_security_event(
                        SecurityEventType.SUSPICIOUS_ACTIVITY,
                        {'error': 'bad_request', 'path': cherrypy.request.path_info},
                        severity='WARNING',
                        ip_address=self._get_client_ip()
                    )
                return self._json_error_response({'error': 'Bad request'}, 400)
            
            def handle_401():
                if self.security_logger:
                    self.security_logger.log_unauthorized_access(
                        cherrypy.request.path_info,
                        ip_address=self._get_client_ip(),
                        reason='Authentication required'
                    )
                return self._json_error_response({'error': 'Unauthorized'}, 401)
            
            def handle_403():
                if self.security_logger:
                    self.security_logger.log_security_event(
                        SecurityEventType.PERMISSION_DENIED,
                        {'path': cherrypy.request.path_info},
                        user_id=getattr(cherrypy.session, 'user_id', None),
                        ip_address=self._get_client_ip(),
                        severity='WARNING'
                    )
                return self._json_error_response({'error': 'Forbidden'}, 403)
            
            def handle_429():
                if self.security_logger:
                    self.security_logger.log_rate_limit_exceeded(
                        cherrypy.request.path_info,
                        'general',
                        user_id=getattr(cherrypy.session, 'user_id', None),
                        ip_address=self._get_client_ip()
                    )
                return self._json_error_response({'error': 'Rate limit exceeded'}, 429)
            
            def handle_500():
                if self.security_logger:
                    self.security_logger.log_security_event(
                        SecurityEventType.SUSPICIOUS_ACTIVITY,
                        {'error': 'internal_server_error', 'path': cherrypy.request.path_info},
                        severity='ERROR',
                        ip_address=self._get_client_ip()
                    )
                return self._json_error_response({'error': 'Internal server error'}, 500)
            
            # Register error handlers
            cherrypy.config.update({
                'error_page.400': handle_400,
                'error_page.401': handle_401,
                'error_page.403': handle_403,
                'error_page.429': handle_429,
                'error_page.500': handle_500,
            })
    
    def _setup_cherrypy_tools(self) -> None:
        """Setup CherryPy tools for security."""
        # Setup security validation tool
        @cherrypy.tools.register('before_handler', priority=50)
        def security_validation():
            """Validate incoming requests for security."""
            try:
                self._validate_incoming_request()
            except cherrypy.HTTPError:
                raise
            except Exception as e:
                cherrypy.log(f"Security validation error: {e}", severity=40)
                raise cherrypy.HTTPError(500, "Security validation failed")
        
        # Setup security headers tool
        @cherrypy.tools.register('before_finalize', priority=60)
        def security_headers():
            """Add security headers to response."""
            try:
                SecurityHeaders.add_headers_to_cherrypy_response()
            except Exception as e:
                cherrypy.log(f"Security headers error: {e}", severity=40)
        
        # Enable tools by default
        cherrypy.config.update({
            'tools.security_validation.on': True,
            'tools.security_headers.on': True,
        })
    
    def _validate_incoming_request(self) -> None:
        """Validate incoming request for security issues."""
        client_ip = self._get_client_ip()
        
        # Check rate limits
        if not self._check_rate_limits():
            raise cherrypy.HTTPError(429, "Rate limit exceeded")
        
        # Check if authentication is required
        if self._requires_authentication() and not self._validate_session():
            raise cherrypy.HTTPError(401, "Authentication required")
        
        # Validate input data
        if cherrypy.request.method in ('POST', 'PUT', 'PATCH'):
            try:
                # Validate request parameters
                if hasattr(cherrypy.request, 'params'):
                    if not InputValidator.validate_request_data(cherrypy.request.params):
                        raise cherrypy.HTTPError(400, "Invalid request data")
            except Exception as e:
                cherrypy.log(f"Input validation error: {e}", severity=40)
                raise cherrypy.HTTPError(400, "Request validation failed")
        
        # Log request if needed
        if self._should_log_request():
            self._log_request()
    
    def _get_client_ip(self) -> str:
        """Get client IP address."""
        # Check for forwarded headers first
        ip = cherrypy.request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        if not ip:
            ip = cherrypy.request.headers.get('X-Real-IP', '')
        if not ip:
            ip = getattr(cherrypy.request, 'remote', {}).get('ip', 'unknown')
        return ip
    
    def _check_rate_limits(self) -> bool:
        """Check if request is within rate limits."""
        if not self.rate_limiter:
            return True
        
        client_ip = self._get_client_ip()
        endpoint_type = self._get_endpoint_type()
        
        try:
            allowed, info = self.rate_limiter.check_rate_limit(endpoint_type)
            return allowed
        except Exception as e:
            cherrypy.log(f"Rate limit check error: {e}", severity=40)
            return True  # Allow on error to avoid blocking legitimate requests
    
    def _get_endpoint_type(self) -> str:
        """Determine endpoint type for rate limiting."""
        path = cherrypy.request.path_info
        if path.startswith('/api/'):
            return 'api'
        elif path.startswith('/login') or path.startswith('/auth'):
            return 'login'
        elif cherrypy.request.method in ('POST', 'PUT', 'DELETE'):
            return 'scan'
        else:
            return 'web'
    
    def _requires_authentication(self) -> bool:
        """Check if the current endpoint requires authentication."""
        path = cherrypy.request.path_info
        
        # Public endpoints that don't require authentication
        public_endpoints = ['/login', '/static', '/css', '/js', '/images', '/favicon.ico']
        
        for endpoint in public_endpoints:
            if path.startswith(endpoint):
                return False
        
        return self.app_config.get('authentication_required', False)
    
    def _validate_session(self) -> bool:
        """Validate session."""
        if not self.session_manager:
            return True  # No session management configured
        
        try:
            session_token = cherrypy.session.get('session_token')
            if not session_token:
                return False
            
            user_agent = cherrypy.request.headers.get('User-Agent', '')
            client_ip = self._get_client_ip()
            
            session_data = self.session_manager.validate_session(
                session_token, user_agent, client_ip
            )
            
            return session_data is not None
        except Exception as e:
            cherrypy.log(f"Session validation error: {e}", severity=40)
            return False
    
    def _should_log_request(self) -> bool:
        """Determine if request should be logged."""
        if not self.security_logger:
            return False
        
        # Log all POST/PUT/DELETE requests
        if cherrypy.request.method in ('POST', 'PUT', 'DELETE'):
            return True
        
        # Log API requests
        if cherrypy.request.path_info.startswith('/api/'):
            return True
        
        # Log admin requests
        if cherrypy.request.path_info.startswith('/admin'):
            return True
        
        return False
    
    def _log_request(self) -> None:
        """Log request details."""
        if not self.security_logger:
            return
        
        try:
            self.security_logger.log_security_event(
                SecurityEventType.API_KEY_CREATED if cherrypy.request.path_info.startswith('/api/') else SecurityEventType.SCAN_CREATED,
                {
                    'method': cherrypy.request.method,
                    'path': cherrypy.request.path_info,
                    'query_string': cherrypy.request.query_string,
                    'user_agent': cherrypy.request.headers.get('User-Agent', '')
                },
                user_id=getattr(cherrypy.session, 'user_id', None),
                ip_address=self._get_client_ip()
            )
        except Exception as e:
            cherrypy.log(f"Request logging error: {e}", severity=40)
    
    def _json_error_response(self, error_data: dict, status_code: int) -> str:
        """Return JSON error response."""
        cherrypy.response.status = status_code
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(error_data)


def create_secure_cherrypy_app(config=None) -> SpiderFootSecurityManager:
    """Create CherryPy app with security configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        SpiderFootSecurityManager instance with security enabled
    """
    # Load default security configuration
    default_config = {
        'secret_key': os.environ.get('SECRET_KEY') or os.urandom(32).hex(),
        'csrf_enabled': True,
        'rate_limiting_enabled': True,
        'secure_sessions': True,
        'authentication_required': False,
        'security_log_file': 'logs/security.log',
        'jwt_expiry': 3600,
        'redis': {
            'host': 'localhost',
            'port': 6379,
            'db': 0
        }
    }
    
    # Override with provided config
    if config:
        default_config.update(config)
    
    # Configure CherryPy security settings
    cherrypy.config.update({
        'tools.sessions.on': True,
        'tools.sessions.timeout': 60,
        'tools.sessions.httponly': True,
        'tools.sessions.secure': default_config.get('session_cookie_secure', True),
        'tools.sessions.samesite': 'Strict',
    })
    
    # Initialize security
    security_manager = SpiderFootSecurityManager(default_config)
    
    return security_manager


# Decorators for route protection
def require_auth(f):
    """Require authentication for route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not cherrypy.session.get('authenticated', False):
            raise cherrypy.HTTPError(401, "Authentication required")
        return f(*args, **kwargs)
    return decorated_function


def require_permission(scope):
    """Require specific permission for route."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_scopes = cherrypy.session.get('scopes', [])
            if scope not in user_scopes:
                raise cherrypy.HTTPError(403, f"Permission '{scope}' required")
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def csrf_protect(f):
    """Require CSRF protection for route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # This will be handled by the CSRF tool
        return f(*args, **kwargs)
    return decorated_function

# -*- coding: utf-8 -*-
"""
Web Interface Security Integration for SpiderFoot
Integrates all security components into the Flask web application.
"""

from flask import Flask, request, g, session, jsonify, render_template
from functools import wraps
import os
import time

# Import our security modules
from .csrf_protection import CSRFProtection
from .input_validation import InputValidator, SecurityHeaders
from .rate_limiting import RateLimiter
from .secure_config import SecureConfigManager
from .session_security import SecureSessionManager
from .api_security import APISecurityManager, APIKeyManager
from .security_logging import SecurityLogger, SecurityEventType, SecurityMonitor


class SpiderFootSecurityManager:
    """Main security manager that integrates all security components."""
    
    def __init__(self, app: Flask = None):
        """Initialize security manager.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        self.csrf_protection = None
        self.rate_limiter = None
        self.config_manager = None
        self.session_manager = None
        self.api_security = None
        self.api_key_manager = None
        self.security_logger = None
        self.security_monitor = None
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Flask) -> None:
        """Initialize security for Flask application.
        
        Args:
            app: Flask application instance
        """
        self.app = app
        
        # Initialize security components
        self._init_security_logging()
        self._init_csrf_protection()
        self._init_rate_limiting()
        self._init_config_management()
        self._init_session_management()
        self._init_api_security()
        self._init_security_headers()
        self._init_request_validation()
        self._init_error_handlers()
        
        # Set up security middleware
        self._setup_before_request()
        self._setup_after_request()
        
        # Store security manager in app
        app.security_manager = self
    
    def _init_security_logging(self) -> None:
        """Initialize security logging."""
        log_file = self.app.config.get('SECURITY_LOG_FILE', 'logs/security.log')
        self.security_logger = SecurityLogger(log_file)
        self.security_monitor = SecurityMonitor(self.security_logger)
        
        self.app.security_logger = self.security_logger
        self.app.security_monitor = self.security_monitor
    
    def _init_csrf_protection(self) -> None:
        """Initialize CSRF protection."""
        if self.app.config.get('CSRF_ENABLED', True):
            secret_key = self.app.config.get('SECRET_KEY') or os.urandom(32)
            self.csrf_protection = CSRFProtection(self.app, secret_key)
    
    def _init_rate_limiting(self) -> None:
        """Initialize rate limiting."""
        if self.app.config.get('RATE_LIMITING_ENABLED', True):
            redis_config = self.app.config.get('REDIS_CONFIG', {})
            self.rate_limiter = RateLimiter(**redis_config)
            self.app.rate_limiter = self.rate_limiter
    
    def _init_config_management(self) -> None:
        """Initialize secure configuration management."""
        master_key = self.app.config.get('MASTER_KEY')
        self.config_manager = SecureConfigManager(master_key)
        self.app.config_manager = self.config_manager
    
    def _init_session_management(self) -> None:
        """Initialize secure session management."""
        if self.app.config.get('SECURE_SESSIONS', True):
            redis_config = self.app.config.get('REDIS_CONFIG', {})
            self.session_manager = SecureSessionManager(**redis_config)
            self.app.session_manager = self.session_manager
    
    def _init_api_security(self) -> None:
        """Initialize API security."""
        secret_key = self.app.config.get('JWT_SECRET_KEY') or self.app.config.get('SECRET_KEY')
        token_expiry = self.app.config.get('JWT_EXPIRY', 3600)
        
        self.api_security = APISecurityManager(secret_key, token_expiry)
        
        # Initialize API key manager if database is available
        if hasattr(self.app, 'database'):
            self.api_key_manager = APIKeyManager(self.app.database)
            self.app.api_key_manager = self.api_key_manager
        
        self.app.api_security = self.api_security
    
    def _init_security_headers(self) -> None:
        """Initialize security headers."""
        @self.app.after_request
        def add_security_headers(response):
            return SecurityHeaders.add_security_headers(response)
    
    def _init_request_validation(self) -> None:
        """Initialize request validation."""
        @self.app.before_request
        def validate_request():
            return self._validate_incoming_request()
    
    def _init_error_handlers(self) -> None:
        """Initialize security-aware error handlers."""
        @self.app.errorhandler(400)
        def handle_bad_request(e):
            self.security_logger.log_security_event(
                SecurityEventType.SUSPICIOUS_ACTIVITY,
                {'error': 'bad_request', 'path': request.path},
                severity='WARNING',
                ip_address=request.remote_addr
            )
            return jsonify({'error': 'Bad request'}), 400
        
        @self.app.errorhandler(401)
        def handle_unauthorized(e):
            self.security_logger.log_unauthorized_access(
                request.path,
                ip_address=request.remote_addr,
                reason='unauthorized'
            )
            return jsonify({'error': 'Unauthorized'}), 401
        
        @self.app.errorhandler(403)
        def handle_forbidden(e):
            self.security_logger.log_unauthorized_access(
                request.path,
                user_id=getattr(g, 'user_id', None),
                ip_address=request.remote_addr,
                reason='forbidden'
            )
            return jsonify({'error': 'Forbidden'}), 403
        
        @self.app.errorhandler(429)
        def handle_rate_limit(e):
            self.security_logger.log_rate_limit_exceeded(
                request.path,
                'unknown',
                user_id=getattr(g, 'user_id', None),
                ip_address=request.remote_addr
            )
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        @self.app.errorhandler(500)
        def handle_internal_error(e):
            self.security_logger.log_security_event(
                SecurityEventType.SUSPICIOUS_ACTIVITY,
                {'error': 'internal_server_error', 'path': request.path},
                severity='ERROR',
                user_id=getattr(g, 'user_id', None),
                ip_address=request.remote_addr
            )
            return jsonify({'error': 'Internal server error'}), 500
    
    def _setup_before_request(self) -> None:
        """Set up before request middleware."""
        @self.app.before_request
        def security_before_request():
            # Store request start time for rate limiting
            g.request_start_time = time.time()
            
            # Extract client information
            g.client_ip = self._get_client_ip()
            g.user_agent = request.headers.get('User-Agent', '')
            
            # Skip security checks for static files
            if request.endpoint and request.endpoint.startswith('static'):
                return
            
            # Check rate limits
            if self.rate_limiter and not self._check_rate_limits():
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            # Validate session for authenticated routes
            if self._requires_authentication():
                if not self._validate_session():
                    return jsonify({'error': 'Authentication required'}), 401
    
    def _setup_after_request(self) -> None:
        """Set up after request middleware."""
        @self.app.after_request
        def security_after_request(response):
            # Add security headers
            response = SecurityHeaders.add_security_headers(response)
            
            # Log request if needed
            if self._should_log_request():
                self._log_request(response)
            
            return response
    
    def _validate_incoming_request(self) -> None:
        """Validate incoming request for security threats."""
        # Check for common attack patterns
        suspicious_patterns = [
            '<script', 'javascript:', 'onload=', 'onerror=',
            'union select', 'drop table', '--', '/*', '*/',
            '<?php', '<%', '%>', 'eval(', 'exec('
        ]
        
        # Check URL and parameters
        full_url = request.url.lower()
        for pattern in suspicious_patterns:
            if pattern in full_url:
                self.security_logger.log_security_event(
                    SecurityEventType.SUSPICIOUS_ACTIVITY,
                    {
                        'type': 'malicious_pattern_in_url',
                        'pattern': pattern,
                        'url': request.url[:200]  # Truncate for logging
                    },
                    severity='ERROR',
                    ip_address=request.remote_addr
                )
                break
        
        # Check request headers
        for header, value in request.headers:
            if any(pattern in value.lower() for pattern in suspicious_patterns):
                self.security_logger.log_security_event(
                    SecurityEventType.SUSPICIOUS_ACTIVITY,
                    {
                        'type': 'malicious_pattern_in_header',
                        'header': header,
                        'value': value[:100]  # Truncate for logging
                    },
                    severity='ERROR',
                    ip_address=request.remote_addr
                )
                break
    
    def _get_client_ip(self) -> str:
        """Get client IP address considering proxies.
        
        Returns:
            Client IP address
        """
        # Check for forwarded headers
        forwarded_headers = [
            'X-Forwarded-For',
            'X-Real-IP',
            'X-Forwarded',
            'Forwarded-For',
            'Forwarded'
        ]
        
        for header in forwarded_headers:
            ip = request.headers.get(header)
            if ip:
                # Take first IP if multiple
                return ip.split(',')[0].strip()
        
        return request.remote_addr or 'unknown'
    
    def _check_rate_limits(self) -> bool:
        """Check rate limits for current request.
        
        Returns:
            True if request is within limits
        """
        if not self.rate_limiter:
            return True
        
        # Determine rate limit type based on path
        if request.path.startswith('/api/'):
            limit_type = 'api'
        elif request.path in ['/login', '/authenticate']:
            limit_type = 'login'
        elif 'scan' in request.path:
            limit_type = 'scan'
        else:
            limit_type = 'web'
        
        return not self.rate_limiter.is_rate_limited(limit_type)
    
    def _requires_authentication(self) -> bool:
        """Check if current route requires authentication.
        
        Returns:
            True if authentication is required
        """
        # Define public endpoints that don't require authentication
        public_endpoints = [
            'static', 'login', 'health', 'status'
        ]
        
        if request.endpoint in public_endpoints:
            return False
        
        # API endpoints require authentication
        if request.path.startswith('/api/'):
            return True
        
        # Check if user authentication is enabled
        return self.app.config.get('AUTHENTICATION_REQUIRED', False)
    
    def _validate_session(self) -> bool:
        """Validate user session.
        
        Returns:
            True if session is valid
        """
        if not self.session_manager:
            return True  # Session management disabled
        
        # Check API authentication for API endpoints
        if request.path.startswith('/api/'):
            return self._validate_api_auth()
        
        # Check web session
        session_token = session.get('session_token')
        if not session_token:
            return False
        
        session_data = self.session_manager.validate_session(
            session_token,
            g.user_agent,
            g.client_ip
        )
        
        if session_data:
            g.user_id = session_data.get('user_id')
            g.session_data = session_data
            return True
        
        return False
    
    def _validate_api_auth(self) -> bool:
        """Validate API authentication.
        
        Returns:
            True if API authentication is valid
        """
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return False
        
        api_key = auth_header[7:]  # Remove 'Bearer ' prefix
        claims = self.api_security.validate_api_key(api_key)
        
        if claims:
            g.user_id = claims.get('user_id')
            g.api_scopes = claims.get('scopes', [])
            g.api_claims = claims
            return True
        
        return False
    
    def _should_log_request(self) -> bool:
        """Determine if request should be logged.
        
        Returns:
            True if request should be logged
        """
        # Log all POST, PUT, DELETE requests
        if request.method in ['POST', 'PUT', 'DELETE']:
            return True
        
        # Log API requests
        if request.path.startswith('/api/'):
            return True
        
        # Log admin requests
        if 'admin' in request.path:
            return True
        
        # Log scan-related requests
        if 'scan' in request.path:
            return True
        
        return False
    
    def _log_request(self, response) -> None:
        """Log request for security audit.
        
        Args:
            response: Flask response object
        """
        request_data = {
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'user_agent': g.user_agent,
            'content_length': response.content_length,
            'processing_time': time.time() - g.request_start_time
        }
        
        # Determine severity based on status code
        if response.status_code >= 500:
            severity = 'ERROR'
        elif response.status_code >= 400:
            severity = 'WARNING'
        else:
            severity = 'INFO'
        
        self.security_logger.log_security_event(
            SecurityEventType.SUSPICIOUS_ACTIVITY,
            {
                'type': 'request_audit',
                'request_data': request_data
            },
            severity=severity,
            user_id=getattr(g, 'user_id', None),
            ip_address=g.client_ip
        )


def create_secure_app(config=None) -> Flask:
    """Create Flask app with security configuration.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Flask app instance with security enabled
    """
    app = Flask(__name__)
    
    # Load default security configuration
    app.config.update({
        'SECRET_KEY': os.environ.get('SECRET_KEY') or os.urandom(32),
        'CSRF_ENABLED': True,
        'RATE_LIMITING_ENABLED': True,
        'SECURE_SESSIONS': True,
        'AUTHENTICATION_REQUIRED': False,
        'SECURITY_LOG_FILE': 'logs/security.log',
        'JWT_EXPIRY': 3600,
        'SESSION_COOKIE_SECURE': True,
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Strict',
    })
    
    # Override with provided config
    if config:
        app.config.update(config)
    
    # Initialize security
    security_manager = SpiderFootSecurityManager(app)
    
    return app


# Decorators for route protection
def require_auth(f):
    """Require authentication for route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'user_id') or not g.user_id:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def require_permission(scope):
    """Require specific permission for route."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'api_scopes'):
                return jsonify({'error': 'API authentication required'}), 401
            
            # Check permission using API security manager
            from flask import current_app
            if hasattr(current_app, 'api_security'):
                claims = getattr(g, 'api_claims', {})
                if not current_app.api_security.check_permission(claims, scope):
                    return jsonify({'error': f'Permission denied. Required: {scope}'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
